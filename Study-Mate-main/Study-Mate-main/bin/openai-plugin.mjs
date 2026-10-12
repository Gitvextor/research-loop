import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { adaptOpenAiSkill } from './openai-skill-compat.mjs';
import { getOpenAiSkillUi } from './openai-skill-ui.mjs';

const source = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const marker = '.studymate-build.json';

function inside(parent, child) {
  const relative = path.relative(parent, child);
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative));
}

function copyTree(from, to) {
  const stat = fs.lstatSync(from);
  if (stat.isSymbolicLink()) throw new Error(`插件资源不能是符号链接：${from}`);
  if (stat.isDirectory()) {
    fs.mkdirSync(to, { recursive: true });
    for (const name of fs.readdirSync(from).sort()) {
      if (name === '__pycache__' || name.endsWith('.pyc')) continue;
      copyTree(path.join(from, name), path.join(to, name));
    }
  } else if (stat.isFile()) {
    fs.mkdirSync(path.dirname(to), { recursive: true });
    fs.copyFileSync(from, to);
  }
}

function assertReplaceable(directory) {
  const stat = fs.lstatSync(directory, { throwIfNoEntry: false });
  if (!stat) return;
  if (!stat.isDirectory() || stat.isSymbolicLink()) throw new Error(`输出不是独立目录：${directory}`);
  let metadata;
  try { metadata = JSON.parse(fs.readFileSync(path.join(directory, marker), 'utf8')); } catch { /* Unmanaged output. */ }
  if (metadata?.generator !== '@yunmiao/studymate') {
    throw new Error(`输出目录已有非构建文件，请选择其他 --output 目录：${directory}`);
  }
}

