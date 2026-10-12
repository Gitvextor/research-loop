#!/usr/bin/env python3
"""课件渲染器 `scripts/render_lesson.py` 的回归测试，26 个场景。

渲染器是**唯一**的课件 HTML 产出者：讲解角色只写内容文件（`.md`），出题角色只写按锚点组织的
题库（`.quiz.json`），HTML 由渲染器从 `templates/lesson.html` 的占位符壳 + `curriculum.yaml`
（序号/邻居/标题）一次渲染出来。所以这套测试钉的不是"渲染器没报错"，而是**渲染产物里的真实片段**：

  壳与接线（共享层 4 引用 + 科目组件 2 引用 + 主题开关 + 三个 script）· `&<>` 转义与代码原文
  逐字 · 表格/列表/围栏/行内标记 · 题目按锚点合入且 `data-quiz` 属性值转义正确（单引号包裹、
  值里 `&#39;` / `&lt;` / `&gt;`）· 锚点缺题必须 `empty_reason`（且**只准**出现在 `::: quiz`——
  写进 `::: practice`／`::: tip` 会被当段落印成 `<p>empty_reason: …</p>`，按错拦下）· 配图存在性与题注来源 ·
  front matter 的 `title` 与 `curriculum.yaml` 该节点的 `title` 逐字一致（不一致按行号报错、不写盘）· 导航
  与序号按大纲算 · 未知指令与块语法带行号报错 · `--check` 不写盘 · 渲染产物过检查 ·
  锚点**双向**对账（题库缺题要 `empty_reason`；题库里多出来的孤儿键、同一个锚点被两个题目位置引用，
  都带行号报错）· 用法错误退 2 与坏题库三种形态（非 JSON／非对象／值是空数组）·
  `kind: 实验` 的说明页没有题库也能渲染并过检查（R12）· 名单里每个名字都必须被形状正则捕获
  （连字符名 `<syo-editor>` 捕不到——它只能做成 `:::` 指令，不能靠加名单）·
  **一级标题与段落中间的 HTML 都不许静默通过**（前者会连内容一起消失、后者会当字面量显示；
  真标签白名单与 code span 判定都只有一份，落单反引号遮不住标签、`n<m` 也不会被误杀；
  白名单是**完整**的 HTML 元素表 + SVG 名，`iframe`/`video`/`form`/`main`/`button`/`canvas`
  与 11 个 SVG 名字一个都不能漏，且「代码 = 格式文档 = 测试里写死的集合」三份逐字一致；
  `alt:` 与 `caption:` 同一条检查、`::: svg` 的收尾按保留换行的文本判）。

每个场景自造一个临时科目（`fixtures.write_subject` + `write_content` + `write_quiz`），
**不读也不写任何工作区**。用法：python3 scripts/tests/test_render_lesson.py
"""
import html as html_mod
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fixtures  # noqa: E402
import render_lesson  # noqa: E402  只用来直接验 render_block 的兜底（其余用例都起真子进程）

TMP = tempfile.mkdtemp(prefix='smtest-render-')
_SUBJECT_SEQ = [0]

# 图片库索引的表头与一行数据（列序见 check_pool.py：文件/主题标签/说明/来源 URL/许可/尺寸/抓取日期）
POOL_HEADER = '| 文件 | 主题标签 | 一句话说明 | 来源 URL | 许可 | 尺寸 | 抓取日期 |'
POOL_SEP = '| --- | --- | --- | --- | --- | --- | --- |'
POOL_IMAGE = '数组-内存布局-连续存储-cppreference-01.png'
POOL_ROW = (f'| {POOL_IMAGE} | 数组 · 内存布局 | 连续存储的内存布局 | '
            'https://en.cppreference.com/w/cpp/language/array | CC BY-SA 4.0 | 640×360 | 2026-09-19 |')

# 一道题面里同时有 `printf("x")`、`a > 0` 与单引号（';'）：三种转义一次钉住
QUIZ_BOUNDARY = [{
    'q': '这段代码里 printf("x") 在 a > 0 时执行吗？\n\n```cpp\nif (a > 0) printf("x");\n```\n',
    'opts': ['执行', '不执行'],
    'ans': 0,
    'why': 'a > 0 成立才执行；编译器对 \';\' 的报错属于语法错误那一类。',
}]

CASES = []


def case(label):
    """收集一个场景（函数收到一个 Asserts，把失败记进去）。"""
    def wrap(fn):
        CASES.append((label, fn))
        return fn
    return wrap


def new_subject(nodes=None, name='测试科目'):
    """每个场景一个干净的临时科目（互不干扰）。"""
    _SUBJECT_SEQ[0] += 1
    root = os.path.join(TMP, f'case{_SUBJECT_SEQ[0]}')
    os.makedirs(root, exist_ok=True)
    return fixtures.write_subject(root, nodes=nodes, name=name)


def write_pool(subject, files=(POOL_IMAGE,)):
    """造一个图片库：`assets/img/pool/` 下的文件 + 兄弟索引 pool.md。"""
    pool = os.path.join(subject, 'assets', 'img', 'pool')
    os.makedirs(pool, exist_ok=True)
    for name in files:
        with open(os.path.join(pool, name), 'wb') as handle:
            handle.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 24)
    with open(os.path.join(subject, 'assets', 'img', 'pool.md'), 'w', encoding='utf-8') as handle:
        handle.write(f'{POOL_HEADER}\n{POOL_SEP}\n{POOL_ROW}\n')


class Asserts:
    """断言收集器：一个场景里所有断言都跑完，失败原因一起报，不半路中断。"""

    def __init__(self):
        self.failures = []

    def ok(self, label, passed, detail=''):
        if not passed:
            self.failures.append(label + (f'（{detail}）' if detail else ''))

    def has(self, text, *needles, label=None):
        """产物里必须逐字出现这些片段。"""
        missing = [needle for needle in needles if needle not in text]
        self.ok(label or f'含 {needles[0][:40]!r}', not missing,
                '缺 ' + '、'.join(repr(item) for item in missing))

    def hasnt(self, text, *needles, label=None):
        """产物里不许出现这些片段（例如首课不该有 --prev）。"""
        hit = [needle for needle in needles if needle in text]
        self.ok(label or f'不含 {needles[0][:40]!r}', not hit,
                '却出现 ' + '、'.join(repr(item) for item in hit))

    def equal(self, label, got, want):
        self.ok(label, got == want, f'实际 {got!r}，应为 {want!r}')


def render(subject, number, node_id, *args):
    """跑渲染器，返回 (exit_code, 输出, 产物文本（没写盘就是空串）, 产物路径)。"""
    code, out = fixtures.run_render(subject, node_id, *args)
    path = fixtures.lesson_html(subject, number, node_id)
    text = open(path, encoding='utf-8').read() if os.path.exists(path) else ''
    return code, out, text, path


