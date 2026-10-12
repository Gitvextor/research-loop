import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';
import test from 'node:test';
import { findPython } from '../../bin/studymate.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const python = findPython();
const plugin = pathToFileURL(path.join(root, 'bin/dsh-plugin.mjs')).href;

function fixture(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'studymate-bundle-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const home = path.join(dir, "家 O'Brien #1");
  const dshHome = path.join(home, '.dsh');
  const workspace = path.join(home, '学习资料');
  const env = { ...process.env, HOME: home, USERPROFILE: home, DSH_HOME: dshHome, LEARN_WORKSPACE: workspace };
  const patch = path.join(dshHome, 'profiles', 'web', 'cordis.patch.yml');
  const config = path.join(dshHome, 'studymate-config.yaml');
  const engine = path.join(dshHome, 'studymate', 'engine');
  const run = (code, overrides = {}) => spawnSync(process.execPath, ['--input-type=module', '-e', code], {
    env: { ...env, ...overrides }, encoding: 'utf8', timeout: 30000,
  });
  function boot(overrides = {}, scenario = 'normal', url = plugin) {
    return run(`import { apply } from ${JSON.stringify(url)};
      const scenario = ${JSON.stringify(scenario)};
      const state = {registered: 0, disposed: 0, warnings: []};
      console.warn = message => {state.warnings.push(String(message));};
      const effects = [];
      const ctx = {
        get: () => ({name: 'web', home: process.env.DSH_HOME}),
        agentPresets: {register: async config => {
          state.config = config; state.registered++;
          if (scenario === 'duplicate') throw new Error('Duplicate agent preset: learning');
          return async () => { state.disposed++; };
        }},
        effect: async fn => {effects.push(await fn());},
      };
      try {await apply(ctx); for (const dispose of effects) await dispose();}
      catch (error) {state.error = error.message; process.exitCode = 1;}
      console.log(JSON.stringify(state));`, overrides);
  }
  function yaml(file) {
    const result = spawnSync(python.command, [...python.prefix, '-c',
      'import json,sys,yaml; print(json.dumps(yaml.safe_load(open(sys.argv[1],encoding="utf-8"))))', file], { encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr);
    return JSON.parse(result.stdout);
  }
  return { dir, env, dshHome, workspace, patch, config, engine, run, boot, yaml };
}

function snapshot(dir) {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name)).flatMap(entry => {
    const file = path.join(dir, entry.name);
    return entry.isDirectory()
      ? [[entry.name, 'directory'], ...snapshot(file).map(([name, hash]) => [path.join(entry.name, name), hash])]
      : [[entry.name, createHash('sha256').update(fs.readFileSync(file)).digest('hex')]];
  });
}

test('native loading initializes portable skills and owns the preset lifetime without a dsh subprocess', t => {
  const f = fixture(t);
  const result = f.boot();
  assert.equal(result.status, 0, result.stderr + result.stdout);
  const state = JSON.parse(result.stdout);
  assert.equal(state.registered, 1);
  assert.equal(state.disposed, 1);
  assert.deepEqual(state.warnings, []);
  assert.equal(state.config.id, 'learning');
  assert.deepEqual(state.config.plugins.find(row => row.id === 'tool-bash').disabled,
    { __jsExpr: "process.platform === 'win32'" });
  assert.deepEqual(state.config.plugins.find(row => row.id === 'skill-filesystem').config.customSkillDirs,
    [path.join(f.engine, '.dsh', 'skills').split(path.sep).join('/')]);
  const skills = fs.readFileSync(path.join(f.engine, '.dsh/skills/learning-system/SKILL.md'), 'utf8');
  assert.ok(skills.includes(process.platform === 'win32' ? 'PowerShell' : 'python'));
  assert.equal(fs.existsSync(f.patch), false);
  assert.equal(fs.existsSync(path.join(f.dshHome, '.agent-presets')), false);
  assert.equal(f.yaml(f.config).workspace, fs.realpathSync(f.workspace));
  const data = path.join(f.workspace, '.learning', 'subjects', 'keep.txt');
  fs.writeFileSync(data, 'my learning data');
  const config = { ...f.yaml(f.config), custom: 'keep' };
  fs.writeFileSync(f.config, JSON.stringify(config));
  fs.writeFileSync(path.join(f.engine, 'obsolete.txt'), 'old package');
  const again = f.boot({ LEARN_WORKSPACE: '' });
  assert.equal(again.status, 0, again.stderr + again.stdout);
  assert.equal(f.yaml(f.config).custom, 'keep');
  assert.equal(fs.readFileSync(data, 'utf8'), 'my learning data');
  assert.equal(fs.existsSync(path.join(f.engine, 'obsolete.txt')), false);
});

