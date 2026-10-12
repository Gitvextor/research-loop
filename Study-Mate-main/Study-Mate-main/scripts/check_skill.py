#!/usr/bin/env python3
"""校验 SKILL.md 的 frontmatter：解析、name 与目录名一致、按声明断言调用方式。

用法：
  python3 scripts/check_skill.py <skill目录> [<skill目录> ...]
  python3 scripts/check_skill.py .dsh/skills/learning-coach --expect-role
  python3 scripts/check_skill.py .dsh/skills/learning-system --expect-model-invocable
  python3 scripts/check_skill.py .dsh/skills/lesson-design --expect-model-invocable

角色 skill 设 `disable-model-invocation: true`（不可被模型加载，由总控在派发 prompt 里内联）；
协议与 learning-system 不设（可被 `skill` 工具按名字加载）。
"""
import os
import re
import sys

import yaml

FRONTMATTER = re.compile(r'^---\r?\n(.*?)\r?\n---\r?\n', re.S)


def read_frontmatter(skill_dir):
    path = os.path.join(skill_dir, 'SKILL.md')
    with open(path, encoding='utf-8-sig') as handle:
        text = handle.read()
    match = FRONTMATTER.match(text)
    if not match:
        raise ValueError('frontmatter 缺失或格式不对（需以 --- 开头并闭合）')
    meta = yaml.safe_load(match.group(1))
    if not isinstance(meta, dict):
        raise ValueError('frontmatter 必须是 YAML 映射')
    return meta


def main(argv):
    dirs = [a for a in argv if not a.startswith('--')]
    flags = {a for a in argv if a.startswith('--')}
    if not dirs:
        raise SystemExit(__doc__)
    failed = False
    for skill_dir in dirs:
        try:
            meta = read_frontmatter(skill_dir)
        except (OSError, UnicodeDecodeError, yaml.YAMLError, ValueError) as exc:
            failed = True
            print(f'FAIL {skill_dir}: {exc}')
            continue
        expected_name = os.path.basename(os.path.normpath(skill_dir))
        problems = []
        if meta.get('name') != expected_name:
            problems.append(f"name={meta.get('name')!r} 与目录名 {expected_name!r} 不一致")
        if not meta.get('description'):
            problems.append('description 缺失')
        disabled = meta.get('disable-model-invocation', False)
        if not isinstance(disabled, bool):
            problems.append('disable-model-invocation 必须是布尔值 true / false')
        model_invocable = disabled is not True
        if '--expect-model-invocable' in flags and not model_invocable:
            problems.append('本 skill 应允许模型直接调用，但设了 disable-model-invocation')
        if '--expect-role' in flags and model_invocable:
            problems.append('角色/协议 skill 需设 disable-model-invocation: true')
        if problems:
            failed = True
            print(f'FAIL {skill_dir}: ' + '；'.join(problems))
        else:
            print(f'OK   {skill_dir}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
