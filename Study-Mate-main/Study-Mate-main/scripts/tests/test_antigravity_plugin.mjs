import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import { buildAntigravityPlugin } from '../../bin/antigravity-plugin.mjs';
import { findPython } from '../../bin/studymate.mjs';
import { AGENT_ROLES, AGENT_TOOLS } from '../../bin/antigravity-skill-compat.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const python = findPython();
const cli = path.join(root, 'bin/studymate.mjs');

function fixture(t) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'studymate-agy-'));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  return directory;
}

function runPython(args, env = process.env) {
  const result = spawnSync(python.command, [...python.prefix, '-X', 'utf8', ...args], { encoding: 'utf8', env, windowsHide: true });
  assert.equal(result.status, 0, result.error?.message || result.stderr || result.stdout);
  return result.stdout;
}

test('exported Antigravity ZIP contains complete agents, skills, and templates', t => {
  const directory = fixture(t);
  const output = path.join(directory, "输出 Antigravity #1");
  const result = buildAntigravityPlugin({ output, python });
  const extracted = path.join(directory, 'unpacked');
  runPython(['-m', 'zipfile', '-e', result.archive, extracted]);
  const plugin = path.join(extracted, 'studymate');

  // 1. Manifest
  const manifest = JSON.parse(fs.readFileSync(path.join(plugin, 'plugin.json'), 'utf8'));
  assert.equal(manifest.name, 'studymate');
  assert.equal(manifest.displayName, 'StudyMate');
  assert.equal(manifest.version, JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8')).version);

  // 2. Agents (5 dedicated subagents)
  assert.equal(fs.existsSync(path.join(plugin, 'agents')), true);
  for (const role of AGENT_ROLES) {
    const agentFile = path.join(plugin, 'agents', `${role}.md`);
    assert.ok(fs.existsSync(agentFile), `Agent file must exist: ${role}.md`);
    const content = fs.readFileSync(agentFile, 'utf8');
    assert.match(content, /subagent:\s*true/);
    assert.match(content, /mainAgent:\s*false/);
    assert.match(content, /commandExecutionPolicy:\s*auto/);
    for (const tool of AGENT_TOOLS[role]) {
      assert.ok(content.includes(`- ${tool}`), `Agent ${role} must declare tool ${tool}`);
    }
  }

  // Verify rich prompts in agents
  assert.ok(fs.readFileSync(path.join(plugin, 'agents/resource-scout.md'), 'utf8').includes('资料收集准则与分级'));
  assert.ok(fs.readFileSync(path.join(plugin, 'agents/image-scout.md'), 'utf8').includes('采图与编排准则'));
  assert.ok(fs.readFileSync(path.join(plugin, 'agents/curriculum-designer.md'), 'utf8').includes('课程设计核心准则'));
  assert.ok(fs.readFileSync(path.join(plugin, 'agents/learning-coach.md'), 'utf8').includes('课件编写核心准则'));
  assert.ok(fs.readFileSync(path.join(plugin, 'agents/practice-evaluator.md'), 'utf8').includes('四层练习架构'));

  // 3. Skills (12 skills)
  assert.equal(fs.readdirSync(path.join(plugin, 'skills')).length, 12);
  for (const name of fs.readdirSync(path.join(plugin, 'skills'))) {
    const skillContent = fs.readFileSync(path.join(plugin, 'skills', name, 'SKILL.md'), 'utf8');
    const fm = skillContent.match(/^---\n([\s\S]*?)\n---\n/);
    assert.ok(fm, `Skill ${name} must have valid frontmatter`);
    assert.doesNotMatch(fm[1], /disable-model-invocation/, `Skill ${name} must not have disable-model-invocation`);
    assert.doesNotMatch(fm[1], /user-invocable/, `Skill ${name} must not have user-invocable`);
  }
  const controller = fs.readFileSync(path.join(plugin, 'skills/learning-system/SKILL.md'), 'utf8');
  assert.ok(controller.includes('invoke_subagent'), 'Controller should mention invoke_subagent');
  assert.ok(controller.includes('ask_question'), 'Controller should use ask_question');
  assert.ok(controller.includes('Antigravity 宿主约定'), 'Controller should include Antigravity host guide');

  // 3b. Nothing may ship empty: a referenced-but-empty file is a broken plugin.
  const empty = [];
  const collectEmpty = directory => {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const full = path.join(directory, entry.name);
      if (entry.isDirectory()) collectEmpty(full);
      else if (fs.statSync(full).size === 0) empty.push(path.relative(plugin, full));
    }
  };
  collectEmpty(plugin);
  assert.deepEqual(empty, [], `插件内不得有 0 字节文件：${empty.join('、')}`);

  // 4. Rules
  assert.ok(fs.existsSync(path.join(plugin, 'rules/AGENTS.md')), 'rules/AGENTS.md must exist');

  // 5. Assets, templates, schemas, scripts, docs
  for (const asset of [
    'assets/logo.png',
    'templates/lesson.html',
    'templates/home-index.html',
    'templates/subject-index.html',
    'templates/assets/katex/katex.min.js',
    'schemas/curriculum.schema.json',
    'schemas/progress.schema.json',
    'scripts/render_lesson.py',
    'scripts/gen_home.py',
    'scripts/check_lesson.py',
    'docs/文件归属.md',
    'README.md',
    'LICENSE',
  ]) {
    assert.ok(fs.existsSync(path.join(plugin, asset)), `Asset must exist: ${asset}`);
  }

  // 6. Exclude unwanted files
  for (const unwanted of ['node_modules', '.git', 'workspace', '.dsh', 'preset', 'scripts/tests', 'scripts/install_preset.py']) {
    assert.equal(fs.existsSync(path.join(plugin, unwanted)), false, `Unwanted asset present: ${unwanted}`);
  }

  // 7. Verify lesson rendering works standalone using the plugin scripts & templates
  const checkResult = spawnSync(python.command, [
    ...python.prefix,
    path.join(plugin, 'scripts/render_lesson.py'),
    path.join(root, 'examples/.learning/subjects/linear-algebra'),
    'vector.space',
    '--check',
  ], { encoding: 'utf8', windowsHide: true });
  assert.equal(checkResult.status, 0, checkResult.stderr);
});