test('native startup leaves installer-managed registration and payload unchanged', t => {
  const f = fixture(t);
  fs.mkdirSync(path.dirname(f.patch), { recursive: true });
  fs.writeFileSync(f.patch, '# unrelated plugin\n- id: keep\n  disabled: true\n');
  const cliUrl = pathToFileURL(path.join(root, 'bin/studymate.mjs')).href;
  const installed = f.run(`import {installPayload} from ${JSON.stringify(cliUrl)};
    installPayload({version:'0.1.7-alpha.1'});`);
  assert.equal(installed.status, 0, installed.stderr);
  assert.match(fs.readFileSync(f.patch, 'utf8'), /BEGIN STUDYMATE/);
  const data = path.join(f.workspace, '.learning', 'subjects', 'keep.txt');
  fs.writeFileSync(data, 'my learning data');
  const before = snapshot(f.dshHome);
  const attempted = f.boot();
  assert.equal(attempted.status, 0, attempted.stdout + attempted.stderr);
  const state = JSON.parse(attempted.stdout);
  assert.equal(state.registered, 0);
  assert.match(state.warnings.join('\n'), /--mode native/);
  assert.deepEqual(snapshot(f.dshHome), before);
  assert.equal(fs.readFileSync(data, 'utf8'), 'my learning data');
});

test('standalone installation in another profile preserves native Web ownership', t => {
  const f = fixture(t);
  const initial = f.boot();
  assert.equal(initial.status, 0, initial.stdout + initial.stderr);
  assert.equal(JSON.parse(initial.stdout).registered, 1);
  assert.deepEqual(f.yaml(f.config).installModes, { web: 'native' });
  const cliUrl = pathToFileURL(path.join(root, 'bin/studymate.mjs')).href;
  const installed = f.run(`import {installPayload} from ${JSON.stringify(cliUrl)};
    installPayload({version:'0.1.7-alpha.1', profile:'headless'});`);
  assert.equal(installed.status, 0, installed.stderr);
  assert.deepEqual(f.yaml(f.config).installModes, { web: 'native', headless: 'standalone' });
  const headlessPatch = path.join(f.dshHome, 'profiles', 'headless', 'cordis.patch.yml');
  const preset = path.join(f.dshHome, '.agent-presets', 'learning', 'agent.cordis.yml');
  const originalPatch = fs.readFileSync(headlessPatch);
  const originalPreset = fs.readFileSync(preset);
  const restarted = f.boot();
  assert.equal(restarted.status, 0, restarted.stdout + restarted.stderr);
  const state = JSON.parse(restarted.stdout);
  assert.equal(state.registered, 1);
  assert.deepEqual(state.warnings, []);
  assert.deepEqual(f.yaml(f.config).installModes, { web: 'native', headless: 'standalone' });
  assert.deepEqual(fs.readFileSync(headlessPatch), originalPatch);
  assert.deepEqual(fs.readFileSync(preset), originalPreset);
});

test('native startup does not take over an old legacy installer without an ownership marker', t => {
  const f = fixture(t);
  const cliUrl = pathToFileURL(path.join(root, 'bin/studymate.mjs')).href;
  const installed = f.run(`import {installPayload} from ${JSON.stringify(cliUrl)};
    installPayload({version:'0.1.5-rc.2'});`);
  assert.equal(installed.status, 0, installed.stderr);
  assert.equal(fs.existsSync(f.patch), false);
  const oldConfig = f.yaml(f.config);
  delete oldConfig.installModes;
  fs.writeFileSync(f.config, JSON.stringify(oldConfig));
  assert.ok(fs.existsSync(path.join(f.dshHome, '.agent-presets', 'learning', 'agent.cordis.yml')));
  const before = snapshot(f.dshHome);
  const result = f.boot();
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const state = JSON.parse(result.stdout);
  assert.equal(state.registered, 0);
  assert.match(state.warnings.join('\n'), /--mode native/);
  assert.deepEqual(snapshot(f.dshHome), before);
});

