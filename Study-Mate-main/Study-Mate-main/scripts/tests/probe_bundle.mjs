// Manual smoke test for an installed native bundle; never uses the real DSH home.
// Set STUDYMATE_DSH_MODULES to the DSH installation's node_modules, and set
// HOME / USERPROFILE and DSH_HOME to an isolated profile under a temporary directory.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

function inside(parent, child) {
  const relative = path.relative(parent, child);
  return relative !== '' && relative !== '..' &&
    !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative);
}

function canonical(destination) {
  if (fs.existsSync(destination)) return fs.realpathSync(destination);
  const parent = path.dirname(destination);
  assert.notEqual(parent, destination, `Path is unavailable: ${destination}`);
  return path.join(canonical(parent), path.basename(destination));
}

const temporaryRoots = [os.tmpdir(), ...(process.platform === 'win32' ? [] : ['/tmp'])]
  .filter(directory => fs.existsSync(directory)).map(directory => fs.realpathSync(directory));
function isolated(directory, label) {
  assert.ok(directory && path.isAbsolute(directory), `${label} must be an absolute temporary path`);
  const resolved = canonical(directory);
  assert.ok(temporaryRoots.some(root => inside(root, resolved)), `${label} must be inside a temporary directory`);
  return resolved;
}

function redact(text) {
  return String(text).replace(/https?:\/\/[^\s<>"')]+/g, '[url]')
    .replace(/((?:token|authorization|secret)\s*[=:]\s*)[^\s,;]+/gi, '$1[redacted]');
}

let app;
let mounts;
let outcome;
let exitCode = 0;
const stdout = process.stdout.write;
const stderr = process.stderr.write;
const writeResult = value => stdout.call(process.stdout, `PROBE_RESULT ${JSON.stringify(value)}\n`);
// The web app prints a process-token URL. Keep runtime output out of the probe log.
const quiet = (_chunk, encoding, callback) => {
  const done = typeof encoding === 'function' ? encoding : callback;
  if (done) queueMicrotask(done);
  return true;
};
process.stdout.write = quiet;
process.stderr.write = quiet;
const timeout = setTimeout(() => {
  writeResult({ ok: false, error: 'Activation probe timed out after 45 seconds' });
  process.exit(2);
}, 45000);

try {
  const modules = process.env.STUDYMATE_DSH_MODULES;
  assert.ok(modules && path.isAbsolute(modules), 'STUDYMATE_DSH_MODULES must be an absolute node_modules directory');
  const home = isolated(os.homedir(), 'HOME / USERPROFILE');
  const dshHome = isolated(process.env.DSH_HOME, 'DSH_HOME');
  assert.ok(inside(home, dshHome), 'DSH_HOME must be inside the isolated home');
  process.env.LEARN_WORKSPACE = isolated(process.env.LEARN_WORKSPACE || path.join(home, 'StudyMate'), 'LEARN_WORKSPACE');
  assert.ok(fs.statSync(home).isDirectory(), 'Create the isolated home and install the bundle before probing');
  process.chdir(home);

  const fromRuntime = (name, file) => import(pathToFileURL(path.join(modules, '@deepseek-ai', name, file)).href);
  const [{ runProfile }, { loadLayeredEnv }, registry] = await Promise.all([
    fromRuntime('dsh', 'lib/profile-boot.js'),
    fromRuntime('dsh-app-boot', 'lib/index.js'),
    fromRuntime('dsh-agent-preset-registry', 'lib/index.js'),
  ]);
  const { livePresetMounts, auditRows } = registry;
  app = await runProfile({
    environment: loadLayeredEnv('studymate-bundle-probe', home),
    profile: 'web', patchFiles: [],
    args: ['--host', '127.0.0.1', '--port', '0', '--no-open'],
  });
  mounts = () => livePresetMounts(app.ctx.fiber).filter(mount => mount.presetId === 'learning');

  async function verifyPreset() {
    const preset = await app.ctx.agentPresets.resolve('learning');
    assert.equal(preset.broken, undefined);
    assert.equal(mounts().length, 1, 'Exactly one learning preset must be mounted');
    const audit = await auditRows(mounts()[0].tree);
    assert.deepEqual(audit, { failed: [], pending: [] });
    const inventory = (await app.ctx.agentPresets.compositionInventory()).find(item => item.id === 'learning');
    assert.ok(inventory);
    assert.equal(inventory.broken, undefined);
    for (const moduleName of ['@deepseek-ai/dsh-workflow-ptc', '@deepseek-ai/dsh-tool-present']) {
      const row = inventory.rows.find(item => item.moduleName === moduleName);
      assert.ok(row, `${moduleName} must exist`);
      assert.equal(row.enabled, true, `${moduleName} must be enabled`);
      assert.equal(row.fiberState, 2, `${moduleName} must be active`);
    }
    return { failed: audit.failed.length, pending: audit.pending.length, activeRows: inventory.rows.filter(row => row.fiberState === 2).length };
  }

  const initial = await verifyPreset();
  const configFile = path.join(dshHome, 'studymate-config.yaml');
  // The native installer writes a JSON object with one YAML comment header.
  const config = JSON.parse(fs.readFileSync(configFile, 'utf8').replace(/^#[^\r\n]*\r?\n/, ''));
  assert.equal(canonical(config.root), canonical(path.join(dshHome, 'studymate', 'engine')));
  assert.equal(canonical(config.workspace), canonical(process.env.LEARN_WORKSPACE));
  for (const file of ['scripts/gen_home.py', '.dsh/skills/learning-system/SKILL.md']) {
    assert.ok(fs.statSync(path.join(config.root, file)).isFile());
  }
  assert.ok(fs.statSync(path.join(config.workspace, '.learning', 'subjects')).isDirectory());

  const bootstrap = [...app.ctx.loader.entries()].filter(entry => entry.options.name === '@yunmiao/studymate');
  assert.equal(bootstrap.length, 1, 'Exactly one StudyMate bundle entry must exist');
  const entry = bootstrap[0];
  const oldFiber = entry.fiber;
  assert.equal(oldFiber?.state, 2);
  await entry.update({ disabled: true });
  await oldFiber.await();
  await app.ctx.loader.await();
  assert.equal(mounts().length, 0, 'Disabling the bundle must release its preset');
  assert.equal((await app.ctx.agentPresets.list()).some(preset => preset.id === 'learning'), false);
  await entry.update({ disabled: false });
  await app.ctx.loader.await();
  const reenabled = await verifyPreset();
  outcome = { ok: true, initial, reenabled, lifecycle: 'disable / enable passed', modelRequestsIssued: 0 };
} catch (error) {
  exitCode = 1;
  outcome = { ok: false, error: redact(error.stack || error) };
} finally {
  try {
    if (app) {
      await app.shutdown.shutdown(exitCode);
      assert.equal(mounts?.().length, 0, 'Shutdown must release the learning preset');
    }
  } catch (error) {
    exitCode = 1;
    outcome = { ok: false, error: redact(error.stack || error), previous: outcome };
  }
  clearTimeout(timeout);
  process.stdout.write = stdout;
  process.stderr.write = stderr;
}
process.exitCode = exitCode;
writeResult(outcome);
