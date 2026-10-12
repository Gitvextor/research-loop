import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { addChangelog, bumpVersion, mergedPullRequests, notesFromChangelog, registryVersion,
  releaseNotes, releasePlan, validatePack, verifyPublished, verifyPublishOrder,
  buildReleasePlugin, ensureGithubRelease, ensureReleaseAsset, withInstallationNotes } from './release.mjs';

const repository = 'Miaotofu01/Study-Mate';
const name = '@yunmiao/studymate';
function fixture(t) {
  const cwd = mkdtempSync(join(tmpdir(), 'studymate-release-test-'));
  t.after(() => rmSync(cwd, { recursive: true, force: true }));
  const git = (...args) => {
    const result = spawnSync('git', ['-c', 'user.name=Release test', '-c', 'user.email=test@example.invalid', '-c', 'commit.gpgsign=false', '-c', 'tag.gpgsign=false', ...args], { cwd, encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr);
    return result.stdout.trim();
  };
  git('init', '-b', 'main');
  writeFileSync(join(cwd, 'package.json'), JSON.stringify({ name, version: '0.1.1' }));
  git('add', 'package.json');
  git('commit', '-m', '最初版本');
  return { cwd, git, commit(file, message) {
    writeFileSync(join(cwd, file), message);
    git('add', file);
    git('commit', '-m', message);
    return git('rev-parse', 'HEAD');
  } };
}

test('stable patch/minor/major increments and rejects non-release inputs', () => {
  assert.equal(bumpVersion('0.1.1', 'patch'), '0.1.2');
  assert.equal(bumpVersion('0.1.9', 'minor'), '0.2.0');
  assert.equal(bumpVersion('0.9.9', 'major'), '1.0.0');
  for (const [version, bump] of [['1.2.3-beta', 'patch'], ['01.2.3', 'minor'], ['1.2.3', '$(echo danger)']]) {
    assert.throws(() => bumpVersion(version, bump));
  }
});

test('ordinary Chinese commits, full bodies and merged PRs survive changelog generation', () => {
  const notes = releaseNotes({ version: '0.1.2', baseTag: 'v0.1', date: '2026-09-23',
    commits: [{ sha: 'a'.repeat(40), subject: '修复学习模式 <script>', body: '保留详细说明\n第二行\n\n## 嵌入标题' }],
    pulls: [{ number: 4, title: '适配新版本 [DSH]' }] });
  assert.match(notes, /修复学习模式 &lt;script&gt;/);
  assert.match(notes, /第二行/);
  assert.match(notes, /compare\/v0\.1\.\.\.v0\.1\.2/);
  assert.match(notes, /pull\/4/);
  const previous = '# 更新记录\n\n## 手写记录\n\n原有文字\n';
  const changelog = addChangelog(previous, '0.1.2', notes);
  assert.ok(changelog.endsWith(previous.slice('# 更新记录\n\n'.length)));
  assert.equal(notesFromChangelog(changelog, '0.1.2'), notes.trim());
  assert.throws(() => addChangelog(changelog, '0.1.2', notes), /already contains/);
  assert.throws(() => addChangelog('## [0.1.2](url)\n', '0.1.2', notes), /already contains/);
});

test('first release includes history; v0.1 legacy tag bounds later release history', t => {
  const repo = fixture(t);
  const initial = repo.git('rev-parse', 'HEAD');
  assert.equal(releasePlan(repo.cwd, initial, 'patch').commits.length, 1);
  repo.git('tag', 'v0.1');
  const source = repo.commit('feature.txt', '完善中文功能\n\n保留普通提交的多行说明');
  repo.git('tag', 'not-a-release');
  const plan = releasePlan(repo.cwd, source, 'patch');
  assert.equal(plan.version, '0.1.2');
  assert.equal(plan.baseTag, 'v0.1');
  assert.equal(plan.commits.length, 1);
  assert.match(plan.commits[0].body, /多行说明/);
  assert.throws(() => releasePlan(repo.cwd, initial, 'patch'), /No commits/);
});

test('re-running the same source resumes only a matching annotated release tag', t => {
  const repo = fixture(t);
  repo.git('tag', 'v0.1');
  const source = repo.commit('change.txt', '兼容新版');
  const plan = releasePlan(repo.cwd, source, 'patch');
  writeFileSync(join(repo.cwd, 'package.json'), JSON.stringify({ name, version: plan.version }));
  repo.git('add', 'package.json');
  repo.git('commit', '-m', 'chore(release): v0.1.2');
  const { commits, retry, ...metadata } = plan;
  repo.git('tag', '-a', plan.tag, '-m', `StudyMate release metadata\n${JSON.stringify(metadata)}`);
  const resumed = releasePlan(repo.cwd, source, 'patch');
  assert.equal(resumed.retry, true);
  assert.equal(resumed.commit, repo.git('rev-parse', 'HEAD'));
  repo.git('tag', '-d', plan.tag);
  repo.git('tag', plan.tag);
  assert.throws(() => releasePlan(repo.cwd, source, 'patch'), /not created by this workflow/);
});

test('a tagged release cannot smuggle untested source changes into a retry', t => {
  const repo = fixture(t);
  const source = repo.git('rev-parse', 'HEAD');
  const plan = releasePlan(repo.cwd, source, 'patch');
  repo.commit('unexpected.mjs', 'untested source');
  repo.git('tag', '-a', plan.tag, '-m', `StudyMate release metadata\n${JSON.stringify(plan)}`);
  assert.throws(() => releasePlan(repo.cwd, source, 'patch'), /outside release metadata/);
});

test('merged PR lookup paginates and deduplicates, excluding unmerged or other-base PRs', async () => {
  const pr = (number, more = {}) => ({ number, merged_at: '2026-09-23', base: { ref: 'main', repo: { full_name: repository } }, ...more });
  const called = [];
  const pulls = await mergedPullRequests([{ sha: 'a' }, { sha: 'b' }], async path => {
    called.push(path);
    if (path.includes('/a/') && path.endsWith('page=1')) return Array.from({ length: 100 }, () => pr(4));
    return [pr(5), pr(6, { merged_at: null }), pr(7, { base: { ref: 'develop', repo: { full_name: repository } } })];
  });
  assert.deepEqual(pulls.map(pr => pr.number).sort(), [4, 5]);
  assert.ok(called.some(path => path.includes('/a/') && path.endsWith('page=2')));
});

test('npm status distinguishes unpublished from registry failure and immutable content conflicts', async () => {
  assert.equal(await registryVersion('0.1.2', async () => ({ status: 404 })), null);
  await assert.rejects(registryVersion('0.1.2', async () => ({ status: 503, ok: false })), /unknown/);
  const remote = { name, version: '0.1.2', dist: { integrity: 'sha512-matching' } };
  const pack = { version: '0.1.2', integrity: 'sha512-matching' };
  verifyPublished(remote, pack);
  assert.throws(() => verifyPublished(remote, { ...pack, integrity: 'sha512-other' }), /different contents/);
  verifyPublishOrder('0.1.2', { version: '0.1.1' });
  assert.throws(() => verifyPublishOrder('0.1.2', { version: '0.1.3' }), /refusing to replace/);
  assert.throws(() => verifyPublishOrder('0.1.2', { version: '1.0.0-beta' }), /not a stable version/);
});

test('tarball inspection rejects personal workspace, credentials and incomplete payloads', () => {
  const files = ['package.json', 'README.md', 'cordis.patch.yml', 'bin/dsh-plugin.mjs', 'bin/studymate.mjs', 'bin/skill-compat.mjs',
    'bin/openai-plugin.mjs', 'bin/openai-skill-compat.mjs', 'bin/openai-interaction.mjs', 'bin/openai-skill-ui.mjs',
    'openai/studymate/scripts/interaction_state.py', 'openai/studymate/skills/learning-system/references/codex-interaction.md',
    'openai/studymate/.codex-plugin/plugin.json', 'openai/studymate/requirements.txt', 'docs/Codex与ChatGPT.md',
    'preset/learning/agent.cordis.yml', 'scripts/install_preset.py', 'scripts/gen_home.py', '.dsh/skills/learning-system/SKILL.md',
    'schemas/subject.json', 'templates/home.html', 'docs/使用说明.md'];
  const pack = { name, version: '0.1.2', files: files.map(path => ({ path })) };
  validatePack(pack);
  for (const path of ['workspace/我的科目/private.md', '.npmrc', 'templates/.env', 'scripts/release/release.mjs']) {
    assert.throws(() => validatePack({ ...pack, files: [...pack.files, { path }] }), /Unexpected or private/);
  }
  assert.throws(() => validatePack({ ...pack, files: pack.files.filter(file => !file.path.startsWith('schemas/')) }), /missing schemas/);
  for (const required of ['cordis.patch.yml', 'bin/dsh-plugin.mjs']) {
    assert.throws(() => validatePack({ ...pack, files: pack.files.filter(file => file.path !== required) }),
      error => error.message === `npm tarball is missing ${required}.`);
  }
});

test('release CLI refuses local runs before touching repository or contacting registries', () => {
  const before = readFileSync(new URL('../../package.json', import.meta.url));
  const result = spawnSync(process.execPath, ['scripts/release/release.mjs', 'prepare'], {
    encoding: 'utf8', env: { ...process.env, GITHUB_ACTIONS: 'false' },
  });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /only allowed/);
  assert.deepEqual(readFileSync(new URL('../../package.json', import.meta.url)), before);
});

