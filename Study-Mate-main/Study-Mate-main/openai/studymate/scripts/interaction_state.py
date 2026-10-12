#!/usr/bin/env python3
"""Record a StudyMate interaction checkpoint without changing learning progress.

Python 3.9+, standard library only. The workspace must be an explicit absolute
path with an existing .learning directory. State lives in .learning/interaction.json.
Reading an absent state returns revision 0 without writing anything. Updating
replaces the complete business state, requiring the revision from the last read.
The helper adds schema_version=1 and increments revision. It never records mastery.

Examples (replace /absolute/StudyMate with your actual workspace):
  python interaction_state.py --workspace /absolute/StudyMate read
  python interaction_state.py --workspace /absolute/StudyMate update --input next.json --expected-revision 0
  python interaction_state.py --workspace /absolute/StudyMate answer --question-id goal-1 --input reply.json --expected-revision 1

An executable next.json example (all seven fields are required):
{
  "active_subject": null,
  "phase": "clarify",
  "node_id": null,
  "intent": "Learn linear algebra",
  "answers": {"weekly_hours": 4},
  "pending": {
    "id": "goal-1", "kind": "preference", "topic": "learning_goal",
    "question": "What would you like to focus on?",
    "options": [{"id": "theory", "label": "Theory"}, {"id": "applications", "label": "Applications"}],
    "resume_phase": "plan"
  },
  "next_action": "Wait for the learning goal, then propose a plan"
}

For the answer command, reply.json contains the actual JSON reply value, such as
"Applications" or {"selected": ["applied"], "comment": "Prefer concrete examples"}.
It consumes only the matching pending question, records answers[question_id] as
{"topic": pending.topic, "value": reply}, resumes pending.resume_phase, and clears
pending. next_action changes to continuing the resumed phase with the received
answer. Empty replies, stale revisions, and late or duplicate replies are rejected.
Success prints the complete state as JSON and exits 0; errors go to stderr and
exit nonzero without replacing state. Interpretation of a recorded reply remains
the controller's job; no answer updates mastery or progress.

The update command supports corrections, clearing pending with null, or replacing
it completely after a changed user request. Question IDs must be unique across
questions; an ID already recorded in answers cannot be consumed again. Options may
be empty for free-text questions. Use --forbid-root ABS to exclude additional
plugin/cache locations. Plugin roots and known Codex/Agents plugin caches are
always excluded.

Updates use an exclusive, non-waiting .learning/.interaction.lock and atomic file
replacement. A competing update or stale revision fails without overwriting state.
After a process crash, inspect the lock and remove it only after confirming that
no update process is running; this helper never steals or waits for an existing lock.
"""
import argparse
import json
import os
from pathlib import Path
import stat
import sys
import tempfile


SCHEMA_VERSION = 1
PHASES = frozenset(('clarify', 'plan', 'produce', 'learn', 'practice', 'review', 'paused'))
FIELDS = frozenset(('active_subject', 'phase', 'node_id', 'intent', 'answers', 'pending', 'next_action'))
PENDING_FIELDS = frozenset(('id', 'kind', 'topic', 'question', 'options', 'resume_phase'))


class StateError(ValueError):
    """Invalid input, unsafe location, incompatible state, or update conflict."""


def initial_state():
    return dict(schema_version=SCHEMA_VERSION, revision=0, active_subject=None,
                phase='clarify', node_id=None, intent='', answers={}, pending=None,
                next_action='')


