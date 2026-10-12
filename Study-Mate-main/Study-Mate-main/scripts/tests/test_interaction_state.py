#!/usr/bin/env python3
"""Portable interaction checkpoints: isolation, continuity, and atomic conflicts."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'openai' / 'studymate' / 'scripts' / 'interaction_state.py'
SPEC = importlib.util.spec_from_file_location('interaction_state', SCRIPT)
state = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(state)


class InteractionStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='studymate-interaction-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.workspace = self.base / "学习 [1] O'Brien # notes"
        self.learning = self.workspace / '.learning'
        self.learning.mkdir(parents=True)
        self.file = self.learning / 'interaction.json'

    def business(self, **changes):
        data = {key: value for key, value in state.initial_state().items() if key in state.FIELDS}
        data.update(intent='学习线性代数', answers={'weekly_hours': 4}, next_action='询问学习目标')
        data.update(changes)
        return data

    def pending(self, **changes):
        result = dict(id='goal-1', kind='preference', topic='learning_goal',
                      question='偏好概念还是应用？', options=[dict(id='theory', label='概念'), dict(id='applied', label='应用')],
                      resume_phase='plan')
        result.update(changes)
        return result

    def input_file(self, data, name='next.json'):
        file = self.base / name
        file.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return file

    def command(self, *args, workspace=None):
        return [sys.executable, '-X', 'utf8', str(SCRIPT), '--workspace', str(workspace or self.workspace), *map(str, args)]

    def run_cli(self, *args, workspace=None):
        return subprocess.run(self.command(*args, workspace=workspace), capture_output=True,
                              text=True, encoding='utf-8', timeout=10)

    def assert_unchanged(self, original):
        self.assertEqual(self.file.read_bytes(), original)
        self.assertFalse((self.learning / '.interaction.lock').exists())
        self.assertEqual(list(self.learning.glob('.interaction-*.tmp')), [])

    def test_first_read_does_not_write(self):
        self.assertEqual(state.workspace_path(str(self.workspace)), self.workspace)
        result = self.run_cli('read')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), state.initial_state())
        self.assertEqual(list(self.learning.iterdir()), [])

    def test_requires_explicit_initialized_workspace(self):
        empty = self.base / 'uninitialized'
        empty.mkdir()
        result = self.run_cli('update', '--input', self.input_file(self.business()), '--expected-revision', 0, workspace=empty)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('existing .learning', result.stderr)
        self.assertEqual(list(empty.iterdir()), [])
        result = subprocess.run([sys.executable, str(SCRIPT), 'read'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        with self.assertRaisesRegex(state.StateError, 'absolute'):
            state.workspace_path('relative-directory')

    def test_save_reopen_and_complete_pending_without_touching_progress(self):
        subject = self.learning / 'subjects' / 'linear-algebra'
        subject.mkdir(parents=True)
        progress = subject / 'progress.yaml'
        progress.write_text('mastery: 0\n', encoding='utf-8')
        pending = self.pending(kind='learning_check', resume_phase='learn')
        data = self.business(active_subject='linear-algebra', phase='practice', node_id='vector.space', pending=pending)
        result = self.run_cli('update', '--input', self.input_file(data), '--expected-revision', 0)
        self.assertEqual(result.returncode, 0, result.stderr)
        reopened = json.loads(self.run_cli('read').stdout)
        self.assertEqual(reopened['revision'], 1)
        self.assertEqual(reopened['pending'], pending)
        self.assertEqual(reopened['node_id'], 'vector.space')
        next_data = {key: reopened[key] for key in state.FIELDS}
        next_data.update(answers={'weekly_hours': 4, 'student_reply': '我的推导如下'}, pending=None, phase='review')
        result = self.run_cli('update', '--input', self.input_file(next_data), '--expected-revision', 1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['revision'], 2)
        self.assertIsNone(json.loads(result.stdout)['pending'])
        self.assertEqual(progress.read_text(encoding='utf-8'), 'mastery: 0\n')

    def test_changed_intent_can_supersede_and_clear_pending(self):
        state.update_state(self.workspace, self.business(pending=self.pending()), 0)
        replacement = self.business(intent='改学概率论', pending=self.pending(id='probability-goal', question='学习概率论的目标是什么？', options=[]))
        saved = state.update_state(self.workspace, replacement, 1)
        self.assertEqual(saved['pending']['id'], 'probability-goal')
        saved = state.update_state(self.workspace, self.business(intent='先暂停', phase='paused', pending=None), 2)
        self.assertIsNone(saved['pending'])
        self.assertEqual(saved['intent'], '先暂停')

    def test_answer_records_original_json_and_resumes_phase(self):
        state.update_state(self.workspace, self.business(pending=self.pending()), 0)
        reply = {'selected': ['applied'], 'comment': '  我想用中文学习，先做应用！  '}
        result = self.run_cli('answer', '--question-id', 'goal-1', '--input', self.input_file(reply), '--expected-revision', 1)
        self.assertEqual(result.returncode, 0, result.stderr)
        saved = json.loads(result.stdout)
        self.assertEqual(saved['revision'], 2)
        self.assertEqual(saved['phase'], 'plan')
        self.assertIsNone(saved['pending'])
        self.assertEqual(saved['answers']['goal-1'], {'topic': 'learning_goal', 'value': reply})
        self.assertEqual(saved['answers']['weekly_hours'], 4)
        self.assertEqual(saved['next_action'], '根据已收到的 learning_goal 回答继续 plan')
        self.assertNotEqual(saved['next_action'], '询问学习目标')
        self.assertEqual(state.read_state(self.workspace), saved)

    def test_late_duplicate_and_consumed_question_ids_cannot_advance(self):
        state.update_state(self.workspace, self.business(pending=self.pending()), 0)
        state.update_state(self.workspace, self.business(pending=self.pending(id='new-goal')), 1)
        original = self.file.read_bytes()
        with self.assertRaisesRegex(state.StateError, 'question conflict'):
            state.answer_state(self.workspace, 'goal-1', '迟到的旧答案', 2)
        self.assert_unchanged(original)
        state.answer_state(self.workspace, 'new-goal', '应用', 2)
        original = self.file.read_bytes()
        with self.assertRaisesRegex(state.StateError, 'no pending question'):
            state.answer_state(self.workspace, 'new-goal', '应用', 3)
        self.assert_unchanged(original)
        data = {key: state.read_state(self.workspace)[key] for key in state.FIELDS}
        data['pending'] = self.pending(id='new-goal')
        state.update_state(self.workspace, data, 3)
        original = self.file.read_bytes()
        with self.assertRaisesRegex(state.StateError, 'already answered'):
            state.answer_state(self.workspace, 'new-goal', '重复答案', 4)
        self.assert_unchanged(original)

    def test_answer_with_stale_revision_is_rejected(self):
        state.update_state(self.workspace, self.business(pending=self.pending()), 0)
        original = self.file.read_bytes()
        result = self.run_cli('answer', '--question-id', 'goal-1', '--input', self.input_file('应用'), '--expected-revision', 0)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('revision conflict', result.stderr)
        self.assert_unchanged(original)

    def test_pausing_clears_pending_and_rejects_its_late_answer(self):
        state.update_state(self.workspace, self.business(pending=self.pending()), 0)
        original = self.file.read_bytes()
        with self.assertRaisesRegex(state.StateError, 'paused state must clear pending'):
            state.update_state(self.workspace, self.business(phase='paused', pending=self.pending()), 1)
        self.assert_unchanged(original)
        state.update_state(self.workspace, self.business(phase='paused', pending=None, next_action='等待学生恢复'), 1)
        original = self.file.read_bytes()
        with self.assertRaisesRegex(state.StateError, 'no pending question'):
            state.answer_state(self.workspace, 'goal-1', '迟到的选择', 2)
        self.assert_unchanged(original)

    def test_empty_answers_cannot_consume_pending(self):
        state.update_state(self.workspace, self.business(pending=self.pending()), 0)
        original = self.file.read_bytes()
        for reply in (None, '', ' \n\t ', [], {}, ['', None], {'reply': ''}):
            with self.subTest(reply=reply):
                result = self.run_cli('answer', '--question-id', 'goal-1', '--input', self.input_file(reply), '--expected-revision', 1)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('empty answer', result.stderr)
                self.assert_unchanged(original)

    def test_explicit_false_and_zero_are_valid_answers(self):
        for index, reply in enumerate((False, 0, ['应用'], '先暂停')):
            with self.subTest(reply=reply):
                revision = index * 2
                question_id = f'question-{index}'
                state.update_state(self.workspace, self.business(pending=self.pending(id=question_id)), revision)
                saved = state.answer_state(self.workspace, question_id, reply, revision + 1)
                self.assertEqual(saved['answers'][question_id]['value'], reply)
                self.assertIsNone(saved['pending'])

    def test_stale_revision_is_rejected_without_changes(self):
        state.update_state(self.workspace, self.business(), 0)
        original = self.file.read_bytes()
        with self.assertRaisesRegex(state.StateError, 'revision conflict'):
            state.update_state(self.workspace, self.business(intent='stale request'), 0)
        self.assert_unchanged(original)

    def test_damaged_or_future_state_cannot_be_overwritten(self):
        for contents in ('{broken', '[]', '{"schema_version": 2}', '{"schema_version": true}',
                         json.dumps(dict(state.initial_state(), revision=-1)),
                         '{"schema_version":1,"schema_version":2}'):
            with self.subTest(contents=contents):
                self.file.write_text(contents, encoding='utf-8')
                original = self.file.read_bytes()
                result = self.run_cli('update', '--input', self.input_file(self.business()), '--expected-revision', 0)
                self.assertNotEqual(result.returncode, 0)
                self.assert_unchanged(original)

    def test_complete_business_state_and_pending_validation(self):
        invalid = []
        missing = self.business()
        del missing['answers']
        invalid.append(missing)
        invalid.extend(self.business(**changes) for changes in (
            {'schema_version': 1}, {'revision': 0}, {'phase': 'mastered'}, {'phase': []},
            {'answers': []}, {'node_id': 12}, {'active_subject': '../outside'},
            {'active_subject': 'nested/subject'}, {'active_subject': 'C:\\outside'},
            {'pending': self.pending(kind='mastery')}, {'pending': self.pending(resume_phase='unknown')},
            {'pending': self.pending(options=[{'id': 'x', 'label': 'A'}, {'id': 'x', 'label': 'B'}])},
            {'pending': self.pending(extra='unsupported')},
        ))
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(state.StateError):
                state.update_state(self.workspace, data, 0)
        self.assertEqual(list(self.learning.iterdir()), [])
        malformed = self.base / 'non-json.json'
        malformed.write_text('{"answers": NaN}', encoding='utf-8')
        with self.assertRaisesRegex(state.StateError, 'non-JSON'):
            state.load_json(malformed)

    def test_existing_lock_fails_immediately_and_is_preserved(self):
        state.update_state(self.workspace, self.business(), 0)
        original = self.file.read_bytes()
        lock = self.learning / '.interaction.lock'
        lock.write_text('another process\n', encoding='utf-8')
        started = time.monotonic()
        result = self.run_cli('update', '--input', self.input_file(self.business()), '--expected-revision', 1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('update locked', result.stderr)
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(lock.read_text(encoding='utf-8'), 'another process\n')
        self.assertEqual(self.file.read_bytes(), original)

    def test_two_processes_cannot_commit_the_same_revision(self):
        files = [self.input_file(self.business(intent=intent), f'{intent}.json') for intent in ('first', 'second')]
        processes = [subprocess.Popen(self.command('update', '--input', file, '--expected-revision', 0),
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
                     for file in files]
        outputs = [process.communicate(timeout=10) for process in processes]
        self.assertEqual(sorted(process.returncode for process in processes), [0, 1], outputs)
        failed = next(output[1] for process, output in zip(processes, outputs) if process.returncode != 0)
        self.assertRegex(failed, 'revision conflict|update locked')
        self.assertEqual(state.read_state(self.workspace)['revision'], 1)
        self.assertIn(state.read_state(self.workspace)['intent'], ('first', 'second'))
        self.assertFalse((self.learning / '.interaction.lock').exists())

    def test_atomic_replace_failure_preserves_previous_state(self):
        state.update_state(self.workspace, self.business(), 0)
        original = self.file.read_bytes()
        with patch.object(state.os, 'replace', side_effect=OSError('simulated replace failure')):
            with self.assertRaisesRegex(OSError, 'replace failure'):
                state.update_state(self.workspace, self.business(intent='new request'), 1)
        self.assert_unchanged(original)

    def test_committed_answer_is_successful_even_if_lock_cleanup_fails(self):
        state.update_state(self.workspace, self.business(pending=self.pending()), 0)
        lock = self.learning / '.interaction.lock'
        original_unlink = Path.unlink

        def fail_lock_cleanup(path, *args, **kwargs):
            if path == lock:
                raise OSError('lock cleanup temporarily unavailable')
            return original_unlink(path, *args, **kwargs)

        warning = io.StringIO()
        with patch.object(Path, 'unlink', fail_lock_cleanup), contextlib.redirect_stderr(warning):
            saved = state.answer_state(self.workspace, 'goal-1', '应用', 1)
        self.assertEqual(saved['revision'], 2)
        self.assertIsNone(saved['pending'])
        self.assertEqual(state.read_state(self.workspace)['answers']['goal-1']['value'], '应用')
        self.assertIn('state saved', warning.getvalue())
        self.assertTrue(lock.exists())
        with self.assertRaisesRegex(state.StateError, 'update locked'):
            state.update_state(self.workspace, self.business(), 2)
        lock.unlink()

    def test_state_and_subject_symlinks_are_rejected(self):
        other = self.base / 'outside.json'
        other.write_text(json.dumps(state.initial_state()), encoding='utf-8')
        try:
            self.file.symlink_to(other)
        except OSError as error:
            self.skipTest(f'symlinks unavailable: {error}')
        original = other.read_bytes()
        with self.assertRaisesRegex(state.StateError, 'symlink'):
            state.update_state(self.workspace, self.business(), 0)
        self.assertEqual(other.read_bytes(), original)
        self.file.unlink()
        outside = self.base / 'outside-subject'
        outside.mkdir()
        subjects = self.learning / 'subjects'
        subjects.mkdir()
        (subjects / 'linked').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(state.StateError, 'symlink'):
            state.update_state(self.workspace, self.business(active_subject='linked'), 0)
        self.assertFalse(self.file.exists())

    def test_plugin_caches_and_additional_roots_are_rejected(self):
        for relative in ('.codex/plugins/cache/studymate/workspace', '.agents/plugins/cache/studymate/workspace'):
            workspace = self.base / relative
            (workspace / '.learning').mkdir(parents=True)
            with self.assertRaisesRegex(state.StateError, 'plugin cache'):
                state.workspace_path(str(workspace))
        plugin = self.base / 'local-plugin'
        (plugin / '.codex-plugin').mkdir(parents=True)
        (plugin / '.codex-plugin' / 'plugin.json').write_text('{}', encoding='utf-8')
        (plugin / 'workspace' / '.learning').mkdir(parents=True)
        with self.assertRaisesRegex(state.StateError, 'plugin root'):
            state.workspace_path(str(plugin / 'workspace'))
        with self.assertRaisesRegex(state.StateError, 'forbidden root'):
            state.workspace_path(str(self.workspace), [str(self.base)])


if __name__ == '__main__':
    unittest.main()
