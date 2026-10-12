#!/usr/bin/env python3
"""两个「总控机械活」脚本的回归测试：位次重命名 + 空题理由回填。

被测：
    scripts/renumber_lessons.py      大纲插/删节点以后，按 nodes: 顺序重排 lessons/ 的文件名序号
    scripts/apply_empty_reasons.py   把出题角色的 `empty_reason` 打进 ::: quiz 题目位置

两个脚本都在改**别人的文件**（讲解角色的内容文件、交付课件的文件名），所以每个用例除了断言
输出，都拿 md5 快照核对「报错时盘上一个字都没动」——`--dry-run` 同样要一字未动。凡是「该拦下」
的用例都同时钉住三件事：退出码 1、报出该报的那条、文件没变。

临时科目全造在 tempfile 里（`fixtures.py` 造大纲与最小内容文件），**不读也不写任何真实工作区**。

用法：python3 scripts/tests/test_lesson_scripts.py
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures  # noqa: E402

TESTS_DIR = Path(__file__).resolve().parent
REPO = TESTS_DIR.parents[1]
RENUMBER = REPO / 'scripts' / 'renumber_lessons.py'
APPLY = REPO / 'scripts' / 'apply_empty_reasons.py'

# 三个课时（`cpp.types` 的节点 id 带点，用来钉住 `0002-cpp.types.quiz.json` 这种双扩展名的拆法）
NODES3 = [('hello.first', '概念', '你好世界'),
          ('cpp.types', '概念', '类型与变量'),
          ('cpp.io', '概念', '读入与输出')]
NODES4 = [('hello.first', '概念', '你好世界'),
          ('cpp.branch', '概念', '分支与循环'),
          ('cpp.types', '概念', '类型与变量'),
          ('cpp.io', '概念', '读入与输出')]

CASES = []


def case(func):
    """登记一个用例：用例的 docstring 第一行就是它的名字。"""
    CASES.append((func.__doc__.strip().splitlines()[0], func))
    return func


class Case:
    """一个用例的断言盒：失败不中断，攒起来一起报（与 fixtures.check 的报错口径一致）。"""

    def __init__(self, label):
        self.label = label
        self.slug = re.sub(r'[^0-9A-Za-z]+', '-', label).strip('-')[:40] or 'case'
        self.problems = []

    def expect(self, condition, message):
        if not condition:
            self.problems.append(message)

    def has(self, output, *needles):
        for needle in needles:
            self.expect(needle in output, f'输出里应含 {needle!r}；实际：\n{output.strip()}')

    def lacks(self, output, *needles):
        for needle in needles:
            self.expect(needle not in output, f'输出里不该出现 {needle!r}；实际：\n{output.strip()}')

    def same(self, before, after, note='盘上的文件被动了'):
        changed = [name for name, digest in before.items() if after.get(name) != digest]
        changed += [name for name in after if name not in before]
        self.expect(not changed, f'{note}（{len(changed)} 处：{"、".join(changed[:6])}）；'
                                 f'实际：\n{_tree(after)}')

    def gone(self, *paths):
        for path in paths:
            self.expect(not os.path.exists(path), f'{path} 应该已经不在了')

    def present(self, *paths):
        for path in paths:
            self.expect(os.path.isfile(path), f'{path} 应该在，但没有')


def _tree(snapshot):
    return '\n'.join(f'      {name}' for name in sorted(snapshot)) or '      （空目录）'


def run(script, *args):
    """跑一个被测脚本，返回 (退出码, stdout, stderr)。"""
    proc = subprocess.run([sys.executable, str(script), *[str(arg) for arg in args]],
                          capture_output=True, text=True, encoding='utf-8')
    return proc.returncode, proc.stdout, proc.stderr


def snapshot(root):
    """目录下所有文件的 md5（相对路径 → 摘要）：用来断言「一个字都没动」。"""
    digests = {}
    for path in sorted(Path(root).rglob('*')):
        if path.is_file():
            digests[str(path.relative_to(root))] = hashlib.md5(path.read_bytes()).hexdigest()
    return digests


def outline(subject, nodes):
    """按 nodes 顺序重写 curriculum.yaml——插节点、删节点都只是重写这个文件。"""
    lines = ['nodes:']
    for node_id, kind, title in nodes:
        lines += [f'- id: {node_id}', f'  title: {title}', f'  kind: {kind}']
    Path(subject, 'curriculum.yaml').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def write(subject, name, text, newline='\n'):
    """往 lessons/ 写一个文件（newline='\\r\\n' 就写成 CRLF），返回路径。"""
    path = os.path.join(subject, 'lessons', name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Path(path).write_bytes(text.replace('\n', newline).encode('utf-8'))
    return path


def write_tsv(root, text, name='reasons.tsv'):
    """写 TSV，返回路径。"""
    path = os.path.join(root, name)
    Path(path).write_bytes(text.encode('utf-8'))
    return path


def lesson_md(subject, name='0002-cpp.types.md'):
    return os.path.join(subject, 'lessons', name)


# ══════════════════════════════════════════════════════════════════
# renumber_lessons.py
# ══════════════════════════════════════════════════════════════════

@case
def renumber_normal(box, root):
    """1 正常路径：插节点后整体后移，三件一起改、内容逐字不变"""
    subject = fixtures.write_subject(root, nodes=NODES3)
    write(subject, '0001-hello.first.md', '#1 你好世界\n')
    write(subject, '0001-hello.first.html', '<html>1</html>\n')
    write(subject, '0002-cpp.types.md', '#2 类型与变量\n')
    write(subject, '0002-cpp.types.quiz.json', '{"整型的范围": []}\n')
    write(subject, '0002-cpp.types.html', '<html>2</html>\n')
    write(subject, '0003-cpp.io.md', '#3 读入与输出\n')
    before = snapshot(root)
    outline(subject, NODES4)                                  # 在位置 2 插进 cpp.branch

    code, out, err = run(RENUMBER, subject)
    box.expect(code == 0, f'退出码应为 0，实际 {code}；stderr：\n{err}')
    box.has(out,
            '0002-cpp.types.md → 0003-cpp.types.md',
            '0002-cpp.types.quiz.json → 0003-cpp.types.quiz.json',
            '0002-cpp.types.html → 0003-cpp.types.html',
            '0003-cpp.io.md → 0004-cpp.io.md',
            '改了 2 个节点的 4 个文件 / 渲染 0 个页面')
    box.lacks(out, '未处理', '0001-hello.first.md →')
    lessons = os.path.join(subject, 'lessons')
    box.present(os.path.join(lessons, '0003-cpp.types.md'),
                os.path.join(lessons, '0003-cpp.types.quiz.json'),
                os.path.join(lessons, '0003-cpp.types.html'),
                os.path.join(lessons, '0004-cpp.io.md'))
    box.gone(os.path.join(lessons, '0002-cpp.types.md'),
             os.path.join(lessons, '0002-cpp.types.quiz.json'),
             os.path.join(lessons, '0002-cpp.types.html'),
             os.path.join(lessons, '0003-cpp.io.md'))
    after = snapshot(root)
    # 改名不改内容：新旧名字下的摘要一一对上
    for old, new in (('lessons/0002-cpp.types.md', 'lessons/0003-cpp.types.md'),
                     ('lessons/0002-cpp.types.quiz.json', 'lessons/0003-cpp.types.quiz.json'),
                     ('lessons/0002-cpp.types.html', 'lessons/0003-cpp.types.html'),
                     ('lessons/0003-cpp.io.md', 'lessons/0004-cpp.io.md')):
        box.expect(after.get(new) == before.get(old), f'{old} 的内容应原样落到 {new}')
    box.expect(after.get('lessons/0001-hello.first.md') == before.get('lessons/0001-hello.first.md'),
               '没轮到改的文件不该动')


@case
def renumber_dry_run(box, root):
    """2 --dry-run：打印计划与「会渲染几个」，盘上一个字都没动"""
    subject = fixtures.write_subject(root, nodes=NODES3)
    write(subject, '0002-cpp.types.md', '#2\n')
    write(subject, '0003-cpp.io.md', '#3\n')
    outline(subject, NODES4)
    before = snapshot(root)

    code, out, err = run(RENUMBER, subject, '--dry-run', '--render')
    box.expect(code == 0, f'退出码应为 0，实际 {code}；stderr：\n{err}')
    box.has(out, '[dry-run] 0002-cpp.types.md → 0003-cpp.types.md',
            '[dry-run] 0003-cpp.io.md → 0004-cpp.io.md',
            '[dry-run] 改了 2 个节点的 2 个文件 / 渲染 2 个页面')
    box.same(before, snapshot(root), '--dry-run 不该动盘')


@case
def renumber_delete_node(box, root):
    """3 删节点：后面的位次前移（0003 → 0002、0004 → 0003）"""
    subject = fixtures.write_subject(root, nodes=NODES4)
    for name in ('0001-hello.first.md', '0002-cpp.branch.md', '0003-cpp.types.md', '0004-cpp.io.md'):
        write(subject, name, f'{name}\n')
    before = snapshot(root)
    outline(subject, NODES3)                                  # 删掉 cpp.branch

    code, out, err = run(RENUMBER, subject)
    box.expect(code == 0, f'退出码应为 0，实际 {code}；stderr：\n{err}')
    box.has(out, '0003-cpp.types.md → 0002-cpp.types.md', '0004-cpp.io.md → 0003-cpp.io.md',
            '改了 2 个节点的 2 个文件 / 渲染 0 个页面')
    after = snapshot(root)
    box.expect(after.get('lessons/0002-cpp.types.md') == before.get('lessons/0003-cpp.types.md'),
               '前移后的内容应原样')
    box.present(lesson_md(subject, '0002-cpp.types.md'), lesson_md(subject, '0003-cpp.io.md'))


@case
def renumber_target_taken(box, root):
    """4 目标名被别的文件占着：报错退出 1，整批不动"""
    subject = fixtures.write_subject(root, nodes=NODES3)
    write(subject, '0002-cpp.types.md', '#2\n')
    os.makedirs(os.path.join(subject, 'lessons', '0003-cpp.types.md'))   # 名字被一个目录占着
    outline(subject, NODES4)
    before = snapshot(root)

    code, out, err = run(RENUMBER, subject)
    box.expect(code == 1, f'退出码应为 1，实际 {code}；stdout：\n{out}')
    box.has(err, '0003-cpp.types.md:1', '目标名已存在', '0002-cpp.types.md')
    box.lacks(out, '→', '改了')                               # 有错就不给计划、不给汇总
    box.same(before, snapshot(root))
    box.present(lesson_md(subject, '0002-cpp.types.md'))


@case
def renumber_duplicate_copy(box, root):
    """5 一个节点两份同名后缀：报错退出 1，整批不动"""
    subject = fixtures.write_subject(root, nodes=NODES3)
    write(subject, '0001-cpp.types.md', '#旧的一份\n')
    write(subject, '0003-cpp.types.md', '#新的一份\n')
    before = snapshot(root)

    code, out, err = run(RENUMBER, subject)
    box.expect(code == 1, f'退出码应为 1，实际 {code}；stdout：\n{out}')
    box.has(err, '节点 cpp.types 的 .md 有 2 份', '0001-cpp.types.md', '0003-cpp.types.md')
    box.same(before, snapshot(root), '两份都该原样留着，等人工挑一份')


@case
def renumber_unknown_names(box, root):
    """6 认不出的命名：一个都不动，列进「未处理」清单、stderr 提示、退出码仍是 0"""
    subject = fixtures.write_subject(root, nodes=NODES3)
    write(subject, '0002-cpp.types.md', '#2\n')
    for name in ('notes.md', '0009-ghost.md', '08-cpp.io.md', '0003-cpp.io.txt'):
        write(subject, name, '别人家的文件\n')
    outline(subject, NODES4)
    before = snapshot(root)

    code, out, err = run(RENUMBER, subject)
    box.expect(code == 0, f'未处理项不影响退出码（应为 0），实际 {code}；stderr：\n{err}')
    box.has(out, '0002-cpp.types.md → 0003-cpp.types.md',
            '未处理 4 个文件（没动它们）',
            'notes.md —— 没有「4 位序号-」前缀',
            '0009-ghost.md —— 节点 id「ghost」不在 curriculum.yaml 的 nodes: 里',
            '08-cpp.io.md —— 序号 08 不是 4 位补零',
            '0003-cpp.io.txt —— 认不出的命名（后缀要正好是 md / quiz.json / html）')
    box.has(err, '提示:', '4 个文件没被接管')
    box.expect(out.strip().splitlines()[-1] == '改了 1 个节点的 1 个文件 / 渲染 0 个页面',
               f'汇总要是 stdout 的最后一行；实际：{out.strip().splitlines()[-1]!r}')
    box.present(lesson_md(subject, '0003-cpp.types.md'))
    after = snapshot(root)
    for name in ('lessons/notes.md', 'lessons/0009-ghost.md', 'lessons/08-cpp.io.md',
                 'lessons/0003-cpp.io.txt'):
        box.expect(after.get(name) == before.get(name), f'{name} 不该动')


@case
def renumber_render_ok(box, root):
    """7 --render：改名后重渲染，页面里的序号与上下节课指针按新位次重写"""
    subject = fixtures.write_subject(root, nodes=NODES3)
    fixtures.write_content(subject, 1, 'hello.first')
    fixtures.write_content(subject, 2, 'cpp.types')
    fixtures.write_content(subject, 3, 'cpp.io')
    outline(subject, NODES4)                                  # 位置 2 插进 cpp.branch（还没有内容文件）
    for name in ('0002-cpp.types.md', '0003-cpp.io.md'):
        box.present(lesson_md(subject, name))

    code, out, err = run(RENUMBER, subject, '--render')
    box.expect(code == 0, f'退出码应为 0，实际 {code}；stderr：\n{err}')
    box.has(out, '改了 2 个节点的 2 个文件 / 渲染 2 个页面')
    html_path = os.path.join(subject, 'lessons', '0003-cpp.types.html')
    box.present(html_path, os.path.join(subject, 'lessons', '0004-cpp.io.html'))
    page = Path(html_path).read_text(encoding='utf-8')
    box.expect('0003' in page, '重渲染的页面里应出现新序号 0003')
    box.expect('0002-cpp.branch.html' in page, '上节课指针应指向新位次的邻居 0002-cpp.branch.html')
    box.expect('0004-cpp.io.html' in page, '下节课指针应指向 0004-cpp.io.html')
    box.gone(os.path.join(subject, 'lessons', '0002-cpp.types.html'))


@case
def renumber_render_fail_keeps_renames(box, root):
    """8 --render 失败：如实报错退出 1，但改名不回滚"""
    subject = fixtures.write_subject(root, nodes=[('hello.first', '概念', '你好世界'),
                                                  ('cpp.types', '概念', '类型与变量')])
    fixtures.write_content(subject, 1, 'hello.first')
    write(subject, '0002-cpp.types.md',
          '---\ntitle: 类型与变量\ngoal: 分清类型。\n---\n\n## 正文\n\n'
          '::: quiz 理解 锚点：整型的范围\n:::\n')            # 有题目位置却没交题库 → 渲染必失败
    write(subject, '0002-cpp.types.html', '<html>旧产物</html>\n')
    outline(subject, [('cpp.branch', '概念', '分支与循环')] + NODES3[:2])   # 前面插一节，两个都后移

    code, out, err = run(RENUMBER, subject, '--render')
    box.expect(code == 1, f'渲染失败要退出 1，实际 {code}')
    box.has(out, '0001-hello.first.md → 0002-hello.first.md',
            '0002-cpp.types.md → 0003-cpp.types.md',
            '改了 2 个节点的 3 个文件 / 渲染 1 个页面')       # hello.first 渲染成功、cpp.types 失败
    box.has(err, '找不到题库文件', '渲染失败', '不回滚')
    lessons = os.path.join(subject, 'lessons')
    box.present(os.path.join(lessons, '0003-cpp.types.md'), os.path.join(lessons, '0003-cpp.types.html'),
                os.path.join(lessons, '0002-hello.first.md'), os.path.join(lessons, '0002-hello.first.html'))
    box.gone(os.path.join(lessons, '0002-cpp.types.md'), os.path.join(lessons, '0001-hello.first.md'))


@case
def renumber_swap_guard(box, root):
    """9 兜底：目标名被本次要改走的文件占着时走临时名——绝不覆盖（直接调 apply_renames）"""
    sys.path.insert(0, str(REPO / 'scripts'))
    import renumber_lessons
    lessons = os.path.join(root, 'lessons')
    os.makedirs(lessons)
    for name, body in (('0001-cpp.types.md', '旧的第 1 份\n'), ('0002-cpp.types.md', '旧的第 2 份\n')):
        Path(lessons, name).write_bytes(body.encode('utf-8'))
    # 「一个节点一件」已经把这种数据拦在 CLI 外面了，这一层是防 `os.rename` 静默覆盖的兜底：
    # 两个目标名都被本次要改走的文件占着，只能先过临时名。
    renames = [{'node': 'cpp.types', 'ext': 'md', 'old': '0002-cpp.types.md', 'new': '0001-cpp.types.md'},
               {'node': 'cpp.types', 'ext': 'md', 'old': '0001-cpp.types.md', 'new': '0002-cpp.types.md'}]
    failure = renumber_lessons.apply_renames(lessons, renames)
    box.expect(failure is None, f'换位改名不该失败：{failure}')
    box.expect(Path(lessons, '0001-cpp.types.md').read_text(encoding='utf-8') == '旧的第 2 份\n',
               '换位后 0001 应拿到原先 0002 的内容')
    box.expect(Path(lessons, '0002-cpp.types.md').read_text(encoding='utf-8') == '旧的第 1 份\n',
               '换位后 0002 应拿到原先 0001 的内容')
    box.expect(not [name for name in os.listdir(lessons) if name.startswith('.renumber-tmp-')],
               '不该留下临时名')


@case
def renumber_bad_subject(box, root):
    """10 大纲/目录不对：报错退出 1；用法不对退出 2"""
    subject = fixtures.write_subject(root, nodes=NODES3)
    code, out, err = run(RENUMBER)                            # 没给参数
    box.expect(code == 2, f'没有参数应退出 2，实际 {code}')
    box.has(err, '用法错误', 'renumber_lessons.py')
    code, out, err = run(RENUMBER, subject, '--wipe')          # 未知参数
    box.expect(code == 2, f'未知参数应退出 2，实际 {code}')
    box.has(err, '未知参数 --wipe')
    code, out, err = run(RENUMBER, os.path.join(root, '没有这个科目'))
    box.expect(code == 1, f'找不到大纲应退出 1，实际 {code}')
    box.has(err, 'curriculum.yaml', '找不到大纲文件')
    empty = os.path.join(root, 'subject-empty')
    os.makedirs(empty)
    Path(empty, 'curriculum.yaml').write_text('nodes: []\n', encoding='utf-8')
    code, out, err = run(RENUMBER, empty)
    box.expect(code == 1, f'空大纲应退出 1，实际 {code}')
    box.has(err, '没有 nodes:')
    nolessons = os.path.join(root, 'subject-nolessons')
    os.makedirs(nolessons)
    Path(nolessons, 'curriculum.yaml').write_text('nodes:\n- id: a\n  title: A\n  kind: 概念\n',
                                                  encoding='utf-8')
    code, out, err = run(RENUMBER, nolessons)
    box.expect(code == 1, f'没有 lessons/ 应退出 1，实际 {code}')
    box.has(err, '找不到课件目录')


# ══════════════════════════════════════════════════════════════════
# apply_empty_reasons.py
# ══════════════════════════════════════════════════════════════════

SOURCE = '''---
title: 读入与输出
goal: 能把输入读进来、把答案打出去。
---

## 正文

这一段没有问题位。

::: quiz 理解 锚点：整型的范围
:::

中间还隔着一段话。

::: quiz 应用 锚点：分档数组版

块里本来就有一个空行。

:::
'''

EXPECTED = '''---
title: 读入与输出
goal: 能把输入读进来、把答案打出去。
---

## 正文

这一段没有问题位。

::: quiz 理解 锚点：整型的范围
empty_reason: 本轮不出题，过关标准在 lab
:::

中间还隔着一段话。

::: quiz 应用 锚点：分档数组版

块里本来就有一个空行。

empty_reason: 题量够了，下一轮补
:::
'''

TWO_ROWS = ('# 出题角色这一轮的空题理由\n'
            '\n'
            '整型的范围\t本轮不出题，过关标准在 lab\n'
            '分档数组版\t题量够了，下一轮补\n')


def subject_with_source(root, nodes=NODES3, number=2, node='cpp.types'):
    """造一个科目 + 一份两处题目位置的内容文件，返回 (科目路径, TSV 路径)。"""
    subject = fixtures.write_subject(root, nodes=nodes)
    write(subject, f'{number:04d}-{node}.md', SOURCE)
    return subject, write_tsv(root, TWO_ROWS)


@case
def apply_normal(box, root):
    """11 正常路径：两处插进对的块、行号对、其余逐字不变、跳过行数报对"""
    subject, tsv = subject_with_source(root)
    md = lesson_md(subject)

    code, out, err = run(APPLY, subject, 'cpp.types', tsv)
    box.expect(code == 0, f'退出码应为 0，实际 {code}；stderr：\n{err}')
    box.has(out, f'插入了 empty_reason: 整型的范围 → {md}:11',
            f'插入了 empty_reason: 分档数组版 → {md}:20',
            '2 处 / 跳过 2 行')                               # 空行 + `#` 注释
    box.expect(Path(md).read_text(encoding='utf-8') == EXPECTED,
               '写回的内容与预期不一致：\n' + Path(md).read_text(encoding='utf-8'))
    box.expect(Path(md).read_bytes().endswith(b':::\n'), '末尾换行应与原文件一致')


@case
def apply_dry_run(box, root):
    """12 --dry-run：打印将插入的行与位置，文件一字未动"""
    subject, tsv = subject_with_source(root)
    md = lesson_md(subject)
    before = snapshot(root)

    code, out, err = run(APPLY, subject, 'cpp.types', tsv, '--dry-run')
    box.expect(code == 0, f'退出码应为 0，实际 {code}；stderr：\n{err}')
    box.has(out, f'[dry-run] 插入了 empty_reason: 整型的范围 → {md}:11',
            f'[dry-run] 插入了 empty_reason: 分档数组版 → {md}:20',
            '[dry-run] 2 处 / 跳过 2 行')
    box.same(before, snapshot(root), '--dry-run 不该动盘')


@case
def apply_anchor_missing(box, root):
    """13 锚点在内容文件里找不到：报错退出 1，一个字都不改"""
    subject = fixtures.write_subject(root, nodes=NODES3)
    write(subject, '0002-cpp.types.md', SOURCE)
    tsv = write_tsv(root, '整型的范围\t本轮不出题\n没有这个锚点\t随便一个理由\n')
    before = snapshot(root)

    code, out, err = run(APPLY, subject, 'cpp.types', tsv)
    box.expect(code == 1, f'退出码应为 1，实际 {code}；stdout：\n{out}')
    box.has(err, f'{tsv}:2', '锚点「没有这个锚点」在内容文件里没有对应的 ::: quiz 题目位置')
    box.lacks(out, '插入了')                                  # 一处坏就一处都不写
    box.same(before, snapshot(root))


@case
def apply_duplicate_anchor(box, root):
    """14 同一个锚点被两个 ::: quiz 引用：报错退出 1，一个字都不改"""
    subject = fixtures.write_subject(root, nodes=NODES3)
    write(subject, '0002-cpp.types.md',
          '---\ntitle: 类型与变量\ngoal: 分清类型。\n---\n\n## 正文\n\n'
          '::: quiz 理解 锚点：整型的范围\n:::\n\n::: quiz 应用 锚点：整型的范围\n:::\n')
    tsv = write_tsv(root, '整型的范围\t本轮不出题\n')
    before = snapshot(root)

    code, out, err = run(APPLY, subject, 'cpp.types', tsv)
    box.expect(code == 1, f'退出码应为 1，实际 {code}；stdout：\n{out}')
    box.has(err, '被 2 个 ::: quiz 题目位置引用', '第 8、11 行')
    box.same(before, snapshot(root))


@case
def apply_already_has_reason(box, root):
    """15 块里已经有 empty_reason:：报错退出 1，一个字都不改"""
    subject = fixtures.write_subject(root, nodes=NODES3)
    write(subject, '0002-cpp.types.md',
          '---\ntitle: 类型与变量\ngoal: 分清类型。\n---\n\n## 正文\n\n'
          '::: quiz 理解 锚点：整型的范围\nempty_reason: 上一轮写的理由\n:::\n')
    tsv = write_tsv(root, '整型的范围\t这一轮的理由\n')
    before = snapshot(root)

    code, out, err = run(APPLY, subject, 'cpp.types', tsv)
    box.expect(code == 1, f'退出码应为 1，实际 {code}；stdout：\n{out}')
    box.has(err, ':9', '已经有 empty_reason:')
    box.same(before, snapshot(root))


@case
def apply_duplicate_row(box, root):
    """16 TSV 里同一锚点两次：报错退出 1，一个字都不改"""
    subject = fixtures.write_subject(root, nodes=NODES3)
    write(subject, '0002-cpp.types.md', SOURCE)
    tsv = write_tsv(root, '整型的范围\t第一遍的理由\n整型的范围\t第二遍的理由\n')
    before = snapshot(root)

    code, out, err = run(APPLY, subject, 'cpp.types', tsv)
    box.expect(code == 1, f'退出码应为 1，实际 {code}；stdout：\n{out}')
    box.has(err, f'{tsv}:2', '锚点「整型的范围」在 TSV 里出现两次', '第 1 行、第 2 行')
    box.same(before, snapshot(root))


@case
def apply_bad_rows(box, root):
    """17 锚点为空 / 理由为空 / 理由带前缀 / 多出一列：四条都报，一个字都不改"""
    subject = fixtures.write_subject(root, nodes=NODES3)
    write(subject, '0002-cpp.types.md', SOURCE)
    tsv = write_tsv(root, '\t只有理由没有锚点\n整型的范围\n分档数组版\tempty_reason: 理由\n'
                          '整型的范围\tabc\tdef\n')
    before = snapshot(root)

    code, out, err = run(APPLY, subject, 'cpp.types', tsv)
    box.expect(code == 1, f'退出码应为 1，实际 {code}；stdout：\n{out}')
    box.has(err, f'{tsv}:1', '锚点文本是空的',
            f'{tsv}:2', '理由为空',
            f'{tsv}:3', '不要再写 `empty_reason:` 前缀',
            f'{tsv}:4', '只有两列')
    box.lacks(out, '插入了')
    box.same(before, snapshot(root))


@case
def apply_fenced_anchor(box, root):
    """18 围栏里的 ::: quiz 是代码原文：不算题目位置，锚点照样找不到"""
    subject = fixtures.write_subject(root, nodes=NODES3)
    write(subject, '0002-cpp.types.md',
          '---\ntitle: 类型与变量\ngoal: 分清类型。\n---\n\n## 正文\n\n'
          '```markdown\n::: quiz 理解 锚点：整型的范围\n:::\n```\n')
    tsv = write_tsv(root, '整型的范围\t本轮不出题\n')
    before = snapshot(root)

    code, out, err = run(APPLY, subject, 'cpp.types', tsv)
    box.expect(code == 1, f'退出码应为 1，实际 {code}；stdout：\n{out}')
    box.has(err, '锚点「整型的范围」在内容文件里没有对应的 ::: quiz 题目位置')
    box.same(before, snapshot(root))


@case
def apply_crlf(box, root):
    """19 CRLF 的内容文件：插进去的那行也用 CRLF，其余字节逐字不变"""
    subject = fixtures.write_subject(root, nodes=NODES3)
    md = write(subject, '0002-cpp.types.md', SOURCE, newline='\r\n')
    tsv = write_tsv(root, '整型的范围\t本轮不出题，过关标准在 lab\n')
    want = SOURCE.replace('::: quiz 理解 锚点：整型的范围\n:::',         # 只在那一处插一行
                          '::: quiz 理解 锚点：整型的范围\n'
                          'empty_reason: 本轮不出题，过关标准在 lab\n:::').replace('\n', '\r\n')

    code, out, err = run(APPLY, subject, 'cpp.types', tsv)
    box.expect(code == 0, f'退出码应为 0，实际 {code}；stderr：\n{err}')
    box.has(out, f'插入了 empty_reason: 整型的范围 → {md}:11', '1 处 / 跳过 0 行')
    # 逐字节比：不能把整个文件的行尾翻译成 LF（那是把别人的文件重排一遍）
    box.expect(Path(md).read_bytes() == want.encode('utf-8'),
               'CRLF 文件应只在原处多一行，其余逐字节不变：\n'
               + repr(Path(md).read_bytes()[:160]))


@case
def apply_nothing_to_do(box, root):
    """20 TSV 全是注释与空行：0 处、不写盘、退出 0"""
    subject = fixtures.write_subject(root, nodes=NODES3)
    write(subject, '0002-cpp.types.md', SOURCE)
    tsv = write_tsv(root, '# 这一轮没有空题\n\n\n')
    before = snapshot(root)

    code, out, err = run(APPLY, subject, 'cpp.types', tsv)
    box.expect(code == 0, f'退出码应为 0，实际 {code}；stderr：\n{err}')
    box.has(out, '0 处 / 跳过 3 行')
    box.same(before, snapshot(root))


@case
def apply_bom_tsv(box, root):
    """21 TSV 带 BOM（表格软件导出的那种）：锚点照常匹配，BOM 不算锚点的一部分"""
    subject = fixtures.write_subject(root, nodes=NODES3)
    write(subject, '0002-cpp.types.md', SOURCE)
    tsv = write_tsv(root, '\ufeff整型的范围\t本轮不出题，过关标准在 lab\n')

    code, out, err = run(APPLY, subject, 'cpp.types', tsv)
    box.expect(code == 0, f'退出码应为 0，实际 {code}；stderr：\n{err}')
    box.has(out, '插入了 empty_reason: 整型的范围', '1 处 / 跳过 0 行')


@case
def apply_bad_target(box, root):
    """22 节点不在大纲 / 内容文件没产出 / TSV 不在 / 用法不对：各报各的"""
    subject = fixtures.write_subject(root, nodes=NODES3)
    write(subject, '0002-cpp.types.md', SOURCE)
    tsv = write_tsv(root, TWO_ROWS)
    before = snapshot(root)

    code, out, err = run(APPLY, subject, 'ghost', tsv)
    box.expect(code == 1, f'节点不在大纲应退出 1，实际 {code}')
    box.has(err, '节点 ghost 不在 curriculum.yaml 的 nodes: 里')
    code, out, err = run(APPLY, subject, 'cpp.io', tsv)        # 大纲里有、但还没交内容文件
    box.expect(code == 1, f'内容文件没产出应退出 1，实际 {code}')
    box.has(err, os.path.join('lessons', '0003-cpp.io.md') + ':1', '找不到内容文件')
    code, out, err = run(APPLY, subject, 'cpp.types', os.path.join(root, '没有这个.tsv'))
    box.expect(code == 1, f'TSV 不在应退出 1，实际 {code}')
    box.has(err, '找不到 TSV 文件')
    code, out, err = run(APPLY, subject, 'cpp.types')
    box.expect(code == 2, f'参数不够应退出 2，实际 {code}')
    box.has(err, '用法错误', 'apply_empty_reasons.py')
    code, out, err = run(APPLY, subject, 'cpp.types', tsv, '--go')
    box.expect(code == 2, f'未知参数应退出 2，实际 {code}')
    box.has(err, '未知参数 --go')
    box.same(before, snapshot(root))


def main():
    tmp = tempfile.mkdtemp(prefix='smtest-lesson-scripts-')
    failures = 0
    try:
        for label, func in CASES:
            box = Case(label)
            try:
                func(box, os.path.join(tmp, box.slug))
            except Exception as exc:                          # 用例自己炸了也算失败，别中断整套
                box.problems.append(f'用例抛异常：{exc!r}')
            failures += bool(box.problems)
            fixtures.check(label, not box.problems, '\n'.join(box.problems))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    total = len(CASES)
    print(f'\n{total - failures}/{total} 通过')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
