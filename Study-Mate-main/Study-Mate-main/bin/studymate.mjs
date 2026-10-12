#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { adaptSkill } from './skill-compat.mjs';
import { buildOpenAiPlugin } from './openai-plugin.mjs';
import { buildAntigravityPlugin } from './antigravity-plugin.mjs';

const source = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const metadata = JSON.parse(fs.readFileSync(path.join(source, 'package.json'), 'utf8'));
const help = `StudyMate ${metadata.version}

在 DSH 中安装或更新 StudyMate：npx -y @yunmiao/studymate@latest install
Codex / ChatGPT Work：下载并导入最新插件 ZIP：
https://github.com/Miaotofu01/Study-Mate/releases/latest/download/studymate-openai.zip

用法：studymate [install] [--workspace <目录>] [--profile <名称>] [--mode standalone|native]
      studymate build-plugin [--output <目录>]（开发者构建）
      studymate build-antigravity [--output <目录>] [--install]（Antigravity 插件构建）
      studymate --help | --version

将学习模式和引擎安装到 DSH_HOME（默认 ~/.dsh）。
工作区优先使用 --workspace、LEARN_WORKSPACE、已有配置，首次默认为 ~/StudyMate。
DSH 0.1.7+ 默认注册到 web profile；其他 profile 用 --profile 指定。
默认由安装器管理；已添加 DSH 原生插件时，可用 --mode native 显式切换。
需要 Node.js ^22.19.0 或 >=24、dsh >=0.1.5-rc.2、Python 3.9+ 和 PyYAML。
安装器不会安装或升级 dsh，也不会重启正在运行的会话。

更新使用相同的 install 命令，沿用已有学习工作区。
build-plugin 供开发者导出 Codex / ChatGPT Work 技能插件目录及 ZIP（默认 ./dist）。
导出只需要 Node.js、Python 3.9+ 和 PyYAML，不需要 DSH，也不会更改客户端配置。`;

function run(command, args, extra = {}) {
  return spawnSync(command, args, { encoding: 'utf8', timeout: 15000, windowsHide: true, ...extra });
}

export function supportsDsh(value) {
  const version = value.match(/^v?(\d+)\.(\d+)\.(\d+)(?:-([\w.-]+))?(?:\+[\w.-]+)?$/);
  if (!version) return false;
  const minimum = [0, 1, 5];
  for (let i = 0; i < minimum.length; i++) {
    const number = Number(version[i + 1]);
    if (number !== minimum[i]) return number > minimum[i];
  }
  if (!version[4]) return true;
  const identifiers = version[4].split('.');
  const baseline = ['rc', '2'];
  for (let i = 0; i < Math.max(identifiers.length, baseline.length); i++) {
    const current = identifiers[i], required = baseline[i];
    if (current === required) continue;
    if (current === undefined) return false;
    if (required === undefined) return true;
    const numeric = /^\d+$/.test(current), otherNumeric = /^\d+$/.test(required);
    if (numeric && otherNumeric) return Number(current) > Number(required);
    if (numeric !== otherNumeric) return !numeric;
    return current > required;
  }
  return true;
}