test('rebuild produces identical Antigravity ZIP bytes', t => {
  const directory = fixture(t);
  const output = path.join(directory, 'output');
  const first = buildAntigravityPlugin({ output, python });
  const firstBytes = fs.readFileSync(first.archive);
  const second = buildAntigravityPlugin({ output, python });
  const secondBytes = fs.readFileSync(second.archive);
  assert.ok(firstBytes.equals(secondBytes), 'ZIP bytes should be deterministic');
});

test('buildAntigravityPlugin refuses output inside source directories', () => {
  assert.throws(() => buildAntigravityPlugin({ output: path.join(root, '.dsh'), python }), /输出目录不能位于构建源文件内/);
  assert.throws(() => buildAntigravityPlugin({ output: path.join(root, 'scripts'), python }), /输出目录不能位于构建源文件内/);
});

test('已被占用的输出目录不会被静默清空', t => {
  const directory = fixture(t);
  const managed = path.join(directory, 'managed');
  const occupied = path.join(managed, 'studymate');
  fs.mkdirSync(occupied, { recursive: true });
  fs.writeFileSync(path.join(occupied, 'important.txt'), 'user data\n');
  assert.throws(() => buildAntigravityPlugin({ output: managed, python }), /输出目录已有非构建文件/);
  assert.equal(fs.readFileSync(path.join(occupied, 'important.txt'), 'utf8'), 'user data\n');

  // 宿主预建的空插件目录（--install 的落点）可以接管
  const empty = path.join(directory, 'empty-install', 'studymate');
  fs.mkdirSync(empty, { recursive: true });
  const result = buildAntigravityPlugin({ output: empty, python });
  assert.equal(result.plugin, empty);
  // 自己上一次的产物可以覆盖
  const again = buildAntigravityPlugin({ output: empty, python });
  assert.equal(again.plugin, empty);
});

test('CLI exports Antigravity plugin via build-antigravity', t => {
  const directory = fixture(t);
  const output = path.join(directory, 'cli-output');
  const result = spawnSync(process.execPath, [cli, 'build-antigravity', '--output', output], {
    encoding: 'utf8', windowsHide: true,
  });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Antigravity 插件已构建/);
  assert.ok(fs.existsSync(path.join(output, 'studymate/plugin.json')));
  assert.ok(fs.existsSync(path.join(output, 'studymate-antigravity.zip')));
});