test('native startup warns about manual learning declarations without replacing data', t => {
  const f = fixture(t);
  assert.equal(f.boot().status, 0);
  fs.mkdirSync(path.dirname(f.patch), { recursive: true });
  const manual = '- insert:\n  - id: custom-learning\n    name: "@deepseek-ai/dsh-agent-preset"\n    config: {id: learning, plugins: []}\n';
  fs.writeFileSync(f.patch, manual);
  const before = snapshot(f.dshHome);
  const failed = f.boot();
  assert.equal(failed.status, 0, failed.stdout + failed.stderr);
  const state = JSON.parse(failed.stdout);
  assert.equal(state.registered, 0);
  assert.match(state.warnings.join('\n'), /learning/);
  assert.deepEqual(snapshot(f.dshHome), before);
});

test('registry failures are reported without stopping the host or deleting learning data', t => {
  const f = fixture(t);
  assert.equal(f.boot().status, 0);
  const data = path.join(f.workspace, '.learning', 'subjects', 'keep.txt');
  fs.writeFileSync(data, 'my learning data');
  const result = f.boot({}, 'duplicate');
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const state = JSON.parse(result.stdout);
  assert.equal(state.registered, 1);
  assert.equal(state.disposed, 0);
  assert.match(state.warnings.join('\n'), /Duplicate agent preset: learning/);
  assert.equal(fs.readFileSync(data, 'utf8'), 'my learning data');
});

test('missing Python is reported without stopping the host or creating installation files', t => {
  const f = fixture(t);
  const copied = path.join(f.dir, 'dsh-plugin.mjs');
  fs.copyFileSync(path.join(root, 'bin/dsh-plugin.mjs'), copied);
  // Simulate dependency failure at the installer boundary; Windows launchers
  // may find Python even with an empty PATH.
  fs.writeFileSync(path.join(f.dir, 'studymate.mjs'),
    'export function installPayload() { throw new Error("需要 Python 3.9+ 和 PyYAML"); }');
  const result = f.boot({}, 'normal', pathToFileURL(copied).href);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const state = JSON.parse(result.stdout);
  assert.equal(state.registered, 0);
  assert.match(state.warnings.join('\n'), /Python 3\.9\+ 和 PyYAML/);
  assert.equal(fs.existsSync(f.dshHome), false);
});

test('unavailable Python reports the prerequisite on every supported platform', () => {
  for (const platform of ['darwin', 'linux', 'win32']) {
    assert.throws(() => findPython(platform, () => ({ status: 1 })), /没有找到可用的 Python 3\.9\+/);
  }
});

test('Python discovery prefers an interpreter that already has PyYAML', () => {
  const result = findPython('linux', command => {
    if (command === 'python3' || command === 'python') {
      return { status: 0, stdout: JSON.stringify({ executable: `/opt/${command}`, version: [3, 14, 5] }) };
    }
    return { status: command === '/opt/python' ? 0 : 1 };
  });
  assert.deepEqual(result, { command: '/opt/python', prefix: ['-X', 'utf8'] });
});

test('missing PyYAML reports the detected Windows interpreter and its pip command', () => {
  const executable = 'C:\\Python 3.14\\python.exe';
  for (const launcher of ['python3', 'python', 'py']) {
    const invocation = launcher === 'py' ? 'py -3' : launcher;
    assert.throws(() => findPython('win32', command => command === launcher
      ? { status: 0, stdout: JSON.stringify({ executable, version: [3, 14, 5] }) }
      : { status: 1 }), error => {
      assert.match(error.message, /已找到 Python 3\.14\.5/);
      assert.match(error.message, /缺少 PyYAML/);
      assert.ok(error.message.includes(executable));
      assert.ok(error.message.includes(`${invocation} -m pip install PyYAML`));
      assert.ok(error.message.includes(`${invocation} -m ensurepip --upgrade`));
      return true;
    });
  }
});

test('an unsupported Python version is distinguished from a missing interpreter', () => {
  assert.throws(() => findPython('linux', command => command === 'python3'
    ? { status: 0, stdout: JSON.stringify({ executable: '/opt/python3', version: [3, 8, 20] }) }
    : { status: 1 }), /检测到 Python 3\.8\.20，需要 Python 3\.9\+/);
});

test('an old host skips unsupported native loading without blocking startup', async () => {
  const { apply } = await import(plugin);
  const warnings = [];
  const previousWarn = console.warn;
  console.warn = message => warnings.push(String(message));
  try {
    await apply({});
    await apply({ get: () => ({ name: 'web', home: '/unused' }) });
  } finally {
    console.warn = previousWarn;
  }
  assert.equal(warnings.length, 2);
  for (const warning of warnings) {
    assert.match(warning, /0\.1\.7-alpha\.1/);
    assert.match(warning, /npx -y @yunmiao\/studymate@latest install/);
  }
});
