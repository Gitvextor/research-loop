// Real-runtime regression tests. The supplied DSH installation is read-only.
// STUDYMATE_DSH_PACKAGE=/absolute/path/to/@deepseek-ai/dsh \
// STUDYMATE_DSH_EXPECTED_VERSION=0.1.7-alpha.2 node --test scripts/tests/test_dsh_runtime.mjs
// Without STUDYMATE_DSH_PACKAGE these tests skip; normal unit tests need no DSH.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import test from 'node:test';

const self = fileURLToPath(import.meta.url);
const project = path.resolve(path.dirname(self), '../..');
const runtime = process.env.STUDYMATE_DSH_PACKAGE;
const marker = 'STUDYMATE_RUNTIME_RESULT ';

function inside(parent, child) {
  const relative = path.relative(parent, child);
  return relative !== '' && relative !== '..' && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative);
}

function redact(text) {
  return String(text).replace(/https?:\/\/[^\s<>"')]+/g, '[url]')
    .replace(/((?:token|authorization|secret)\s*[=:]\s*)[^\s,;]+/gi, '$1[redacted]');
}

function atLeastRelease(version, minor, patch) {
  const match = /^(\d+)\.(\d+)\.(\d+)/.exec(version);
  assert.ok(match, `Unrecognized DSH version: ${version}`);
  return Number(match[1]) > 0 || Number(match[2]) > minor ||
    Number(match[2]) === minor && Number(match[3]) >= patch;
}

const modern = version => atLeastRelease(version, 1, 7);

async function probe() {
  const stdout = process.stdout.write.bind(process.stdout);
  const quiet = (_chunk, encoding, callback) => {
    const done = typeof encoding === 'function' ? encoding : callback;
    if (done) queueMicrotask(done);
    return true;
  };
  // Web startup prints an access-token URL; only emit our explicit result.
  process.stdout.write = quiet;
  process.stderr.write = quiet;
  const timer = setTimeout(() => {
    stdout(`${marker}${JSON.stringify({ ok: false, error: 'Runtime probe timed out after 45 seconds' })}\n`);
    process.exit(2);
  }, 45000);
  let app;
  let scope;
  let result;
  try {
    assert.ok(runtime && path.isAbsolute(runtime), 'STUDYMATE_DSH_PACKAGE must be absolute');
    const temporary = fs.realpathSync(os.tmpdir());
    const home = fs.realpathSync(os.homedir());
    const dshHome = fs.realpathSync(process.env.DSH_HOME);
    assert.ok(inside(temporary, home), 'Refusing to use a non-temporary HOME');
    assert.ok(inside(home, dshHome), 'DSH_HOME must be inside the isolated HOME');
    assert.ok(inside(home, fs.realpathSync(process.env.LEARN_WORKSPACE)), 'Workspace must be isolated');
    process.chdir(home);

    const manifest = JSON.parse(fs.readFileSync(path.join(runtime, 'package.json'), 'utf8'));
    const isModern = modern(manifest.version);
    const requireRuntime = createRequire(path.join(runtime, 'package.json'));
    const fromRuntime = name => import(pathToFileURL(requireRuntime.resolve(`@deepseek-ai/${name}`)).href);
    const publicBoot = path.join(runtime, 'lib/profile-boot.js');
    const bootFile = fs.existsSync(publicBoot) ? publicBoot : path.join(runtime, 'lib',
      fs.readdirSync(path.join(runtime, 'lib')).find(file => /^profile-boot-.+\.js$/.test(file)));
    const bootExports = await import(pathToFileURL(bootFile).href);
    const runProfile = bootExports.runProfile || Object.values(bootExports).find(value => typeof value === 'function' && value.name === 'runProfile');
    assert.equal(typeof runProfile, 'function', 'The installed DSH must expose runProfile');
    const [{ loadLayeredEnv }, registry] = await Promise.all([
      fromRuntime('dsh-app-boot'), fromRuntime(isModern ? 'dsh-agent-preset-registry' : 'dsh-agent-presets'),
    ]);
    app = await runProfile({
      environment: loadLayeredEnv('studymate-runtime-regression', home), profile: 'web', patchFiles: [],
      args: ['--host', '127.0.0.1', '--port', '0', '--no-open'],
    });
    assert.ok(app.ctx.get('webServer')?.port > 0, 'Web must listen on an ephemeral port');
    const nativeEntries = [...app.ctx.loader.entries()].filter(entry => entry.options.name === '@yunmiao/studymate');
    assert.equal(nativeEntries.length, 1, 'There must be exactly one native entry');
    const downgraded = process.env.STUDYMATE_RUNTIME_SCENARIO === 'downgraded';
    const migrated = downgraded || process.env.STUDYMATE_RUNTIME_SCENARIO === 'migrated';
    assert.equal(Boolean(nativeEntries[0].disabled), migrated, 'Only the migrated native entry should be disabled');
    if (!migrated) assert.equal(nativeEntries[0].fiber?.state, 2, 'Native entry must remain Active');
    const expectLearning = migrated || isModern;
    const roster = await app.ctx.agentPresets.list();
    const standard = await app.ctx.agentPresets[isModern ? 'resolve' : 'resolveMountable']('standard');
    assert.equal(standard.broken, undefined, 'Standard mode must remain usable');
    if (downgraded) {
      const declaration = [...app.ctx.loader.entries()].find(entry => entry.options.id === 'studymate-learning-preset');
      assert.equal(declaration?.disabled, true, 'Old DSH must skip the newer declaration before importing it');
    } else {
      assert.equal(roster.filter(preset => preset.id === 'learning').length, expectLearning ? 1 : 0,
        'Learning preset must exist exactly once when supported');
    }
    if (expectLearning && !downgraded) {
      const preset = await app.ctx.agentPresets[isModern ? 'resolve' : 'resolveMountable']('learning');
      assert.equal(preset.broken, undefined);
      if (!isModern) {
        const { createScope } = await fromRuntime('dsh-scope');
        scope = createScope(app.ctx, {});
        await app.ctx.agentPresets.mount(scope.ctx, 'learning');
      }
      const mounts = registry.livePresetMounts(app.ctx.fiber).filter(mount => mount.presetId === 'learning');
      assert.equal(mounts.length, 1, 'There must be exactly one learning composition');
      if (isModern) assert.deepEqual(await registry.auditRows(mounts[0].tree), { failed: [], pending: [] });
      else assert.deepEqual(await registry.inactiveRows(mounts[0].tree), []);
      const workflowName = `@deepseek-ai/dsh-workflow-${atLeastRelease(manifest.version, 1, 6) ? 'ptc' : 'worker-thread'}`;
      const workflow = [...mounts[0].tree.entries()].find(entry => entry.options.name === workflowName);
      assert.equal(workflow?.fiber?.state, 2, 'The correct workflow must be Active');
    }
    result = { ok: true, version: manifest.version, webStarted: true, nativeDisabled: migrated,
      learningPresets: roster.filter(preset => preset.id === 'learning').length,
      learningReady: expectLearning && !downgraded, modelRequestsIssued: 0 };
  } catch (error) {
    process.exitCode = 1;
    result = { ok: false, error: redact(error.stack || error) };
  } finally {
    try {
      if (scope) await scope.dispose();
      if (app) await app.shutdown.shutdown(process.exitCode || 0);
    } catch (error) {
      process.exitCode = 1;
      result = { ok: false, error: redact(error.stack || error), previous: result };
    }
    clearTimeout(timer);
  }
  stdout(`${marker}${JSON.stringify(result)}\n`);
}

function fixture(t, scenario) {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'studymate-runtime-'));
  t.after(() => fs.rmSync(temporary, { recursive: true, force: true }));
  const home = path.join(temporary, "家 O'Brien");
  const dshHome = path.join(home, '.dsh');
  const profile = path.join(dshHome, 'profiles/web');
  const workspace = path.join(home, '学习资料');
  fs.mkdirSync(profile, { recursive: true });
  fs.mkdirSync(workspace, { recursive: true });
  const env = {};
  for (const name of ['PATH', 'Path', 'SystemRoot', 'SYSTEMROOT', 'ComSpec', 'PATHEXT', 'TMP', 'TEMP', 'TMPDIR',
    'LANG', 'LC_ALL', 'LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH']) {
    if (process.env[name] !== undefined) env[name] = process.env[name];
  }
  Object.assign(env, { HOME: home, USERPROFILE: home, DSH_HOME: dshHome, LEARN_WORKSPACE: workspace,
    XDG_CONFIG_HOME: path.join(home, '.config'), XDG_CACHE_HOME: path.join(home, '.cache'),
    DSH_TELEMETRY_DISABLED: '1', STUDYMATE_DSH_PACKAGE: path.resolve(runtime), STUDYMATE_RUNTIME_SCENARIO: scenario });
  const installed = path.join(profile, 'node_modules/@yunmiao/studymate');
  fs.mkdirSync(path.dirname(installed), { recursive: true });
  if (scenario === 'native') fs.symlinkSync(project, installed, process.platform === 'win32' ? 'junction' : 'dir');
  else {
    fs.mkdirSync(path.join(installed, 'bin'), { recursive: true });
    fs.writeFileSync(path.join(installed, 'package.json'), JSON.stringify({ name: '@yunmiao/studymate', version: '0.1.3',
      exports: { '.': './bin/dsh-plugin.mjs' }, dsh: { bundle: { patch: './cordis.patch.yml' } } }));
    fs.copyFileSync(path.join(project, 'cordis.patch.yml'), path.join(installed, 'cordis.patch.yml'));
    // A 0.1.3 entry which must never run after the installer takes ownership.
    fs.writeFileSync(path.join(installed, 'bin/dsh-plugin.mjs'),
      'export const inject = ["agentPresets"]; export function apply() { throw new Error("StudyMate 0.1.3 incompatible native entry was executed"); }');
  }
  const manifest = path.join(profile, 'package.json');
  fs.writeFileSync(manifest, JSON.stringify({ name: 'studymate-test-profile', private: true,
    dependencies: { '@yunmiao/studymate': scenario === 'native'
      ? JSON.parse(fs.readFileSync(path.join(project, 'package.json'), 'utf8')).version : '0.1.3' },
    dsh: { profile: { bundles: ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app', '@yunmiao/studymate'] } } }, null, 2));
  const patch = path.join(profile, 'cordis.patch.yml');
  const unrelatedPatch = '# Existing unrelated plugin\n- insert:\n  - id: unrelated-disabled\n    name: "@local/not-installed"\n    disabled: true\n';
  fs.writeFileSync(patch, unrelatedPatch);
  const preserved = [manifest, path.join(profile, 'pnpm-lock.yaml'), path.join(dshHome, 'cordis.patch.yml'),
    path.join(dshHome, 'profiles/other/package.json'), path.join(dshHome, 'profiles/other/cordis.patch.yml')];
  for (const file of preserved.slice(1)) {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, file.endsWith('package.json') ? '{"private":true,"custom":"keep"}\n'
      : file.endsWith('pnpm-lock.yaml') ? "lockfileVersion: '9.0'\nsettings: {}\n" : '# Keep this profile untouched\n[]\n');
  }
  const before = preserved.map(file => fs.readFileSync(file));
  function unchanged() {
    preserved.forEach((file, index) => assert.deepEqual(fs.readFileSync(file), before[index], `${file} must remain unchanged`));
    assert.ok(fs.readFileSync(patch, 'utf8').startsWith(unrelatedPatch), 'Unrelated Web patch bytes must remain unchanged');
  }
  function runProbe(selectedRuntime = runtime, selectedScenario = scenario) {
    const result = spawnSync(process.execPath, [self, '--probe'], {
      env: { ...env, STUDYMATE_DSH_PACKAGE: selectedRuntime, STUDYMATE_RUNTIME_SCENARIO: selectedScenario },
      cwd: home, encoding: 'utf8', timeout: 60000, windowsHide: true,
    });
    const line = result.stdout?.split(/\r?\n/).find(text => text.startsWith(marker));
    assert.ok(line, redact(result.error?.message || result.stderr || 'Probe produced no result'));
    const outcome = JSON.parse(line.slice(marker.length));
    assert.equal(result.status, 0, JSON.stringify(outcome));
    assert.equal(outcome.ok, true, JSON.stringify(outcome));
    return outcome;
  }
  function install(selectedRuntime = runtime) {
    const bin = path.join(temporary, 'bin');
    fs.rmSync(bin, { recursive: true, force: true });
    fs.mkdirSync(bin);
    const dshBin = path.join(selectedRuntime, 'lib/bin.js');
    if (process.platform === 'win32') {
      fs.writeFileSync(path.join(bin, 'dsh.cmd'), '@echo off\r\n"' + process.execPath + '" "' + dshBin + '" %*\r\n');
    } else {
      // Match a real npm command while using only the supplied DSH installation.
      fs.symlinkSync(dshBin, path.join(bin, 'dsh'), 'file');
      fs.symlinkSync(process.execPath, path.join(bin, 'node'), 'file');
    }
    const installerEnv = { ...env, PATH: bin + path.delimiter + (env.PATH || env.Path || '') };
    delete installerEnv.Path;
    const result = spawnSync(process.execPath, [path.join(project, 'bin/studymate.mjs'), 'install'], {
      env: installerEnv, cwd: home, encoding: 'utf8', timeout: 60000, windowsHide: true,
    });
    assert.equal(result.status, 0, redact(result.error?.message || result.stderr || result.stdout));
  }
  return { home, dshHome, workspace, patch, unchanged, runProbe, install };
}

if (process.argv.includes('--probe')) {
  await probe();
} else if (!runtime) {
  test('real DSH integration (set STUDYMATE_DSH_PACKAGE to enable)', { skip: true }, () => {});
} else {
  assert.ok(path.isAbsolute(runtime), 'STUDYMATE_DSH_PACKAGE must be absolute');
  const metadata = JSON.parse(fs.readFileSync(path.join(runtime, 'package.json'), 'utf8'));
  assert.equal(metadata.name, '@deepseek-ai/dsh');
  if (process.env.STUDYMATE_DSH_EXPECTED_VERSION) assert.equal(metadata.version, process.env.STUDYMATE_DSH_EXPECTED_VERSION);
  test(`DSH ${metadata.version}: native entry keeps Web usable`, { timeout: 70000 }, t => {
    const f = fixture(t, 'native');
    const outcome = f.runProbe();
    assert.equal(outcome.learningPresets, modern(metadata.version) ? 1 : 0);
    if (!modern(metadata.version)) {
      assert.equal(fs.existsSync(path.join(f.dshHome, 'studymate-config.yaml')), false);
      assert.equal(fs.existsSync(path.join(f.dshHome, 'studymate')), false);
    }
    f.unchanged();
  });
  test(`DSH ${metadata.version}: installer recovers the old native package without changing other profiles`, { timeout: 70000 }, t => {
    const f = fixture(t, 'migrated');
    const learningData = path.join(f.workspace, 'learning-data.txt');
    fs.writeFileSync(learningData, 'existing learning data');
    fs.writeFileSync(path.join(f.dshHome, 'studymate-config.yaml'), JSON.stringify({ workspace: f.workspace, custom: 'keep' }));
    f.install();
    f.unchanged();
    const outcome = f.runProbe();
    assert.equal(outcome.learningPresets, 1);
    assert.equal(outcome.nativeDisabled, true);
    assert.equal(fs.readFileSync(learningData, 'utf8'), 'existing learning data');
    const config = JSON.parse(fs.readFileSync(path.join(f.dshHome, 'studymate-config.yaml'), 'utf8').replace(/^#[^\r\n]*\r?\n/, ''));
    assert.equal(config.custom, 'keep');
    f.unchanged();
  });
  if (process.env.STUDYMATE_DSH_DOWNGRADE_PACKAGE) {
    test('a modern installer declaration cannot prevent older DSH from booting, and reinstall restores learning', { timeout: 120000 }, t => {
      const older = process.env.STUDYMATE_DSH_DOWNGRADE_PACKAGE;
      assert.equal(modern(metadata.version), true);
      const f = fixture(t, 'migrated');
      const data = path.join(f.workspace, 'keep.txt');
      fs.writeFileSync(data, 'keep learning data');
      f.install();
      f.runProbe();
      const config = path.join(f.dshHome, 'studymate-config.yaml');
      const before = [f.patch, config].map(file => fs.readFileSync(file));
      f.runProbe(older, 'downgraded');
      [f.patch, config].forEach((file, i) => assert.deepEqual(fs.readFileSync(file), before[i]));
      f.install(older);
      assert.equal(f.runProbe(older).learningPresets, 1);
      assert.equal(fs.readFileSync(data, 'utf8'), 'keep learning data');
      f.unchanged();
    });
  }
}
