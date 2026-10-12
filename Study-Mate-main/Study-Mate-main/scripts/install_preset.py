#!/usr/bin/env python3
"""Register a copied learning preset without rewriting unrelated Cordis patches."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import yaml

BEGIN = '# BEGIN STUDYMATE LEARNING PRESET'
END = '# END STUDYMATE LEARNING PRESET'
PLUGIN = '@deepseek-ai/dsh-agent-preset'
ENTRY_ID = 'studymate-learning-preset'
BUNDLE = '@yunmiao/studymate'
BUNDLE_ENTRY_ID = 'studymate'
# Evaluated before importing the row. Older DSH releases cannot resolve this
# package; profileContext alone is insufficient (0.1.6-alpha.2 already has it).
DECLARATIVE_DISABLED = {'__jsExpr': (
    "(() => { try { return !ctx.get('pluginPackages')?.packageOf("
    "'@deepseek-ai/dsh-agent-preset', ctx.baseUrl); } catch { return true; } })()"
)}


class PatchLoader(yaml.SafeLoader):
    pass


PatchLoader.add_constructor('tag:yaml.org,2002:js', lambda loader, node: loader.construct_scalar(node))


class PresetLoader(yaml.SafeLoader):
    pass


# This is the Loader's native JSON representation of an unevaluated !!js node.
# Inline plugin definitions keep the profile's module-resolution context; an
# external cordis:include switches it to the preset folder and fails to import
# the host-installed packages on dsh 0.1.7.
PresetLoader.add_constructor('tag:yaml.org,2002:js',
                             lambda loader, node: {'__jsExpr': loader.construct_scalar(node)})


def at_least(version, minimum):
    def parse(value):
        match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:-([\w.-]+))?(?:\+[\w.-]+)?', value)
        if not match:
            raise ValueError(f'无法识别 dsh 版本：{value}')
        release = tuple(map(int, match.group(1, 2, 3)))
        prerelease = match.group(4)
        parts = tuple((0, int(part)) if part.isdigit() else (1, part)
                      for part in prerelease.split('.')) if prerelease else ()
        return release, not bool(prerelease), parts
    return parse(version) >= parse(minimum)


def installed_version():
    try:
        result = subprocess.run(['dsh', '--version'], capture_output=True, text=True,
                                encoding='utf-8', timeout=15, shell=os.name == 'nt')
    except FileNotFoundError:
        return None
    if result.returncode:
        # cmd.exe reports a missing npm shim as a nonzero exit, not ENOENT.
        if os.name == 'nt':
            import shutil
            if shutil.which('dsh') is None:
                return None
        raise ValueError('dsh --version 运行失败，请修复 dsh 或显式传入 --dsh-version')
    return result.stdout.strip()


def read(path):
    if not path.exists():
        return ''
    with path.open(encoding='utf-8', newline='') as handle:
        return handle.read()


def without_managed(text):
    if BEGIN not in text and END not in text:
        return text
    pattern = rf'(?m)^{re.escape(BEGIN)}\r?\n[\s\S]*?^{re.escape(END)}(?:\r?\n|$)'
    stripped, count = re.subn(pattern, '', text)
    if count != 1 or BEGIN in stripped or END in stripped:
        raise ValueError('StudyMate 注册标记不完整或重复，请先检查 cordis.patch.yml')
    return stripped


def parse_patch(text, path):
    try:
        data = yaml.load(text, Loader=PatchLoader)
        node = yaml.compose(text, Loader=PatchLoader)
    except yaml.YAMLError as error:
        raise ValueError(f'无法解析 {path}，不会覆盖原配置：{error}') from error
    if node is not None and not isinstance(node, yaml.SequenceNode):
        raise ValueError(f'{path} 顶层必须是 YAML 列表')
    def validate(entries):
        if not isinstance(entries, list):
            raise ValueError(f'{path} 的配置行必须是 YAML 列表')
        for row in entries:
            if not isinstance(row, dict):
                raise ValueError(f'{path} 的配置行必须是 YAML 对象')
            if 'insert' in row:
                validate(row['insert'])
            if row.get('group') is True and isinstance(row.get('config'), list):
                validate(row['config'])
    validate(data or [])
    return data or [], node


def rows(data):
    # A plugin's own config is not a Loader patch.
    for row in data:
        yield row
        if isinstance(row.get('insert'), list):
            yield from rows(row['insert'])
        if row.get('group') is True and isinstance(row.get('config'), list):
            yield from rows(row['config'])


def learning_rows(data):
    return [row for row in rows(data)
            if row.get('name') in (None, '', PLUGIN) and isinstance(row.get('config'), dict)
            and row['config'].get('id') == 'learning']


def insert_managed(text, node, entries):
    encoded = [json.dumps(row, ensure_ascii=False) for row in entries]
    if node is not None and node.flow_style:
        # Keep the original flow-list text, including comments and !!js tags.
        closing = node.end_mark.index - 1
        prefix = text[:closing]
        # A trailing comma before an optional comment already separates items.
        tokens = list(yaml.scan(text, Loader=PatchLoader))
        from yaml.tokens import FlowSequenceEndToken, FlowEntryToken
        end = next(i for i, token in enumerate(tokens)
                   if isinstance(token, FlowSequenceEndToken) and token.start_mark.index == closing)
        comma = bool(node.value) and not isinstance(tokens[end - 1], FlowEntryToken)
        separator = '' if prefix.endswith('\n') else '\n'
        payload = ',\n'.join(encoded)
        block = f'{separator}{BEGIN}\n{"," if comma else ""}{payload}\n{END}\n'
        return prefix + block + text[closing:]
    position = node.end_mark.index if node is not None else len(text)
    prefix = text[:position]
    payload = ''.join(f'- {row}\n' for row in encoded)
    block = f'{BEGIN}\n{payload}{END}\n'
    return prefix + ('' if not prefix or prefix.endswith('\n') else '\n') + block + text[position:]


def atomic_write(path, text):
    if path.is_symlink():
        raise ValueError(f'为避免改动其他目录，不覆盖符号链接：{path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                         dir=path.parent, prefix='.studymate-', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
        if path.exists():
            os.chmod(temporary, path.stat().st_mode)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def bundle_selected(profile_dir):
    manifest = profile_dir / 'package.json'
    if not manifest.exists():
        return False
    try:
        data = json.loads(read(manifest))
        bundles = data.get('dsh', {}).get('profile', {}).get('bundles', [])
    except (ValueError, AttributeError) as error:
        raise ValueError(f'无法解析 {manifest}，未修改配置') from error
    if not isinstance(bundles, list) or any(not isinstance(name, str) for name in bundles):
        raise ValueError(f'{manifest} 的 dsh.profile.bundles 必须是包名列表；未修改配置')
    return BUNDLE in bundles


def check_native_overrides(data, path, *, standalone, selected, global_patch=False):
    for row in rows(data):
        introduced = row.get('insert', [])
        if row.get('group') is True and isinstance(row.get('config'), list):
            introduced = [*introduced, *row['config']]
        if any(item.get('name') == BUNDLE or item.get('id') == BUNDLE_ENTRY_ID
               for item in rows(introduced)):
            raise ValueError(f'{path} 有手动插入的 StudyMate 入口；请先处理该声明，未修改配置')
        if row.get('id') == ENTRY_ID:
            raise ValueError(f'{path} 的 {ENTRY_ID} 已被手动配置使用；未修改配置')
        if row.get('id') != BUNDLE_ENTRY_ID:
            continue
        if row.get('name') not in (None, '', BUNDLE):
            raise ValueError(f'{path} 的 studymate id 已被其他插件使用；未修改配置')
        if row.get('group'):
            raise ValueError(f'{path} 的 studymate 入口被设为 group，无法安全切换；未修改配置')
        disabled = row.get('disabled', False)
        if not standalone and disabled is not False:
            raise ValueError(f'{path} 有手动停用 StudyMate 的配置；请先处理该配置，未修改配置')
        if standalone and selected and global_patch and 'disabled' in row and disabled is not True:
            raise ValueError(f'{path} 的全局配置会重新启用 StudyMate 原生入口；未修改配置')


def install(args):
    native = args.bundle
    handoff = args.mode == 'native'
    if native and handoff:
        raise ValueError('--bundle 不可与 --mode native 同时使用')
    version = None if native else args.dsh_version if args.dsh_version is not None else installed_version()
    modern = native or version is not None and at_least(version, '0.1.7-alpha.1')
    if handoff and not modern:
        raise ValueError('切换原生安装需要 DSH 0.1.7-alpha.1+；旧版请使用默认 install')
    workflow = 'ptc' if native or version is not None and at_least(version, '0.1.6-alpha.1') else 'worker-thread'
    home = Path(args.dsh_home).expanduser().absolute()
    profile = args.profile
    if not profile or '/' in profile or '\\' in profile or '\x00' in profile or profile.lower() in ('.', '..', 'node_modules', 'desktop'):
        raise ValueError('--profile 必须是单个配置名称，不能包含路径分隔符，也不能使用 node_modules 或 desktop')
    preset = Path(args.preset_dir) / 'agent.cordis.yml'
    agent = preset.read_text(encoding='utf-8')
    agent = re.sub(r'(@deepseek-ai/dsh-workflow-|\bid: workflow-)(?:worker-thread|ptc)\b',
                   lambda match: match.group(1) + workflow, agent)
    patch = home / 'profiles' / profile / 'cordis.patch.yml'
    selected = bundle_selected(patch.parent)
    if handoff and not selected:
        raise ValueError(f'请先运行 dsh plugin --profile {profile} add @yunmiao/studymate，再切换原生安装')
    bundle = native or handoff
    original = read(patch)
    clean = without_managed(original)
    data, node = parse_patch(clean, patch)
    home_patch = home / 'cordis.patch.yml'
    home_data, _ = parse_patch(read(home_patch), home_patch)
    if learning_rows(home_data):
        raise ValueError(f'{home_patch} 已声明 learning 预设，请先处理该全局声明；未修改配置')
    if learning_rows(data):
        raise ValueError(f'{patch} 已手动声明 learning 预设，请先处理该声明；未修改配置')
    if native and BEGIN in original:
        raise ValueError('学习模式仍由 npx 管理；如需切换，请运行 '
                         f'npx -y @yunmiao/studymate@latest install --mode native --profile {profile} 后重启 DSH')
    for entries, location in [(data, patch), (home_data, home_patch)]:
        check_native_overrides(entries, location, standalone=not bundle,
                               selected=selected, global_patch=location == home_patch)
    updated = original if native else clean
    managed = []
    if modern:
        metadata = yaml.safe_load(read(Path(args.preset_dir) / 'preset.yml')) or {}
        if not isinstance(metadata, dict):
            raise ValueError('学习预设元数据必须是对象；未修改配置')
        config = {key: metadata[key] for key in ('name', 'description', 'order') if key in metadata}
        plugins = yaml.load(agent, Loader=PresetLoader)
        if not isinstance(plugins, list):
            raise ValueError('学习预设必须是插件列表；未修改配置')
        config.update(id='learning', plugins=plugins)
        if not bundle:
            managed.append({'insert': [{'id': ENTRY_ID, 'name': PLUGIN,
                                        'disabled': DECLARATIVE_DISABLED, 'config': config}]})
    if selected and not bundle:
        managed.append({'id': BUNDLE_ENTRY_ID, 'name': BUNDLE, 'disabled': True})
    if managed:
        updated = insert_managed(clean, node, managed)
    elif not native and updated != original and node is None:
        # A comment-only document parses as null, which DSH refuses to load.
        updated += ('' if not updated or updated.endswith('\n') else '\n') + '[]\n'
    parse_patch(updated, patch)
    # Do not touch active profile configuration when the npm installer stages an update.
    changed = not native and updated != original
    output = Path(args.patch_output) if args.patch_output else patch
    if preset.is_symlink() or changed and output.is_symlink():
        raise ValueError('预设或配置文件是符号链接；未修改配置')
    atomic_write(preset, agent)
    if changed:
        atomic_write(output, updated)
    result = {'patchPath': str(output) if changed else None, 'patchChanged': changed,
              'mode': 'bundle' if bundle else 'declarative' if modern else 'legacy'}
    if bundle:
        result['config'] = config
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preset-dir', required=True)
    parser.add_argument('--preset-target', required=True)
    parser.add_argument('--dsh-home', required=True)
    parser.add_argument('--profile', default='web')
    parser.add_argument('--mode', choices=['standalone', 'native'], default='standalone')
    parser.add_argument('--dsh-version')
    parser.add_argument('--patch-output')
    parser.add_argument('--bundle', action='store_true', help='由 DSH 插件注册预设，不写入独立声明')
    try:
        print(json.dumps(install(parser.parse_args()), ensure_ascii=False))
    except (ValueError, OSError, subprocess.SubprocessError, yaml.YAMLError) as error:
        print(f'StudyMate：{error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
