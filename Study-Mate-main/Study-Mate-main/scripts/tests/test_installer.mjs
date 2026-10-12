import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { supportsDsh, findPython } from '../../bin/studymate.mjs';
import { adaptSkill } from '../../bin/skill-compat.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const cli = path.join(root, 'bin/studymate.mjs');
const python = findPython();

function fixture(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'studymate-test-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const home = path.join(dir, "家 O'Brien #1");
  const bin = path.join(dir, 'bin');
  fs.mkdirSync(bin, { recursive: true });
  const env = { ...process.env, HOME: home, USERPROFILE: home, DSH_HOME: path.join(home, '.dsh') };
  delete env.LEARN_WORKSPACE;
  const pathKey = Object.keys(env).find(key => key.toLowerCase() === 'path') || 'PATH';
  env[pathKey] = bin + path.delimiter + (env[pathKey] || '');
  const preset = path.join(env.DSH_HOME, '.agent-presets', 'learning', 'agent.cordis.yml');
  const patch = path.join(env.DSH_HOME, 'profiles', 'web', 'cordis.patch.yml');
  const config = path.join(env.DSH_HOME, 'studymate-config.yaml');
  function version(value) {
    fs.writeFileSync(path.join(bin, process.platform === 'win32' ? 'dsh.cmd' : 'dsh'),
      process.platform === 'win32' ? `@echo ${value}\r\n` : `#!/bin/sh\nprintf '%s\\n' '${value}'\n`, { mode: 0o755 });
  }
  function install(...args) {
    return spawnSync(process.execPath, [cli, 'install', ...args], { cwd: dir, env, encoding: 'utf8', timeout: 30000 });
  }
  function yaml(file) {
    const result = spawnSync(python.command, [...python.prefix, '-c',
      'import json,sys,yaml; print(json.dumps(yaml.safe_load(open(sys.argv[1],encoding="utf-8"))))', file], { encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr);
    return JSON.parse(result.stdout);
  }
  version('0.1.7-alpha.1');
  return { dir, home, env, preset, patch, config, version, install, yaml };
}

test('minimum DSH prerelease is compared correctly', () => {
  for (const version of ['0.1.5-rc.2', '0.1.5-rc.10', '0.1.5', '0.1.6-alpha.1', '0.1.7-alpha.1']) assert.ok(supportsDsh(version), version);
  for (const version of ['0.1.4', '0.1.5-alpha.9', '0.1.5-rc.1', 'bad']) assert.equal(supportsDsh(version), false, version);
});

test('installed skill copies get the write-boundary conventions in machine terms', () => {
  const sample = ['暂存模式：`<WS>` = `/tmp/studymate-stage/<slug>`',
    '角色产出走 `<subject_path>/.stage/practice-evaluator-<节点id>/deliver/`',
    'cp -r /tmp/practice-evaluator-<节点id>/deliver/. <subject_path>/'].join('\n');
  const adapted = adaptSkill(sample, {
    platform: 'win32', pythonExecutable: 'C:\\Python\\python.exe',
    configFile: 'C:\\Users\\me\\.dsh\\studymate-config.yaml', tempDirectory: 'C:/Temp',
  });
  assert.ok(!adapted.includes('`/tmp`'), '临时目录应换成本机实值');
  assert.match(adapted, /C:\/Temp\/studymate-stage\/<slug>/);
  assert.match(adapted, /先写科目自己的 `<subject_path>\/\.stage\//);
});

test('install, reinstall and downgrade preserve workspace and unrelated profile configuration', t => {
  const f = fixture(t);
  fs.mkdirSync(path.dirname(f.patch), { recursive: true });
  const original = '# my other plugin\n- id: user-plugin\n  disabled: true\n';
  fs.writeFileSync(f.patch, original);
  const workspace = path.join(f.dir, '学习 [1]');
  let result = f.install('--workspace', workspace);
  assert.equal(result.status, 0, result.stderr);
  let patch = fs.readFileSync(f.patch, 'utf8');
  assert.ok(patch.startsWith(original));
  const row = f.yaml(f.patch).find(row => row.insert)?.insert[0];
  assert.equal(row.name, '@deepseek-ai/dsh-agent-preset');
  assert.equal(row.config.id, 'learning');
  const plugins = [];
  function collect(value) {
    if (!value || typeof value !== 'object') return;
    if (value.id) plugins.push(value);
    for (const child of Object.values(value)) collect(child);
  }
  collect(row.config.plugins);
  assert.equal(plugins.find(plugin => plugin.id === 'workflow-ptc').name, '@deepseek-ai/dsh-workflow-ptc');
  assert.deepEqual(plugins.find(plugin => plugin.id === 'skill-filesystem').config.customSkillDirs,
    [path.join(f.env.DSH_HOME, 'studymate', 'engine', '.dsh', 'skills').split(path.sep).join('/')]);
  assert.match(fs.readFileSync(f.preset, 'utf8'), /@deepseek-ai\/dsh-workflow-ptc/);
  // 安装完必须说清"会话开在哪"：会话目录不在工作区里时，StudyMate 每一步落盘都要授权。
  assert.match(result.stdout, /启动会话时把工作目录设为/);
  // 装出来的技能副本是本机口径：暂存约定保留，`/tmp` 写成这台机器的临时目录
  // （Linux 上两者常常都是 /tmp，所以真正钉住改写的是下面那条注入临时目录的断言）。
  const skillCopy = fs.readFileSync(path.join(f.env.DSH_HOME, 'studymate', 'engine',
    '.dsh', 'skills', 'learning-system', 'SKILL.md'), 'utf8');
  assert.match(skillCopy, /<subject_path>\/\.stage\//);
  assert.ok(skillCopy.includes('.studymate-stage/<slug>'), '暂存根应落在会话目录下');
  const config = f.yaml(f.config);
  config.custom = 'keep';
  fs.writeFileSync(f.config, JSON.stringify(config));
  const notes = path.join(workspace, '.learning', 'subjects', 'notes.md');
  fs.writeFileSync(notes, 'my learning notes');
  result = f.install();
  assert.equal(result.status, 0, result.stderr);
  assert.equal(fs.readFileSync(f.patch, 'utf8'), patch);
  assert.equal(f.yaml(f.config).workspace, fs.realpathSync(workspace));
  assert.equal(f.yaml(f.config).custom, 'keep');
  assert.equal(fs.readFileSync(notes, 'utf8'), 'my learning notes');
  for (const [version, workflow] of [['0.1.6-alpha.1', 'ptc'], ['0.1.5-rc.2', 'worker-thread']]) {
    f.version(version);
    result = f.install();
    assert.equal(result.status, 0, result.stderr);
    assert.equal(fs.readFileSync(f.patch, 'utf8').trim(), original.trim());
    assert.ok(fs.readFileSync(f.preset, 'utf8').includes(`@deepseek-ai/dsh-workflow-${workflow}`));
  }
});

test('workspace paths expand home and resolve relative to the invocation directory', t => {
  const f = fixture(t);
  for (const [workspace, expected] of [
    ['~/学习笔记', path.join(f.home, '学习笔记')],
    ["relative [1] O'Brien # notes", path.join(f.dir, "relative [1] O'Brien # notes")],
  ]) {
    const result = f.install('--workspace', workspace);
    assert.equal(result.status, 0, result.stderr);
    assert.equal(f.yaml(f.config).workspace, fs.realpathSync(expected));
    assert.equal(f.install().status, 0);
    assert.equal(f.yaml(f.config).workspace, fs.realpathSync(expected));
  }
});

test('invalid profile patch fails before replacing a working install', t => {
  const f = fixture(t);
  const result = f.install('--workspace', path.join(f.dir, 'workspace'));
  assert.equal(result.status, 0, result.stderr);
  const before = fs.readFileSync(f.preset, 'utf8');
  const config = fs.readFileSync(f.config, 'utf8');
  fs.writeFileSync(f.patch, 'not: [valid');
  const failed = f.install();
  assert.notEqual(failed.status, 0);
  assert.equal(fs.readFileSync(f.preset, 'utf8'), before);
  assert.equal(fs.readFileSync(f.config, 'utf8'), config);
  assert.equal(fs.readFileSync(f.patch, 'utf8'), 'not: [valid');
  assert.equal(fs.readdirSync(f.env.DSH_HOME).some(name => name.startsWith('.studymate-install-')), false);
});

test('profile option registers only the selected profile and rejects traversal', t => {
  const f = fixture(t);
  assert.notEqual(f.install('--profile', '../outside').status, 0);
  assert.equal(fs.existsSync(f.config), false);
  const result = f.install('--profile', 'headless', '--workspace', path.join(f.dir, 'workspace'));
  assert.equal(result.status, 0, result.stderr);
  assert.equal(fs.existsSync(f.patch), false);
  assert.equal(f.yaml(path.join(f.env.DSH_HOME, 'profiles', 'headless', 'cordis.patch.yml'))[0].insert[0].config.id, 'learning');
});

test('default install manages learning and disables only the selected StudyMate bundle', t => {
  const f = fixture(t);
  fs.mkdirSync(path.dirname(f.patch), { recursive: true });
  const original = '# unrelated plugin\n- id: keep\n  disabled: false\n';
  const manifest = path.join(path.dirname(f.patch), 'package.json');
  const manifestText = JSON.stringify({ dependencies: { '@yunmiao/studymate': '0.1.3' },
    dsh: { profile: { bundles: ['@deepseek-ai/dsh-base', '@yunmiao/studymate'] } } });
  fs.writeFileSync(manifest, manifestText);
  for (const version of ['0.1.7-alpha.1', '0.1.5-rc.2']) {
    f.version(version);
    fs.writeFileSync(f.patch, original);
    const result = f.install('--workspace', path.join(f.dir, 'workspace'));
    assert.equal(result.status, 0, result.stderr + result.stdout);
    const rows = f.yaml(f.patch);
    assert.deepEqual(rows[0], { id: 'keep', disabled: false });
    const guard = rows.find(row => row.id === 'studymate');
    assert.deepEqual(guard, { id: 'studymate', name: '@yunmiao/studymate', disabled: true });
    const declarations = rows.flatMap(row => row.insert || []).filter(row => row.config?.id === 'learning');
    assert.equal(declarations.length, version === '0.1.7-alpha.1' ? 1 : 0);
    assert.equal(fs.readFileSync(manifest, 'utf8'), manifestText);
    assert.ok(fs.existsSync(f.preset));
    assert.equal(f.yaml(f.config).installModes.web, 'standalone');
    const before = fs.readFileSync(f.patch, 'utf8');
    assert.equal(f.install().status, 0);
    assert.equal(fs.readFileSync(f.patch, 'utf8'), before);
  }
});

test('explicit native switch records ownership and removes registration without replacing payload or user files', t => {
  const f = fixture(t);
  fs.mkdirSync(path.dirname(f.patch), { recursive: true });
  const original = '# my other plugin\n- id: unrelated\n  disabled: true\n';
  fs.writeFileSync(f.patch, original);
  const manifest = path.join(path.dirname(f.patch), 'package.json');
  const manifestText = JSON.stringify({ dependencies: { '@yunmiao/studymate': '0.1.3' },
    dsh: { profile: { bundles: ['@yunmiao/studymate'] } } });
  fs.writeFileSync(manifest, manifestText);
  const lockfile = path.join(path.dirname(f.patch), 'pnpm-lock.yaml');
  fs.writeFileSync(lockfile, '# existing package manager lock\n');
  const installed = f.install('--workspace', path.join(f.dir, 'workspace'));
  assert.equal(installed.status, 0, installed.stderr);
  assert.match(fs.readFileSync(f.patch, 'utf8'), /BEGIN STUDYMATE/);
  const engineSentinel = path.join(f.env.DSH_HOME, 'studymate', 'engine', 'keep.txt');
  fs.writeFileSync(engineSentinel, 'existing engine');
  const learningData = path.join(f.yaml(f.config).workspace, '.learning', 'subjects', 'keep.txt');
  fs.writeFileSync(learningData, 'my notes');
  const originalConfig = { ...f.yaml(f.config), custom: 'keep',
    installModes: { ...f.yaml(f.config).installModes, headless: 'standalone' } };
  fs.writeFileSync(f.config, JSON.stringify(originalConfig));
  const untouched = [f.preset, manifest, lockfile, engineSentinel, learningData];
  const before = untouched.map(file => fs.readFileSync(file));
  const switched = f.install('--mode', 'native');
  assert.equal(switched.status, 0, switched.stderr + switched.stdout);
  assert.equal(fs.readFileSync(f.patch, 'utf8'), original);
  untouched.forEach((file, index) => assert.deepEqual(fs.readFileSync(file), before[index], file));
  assert.deepEqual(f.yaml(f.config), { ...originalConfig,
    installModes: { ...originalConfig.installModes, web: 'native' } });
  assert.equal(f.install('--mode', 'native').status, 0);
  assert.equal(fs.readFileSync(f.patch, 'utf8'), original);
});

test('native switch refuses unsupported hosts, missing bundles and invalid modes without changing installation', t => {
  const f = fixture(t);
  const installed = f.install('--workspace', path.join(f.dir, 'workspace'));
  assert.equal(installed.status, 0, installed.stderr);
  const paths = [f.patch, f.config, f.preset];
  const before = paths.map(file => fs.readFileSync(file));
  const checkUnchanged = () => paths.forEach((file, index) => assert.deepEqual(fs.readFileSync(file), before[index], file));
  assert.notEqual(f.install('--mode', 'native').status, 0);
  checkUnchanged();
  const manifest = path.join(path.dirname(f.patch), 'package.json');
  fs.writeFileSync(manifest, JSON.stringify({ dsh: { profile: { bundles: ['@yunmiao/studymate'] } } }));
  f.version('0.1.6-alpha.2');
  const unsupported = f.install('--mode', 'native');
  assert.notEqual(unsupported.status, 0);
  assert.match(unsupported.stderr, /0\.1\.7-alpha\.1/);
  checkUnchanged();
  f.version('0.1.7-alpha.1');
  assert.notEqual(f.install('--mode', 'unexpected').status, 0);
  checkUnchanged();
});