function assetFixture() {
  const bytes = Buffer.from('PK\x03\x04test plugin contents');
  const local = { name: 'studymate-openai.zip', bytes, size: bytes.length,
    digest: `sha256:${createHash('sha256').update(bytes).digest('hex')}` };
  const release = { id: 12, tag_name: 'v0.2.0', draft: false, prerelease: false,
    upload_url: `https://uploads.github.com/repos/${repository}/releases/12/assets{?name,label}` };
  const remote = { id: 13, name: local.name, size: local.size, digest: local.digest, state: 'uploaded' };
  return { local, release, remote };
}

test('plugin release build checks the prepared version and produces a SHA256 artifact', t => {
  const bytes = Buffer.from('PK\x03\x04mock archive');
  const build = version => (executable, args) => {
    assert.equal(executable, process.execPath);
    assert.deepEqual(args.slice(0, 3), ['bin/studymate.mjs', 'build-plugin', '--output']);
    const directory = args[3];
    t.after(() => rmSync(directory, { recursive: true, force: true }));
    mkdirSync(join(directory, 'studymate', '.codex-plugin'), { recursive: true });
    writeFileSync(join(directory, 'studymate', '.codex-plugin', 'plugin.json'), JSON.stringify({ version }));
    writeFileSync(join(directory, 'studymate-openai.zip'), bytes);
  };
  const artifact = buildReleasePlugin('0.2.0', build('0.2.0'));
  assert.equal(artifact.name, 'studymate-openai.zip');
  assert.deepEqual(artifact.bytes, bytes);
  assert.equal(artifact.digest, `sha256:${createHash('sha256').update(bytes).digest('hex')}`);
  assert.throws(() => buildReleasePlugin('0.2.0', build('0.1.5')), /version differs/);
});

