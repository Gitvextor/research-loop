#!/usr/bin/env python3
"""题面写法：代码围栏、Markdown 标记、以及裸 `>` 的取值陷阱。

`quiz.js` 把 ``` 围栏渲染成真代码块（<pre><code> + 缩进 + 自动上色），见它顶部契约。
检查只管一件结构事：**围栏成对**——不成对的话后半段会被整段渲染成代码块，学生看到的
题面就变了。渲染本身由 `quiz_dom_test.js`（结构）与 `browser/quiz_code_test.mjs`
（真实 Chrome 里的上色与缩进）钉。

用法：python3 scripts/tests/test_quiz_code.py
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures  # noqa: E402

CODE = 'while (i <= 100) {\n    ++cnt;\n}'


def block(q, why='w'):
    item = {'q': q, 'opts': ['A', 'B'], 'ans': 0, 'why': why}
    return '<div class="quiz" data-quiz=\'' + json.dumps([item], ensure_ascii=False) + '\'></div>'


def open_block(answer):
    return ('<div class="quiz" data-quiz=\''
            + json.dumps([{'q': '题面', 'answer': answer, 'criteria': '写出即算过'}], ensure_ascii=False)
            + '\'></div>')


# (说明, 题目块, 该不该拦, 拦截文案要含, 必须出现的提示, 不许出现的提示)
CASES = [
    ('成对围栏（放行）', block('看这段：\n\n```cpp\n' + CODE + '\n```\n\n输出什么？'), False, None, None, None),
    ('围栏不写语言（放行）', block('看这段：\n\n```\n' + CODE + '\n```'), False, None, None, None),
    ('围栏没闭合（拦）', block('看这段：\n\n```cpp\n' + CODE), True, '围栏没闭合', None, None),
    ('answer 里没闭合（拦）', open_block('参考答案：\n\n```cpp\n' + CODE), True, '围栏没闭合', None, None),
    ('行内单个反引号（放行 + 提示）', block('shell 里 `pwd` 是做什么的？'), False, None, '纯文本', None),
    ('无围栏的多行纯文本（放行）', block('n 是 5。\n循环体跑几次？'), False, None, None, None),
    # 字段是纯文本：Markdown 标记不会渲染，检查提示（不拦——数学写法也可能长这样）
    ('Markdown 加粗（放行 + 提示）', block('这段 **一定要** 看懂：\n为什么？'), False, None, '纯文本', None),
    ('Markdown 标题（放行 + 提示）', block('# 读数\n这段在做什么？'), False, None, '纯文本', None),
    ('围栏里的 ** 不提示（指针 int **p 合法）',
     block('看这段：\n\n```cpp\nint **p = &q;\n```\n\np 是什么类型？'), False, None, None, '纯文本'),
    ('作者的 1. 枚举不提示', block('1. 先读题。\n2. 再动手。\n为什么按这个顺序？'), False, None, None, '纯文本'),
    # 裸 > 会切断检查的取值正则：页面能渲染，但检查认不出题目块（要写 &gt;）
    ('裸 > 的题目（拦 + 说清原因）', block('x > 0 时怎样？'), True, '值取不出来', None, None),
    ('写成 &gt;（放行）', block('x &gt; 0 时怎样？'), False, None, None, None),
]


def main():
    tmp = tempfile.mkdtemp(prefix='smtest-code-')
    # 单节点科目：这一课没有上下节课，断言只反映围栏这一处
    subject = fixtures.write_subject(tmp, nodes=[('solo-node', '概念', '唯一节点')])
    failures = 0
    for label, quiz, want_fail, must, want_note, no_note in CASES:
        fixtures.clear_lessons(subject)
        path = fixtures.write_lesson(subject, 1, 'solo-node', quiz='  ' + quiz + '\n', nav=[])
        code, out = fixtures.run_gate(path, subject, 'solo-node')
        ok = (code != 0) == want_fail
        ok = ok and (not must or must in out)
        ok = ok and (not want_note or want_note in out)
        ok = ok and (not no_note or no_note not in out)
        failures += not ok
        fixtures.check(label, ok, out if not ok else f'检查={"FAIL" if code else "OK"}')
    total = len(CASES)
    print(f'\n{total - failures}/{total} 通过')
    shutil.rmtree(tmp, ignore_errors=True)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