export function findPython(platform = process.platform, execute = run) {
  const candidates = [['python3', []], ['python', []]];
  if (platform === 'win32') candidates.push(['py', ['-3']]);
  const probe = 'import sys, json; print(json.dumps(dict(executable=sys.executable, version=list(sys.version_info[:3]))))';
  let missingYaml, outdated;
  for (const [command, prefix] of candidates) {
    let result = execute(command, [...prefix, '-X', 'utf8', '-c', probe]);
    if (platform === 'win32' && result.error) {
      // Probe .cmd/.bat shims using constant arguments only. Later calls use
      // sys.executable directly, so user paths never pass through cmd.exe.
      result = execute(process.env.ComSpec || 'cmd.exe', ['/d', '/s', '/c',
        `"${command} ${[...prefix, '-X', 'utf8'].join(' ')} -c "${probe}""`],
      { windowsVerbatimArguments: true });
    }
    if (result.status !== 0) continue;
    try {
      const { executable, version } = JSON.parse(result.stdout);
      if (typeof executable !== 'string' || !executable || !Array.isArray(version) ||
          version.length < 2 || !version.every(Number.isInteger)) continue;
      if (version[0] < 3 || (version[0] === 3 && version[1] < 9)) {
        outdated ??= version.join('.');
        continue;
      }
      const python = { command: executable, prefix: ['-X', 'utf8'] };
      if (execute(executable, [...python.prefix, '-c', 'import yaml']).status === 0) return python;
      missingYaml ??= { executable, version: version.join('.'), launcher: [command, ...prefix].join(' ') };
    } catch { /* A launcher that did not produce the probe result is not usable. */ }
  }
  const checked = candidates.map(([command, prefix]) => [command, ...prefix].join(' ')).join('、');
  if (missingYaml) {
    const terminal = platform === 'win32' ? '命令提示符（CMD）或 PowerShell' : '系统终端';
    throw new Error(`已找到 Python ${missingYaml.version}：${missingYaml.executable}\n` +
      `但这个 Python 缺少 PyYAML 或无法加载它。PyYAML 用于读取 StudyMate 的 YAML 配置，需要单独安装。\n\n` +
      `1. 如果当前看到 Python 的 >>> 提示符，先输入 exit() 返回终端。\n` +
      `2. 在${terminal}中复制执行下面的命令（使用本次检测到的 Python）：\n` +
      `   ${missingYaml.launcher} -m pip install PyYAML\n` +
      `3. 安装完成后，重新运行刚才的 StudyMate 命令，保留原有参数。\n\n` +
      `如果提示 No module named pip，先执行：\n` +
      `   ${missingYaml.launcher} -m ensurepip --upgrade\n` +
      `然后重新执行上面的 PyYAML 安装命令。`);
  }
  if (outdated) throw new Error(`检测到 Python ${outdated}，需要 Python 3.9+（已检查 ${checked}）。请升级 Python 后重试。`);
  throw new Error(`没有找到可用的 Python 3.9+（已检查 ${checked}）。请安装 Python 3.9+，并确认能从终端运行。`);
}

function checkDependencies() {
  const [major, minor] = process.versions.node.split('.').map(Number);
  if (!(major >= 24 || (major === 22 && minor >= 19))) {
    throw new Error('需要 Node.js ^22.19.0 或 >=24，请先升级 Node.js。');
  }
  // npm's Windows entry point is dsh.cmd; the shell receives no user input.
  const dsh = process.platform === 'win32'
    ? run(process.env.ComSpec || 'cmd.exe', ['/d', '/s', '/c', '"dsh --version"'], { windowsVerbatimArguments: true })
    : run('dsh', ['--version']);
  const version = dsh.stdout?.trim();
  if (dsh.status !== 0 || !version) {
    throw new Error('找不到可运行的 dsh。请先运行 npm install -g @deepseek-ai/dsh@latest，再重试。');
  }
  if (!supportsDsh(version)) {
    throw new Error(`dsh ${version} 不支持此学习预设，需要 >=0.1.5-rc.2。请运行 npm install -g @deepseek-ai/dsh@latest。`);
  }
  return { python: findPython(), version };
}

function absolute(value) {
  if (value === '~') return os.homedir();
  if (/^~[/\\]/.test(value)) return path.resolve(os.homedir(), value.slice(2));
  return path.resolve(value);
}

function contained(parent, child) {
  const relative = path.relative(parent, child);
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative));
}

export function realDestination(directory) {
  if (fs.existsSync(directory)) return fs.realpathSync(directory);
  const parent = path.dirname(directory);
  if (parent === directory) throw new Error(`目录所在的磁盘或共享位置不可用：${directory}`);
  return path.join(realDestination(parent), path.basename(directory));
}

export function readConfig(file, python) {
  if (!fs.existsSync(file)) return {};
  const result = run(python.command, [...python.prefix, '-c', `import json, pathlib, sys, yaml
value = yaml.safe_load(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
if value is None: value = {}
if not isinstance(value, dict): raise ValueError('配置必须是 YAML 对象')
workspace = value.get('workspace')
if workspace is not None and not isinstance(workspace, str): raise ValueError('workspace 必须是路径字符串')
print(json.dumps(value, ensure_ascii=True))`, file]);
  if (result.status !== 0) throw new Error(`无法读取 ${file}，请修正配置后重试。\n${result.stderr?.trim() || result.error?.message || ''}`);
  return JSON.parse(result.stdout);
}