/** Export a complete skills-only plugin, independent of the DSH installer. */
export function buildOpenAiPlugin({ output = path.resolve('dist'), python } = {}) {
  if (!python?.command) throw new Error('构建插件需要 Python 3.9+。');
  const outputDir = path.resolve(output);
  // Resolve symlinks before deciding whether output could overwrite build inputs.
  let existing = outputDir;
  const suffix = [];
  while (!fs.existsSync(existing)) {
    if (path.dirname(existing) === existing) throw new Error(`输出目录所在磁盘或共享不可访问：${outputDir}`);
    suffix.unshift(path.basename(existing));
    existing = path.dirname(existing);
  }
  const realOutput = path.join(fs.realpathSync(existing), ...suffix);
  for (const name of ['.dsh', 'bin', 'scripts', 'schemas', 'templates', 'docs', 'openai']) {
    if (inside(path.join(fs.realpathSync(source), name), realOutput)) {
      throw new Error(`输出目录不能位于构建源文件内：${outputDir}`);
    }
  }
  const target = path.join(realOutput, 'studymate');
  if (inside(target, fs.realpathSync(source))) throw new Error('输出目录不能覆盖项目源文件。');
  assertReplaceable(target);
  fs.mkdirSync(realOutput, { recursive: true });
  const archive = path.join(realOutput, 'studymate-openai.zip');
  const archiveStat = fs.lstatSync(archive, { throwIfNoEntry: false });
  if (archiveStat && (!archiveStat.isFile() || archiveStat.isSymbolicLink())) {
    throw new Error(`ZIP 输出不是独立文件：${archive}`);
  }
  const staging = fs.mkdtempSync(path.join(realOutput, '.studymate-build-'));
  const plugin = path.join(staging, 'studymate');
  const packageInfo = JSON.parse(fs.readFileSync(path.join(source, 'package.json'), 'utf8'));
  let preserveStaging = false;
  try {
    copyTree(path.join(source, 'openai', 'studymate'), plugin);
    const manifestPath = path.join(plugin, '.codex-plugin', 'plugin.json');
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    // package.json remains the single source of release versions.
    manifest.version = packageInfo.version;
    fs.writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
    for (const name of fs.readdirSync(path.join(source, '.dsh', 'skills')).sort()) {
      const skillSource = path.join(source, '.dsh', 'skills', name);
      if (!fs.statSync(skillSource).isDirectory()) continue;
      const destination = path.join(plugin, 'skills', name);
      copyTree(skillSource, destination);
      const skillFile = path.join(destination, 'SKILL.md');
      fs.writeFileSync(skillFile, adaptOpenAiSkill(fs.readFileSync(skillFile, 'utf8'), name));
      fs.mkdirSync(path.join(destination, 'agents'), { recursive: true });
      fs.writeFileSync(path.join(destination, 'agents', 'openai.yaml'), getOpenAiSkillUi(name));
    }
    for (const name of ['templates', 'schemas']) copyTree(path.join(source, name), path.join(plugin, name));
    for (const name of fs.readdirSync(path.join(source, 'scripts')).filter(name => name.endsWith('.py') && name !== 'install_preset.py')) {
      copyTree(path.join(source, 'scripts', name), path.join(plugin, 'scripts', name));
    }
    for (const name of fs.readdirSync(path.join(source, 'docs')).filter(name => name.endsWith('.md'))) {
      const text = fs.readFileSync(path.join(source, 'docs', name), 'utf8').replaceAll('.dsh/skills', 'skills');
      fs.mkdirSync(path.join(plugin, 'docs'), { recursive: true });
      fs.writeFileSync(path.join(plugin, 'docs', name), text);
    }
    copyTree(path.join(source, 'docs', 'images', 'logo.png'), path.join(plugin, 'assets', 'logo.png'));
    copyTree(path.join(source, 'LICENSE'), path.join(plugin, 'LICENSE'));
    fs.writeFileSync(path.join(plugin, 'README.md'), '# StudyMate\n\nCodex / ChatGPT Work 学习插件。\n\n首次安装时导入 studymate-openai.zip；更新时下载最新 ZIP，在浏览器中打开已有插件的链接并上传新版本，随后新建任务。\n\n安装与使用见 [使用指南](docs/Codex与ChatGPT.md)。\n\n本目录是已构建的完整插件，无需运行安装脚本或构建命令。学习数据应放在插件目录外。\n');
    fs.writeFileSync(path.join(plugin, marker), `${JSON.stringify({ generator: packageInfo.name, version: packageInfo.version })}\n`);
    const zipFile = path.join(staging, 'studymate-openai.zip');
    const zipCode = `import pathlib,sys,zipfile
root=pathlib.Path(sys.argv[1])
with zipfile.ZipFile(sys.argv[2], 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    for file in sorted(root.rglob('*')):
        if file.is_file():
            info=zipfile.ZipInfo(file.relative_to(root.parent).as_posix(), date_time=(2020,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644 << 16
            archive.writestr(info, file.read_bytes())
`;
    const result = spawnSync(python.command, [...(python.prefix || []), '-X', 'utf8', '-c', zipCode, plugin, zipFile], {
      encoding: 'utf8', windowsHide: true, timeout: 120000,
    });
    if (result.error || result.status !== 0) throw new Error(result.error?.message || result.stderr || 'ZIP 构建失败。');
    // Swap only our own generated output; preserve previous artifacts on failure.
    const replacements = [];
    try {
      for (const [fresh, destination] of [[plugin, target], [zipFile, archive]]) {
        const backup = path.join(staging, `backup-${replacements.length}`);
        const existed = fs.existsSync(destination);
        if (existed) fs.renameSync(destination, backup);
        const change = { destination, backup, existed, installed: false };
        replacements.push(change);
        fs.renameSync(fresh, destination);
        change.installed = true;
      }
    } catch (error) {
      try {
        for (const change of replacements.reverse()) {
          if (change.installed) fs.rmSync(change.destination, { recursive: true, force: true });
          if (change.existed) fs.renameSync(change.backup, change.destination);
        }
      } catch (rollbackError) {
        preserveStaging = true;
        throw new Error(`${error.message}\n自动恢复失败：${rollbackError.message}；备份保留在 ${staging}`);
      }
      throw error;
    }
    return { plugin: target, archive, version: packageInfo.version };
  } finally {
    if (!preserveStaging) fs.rmSync(staging, { recursive: true, force: true });
  }
}
