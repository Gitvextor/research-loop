// No runtime dependencies; mutations are restricted to the upstream manual CI run.
import { appendFileSync, existsSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';

const REPOSITORY = 'Miaotofu01/Study-Mate';
const PACKAGE = '@yunmiao/studymate';
const REGISTRY = 'https://registry.npmjs.org/';
const VERSION = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/;
const RELEASE_TAG = /^v(0|[1-9]\d*)\.(0|[1-9]\d*)(?:\.(0|[1-9]\d*))?$/;
const TAG_MARKER = 'StudyMate release metadata\n';
const OPENAI_ASSET = 'studymate-openai.zip';
const INSTALLATION_START = '<!-- studymate-installation -->';
const INSTALLATION_END = '<!-- /studymate-installation -->';
const STATE = () => join(process.env.RUNNER_TEMP || tmpdir(), 'studymate-release-state.json');

function command(name, args, { cwd = process.cwd(), input, allowFailure = false } = {}) {
  const result = spawnSync(name, args, { cwd, input, encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 });
  if (!allowFailure && (result.error || result.status !== 0)) {
    throw new Error(`${name} ${args[0]} failed: ${result.error?.message || result.stderr || result.stdout}`);
  }
  return result;
}
function git(args, cwd) { return command('git', args, { cwd }).stdout.trimEnd(); }
function optionalGit(args, cwd) {
  const result = command('git', args, { cwd, allowFailure: true });
  return result.status === 0 ? result.stdout.trimEnd() : null;
}
function jsonFile(file) { return JSON.parse(readFileSync(file, 'utf8')); }
function writeJson(file, data) { writeFileSync(file, `${JSON.stringify(data, null, 2)}\n`); }
function summary(text) {
  console.log(text);
  if (process.env.GITHUB_STEP_SUMMARY) appendFileSync(process.env.GITHUB_STEP_SUMMARY, `${text}\n\n`);
}

export function bumpVersion(version, bump) {
  if (!VERSION.test(version) || !['patch', 'minor', 'major'].includes(bump)) throw new Error('Expected a stable x.y.z version and patch/minor/major.');
  const parts = version.split('.').map(BigInt);
  const index = { major: 0, minor: 1, patch: 2 }[bump];
  parts[index] += 1n;
  for (let i = index + 1; i < 3; i++) parts[i] = 0n;
  return parts.join('.');
}

function markdown(value) {
  return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replace(/[\\`*_[\]#]/g, '\\$&');
}

export function releaseNotes({ version, baseTag, commits, pulls, date, repository = REPOSITORY }) {
  const url = `https://github.com/${repository}`;
  const lines = [`## [${version}](${url}/releases/tag/v${version}) - ${date}`, ''];
  if (pulls.length) {
    lines.push('### 已合并的 Pull Request', '');
    for (const pr of [...pulls].sort((a, b) => a.number - b.number)) {
      lines.push(`- ${markdown(pr.title)} ([#${pr.number}](${url}/pull/${pr.number}))`);
    }
    lines.push('');
  }
  lines.push('### 所有提交', '');
  for (const commit of commits) {
    lines.push(`- ${markdown(commit.subject)} ([${commit.sha.slice(0, 7)}](${url}/commit/${commit.sha}))`);
    if (commit.body.trim()) lines.push('', ...commit.body.trim().split(/\r?\n/).map(line => `  > ${markdown(line)}`), '');
  }
  lines.push('', baseTag ? `[完整比较](${url}/compare/${baseTag}...v${version})` : '首次生成更新记录，包含当前版本之前的全部仓库提交。');
  return `${lines.join('\n').trim()}\n`;
}

export function addChangelog(previous, version, notes) {
  const marker = `<!-- studymate-release:v${version} -->`;
  if (previous.includes(marker) || new RegExp(`^## \\[?${version.replaceAll('.', '\\.')}[\\] \\(]`, 'm').test(previous)) {
    throw new Error(`CHANGELOG already contains ${version}.`);
  }
  const block = `${marker}\n${notes.trim()}\n<!-- /studymate-release:v${version} -->\n\n`;
  if (!previous.trim()) return `# 更新记录\n\n${block}`;
  const heading = previous.match(/^# [^\r\n]+\r?\n(?:\r?\n)?/);
  return heading ? `${heading[0]}${block}${previous.slice(heading[0].length)}` : `${block}${previous}`;
}

export function notesFromChangelog(changelog, version) {
  const start = `<!-- studymate-release:v${version} -->\n`;
  const end = `<!-- /studymate-release:v${version} -->`;
  const offset = changelog.indexOf(start);
  const finish = changelog.indexOf(end, offset + start.length);
  if (offset < 0 || finish < 0) throw new Error(`Missing release notes for ${version}.`);
  return changelog.slice(offset + start.length, finish).trim();
}

export function releasePlan(cwd, source, bump) {
  if (!/^[0-9a-f]{40}$/.test(source)) throw new Error('Expected an exact source commit SHA.');
  const pkg = JSON.parse(git(['show', `${source}:package.json`], cwd));
  if (pkg.name !== PACKAGE) throw new Error(`Unexpected package ${pkg.name}.`);
  const version = bumpVersion(pkg.version, bump);
  const tag = `v${version}`;
  const existing = optionalGit(['rev-parse', '--verify', `refs/tags/${tag}^{commit}`], cwd);
  if (existing) {
    const annotation = git(['for-each-ref', '--format=%(contents)', `refs/tags/${tag}`], cwd);
    if (!annotation.startsWith(TAG_MARKER)) throw new Error(`${tag} already exists and was not created by this workflow.`);
    const metadata = JSON.parse(annotation.slice(TAG_MARKER.length));
    if (metadata.repository !== REPOSITORY || metadata.source !== source || metadata.bump !== bump || metadata.version !== version) {
      throw new Error(`${tag} belongs to a different release. Refusing to overwrite it.`);
    }
    if (git(['rev-parse', `${existing}^`], cwd) !== source) throw new Error(`${tag} is not based on the tested source commit.`);
    const changed = git(['diff-tree', '--no-commit-id', '--name-only', '-r', existing], cwd).split('\n');
    if (changed.some(file => !['package.json', 'CHANGELOG.md', 'package-lock.json', 'npm-shrinkwrap.json'].includes(file))) {
      throw new Error(`${tag} changes files outside release metadata.`);
    }
    const taggedPackage = JSON.parse(git(['show', `${existing}:package.json`], cwd));
    if (taggedPackage.name !== PACKAGE || taggedPackage.version !== version) throw new Error(`${tag} has an unexpected package version.`);
    return { ...metadata, tag, commit: existing, retry: true };
  }
  const baseTag = git(['tag', '--merged', source, '--list', 'v*', '--sort=-version:refname'], cwd)
    .split('\n').find(value => RELEASE_TAG.test(value)) || null;
  if (baseTag && git(['rev-parse', `${baseTag}^{commit}`], cwd) === source) throw new Error('No commits since the latest release.');
  if (baseTag && VERSION.test(baseTag.slice(1)) && baseTag !== `v${pkg.version}`) {
    throw new Error(`package.json (${pkg.version}) and latest release (${baseTag}) disagree.`);
  }
  if (baseTag) {
    const previous = baseTag.slice(1).split('.').map(BigInt);
    if (previous.length === 2) previous.push(0n); // Historical tag v0.1 predates npm 0.1.1.
    const current = pkg.version.split('.').map(BigInt);
    const difference = current.map((value, i) => value - previous[i]).find(value => value !== 0n);
    if (difference < 0n) throw new Error(`package.json (${pkg.version}) is behind the latest release (${baseTag}).`);
  }
  const range = baseTag ? `${baseTag}..${source}` : source;
  const commits = git(['rev-list', '--reverse', range], cwd).split('\n').filter(Boolean).map(sha => {
    const [subject, ...body] = git(['show', '-s', '--format=%s%n%b', sha], cwd).split('\n');
    return { sha, subject, body: body.join('\n') };
  });
  if (!commits.length) throw new Error('No commits to release.');
  return { repository: REPOSITORY, source, bump, version, tag, baseTag, commits, retry: false };
}

async function github(path, { method = 'GET', body, missing = false } = {}) {
  const response = await fetch(`https://api.github.com/repos/${REPOSITORY}${path}`, {
    method, headers: { Authorization: `Bearer ${process.env.GH_TOKEN}`, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(30_000),
  });
  if (missing && response.status === 404) return null;
  if (!response.ok) throw new Error(`GitHub ${method} ${path}: HTTP ${response.status} ${await response.text()}`);
  return response.json();
}

export async function mergedPullRequests(commits, request = github) {
  const found = new Map();
  // GitHub's commit association endpoint also handles squash and rebase merges.
  for (let offset = 0; offset < commits.length; offset += 4) {
    await Promise.all(commits.slice(offset, offset + 4).map(async ({ sha }) => {
      for (let page = 1; ; page++) {
        const rows = await request(`/commits/${sha}/pulls?per_page=100&page=${page}`);
        for (const pr of rows) {
          if (pr.merged_at && pr.base?.ref === 'main' && pr.base?.repo?.full_name === REPOSITORY) found.set(pr.number, pr);
        }
        if (rows.length < 100) break;
      }
    }));
  }
  return [...found.values()];
}

function requireWorkflow() {
  if (process.env.GITHUB_ACTIONS !== 'true' || process.env.GITHUB_EVENT_NAME !== 'workflow_dispatch' ||
      process.env.GITHUB_REPOSITORY !== REPOSITORY || process.env.GITHUB_REF !== 'refs/heads/main') {
    throw new Error('Publishing is only allowed from the upstream main workflow_dispatch run.');
  }
  if (!process.env.GH_TOKEN) throw new Error('Missing the workflow GitHub token.');
}

export function validatePack(pack) {
  if (pack.name !== PACKAGE || !VERSION.test(pack.version)) throw new Error('Unexpected npm package identity.');
  const files = pack.files.map(file => file.path);
  const allowed = /^(?:package\.json|cordis\.patch\.yml|README\.md|LICENSE|CHANGELOG\.md|bin\/[^/]+\.mjs|openai\/studymate\/(?:\.codex-plugin\/plugin\.json|requirements\.txt|scripts\/[^/]+\.py|skills\/learning-system\/references\/[^/]+\.md)|\.dsh\/skills\/.+|preset\/learning\/.+|scripts\/[^/]+\.py|schemas\/[^/]+\.json|templates\/.+|docs\/[^/]+\.md|docs\/images\/.+)$/;
  for (const file of files) {
    if (!allowed.test(file) || /(^|\/)(?:\.env(?:\..*)?|\.npmrc|\.git|node_modules|__pycache__|\.DS_Store|[^/]+\.pyc)(\/|$)/.test(file)) {
      throw new Error(`Unexpected or private file in npm tarball: ${file}`);
    }
  }
  for (const required of ['cordis.patch.yml', 'bin/dsh-plugin.mjs', 'bin/studymate.mjs', 'bin/skill-compat.mjs', 'bin/openai-plugin.mjs', 'bin/openai-skill-compat.mjs', 'openai/studymate/.codex-plugin/plugin.json', 'openai/studymate/requirements.txt', 'docs/Codex与ChatGPT.md', 'preset/learning/agent.cordis.yml', 'scripts/install_preset.py', 'scripts/gen_home.py', '.dsh/skills/learning-system/SKILL.md']) {
    if (!files.includes(required)) throw new Error(`npm tarball is missing ${required}.`);
  }
  for (const prefix of ['schemas/', 'templates/', 'docs/']) if (!files.some(file => file.startsWith(prefix))) throw new Error(`npm tarball is missing ${prefix}.`);
  for (const required of ['bin/openai-interaction.mjs', 'bin/openai-skill-ui.mjs',
    'openai/studymate/scripts/interaction_state.py', 'openai/studymate/skills/learning-system/references/codex-interaction.md']) {
    if (!files.includes(required)) throw new Error(`npm tarball is missing ${required}.`);
  }
}

function packPackage() {
  const directory = mkdtempSync(join(process.env.RUNNER_TEMP || tmpdir(), 'studymate-pack-'));
  const [pack] = JSON.parse(command('npm', ['pack', '--json', '--ignore-scripts', '--pack-destination', directory]).stdout);
  validatePack(pack);
  const file = join(directory, pack.filename);
  const integrity = `sha512-${createHash('sha512').update(readFileSync(file)).digest('base64')}`;
  if (integrity !== pack.integrity) throw new Error('Packed tarball does not match npm integrity.');
  return { ...pack, file };
}

// Build from the prepared checkout: the builder sets the plugin manifest version
// from package.json and uses deterministic ZIP timestamps for safe CI retries.
export function buildReleasePlugin(version, execute = command) {
  const directory = mkdtempSync(join(process.env.RUNNER_TEMP || tmpdir(), 'studymate-openai-release-'));
  execute(process.execPath, ['bin/studymate.mjs', 'build-plugin', '--output', directory]);
  const manifest = jsonFile(join(directory, 'studymate', '.codex-plugin', 'plugin.json'));
  if (manifest.version !== version) throw new Error('Built plugin version differs from the prepared release.');
  const file = join(directory, OPENAI_ASSET);
  const bytes = readFileSync(file);
  if (bytes.length < 4 || bytes.readUInt32LE(0) !== 0x04034b50) throw new Error('Plugin build did not produce a ZIP archive.');
  return { name: OPENAI_ASSET, file, bytes, size: bytes.length,
    digest: `sha256:${createHash('sha256').update(bytes).digest('hex')}` };
}

export function withInstallationNotes(body, version) {
  const installation = `${INSTALLATION_START}\n### 安装与更新\n\n` +
    `**DeepSeek Harness (DSH)**：\n\n\`\`\`sh\nnpx -y ${PACKAGE}@${version} install\n\`\`\`\n\n` +
    `首次安装与更新使用同一命令；更新沿用已有学习工作区。\n\n` +
    `**Codex / ChatGPT Work**：[下载同版本 OpenAI 插件 ZIP](https://github.com/${REPOSITORY}/releases/download/v${version}/${OPENAI_ASSET})。` +
    `首次安装时导入完整 ZIP；更新时下载 ZIP，在浏览器中打开已有插件的链接并上传新版本，随后新建任务。详细步骤见包内使用指南，学习数据保存在插件目录之外。\n${INSTALLATION_END}`;
  const start = body.indexOf(INSTALLATION_START);
  const end = body.indexOf(INSTALLATION_END);
  if (start < 0 && end < 0) return `${body.trim()}\n\n${installation}\n`;
  if (start < 0 || end < start) throw new Error('GitHub release installation notes have incomplete markers.');
  return body.slice(0, start) + installation + body.slice(end + INSTALLATION_END.length);
}

export async function ensureGithubRelease(state, notes, request = github) {
  let release = await request(`/releases/tags/${state.tag}`, { missing: true });
  if (!release) {
    return request('/releases', { method: 'POST', body: {
      tag_name: state.tag, target_commitish: state.commit, name: state.tag, make_latest: 'legacy',
      body: withInstallationNotes(notes, state.version), draft: false, prerelease: false,
    } });
  }
  if (release.draft || release.prerelease || release.tag_name !== state.tag) {
    throw new Error(`GitHub ${state.tag} is not the expected stable release; inspect it before retrying.`);
  }
  const body = withInstallationNotes(release.body || notes, state.version);
  if (body !== release.body) {
    release = await request(`/releases/${release.id}`, { method: 'PATCH', body: { body } });
  }
  return release;
}

async function matchingReleaseAsset(release, name, request) {
  let found = null;
  for (let page = 1; ; page++) {
    const assets = await request(`/releases/${release.id}/assets?per_page=100&page=${page}`);
    for (const asset of assets) {
      if (asset.name !== name) continue;
      if (found) throw new Error(`Multiple GitHub assets named ${name}; inspect the release before retrying.`);
      found = asset;
    }
    if (assets.length < 100) return found;
  }
}

async function verifyReleaseAsset(asset, local, transfer) {
  if (asset.state !== 'uploaded') {
    throw new Error(`GitHub asset ${local.name} has incomplete state '${asset.state}'. Inspect the failed upload before retrying; no asset was deleted or overwritten.`);
  }
  if (asset.size !== local.size) throw new Error(`GitHub asset ${local.name} already exists with different contents (size). Refusing to overwrite it.`);
  let digest = asset.digest;
  if (!/^sha256:[0-9a-f]{64}$/i.test(digest || '')) {
    // Older assets may not have a server digest. Download via the authenticated
    // API endpoint rather than trusting an arbitrary browser_download_url.
    if (!Number.isSafeInteger(asset.id) || asset.id < 1) throw new Error('Invalid GitHub asset identity.');
    const response = await transfer(`https://api.github.com/repos/${REPOSITORY}/releases/assets/${asset.id}`, {
      headers: { Authorization: `Bearer ${process.env.GH_TOKEN}`, Accept: 'application/octet-stream', 'X-GitHub-Api-Version': '2022-11-28' },
      signal: AbortSignal.timeout(120_000),
    });
    if (!response.ok) throw new Error(`Cannot verify existing GitHub asset ${local.name}: HTTP ${response.status}.`);
    const bytes = Buffer.from(await response.arrayBuffer());
    digest = `sha256:${createHash('sha256').update(bytes).digest('hex')}`;
  }
  if (digest.toLowerCase() !== local.digest.toLowerCase()) {
    throw new Error(`GitHub asset ${local.name} already exists with different contents (SHA256). Refusing to overwrite it.`);
  }
}

/** Upload immutable release content or verify it on retry; never replace assets.
 * GitHub's raw upload, SHA256 digest and starter-state behavior are documented at
 * https://docs.github.com/en/rest/releases/assets#upload-a-release-asset
 */
export async function ensureReleaseAsset(release, local, { request = github, transfer = fetch } = {}) {
  if (!Number.isSafeInteger(release.id) || release.id < 1) throw new Error('Invalid GitHub release identity.');
  const existing = await matchingReleaseAsset(release, local.name, request);
  if (existing) {
    await verifyReleaseAsset(existing, local, transfer);
    return { asset: existing, skipped: true };
  }
  const upload = new URL((release.upload_url || '').replace(/\{[^}]*\}$/, ''));
  if (upload.origin !== 'https://uploads.github.com' || upload.username || upload.password ||
      upload.pathname !== `/repos/${REPOSITORY}/releases/${release.id}/assets`) {
    throw new Error('Unexpected GitHub upload URL; refusing to send release credentials.');
  }
  upload.search = '';
  upload.hash = '';
  upload.searchParams.set('name', local.name);
  let asset;
  try {
    const response = await transfer(upload.href, {
      method: 'POST', headers: { Authorization: `Bearer ${process.env.GH_TOKEN}`, Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/zip', 'Content-Length': String(local.size) },
      body: local.bytes, redirect: 'error', signal: AbortSignal.timeout(120_000),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status} ${await response.text()}`);
    asset = await response.json();
  } catch (error) {
    // A lost response or a duplicate-upload race can follow a successful upload.
    // Reconcile once by reading remote state, without deleting or retrying POST.
    const recovered = await matchingReleaseAsset(release, local.name, request);
    if (recovered) {
      await verifyReleaseAsset(recovered, local, transfer);
      return { asset: recovered, skipped: true, recovered: true };
    }
    throw new Error(`GitHub upload ${local.name} could not be verified: ${error.message}. Re-run this workflow after inspecting the release.`);
  }
  if (asset.name !== local.name) throw new Error(`GitHub returned an unexpected uploaded asset name: ${asset.name}.`);
  await verifyReleaseAsset(asset, local, transfer);
  return { asset, skipped: false };
}

async function prepare() {
  requireWorkflow();
  if (git(['status', '--porcelain'])) throw new Error('Release checkout must be clean.');
  git(['fetch', 'origin', 'main', '--tags']);
  const plan = releasePlan(process.cwd(), process.env.GITHUB_SHA, process.env.RELEASE_BUMP);
  if (plan.retry) {
    if (optionalGit(['merge-base', '--is-ancestor', plan.commit, 'origin/main']) === null) throw new Error('Existing release commit is not on origin/main.');
    git(['checkout', '--detach', plan.commit]);
  } else {
    if (git(['rev-parse', 'origin/main']) !== plan.source) throw new Error('main advanced during checks. Start a new release from the latest main.');
    git(['checkout', '--detach', plan.source]);
    const pulls = await mergedPullRequests(plan.commits);
    const notes = releaseNotes({ ...plan, pulls, date: new Date().toISOString().slice(0, 10) });
    const previous = existsSync('CHANGELOG.md') ? readFileSync('CHANGELOG.md', 'utf8') : '';
    writeFileSync('CHANGELOG.md', addChangelog(previous, plan.version, notes));
    const files = ['package.json', 'CHANGELOG.md'];
    const pkg = jsonFile('package.json');
    pkg.version = plan.version;
    writeJson('package.json', pkg);
    for (const file of ['package-lock.json', 'npm-shrinkwrap.json']) {
      if (!existsSync(file)) continue;
      const lock = jsonFile(file);
      lock.version = plan.version;
      if (lock.packages?.['']) lock.packages[''].version = plan.version;
      writeJson(file, lock);
      files.push(file);
    }
    packPackage(); // Refuse an incomplete or private tarball before creating refs.
    git(['add', '--', ...files]);
    const identity = ['-c', 'user.name=github-actions[bot]', '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com'];
    git([...identity, 'commit', '-m', `chore(release): ${plan.tag}`]);
    const { commits, retry, ...metadata } = plan;
    const messageFile = join(process.env.RUNNER_TEMP || tmpdir(), 'studymate-tag-message.txt');
    writeFileSync(messageFile, `${TAG_MARKER}${JSON.stringify(metadata)}\n`);
    git([...identity, 'tag', '-a', plan.tag, '-F', messageFile]);
    // A concurrent main update or branch protection rejects both refs; never force.
    git(['push', '--atomic', 'origin', 'HEAD:refs/heads/main', `refs/tags/${plan.tag}`]);
    plan.commit = git(['rev-parse', 'HEAD']);
  }
  writeJson(STATE(), { version: plan.version, tag: plan.tag, commit: plan.commit, source: plan.source });
  summary(`Prepared **${plan.tag}** at \`${plan.commit}\`${plan.retry ? ' (resuming an existing release)' : ''}.`);
}

export async function registryVersion(version, request = fetch) {
  const response = await request(`${REGISTRY}${encodeURIComponent(PACKAGE)}/${encodeURIComponent(version)}`, {
    headers: { 'Cache-Control': 'no-cache' }, signal: AbortSignal.timeout(30_000),
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`npm registry returned HTTP ${response.status}; publication status is unknown.`);
  return response.json();
}

export function verifyPublished(remote, pack) {
  if (remote.name !== PACKAGE || remote.version !== pack.version || remote.dist?.integrity !== pack.integrity) {
    throw new Error(`${PACKAGE}@${pack.version} already exists with different contents. It cannot be overwritten.`);
  }
}

export function verifyPublishOrder(version, latest) {
  if (!latest) return;
  if (!VERSION.test(latest.version)) throw new Error('npm latest is not a stable version; inspect dist-tags before publishing.');
  const current = version.split('.').map(BigInt);
  const previous = latest.version.split('.').map(BigInt);
  const difference = current.map((value, i) => value - previous[i]).find(value => value !== 0n);
  if (difference < 0n) throw new Error(`npm latest is already ${latest.version}; refusing to replace it with older ${version}.`);
}

async function publish() {
  requireWorkflow();
  const state = jsonFile(STATE());
  if (state.source !== process.env.GITHUB_SHA || git(['rev-parse', 'HEAD']) !== state.commit || git(['rev-parse', `${state.tag}^{commit}`]) !== state.commit) {
    throw new Error('Release state, checkout and tag do not agree.');
  }
  // A plugin build failure must happen before the immutable npm publication.
  const plugin = buildReleasePlugin(state.version);
  const pack = packPackage();
  if (pack.version !== state.version) throw new Error('Packed version differs from the prepared release.');
  let remote = await registryVersion(pack.version);
  if (!remote) {
    verifyPublishOrder(pack.version, await registryVersion('latest'));
    const result = command('npm', ['publish', pack.file, '--access', 'public', '--provenance', '--ignore-scripts', '--registry', REGISTRY], { allowFailure: true });
    process.stdout.write(result.stdout || '');
    process.stderr.write(result.stderr || '');
    // npm processes accepted publications asynchronously; allow up to five minutes.
    // A lost HTTP response may also follow a successful immutable publication.
    for (let attempt = 0; attempt < 60 && !remote; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 5000));
      remote = await registryVersion(pack.version);
    }
    if (!remote) throw new Error(`npm publication could not be verified (exit ${result.status}). Re-run this workflow after checking npm.`);
  }
  verifyPublished(remote, pack);
  const notes = notesFromChangelog(readFileSync('CHANGELOG.md', 'utf8'), state.version);
  const release = await ensureGithubRelease(state, notes);
  const uploaded = await ensureReleaseAsset(release, plugin);
  summary(`Published [${PACKAGE}@${state.version}](https://www.npmjs.com/package/${PACKAGE}/v/${state.version}) and [${state.tag}](https://github.com/${REPOSITORY}/releases/tag/${state.tag}) with [${OPENAI_ASSET}](https://github.com/${REPOSITORY}/releases/download/${state.tag}/${OPENAI_ASSET})${uploaded.skipped ? ' (verified existing ZIP)' : ''}. ZIP SHA256: \`${plugin.digest.slice('sha256:'.length)}\`.`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try {
    if (process.argv[2] === 'prepare') await prepare();
    else if (process.argv[2] === 'publish') await publish();
    else throw new Error('Usage: node scripts/release/release.mjs prepare|publish (GitHub Actions only)');
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
