#!/usr/bin/env python3
"""回归测试用的**临时科目**：不依赖任何工作区，自己造 curriculum.yaml 与课件。

检查（`scripts/check_lesson.py`）要判的东西不少（文件名、两类引用、题目块、主题开关、
命名与上下节课指针），所以 fixture 得是一份**能过检查**的最小课件——测试再往里注入
自己那一处偏差，断言才不会被无关的 FAIL 污染。

内容格式那条链路（`scripts/render_lesson.py`）另有一套 fixture：`write_content()` 写内容文件，
`write_quiz()` 写按锚点组织的题库，`run_render()` 跑渲染器——渲染产物再交给 `run_gate()` 判。

用法：
    subject = fixtures.write_subject(tmp)                 # 造科目（5 个概念节点）
    path = fixtures.write_lesson(subject, 2, 'first-program')   # 造第 2 份课件（指针自动填对）
    code, out = fixtures.run_gate(path, subject, 'first-program')

    md = fixtures.write_content(subject, 2, 'first-program')    # 内容文件（默认一份最小正文）
    code, out = fixtures.run_render(subject, 'first-program')   # 渲染成 .html
"""
import json
import os
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO = TESTS_DIR.parents[1]
GATE = REPO / 'scripts' / 'check_lesson.py'
POOL_CHECK = REPO / 'scripts' / 'check_pool.py'
RENDER = REPO / 'scripts' / 'render_lesson.py'

# 默认大纲：全是「概念」课——概念课不要求 lab，fixture 就不用造 lab 产物
DEFAULT_NODES = [
    ('overview-map', '概念', '全景地图'),
    ('first-program', '概念', '编译并跑通'),
    ('io-and-vars', '概念', '读入数据与输出答案'),
    ('branch-and-loop', '概念', '分支与循环'),
    ('func-and-ref', '概念', '函数与引用'),
]

VALID_QUIZ = ('<div class="quiz" data-quiz=\'[{"q":"这是题面？","opts":["A","B"],'
              '"ans":0,"why":"一句解释"}]\'></div>')

# 课件引用的共享层与科目组件：检查项 10 会核对它们真实存在，所以 fixture 要落一份占位文件。
# 课件的相对路径按**真实布局**写：`<root>/.learning/subjects/<slug>/lessons/x.html`
#   → 共享层 `../../../assets/…`（= `<root>/.learning/assets/`）、科目组件 `../assets/…`。
SHARED_STUBS = ('sayo/sayo.css', 'sayo/sayo.js', 'learn-theme.css', 'learn-theme.js',
                'katex/katex.min.css', 'katex/katex.min.js', 'lesson-math.js')
COMPONENT_STUBS = ('style.css', 'quiz.js', 'lesson-toc.js')

# 能过检查的最小课件：两类引用齐全、有主题开关与接线、有一个合法题目块、没有题目位置残留。
# 相对路径按 lessons/<file>.html → 共享层 ../../../assets/、科目组件 ../assets/ 写。
LESSON_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · 测试科目</title>
<link rel="stylesheet" href="../../../assets/sayo/sayo.css">
<link rel="stylesheet" href="../../../assets/learn-theme.css">
<link rel="stylesheet" href="../assets/style.css">
<script src="../../../assets/learn-theme.js"></script>
<script>LearnTheme.apply();</script>
</head>
<body class="lesson-body">

<nav class="lesson-bar">
  <a href="../index.html">← 返回课程</a>
  <span>测试科目</span>
  <span class="lesson-bar__no">{number}</span>
  <label class="syo-toggle syo-toggle--theme lesson-bar__toggle" title="切换深浅主题">
    <input type="checkbox" id="lesson-theme-checkbox" checked>
    <span class="syo-toggle-track"></span>
    <span class="syo-toggle-knob"></span>
  </label>
</nav>

<article class="lesson">

  <header class="lesson-header">
    <span class="lesson-header__eyebrow">{number} · {title}</span>
    <h1>{title}</h1>
    <p class="lesson-goal"><b>本节目标：</b>回归测试用的最小课件。</p>
  </header>

  <h2>正文</h2>
  <p>这一节只是让检查有东西可看。</p>

  {quiz}
{extra}
  <nav class="lesson-nav" aria-label="上一课 / 下一课">
{nav}  </nav>

  <footer class="lesson-footer">
    StudyMate · {number} {title} · 回归测试
  </footer>