test('release notes give both exact-version DSH installation and the OpenAI ZIP', () => {
  const body = withInstallationNotes('手工保留的版本说明', '0.2.0');
  assert.match(body, /npx -y @yunmiao\/studymate@0\.2\.0 install/);
  assert.match(body, /Codex \/ ChatGPT Work/);
  assert.match(body, /releases\/download\/v0\.2\.0\/studymate-openai\.zip/);
  assert.equal(withInstallationNotes(body, '0.2.0'), body);
  assert.ok(withInstallationNotes(body, '0.3.0').startsWith('手工保留的版本说明'));
  assert.doesNotMatch(withInstallationNotes(body, '0.3.0'), /studymate@0\.2\.0/);
});

test('GitHub release creation and retry update only missing installation information', async () => {
  const { release } = assetFixture();
  const state = { tag: 'v0.2.0', version: '0.2.0', commit: 'a'.repeat(40) };
  const calls = [];
  const created = await ensureGithubRelease(state, '版本说明', async (path, options) => {
    calls.push([path, options]);
    if (path.includes('/tags/')) return null;
    assert.equal(options.body.target_commitish, state.commit);
    assert.equal(options.body.make_latest, 'legacy');
    return { ...release, body: options.body.body };
  });
  assert.deepEqual(calls.map(([path]) => path), ['/releases/tags/v0.2.0', '/releases']);
  calls.length = 0;
  await ensureGithubRelease(state, '版本说明', async (path, options) => {
    calls.push([path, options]);
    return created;
  });
  assert.equal(calls.length, 1);
  await ensureGithubRelease(state, '版本说明', async (path, options) => {
    if (path.includes('/tags/')) return { ...release, body: '已有的手工说明' };
    assert.equal(path, '/releases/12');
    assert.equal(options.method, 'PATCH');
    assert.deepEqual(Object.keys(options.body), ['body']);
    assert.match(options.body.body, /^已有的手工说明/);
    return { ...release, body: options.body.body };
  });
  await assert.rejects(ensureGithubRelease(state, '版本说明', async () => ({ ...release, draft: true })), /expected stable release/);
});

