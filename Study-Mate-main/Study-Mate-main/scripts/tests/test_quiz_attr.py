#!/usr/bin/env python3
"""`data-quiz` 属性值转义的回归测试（9 例矩阵，检查口径）。

每个用例是「能过检查的最小课件 + 一个题目块」，**只改属性怎么写**；断言检查放行/拦截，
以及拦截文案有没有指到正确改法。

背景（2026-09-18）：契约一度把 `" → &quot;` 写成正式规则，而单引号包裹时 `&quot;` 解码成
裸 `"`、提前闭合 JSON 字符串。浏览器实测（headless Chrome，同一批用例）：

    写法                      浏览器                          检查
    ' 包裹 + \\"              正常渲染 printf("x")            放行
    ' 包裹 + &quot; / &#34;      题目块显示「解析失败」            拦（文案给改法）
    " 包裹 + \\&quot;           正常                             放行
    " 包裹 + &quot;             「解析失败」                     拦
    " 包裹 + 裸 \\"           「解析失败」（属性被截断）        拦（截断那条）
    ' 包裹 + &#39;             正常渲染 printf('x')             放行

用法：python3 scripts/tests/test_quiz_attr.py
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures  # noqa: E402


def single_attr(inner):
    """单引号包裹（本项目模板的写法）：JSON 的结构引号照常写裸 `"`。"""
    q = 'printf(' + inner + 'x' + inner + ') 是什么意思？'
    return ("<div class=\"quiz\" data-quiz='[{\"q\":\"" + q
            + "\",\"opts\":[\"A\",\"B\"],\"ans\":0,\"why\":\"w\"}]'></div>")


def double_attr(inner):
    """双引号包裹：连 JSON 的结构引号也必须写实体，否则属性当场被 `"` 截断。"""
    q = 'printf(' + inner + 'x' + inner + ') 是什么意思？'
    return ('<div class="quiz" data-quiz="[{&quot;q&quot;:&quot;' + q
            + '&quot;,&quot;opts&quot;:[&quot;A&quot;,&quot;B&quot;],&quot;ans&quot;:0,'
              '&quot;why&quot;:&quot;w&quot;}]"></div>')


# 用例 → (题目块, 该不该拦, 拦截文案里必须出现什么)
CASES = [
    ('A 单引号 + \\"（正确写法）', single_attr('\\"'), False, None),
    ('B 单引号 + &quot;', single_attr('&quot;'), True, '实体引号'),
    ('C 单引号 + &#34;', single_attr('&#34;'), True, '实体引号'),
    ('D 双引号 + \\&quot;（正确写法）', double_attr('\\&quot;'), False, None),
    ('E 双引号 + &quot;', double_attr('&quot;'), True, None),
    ('F 双引号 + 裸 \\"（属性被浏览器截断）', double_attr('\\"'), True, '截断'),
    ('G 单引号 + &#39;（正确写法）', single_attr('&#39;'), False, None),
    ('H 单引号 + 用 &quot; 顶替引号', '<div class="quiz" data-quiz=\'[{"q":"&quot;",'
                                     '"opts":["A","B"],"ans":0,"why":"w"}]\'></div>', True, '实体引号'),
    ('I 单引号 + &quot; 吃掉收尾引号', '<div class="quiz" data-quiz=\'[{"q":"a&quot;",'
                                       '"opts":["A","B"],"ans":0,"why":"w"}]\'></div>', True, '实体引号'),
]


def main():
    tmp = tempfile.mkdtemp(prefix='smtest-attr-')
    # 只放一个节点：这一课没有上/下节课，指针不参与，断言只反映题目块的属性写法
    subject = fixtures.write_subject(tmp, nodes=[('solo-node', '概念', '唯一节点')])
    failures = 0
    for label, block, want_fail, must in CASES:
        fixtures.clear_lessons(subject)
        path = fixtures.write_lesson(subject, 1, 'solo-node',
                                     quiz='  ' + block + '\n', nav=[])
        code, out = fixtures.run_gate(path, subject, 'solo-node')
        ok = (code != 0) == want_fail and (not must or must in out)
        failures += not ok
        verdict = 'FAIL' if code else 'OK'
        note = f'检查={verdict}' + (f'，文案含「{must}」' if must and must in out else '')
        fixtures.check(label, ok, note if ok else note + '\n' + out)
    total = len(CASES)
    print(f'\n{total - failures}/{total} 通过')
    shutil.rmtree(tmp, ignore_errors=True)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