</article>

<script src="../../../assets/sayo/sayo.js"></script>
<script src="../assets/quiz.js" defer></script>
<script src="../assets/lesson-toc.js" defer></script>
<script>LearnTheme.wire(document.getElementById('lesson-theme-checkbox'));</script>
</body>
</html>
'''


def write_subject(root, nodes=None, name=None):
    """在 root 下造一个科目目录（按真实布局 `<root>/.learning/subjects/<slug>/`），返回科目路径。

    布局与真实工作区一致**是必须的**：课件的共享层引用写作 `../../../assets/…`（解析到
    `<root>/.learning/assets/`），科目组件写作 `../assets/…`。检查项 10 会核对这些引用真实可达，
    所以共享层、科目组件与科目主页都放一份占位文件——真实工作区里它们由 `gen_home.py` 与建课流程
    产出，占位内容检查不解码。

    `name` 给了才写 subject.yaml——渲染器读它的 `name` 填顶栏与 `<title>`（缺文件时退回目录名）。
    """
    nodes = nodes or DEFAULT_NODES
    workspace = Path(root) / '.learning'
    subject = workspace / 'subjects' / 'subject'
    (subject / 'lessons').mkdir(parents=True, exist_ok=True)
    for relative in SHARED_STUBS:
        stub = workspace / 'assets' / relative
        stub.parent.mkdir(parents=True, exist_ok=True)
        stub.write_text('/* 测试占位：真实工作区里由 gen_home.py 铺共享层 */\n', encoding='utf-8')
    for relative in COMPONENT_STUBS:
        stub = subject / 'assets' / relative
        stub.parent.mkdir(parents=True, exist_ok=True)
        stub.write_text('/* 测试占位：真实科目里是 templates/assets/ 的副本 */\n', encoding='utf-8')
    (subject / 'index.html').write_text('<!DOCTYPE html><title>科目主页占位</title>\n', encoding='utf-8')
    lines = ['nodes:']
    for node_id, kind, title in nodes:
        lines += [f'- id: {node_id}', f'  title: {title}', f'  kind: {kind}']
    (subject / 'curriculum.yaml').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    if name:
        (subject / 'subject.yaml').write_text(
            f'name: "{name}"\nslug: "test-subject"\nstatus: 进行中\n', encoding='utf-8')
    return str(subject)


def clear_lessons(subject):
    """清掉 lessons/ 下所有课件——每个场景都从干净的一份重建。"""
    lessons = os.path.join(subject, 'lessons')
    for name in os.listdir(lessons):
        os.remove(os.path.join(lessons, name))


def auto_nav(subject, number):
    """按大纲顺序给第 number 份课件算出上/下节课指针（含「下节课还没产出」的情况）。"""
    nodes = read_nodes(subject)
    index = number - 1
    links = []
    if index >= 1:
        prev_id, _, prev_title = nodes[index - 1]
        links.append(('prev', f'{index:04d}-{prev_id}.html', prev_title))
    if index + 1 < len(nodes):
        next_id, _, next_title = nodes[index + 1]
        links.append(('next', f'{index + 2:04d}-{next_id}.html', next_title))
    return links


def read_nodes(subject):
    """读回 curriculum.yaml 的 nodes（只要 id/kind/title，手写解析够用）。"""
    nodes = []
    with open(os.path.join(subject, 'curriculum.yaml'), encoding='utf-8') as handle:
        current = {}
        for line in handle:
            line = line.strip()
            if line.startswith('- id:'):
                current = {'id': line.split(':', 1)[1].strip()}
                nodes.append(current)
            elif line.startswith('title:') and current is not None:
                current['title'] = line.split(':', 1)[1].strip()
            elif line.startswith('kind:'):
                current['kind'] = line.split(':', 1)[1].strip()
    return [(n['id'], n.get('kind', '概念'), n.get('title', n['id'])) for n in nodes]


def nav_html(links):
    """把 [(方向, href, 标题)] 拼成 .lesson-nav 的内容。"""
    label = {'prev': '上节课', 'next': '下节课'}
    out = ''
    for direction, href, title in links:
        out += (f'    <a class="lesson-nav__link lesson-nav__link--{direction}" href="{href}">\n'
                f'      <span class="lesson-nav__dir">{label[direction]}</span>\n'
                f'      <span class="lesson-nav__title">{title}</span>\n'
                f'    </a>\n')
    return out


def write_lesson(subject, number, node_id, quiz=None, nav='auto', title=None, extra=''):
    """写一份课件，返回路径。

    number  —— 编号（1 起，等于节点在 nodes 里的位次）
    quiz    —— 题目块的原始 HTML；不给就用一个合法题目块
    nav     —— 'auto'（按大纲自动填对）或 [(方向, href, 标题)]（原样写，用来注入偏差）
    extra   —— 插在题目块与导航之间的原始 HTML（配图、表格等，测别的检查项用）
    """
    if nav == 'auto':
        nav = auto_nav(subject, number)
    titles = {nid: node_title for nid, _, node_title in read_nodes(subject)}
    path = os.path.join(subject, 'lessons', f'{number:04d}-{node_id}.html')
    html = LESSON_TEMPLATE.format(
        number=f'{number:04d}',
        title=title or titles.get(node_id, node_id),
        quiz=quiz if quiz is not None else VALID_QUIZ,
        extra=extra,
        nav=nav_html(nav),
    )
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(html)
    return path


# 内容格式的最小正文：front matter（title/goal 必填）+ 一个小节 + 一段话。
# 段落里不带 `` ` `` / `**` / `[` 这些行内标记，用例要什么自己往 body 里写。
CONTENT_TEMPLATE = '''---
title: {title}
goal: {goal}
---