def run_raw(*args):
    """直接跑渲染器的命令行入口，返回 (exit_code, stdout+stderr)——用法错误只能这样测。"""
    proc = subprocess.run([sys.executable, str(fixtures.RENDER), *args],
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def line_of(md_path, needle):
    """needle 在内容文件里的行号（1 起）——报错信息必须指到这里。"""
    with open(md_path, encoding='utf-8') as handle:
        for index, line in enumerate(handle, 1):
            if line.rstrip('\n') == needle:
                return index
    raise AssertionError(f'{md_path} 里找不到 {needle!r}')


def quiz_attr(text):
    """取第一个 .quiz 块的 data-quiz 属性值（按书写原样，不解码实体）。"""
    match = re.search(r"<div class=\"quiz\" data-quiz='(.*?)'></div>", text, re.S)
    return match.group(1) if match else None


# ══════════════════════════════════════════════════════════════════
# ① 壳与接线：共享层 4 引用、科目组件 2 引用、主题开关、三个 script、抬头与页脚
# ══════════════════════════════════════════════════════════════════

@case('壳与接线齐全（共享层/科目组件/主题开关/三个 script/抬头页脚）')
def _(a):
    subject = new_subject()
    goal = '能把 `main.cpp` 编译成可执行文件，并看到程序打印的那一行。'
    fixtures.write_content(subject, 2, 'first-program', body='''## 一笔取款走过几条路

程序拿金额去比两个数，比完决定怎么处理。

::: quiz 理解 锚点：本节校验
:::
''', goal=goal)
    fixtures.write_quiz(subject, 2, 'first-program', {'本节校验': QUIZ_BOUNDARY})
    code, out, text, path = render(subject, 2, 'first-program')
    a.equal('渲染退出码 0', code, 0)
    a.has(text,
          '<!DOCTYPE html>',
          '<html lang="zh-CN" data-theme="dark">',
          '<title>编译并跑通 · 测试科目</title>',
          '<link rel="stylesheet" href="../../../assets/sayo/sayo.css">',
          '<link rel="stylesheet" href="../../../assets/learn-theme.css">',
          '<link rel="stylesheet" href="../assets/style.css">',
          '<script src="../../../assets/learn-theme.js"></script>',
          '<script>LearnTheme.apply();</script>',
          '<script src="../../../assets/sayo/sayo.js"></script>',
          '<script src="../assets/quiz.js" defer></script>',
          '<script src="../assets/lesson-toc.js" defer></script>',
          '<input type="checkbox" id="lesson-theme-checkbox" checked>',
          'LearnTheme.wire(document.getElementById(\'lesson-theme-checkbox\'));',
          '<span>测试科目</span>',
          '<span class="lesson-bar__no">0002</span>',
          '<span class="lesson-header__eyebrow">0002 · 编译并跑通</span>',
          '<h1>编译并跑通</h1>',
          '<p class="lesson-goal"><b>本节目标：</b>能把 <code>main.cpp</code> 编译成可执行文件，'
          '并看到程序打印的那一行。</p>',
          '<div class="lesson-ask">',
          '把看不懂的段落（或报错）原样复制回会话',
          'StudyMate · 0002 编译并跑通 · 本地学习工作区')
    a.has(text, '<h2>一笔取款走过几条路</h2>', '<p>程序拿金额去比两个数，比完决定怎么处理。</p>')
    a.ok('交付页面从 <!DOCTYPE html> 起（模板说明注释不随页面出厂）',
         text.startswith('<!DOCTYPE html>\n<html'), repr(text[:60]))
    a.hasnt(text, '课件骨架', '检查会拦', '不要手工拷贝', '写给维护者', '渲染器只从',
            label='产物里没有写给维护者的说明注释')


# ══════════════════════════════════════════════════════════════════
# ①′ 这节课叫什么只有一个答案：front matter 的 title = 大纲节点的 title（逐字）
# ══════════════════════════════════════════════════════════════════

@case('title 一致性：与 curriculum.yaml 不一致时带行号报错、不写盘；逐字一致才放行')
def _(a):
    subject = new_subject()
    bad_title = '编译并跑通（改坏了）'
    md = fixtures.write_content(subject, 2, 'first-program', title=bad_title)
    code, out, text, path = render(subject, 2, 'first-program')
    a.ok('不一致时非零退出', code != 0, f'exit={code}')
    a.has(out, f'{md}:{line_of(md, f"title: {bad_title}")}',
          label='报错指到 front matter 的 title 行（不是别的行）')
    a.has(out, f'title「{bad_title}」', 'title「编译并跑通」',
          label='报错说清两个名字各是什么')
    a.has(out, '第 1 节', label='报错指向格式文档的规则出处')
    a.ok('不一致时不写盘', not os.path.exists(path))

    # 逐字对上（fixtures 默认取大纲里的节点标题）→ 照常出厂
    fixtures.write_content(subject, 2, 'first-program')
    code2, out2, text2, path2 = render(subject, 2, 'first-program')
    a.equal('一致时放行', code2, 0)
    a.has(text2, '<title>编译并跑通 · 测试科目</title>', '<h1>编译并跑通</h1>',
          label='页面两处都用 front matter 的名字')


# ══════════════════════════════════════════════════════════════════
# ② 转义：正文与代码里的 &<>，且代码原文逐字保留
# ══════════════════════════════════════════════════════════════════

CODE_CPP = '''#include <cstdio>
#include <iostream>

int main() {
    int a = 1, b = 2;
    if (a < b && b > 0) printf("ok\\n");
    return 0;
}'''


@case('转义：正文 &<> 与代码原文逐字保留（不双重转义）')
def _(a):
    subject = new_subject()
    fixtures.write_content(subject, 1, 'overview-map', body='''## 比较与包含

比较写成 a < b && c > d 就算说清了。

```cpp
''' + CODE_CPP + '''
```

```text
原样的一段：a < b && c > d
```
''')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.equal('渲染退出码 0', code, 0)
    a.has(text,
          '<p>比较写成 a &lt; b &amp;&amp; c &gt; d 就算说清了。</p>',
          '<pre data-lang="cpp"><code>#include &lt;cstdio&gt;',
          'if (a &lt; b &amp;&amp; b &gt; 0) printf("ok\\n");',
          '<pre data-lang="text"><code>原样的一段：a &lt; b &amp;&amp; c &gt; d</code></pre>')
    a.hasnt(text, '&amp;lt;', '&amp;amp;', '&amp;gt;', label='不双重转义')

    match = re.search(r'<pre data-lang="cpp"><code>(.*?)</code></pre>', text, re.S)
    a.ok('代码块在产物里', match is not None)
    if match:
        a.equal('代码原文解码后与内容文件逐字相同', html_mod.unescape(match.group(1)), CODE_CPP)
    # 缺语言 → 不写 data-lang（不上色）
    fixtures.write_content(subject, 1, 'overview-map', body='''## 没语言标签

```
ls -la
```
''')
    code2, out2, text2, path2 = render(subject, 1, 'overview-map')
    a.equal('缺语言的围栏也渲染成功', code2, 0)
    a.has(text2, '<pre><code>ls -la</code></pre>')
    a.hasnt(text2, 'data-lang=""', label='缺语言时不写空的 data-lang')


# ══════════════════════════════════════════════════════════════════
# ③ 块与行内：标题、列表（含嵌套）、表格、行内标记
# ══════════════════════════════════════════════════════════════════

@case('块与行内：h3/列表嵌套/表格/行内 code·粗·斜·链接·上下标/段内换行')
def _(a):
    subject = new_subject()
    fixtures.write_content(subject, 1, 'overview-map', body='''## 写法总览

### 更小的标题

行内：`code`、**粗**、*斜*、[文字](https://example.com/a)、2^31^ 与 a~n~。

第二段从这里开始，
中文换行直接相接。
English words
wrap with a space.

- 项一
- 项二
  - 子项

1. 第一
2. 第二

| 题面里的说法 | 写法 |
| --- | --- |
| 不足 100 元 | `amount < 100` |
''')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.equal('渲染退出码 0', code, 0)
    a.has(text,
          '<h2>写法总览</h2>',
          '<h3>更小的标题</h3>',
          '<code>code</code>',
          '<b>粗</b>',
          '<em>斜</em>',
          '<a href="https://example.com/a">文字</a>',
          '<sup>31</sup>',
          '<sub>n</sub>',
          '<p>第二段从这里开始，中文换行直接相接。 English words wrap with a space.</p>',
          '<li>项一</li>',
          '<li>子项</li>',
          '<li>第一</li>')
    a.has(text, '<ul>', '</ul>', '<ol>', '</ol>', label='有序/无序列表都在')
    a.ok('列表嵌套（子项在最内层 ul 里）',
         re.search(r'<li>项二\s*<ul>\s*<li>子项</li>\s*</ul>\s*</li>', text) is not None,
         '产物的列表结构：' + repr(re.findall(r'<ul>.*?</ul>', text, re.S)[:1]))
    a.has(text, '<table>', '<thead>', '<th>题面里的说法</th>', '<th>写法</th>', '<tbody>',
          '<td>不足 100 元</td>', '<td><code>amount &lt; 100</code></td>')


# ══════════════════════════════════════════════════════════════════
# ④ 题目：按锚点合入 + data-quiz 属性值转义（单引号包裹）
# ══════════════════════════════════════════════════════════════════

@case('题目按锚点合入：data-quiz 单引号包裹、值里 &#39;/&lt;/&gt; 正确')
def _(a):
    subject = new_subject()
    fixtures.write_content(subject, 2, 'first-program', body='''## 边界值该算哪一档

先不编译，按规则判一次它实际走哪条路。

::: quiz 理解 锚点：校对边界
:::
''')
    fixtures.write_quiz(subject, 2, 'first-program', {'校对边界': QUIZ_BOUNDARY})
    code, out, text, path = render(subject, 2, 'first-program')
    a.equal('渲染退出码 0', code, 0)
    a.has(text, '<div class="quiz" data-quiz=\'')
    raw = quiz_attr(text)
    a.ok('能取出 data-quiz 的值', raw is not None)
    if raw is None:
        return
    a.has(raw, '&#39;;&#39;', label='题面里的单引号写成 &#39;')
    a.has(raw, '&gt; 0', label='题面里的 > 写成 &gt;')
    a.has(raw, 'printf(\\"x\\")', label='JSON 字符串里的双引号走 JSON 转义')
    a.hasnt(raw, "';'", label='值里不出现裸的单引号（浏览器会截断属性）')
    a.hasnt(raw, '&quot;', label='单引号包裹时不写实体引号（会提前闭合 JSON 字符串）')
    try:
        got = json.loads(html_mod.unescape(raw))
    except ValueError as exc:
        a.ok('解码实体后是合法 JSON', False, str(exc))
        return
    a.equal('题目内容与题库逐字一致', got, QUIZ_BOUNDARY)


# ══════════════════════════════════════════════════════════════════
# ⑤ 锚点无题：必须 empty_reason，否则带行号报错
# ══════════════════════════════════════════════════════════════════

@case('锚点无题：缺 empty_reason 报错带行号；有则跳过不报')
def _(a):
    subject = new_subject()
    # 题库是空对象：这份内容里的题目位置全靠 empty_reason 交代，没有一道题——
    # 写别的键会变成「没人引用的孤儿锚点」，那是另一条错（见 ㉑）
    fixtures.write_quiz(subject, 2, 'first-program', {})
    directive = '::: quiz 理解 锚点：不存在的锚点'
    md = fixtures.write_content(subject, 2, 'first-program', body=f'''## 数次数

数循环次数靠把取值列出来。

{directive}
:::
''')
    code, out, text, path = render(subject, 2, 'first-program')
    a.ok('缺 empty_reason 时非零退出', code != 0, f'exit={code}')
    a.has(out, f'{md}:{line_of(md, directive)}', label='报错指到内容文件的行')
    a.has(out, 'empty_reason', label='报错说清要补什么')
    a.ok('报错时没有写盘', not os.path.exists(path))

    subject2 = new_subject()
    fixtures.write_quiz(subject2, 2, 'first-program', {})
    fixtures.write_content(subject2, 2, 'first-program', body=f'''## 数次数

数循环次数靠把取值列出来。

{directive}
empty_reason: 该锚点本轮没有出题
:::
''')
    code2, out2, text2, path2 = render(subject2, 2, 'first-program')
    a.equal('写了 empty_reason 就放行', code2, 0)
    a.ok('产物写出来了', os.path.exists(path2))
    a.hasnt(text2, 'data-quiz', label='无题的锚点不产出题目块')


# ══════════════════════════════════════════════════════════════════
# ⑥ 配图：缺文件报错；图片库里的图自动补来源与许可
# ══════════════════════════════════════════════════════════════════

@case('配图：缺文件报错带行号；图片库里的图题注自动补来源与许可')
def _(a):
    subject = new_subject()
    missing = '::: figure ../assets/img/pool/不存在的图.png'
    md = fixtures.write_content(subject, 1, 'overview-map', body=f'''## 配图

{missing}
alt: 内存里挨着放
:::
''')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.ok('图片文件不存在时非零退出', code != 0, f'exit={code}')
    a.has(out, f'{md}:{line_of(md, missing)}', label='报错指到内容文件的行')
    a.has(out, '不存在的图.png', label='报错说清是哪个文件')

    subject2 = new_subject()
    write_pool(subject2)
    fixtures.write_content(subject2, 1, 'overview-map', body=f'''## 配图

::: figure ../assets/img/pool/{POOL_IMAGE}
alt: 连续存储
caption: 图 1 · 数组在内存里挨着放
:::
''')
    code2, out2, text2, path2 = render(subject2, 1, 'overview-map')
    a.equal('图片库里的图放行', code2, 0)
    a.has(text2,
          '<figure class="lesson-figure">',
          f'<img src="../assets/img/pool/{POOL_IMAGE}" alt="连续存储">',
          '<figcaption>图 1 · 数组在内存里挨着放（来源：'
          'https://en.cppreference.com/w/cpp/language/array，许可：CC BY-SA 4.0）</figcaption>')

    # alt: 是属性值（纯文本），但和 caption: 一样不许真标签——格式文档把它列进「会报错的位置」
    subject3 = new_subject()
    write_pool(subject3)
    bad_alt = 'alt: <b>内存</b>里挨着放'
    md3 = fixtures.write_content(subject3, 1, 'overview-map', body=f'''## 配图

::: figure ../assets/img/pool/{POOL_IMAGE}
{bad_alt}
:::
''')
    code3, out3, text3, path3 = render(subject3, 1, 'overview-map')
    a.ok('alt: 里的真标签非零退出', code3 != 0, f'exit={code3}')
    a.has(out3, f'{md3}:{line_of(md3, bad_alt)}', label='报错指到 alt: 那一行（不是指令那一行）')
    a.has(out3, '<b>', label='报错说清读到哪个标签')
    a.ok('alt: 报错时不写盘', not os.path.exists(path3))

    # 没有标签的 alt: 照常出厂，属性转义口径不变（& 仍然转成 &amp;）
    subject4 = new_subject()
    write_pool(subject4)
    fixtures.write_content(subject4, 1, 'overview-map', body=f'''## 配图

::: figure ../assets/img/pool/{POOL_IMAGE}
alt: 连续存储 & 下标
:::
''')
    code4, out4, text4, path4 = render(subject4, 1, 'overview-map')
    a.equal('正常 alt: 放行', code4, 0)
    a.has(text4, 'alt="连续存储 &amp; 下标">')


# ══════════════════════════════════════════════════════════════════
# ⑦ 导航与序号：按 curriculum.yaml 的 nodes 顺序算
# ══════════════════════════════════════════════════════════════════

@case('导航与序号：首课无 --prev、末课无 --next、中间课两侧都对')
def _(a):
    subject = new_subject()
    body = '## 正文\n\n一段话。\n'
    for number, node in ((1, 'overview-map'), (2, 'first-program'), (5, 'func-and-ref')):
        fixtures.write_content(subject, number, node, body=body, goal='说清这一节要能做到什么。')

    code1, out1, first, path1 = render(subject, 1, 'overview-map')
    a.equal('首课渲染成功', code1, 0)
    a.ok('文件名 = <序号>-<节点id>.html', path1.endswith('0001-overview-map.html'))
    a.hasnt(first, 'lesson-nav__link--prev', label='首课没有 --prev 指针')
    a.has(first, '<a class="lesson-nav__link lesson-nav__link--next" href="0002-first-program.html">',
          '<span class="lesson-nav__dir">下节课</span>',
          '<span class="lesson-nav__title">编译并跑通</span>')

    code5, out5, last, path5 = render(subject, 5, 'func-and-ref')
    a.equal('末课渲染成功', code5, 0)
    a.hasnt(last, 'lesson-nav__link--next', label='末课没有 --next 指针')
    a.has(last, '<a class="lesson-nav__link lesson-nav__link--prev" href="0004-branch-and-loop.html">',
          '<span class="lesson-nav__dir">上节课</span>',
          '<span class="lesson-nav__title">分支与循环</span>')

    code2, out2, middle, path2 = render(subject, 2, 'first-program')
    a.equal('中间课渲染成功', code2, 0)
    a.has(middle,
          '<a class="lesson-nav__link lesson-nav__link--prev" href="0001-overview-map.html">',
          '<span class="lesson-nav__title">全景地图</span>',
          '<a class="lesson-nav__link lesson-nav__link--next" href="0003-io-and-vars.html">',
          '<span class="lesson-nav__title">读入数据与输出答案</span>')


# ══════════════════════════════════════════════════════════════════
# ⑧ 严格模式：未知指令与认不出的块语法都带行号报错
# ══════════════════════════════════════════════════════════════════

@case('严格模式：未知指令 / 四级标题 / 手写 HTML / 指令没闭合 都报错带行号')
def _(a):
    # 未知指令
    subject = new_subject()
    unknown = '::: fancy 一个不存在的指令'
    md = fixtures.write_content(subject, 1, 'overview-map',
                                body=f'## 正文\n\n{unknown}\n:::\n')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.ok('未知指令非零退出', code != 0, f'exit={code}')
    a.has(out, f'{md}:{line_of(md, unknown)}', label='未知指令报错带行号')
    a.has(out, '未知指令', label='报错说清是未知指令')
    a.ok('未知指令时不写盘', not os.path.exists(path))

    # 词汇表里没有的块语法：四级标题
    subject = new_subject()
    fixture = '#### 四级标题'
    md = fixtures.write_content(subject, 1, 'overview-map', body=f'## 正文\n\n{fixture}\n')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.ok('四级标题非零退出', code != 0, f'exit={code}')
    a.has(out, f'{md}:{line_of(md, fixture)}', label='四级标题报错带行号')
    a.has(out, '##', label='报错说清只支持 ## 与 ###')

    # 模型手写 HTML：块级标签一律拒收
    subject = new_subject()
    html_line = '<div class="lesson-tip">手写的提示块</div>'
    md = fixtures.write_content(subject, 1, 'overview-map', body=f'## 正文\n\n{html_line}\n')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.ok('手写 HTML 非零退出', code != 0, f'exit={code}')
    a.has(out, f'{md}:{line_of(md, html_line)}', label='手写 HTML 报错带行号')
    a.has(out, 'HTML', label='报错说清不该写 HTML')

    # 指令没闭合
    subject = new_subject()
    opener = '::: tip 忘了闭合'
    md = fixtures.write_content(subject, 1, 'overview-map',
                                body=f'## 正文\n\n{opener}\n\n正文写到一半就没了。\n')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.ok('指令没闭合非零退出', code != 0, f'exit={code}')
    a.has(out, f'{md}:{line_of(md, opener)}', label='没闭合报错指到指令那一行')
    a.has(out, '闭合', label='报错说清是没闭合')

    # related 的条目带说明（说明只有 resources 有）
    subject = new_subject()
    item = '- [上节课：浮点与精度](0004-cpp.float.html) | 官方文档'
    md = fixtures.write_content(subject, 1, 'overview-map',
                                body=f'## 正文\n\n::: related\n{item}\n:::\n')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.ok('related 带说明非零退出', code != 0, f'exit={code}')
    a.has(out, f'{md}:{line_of(md, item)}', label='related 带说明报错带行号')

    # svg 带了参数（说明只能写在块里的 alt:/caption:）
    subject = new_subject()
    opener = '::: svg 双指针收拢'
    md = fixtures.write_content(subject, 1, 'overview-map',
                                body=f'## 正文\n\n{opener}\n<svg viewBox="0 0 4 2"></svg>\n:::\n')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.ok('svg 带参数非零退出', code != 0, f'exit={code}')
    a.has(out, f'{md}:{line_of(md, opener)}', label='svg 带参数报错带行号')

    # 表格分隔行：格子里不是 --- 语法
    subject = new_subject()
    separator = '| --- | |'
    md = fixtures.write_content(subject, 1, 'overview-map',
                                body=f'## 表格\n\n| a | b |\n{separator}\n| 1 | 2 |\n')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.ok('分隔行语法不对时非零退出', code != 0, f'exit={code}')
    a.has(out, f'{md}:{line_of(md, separator)}', label='分隔行语法报错带行号')

    # 表格分隔行：格子数与表头不一致
    subject = new_subject()
    separator = '| --- |'
    md = fixtures.write_content(subject, 1, 'overview-map',
                                body=f'## 表格\n\n| a | b |\n{separator}\n| 1 | 2 |\n')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.ok('分隔行格子数不符时非零退出', code != 0, f'exit={code}')
    a.has(out, f'{md}:{line_of(md, separator)}', label='分隔行格子数报错带行号')
    a.has(out, '表头是 2 格', label='报错说清表头有几格')


# ══════════════════════════════════════════════════════════════════
# ⑨ --check：只解析校验、不写盘
# ══════════════════════════════════════════════════════════════════

@case('--check 只校验不写盘；坏内容 --check 也报错')
def _(a):
    subject = new_subject()
    fixtures.write_content(subject, 2, 'first-program', body='''## 正文

一段话。

::: quiz 理解 锚点：本节校验
:::
''')
    fixtures.write_quiz(subject, 2, 'first-program', {'本节校验': QUIZ_BOUNDARY})
    code, out, text, path = render(subject, 2, 'first-program', '--check')
    a.equal('--check 退出码 0', code, 0)
    a.ok('--check 不写盘', not os.path.exists(path), f'却写出了 {path}')

    code2, out2, text2, path2 = render(subject, 2, 'first-program')
    a.equal('不带 --check 才写盘', code2, 0)
    a.ok('产物存在', os.path.exists(path2))

    fixtures.write_content(subject, 2, 'first-program', body='## 正文\n\n::: nope 一个不存在的指令\n:::\n')
    code3, out3, text3, path3 = render(subject, 2, 'first-program', '--check')
    a.ok('坏内容 --check 非零退出', code3 != 0, f'exit={code3}')
    a.has(out3, '未知指令')


# ══════════════════════════════════════════════════════════════════
# ⑩ 提示卡：tip / warn / note（note 是追加的词汇，见 docs/课件内容格式.md）
# ══════════════════════════════════════════════════════════════════

@case('提示卡：tip / warn / note 的类名与加粗标题')
def _(a):
    subject = new_subject()
    fixtures.write_content(subject, 1, 'overview-map', body='''## 三个提示卡

::: tip 不想建文件也可以
临时试一行输入，可以直接敲 `./main` 回车。
:::

::: warn 两个反过来的写法
把 `-O2` 当成选项名会记串。
:::

::: note 两个名字先记住
`std::` 是标准库的命名空间前缀。
:::
''')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.equal('渲染退出码 0', code, 0)
    a.has(text,
          '<div class="lesson-tip">',
          '<b>不想建文件也可以</b>',
          '<p>临时试一行输入，可以直接敲 <code>./main</code> 回车。</p>',
          '<div class="lesson-warn">',
          '<b>两个反过来的写法</b>',
          '<div class="lesson-note">',
          '<b>两个名字先记住</b>')


# ══════════════════════════════════════════════════════════════════
# ⑪ 资源与相关：resources（ul + 说明）与 related（div + 链接）
# ══════════════════════════════════════════════════════════════════

@case('资源与相关：lesson-resources 的 li 结构、无链接条目、related 的 div')
def _(a):
    subject = new_subject()
    fixtures.write_content(subject, 1, 'overview-map', body='''## 参考资料

::: resources
- [OI Wiki · 分支](https://oi-wiki.org/lang/branch/) | 官方文档 · if 与 else if 的写法
- Competitive Programming 4（Halim 等，第 4 版） | 书 · 当参考书查
:::

::: related
- [上节课：浮点与精度](0004-cpp.float.html)
:::
''')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.equal('渲染退出码 0', code, 0)
    a.has(text, '<ul class="lesson-resources">',
          '<li><a href="https://oi-wiki.org/lang/branch/">'
          'OI Wiki · 分支</a><span class="lesson-resources__meta">官方文档 · if 与 else if 的写法'
          '</span></li>',
          '<li>Competitive Programming 4（Halim 等，第 4 版）'
          '<span class="lesson-resources__meta">书 · 当参考书查</span></li>',
          '</ul>',
          '<div class="lesson-related">',
          '<a href="0004-cpp.float.html">上节课：浮点与精度</a>')


# ══════════════════════════════════════════════════════════════════
# ⑫ 代码 span 逐字：里面的 ~ ^ ** 不当标记
# ══════════════════════════════════════════════════════════════════

@case('代码 span：~ ^ ** 是字面量，但上下标仍解析（语料 0002 的 code 里有 <sup>）')
def _(a):
    subject = new_subject()
    fixtures.write_content(subject, 1, 'overview-map', body='''## 位运算

按位取反写 `~a & ~b`，指针写 `int **p`，异或写 `a ^ b`。

算式写进代码里：`100000 × 100000 = 10^10^`。

区间写成 10 ~ 20 也行，单独的 ^ 与 * 不当标记。
''')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.equal('渲染退出码 0', code, 0)
    a.has(text,
          '<code>~a &amp; ~b</code>',
          '<code>int **p</code>',
          '<code>a ^ b</code>',
          '<code>100000 × 100000 = 10<sup>10</sup></code>',
          '区间写成 10 ~ 20 也行，单独的 ^ 与 * 不当标记。')
    a.hasnt(text, '<sub>', label='落单/带空格的 ~ 不产生下标（code 里也一样）')


# ══════════════════════════════════════════════════════════════════
# ⑬ 内联 SVG：原样透传
# ══════════════════════════════════════════════════════════════════

@case('内联 SVG：figure--inline + 块内 SVG 原样透传（缺 </svg> 报错）')
def _(a):
    subject = new_subject()
    svg = ('<svg viewBox="0 0 40 20" role="img" aria-hidden="true">'
           '<path d="M2 10h36" stroke="currentColor"/></svg>')
    fixtures.write_content(subject, 1, 'overview-map', body=f'''## 画一张

::: svg
alt: 双指针向中间收拢
caption: 图 1 · 收拢过程

{svg}
:::
''')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.equal('渲染退出码 0', code, 0)
    a.has(text,
          '<figure class="lesson-figure lesson-figure--inline" role="img" aria-label="双指针向中间收拢">',
          svg,
          '<figcaption>图 1 · 收拢过程</figcaption>')
    a.ok('SVG 逐字在产物里', text.count(svg) == 1)

    # 缺 </svg>：原样透传会把页面结构从这里断掉，必须报错而不是照发
    subject2 = new_subject()
    broken = '<svg viewBox="0 0 40 20"><path d="M2 10h36"/>'
    md = fixtures.write_content(subject2, 1, 'overview-map',
                                body=f'## 画一张\n\n::: svg\n{broken}\n:::\n')
    code2, out2, text2, path2 = render(subject2, 1, 'overview-map')
    a.ok('缺 </svg> 非零退出', code2 != 0, f'exit={code2}')
    a.has(out2, f'{md}:{line_of(md, "::: svg")}', label='缺 </svg> 报错指到指令那一行')
    a.has(out2, '</svg>', label='报错说清缺什么')

    # 自闭合的根 <svg/> 是合法收尾（退化但合法），不能拦
    subject3 = new_subject()
    fixtures.write_content(subject3, 1, 'overview-map',
                           body='## 画一张\n\n::: svg\n<svg viewBox="0 0 4 2"/>\n:::\n')
    code3, out3, text3, path3 = render(subject3, 1, 'overview-map')
    a.equal('自闭合 <svg/> 放行', code3, 0)
    a.has(text3, '<figure class="lesson-figure lesson-figure--inline">',
          '<svg viewBox="0 0 4 2"/>')

    # 注释里写 </svg> 不算收尾（先遮注释再判）；<svgfoo> 不算 <svg> 开头
    subject4 = new_subject()
    fake = '<svg viewBox="0 0 4 2"><!-- </svg> -->'
    md = fixtures.write_content(subject4, 1, 'overview-map',
                                body=f'## 画一张\n\n::: svg\n{fake}\n:::\n')
    code4, out4, text4, path4 = render(subject4, 1, 'overview-map')
    a.ok('注释里的 </svg> 不算收尾：非零退出', code4 != 0, f'exit={code4}')
    a.has(out4, f'{md}:{line_of(md, "::: svg")}', label='假收尾报错指到指令那一行')

    subject5 = new_subject()
    md = fixtures.write_content(subject5, 1, 'overview-map',
                                body='## 画一张\n\n::: svg\n<svgfoo>\n:::\n')
    code5, out5, text5, path5 = render(subject5, 1, 'overview-map')
    a.ok('<svgfoo> 不算 <svg>：非零退出', code5 != 0, f'exit={code5}')
    a.has(out5, f'{md}:{line_of(md, "::: svg")}', label='假开头报错指到指令那一行')

    # 正常闭合的多行 SVG：逐字透传
    subject6 = new_subject()
    multi = ('<svg viewBox="0 0 40 20" role="img">\n'
             '  <path d="M2 10h36" stroke="currentColor"/>\n'
             '</svg>')
    fixtures.write_content(subject6, 1, 'overview-map',
                           body=f'## 画一张\n\n::: svg\n{multi}\n:::\n')
    code6, out6, text6, path6 = render(subject6, 1, 'overview-map')
    a.equal('多行 SVG 放行', code6, 0)
    a.has(text6, multi)

    # 收尾被拆成两行（`</sv` + `g>`）：拼接判据一旦不留换行，这种断掉的收尾也会算数
    subject7 = new_subject()
    split = '<svg viewBox="0 0 40 20" role="img">\n<path d="M2 10h36"/>\n</sv\ng>'
    md7 = fixtures.write_content(subject7, 1, 'overview-map',
                                 body=f'## 画一张\n\n::: svg\n{split}\n:::\n')
    code7, out7, text7, path7 = render(subject7, 1, 'overview-map')
    a.ok('收尾拆成两行非零退出', code7 != 0, f'exit={code7}')
    a.has(out7, f'{md7}:{line_of(md7, "::: svg")}', label='拆分收尾报错指到指令那一行')
    a.has(out7, '</svg>', label='报错说清缺什么')

    # 开标签跨行、自闭合根跨行都是合法写法（保留换行不能把它们误杀）
    subject8 = new_subject()
    wrapped = ('<svg\n  viewBox="0 0 40 20"\n  role="img">\n'
               '<path d="M2 10h36" stroke="currentColor"/>\n</svg>')
    fixtures.write_content(subject8, 1, 'overview-map',
                           body=f'## 画一张\n\n::: svg\n{wrapped}\n:::\n')
    code8, out8, text8, path8 = render(subject8, 1, 'overview-map')
    a.equal('开标签跨行放行', code8, 0)
    a.has(text8, wrapped)

    subject9 = new_subject()
    folded = '<svg\n  viewBox="0 0 4 2"\n/>'
    fixtures.write_content(subject9, 1, 'overview-map',
                           body=f'## 画一张\n\n::: svg\n{folded}\n:::\n')
    code9, out9, text9, path9 = render(subject9, 1, 'overview-map')
    a.equal('自闭合根跨行放行', code9, 0)
    a.has(text9, folded)

    # alt: 同 figure：属性值是纯文本，但真标签要拦，行号指到 alt: 那一行
    subject10 = new_subject()
    bad_alt = 'alt: <script>alert(1)</script>'
    md10 = fixtures.write_content(subject10, 1, 'overview-map',
                                  body=f'## 画一张\n\n::: svg\n{bad_alt}\n{svg}\n:::\n')
    code10, out10, text10, path10 = render(subject10, 1, 'overview-map')
    a.ok('svg 的 alt: 里的真标签非零退出', code10 != 0, f'exit={code10}')
    a.has(out10, f'{md10}:{line_of(md10, bad_alt)}', label='报错指到 alt: 那一行')
    a.ok('svg 的 alt: 报错时不写盘', not os.path.exists(path10))


# ══════════════════════════════════════════════════════════════════
# ⑬′ 图注编号：渲染器按页内顺序给号（figure 与 svg 共用一条序列，手写旧号被剥掉重编）
# ══════════════════════════════════════════════════════════════════

@case('图注编号：页内顺序、figure 与 svg 共用序列、旧号被剥掉重编、没 caption 不占号')
def _(a):
    subject = new_subject()
    write_pool(subject)
    svg = ('<svg viewBox="0 0 40 20" role="img" aria-hidden="true">'
           '<path d="M2 10h36" stroke="currentColor"/></svg>')
    fixtures.write_content(subject, 1, 'overview-map', body=f'''## 画三张

::: svg
alt: 第一张示意图
caption: 收拢过程

{svg}
:::

::: figure ../assets/img/pool/{POOL_IMAGE}
alt: 没有说明的图
:::

::: figure ../assets/img/pool/{POOL_IMAGE}
alt: 作者写了旧号
caption: 图 7 · 内存里挨着放
:::
''')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.equal('渲染退出码 0', code, 0)
    a.has(text,
          '<figcaption>图 1 · 收拢过程</figcaption>',
          '<figcaption>图 2 · 内存里挨着放（来源：'
          'https://en.cppreference.com/w/cpp/language/array，许可：CC BY-SA 4.0）</figcaption>',
          label='编号按页内顺序给（svg 先出场就是图 1），手写的「图 7 ·」被剥掉重编成图 2')
    a.hasnt(text, '图 7', label='旧号不留在产物里')
    a.ok('没写 caption 的图不编号、也不占号（只有来源那一行，且不出现图 3）',
         '<figcaption>（来源：' in text and '图 3' not in text)

    # 幂等：同一份内容再渲染一次，产物逐字相同（旧号已经不存在，重编结果不变）
    code2, out2, text2, path2 = render(subject, 1, 'overview-map')
    a.equal('重渲染幂等（产物不变）', text2, text)

    # 只有空白的 caption：不生成 figcaption，也不占号
    subject2 = new_subject()
    fixtures.write_content(subject2, 1, 'overview-map',
                           body=f'## 画一张\n\n::: svg\ncaption:   \n{svg}\n:::\n')
    code3, out3, text3, path3 = render(subject2, 1, 'overview-map')
    a.equal('空白 caption 放行', code3, 0)
    a.hasnt(text3, '<figcaption>', label='空白 caption 不生成图注')

    # 两张都没写 caption：都不编号，后面那张写了号才从图 1 起（号跟着可见标签走）
    subject3 = new_subject()
    write_pool(subject3)
    fixtures.write_content(subject3, 1, 'overview-map', body=f'''## 画两张

::: figure ../assets/img/pool/{POOL_IMAGE}
alt: 第一张没说明
:::

::: figure ../assets/img/pool/{POOL_IMAGE}
alt: 第二张有说明
caption: 只有这张有号
:::
''')
    code4, out4, text4, path4 = render(subject3, 1, 'overview-map')
    a.equal('两张图放行', code4, 0)
    a.has(text4, '<figcaption>图 1 · 只有这张有号（来源：',
          label='编号只数有说明的图：第二张才是图 1')


# ══════════════════════════════════════════════════════════════════
# ⑬″ 数学式：$…$ 行内 / $$…$$ 块级（离线 KaTeX，按需注入）
# ══════════════════════════════════════════════════════════════════

@case('数学式：行内与块级、代码里不解析、\\$ 转义、没收尾报错、没公式不注入 KaTeX')
def _(a):
    subject = new_subject()
    fixtures.write_content(subject, 1, 'overview-map', body=r'''## 公式

行内 $Ax = b$ 与 $\lambda_1 v_1$，不等式两个都要转义：$x < y$。

$$
\begin{bmatrix} 2 & 1 \\ 1 & 3 \end{bmatrix}
$$

段落中间的块级也认：价格 $$p = 3q$$ 一段。

代码里不动：`$HOME` 与

```bash
echo $HOME
```

正文里的美元号写 \$5。
''')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.equal('渲染退出码 0', code, 0)
    a.has(text,
          '<span class="math-inline">Ax = b</span>',
          '<span class="math-inline">\\lambda_1 v_1</span>',
          '<span class="math-inline">x &lt; y</span>',
          '<div class="math-block">\\begin{bmatrix} 2 &amp; 1 \\\\ 1 &amp; 3 \\end{bmatrix}</div>',
          '<span class="math-block">p = 3q</span>',
          label='行内/块级公式包成占位元素，TeX 里的 &<> 转义')
    a.has(text, '<code>$HOME</code>', '<pre data-lang="bash"><code>echo $HOME</code></pre>',
          label='代码 span 与代码围栏里的美元号不受影响')
    a.has(text, '正文里的美元号写 $5。', label='`\\$` 转义成字面美元号')
    a.has(text,
          '<link rel="stylesheet" href="../../../assets/katex/katex.min.css">',
          '<script src="../../../assets/katex/katex.min.js" defer></script>',
          '<script src="../../../assets/lesson-math.js" defer></script>',
          label='有公式的页面注入离线 KaTeX 三件')

    # 没有公式的页面：不注入引用，也不留占位符残留（老课件与非数学课零 diff）
    subject2 = new_subject()
    fixtures.write_content(subject2, 1, 'overview-map', body='## 试\n\n这一页只有文字。\n')
    code2, out2, text2, path2 = render(subject2, 1, 'overview-map')
    a.equal('无公式页渲染退出码 0', code2, 0)
    a.hasnt(text2, 'katex', '@LEARN:MATH', label='无公式页不注入 KaTeX、不留占位符')

    # 行内公式没收尾：公式写错时页面只显示 TeX 原文（看不出错），所以按确定性错误拦下
    subject3 = new_subject()
    md3 = fixtures.write_content(subject3, 1, 'overview-map',
                                 body='## 试\n\n行内公式 $Ax = b 忘了收尾。\n')
    code3, out3, text3, path3 = render(subject3, 1, 'overview-map')
    a.ok('行内公式没收尾非零退出', code3 != 0, f'exit={code3}')
    a.has(out3, f'{md3}:{line_of(md3, "行内公式 $Ax = b 忘了收尾。")}', label='报错指到那一行')
    a.has(out3, '\\$', label='报错给出 `\\$` 的出路')
    a.ok('报错时不写盘', not os.path.exists(path3))

    # 块级公式没收尾：同样报错（别让它把后面整段吞成公式）
    subject4 = new_subject()
    md4 = fixtures.write_content(subject4, 1, 'overview-map',
                                 body='## 试\n\n$$\n\\begin{bmatrix} 1 & 2 \\end{bmatrix}\n')
    code4, out4, text4, path4 = render(subject4, 1, 'overview-map')
    a.ok('块级公式没收尾非零退出', code4 != 0, f'exit={code4}')
    a.has(out4, '块级公式 `$$…$$` 没有收尾', label='块级报错说清缺什么')


@case('题库里只有公式：正文没有 $…$，也要给页面注入 KaTeX（quiz.js 在浏览器里排版）')
def _(a):
    subject = new_subject()
    fixtures.write_content(subject, 1, 'overview-map',
                           body='## 试\n\n这一页正文一个公式都没有。\n\n::: quiz 理解 锚点：本节校验\n:::\n')
    fixtures.write_quiz(subject, 1, 'overview-map', {
        '本节校验': [{'q': '矩阵 $\\begin{bmatrix} 2 & 1 \\\\ 1 & 3 \\end{bmatrix}$ 的行列式？',
                      'opts': ['$1$', '$6$'], 'ans': 1, 'why': '用 $ad - bc$ 算。'}],
    })
    code, out, text, path = render(subject, 1, 'overview-map')
    a.equal('渲染退出码 0', code, 0)
    a.has(text,
          '<link rel="stylesheet" href="../../../assets/katex/katex.min.css">',
          '<script src="../../../assets/katex/katex.min.js" defer></script>',
          '<script src="../../../assets/lesson-math.js" defer></script>',
          label='公式只在题库里 → 壳里照样注入 KaTeX')
    a.hasnt(text, '<span class="math-inline">', label='正文里确实没有静态公式占位')

    # 反过来：题库与正文都没有公式时，一个引用都不该有
    subject2 = new_subject()
    fixtures.write_content(subject2, 1, 'overview-map',
                           body='## 试\n\n没有公式。\n\n::: quiz 理解 锚点：本节校验\n:::\n')
    fixtures.write_quiz(subject2, 1, 'overview-map',
                        {'本节校验': [{'q': '题干', 'opts': ['A', 'B'], 'ans': 0, 'why': '解释'}]})
    code2, out2, text2, path2 = render(subject2, 1, 'overview-map')
    a.equal('无公式页渲染退出码 0', code2, 0)
    a.hasnt(text2, 'katex', label='题面也没有公式时不注入')


# ══════════════════════════════════════════════════════════════════
# ⑭ 端到端：渲染产物过检查（check_lesson.py）
# ══════════════════════════════════════════════════════════════════

@case('渲染产物过检查：check_lesson.py 报 OK')
def _(a):
    subject = new_subject()
    # 检查按同目录编号判「不能跳号」：把邻居也渲染出来，0002 才是目录里的中间编号
    for number, node in ((1, 'overview-map'), (3, 'io-and-vars')):
        fixtures.write_content(subject, number, node, body='## 正文\n\n一段话。\n',
                               goal='说清这一节要能做到什么。')
        render(subject, number, node)
    fixtures.write_content(subject, 2, 'first-program', body='''## 校对边界

先不编译，按规则判一次它实际走哪条路。

::: quiz 理解 锚点：校对边界
:::

::: resources
- [OI Wiki · 分支](https://oi-wiki.org/lang/branch/) | 官方文档 · if 与 else if 的写法
:::
''')
    fixtures.write_quiz(subject, 2, 'first-program', {'校对边界': QUIZ_BOUNDARY})
    code, out, text, path = render(subject, 2, 'first-program')
    a.equal('渲染退出码 0', code, 0)
    gate_code, gate_out = fixtures.run_gate(path, subject, 'first-program')
    a.equal('检查退出码 0', gate_code, 0)
    a.has(gate_out, f'OK   {path}', label='检查回 OK')


# ══════════════════════════════════════════════════════════════════
# ⑮ 一级标题不许静默消失（`# 标题` 与行首 `#include` 都要报错）
# ══════════════════════════════════════════════════════════════════

@case('一级标题与行首 #include 都报错带行号（内容不会静默消失）')
def _(a):
    subject = new_subject()
    heading = '# 这一行连同标题会整块消失'
    include = '#include <cstdio>'
    md = fixtures.write_content(subject, 1, 'overview-map', body=f'''## 正文

这一段还在。

{heading}

再写一行：
{include}
''')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.ok('一级标题非零退出', code != 0, f'exit={code}')
    a.has(out, f'{md}:{line_of(md, heading)}', label='一级标题报错带行号')
    a.has(out, f'{md}:{line_of(md, include)}', label='行首 #include 报错带行号')
    a.has(out, '## 与 ###', '围栏', label='报错给出改法（只有 ##/###，代码放围栏）')
    a.ok('报错时不写盘', not os.path.exists(path))

    # 放进围栏就正常：同一段代码不该再被当成标题
    fixtures.write_content(subject, 1, 'overview-map', body=f'''## 正文

```cpp
{include}
```
''')
    code2, out2, text2, path2 = render(subject, 1, 'overview-map')
    a.equal('围栏里的 #include 放行', code2, 0)
    a.has(text2, '<pre data-lang="cpp"><code>#include &lt;cstdio&gt;</code></pre>')

    # 兜底：渲染器遇到不认识的块要报错，不能安静地丢
    problems = render_lesson.Problems()
    renderer = render_lesson.Renderer('x.md', problems, '.', None, 'x.quiz.json', {})
    output = renderer.render_block({'kind': 'h1', 'text': '一级标题', 'line': 7}, '  ')
    a.equal('不认识的块不产出内容', output, '')
    a.ok('不认识的块记了一条问题', bool(problems) and problems.items[0][1] == 7,
         f'problems={problems.items}')

    # 兜底同理：不认识的指令也要报错（不能静默空输出）
    problems2 = render_lesson.Problems()
    renderer2 = render_lesson.Renderer('x.md', problems2, '.', None, 'x.quiz.json', {})
    output2 = renderer2.render_directive({'kind': 'directive', 'name': 'nope', 'line': 9}, '  ')
    a.equal('不认识的指令不产出内容', output2, '')
    a.ok('不认识的指令记了一条问题', bool(problems2) and problems2.items[0][1] == 9,
         f'problems={problems2.items}')


# ══════════════════════════════════════════════════════════════════
# ⑯ 段落中间的 HTML 标签要拦；运算符/泛型/落单反引号都不误伤
# ══════════════════════════════════════════════════════════════════

@case('段落中间的 HTML 标签报错；运算符/泛型/落单反引号都不误伤')
def _(a):
    subject = new_subject()
    inline_html = '这段里手写了 <b>粗</b> 标签。'
    md = fixtures.write_content(subject, 1, 'overview-map',
                                body=f'## 正文\n\n{inline_html}\n')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.ok('段落内标签非零退出', code != 0, f'exit={code}')
    a.has(out, f'{md}:{line_of(md, inline_html)}', label='段落内标签报错带行号')
    a.has(out, '<b>', '**…**', label='报错给出改法（粗体写 **…**）')
    a.ok('报错时不写盘', not os.path.exists(path))

    # 落单的反引号不是 code 区：它不能把后面的标签遮住（code span 判定与 inline() 共用一份）
    subject = new_subject()
    masked = '见 ` 这里 <b>粗</b> 结束。'
    md = fixtures.write_content(subject, 1, 'overview-map',
                                body=f'## 正文\n\n{masked}\n')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.ok('落单反引号遮不住标签：非零退出', code != 0, f'exit={code}')
    a.has(out, f'{md}:{line_of(md, masked)}', label='落单反引号那一段报错带行号')
    a.has(out, '<b>')

    # 段落中间的 HTML 注释也要拦（手写时代留「题目位置」的写法）
    subject = new_subject()
    comment = '前面 <!-- 题目位置：L1 ×2 --> 后面。'
    md = fixtures.write_content(subject, 1, 'overview-map',
                                body=f'## 正文\n\n{comment}\n')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.ok('段落中间注释非零退出', code != 0, f'exit={code}')
    a.has(out, f'{md}:{line_of(md, comment)}', label='段落中间注释报错带行号')
    a.has(out, 'HTML 注释', label='报错说清是注释')

    # front matter 的 title 也是散文，同样要查（它是纯文本，不走 inline()）
    subject = new_subject()
    fixtures.write_content(subject, 1, 'overview-map', body='## 正文\n\n一段话。\n',
                           title='<b>粗</b>标题')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.ok('title 里的标签非零退出', code != 0, f'exit={code}')
    a.has(out, 'title', label='报错说清是 front matter 的 title')

    # 运算符、泛型、code span：都必须原样放行
    subject2 = new_subject()
    operators = ('当 n<m 且 m>0 时循环继续，a<b>c 也一样；比较写成 a < b && c > d、2 < n，'
                 '泛型写 <T> 与 `vector<int>` 都没问题。')
    fixtures.write_content(subject2, 1, 'overview-map', body=f'## 运算符\n\n{operators}\n')
    code2, out2, text2, path2 = render(subject2, 1, 'overview-map')
    a.equal('运算符与泛型放行', code2, 0)
    a.has(text2, '<p>当 n&lt;m 且 m&gt;0 时循环继续，a&lt;b&gt;c 也一样；'
                 '比较写成 a &lt; b &amp;&amp; c &gt; d、2 &lt; n，'
                 '泛型写 &lt;T&gt; 与 <code>vector&lt;int&gt;</code> 都没问题。</p>')


# ══════════════════════════════════════════════════════════════════
# ⑰ 指令体里的代码围栏不被当成指令边界
# ══════════════════════════════════════════════════════════════════

@case('指令体里的围栏：里面的 ::: 是代码文本，不当指令边界')
def _(a):
    subject = new_subject()
    fixtures.write_content(subject, 1, 'overview-map', body='''## 写法示例

::: tip 题目位置的写法
题目位置在正文里长这样：

```markdown
::: quiz 理解 锚点：某个锚点
:::
```

锚点要和题库的键逐字一致。
:::
''')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.equal('渲染退出码 0', code, 0)
    a.ok('没有误报「指令块不能嵌套」', '不能嵌套' not in out, out)
    a.has(text,
          '<div class="lesson-tip">',
          '<b>题目位置的写法</b>',
          '<pre data-lang="markdown"><code>::: quiz 理解 锚点：某个锚点\n:::</code></pre>',
          '<p>锚点要和题库的键逐字一致。</p>')


# ══════════════════════════════════════════════════════════════════
# ⑱ 模板占位符报错的行号要指到 templates/lesson.html 的真实行
# ══════════════════════════════════════════════════════════════════

@case('模板占位符报错指到模板文件的真实行号（不被 DOCTYPE 切片平移）')
def _(a):
    template_path = render_lesson.TEMPLATE
    original = open(template_path, encoding='utf-8').read()
    marker = '<!-- @LEARN:TITLE -->'
    a.ok('模板里 TITLE 出现两次（用例前提）', original.count(marker) == 2,
         f'实际 {original.count(marker)} 次')

    # 去掉 <h1> 那一处，只留 <title> 那一处：占位符数不对（1 ≠ 2），报错必须指到留下的那一行
    broken = original.replace(f'<h1>{marker}</h1>', '<h1>标题</h1>', 1)
    tmp_dir = tempfile.mkdtemp(prefix='smtest-tpl-')
    broken_path = os.path.join(tmp_dir, 'lesson.html')
    with open(broken_path, 'w', encoding='utf-8') as handle:
        handle.write(broken)
    true_line = broken[:broken.find(marker)].count('\n') + 1
    problems = render_lesson.Problems()
    a.ok('模板能读进来', render_lesson.load_template(broken_path, problems) is not None)
    a.ok('模板缺占位符时报错', bool(problems), '没有报错')
    if problems:
        path, line, message = problems.items[0]
        a.equal('报错指到模板文件', path, broken_path)
        a.equal('行号 = 模板文件里的真实行号', line, true_line)
        a.has(message, marker)
    shutil.rmtree(tmp_dir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════
# ⑲ 真标签名单：完整 HTML 元素表 + SVG 名（script/iframe/video… 都拦），名单与格式文档逐字一致
# ══════════════════════════════════════════════════════════════════

# 完整标准 HTML 元素表（HTML living standard 的每一个元素，含旧式、表现型与已废弃的那些）
# + SVG 元素名，全小写。这是**写死的第二份**：代码、本节、docs/课件内容格式.md §2 三份必须
# 逐字一致——名单曾经收窄成 45 个名字，于是 <iframe>/<video>/<form>/<main> 与 11 个 SVG 名字
# 静默当字面量出厂（exit 0）。
RULED_TAG_NAMES = frozenset('''
    a abbr acronym address animate animatemotion animatetransform applet area article aside audio b
    base basefont bdi bdo bgsound big blink blockquote body br button canvas caption center circle
    cite clippath code col colgroup content data datalist dd defs del desc details dfn dialog dir
    div dl dt ellipse em embed feblend fecolormatrix fecomponenttransfer fecomposite
    feconvolvematrix fediffuselighting fedisplacementmap fedistantlight fedropshadow feflood fefunca
    fefuncb fefuncg fefuncr fegaussianblur feimage femerge femergenode femorphology fencedframe
    feoffset fepointlight fespecularlighting fespotlight fetile feturbulence fieldset figcaption
    figure filter font footer foreignobject form frame frameset g geolocation h1 h2 h3 h4 h5 h6 head
    header hgroup hr html i iframe image img input ins isindex kbd keygen label legend li line
    lineargradient link listing main map mark marker marquee mask math menu menuitem meta metadata
    meter mpath multicol nav nextid nobr noembed noframes noscript object ol optgroup option output
    p param path pattern picture plaintext polygon polyline pre progress q radialgradient rb rect rp
    rt rtc ruby s samp script search section select selectedcontent set shadow slot small source
    spacer span stop strike strong style sub summary sup svg switch symbol table tbody td template
    text textarea textpath tfoot th thead time title tr track tspan tt u ul use var video view wbr
    xmp
'''.split())

# 上一轮收窄后静默放行、本轮必须重新拦下的名字：16 个正文/旧式（复评逐条探过）+ 11 个 SVG。
REGRESSED_TAG_NAMES = (
    'aside blockquote button canvas caption dd details dl dt form iframe main small summary '
    'tfoot video circle rect line polygon polyline g text use tspan marker defs').split()


def doc_tag_names():
    """从 docs/课件内容格式.md §2 的白名单那句里取名字（`h1…h6` 展开成 h1..h6）。"""
    doc = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                       'docs', '课件内容格式.md')
    text = open(doc, encoding='utf-8').read()
    sentence = re.search(r'真标签白名单\*\*里——(.+?)这些引擎', text, re.S)
    assert sentence, 'docs/课件内容格式.md 里找不到真标签白名单那句（文档被改写了）'
    listed = re.search(r'`([^`]+)`', sentence.group(1), re.S).group(1)
    listed = re.sub(r'h1…h6', ' '.join(f'h{i}' for i in range(1, 7)), listed)
    return {token for token in re.findall(r'[a-z][a-z0-9]*', listed)}


@case('真标签名单：完整 HTML 元素表 + SVG 名都拦；名单 = 写死集合 = 格式文档')
def _(a):
    a.ok('名单 = 测试里写死的完整集合（多一个少一个都不行）',
         render_lesson.HTML_TAG_NAMES == RULED_TAG_NAMES,
         f'代码多 {sorted(render_lesson.HTML_TAG_NAMES - RULED_TAG_NAMES)}，'
         f'代码少 {sorted(RULED_TAG_NAMES - render_lesson.HTML_TAG_NAMES)}')
    a.ok('名单 = docs/课件内容格式.md 里列的那一份（多一个少一个都不行）',
         render_lesson.HTML_TAG_NAMES == doc_tag_names(),
         f'代码多 {sorted(render_lesson.HTML_TAG_NAMES - doc_tag_names())}，'
         f'代码少 {sorted(doc_tag_names() - render_lesson.HTML_TAG_NAMES)}')
    a.ok('名单全是小写（查表前 lower()，大小写约定一致）',
         all(name == name.lower() for name in render_lesson.HTML_TAG_NAMES))
    a.ok('被收窄掉的 27 个名字都在名单里', set(REGRESSED_TAG_NAMES) <= RULED_TAG_NAMES,
         f'缺：{sorted(set(REGRESSED_TAG_NAMES) - RULED_TAG_NAMES)}')

    # 四个 head 标签：段落中间与行首都要拦（曾经漏在名单外，静默当字面量出厂）
    for name, sample in (('script', '<script>alert(1)</script>'),
                         ('style', '<style>p{color:red}</style>'),
                         ('link', '<link rel="stylesheet" href="x.css">'),
                         ('meta', '<meta charset="utf-8">')):
        subject = new_subject()
        inline = f'这段里写了 {sample} 标签。'
        md = fixtures.write_content(subject, 1, 'overview-map',
                                    body=f'## 正文\n\n{inline}\n')
        code, out, text, path = render(subject, 1, 'overview-map')
        a.ok(f'段落中间的 <{name}> 非零退出', code != 0, f'exit={code}')
        a.has(out, f'{md}:{line_of(md, inline)}', label=f'<{name}> 报错带行号')
        a.ok(f'<{name}> 报错时不写盘', not os.path.exists(path))

        subject2 = new_subject()
        md2 = fixtures.write_content(subject2, 1, 'overview-map',
                                     body=f'## 正文\n\n{sample}\n')
        code2, out2, text2, path2 = render(subject2, 1, 'overview-map')
        a.ok(f'行首 <{name}> 非零退出', code2 != 0, f'exit={code2}')
        a.has(out2, f'{md2}:{line_of(md2, sample)}', label=f'行首 <{name}> 报错带行号')

    # 复评探过的那 27 个名字（iframe/video/form/main/button/canvas… 与 circle/rect/g/text/defs…）：
    # 段落中间出现就要 exit≠0 + 报错带行号 + 不写盘（re-review 的原始形状，逐个单独渲染）
    for name in REGRESSED_TAG_NAMES:
        subject3 = new_subject()
        inline3 = f'这段里写了 <{name}>x</{name}> 标签。'
        md3 = fixtures.write_content(subject3, 1, 'overview-map', body=f'## 正文\n\n{inline3}\n')
        code3, out3, text3, path3 = render(subject3, 1, 'overview-map')
        a.ok(f'段落中间的 <{name}> 非零退出', code3 != 0, f'exit={code3}')
        a.has(out3, f'{md3}:{line_of(md3, inline3)}', label=f'<{name}> 报错带行号')
        a.ok(f'<{name}> 报错时不写盘', not os.path.exists(path3))

    # 名单里每个名字都真的会拦（防止将来再悄悄删条目）：一次渲染里给每个名字一段，
    # 每段都该报出自己那一行——206 段一次跑完，比「一个名字起一次子进程」快一个量级。
    subject4 = new_subject()
    paragraphs = [f'这段里写了 <{name}>x</{name}> 标签。' for name in sorted(RULED_TAG_NAMES)]
    fixtures.write_content(subject4, 1, 'overview-map',
                           body='## 正文\n\n' + '\n\n'.join(paragraphs) + '\n')
    code4, out4, text4, path4 = render(subject4, 1, 'overview-map')
    a.ok('名单里出现任意一个都要非零退出', code4 != 0, f'exit={code4}')
    missing = [name for name in sorted(RULED_TAG_NAMES) if f"读到 '<{name}>'" not in out4]
    a.ok('名单里每个名字都真的会拦', not missing, f'这些名字没拦住：{missing}')
    a.ok('名单全拦截时不写盘', not os.path.exists(path4))


# ══════════════════════════════════════════════════════════════════
# ⑳ empty_reason 只准出现在 ::: quiz：别的指令块里写了会当正文印出来，按错拦下
# ══════════════════════════════════════════════════════════════════

@case('empty_reason 只准出现在 ::: quiz：practice/tip 里写了报错带行号，删掉就放行')
def _(a):
    stray = 'empty_reason: 该锚点的过关标准在 lab 里验'
    head = '## 跑三遍\n\n把命令换三个输入各跑一次。\n\n'

    subject = new_subject()
    md = fixtures.write_content(
        subject, 2, 'first-program',
        body=head + '::: practice 练习 | 第 1 步 · 三条路各跑一次\n\n' + stray + '\n\n:::\n')
    code, out, text, path = render(subject, 2, 'first-program')
    a.ok('练习段落里写了 empty_reason 时非零退出', code != 0, f'exit={code}')
    a.has(out, f'{md}:{line_of(md, stray)}', label='报错指到 empty_reason 那一行')
    a.has(out, '::: quiz', label='报错说清它只属于 ::: quiz')
    a.ok('报错时没有写盘', not os.path.exists(path))

    subject2 = new_subject()
    fixtures.write_content(
        subject2, 2, 'first-program',
        body=head + '::: practice 练习 | 第 1 步 · 三条路各跑一次\n\n三条输入各跑一次。\n\n:::\n')
    code2, _, text2, path2 = render(subject2, 2, 'first-program')
    a.equal('把那一行删掉就放行', code2, 0)
    a.has(text2, 'lesson-practice__level', label='练习段落照常产出')

    subject3 = new_subject()
    md3 = fixtures.write_content(subject3, 2, 'first-program',
                                 body='## 记一下\n\n::: tip 记一下\n\n' + stray + '\n\n:::\n')
    code3, out3, _, path3 = render(subject3, 2, 'first-program')
    a.ok('提示卡里写了也拦', code3 != 0, f'exit={code3}')
    a.has(out3, f'{md3}:{line_of(md3, stray)}', label='提示卡里的也指到那一行')
    a.ok('提示卡报错时也没有写盘', not os.path.exists(path3))


# ══════════════════════════════════════════════════════════════════
# ㉑ 锚点对账（反方向）：题库里多出来的键没有任何题目位置引用，那些题一道都不会上页面
# ══════════════════════════════════════════════════════════════════

@case('题库里的孤儿锚点：没有题目位置引用它 → 报错带行号；删掉那个键就放行')
def _(a):
    subject = new_subject()
    fixtures.write_content(subject, 1, 'overview-map', body='''## 边界

::: quiz 理解 锚点：锚点A
:::
''')
    quiz_path = os.path.splitext(fixtures.lesson_md(subject, 1, 'overview-map'))[0] + '.quiz.json'
    fixtures.write_quiz(subject, 1, 'overview-map',
                        {'锚点A': QUIZ_BOUNDARY, '孤儿锚点': QUIZ_BOUNDARY})
    code, out, text, path = render(subject, 1, 'overview-map')
    a.ok('孤儿键非零退出', code != 0, f'exit={code}')
    a.has(out, f'{quiz_path}:', label='报错指到题库文件（不是内容文件）')
    a.has(out, '孤儿锚点', label='报错点名那个没人引用的键')
    a.has(out, '任何 ::: quiz 题目位置引用', label='报错说清方向：没有任何题目位置引用它')
    a.ok('孤儿键报错时不写盘', not os.path.exists(path))

    # 正方向没被误伤：删掉孤儿键，被引用的那道题照常渲染
    fixtures.write_quiz(subject, 1, 'overview-map', {'锚点A': QUIZ_BOUNDARY})
    code2, out2, text2, path2 = render(subject, 1, 'overview-map')
    a.equal('删掉孤儿键后渲染成功', code2, 0)
    a.has(text2, '<div class="quiz" data-quiz=', label='被引用的题照常产出')

    # 同一类漏法的另一头：内容里一个题目位置都没有，题库文件却还在（整份交付没人用）
    subject2 = new_subject()
    fixtures.write_content(subject2, 1, 'overview-map', body='## 正文\n\n一段话。\n')
    stale = fixtures.write_quiz(subject2, 1, 'overview-map', {'锚点A': QUIZ_BOUNDARY})
    code3, out3, text3, path3 = render(subject2, 1, 'overview-map')
    a.ok('没有题目位置却留着题库文件：非零退出', code3 != 0, f'exit={code3}')
    a.has(out3, f'{stale}:1', '没有任何 ::: quiz 题目位置', label='报错指到题库文件并说清原因')
    a.ok('这条报错时也不写盘', not os.path.exists(path3))

    os.remove(stale)                                   # 说明页那种「本来就不交题库」的状态
    code4, _, text4, path4 = render(subject2, 1, 'overview-map')
    a.equal('把题库文件删掉就放行（没有题目位置不要求题库）', code4, 0)
    a.hasnt(text4, 'data-quiz', label='页面上没有题目块')


# ══════════════════════════════════════════════════════════════════
# ㉒ 锚点对账（同向重复）：两个题目位置用同一个锚点，同一批题会渲染两遍
# ══════════════════════════════════════════════════════════════════

@case('重复锚点：两个题目位置用同一个锚点 → 报错指到第二个题目位置；不写盘')
def _(a):
    subject = new_subject()
    second = '::: quiz 应用 锚点：锚点A'
    md = fixtures.write_content(subject, 1, 'overview-map', body='''## 边界

::: quiz 理解 锚点：锚点A
:::

换个层级再问一次：

''' + second + '''
''')
    fixtures.write_quiz(subject, 1, 'overview-map', {'锚点A': QUIZ_BOUNDARY})
    code, out, text, path = render(subject, 1, 'overview-map')
    a.ok('重复锚点非零退出', code != 0, f'exit={code}')
    a.has(out, f'{md}:{line_of(md, second)}', label='报错指到第二个题目位置那一行')
    a.has(out, '锚点A', '重复', label='报错说清是同一个锚点被用了两次')
    a.ok('重复锚点报错时不写盘', not os.path.exists(path))

    # 两个题目位置各用各的锚点就放行：两块都要在页面上（每块一份自己的题）
    subject2 = new_subject()
    fixtures.write_content(subject2, 1, 'overview-map', body='''## 边界

::: quiz 理解 锚点：锚点A
:::

再问一道：

::: quiz 应用 锚点：锚点B
:::
''')
    fixtures.write_quiz(subject2, 1, 'overview-map',
                        {'锚点A': QUIZ_BOUNDARY, '锚点B': QUIZ_BOUNDARY})
    code2, out2, text2, path2 = render(subject2, 1, 'overview-map')
    a.equal('两个不同锚点放行', code2, 0)
    a.equal('两道题各出一块', text2.count('<div class="quiz" data-quiz='), 2)


# ══════════════════════════════════════════════════════════════════
# ㉓ 用法错误退 2；坏题库的三种形态都要响（不是 JSON / 不是对象 / 值是空数组）
# ══════════════════════════════════════════════════════════════════

@case('用法错误退 2（缺参/多参/未知参数；--help 退 0）；坏题库三种形态都非零退出')
def _(a):
    code, out = run_raw()
    a.equal('不给参数退 2', code, 2)
    a.has(out, '用法错误', '用法：python3 scripts/render_lesson.py', label='用法错误时打印用法')

    code, out = run_raw('某个科目目录')
    a.equal('只给一个参数退 2', code, 2)
    a.has(out, '用法错误', label='缺参数也算用法错误')

    code, out = run_raw('--nope', 'a', 'b')
    a.equal('未知参数退 2', code, 2)
    a.has(out, '未知参数 --nope', label='未知参数点名')

    code, out = run_raw('--help')
    a.equal('--help 退 0', code, 0)
    a.has(out, '用法：', 'python3 scripts/render_lesson.py <科目目录> <节点id> [--check]',
          label='--help 打印用法（文档字符串）')

    subject = new_subject()
    fixtures.write_content(subject, 1, 'overview-map',
                           body='## 边界\n\n::: quiz 理解 锚点：锚点A\n:::\n')
    quiz_path = os.path.splitext(fixtures.lesson_md(subject, 1, 'overview-map'))[0] + '.quiz.json'
    for label, payload, expect in (
            ('不是合法 JSON', '这不是 JSON', '不是合法 JSON'),
            ('最外层不是对象', '[]', '最外层是对象'),
            ('锚点的值是空数组', '{"锚点A": []}', '值应是非空的题目数组')):
        with open(quiz_path, 'w', encoding='utf-8') as handle:
            handle.write(payload)
        code, out, text, path = render(subject, 1, 'overview-map')
        a.ok(f'{label}：非零退出', code != 0, f'exit={code}')
        a.has(out, f'{quiz_path}:', label=f'{label}：报错指到题库文件')
        a.has(out, expect, label=f'{label}：报错说清原因')
        a.ok(f'{label}：报错时不写盘', not os.path.exists(path))


# ══════════════════════════════════════════════════════════════════
# ㉔ R12：`kind: 实验` 的说明页（任务书、不出题、没有 .quiz.json）也走渲染器并过检查
# ══════════════════════════════════════════════════════════════════

@case('kind: 实验 说明页：没有题库文件也渲染，且过检查 OK（R12 路径）')
def _(a):
    subject = new_subject(nodes=[('overview-map', '概念', '全景地图'),
                                 ('first-lab', '实验', '第一个实验')])
    # 检查对 `kind: 实验` 的课要求 lab 产物齐全：lab/<编号>-*/ 有任务文件 + lab/solutions/ 非空
    lab_dir = os.path.join(subject, 'lab', '0002-first-lab')
    os.makedirs(lab_dir, exist_ok=True)
    with open(os.path.join(lab_dir, 'README.md'), 'w', encoding='utf-8') as handle:
        handle.write('# 第一个实验\n\n任务：按三步把过程写下来。\n')
    solutions = os.path.join(subject, 'lab', 'solutions')
    os.makedirs(solutions, exist_ok=True)
    with open(os.path.join(solutions, 'main.cpp'), 'w', encoding='utf-8') as handle:
        handle.write('int main() { return 0; }\n')

    fixtures.write_content(subject, 1, 'overview-map', body='## 正文\n\n一段话。\n')
    render(subject, 1, 'overview-map')                 # 检查按同目录编号判跳号，0001 要在
    md = fixtures.write_content(subject, 2, 'first-lab', body='''## 任务书

先读 [实验任务书](../lab/0002-first-lab/README.md)，按里面的三步做。

::: tip 留白态
`solutions/` 里的参考解不是给你看的。
:::
''')
    quiz_path = os.path.splitext(md)[0] + '.quiz.json'
    a.ok('实验说明页没有题目位置（不出题）',
         '::: quiz' not in open(md, encoding='utf-8').read())
    code, out, text, path = render(subject, 2, 'first-lab')
    a.equal('没有 .quiz.json 也渲染成功', code, 0)
    a.ok('渲染器没有去要题库文件', not os.path.exists(quiz_path))
    a.has(text, '<h1>第一个实验</h1>',
          '<a href="../lab/0002-first-lab/README.md">实验任务书</a>',
          '<div class="lesson-tip">', label='说明页渲染出正文与 lab 链接')
    a.hasnt(text, 'class="quiz"', label='说明页里没有题目块')
    gate_code, gate_out = fixtures.run_gate(path, subject, 'first-lab')
    a.equal('实验说明页过检查', gate_code, 0)
    a.has(gate_out, f'OK   {path}', label='检查回 OK')


# ══════════════════════════════════════════════════════════════════
# ㉕ 加名字的硬边界：名单里每个名字都必须被形状正则捕获；连字符名捕不到（只能做 ::: 指令）
# ══════════════════════════════════════════════════════════════════

@case('名单与形状正则对得上（连字符名捕不到）＋文档写明了这条边界')
def _(a):
    unmatched = [name for name in sorted(render_lesson.HTML_TAG_NAMES)
                 if not render_lesson.HTML_TAG_RE.match(f'<{name}>')
                 or not render_lesson.TAG_SHAPE_RE.search(f'<{name}>')]
    a.ok('名单里每个名字都被两个形状正则捕获（加进来的名字必须捕得到）', not unmatched,
         f'这些名字正则捕不到：{unmatched}')
    a.ok('名单里没有连字符名（形状正则的名字部分不含连字符）',
         not [name for name in render_lesson.HTML_TAG_NAMES if '-' in name])
    a.ok('连字符自定义元素的完整名字捕不到（「往名单里加名字」对它无效）',
         render_lesson.HTML_TAG_RE.match('<syo-editor>').group(1) == 'syo'
         and render_lesson.TAG_SHAPE_RE.search('<syo-editor>') is None)

    doc_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), 'docs', '课件内容格式.md')
    doc = open(doc_path, encoding='utf-8').read()
    a.has(doc, '不含连字符', 'syo-editor', 'MathML',
          label='格式文档写明连字符与 MathML 两条边界')

    # 行为侧再钉一次：连字符名是普通文字（按文档是已知边界），换成标准标签就拦
    subject = new_subject()
    fixtures.write_content(subject, 1, 'overview-map',
                           body='## 组件\n\n这段里写了 <syo-editor> 组件。\n')
    code, out, text, path = render(subject, 1, 'overview-map')
    a.equal('<syo-editor> 当普通文字放行（连字符名不进判据）', code, 0)
    a.has(text, '<p>这段里写了 &lt;syo-editor&gt; 组件。</p>', label='按字面量转义出厂')


def main():
    failures = 0
    for label, fn in CASES:
        a = Asserts()
        try:
            fn(a)
        except Exception as exc:                                   # 用例自己崩了也要报出来
            a.failures.append(f'用例抛异常：{exc!r}')
        failures += bool(a.failures)
        fixtures.check(label, not a.failures, '；'.join(a.failures))
    total = len(CASES)
    print(f'\n{total - failures}/{total} 通过')
    shutil.rmtree(TMP, ignore_errors=True)
    return 1 if failures else 0

if __name__ == '__main__':
    sys.exit(main())
