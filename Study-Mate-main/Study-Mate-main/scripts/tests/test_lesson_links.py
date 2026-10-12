#!/usr/bin/env python3
r"""本地引用可达：检查项 10 的判定（页面里的 href/src 必须落到真实文件）。

为什么单独有这道：`gen_home.py` 的断链自检只管它自己写出的主页（根主页 + 科目主页），
课件页不在它的范围内。检查项 2/3 只核对「引用写没写齐」，不管目标在不在；检查项 9 只管
`<img>`。于是页面可以**同时"通过全部检查"和"点开是白板 / 404"**——示例工作区里真发生过两次：
科目 `assets/` 缺了 `quiz.js` / `style.css`（页面没样式、题点不动），以及正文里那条 lab 链接
指向不存在的 README。

判定口径：
  · 本地目标不存在 → 阻断
  · 外链、锚点、`mailto:`、协议相对 `//` → 跳过
  · HTML 注释里的路径 → 跳过（模板里带一堆给生成器看的示例链接）
  · 上/下节课指针 → 跳过（落空是设计内的，检查项 8 只提示）
  · `?查询串` 与 `#片段` 先剥掉再解析；`%xx` 先解码

另外三条钉的是**另外两类**：
  · 条件引用（检查项 11）：页面里有 `.math-inline` / `.math-block` 时，壳里必须有离线 KaTeX 三件
    （`katex/katex.min.css`、`katex/katex.min.js`、`lesson-math.js`）；没有数学式的页面不要求它们。
  · 生成产物（检查项 10 的例外）：壳里那条「返回课程」回链指向 `index.html`，它是 `gen_home.py`
    的产物——还没生成时只提示，**不阻断**（作者产不出这个文件；否则每门新科目在跑生成器之前
    都过不了检查）。
  · 题库里的公式（检查项 11）：题目正文由 quiz.js 运行时插入，静态看不到 `.math-inline`，
    所以 `data-quiz` 属性里出现 `$…$` 也算「页面有数学式」。
  · 方程组的大括号（质量线，只提示）：`aligned` 里 ≥2 行等式却没被 `\left\{ … \right.` 包住
    ——KaTeX 不会自己加，少了读者会把一列等式当成几个独立结论。

用法：python3 scripts/tests/test_lesson_links.py
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures  # noqa: E402

EXISTING = '  <p>速查页见 <a href="../reference/cheatsheet.html">这份速查</a>。</p>\n'
MISSING_LAB = '  <p>任务见 <a href="../lab/0001-ghost/README.md">lab 说明</a>。</p>\n'
EXTERNAL = ('  <p><a href="https://example.com/x">外链</a> '
            '<a href="#sec">锚点</a> '
            '<a href="mailto:someone@example.com">邮件</a> '
            '<a href="//cdn.example.com/lib.js">协议相对</a></p>\n')
COMMENTED = '  <!-- <a href="../lab/ghost/README.md">模板里的示例链接</a> -->\n'
WITH_QUERY = '  <p><a href="../reference/cheatsheet.html?v=2#top">带查询串的速查</a></p>\n'

# (说明, extra 里的 HTML, 要不要先删掉某个组件文件, 该不该拦, 输出里要含的片段)
CASES = [
    ('引用齐全（放行）', EXISTING, None, False, None),
    ('正文链接指向不存在的文件（拦）', MISSING_LAB, None, True, '不存在的本地文件'),
    ('正文链接指向存在的文件（放行）', EXISTING, None, False, None),
    ('外链/锚点/mailto/协议相对（放行）', EXTERNAL, None, False, None),
    ('注释里的路径（放行）', COMMENTED, None, False, None),
    ('带 ?查询串 与 #片段（放行）', WITH_QUERY, None, False, None),
    ('科目组件 quiz.js 不在（拦）', '', 'quiz.js', True, 'quiz.js'),
    ('科目组件 lesson-toc.js 不在（拦）', '', 'lesson-toc.js', True, 'lesson-toc.js'),
    ('共享层 learn-theme.css 不在（拦）', '', 'shared:learn-theme.css', True, 'learn-theme.css'),
]


def prepare_reference(subject):
    """造一份真实存在的速查页，给「链接指向存在的文件」这条用。"""
    reference = os.path.join(subject, 'reference')
    os.makedirs(reference, exist_ok=True)
    with open(os.path.join(reference, 'cheatsheet.html'), 'w', encoding='utf-8') as handle:
        handle.write('<!DOCTYPE html><title>速查</title>\n')


def drop_component(subject, which):
    """删掉一个组件文件；`shared:` 前缀表示共享层（`<root>/.learning/assets/`）。"""
    if which.startswith('shared:'):
        learning = os.path.dirname(os.path.dirname(subject))      # <root>/.learning
        target = os.path.join(learning, 'assets', which.split(':', 1)[1])
    else:
        target = os.path.join(subject, 'assets', which)
    os.remove(target)


def main():
    tmp = tempfile.mkdtemp(prefix='smtest-links-')
    subject = fixtures.write_subject(tmp)
    prepare_reference(subject)
    failures = 0
    for label, extra, drop, want_fail, must in CASES:
        fixtures.clear_lessons(subject)
        # 组件每次都重建：上一个用例可能删过它们
        fixtures.write_subject(tmp)
        if drop:
            drop_component(subject, drop)
        path = fixtures.write_lesson(subject, 1, 'overview-map', extra=extra)
        code, out = fixtures.run_gate(path, subject, 'overview-map')
        ok = (code != 0) == want_fail and (not must or must in out)
        failures += not ok
        fixtures.check(label, ok, out if not ok else f'检查={"FAIL" if code else "OK"}')

    # 下节课指针落空：属设计内，只提示不阻断
    fixtures.write_subject(tmp)
    fixtures.clear_lessons(subject)
    path = fixtures.write_lesson(subject, 1, 'overview-map')
    code, out = fixtures.run_gate(path, subject, 'overview-map')
    ok = code == 0 and '悬空指针' in out
    failures += not ok
    fixtures.check('下节课还没产出（放行，只有提示）', ok, out)

    # 数学式：渲染器会自动注入 KaTeX 三件；把它们删掉就必须报（检查项 11）
    subject2 = fixtures.write_subject(tmp)
    fixtures.write_content(subject2, 1, 'overview-map', body='## 试\n\n行内 $Ax = b$ 一段。\n')
    fixtures.run_render(subject2, 'overview-map')
    page = fixtures.lesson_html(subject2, 1, 'overview-map')
    code_math, out_math = fixtures.run_gate(page, subject2, 'overview-map')
    ok = '页面里有数学式' not in out_math
    failures += not ok
    fixtures.check('有公式 + 渲染器注入的 KaTeX 引用（数学这一项不报）', ok, out_math)

    import re as _re
    with open(page, encoding='utf-8') as handle:
        stripped = _re.sub(r'.*(katex\.min\.css|katex\.min\.js|lesson-math\.js).*\n', '', handle.read())
    with open(page, 'w', encoding='utf-8') as handle:
        handle.write(stripped)
    code_math2, out_math2 = fixtures.run_gate(page, subject2, 'overview-map')
    ok2 = '页面里有数学式' in out_math2
    failures += not ok2
    fixtures.check('有公式但引用被删（拦下，指到缺哪一件）', ok2, out_math2)

    # 科目主页（gen_home 的产物）还没生成：只提示，不阻断
    subject3 = fixtures.write_subject(tmp)
    fixtures.clear_lessons(subject3)
    os.remove(os.path.join(subject3, 'index.html'))
    path3 = fixtures.write_lesson(subject3, 1, 'overview-map')
    code_index, out_index = fixtures.run_gate(path3, subject3, 'overview-map')
    ok3 = code_index == 0 and '科目主页还没生成' in out_index
    failures += not ok3
    fixtures.check('科目主页还没生成（放行，只有提示）', ok3, out_index)

    # 题库里的公式也算「页面有数学式」：题目正文由 quiz.js 运行时插入，静态看不到 .math-inline
    subject4 = fixtures.write_subject(tmp)
    fixtures.clear_lessons(subject4)
    quiz_with_math = ('<div class="quiz" data-quiz=\'[{"q":"矩阵 $A$ 的秩？",'
                      '"opts":["$1$","$2$"],"ans":1,"why":"看主元。"}]\'></div>')
    path4 = fixtures.write_lesson(subject4, 1, 'overview-map', quiz=quiz_with_math)
    code_quiz, out_quiz = fixtures.run_gate(path4, subject4, 'overview-map')
    ok4 = code_quiz != 0 and '页面里有数学式' in out_quiz
    failures += not ok4
    fixtures.check('公式只在题库里也算数学式（漏引用就拦）', ok4, out_quiz)

    # 方程组少了 \left\{ … \right.：只提示、不阻断（质量线，规格见课件内容格式第 3 节）
    subject5 = fixtures.write_subject(tmp)
    fixtures.write_content(subject5, 1, 'overview-map', body='## 试\n\n$$\n\\begin{aligned}\n'
                                                     'x + y &= 1 \\\\\n'  'x - y &= 0\n\\end{aligned}\n$$\n'
                                                     '\n::: quiz 理解 锚点：本节校验\n:::\n')
    fixtures.write_quiz(subject5, 1, 'overview-map',
                        {'本节校验': [{'q': '题干', 'opts': ['A', 'B'], 'ans': 0, 'why': '解释'}]})
    fixtures.run_render(subject5, 'overview-map')
    page5 = fixtures.lesson_html(subject5, 1, 'overview-map')
    code_brace, out_brace = fixtures.run_gate(page5, subject5, 'overview-map')
    ok5 = code_brace == 0 and '大括号' in out_brace
    failures += not ok5
    fixtures.check('方程组缺大括号（提示，不阻断）', ok5, out_brace)

    subject6 = fixtures.write_subject(tmp)
    fixtures.write_content(subject6, 1, 'overview-map', body='## 试\n\n$$\n\\left\\{\\begin{aligned}\n'
                                                     'x + y &= 1 \\\\\n'  'x - y &= 0\n\\end{aligned}\\right.\n$$\n'
                                                     '\n::: quiz 理解 锚点：本节校验\n:::\n')
    fixtures.write_quiz(subject6, 1, 'overview-map',
                        {'本节校验': [{'q': '题干', 'opts': ['A', 'B'], 'ans': 0, 'why': '解释'}]})
    fixtures.run_render(subject6, 'overview-map')
    code_ok, out_ok = fixtures.run_gate(fixtures.lesson_html(subject6, 1, 'overview-map'), subject6, 'overview-map')
    # 只看 WARN/FAIL 行：解释器警告之类会把源码那行回显出来（那行本来就含「大括号」三个字）
    warning_lines = [l for l in out_ok.splitlines() if l.startswith(('WARN', 'FAIL'))]
    ok6 = code_ok == 0 and not any('大括号' in l for l in warning_lines)
    failures += not ok6
    fixtures.check('方程组带了大括号（不再提示）', ok6, out_ok)

    total = len(CASES) + 7
    print(f'\n{total - failures}/{total} 通过')
    shutil.rmtree(tmp, ignore_errors=True)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
