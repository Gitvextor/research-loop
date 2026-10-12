#!/usr/bin/env python3
"""检查项 8（命名 + 上/下节课指针 + 归属）的回归测试，9 个场景。

每个场景都从 fixture 重建 `lessons/`，只改这一处偏差，再跑检查断言
「该拦的拦住、该放行的放行」。检查项 8 是「悬空指针」成立的前提：上一课的
「下节课」按命名规则预写，下一课照规则起名，链接自己就通了（零回填）。

用法：python3 scripts/tests/test_naming_nav.py
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures  # noqa: E402

# 干净的三课：0001 → 0002 → 0003（大纲 5 个节点，0004/0005 故意没产出，用来测悬空指针）
CLEAN = [
    (1, 'overview-map', 'auto'),
    (2, 'first-program', 'auto'),
    (3, 'io-and-vars', 'auto'),
]

SCENARIOS = []


def scenario(label, lessons, check_node, path_name, want_fail, must=None, must_not=None, rename=None):
    SCENARIOS.append({'label': label, 'lessons': lessons, 'node': check_node, 'path': path_name,
                      'want_fail': want_fail, 'must': must, 'must_not': must_not, 'rename': rename})


scenario('放行：第一课只带下节课', CLEAN, 'overview-map', '0001-overview-map.html', False)
scenario('放行：中间课带上/下节', CLEAN, 'first-program', '0002-first-program.html', False)
scenario('放行：下节课未产出 → 只提示不阻断', CLEAN, 'io-and-vars', '0003-io-and-vars.html', False,
         must='还没产出',
         must_not=['与大纲不符', '指针指向', '缺上节课指针', '缺下节课指针', '不该有'])
scenario('拦：下节课指针指错', [
    (1, 'overview-map', 'auto'),
    (2, 'first-program', [('prev', '0001-overview-map.html', '全景地图'),
                          ('next', '0005-func-and-ref.html', '函数与引用')]),
    (3, 'io-and-vars', 'auto'),
], 'first-program', '0002-first-program.html', True, must='下节课指针指向')
scenario('拦：漏写下节课指针', [
    (1, 'overview-map', 'auto'),
    (2, 'first-program', [('prev', '0001-overview-map.html', '全景地图')]),
    (3, 'io-and-vars', 'auto'),
], 'first-program', '0002-first-program.html', True, must='缺下节课指针')
scenario('拦：第一课写了上节课指针', [
    (1, 'overview-map', [('prev', '0000-x.html', '不存在的上一课'),
                         ('next', '0002-first-program.html', '编译并跑通')]),
    (2, 'first-program', 'auto'),
    (3, 'io-and-vars', 'auto'),
], 'overview-map', '0001-overview-map.html', True, must='不该有上节课指针')
scenario('拦：节点不在大纲里（归属查不出）', CLEAN, 'no-such-node', '0002-first-program.html', True,
         must='不在 curriculum.yaml')
# 下面两个改的只是**文件名**，文件本身照写：节点 id 写错、编号写错都要拦
scenario('拦：文件名里的节点 id 与大纲不符', CLEAN, 'first-program', '0002-compile-and-run.html', True,
         must='与大纲不符', rename=('0002-first-program.html', '0002-compile-and-run.html'))
scenario('拦：序号与大纲位次不符（0002 → 0007）', CLEAN, 'first-program', '0007-first-program.html', True,
         must='与大纲不符', rename=('0002-first-program.html', '0007-first-program.html'))


def build(subject, scenario_item):
    """按场景重建 lessons/：每份课件用指定的指针（'auto' = 按大纲自动填对），需要时改名。"""
    fixtures.clear_lessons(subject)
    for number, node_id, nav in scenario_item['lessons']:
        fixtures.write_lesson(subject, number, node_id, nav=nav)
    if scenario_item['rename']:
        old, new = scenario_item['rename']
        os.rename(os.path.join(subject, 'lessons', old), os.path.join(subject, 'lessons', new))


def main():
    tmp = tempfile.mkdtemp(prefix='smtest-nav-')
    subject = fixtures.write_subject(tmp)
    failures = 0
    for item in SCENARIOS:
        build(subject, item)
        path = os.path.join(subject, 'lessons', item['path'])
        code, out = fixtures.run_gate(path, subject, item['node'])
        ok = (code != 0) == item['want_fail']
        ok = ok and (not item['must'] or item['must'] in out)
        ok = ok and all(phrase not in out for phrase in (item['must_not'] or []))
        failures += not ok
        fixtures.check(item['label'], ok, out if not ok else f'检查={"FAIL" if code else "OK"}')
    total = len(SCENARIOS)
    print(f'\n{total - failures}/{total} 通过')
    shutil.rmtree(tmp, ignore_errors=True)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
