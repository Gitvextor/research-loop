// Opt-in real CLI regression: STUDYMATE_DSH_PACKAGE=/path/to/@deepseek-ai/dsh
// node --test scripts/tests/test_dsh_plugin_cli.mjs (requires pnpm and Python).
// The temporary registry serves only the two locally packed test versions.
// Optional STUDYMATE_DSH_DOWNGRADE_PACKAGE tests the same home with an older DSH.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { findPython } from '../../bin/studymate.mjs';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const runtime = process.env.STUDYMATE_DSH_PACKAGE;
const packageName = '@yunmiao/studymate';
const redact = value => String(value).replace(/https?:\/\/[^\s<>"')]+/g, '[url]');
const python = runtime ? findPython() : null;
const runtimeVersion = directory => JSON.parse(fs.readFileSync(path.join(directory, 'package.json'), 'utf8')).version;
const modern = directory => {
  const [major, minor, patch] = runtimeVersion(directory).split(/[.-]/).map(Number);
  return major > 0 || minor > 1 || minor === 1 && patch >= 7;
};

function onPath(name) {
  const suffixes = process.platform === 'win32' ? ['.cmd', '.exe', ''] : [''];
  for (const directory of (process.env.PATH || process.env.Path || '').split(path.delimiter)) {
    for (const suffix of suffixes) {
      const file = path.join(directory, name + suffix);
      if (fs.existsSync(file)) return fs.realpathSync(file);
    }
  }
  throw new Error(`${name} is required for CLI integration tests`);
}

function run(command, args, env, cwd, timeout = 45000) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { env, cwd, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    let output = '';
    let stdout = '';
    const record = data => { output = (output + data.toString()).slice(-65536); };
    child.stdout.on('data', data => { stdout += data.toString(); record(data); });
    child.stderr.on('data', record);
    child.on('error', reject);
    const timer = setTimeout(() => child.kill('SIGKILL'), timeout);
    child.on('close', (status, signal) => {
      clearTimeout(timer);
      resolve({ status, signal, output, stdout });
    });
  });
}