test('new release assets upload ZIP bytes with the API media type and verified digest', async () => {
  const { local, release, remote } = assetFixture();
  let uploads = 0;
  const result = await ensureReleaseAsset(release, local, {
    request: async path => {
      assert.equal(path, '/releases/12/assets?per_page=100&page=1');
      return [];
    },
    transfer: async (url, options) => {
      uploads += 1;
      assert.equal(url, `https://uploads.github.com/repos/${repository}/releases/12/assets?name=studymate-openai.zip`);
      assert.equal(options.method, 'POST');
      assert.equal(options.headers['Content-Type'], 'application/zip');
      assert.equal(options.headers['Content-Length'], String(local.size));
      assert.equal(options.redirect, 'error');
      assert.deepEqual(options.body, local.bytes);
      return new Response(JSON.stringify(remote), { status: 201 });
    },
  });
  assert.equal(uploads, 1);
  assert.equal(result.skipped, false);
});

test('identical assets are skipped by SHA256, including beyond the first asset page', async () => {
  const { local, release, remote } = assetFixture();
  const pages = [];
  const result = await ensureReleaseAsset(release, local, {
    request: async path => {
      pages.push(path);
      return path.endsWith('page=1') ? Array.from({ length: 100 }, (_, i) => ({ name: `other-${i}` })) : [remote];
    },
    transfer: async () => assert.fail('No upload or download is needed for an identical digest'),
  });
  assert.equal(result.skipped, true);
  assert.equal(pages.length, 2);
});

test('old assets without a digest are downloaded and compared before skipping', async () => {
  const { local, release, remote } = assetFixture();
  const result = await ensureReleaseAsset(release, local, {
    request: async () => [{ ...remote, digest: null }],
    transfer: async (url, options) => {
      assert.equal(url, `https://api.github.com/repos/${repository}/releases/assets/13`);
      assert.equal(options.method, undefined);
      assert.equal(options.headers.Accept, 'application/octet-stream');
      return new Response(local.bytes);
    },
  });
  assert.equal(result.skipped, true);
  await assert.rejects(ensureReleaseAsset(release, local, {
    request: async () => [{ ...remote, digest: null }],
    transfer: async () => new Response(Buffer.from('different archive')),
  }), /different contents \(SHA256\)/);
});

test('conflicting and incomplete existing assets fail without deleting or overwriting', async () => {
  const { local, release, remote } = assetFixture();
  for (const [changes, message] of [
    [{ digest: `sha256:${'0'.repeat(64)}` }, /different contents \(SHA256\)/],
    [{ size: 1 }, /different contents \(size\)/],
    [{ state: 'starter' }, /incomplete state 'starter'/],
  ]) {
    await assert.rejects(ensureReleaseAsset(release, local, {
      request: async (path, options) => {
        assert.equal(options, undefined);
        assert.match(path, /^\/releases\/12\/assets\?/);
        return [{ ...remote, ...changes }];
      },
      transfer: async () => assert.fail('An existing conflicting asset must never be replaced'),
    }), message);
  }
});

test('lost upload responses recover only after verifying identical remote content', async () => {
  const { local, release, remote } = assetFixture();
  let reads = 0;
  let uploads = 0;
  const result = await ensureReleaseAsset(release, local, {
    request: async () => ++reads === 1 ? [] : [remote],
    transfer: async () => {
      uploads += 1;
      throw new Error('connection interrupted');
    },
  });
  assert.equal(result.recovered, true);
  assert.equal(result.skipped, true);
  assert.equal(uploads, 1);
  for (const [afterFailure, message] of [
    [[], /could not be verified: HTTP 502/],
    [[{ ...remote, state: 'starter' }], /incomplete state 'starter'/],
    [[{ ...remote, digest: `sha256:${'0'.repeat(64)}` }], /different contents/],
  ]) {
    let calls = 0;
    await assert.rejects(ensureReleaseAsset(release, local, {
      request: async () => ++calls === 1 ? [] : afterFailure,
      transfer: async () => new Response('upload failed', { status: 502 }),
    }), message);
    assert.equal(calls, 2);
  }
});

test('upload credentials are sent only to the expected upstream release endpoint', async () => {
  const { local, release } = assetFixture();
  for (const upload_url of [
    'https://example.invalid/assets{?name,label}',
    'https://uploads.github.com/repos/other/project/releases/12/assets{?name,label}',
    `https://uploads.github.com/repos/${repository}/releases/99/assets{?name,label}`,
  ]) {
    await assert.rejects(ensureReleaseAsset({ ...release, upload_url }, local, {
      request: async () => [],
      transfer: async () => assert.fail('Credentials must not be forwarded'),
    }), /Unexpected GitHub upload URL/);
  }
});
