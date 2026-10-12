import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import { buildOpenAiPlugin } from '../../bin/openai-plugin.mjs';
import { findPython } from '../../bin/studymate.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const python = findPython();
const cli = path.join(root, 'bin/studymate.mjs');
function fixture(t) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'studymate-openai-'));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  return directory;
}
function runPython(args, env = process.env) {
  const result = spawnSync(python.command, [...python.prefix, '-X', 'utf8', ...args], { encoding: 'utf8', env, windowsHide: true });
  assert.equal(result.status, 0, result.error?.message || result.stderr || result.stdout);
  return result.stdout;
}

test('exported ZIP contains complete portable skills and renders without DSH or source checkout', t => {
  const directory = fixture(t);
  const output = path.join(directory, "输出 O'Brien #1");
  const result = buildOpenAiPlugin({ output, python });
  const extracted = path.join(directory, 'unpacked');
  runPython(['-m', 'zipfile', '-e', result.archive, extracted]);
  const plugin = path.join(extracted, 'studymate');
  const manifest = JSON.parse(fs.readFileSync(path.join(plugin, '.codex-plugin/plugin.json'), 'utf8'));
  assert.equal(manifest.name, 'studymate');
  assert.equal(manifest.version, JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8')).version);
  assert.equal(fs.readdirSync(path.join(plugin, 'skills')).length, 12);
  for (const asset of ['skills/learning-system/SKILL.md', 'skills/learning-system/references/codex-interaction.md',
    'scripts/interaction_state.py', 'assets/logo.png', 'templates/lesson.html', 'templates/assets/katex/fonts/LICENSE', 'schemas/curriculum.schema.json', 'scripts/render_lesson.py', 'docs/文件归属.md', 'requirements.txt']) {
    assert.ok(fs.existsSync(path.join(plugin, asset)), asset);
  }
  for (const unwanted of ['node_modules', '.git', 'workspace', '.dsh', 'preset', 'scripts/tests', 'scripts/install_preset.py']) {
    assert.equal(fs.existsSync(path.join(plugin, unwanted)), false, unwanted);
  }
  const home = path.join(directory, 'empty-home');
  const workspace = path.join(directory, '学习数据');
  const env = { ...process.env, HOME: home, USERPROFILE: home, DSH_HOME: path.join(home, '.dsh'), STUDYMATE_WORKSPACE: workspace };
  delete env.STUDYMATE_CONFIG;
  delete env.LEARN_WORKSPACE;
  fs.mkdirSync(path.join(workspace, '.learning', 'subjects'), { recursive: true });
  // The installed archive, without the source checkout, can recover a pending
  // decision and uses the original skills' invocation policy in valid YAML.
  const state = JSON.parse(runPython([path.join(plugin, 'scripts/interaction_state.py'), '--workspace', workspace, 'read'], env));
  assert.equal(state.revision, 0);
  assert.equal(fs.existsSync(path.join(workspace, '.learning/interaction.json')), false);
  const next = { active_subject: null, phase: 'clarify', node_id: null, intent: '学 Python', answers: {},
    pending: { id: 'python-project-1', kind: 'preference', topic: 'python.project', question: '做哪个项目？',
      options: [{ id: 'csv', label: '表格分析' }], resume_phase: 'plan' }, next_action: '等待项目选择' };
  const input = path.join(directory, 'checkpoint.json');
  fs.writeFileSync(input, JSON.stringify(next));
  const helper = path.join(plugin, 'scripts/interaction_state.py');
  runPython([helper, '--workspace', workspace, 'update', '--input', input, '--expected-revision', '0'], env);
  assert.equal(JSON.parse(runPython([helper, '--workspace', workspace, 'read'], env)).pending.id, 'python-project-1');
  fs.writeFileSync(input, JSON.stringify('分析 CSV 报表'));
  const answered = JSON.parse(runPython([helper, '--workspace', workspace, 'answer', '--question-id', 'python-project-1',
    '--input', input, '--expected-revision', '1'], env));
  assert.equal(answered.phase, 'plan');
  assert.equal(answered.pending, null);
  assert.equal(answered.answers['python-project-1'].value, '分析 CSV 报表');
  const policies = JSON.parse(runPython(['-c',
    'import json,pathlib,sys,yaml; root=pathlib.Path(sys.argv[1]); print(json.dumps({p.parent.parent.name: yaml.safe_load(p.read_text(encoding="utf-8"))["policy"]["allow_implicit_invocation"] for p in root.glob("skills/*/agents/openai.yaml")}))', plugin], env));
  assert.equal(Object.keys(policies).length, 12);
  assert.equal(policies['learning-system'], true);
  for (const role of ['curriculum-designer', 'image-scout', 'learning-coach', 'practice-evaluator', 'resource-scout']) {
    assert.equal(policies[role], false, role);
  }
  runPython([path.join(plugin, 'scripts/gen_home.py')], env);
  assert.ok(fs.existsSync(path.join(workspace, 'index.html')));
  assert.ok(fs.existsSync(path.join(workspace, '.learning/assets/learn-theme.css')));
  assert.equal(fs.existsSync(env.DSH_HOME), false);
  // Render actual lesson content with only resources from the extracted package.
  const subject = path.join(workspace, '.learning/subjects/linear-algebra');
  // Match the installer's workaround for Node 22.19's native Windows Unicode copy.
  fs.cpSync(path.join(root, 'examples/.learning/subjects/linear-algebra'), subject, {
    recursive: true, filter: () => true,
  });
  assert.ok(fs.existsSync(path.join(subject, 'curriculum.yaml')), 'lesson fixture was copied');
  runPython([path.join(plugin, 'scripts/render_lesson.py'), subject, 'vector.space'], env);
  runPython([path.join(plugin, 'scripts/check_lesson.py'), path.join(subject, 'lessons/0001-vector.space.html'), '--subject', subject, '--node', 'vector.space'], env);
});

test('rebuild replaces generated files and creates the same ZIP bytes', t => {
  const output = fixture(t);
  const first = buildOpenAiPlugin({ output, python });
  const bytes = fs.readFileSync(first.archive);
  fs.writeFileSync(path.join(first.plugin, 'obsolete.txt'), 'stale build');
  buildOpenAiPlugin({ output, python });
  assert.equal(fs.existsSync(path.join(first.plugin, 'obsolete.txt')), false);
  assert.deepEqual(fs.readFileSync(first.archive), bytes);
});

test('export refuses unrelated output and build input directories', t => {
  const output = fixture(t);
  fs.mkdirSync(path.join(output, 'studymate'));
  const keep = path.join(output, 'studymate', 'notes.md');
  fs.writeFileSync(keep, 'keep my notes');
  assert.throws(() => buildOpenAiPlugin({ output, python }), /非构建文件/);
  assert.equal(fs.readFileSync(keep, 'utf8'), 'keep my notes');
  assert.throws(() => buildOpenAiPlugin({ output: path.join(root, 'templates', 'export'), python }), /源文件/);
});

test('a failed archive build preserves the previous plugin and ZIP', t => {
  const output = fixture(t);
  const first = buildOpenAiPlugin({ output, python });
  const bytes = fs.readFileSync(first.archive);
  const manifest = fs.readFileSync(path.join(first.plugin, '.codex-plugin/plugin.json'));
  assert.throws(() => buildOpenAiPlugin({ output, python: { command: process.execPath, prefix: ['--invalid-python-test'] } }));
  assert.deepEqual(fs.readFileSync(first.archive), bytes);
  assert.deepEqual(fs.readFileSync(path.join(first.plugin, '.codex-plugin/plugin.json')), manifest);
});

test('an unavailable Windows volume reports an error instead of hanging', { skip: process.platform !== 'win32' }, () => {
  const missing = 'ZYXWVUTSRPONMLKJIHGFEDAB'.split('').map(letter => `${letter}:\\`).find(drive => !fs.existsSync(drive));
  if (missing) assert.throws(() => buildOpenAiPlugin({ output: path.join(missing, 'studymate-export'), python }), /不可访问/);
});

test('CLI exports to requested directory without calling the DSH installer', t => {
  const directory = fixture(t);
  const output = path.join(directory, 'export');
  const dsh = path.join(directory, 'no-dsh');
  const result = spawnSync(process.execPath, [cli, 'build-plugin', '--output', output], {
    env: { ...process.env, DSH_HOME: dsh }, encoding: 'utf8', windowsHide: true,
  });
  assert.equal(result.status, 0, result.stderr);
  assert.ok(fs.existsSync(path.join(output, 'studymate-openai.zip')));
  assert.equal(fs.existsSync(dsh), false);
  const invalid = spawnSync(process.execPath, [cli, 'build-plugin', '--workspace', output], { encoding: 'utf8' });
  assert.equal(invalid.status, 1);
  assert.match(invalid.stderr, /用法/);
});