async function fixture(t) {
  let activeRuntime = runtime;
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'studymate-cli-'));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  const home = path.join(directory, 'home');
  const dshHome = path.join(home, '.dsh');
  const workspace = path.join(home, 'StudyMate');
  fs.mkdirSync(workspace, { recursive: true });
  const env = {};
  for (const key of ['PATH', 'Path', 'SystemRoot', 'SYSTEMROOT', 'ComSpec', 'PATHEXT', 'TMP', 'TEMP', 'TMPDIR', 'LANG', 'LC_ALL']) {
    if (process.env[key] !== undefined) env[key] = process.env[key];
  }
  Object.assign(env, { HOME: home, USERPROFILE: home, DSH_HOME: dshHome, LEARN_WORKSPACE: workspace,
    XDG_CONFIG_HOME: path.join(home, '.config'), XDG_CACHE_HOME: path.join(home, '.cache'),
    XDG_DATA_HOME: path.join(home, '.local/share'), PNPM_HOME: path.join(home, 'pnpm'),
    npm_config_cache: path.join(directory, 'npm-cache'), npm_config_store_dir: path.join(directory, 'pnpm-store'),
    npm_config_userconfig: path.join(directory, 'empty.npmrc'), npm_config_update_notifier: 'false',
    NODE_COMPILE_CACHE: path.join(directory, 'node-cache'), DSH_TELEMETRY_DISABLED: '1', CI: 'true' });
  fs.writeFileSync(env.npm_config_userconfig, '');
  const npmCommand = process.env.npm_execpath || onPath('npm');
  const npmCli = /\.(?:cmd|bat)$/i.test(npmCommand)
    ? path.join(path.dirname(npmCommand), 'node_modules/npm/bin/npm-cli.js') : npmCommand;
  const cli = (args, overrides = {}) => run(process.execPath,
    [path.join(activeRuntime, 'lib/bin.js'), ...args], { ...env, ...overrides }, home);
  const passed = result => { assert.equal(result.status, 0, redact(result.output)); return result; };
  const packs = path.join(directory, 'packs');
  fs.mkdirSync(packs);
  let packed = passed(await run(process.execPath, [npmCli, 'pack', '--ignore-scripts', '--json', '--pack-destination', packs], env, project));
  const original = path.join(packs, JSON.parse(packed.stdout)[0].filename);
  const unpacked = path.join(directory, 'unpacked');
  passed(await run(python.command, [...python.prefix, '-c',
    'import sys,tarfile; tarfile.open(sys.argv[1]).extractall(sys.argv[2])', original, unpacked], env, home));
  const packageDirectory = path.join(unpacked, 'package');
  const manifestPath = path.join(packageDirectory, 'package.json');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const versions = {};
  const tarballs = new Map();
  for (const revision of [1, 2]) {
    const version = `0.1.3-cli-test.${revision}`;
    manifest.version = version;
    fs.writeFileSync(manifestPath, JSON.stringify(manifest));
    packed = passed(await run(process.execPath, [npmCli, 'pack', '--ignore-scripts', '--json', '--pack-destination', packs], env, packageDirectory));
    const filename = JSON.parse(packed.stdout)[0].filename;
    const content = fs.readFileSync(path.join(packs, filename));
    tarballs.set(`/${filename}`, content);
    versions[version] = { ...manifest, dist: { tarball: `/${filename}`,
      shasum: createHash('sha1').update(content).digest('hex'),
      integrity: `sha512-${createHash('sha512').update(content).digest('base64')}` } };
  }
  let latest = '0.1.3-cli-test.1';
  let registryUrl;
  const server = http.createServer((request, response) => {
    const url = new URL(request.url, registryUrl);
    if (decodeURIComponent(url.pathname) === `/${packageName}`) {
      response.setHeader('content-type', 'application/json');
      response.end(JSON.stringify({ name: packageName, 'dist-tags': { latest }, versions:
        Object.fromEntries(Object.entries(versions).map(([version, metadata]) => [version,
          { ...metadata, dist: { ...metadata.dist, tarball: registryUrl + metadata.dist.tarball } }])) }));
    } else if (tarballs.has(url.pathname)) {
      response.setHeader('content-type', 'application/octet-stream');
      response.end(tarballs.get(url.pathname));
    } else {
      response.statusCode = 404;
      response.end('Only the local StudyMate test package is available.');
    }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  registryUrl = `http://127.0.0.1:${server.address().port}`;
  env.npm_config_registry = registryUrl;
  const data = path.join(workspace, 'keep.txt');
  fs.writeFileSync(data, 'existing learning data');
  const engineVersion = () => {
    const file = path.join(dshHome, 'studymate/engine/package.json');
    return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')).version : undefined;
  };

  const probe = path.join(directory, 'probe.mjs');
  fs.writeFileSync(probe, `import assert from 'node:assert/strict';
import{createRequire}from'node:module';
import{pathToFileURL}from'node:url';
const isModern=process.env.STUDYMATE_CLI_MODERN==='true';
const runtimeRequire=createRequire(process.env.STUDYMATE_CLI_RUNTIME+'/package.json');
const load=name=>import(pathToFileURL(runtimeRequire.resolve('@deepseek-ai/'+name)).href);
const registry=await load(isModern?'dsh-agent-preset-registry':'dsh-agent-presets');
export const inject=['agentPresets','appReady','webServer','appExit'];
export function apply(ctx){
  ctx.effect(()=>ctx.appReady.onReady(()=>{void(async()=>{
    let scope,result;
    try{
      const expected=Number(process.env.STUDYMATE_CLI_EXPECT_LEARNING);
      assert.ok(ctx.webServer.port>0);
      const roster=await ctx.agentPresets.list();
      assert.equal(roster.filter(row=>row.id==='learning').length,expected);
      const standard=await ctx.agentPresets.resolve('standard');
      assert.equal(standard.broken,undefined);
      if(expected){
        const preset=await ctx.agentPresets[isModern?'resolve':'resolveMountable']('learning');
        assert.equal(preset.broken,undefined);
        if(!isModern){
          const {createScope}=await load('dsh-scope');
          scope=createScope(ctx,{});
          await ctx.agentPresets.mount(scope.ctx,'learning');
        }
        const learning=registry.livePresetMounts().filter(row=>row.presetId==='learning');
        assert.equal(learning.length,1);
        if(isModern)assert.deepEqual(await registry.auditRows(learning[0].tree),{failed:[],pending:[]});
        else assert.deepEqual(await registry.inactiveRows(learning[0].tree),[]);
        const workflow=[...learning[0].tree.entries()].find(row=>row.options.name==='@deepseek-ai/dsh-workflow-'+process.env.STUDYMATE_CLI_WORKFLOW);
        assert.equal(workflow?.fiber?.state,2);
      }
      result={ok:true,learning:expected,web:true};
    }catch(error){result={ok:false,error:error.message};}
    finally{if(scope)await scope.dispose();}
    console.log('STUDYMATE_CLI_PROBE '+JSON.stringify(result));
    ctx.appExit(result.ok?0:1);
  })();}));
}
`);
  const overlay = path.join(directory, 'probe.patch.yml');
  fs.writeFileSync(overlay, JSON.stringify([{ insert: [{ id: 'studymate-cli-test-probe', name: probe }] }]));
  async function web(expected, overrides = {}) {
    const version = runtimeVersion(activeRuntime);
    const result = passed(await cli(['web', '--patch', overlay, '--host', '127.0.0.1', '--port', '0', '--no-open'],
      { STUDYMATE_CLI_EXPECT_LEARNING: String(expected), STUDYMATE_CLI_RUNTIME: activeRuntime,
        STUDYMATE_CLI_MODERN: String(modern(activeRuntime)),
        STUDYMATE_CLI_WORKFLOW: /^0\.1\.[0-5](?:-|$)/.test(version) ? 'worker-thread' : 'ptc', ...overrides }));
    const line = result.output.split(/\r?\n/).find(value => value.startsWith('STUDYMATE_CLI_PROBE '));
    assert.ok(line, redact(result.output));
    assert.equal(JSON.parse(line.slice('STUDYMATE_CLI_PROBE '.length)).ok, true, line);
    assert.equal(fs.readFileSync(data, 'utf8'), 'existing learning data');
    return result;
  }
  async function installCli(mode) {
    // Match a real npm command shim so CLI dependency detection uses this fixture's DSH.
    const bin = path.join(directory, 'bin');
    fs.rmSync(bin, { recursive: true, force: true });
    fs.mkdirSync(bin);
    const dshBin = path.join(activeRuntime, 'lib/bin.js');
    if (process.platform === 'win32') {
      fs.writeFileSync(path.join(bin, 'dsh.cmd'), '@echo off\r\n"' + process.execPath + '" "' + dshBin + '" %*\r\n');
    } else {
      fs.symlinkSync(dshBin, path.join(bin, 'dsh'), 'file');
      fs.symlinkSync(process.execPath, path.join(bin, 'node'), 'file');
    }
    const installerEnv = { ...env, PATH: bin + path.delimiter + (env.PATH || env.Path || '') };
    delete installerEnv.Path;
    passed(await run(process.execPath, [path.join(project, 'bin/studymate.mjs'), 'install',
      ...(mode ? ['--mode', mode] : [])], installerEnv, home));
  }
  const managedFiles = [path.join(dshHome, 'studymate-config.yaml'),
    path.join(dshHome, 'profiles/web/cordis.patch.yml')];
  const snapshot = () => managedFiles.map(file => fs.existsSync(file) ? fs.readFileSync(file) : null);
  const unchanged = before => assert.deepEqual(snapshot(), before, 'Boot must preserve installer-owned config and patch bytes');
  const emptyPath = path.join(directory, 'no-python');
  fs.mkdirSync(emptyPath);
  return { cli, web, passed, engineVersion, snapshot, unchanged, emptyPath, configFile: managedFiles[0],
    engineDirectory: path.join(dshHome, 'studymate/engine'),
    installCli, switchRuntime: directory => { activeRuntime = directory; },
    updateRegistry: () => { latest = '0.1.3-cli-test.2'; } };

}

if (!runtime) {
  test('DSH plugin CLI (set STUDYMATE_DSH_PACKAGE to enable)', { skip: true }, () => {});
} else {
  test('real DSH add / update @latest / remove keeps Web usable and preserves learning data', { timeout: 180000 }, async t => {
    const f = await fixture(t);
    const expected = modern(runtime) ? 1 : 0;
    f.passed(await f.cli(['plugin', '--profile', 'web', 'add', packageName]));
    const first = await f.web(expected);
    assert.equal(f.engineVersion(), expected ? '0.1.3-cli-test.1' : undefined);
    f.updateRegistry();
    f.passed(await f.cli(['plugin', '--profile', 'web', 'update', `${packageName}@latest`]));
    const updated = await f.web(expected);
    assert.equal(f.engineVersion(), expected ? '0.1.3-cli-test.2' : undefined);
    f.passed(await f.cli(['plugin', '--profile', 'web', 'remove', packageName]));
    await f.web(0);
    if (!expected) {
      assert.match(redact(first.output), /0\.1\.7-alpha\.1\+/);
      assert.match(redact(updated.output), /npx -y @yunmiao\/studymate@latest install/);
    }
  });
  test('npx remains the owner after native add; explicit migration enables native updates', { timeout: 180000 }, async t => {
    const f = await fixture(t);
    await f.installCli();
    const version = f.engineVersion();
    f.passed(await f.cli(['plugin', '--profile', 'web', 'add', packageName]));
    const before = f.snapshot();
    const sentinel = path.join(f.engineDirectory, 'keep-owner.txt');
    fs.writeFileSync(sentinel, 'npx owns this engine');
    await f.web(1);
    f.unchanged(before);
    assert.equal(f.engineVersion(), version);
    assert.equal(fs.readFileSync(sentinel, 'utf8'), 'npx owns this engine');
    if (modern(runtime)) {
      await f.installCli('native');
      assert.equal(f.engineVersion(), version, 'Handoff must not replace the engine before native boot');
      assert.equal(fs.readFileSync(sentinel, 'utf8'), 'npx owns this engine');
      const migrated = f.snapshot();
      await f.web(1);
      // Native activation may normalize config; it must never rewrite the profile.
      assert.deepEqual(f.snapshot()[1], migrated[1]);
      assert.equal(f.engineVersion(), '0.1.3-cli-test.1');
      f.updateRegistry();
      f.passed(await f.cli(['plugin', '--profile', 'web', 'update', `${packageName}@latest`]));
      await f.web(1);
      assert.deepEqual(f.snapshot()[1], migrated[1]);
      assert.equal(f.engineVersion(), '0.1.3-cli-test.2');
    } else {
      f.updateRegistry();
      f.passed(await f.cli(['plugin', '--profile', 'web', 'update', `${packageName}@latest`]));
      await f.web(1);
      f.unchanged(before);
      assert.equal(f.engineVersion(), version);
      assert.equal(fs.readFileSync(sentinel, 'utf8'), 'npx owns this engine');
    }
  });
  test('running npx after native installation explicitly takes ownership', { timeout: 180000 }, async t => {
    const f = await fixture(t);
    f.passed(await f.cli(['plugin', '--profile', 'web', 'add', packageName]));
    await f.web(modern(runtime) ? 1 : 0);
    await f.installCli();
    const version = f.engineVersion();
    const before = f.snapshot();
    await f.web(1);
    f.unchanged(before);
    f.updateRegistry();
    f.passed(await f.cli(['plugin', '--profile', 'web', 'update', `${packageName}@latest`]));
    await f.web(1);
    f.unchanged(before);
    assert.equal(f.engineVersion(), version);
  });
  if (modern(runtime)) {
    test('missing Python keeps ordinary Web running and explains why learning is unavailable', { timeout: 180000 }, async t => {
      const f = await fixture(t);
      f.passed(await f.cli(['plugin', '--profile', 'web', 'add', packageName]));
      const before = f.snapshot();
      const result = await f.web(0, { PATH: f.emptyPath, Path: f.emptyPath });
      assert.match(result.output, /Python 3\.9\+.*PyYAML/);
      f.unchanged(before);
      assert.equal(f.engineVersion(), undefined);
    });
  }
  if (process.env.STUDYMATE_DSH_DOWNGRADE_PACKAGE) {
    test('upgrading legacy npx users to modern DSH requires an explicit native handoff', { timeout: 180000 }, async t => {
      assert.equal(modern(runtime), true);
      const older = process.env.STUDYMATE_DSH_DOWNGRADE_PACKAGE;
      assert.equal(modern(older), false);
      const f = await fixture(t);
      f.switchRuntime(older);
      await f.installCli();
      // Simulate the published legacy installer, which had no ownership metadata.
      const config = JSON.parse(fs.readFileSync(f.configFile, 'utf8').replace(/^#[^\r\n]*\r?\n/, ''));
      delete config.installModes;
      fs.writeFileSync(f.configFile, JSON.stringify(config, null, 2) + '\n');
      const version = f.engineVersion();
      const sentinel = path.join(f.engineDirectory, 'legacy-owner.txt');
      fs.writeFileSync(sentinel, 'Preserve legacy npx engine');
      f.switchRuntime(runtime);
      f.passed(await f.cli(['plugin', '--profile', 'web', 'add', packageName]));
      const before = f.snapshot();
      const result = await f.web(0);
      assert.match(result.output, /--mode native/);
      f.unchanged(before);
      assert.equal(f.engineVersion(), version);
      assert.equal(fs.readFileSync(sentinel, 'utf8'), 'Preserve legacy npx engine');
      await f.installCli('native');
      assert.equal(f.engineVersion(), version);
      assert.equal(fs.readFileSync(sentinel, 'utf8'), 'Preserve legacy npx engine');
      await f.web(1);
      assert.equal(f.engineVersion(), '0.1.3-cli-test.1');
    });
    test('a modern native installation survives starting an older DSH in the same home', { timeout: 180000 }, async t => {
      assert.equal(modern(runtime), true, 'Start this test with a modern DSH');
      const older = process.env.STUDYMATE_DSH_DOWNGRADE_PACKAGE;
      assert.equal(modern(older), false, 'The downgrade target must use legacy presets');
      const f = await fixture(t);
      f.passed(await f.cli(['plugin', '--profile', 'web', 'add', packageName]));
      await f.web(1);
      const version = f.engineVersion();
      const sentinel = path.join(f.engineDirectory, 'downgrade-check.txt');
      fs.writeFileSync(sentinel, 'Preserve the installed engine.');
      f.switchRuntime(older);
      const result = await f.web(0);
      assert.equal(f.engineVersion(), version, 'Downgrade must not overwrite the modern engine');
      assert.equal(fs.readFileSync(sentinel, 'utf8'), 'Preserve the installed engine.');
      assert.match(redact(result.output), /0\.1\.7-alpha\.1\+/);
    });
  }
}