## 正文

这一节只是让渲染器有东西可看。
'''


def write_content(subject, number, node_id, body=None, title=None, goal='能把这一节的目标说清楚。'):
    """写一份内容格式的正文（`lessons/<NNNN>-<节点id>.md`），返回路径。

    number / node_id —— 编号与节点 id（编号 = 节点在 curriculum.yaml 里的位次）
    body             —— `## 正文` 之后的块；不给就用一句话的最小正文
    title / goal     —— front matter 的两个必填字段；title 不给就取大纲里的节点标题
    """
    titles = {nid: node_title for nid, _, node_title in read_nodes(subject)}
    text = CONTENT_TEMPLATE.format(title=title or titles.get(node_id, node_id), goal=goal)
    if body is not None:
        text = text.split('## 正文', 1)[0] + body.lstrip('\n') + (
            '' if body.endswith('\n') else '\n')
    path = os.path.join(subject, 'lessons', f'{number:04d}-{node_id}.md')
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)
    return path


def write_quiz(subject, number, node_id, mapping):
    """写按锚点组织的题库（`lessons/<NNNN>-<节点id>.quiz.json`），返回路径。"""
    path = os.path.join(subject, 'lessons', f'{number:04d}-{node_id}.quiz.json')
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(mapping, handle, ensure_ascii=False, indent=2)
    return path


def run_render(subject, node_id, *args):
    """跑渲染器（`scripts/render_lesson.py`），返回 (exit_code, 输出)。"""
    proc = subprocess.run([sys.executable, str(RENDER), str(subject), node_id, *args],
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def lesson_html(subject, number, node_id):
    """渲染器写出的课件路径（`lessons/<NNNN>-<节点id>.html`）。"""
    return os.path.join(subject, 'lessons', f'{number:04d}-{node_id}.html')


def lesson_md(subject, number, node_id):
    """内容文件路径（`lessons/<NNNN>-<节点id>.md`）。"""
    return os.path.join(subject, 'lessons', f'{number:04d}-{node_id}.md')


def run_gate(path, subject, node):
    """跑检查，返回 (exit_code, 输出)。"""
    proc = subprocess.run([sys.executable, str(GATE), str(path), '--subject', str(subject), '--node', node],
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def run_pool(subject):
    """跑图片库校验器（`scripts/check_pool.py`），返回 (exit_code, 输出)。"""
    proc = subprocess.run([sys.executable, str(POOL_CHECK), str(subject)],
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def check(label, ok, detail=''):
    """一行断言输出，返回是否通过。"""
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f'  — {detail}' if detail and not ok else ''))
    if not ok and detail:
        print('      ' + detail.strip().replace('\n', '\n      '))
    return ok