def inside(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def absolute_path(value, label):
    path = Path(value)
    if not path.is_absolute():
        raise StateError(f'{label} must be an explicit absolute path')
    return path


def workspace_path(value, forbid_roots=()):
    requested = absolute_path(value, '--workspace')
    workspace = requested.resolve(strict=True)
    if not workspace.is_dir():
        raise StateError('workspace must be an existing directory')
    forbidden = [Path(__file__).resolve().parents[1]]
    forbidden.extend(absolute_path(root, '--forbid-root').resolve() for root in forbid_roots)
    for candidate in (requested, workspace):
        parts = tuple(part.casefold() for part in candidate.parts)
        if any(parts[i:i + 3] in (('.codex', 'plugins', 'cache'), ('.agents', 'plugins', 'cache'))
               for i in range(len(parts) - 2)):
            raise StateError('workspace cannot be inside a plugin cache')
        if any(inside(candidate, root) for root in forbidden):
            raise StateError('workspace cannot be inside a plugin or forbidden root')
    for ancestor in (workspace, *workspace.parents):
        if (ancestor / '.codex-plugin' / 'plugin.json').is_file() or (ancestor / '.plugin' / 'plugin.json').is_file():
            raise StateError('workspace cannot be inside a plugin root')
    learning = workspace / '.learning'
    if learning.is_symlink() or not learning.is_dir() or not inside(learning.resolve(), workspace):
        raise StateError('workspace must have an existing .learning directory without a symlink or escaped path')
    return workspace


def require_text(value, field, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise StateError(f'{field} must be {"a string" if allow_empty else "a nonempty string"}')


def validate_business(data, workspace):
    if not isinstance(data, dict) or set(data) != FIELDS:
        raise StateError('input must contain exactly these business fields: ' + ', '.join(sorted(FIELDS)))
    subject = data['active_subject']
    if subject is not None:
        require_text(subject, 'active_subject')
        if subject in ('.', '..') or any(char in subject for char in '/\\:\0'):
            raise StateError('active_subject must be a single relative subject slug')
        subjects = workspace / '.learning' / 'subjects'
        target = subjects / subject
        if subjects.is_symlink() or target.is_symlink() or not inside(target.resolve(), subjects.resolve()):
            raise StateError('active_subject cannot escape subjects or use a symlink')
        if not inside(subjects.resolve(), workspace / '.learning'):
            raise StateError('subjects cannot escape the workspace')
    if not isinstance(data['phase'], str) or data['phase'] not in PHASES:
        raise StateError('phase must be one of: ' + ', '.join(sorted(PHASES)))
    if data['node_id'] is not None:
        require_text(data['node_id'], 'node_id')
    require_text(data['intent'], 'intent', allow_empty=True)
    require_text(data['next_action'], 'next_action', allow_empty=True)
    if not isinstance(data['answers'], dict):
        raise StateError('answers must be a JSON object')
    pending = data['pending']
    if pending is None:
        return
    if data['phase'] == 'paused':
        raise StateError('paused state must clear pending before saving')
    if not isinstance(pending, dict) or set(pending) != PENDING_FIELDS:
        raise StateError('pending must be null or contain exactly: ' + ', '.join(sorted(PENDING_FIELDS)))
    for field in ('id', 'topic', 'question'):
        require_text(pending[field], 'pending.' + field)
    if pending['kind'] not in ('preference', 'learning_check'):
        raise StateError('pending.kind must be preference or learning_check')
    if not isinstance(pending['resume_phase'], str) or pending['resume_phase'] not in PHASES:
        raise StateError('pending.resume_phase must be a supported phase')
    if not isinstance(pending['options'], list):
        raise StateError('pending.options must be an array')
    option_ids = set()
    for option in pending['options']:
        if not isinstance(option, dict) or set(option) != {'id', 'label'}:
            raise StateError('each pending option must contain exactly id and label')
        require_text(option['id'], 'option.id')
        require_text(option['label'], 'option.label')
        if option['id'] in option_ids:
            raise StateError('pending option ids must be unique')
        option_ids.add(option['id'])


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise StateError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def reject_constant(value):
    raise StateError(f'non-JSON numeric value: {value}')


def load_json(file):
    with open(file, encoding='utf-8') as handle:
        return json.load(handle, object_pairs_hook=unique_object, parse_constant=reject_constant)


def read_state(workspace):
    file = workspace / '.learning' / 'interaction.json'
    try:
        file_stat = file.lstat()
    except FileNotFoundError:
        return initial_state()
    if not stat.S_ISREG(file_stat.st_mode) or file.is_symlink():
        raise StateError('interaction.json must be a regular file without a symlink')
    data = load_json(file)
    if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] != SCHEMA_VERSION:
        raise StateError('unsupported or missing interaction schema_version; existing state was not changed')
    if type(data.get('revision')) is not int or data['revision'] < 0:
        raise StateError('invalid interaction revision; existing state was not changed')
    validate_business({key: value for key, value in data.items() if key not in ('schema_version', 'revision')}, workspace)
    return data


def change_state(workspace, expected_revision, change):
    if type(expected_revision) is not int or expected_revision < 0:
        raise StateError('expected revision must be a nonnegative integer')
    lock = workspace / '.learning' / '.interaction.lock'
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise StateError(f'update locked: {lock}; no waiting or state changes were performed') from None
    temporary = None
    committed = False
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            handle.write(str(os.getpid()) + '\n')
        current = read_state(workspace)
        if current['revision'] != expected_revision:
            raise StateError(f'revision conflict: expected {expected_revision}, found {current["revision"]}; read again before updating')
        data = change(current)
        validate_business(data, workspace)
        updated = dict(data, schema_version=SCHEMA_VERSION, revision=expected_revision + 1)
        descriptor, name = tempfile.mkstemp(prefix='.interaction-', suffix='.tmp', dir=lock.parent)
        temporary = Path(name)
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as handle:
            json.dump(updated, handle, ensure_ascii=False, allow_nan=False, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, lock.parent / 'interaction.json')
        temporary = None
        committed = True
        return updated
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        try:
            lock.unlink()
        except OSError as error:
            if not committed:
                raise
            # The atomic commit already succeeded. Report the saved revision as
            # success instead of falsely inviting the caller to repeat an answer.
            print(f'interaction state saved; could not remove update lock {lock}: {error}', file=sys.stderr)


def update_state(workspace, data, expected_revision):
    validate_business(data, workspace)
    return change_state(workspace, expected_revision, lambda current: data)


def has_answer(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(has_answer(item) for item in value.values())
    if isinstance(value, list):
        return any(has_answer(item) for item in value)
    return True  # Explicit JSON false and 0 are answers, unlike silence.


def answer_state(workspace, question_id, value, expected_revision):
    require_text(question_id, 'question id')
    if not has_answer(value):
        raise StateError('empty answer: silence or an empty reply cannot consume a pending question')

    def consume(current):
        pending = current['pending']
        if pending is None:
            raise StateError('no pending question: late or duplicate answer was not recorded')
        if pending['id'] != question_id:
            raise StateError(f'question conflict: expected pending id {pending["id"]!r}, received {question_id!r}')
        if question_id in current['answers']:
            raise StateError(f'question {question_id!r} was already answered; use a new id for a new question')
        data = {key: current[key] for key in FIELDS}
        data['answers'] = dict(current['answers'])
        data['answers'][question_id] = {'topic': pending['topic'], 'value': value}
        data['phase'] = pending['resume_phase']
        data['pending'] = None
        data['next_action'] = f'根据已收到的 {pending["topic"]} 回答继续 {pending["resume_phase"]}'
        return data

    return change_state(workspace, expected_revision, consume)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--workspace', required=True, metavar='ABS', help='explicit absolute learning workspace with an existing .learning directory')
    parser.add_argument('--forbid-root', action='append', default=[], metavar='ABS', help='additional root that cannot contain the workspace; may be repeated')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('read', help='read state, or return unwritten revision 0 defaults')
    update = commands.add_parser('update', help='replace the complete business state using optimistic concurrency')
    update.add_argument('--input', required=True, metavar='JSONFILE', help='JSON containing the seven business fields, without schema_version or revision')
    update.add_argument('--expected-revision', required=True, type=int, metavar='N', help='revision returned by the last read (initially 0)')
    answer = commands.add_parser('answer', help='consume only the matching pending question and record the original JSON reply')
    answer.add_argument('--question-id', required=True, metavar='ID', help='exact pending.id shown to the user')
    answer.add_argument('--input', required=True, metavar='JSONFILE', help='nonempty JSON reply value, such as a string, array, or object')
    answer.add_argument('--expected-revision', required=True, type=int, metavar='N', help='revision containing the pending question')
    args = parser.parse_args(argv)
    try:
        workspace = workspace_path(args.workspace, args.forbid_root)
        if args.command == 'read':
            result = read_state(workspace)
        elif args.command == 'answer':
            result = answer_state(workspace, args.question_id, load_json(args.input), args.expected_revision)
        else:
            result = update_state(workspace, load_json(args.input), args.expected_revision)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
        return 0
    except (StateError, OSError, ValueError) as error:
        print(f'interaction state: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    sys.exit(main())
