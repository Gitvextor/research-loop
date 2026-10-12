#!/usr/bin/env python3
"""模板与规格一致：`templates/` 的分节名与键，必须和提示词/schema 写的一致。

为什么单独有这道：规格是散文（写在 SKILL 与 `docs/` 里），模板是另一份文件，两者之间没有测试
连着。真出过事——`templates/GLOSSARY.md` 一直写 `## Terms`，而 `docs/文件归属.md`、
`learning-system`、`image-scout` 三处都按 `## 待掌握`／`## 已掌握` 两节读词：照模板建出来的术语表，
「采图」查不到主题词、主页也没有那两节可读。这类漂移不会有任何报错，只能靠交叉阅读发现。

所以这道**两边一起钉**：规格里写着的分节，模板里必须真有；模板的键，schema 里必须真有。
规格那边改了名而模板没跟、或者模板自创了键，都会红。

用法：python3 scripts/tests/test_templates.py
"""
import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO = TESTS_DIR.parents[1]
TEMPLATES = REPO / 'templates'

failures = 0
total = 0


def check(label, ok, detail=''):
    global failures, total
    total += 1
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f'  — {detail}' if detail and not ok else ''))
    failures += not ok


def read(path):
    return (REPO / path).read_text(encoding='utf-8')


def has_all(text, needles):
    """返回 (全都在, 缺哪些)。"""
    missing = [needle for needle in needles if needle not in text]
    return not missing, missing


def main():
    # ── 一、规格侧：这些分节名是规格定的（改规格要先改这里，再同步模板）────────
    ok, missing = has_all(read('docs/文件归属.md'), ['## 待掌握', '## 已掌握'])
    check('规格仍要求术语表两节（docs/文件归属.md）', ok, f'缺 {missing}')

    ok, missing = has_all(read('.dsh/skills/learning-system/SKILL.md'),
                          ['## Why', '## Success looks like', '## Constraints'])
    check('规格仍要求使命三节（learning-system 建课顺序）', ok, f'缺 {missing}')

    ok, missing = has_all(read('docs/使用说明.md'),
                          ['我是谁 / 教学偏好 / 学习习惯 / 跨科目观察'])
    check('规格仍列出共享记忆四节（docs/使用说明.md §六）', ok, f'缺 {missing}')

    # ── 二、模板侧：照着上面的规格逐条对 ──────────────────────────────────
    ok, missing = has_all(read('templates/GLOSSARY.md'), ['## 待掌握', '## 已掌握'])
    check('templates/GLOSSARY.md 有「待掌握 / 已掌握」两节', ok, f'缺 {missing}')

    ok, missing = has_all(read('templates/MISSION.md'),
                          ['## Why', '## Success looks like', '## Constraints'])
    check('templates/MISSION.md 有使命三节', ok, f'缺 {missing}')

    ok, missing = has_all(read('templates/MEMORY.md'),
                          ['## 我是谁', '## 教学偏好', '## 学习习惯', '## 跨科目观察'])
    check('templates/MEMORY.md 有共享记忆四节', ok, f'缺 {missing}')

    # 科目档案的键：模板与 schema 必须完全一致（模板自创键 = schema 校验会拦下来，
    # schema 加了键而模板没跟 = 学生新建科目时少写一个必填字段）
    schema = json.loads(read('schemas/subject.schema.json'))
    schema_keys = set(schema.get('properties', {}))
    try:
        import yaml
    except ImportError:      # pragma: no cover - 环境缺 pyyaml 时只跳过这一条
        check('templates/subject.yaml 的键与 subject.schema.json 一致（跳过：没有 pyyaml）', True)
    else:
        template_keys = set(yaml.safe_load(read('templates/subject.yaml')) or {})
        check('templates/subject.yaml 的键与 subject.schema.json 完全一致',
              template_keys == schema_keys,
              f'模板多 {sorted(template_keys - schema_keys)} / 模板缺 {sorted(schema_keys - template_keys)}')

    # status 的取值：模板里那个值必须是 schema enum 里的一员（写错的话建课第一步就过不了校验）
    status = (yaml.safe_load(read('templates/subject.yaml')) or {}).get('status')
    check(f'templates/subject.yaml 的 status 取值合法（{status}）',
          status in (schema['properties']['status'].get('enum') or []),
          f'不在 {schema["properties"]["status"].get("enum")} 里')

    print(f'\n{total - failures}/{total} 通过')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