function copyPayload(destination) {
  for (const relative of ['.dsh/skills', 'preset/learning', 'templates', 'schemas']) {
    fs.cpSync(path.join(source, relative), path.join(destination, relative), {
      recursive: true,
      filter: (file) => !['__pycache__', '.DS_Store'].includes(path.basename(file)),
    });
  }
  for (const [directory, extension] of [['scripts', '.py'], ['docs', '.md']]) {
    fs.mkdirSync(path.join(destination, directory), { recursive: true });
    for (const entry of fs.readdirSync(path.join(source, directory), { withFileTypes: true })) {
      if (entry.isFile() && entry.name.endsWith(extension)) {
        fs.copyFileSync(path.join(source, directory, entry.name), path.join(destination, directory, entry.name));
      }
    }
  }
  for (const file of ['package.json', 'LICENSE']) {
    fs.copyFileSync(path.join(source, file), path.join(destination, file));
  }
}

// Shared by the CLI and the DSH bundle. Native loading already runs inside DSH;
// it must not launch a second, possibly different dsh executable from PATH.
export function installPayload({ workspaceArg, profile = 'web', python, version,
  dshHome = absolute(process.env.DSH_HOME || path.join(os.homedir(), '.dsh')), native = false, mode = 'standalone' }) {
  if (!['standalone', 'native'].includes(mode) || native && mode !== 'standalone') {
    throw new Error('--mode 必须是 standalone 或 native；原生启动不执行安装方式切换。');
  }
  if (!profile || /[/\\\0]/.test(profile) || ['.', '..', 'node_modules', 'desktop'].includes(profile)) {
    throw new Error('--profile 必须是单个 DSH 配置名称，不能使用路径或保留名称。');
  }
  python ??= findPython();
  dshHome = absolute(dshHome);
  const configFile = path.join(dshHome, 'studymate-config.yaml');
  const config = readConfig(configFile, python);
  const workspace = absolute(workspaceArg || process.env.LEARN_WORKSPACE || config.workspace || path.join(os.homedir(), 'StudyMate'));
  const engine = path.join(dshHome, 'studymate', 'engine');
  const preset = path.join(dshHome, '.agent-presets', 'learning');
  const installModes = config.installModes ?? {};
  if (typeof installModes !== 'object' || Array.isArray(installModes)) {
    throw new Error('配置中的 installModes 必须是按 profile 记录安装方式的对象。');
  }
  const installedMode = installModes[profile];
  if (native && (installedMode === 'standalone' ||
      installedMode !== 'native' && fs.existsSync(preset))) {
    throw new Error('学习模式仍由安装器管理；如需切换，请运行 ' +
      `npx -y @yunmiao/studymate@latest install --mode native --profile ${profile} 后重启 DSH。`);
  }
  const managedDirectories = native ? [engine] : [engine, preset];
  for (const parent of managedDirectories.map(directory => path.dirname(directory))) {
    if (fs.lstatSync(parent, { throwIfNoEntry: false })?.isSymbolicLink()) {
      throw new Error(`安装目录是符号链接，为避免改动其指向的项目，请先将它改为独立目录：${parent}`);
    }
  }
  for (const managed of managedDirectories) {
    if (fs.lstatSync(managed, { throwIfNoEntry: false })?.isSymbolicLink()) {
      throw new Error(`安装目标是符号链接，请先将它移至其他位置：${managed}`);
    }
    if (contained(realDestination(managed), fs.realpathSync(source))) {
      throw new Error(`安装器源码位于将被替换的目录内，请将源码移到其他位置或从 npx 运行：${managed}`);
    }
    if (contained(realDestination(managed), realDestination(workspace))) {
      throw new Error(`学习工作区不能放在安装器管理的目录内：${managed}`);
    }
  }
  // Build everything before changing the active preset or configuration.
  fs.mkdirSync(path.dirname(engine), { recursive: true });
  if (!native) fs.mkdirSync(path.dirname(preset), { recursive: true });
  const staging = fs.mkdtempSync(path.join(dshHome, '.studymate-install-'));
  const replacements = [];
  let preserveStaging = false;
  let registration;
  try {
    const stagedEngine = path.join(staging, 'engine');
    copyPayload(stagedEngine);
    const stagedSkills = path.join(stagedEngine, '.dsh', 'skills');
    for (const entry of fs.readdirSync(stagedSkills, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      const skillFile = path.join(stagedSkills, entry.name, 'SKILL.md');
      if (!fs.existsSync(skillFile)) continue;
      const skill = fs.readFileSync(skillFile, 'utf8');
      fs.writeFileSync(skillFile, adaptSkill(skill, {
        platform: process.platform, pythonExecutable: python.command,
        configFile, tempDirectory: os.tmpdir(),
      }));
    }
    const stagedPreset = path.join(staging, 'learning');
    // A filter avoids Node 22.19's native Windows copy crash on Unicode paths.
    // https://github.com/nodejs/node/issues/59636
    fs.cpSync(path.join(stagedEngine, 'preset', 'learning'), stagedPreset, { recursive: true, filter: () => true });
    const agentFile = path.join(stagedPreset, 'agent.cordis.yml');
    const agent = fs.readFileSync(agentFile, 'utf8');
    if (!agent.includes('__STUDYMATE_SKILLS__')) throw new Error('预设缺少 __STUDYMATE_SKILLS__，安装包不完整。');
    fs.writeFileSync(agentFile, agent.replaceAll('__STUDYMATE_SKILLS__', path.join(engine, '.dsh', 'skills').split(path.sep).join('/').replaceAll("'", "''")));

    const stagedPatch = path.join(staging, 'cordis.patch.yml');
    const prepare = run(python.command, [...python.prefix, path.join(source, 'scripts', 'install_preset.py'),
      '--preset-dir', stagedPreset, '--preset-target', preset, '--dsh-home', dshHome,
      '--profile', profile, '--patch-output', stagedPatch,
      ...(native ? ['--bundle'] : ['--dsh-version', version, '--mode', mode])]);
    if (prepare.status !== 0) throw new Error(prepare.stderr?.trim() || prepare.error?.message || '无法注册学习预设。');
    registration = JSON.parse(prepare.stdout);

    fs.mkdirSync(path.join(workspace, '.learning', 'subjects'), { recursive: true });
    const realWorkspace = fs.realpathSync(workspace);
    for (const managed of managedDirectories) {
      const realManaged = path.join(fs.realpathSync(path.dirname(managed)), path.basename(managed));
      if (contained(realManaged, realWorkspace)) throw new Error(`学习工作区不能指向安装器管理的目录：${managed}`);
    }
    config.workspace = realWorkspace;
    config.root = engine;
    config.installModes = { ...installModes, [profile]: native || mode === 'native' ? 'native' : 'standalone' };
    const stagedConfig = path.join(staging, 'config.yaml');
    // JSON objects are also valid YAML; retain unrelated user configuration keys.
    fs.writeFileSync(stagedConfig, `# StudyMate 学习工作区与引擎项目定位\n${JSON.stringify(config, null, 2)}\n`);

    const targets = [[stagedConfig, configFile]];
    // Explicit handoff changes registration only; the selected native package
    // initializes its own payload on the next start, avoiding an npx downgrade.
    if (mode !== 'native') {
      targets.unshift([stagedEngine, engine]);
      if (!native) targets.push([stagedPreset, preset]);
    }
    if (registration.patchChanged) {
      const profilePatch = path.join(dshHome, 'profiles', profile, 'cordis.patch.yml');
      if (fs.lstatSync(profilePatch, { throwIfNoEntry: false })?.isSymbolicLink()) {
        throw new Error(`预设配置是符号链接，请先将它改为独立文件：${profilePatch}`);
      }
      fs.mkdirSync(path.dirname(profilePatch), { recursive: true });
      targets.push([stagedPatch, profilePatch]);
    }
    for (const [staged, target] of targets) {
      const backup = path.join(staging, `backup-${replacements.length}`);
      const existed = fs.existsSync(target);
      if (existed) fs.renameSync(target, backup);
      const change = { target, backup, existed, installed: false };
      replacements.push(change);
      fs.renameSync(staged, target);
      change.installed = true;
    }
  } catch (error) {
    try {
      for (const change of replacements.reverse()) {
        if (change.installed) fs.rmSync(change.target, { recursive: true, force: true });
        if (change.existed) fs.renameSync(change.backup, change.target);
      }
    } catch (rollbackError) {
      preserveStaging = true;
      throw new Error(`${error.message}\n自动恢复失败：${rollbackError.message}；原文件保留在 ${staging}`);
    }
    throw error;
  } finally {
    if (!preserveStaging) fs.rmSync(staging, { recursive: true, force: true });
  }
  return { registration, engine, preset, configFile, workspace: config.workspace };
}

function install(workspaceArg, profile, mode) {
  const { python, version } = checkDependencies();
  const { registration, engine, preset, configFile, workspace } = installPayload({ workspaceArg, profile, python, version, mode });
  const registered = registration.mode === 'bundle' ? `\n学习模式由 DSH 插件管理：${profile}`
    : registration.mode === 'declarative' ? `\n已注册到 DSH profile：${profile}` : '';
  console.log(`StudyMate ${metadata.version} 安装完成。\n引擎：${engine}\n学习预设：${preset}${registered}\n学习工作区：${workspace}\n配置：${configFile}\n请在 dsh 中新建会话并选择“学习模式”；已运行的 dsh 如未显示该模式，请重启。\n启动会话时把工作目录设为 ${workspace}，并把会话权限选成 workspace-write 或 danger-full-access：学习数据都写在那个目录里，会话目录不在它里面时，每次落盘都会要求你授权。`);
}

export function main(args = process.argv.slice(2)) {
  try {
    if (args.length === 1 && ['--help', '-h'].includes(args[0])) console.log(help);
    else if (args.length === 1 && ['--version', '-v'].includes(args[0])) console.log(metadata.version);
    else if (args[0] === 'build-plugin') {
      if (args.length !== 1 && !(args.length === 3 && args[1] === '--output' && args[2] && !args[2].startsWith('--'))) {
        throw new Error(`用法：studymate build-plugin [--output <目录>]`);
      }
      const result = buildOpenAiPlugin({ output: args[2], python: findPython() });
      console.log(`StudyMate ${result.version} OpenAI 插件已构建。\n插件目录：${result.plugin}\n插件 ZIP：${result.archive}\n安装方法见插件目录中的 README.md。`);
    }
    else if (args[0] === 'build-antigravity') {
      let output;
      for (let i = 1; i < args.length; i++) {
        if (args[i] === '--output' && args[i + 1] && !args[i + 1].startsWith('--')) {
          output = args[++i];
        } else if (args[i] === '--install') {
          output = path.join(os.homedir(), '.gemini', 'config', 'plugins', 'studymate');
        } else {
          throw new Error('用法：studymate build-antigravity [--output <目录>] [--install]');
        }
      }
      const result = buildAntigravityPlugin({ output, python: findPython() });
      console.log(`StudyMate ${result.version} Antigravity 插件已构建。\n插件目录：${result.plugin}\n插件 ZIP：${result.archive}`);
    }
    else {
      if (args[0] === 'install') args.shift();
      let workspace, profile = 'web', mode = 'standalone';
      const seen = new Set();
      for (let i = 0; i < args.length; i += 2) {
        const option = args[i], value = args[i + 1];
        if (!['--workspace', '--profile', '--mode'].includes(option) || !value || value.startsWith('--') || seen.has(option)) {
          throw new Error(`不支持的参数：${args.join(' ')}\n${help}`);
        }
        seen.add(option);
        if (option === '--workspace') workspace = value;
        else if (option === '--profile') profile = value;
        else mode = value;
      }
      install(workspace, profile, mode);
    }
  } catch (error) {
    console.error(`StudyMate：${error.message}`);
    process.exitCode = 1;
  }
}

if (process.argv[1] && fs.existsSync(process.argv[1]) &&
    fs.realpathSync(process.argv[1]) === fs.realpathSync(fileURLToPath(import.meta.url))) {
  main();
}
