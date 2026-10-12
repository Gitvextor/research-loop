#!/usr/bin/env python3
"""课件渲染器：内容文件 + 题库 + 大纲 → 课件 HTML（模型不再写 HTML）。

用法：
    python3 scripts/render_lesson.py <科目目录> <节点id> [--check]

读：
    <科目>/curriculum.yaml                        节点位次（决定文件名序号）/title/前后邻居
    <科目>/lessons/<序号>-<节点id>.md              内容文件（格式见 docs/课件内容格式.md）
    <科目>/lessons/<序号>-<节点id>.quiz.json       题库（有 `::: quiz` 时才要；按锚点组织）
    <科目>/assets/img/pool.md                      图片池索引（题注的来源/许可从这里取）
    <科目>/subject.yaml                            科目名（顶栏与 <title>；缺文件退回目录名）
写：
    <科目>/lessons/<序号>-<节点id>.html            渲染产物（`--check` 时只解析校验、不写盘）

退出码：0 通过；1 有问题（逐条打印 `<文件>:<行> <问题>` 到 stderr）；用法错误 2。

**成功（退出码 0）时 stderr 上仍可能有 `提示:` 开头的行**（标题超过 16 字、锚点按 `empty_reason`
跳过这类软提醒）——它们不代表失败，退出码只看有没有 `<文件>:<行>` 的问题行。

一条铁律：**认不出就报错**。未知指令、认不出的块语法、手写 HTML（含段落中间的标签形状）、锚点在
题库里没有题又没写 `empty_reason:`、题库里多出来的锚点（没有题目位置引用它）、没有题目位置却留着题库
文件、同一个锚点被两个题目位置引用、front matter 的 `title` 与 `curriculum.yaml` 里该节点的 `title`
不一致、配图文件不存在、模板缺占位符——全部带行号报错，绝不静默降级或
丢内容。渲染器自己产出模型不该写的部分：head 与共享层引用、顶栏与主题开关、页头 eyebrow
（`序号 · 标题`）、提问提示、按 curriculum.yaml 算的上/下节课指针、页脚、三个 `<script>` 与
`LearnTheme.wire(...)`。交付页面从 `<!DOCTYPE html>` 开始：模板里给维护者看的说明注释留在
`<!DOCTYPE` 之前，不进产物。

内容格式的完整语法表、反例与「什么不该写」见 docs/课件内容格式.md（本文件的错误信息与之对应）。
依赖：标准库 + pyyaml（与 check_lesson.py / gen_home.py 同口径，不引第三方新依赖）。
"""
import json
import os
import re
import sys
from urllib.parse import unquote

try:
    import yaml
except ImportError:                                   # pragma: no cover - 环境缺 pyyaml
    yaml = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, 'templates', 'lesson.html')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_home                                        # noqa: E402  占位符替换口径与它一致

USAGE = '用法：python3 scripts/render_lesson.py <科目目录> <节点id> [--check]'

# 模板占位符：名字 → 应出现次数（TITLE 在 <title> 与 <h1>；SUBJECT 在 <title> 与顶栏）
TEMPLATE_PLACEHOLDERS = {
    'TITLE': 2, 'SUBJECT': 2, 'NUMBER': 1, 'EYEBROW': 1, 'GOAL': 1, 'BODY': 1, 'NAV': 1, 'FOOTER': 1,
    'MATH': 1,
}
PLACEHOLDER = '<!-- @LEARN:{} -->'

# 数学式：行内 `$…$`、块级 `$$…$$`（整段就是它）。作者写 TeX，渲染器只包成占位元素，
# 排版在浏览器里由离线 KaTeX（共享层 templates/assets/katex/ + lesson-math.js）完成。
# **有数学式的页面才注入这三个引用**：老课件与非数学课因此零改动、零 diff。
MATH_REFS = ('katex/katex.min.css', 'katex/katex.min.js', 'lesson-math.js')
BLOCK_MATH_RE = re.compile(r'^\$\$(.+)\$\$$', re.S)
# 题库里的行内公式（够用的近似：两个 $ 之间首尾非空白、不跨行）
MATH_PAIR_RE = re.compile(r'\$[^\s$][^$\n]*[^\s$]\$|\$[^\s$]\$')

# 块级词汇：`:::` 指令名（其余一律报错）
# 图注编号（`::: figure` / `::: svg` 的 `caption:`）：作者只写描述，编号由渲染器按页内顺序给。
# 旧课件里手写的「图 N ·」会被剥掉重编——所以重渲染是幂等的，老写法不改也不会重号。
CAPTION_NUMBER_RE = re.compile(r'^图\s*\d+\s*·\s*')

DIRECTIVES = ('practice', 'quiz', 'figure', 'svg', 'tip', 'warn', 'note', 'resources', 'related')
CONTAINER_DIRECTIVES = ('practice', 'tip', 'warn', 'note')          # 块里还能写普通块
CARD_CLASS = {'tip': 'lesson-tip', 'warn': 'lesson-warn', 'note': 'lesson-note'}

UL_RE = re.compile(r'^- (\S.*)$')
ORDERED_RE = re.compile(r'^\d+\. (\S.*)$')
DIRECTIVE_RE = re.compile(r'^:::\s*([a-zA-Z][a-zA-Z0-9_-]*)\s*(.*)$')
FIELD_RE = re.compile(r'^([a-z_]+):\s*(.*)$')
LINK_ITEM_RE = re.compile(r'^-\s*\[([^\]]+)\]\(([^)\s]+)\)\s*(?:\|\s*(.*))?$')
PLAIN_ITEM_RE = re.compile(r'^-\s*([^|]+?)\s*(?:\|\s*(.*))?$')
LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)\s]*)\)')
HEADING_RE = re.compile(r'^(#{1,6})\s*(.*)$')
HTML_TAG_RE = re.compile(r'^</?([a-zA-Z][a-zA-Z0-9]*)\b')
# 散文里的标签形状 HTML（`<b>粗</b>`、`</div>`、`<img src=…>`）。判据两条（缺一不可）：
#   · `<` 前面不是 ASCII 字母/数字——`n<m`、`a<b>c`、`std::vector<int>` 是运算符/泛型，不是标签；
#   · 名字在真标签白名单里——`<T>`、`<m>` 这类泛型/变量名不是标签。
# 名单只收引擎自己的组件与语料真会用到的 HTML 标签，所以 `2 < n`、`x > 0`、`<T>` 照常放行。
TAG_SHAPE_RE = re.compile(r'</?([a-zA-Z][a-zA-Z0-9]*)(?:\s[^<>]*)?/?>')
ASCII_WORD_RE = re.compile(r'[0-9A-Za-z]')
SEPARATOR_CELL_RE = re.compile(r'^:?-{3,}:?$')
SCHEME_RE = re.compile(r'^(?:[A-Za-z][A-Za-z0-9+.\-]*:|//)')
TITLE_SOFT_LIMIT = 16                                  # 节点标题建议 ≤16 字（超了只提示）
HTML_COMMENT_RE = re.compile(r'<!--.*?-->', re.S)      # 模板注释（定位 DOCTYPE 时要先遮掉）
HTML_COMMENT_OPEN = '<!--'                             # 内容文件里的注释（手写时代的标记写法）
# 段内换行要不要补空格：两侧都是中日韩文字与全角标点就直接相接（中文不用空格分词）
CJK_RE = re.compile(r'[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]')

# ── 「什么算 HTML 标签」的唯一名单 ───────────────────────────────────────────
# 这是**唯一来源**：行首检查（html_block_tag）与行内检查（tag_shape_at）都查它，
# 名单之外的写法一律当普通文字（`<T>` 泛型、`n<m` 运算符）。
# 约定：**名单一律小写**；查表前把捕获到的名字 `.lower()`（HTML 标签名本来就不区分大小写）。
# 扩展词汇（例如以后加新组件标签）时，**必须同步往这里加名字**，否则那个标签会被当普通文字
# 放行——docs/课件内容格式.md §2 列的是同一份名单（测试会断言两边逐字一致）。
#
# **但加名字有硬边界**：两个形状正则（HTML_TAG_RE / TAG_SHAPE_RE）捕获的名字都是
# `[a-zA-Z][a-zA-Z0-9]*`——**不含连字符**。所以 `<syo-editor>` 这类连字符自定义元素，往这份名单里
# 加多少名字都匹配不上（行首检查的 HTML_TAG_RE 只截到连字符前的 `syo`，行内检查的 TAG_SHAPE_RE
# 干脆不匹配），照旧被当字面量放行（静默出厂）。这类组件只能走 docs/课件内容格式.md
# §7「已知边界」给的那条路：**做成 `:::` 指令**（渲染器 + 测试 + 文档），不在这份名单里加名字。
# 同理，这份名单收的是**元素名**（标准 HTML 元素 + SVG 元素名）：MathML 的内层元素名
# （`<mrow>`、`<mi>`、`<msqrt>` 这类）不在里面，写进正文会被当普通文字放行——要排数学式
# 就用 `::: svg`（或纯文本），别指望名单兜住。
#
# 范围（**完整**，不是「常用」子集——子集的承诺是假的：模型随手写一个 `<iframe>` 就会
# 当字面量出厂）：标准 HTML 元素全表（HTML living standard 的每一个元素，含 aside/video/form
# 这类正文元素与 center/font/marquee 这类旧式、表现型、已废弃元素）+ SVG 元素名。
# 多词驼峰的 SVG 名字（clipPath、linearGradient、feGaussianBlur…）按小写收：查表前 `.lower()`，
# 所以 `<clipPath>` 会被判成 `clippath` 命中。
# 判据只在这个名单 + `tag_shape_at` 的两条形状规则上，`<T>`、`n<m`、`std::vector<int>` 照常放行。
HTML_TAG_NAMES = frozenset('''
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


class Problems:
    """收集问题：每条都是 `文件:行 问题`，一次跑完把所有问题都报出来（同样的一条只报一次）。"""

    def __init__(self):
        self.items = []
        self._seen = set()

    def add(self, path, line, message):
        item = (path, max(int(line or 1), 1), message)
        if item in self._seen:                          # 同一处在不同层级被查到时不重复报
            return
        self._seen.add(item)
        self.items.append(item)

    def __bool__(self):
        return bool(self.items)

    def report(self):
        for path, line, message in self.items:
            print(f'{path}:{line} {message}', file=sys.stderr)


def note(message):
    """提示（不影响退出码）：只往 stderr 打一行，别混进产物。"""
    print(f'提示: {message}', file=sys.stderr)


def read_text(path, problems, what):
    """严格 UTF-8 读；读不出来记一条问题并返回 None。"""
    try:
        with open(path, encoding='utf-8') as handle:
            return handle.read()
    except UnicodeDecodeError as exc:
        problems.add(path, 1, f'{what} 不是 UTF-8 编码（{exc.reason}）')
    except OSError as exc:
        problems.add(path, 1, f'读不出{what}：{exc.strerror or exc}')
    return None


def line_of(text, needle):
    """needle 在文本里的行号（1 起）；找不到给 1。"""
    index = text.find(needle)
    return text.count('\n', 0, index) + 1 if index >= 0 else 1


# ══════════════════════════════════════════════════════════════════
# 大纲：curriculum.yaml 的 nodes（序号 / 标题 / 前后邻居）
# ══════════════════════════════════════════════════════════════════

class Outline:
    """`nodes:` 的顺序就是课件编号与上/下节课指针的唯一来源（与 check_lesson.py 同口径）。"""

    def __init__(self, path, nodes):
        self.path = path
        self.ids = [node['id'] for node in nodes]
        self.titles = {node['id']: node['title'] for node in nodes}

    def index_of(self, node_id):
        """节点在 `nodes:` 里的位次（1 起）；不在大纲里返回 None。"""
        try:
            return self.ids.index(node_id) + 1
        except ValueError:
            return None

    def title_of(self, node_id):
        return self.titles.get(node_id) or node_id

    def neighbors(self, index):
        """(上一个节点 id, 下一个节点 id)——到头的那个是 None；index 从 1 起。"""
        prev_id = self.ids[index - 2] if index >= 2 else None
        next_id = self.ids[index] if index < len(self.ids) else None
        return prev_id, next_id


def load_outline(subject_dir, problems):
    path = os.path.join(subject_dir, 'curriculum.yaml')
    if yaml is None:                                   # pragma: no cover - 环境缺 pyyaml
        problems.add(path, 1, '读不了 curriculum.yaml：需要 pyyaml（python3 -m pip install pyyaml）')
        return None
    if not os.path.isfile(path):
        problems.add(path, 1, '找不到大纲文件（科目目录里应有 curriculum.yaml）')
        return None
    raw = read_text(path, problems, '大纲文件')
    if raw is None:
        return None
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        mark = getattr(exc, 'problem_mark', None)
        problems.add(path, getattr(mark, 'line', 0) + 1, f'大纲不是合法 YAML：{exc}')
        return None
    nodes = data.get('nodes') if isinstance(data, dict) else None
    if not isinstance(nodes, list):
        problems.add(path, 1, '大纲的 nodes 必须是节点数组')
        return None
    rows = []
    seen = set()
    for position, node in enumerate(nodes, 1):
        node_id = node.get('id') if isinstance(node, dict) else None
        if not isinstance(node_id, str) or not re.fullmatch(r'[a-z0-9]+([.-][a-z0-9]+)*', node_id):
            problems.add(path, 1, f'nodes 第 {position} 项缺少合法的节点 id（小写字母数字，以点或短横线分段）')
            return None
        if node_id in seen:
            problems.add(path, 1, f'大纲里有重复 id: {node_id}（课件编号无法唯一确定）')
            return None
        seen.add(node_id)
        rows.append({'id': node_id, 'title': str(node.get('title') or node_id)})
    if not rows:
        problems.add(path, 1, '大纲里没有 nodes:（课件编号与上下节课指针都按它算）')
        return None
    return Outline(path, rows)


def load_subject_name(subject_dir):
    """科目名：`subject.yaml` 的 name，缺文件/读不出来就退回目录名（顶栏与 <title> 要它）。"""
    path = os.path.join(subject_dir, 'subject.yaml')
    if os.path.isfile(path) and yaml is not None:
        try:
            with open(path, encoding='utf-8') as handle:
                data = yaml.safe_load(handle)
            if isinstance(data, dict) and data.get('name'):
                return str(data['name'])
        except (yaml.YAMLError, OSError, UnicodeDecodeError):
            pass
    return os.path.basename(os.path.normpath(subject_dir)) or '学习科目'


# ══════════════════════════════════════════════════════════════════
# 内容文件：front matter + 块级解析
# ══════════════════════════════════════════════════════════════════

FRONT_KEYS = ('title', 'goal')


def parse_front_matter(path, lines, problems):
    """读 front matter（`---` 起止，title/goal 必填）；返回 (字段, 正文起始行下标, 字段行号)。"""
    if not lines or lines[0].strip().lstrip('\ufeff') != '---':
        problems.add(path, 1, '内容文件要以 front matter 开头（第一行 ---，里面写 title 与 goal）')
        return {}, 0, {}
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == '---':
            end = index
            break
    if end is None:
        problems.add(path, 1, 'front matter 没有结束的 --- 行')
        return {}, 0, {}
    fields, field_lines = {}, {}
    for index in range(1, end):
        raw = lines[index]
        if not raw.strip():
            continue
        if ':' not in raw:
            problems.add(path, index + 1, f'front matter 的字段写成 key: value（认不出：{raw.strip()}）')
            continue
        key, _, value = raw.partition(':')
        key, value = key.strip(), value.strip()
        if key not in FRONT_KEYS:
            problems.add(path, index + 1, f'front matter 不认识的字段 {key}（只有 title 与 goal）')
            continue
        if not value:
            problems.add(path, index + 1, f'front matter 的 {key} 不能为空')
            continue
        fields[key], field_lines[key] = value, index + 1
    for key in FRONT_KEYS:
        if key not in fields:
            problems.add(path, end + 1, f'front matter 缺 {key}')
    if 'title' in fields and len(fields['title']) > TITLE_SOFT_LIMIT:
        note(f'{path}:{field_lines["title"]} 标题 {len(fields["title"])} 字 > {TITLE_SOFT_LIMIT}'
             '（页头与 <title> 都用它，长了会换行）')
    return fields, end + 1, field_lines


def check_title_match(path, node_id, front, front_lines, outline, problems):
    """这节课叫什么只有一个答案：front matter 的 `title` = `curriculum.yaml` 该节点的 `title`（逐字）。

    页面 `<title>`／`<h1>`／eyebrow 用 front matter 的，主页卡片与路线图用大纲的——不一致就是同一节课
    挂了两个名字。行号指向 front matter 的 title 行（规则见 docs/课件内容格式.md 第 1 节）。
    """
    title = front.get('title')
    if not title:                                  # 缺 title 由 parse_front_matter 报过，这里不再重复
        return
    outline_title = outline.title_of(node_id)
    if title != outline_title:
        problems.add(path, front_lines.get('title', 1),
                     f'front matter 的 title「{title}」与 curriculum.yaml 里节点 {node_id} 的 '
                     f'title「{outline_title}」不一致——两处必须逐字一致（改这里或改大纲，'
                     '见 docs/课件内容格式.md 第 1 节）')


def html_block_tag(stripped):
    """行首是**真 HTML 标签**时返回标签名，否则 None（与行内检查同查 `HTML_TAG_NAMES`）。"""
    tag = HTML_TAG_RE.match(stripped)
    if tag and tag.group(1).lower() in HTML_TAG_NAMES:
        return tag.group(1)
    return None


def is_html_block(stripped):
    """行首是真 HTML 标签（内容文件里出现就是「模型在写 HTML」）。"""
    return html_block_tag(stripped) is not None


def mask_comments(text):
    """把 HTML 注释换成**等长空格**：只用于「按位置判断」，下标与原文本一一对应。

    模板定位 `<!DOCTYPE`、`::: svg` 找 `</svg>` 收尾都要它——注释里提到的标签不算数。
    """
    return HTML_COMMENT_RE.sub(lambda match: ' ' * len(match.group(0)), text)


def is_block_start(stripped):
    """这一行会不会开启一个新的块（段落遇到它就结束）。"""
    return bool(stripped.startswith(('#', '```', ':::', '|', '>', '* ', '+ ', '---'))
                or UL_RE.match(stripped) or ORDERED_RE.match(stripped)
                or is_html_block(stripped) or stripped.startswith('<!--'))


def code_span_end(text, start):
    """`text[start]` 是反引号时返回配对的收尾反引号下标；落单（或内容为空）返回 None。

    **code span 的唯一判定**：`inline()` 与行内 HTML 检查都走这个函数。落单的反引号是普通字符、
    不开启 code 区——这条规则只写一份，免得两处漂移（曾经用「反引号奇偶」判定，于是段落里
    一个落单的反引号就把后面的 `<b>` 全遮住了）。
    """
    close = text.find('`', start + 1)
    return close if close > start + 1 else None


def math_close(text, index):
    """`text[index]` 是 `$` 时返回配对收尾 `$` 的下标；不成立返回 None。

    判据（避开散文里的美元号）：开 `$` 后面紧跟非空白、收 `$` 前面也是非空白、中间非空且不跨行。
    与 `code_span_end` 一样，这是行内公式的**唯一判定**：`inline()` 与「没有收尾」的报错共用它。
    """
    if index + 1 >= len(text) or text[index + 1].isspace():
        return None
    close = text.find('$', index + 1)
    if close <= index + 1 or text[close - 1].isspace() or text[close - 1] == '\\':
        return None
    if '\n' in text[index + 1:close]:
        return None
    return close


def tag_shape_at(text, index):
    """`text[index] == '<'`；是**真标签**就返回标签原文，否则 None（判据见 TAG_SHAPE_RE 注释）。"""
    if index > 0 and ASCII_WORD_RE.match(text[index - 1]):
        return None
    match = TAG_SHAPE_RE.match(text, index)
    if not match or match.group(1).lower() not in HTML_TAG_NAMES:
        return None
    return match.group(0)


def join_paragraph(parts):
    """段内换行：两侧都是中文就直接相接，否则按一个空格接（英文单词之间要空格）。"""
    text = parts[0]
    for part in parts[1:]:
        gap = '' if CJK_RE.search(text[-1]) and CJK_RE.search(part[0]) else ' '
        text += gap + part
    return text


def split_cells(row):
    """管道表一行 → 单元格（`\\|` 是转义的字面竖线）。"""
    text = row.strip()
    if text.startswith('|'):
        text = text[1:]
    if text.endswith('|') and not text.endswith('\\|'):
        text = text[:-1]
    cells, buf, index = [], [], 0
    while index < len(text):
        char = text[index]
        if char == '\\' and index + 1 < len(text) and text[index + 1] == '|':
            buf.append('|')
            index += 2
            continue
        if char == '|':
            cells.append(''.join(buf).strip())
            buf = []
            index += 1
            continue
        buf.append(char)
        index += 1
    cells.append(''.join(buf).strip())
    return cells


def parse_blocks(path, lines, start, end, problems):
    """把 [start, end) 行解析成块列表；认不出的语法带行号报错，不猜。"""
    blocks = []
    index = start
    while index < end:
        raw = lines[index]
        stripped = raw.strip()
        line_no = index + 1
        if not stripped:
            index += 1
            continue
        if raw[:1] in (' ', '\t'):                     # 缩进只属于列表嵌套
            problems.add(path, line_no, '块级内容顶格写（只有列表嵌套才缩进 2 空格）')
            index += 1
            continue

        heading = HEADING_RE.match(stripped)
        if heading:
            level = len(heading.group(1))
            if level < 2:
                # 一级标题没有对应组件；重点是把「行首 # 就是标题」这件事说清楚——
                # 竞赛正文里 `#include <cstdio>`、`#define N 100` 出现在行首太常见了
                problems.add(path, line_no,
                             f'这一行被当成一级标题（{stripped[:24]}…）：内容格式只有 ## 与 ###。'
                             '如果这是代码（#include / #define 这类），请放进 ``` 围栏；'
                             '要分节就写 ## 标题')
            elif level > 3:
                problems.add(path, line_no, '标题只支持 ## 与 ###（四级及以下没有组件）')
            elif not heading.group(2).strip():
                problems.add(path, line_no, f'{"#" * level} 后面要写标题文字')
            else:
                blocks.append({'kind': f'h{level}', 'text': heading.group(2).strip(), 'line': line_no})
            index += 1
            continue

        if stripped.startswith('```'):
            block, index = parse_fence(path, lines, index, end, problems)
            if block:
                blocks.append(block)
            continue

        if stripped.startswith(':::'):
            block, index = parse_directive(path, lines, index, end, problems)
            if block:
                blocks.append(block)
            continue

        if UL_RE.match(stripped) or ORDERED_RE.match(stripped):
            block, index = parse_list(path, lines, index, end, problems)
            blocks.append(block)
            continue

        if stripped.startswith('|'):
            block, index = parse_table(path, lines, index, end, problems)
            if block:
                blocks.append(block)
            continue

        if stripped in ('---', '***', '___'):
            problems.add(path, line_no, '内容格式没有分隔线：要分节就写 ## 标题')
            index += 1
            continue

        if stripped.startswith('>') or stripped.startswith('* ') or stripped.startswith('+ '):
            problems.add(path, line_no, '认不出的块语法：无序列表写 `- 项`，引用块本格式不支持')
            index += 1
            continue

        tag = html_block_tag(stripped)
        if tag:
            problems.add(path, line_no, f'内容文件不写 HTML（读到 <{tag}>）：'
                                        '用内容格式的块与行内语法，HTML 由渲染器产出')
            index += 1
            continue
        if stripped.startswith('<!--'):
            problems.add(path, line_no, '内容文件不写 HTML 注释：要留话就给出题角色或写进正文')
            index += 1
            continue

        # 段落：吃到空行或下一个块的开始
        paragraph = [stripped]
        index += 1
        while index < end:
            follow = lines[index]
            if not follow.strip() or is_block_start(follow.strip()) or follow[:1] in (' ', '\t'):
                break
            paragraph.append(follow.strip())
            index += 1
        blocks.append({'kind': 'p', 'text': join_paragraph(paragraph), 'line': line_no})
    return blocks


def parse_fence(path, lines, index, end, problems):
    """``` 围栏 → 代码块（块内原文逐字保留）。"""
    language = lines[index].strip()[3:].strip()
    body, cursor = [], index + 1
    while cursor < end and not lines[cursor].strip().startswith('```'):
        body.append(lines[cursor])
        cursor += 1
    if cursor >= end:
        problems.add(path, index + 1, '代码围栏没有闭合（块尾补一行 ```）')
        return None, end
    return {'kind': 'code', 'lang': language, 'text': '\n'.join(body), 'line': index + 1}, cursor + 1


def parse_list(path, lines, index, end, problems, indent=0):
    """列表 → 一层 items；缩进 2 格的行是上一层最后一项的子列表。"""
    ordered = bool(ORDERED_RE.match(lines[index].strip()))
    marker = ORDERED_RE if ordered else UL_RE
    items, line_no = [], index + 1
    while index < end:
        raw = lines[index]
        stripped = raw.strip()
        if not stripped:
            break
        lead = len(raw) - len(raw.lstrip(' '))
        if lead < indent:
            break
        if lead > indent:
            problems.add(path, index + 1, f'列表嵌套只缩进 2 空格（这一行缩进了 {lead} 格）')
            index += 1
            continue
        match = marker.match(stripped)
        if not match:
            break
        item = {'text': match.group(1), 'children': None, 'line': index + 1}
        index += 1
        if index < end:
            follow = lines[index]
            follow_lead = len(follow) - len(follow.lstrip(' '))
            if (follow.strip() and follow_lead == indent + 2
                    and (UL_RE.match(follow.strip()) or ORDERED_RE.match(follow.strip()))):
                child, index = parse_list(path, lines, index, end, problems, indent + 2)
                item['children'] = child
        items.append(item)
    return {'kind': 'ol' if ordered else 'ul', 'items': items, 'line': line_no}, index


def parse_table(path, lines, index, end, problems):
    """管道表：第二行必须是分隔行（格子数与表头一致、每格都是 `---` 形状）；各行列数也要一致。"""
    rows, cursor = [], index
    while cursor < end and lines[cursor].strip().startswith('|'):
        rows.append(lines[cursor])
        cursor += 1
    line_no = index + 1
    if len(rows) < 2:
        problems.add(path, line_no, '表格第二行必须是分隔行（| --- | --- |），第一行是表头')
        return None, cursor
    header = split_cells(rows[0])
    separator = split_cells(rows[1])
    if len(separator) != len(header):
        problems.add(path, line_no + 1,
                     f'表格分隔行有 {len(separator)} 格，表头是 {len(header)} 格——'
                     '两行的格子数必须一样（如 `| --- | --- |`）')
        return None, cursor
    bad = [cell for cell in separator if not SEPARATOR_CELL_RE.match(cell)]
    if bad:
        shown = '、'.join('空的一格' if cell == '' else repr(cell) for cell in bad)
        problems.add(path, line_no + 1,
                     f'表格分隔行的每一格都要写成 ---（现在是 {shown}）——'
                     '这一行只标明哪几列，不写内容')
        return None, cursor
    body = []
    for offset, row in enumerate(rows[2:], start=2):
        cells = split_cells(row)
        if len(cells) != len(header):
            problems.add(path, line_no + offset,
                         f'表格这一行有 {len(cells)} 格，表头是 {len(header)} 格'
                         '（单元格里的竖线写成 \\|）')
            continue
        body.append(cells)
    return {'kind': 'table', 'header': header, 'rows': body, 'line': line_no}, cursor


def parse_directive(path, lines, index, end, problems):
    """`::: <名字> [参数]` … `:::` —— 认不出的名字/写法都带行号报错。"""
    stripped = lines[index].strip()
    line_no = index + 1
    if stripped == ':::':
        problems.add(path, line_no, '多出来的 :::（没有对应的指令开始）')
        return None, index + 1
    match = DIRECTIVE_RE.match(stripped)
    if not match:
        problems.add(path, line_no, '指令写法是 ::: <名字> [参数]（这一行认不出）')
        return None, index + 1
    name, args = match.group(1), match.group(2).strip()
    known = name in DIRECTIVES
    if not known:
        problems.add(path, line_no,
                     f'未知指令 ::: {name}（可用：{"、".join(DIRECTIVES)}）')

    cursor = index + 1
    nested = False
    in_fence = False                                    # 围栏里的 ::: 是代码文本，不是指令边界
    while cursor < end:
        text = lines[cursor].strip()
        if text.startswith('```'):
            in_fence = not in_fence
            cursor += 1
            continue
        if not in_fence:
            if text == ':::':
                break
            if not nested and DIRECTIVE_RE.match(text):
                problems.add(path, cursor + 1, f'指令块不能嵌套（::: {name} 里又开了一个指令）——'
                                               '把一个块拆成两个平级的块')
                nested = True
        cursor += 1
    if cursor >= end:
        problems.add(path, line_no, f'指令 ::: {name} 没有闭合（块尾补一行 :::）')
        body_end, next_index = end, end
    else:
        body_end, next_index = cursor, cursor + 1
    if not known:
        return None, next_index

    if name != 'quiz':
        reject_stray_empty_reason(path, name, lines, index + 1, body_end, problems)

    if name in CONTAINER_DIRECTIVES:
        body = parse_blocks(path, lines, index + 1, body_end, problems)
        if name == 'practice':
            return build_practice(path, args, body, line_no, problems), next_index
        return {'kind': 'directive', 'name': name, 'title': args, 'body': body, 'line': line_no}, next_index

    if name == 'quiz':
        return build_quiz(path, args, lines, index + 1, body_end, line_no, problems), next_index
    if name == 'figure':
        return build_figure(path, args, lines, index + 1, body_end, line_no, problems), next_index
    if name == 'svg':
        return build_svg(path, args, lines, index + 1, body_end, line_no, problems), next_index
    return build_links(path, name, lines, index + 1, body_end, line_no, problems), next_index


def reject_stray_empty_reason(path, name, lines, start, end, problems):
    """`empty_reason:` 只属于 `::: quiz` 的无题锚点；别的指令块里写了就按错拦下。

    `::: practice`／`::: tip` 这类容器的块内是普通块，这一行会被当段落渲染成
    `<p>empty_reason: …</p>` 印给学生，退出码还是 0——等于把内部记号静默送出厂。
    围栏里的同名字符串是代码原文，不算。
    """
    in_fence = False
    for offset in range(start, end):
        text = lines[offset].strip()
        if text.startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        field = FIELD_RE.match(text)
        if field and field.group(1) == 'empty_reason':
            problems.add(path, offset + 1,
                         f'empty_reason: 只能出现在 ::: quiz 的块里（它给无题锚点用，'
                         f'::: {name} 没有锚点）——删掉这一行；要留题目位置就写 '
                         '::: quiz <层级> 锚点：<锚点文本>')


def build_practice(path, args, body, line_no, problems):
    """`::: practice <层级> | <标题>` → .lesson-practice + __head 里两个 span。"""
    if args.count('|') != 1:
        problems.add(path, line_no, '写法是 ::: practice <层级> | <标题>（中间一个竖线）')
        return None
    level, title = (part.strip() for part in args.split('|'))
    if not level or not title:
        problems.add(path, line_no, 'practice 的层级与标题都要写（如 ::: practice 练习 | 第 1 步 · 跑三遍）')
        return None
    return {'kind': 'directive', 'name': 'practice', 'level': level, 'title': title,
            'body': body, 'line': line_no}


def build_quiz(path, args, lines, start, end, line_no, problems):
    """`::: quiz <层级> 锚点：<文本>` + 可选 `empty_reason: <理由>`。"""
    match = re.match(r'^(.*?)锚点[：:]\s*(.+)$', args)
    if not match:
        problems.add(path, line_no, '写法是 ::: quiz <层级> 锚点：<锚点文本>（锚点要和题库的键逐字一致）')
        return None
    level, anchor = match.group(1).strip(), match.group(2).strip()
    if not level:
        problems.add(path, line_no, 'quiz 要写层级（理解/改造/排错/应用，见 layered-practice）')
        return None
    empty_reason = None
    for offset in range(start, end):
        text = lines[offset].strip()
        if not text:
            continue
        field = FIELD_RE.match(text)
        if not field or field.group(1) != 'empty_reason' or not field.group(2).strip():
            problems.add(path, offset + 1,
                         '::: quiz 的块里只写 empty_reason: <理由>（题目按锚点从 .quiz.json 取）')
            continue
        empty_reason = field.group(2).strip()
    return {'kind': 'directive', 'name': 'quiz', 'level': level, 'anchor': anchor,
            'empty_reason': empty_reason, 'line': line_no}


def build_figure(path, args, lines, start, end, line_no, problems):
    """`::: figure <相对路径>` + `alt:` + 可选 `caption:`。"""
    if not args:
        problems.add(path, line_no, '写法是 ::: figure <相对路径>（图从科目图片库 assets/img/pool/ 挑）')
        return None
    fields, field_lines = {}, {}
    for offset in range(start, end):
        text = lines[offset].strip()
        if not text:
            continue
        field = FIELD_RE.match(text)
        if not field or field.group(1) not in ('alt', 'caption'):
            problems.add(path, offset + 1, '::: figure 的块里只写 alt: 与 caption: 两行')
            continue
        fields[field.group(1)] = field.group(2).strip()
        field_lines[field.group(1)] = offset + 1
    if not fields.get('alt'):
        problems.add(path, line_no, '::: figure 缺 alt:（裂图时读屏软件与学生都只剩空白）')
    return {'kind': 'directive', 'name': 'figure', 'src': args, 'alt': fields.get('alt', ''),
            'caption': fields.get('caption', ''), 'line': line_no,
            'alt_line': field_lines.get('alt', line_no),
            'caption_line': field_lines.get('caption', line_no)}


def build_svg(path, args, lines, start, end, line_no, problems):
    """`::: svg` + 可选 `alt:`/`caption:` + 块内 SVG 原样透传。"""
    if args:
        problems.add(path, line_no, '::: svg 不带参数：说明写在块里的 alt: / caption: 两行')
    fields, raw = {}, []
    field_lines = {}
    for offset in range(start, end):
        raw_line = lines[offset]
        text = raw_line.strip()
        if not raw:
            if not text:
                continue
            field = FIELD_RE.match(text)
            if field and field.group(1) in ('alt', 'caption'):
                fields[field.group(1)] = field.group(2).strip()
                field_lines[field.group(1)] = offset + 1
                continue
            if not text.startswith('<'):
                problems.add(path, offset + 1,
                             '::: svg 的块里先写 alt:/caption:，接着是 <svg>…</svg> 原文（这一行都不是）')
                continue
        raw.append(raw_line)
    # 按**行**拼（保留换行）：拼成一行的话，`</sv` + `g>` 这种拆成两行的收尾也会被当成
    # 合法收尾放行，而页面结构照样断。多行开标签、多行自闭合 `<svg …\n/>` 保留换行也照样过。
    inline_svg = '\n'.join(raw)
    masked = mask_comments(inline_svg)                  # 注释里写的 </svg> 不算收尾
    if not re.search(r'<svg(?=[\s/>])', masked):
        problems.add(path, line_no, '::: svg 块里没有 <svg>…</svg> 原文（内联图直接贴进来）')
    elif not re.search(r'</svg\s*>', masked) and not re.search(r'<svg(?=[\s/>])[^<>]*/>', masked):
        problems.add(path, line_no, '::: svg 块里的 <svg> 没有 </svg> 收尾（原样透传前先补全，'
                                    '否则页面结构会从这里断掉；自闭合的 <svg/> 也算收尾）')
    return {'kind': 'directive', 'name': 'svg', 'alt': fields.get('alt', ''),
            'caption': fields.get('caption', ''), 'raw': '\n'.join(raw), 'line': line_no,
            'alt_line': field_lines.get('alt', line_no),
            'caption_line': field_lines.get('caption', line_no)}


def build_links(path, name, lines, start, end, line_no, problems):
    """`::: resources`（`- [标题](url) | 说明`，链接可省）与 `::: related`（`- [标题](href)`）。

    没有链接的条目（例如一本书、一份本地文档）写成 `- 标题 | 说明`：语料 0004 的
    「Competitive Programming 4（Halim 等，第 4 版）」就是这样一条，不能要求每本参考书都有 URL。
    """
    items = []
    for offset in range(start, end):
        text = lines[offset].strip()
        if not text:
            continue
        match = LINK_ITEM_RE.match(text)
        if match:
            title, href, meta = match.group(1), match.group(2), (match.group(3) or '').strip()
            if meta and name != 'resources':
                problems.add(path, offset + 1, '::: related 的条目只写 `- [标题](链接)`'
                                               '（说明是 resources 才有的）')
                continue
        else:
            plain = PLAIN_ITEM_RE.match(text)
            if not plain or name != 'resources':
                problems.add(path, offset + 1, f'::: {name} 的条目写成 `- [标题](链接)`'
                                               + ('；纯文字条目（书、本地文档）写成 `- 标题 | 说明`'
                                                  if name == 'resources' else ''))
                continue
            title, href, meta = plain.group(1).strip(), '', (plain.group(2) or '').strip()
        if not title:
            problems.add(path, offset + 1, f'::: {name} 的条目缺标题')
            continue
        items.append({'title': title, 'href': href, 'meta': meta, 'line': offset + 1})
    if not items:
        problems.add(path, line_no, f'::: {name} 块里没有条目（写 `- [标题](链接)`）')
    return {'kind': 'directive', 'name': name, 'items': items, 'line': line_no}


# ══════════════════════════════════════════════════════════════════
# 渲染：块 + 行内
# ══════════════════════════════════════════════════════════════════

def escape_quiz_attr(payload):
    """data-quiz 的值用单引号包裹：`& < > '` 写实体，`"` 留给 JSON 自己。

    口径来自 check_lesson.py 的两条属性检查：单引号包裹时值里不能有裸 `'`（浏览器会截断），
    JSON 字符串内部也不能写 `&quot;`（解码后是裸 `"`，会提前闭合字符串）。
    """
    return (payload.replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace("'", '&#39;'))


class Renderer:
    """把块渲染成 HTML；渲染期的每个问题（锚点无题、图片缺失）都带行号进 problems。"""

    def __init__(self, path, problems, lessons_dir, quiz, quiz_name, pool):
        self.path = path
        self.problems = problems
        self.lessons_dir = lessons_dir
        self.quiz = quiz
        self.quiz_name = quiz_name
        self.pool = pool
        self.figure_no = 0            # 页内图注编号（`::: figure` 与 `::: svg` 共用一条序列）
        self.has_math = False         # 这一页有没有数学式（决定壳里注不注入 KaTeX）

    # ── 图注编号 ──────────────────────────────────────────────────

    def numbered_caption(self, caption):
        """给图注编号：剥掉作者可能手写的旧号，按**页内出现顺序**重编。

        编号是可推导的信息（这一页第几张图），手写必然漂移——同页重号、跨课口径不一都发生过。
        只给**有说明文字**的图编号：没 caption 的图没有可见标签，不该占号（否则学生会看到跳号）。
        返回空串＝这张图不编号。
        """
        text = CAPTION_NUMBER_RE.sub('', caption.strip()).strip()
        if not text:
            return ''
        self.figure_no += 1
        return f'图 {self.figure_no} · {text}'

    # ── 行内 ──────────────────────────────────────────────────────

    def check_inline_html(self, text, line, where='正文'):
        """行内文本里出现**真标签**或 HTML 注释就报错（code span 里除外：那是要原样显示的代码）。

        判据与 `inline()` 共用 `code_span_end()`（落单的反引号不是 code 区，遮不住后面的标签），
        标签判据见 `tag_shape_at()`：`a < b`、`x > 0`、`2 < n`、`n<m 且 m>0`、`a<b>c`、`<T>` 这些
        运算符/泛型照常是普通文字；`<b>粗</b>`、`</div>`、`<img src=…>` 一律拦下并给出改法。
        一段文字只报第一处（带总数），不刷屏。
        """
        index, hits, comment = 0, [], None
        while index < len(text):
            char = text[index]
            if char == '`':
                close = code_span_end(text, index)
                index = close + 1 if close is not None else index + 1
                continue
            if char == '<':
                if text.startswith(HTML_COMMENT_OPEN, index) and comment is None:
                    comment = index
                else:
                    tag = tag_shape_at(text, index)
                    if tag:
                        hits.append(tag)
            index += 1
        if comment is not None:
            self.problems.add(self.path, line,
                              f'内容文件不写 HTML 注释（{where}，第 {comment + 1} 个字符处读到 '
                              f'{HTML_COMMENT_OPEN}）——那是手写时代留「题目位置」的写法，'
                              '现在题目位置写 `::: quiz <层级> 锚点：…`，说明写进正文')
        if hits:
            more = f'（这一段还有 {len(hits) - 1} 处）' if len(hits) > 1 else ''
            self.problems.add(self.path, line,
                              f'不写 HTML（{where}）：读到 {hits[0]!r}{more}——内容文件写的是教学内容、'
                              f'不是标记：粗体写 `**…**`。要在页面里展示 HTML 本身，'
                              f'把那段放进 ``` 围栏（短片段也可以用反引号，如 `` `{hits[0]}` ``）')

    def inline(self, text, line, check_html=True):
        """行内语法：`code`、**粗**、*斜*、[文字](href)、^x^、~x~；其余按文字转义。

        落单的标记（没有配对的 `*`、`^`、`~`）当普通字符——竞赛正文里 `10 ~ 20`、`a ^ b`
        这类写法很常见，不能因为落单就报错。代码 span 里的 `*`/`**` 是字面量，但 `^x^`/`~x~`
        仍然解析（语料 0002 有 3 处把 <sup> 写在 <code> 里面，整条算式当代码）。
        """
        if check_html:                                  # 只在最外层查一次（递归时整段已查过）
            self.check_inline_html(text, line)
        out, index, length = [], 0, len(text)
        while index < length:
            char = text[index]
            if char == '`':
                close = code_span_end(text, index)      # 与行内 HTML 检查共用同一判定
                if close is not None:
                    out.append('<code>' + self.code_span(text[index + 1:close]) + '</code>')
                    index = close + 1
                    continue
            elif text.startswith('**', index):
                close = text.find('**', index + 2)
                if close > index + 2:
                    out.append('<b>' + self.inline(text[index + 2:close], line, False) + '</b>')
                    index = close + 2
                    continue
            elif char == '*':
                close = text.find('*', index + 1)
                if close > index + 1 and not text[index + 1].isspace() and not text[close - 1].isspace():
                    out.append('<em>' + self.inline(text[index + 1:close], line, False) + '</em>')
                    index = close + 1
                    continue
            elif char in '^~':
                close = text.find(char, index + 1)
                inner = text[index + 1:close] if close > index + 1 else ''
                if inner and char not in inner and not re.search(r'\s', inner):
                    tag = 'sup' if char == '^' else 'sub'
                    out.append(f'<{tag}>' + self.inline(inner, line, False) + f'</{tag}>')
                    index = close + 1
                    continue
            elif char == '\\' and index + 1 < length and text[index + 1] == '$':
                out.append('$')                          # `\$`：正文里的字面美元号
                index += 2
                continue
            elif char == '$' and text.startswith('$$', index):
                close = text.find('$$', index + 2)      # 段落中间的 `$$…$$`：包成块级占位（span 合法）
                if close > index + 2:
                    tex = text[index + 2:close]
                    self.has_math = True
                    out.append('<span class="math-block">' + gen_home.esc(tex) + '</span>')
                    index = close + 2
                    continue
                self.problems.add(self.path, line,
                                  '块级公式 `$$…$$` 没有收尾——补上收尾的 `$$`')
                out.append('$$')
                index += 2
                continue
            elif char == '$':
                close = math_close(text, index)
                if close is not None:
                    tex = text[index + 1:close]
                    self.has_math = True
                    out.append('<span class="math-inline">' + gen_home.esc(tex) + '</span>')
                    index = close + 1
                    continue
                if not text[index + 1:index + 2].isspace() and text[index + 1:index + 2]:
                    self.problems.add(self.path, line,
                                      '行内公式 `$…$` 没有收尾——补上收尾的 `$`；'
                                      '正文里真要写美元号就写成 `\\$`')
                out.append('$')
                index += 1
                continue
            elif char == '[':
                link = LINK_RE.match(text, index)
                if link:
                    href = gen_home.esc(link.group(2), attr=True)
                    out.append(f'<a href="{href}">{self.inline(link.group(1), line, False)}</a>')
                    index = link.end()
                    continue
            out.append(gen_home.esc(char))
            index += 1
        return ''.join(out)

    def code_span(self, text):
        """code span 的内文：转义，但 `^x^`/`~x~` 仍解析成上/下标（其余标记是字面量）。

        标记规则与正文一致（内容不能带空格、不能再出现同种标记），所以 C++ 的 `~a & ~b`、
        `a ^ b`、`int **p` 都不会被误判；`100000 × 100000 = 10^10^` 会渲染成
        `<code>…10<sup>10</sup></code>`，与语料 0002 手写的形态一致。
        """
        out, index, length = [], 0, len(text)
        while index < length:
            char = text[index]
            if char in '^~':
                close = text.find(char, index + 1)
                inner = text[index + 1:close] if close > index + 1 else ''
                if inner and char not in inner and not re.search(r'\s', inner):
                    tag = 'sup' if char == '^' else 'sub'
                    out.append(f'<{tag}>' + self.code_span(inner) + f'</{tag}>')
                    index = close + 1
                    continue
            out.append(gen_home.esc(char))
            index += 1
        return ''.join(out)

    # ── 块 ────────────────────────────────────────────────────────

    def render(self, blocks, indent='  '):
        chunks = [self.render_block(block, indent) for block in blocks]
        return '\n\n'.join(chunk for chunk in chunks if chunk)

    def render_block(self, block, indent):
        kind = block['kind']
        if kind in ('h2', 'h3'):
            return f'{indent}<{kind}>{self.inline(block["text"], block["line"])}</{kind}>'
        if kind == 'p':
            math = BLOCK_MATH_RE.match(block['text'].strip())
            if math:
                self.has_math = True
                return (f'{indent}<div class="math-block">'
                        f'{gen_home.esc(math.group(1).strip())}</div>')
            return f'{indent}<p>{self.inline(block["text"], block["line"])}</p>'
        if kind == 'code':
            attr = f' data-lang="{gen_home.esc(block["lang"], attr=True)}"' if block['lang'] else ''
            return f'{indent}<pre{attr}><code>{gen_home.esc(block["text"])}</code></pre>'
        if kind in ('ul', 'ol'):
            return self.render_list(block, indent)
        if kind == 'table':
            return self.render_table(block, indent)
        if kind == 'directive':
            return self.render_directive(block, indent)
        # 兜底：认不出的块**报错**而不是安静地丢——静默丢内容正是这次改造要消灭的东西
        self.problems.add(self.path, block.get('line', 1),
                          f'渲染器不认识这种块（kind={kind!r}）——这是渲染器的 bug，'
                          '请把这一条连同内容文件报到引擎维护者')
        return ''

    def render_list(self, block, indent):
        lines = [f'{indent}<{block["kind"]}>']
        for item in block['items']:
            text = self.inline(item['text'], item['line'])
            if item['children']:
                lines.append(f'{indent}  <li>{text}')
                lines.append(self.render_list(item['children'], indent + '    '))
                lines.append(f'{indent}  </li>')
            else:
                lines.append(f'{indent}  <li>{text}</li>')
        lines.append(f'{indent}</{block["kind"]}>')
        return '\n'.join(lines)

    def render_table(self, block, indent):
        head = ''.join(f'<th>{self.inline(cell, block["line"])}</th>' for cell in block['header'])
        lines = [f'{indent}<table>',
                 f'{indent}  <thead>',
                 f'{indent}    <tr>{head}</tr>',
                 f'{indent}  </thead>',
                 f'{indent}  <tbody>']
        for row in block['rows']:
            cells = ''.join(f'<td>{self.inline(cell, block["line"])}</td>' for cell in row)
            lines.append(f'{indent}    <tr>{cells}</tr>')
        lines += [f'{indent}  </tbody>', f'{indent}</table>']
        return '\n'.join(lines)

    def render_directive(self, block, indent):
        name = block['name']
        line = block['line']
        if name == 'practice':
            return self.render_practice(block, indent)
        if name in CARD_CLASS:
            lines = [f'{indent}<div class="{CARD_CLASS[name]}">']
            if block['title']:
                lines.append(f'{indent}  <b>{self.inline(block["title"], line)}</b>')
            inner = self.render(block['body'], indent + '  ')
            if inner:
                lines.append(inner)
            lines.append(f'{indent}</div>')
            return '\n'.join(lines)
        if name == 'quiz':
            return self.render_quiz(block, indent)
        if name == 'figure':
            return self.render_figure(block, indent)
        if name == 'svg':
            return self.render_svg(block, indent)
        if name in ('resources', 'related'):
            return self.render_links(block, indent)
        # 兜底：与 render_block 同理——认不出的指令**报错**，不做静默空输出
        self.problems.add(self.path, line,
                          f'渲染器不认识这个指令（name={name!r}）——这是渲染器的 bug，'
                          '请把这一条连同内容文件报到引擎维护者')
        return ''

    def render_practice(self, block, indent):
        lines = [f'{indent}<div class="lesson-practice">',
                 f'{indent}  <div class="lesson-practice__head">',
                 f'{indent}    <span class="lesson-practice__level">'
                 f'{self.inline(block["level"], block["line"])}</span>',
                 f'{indent}    <span class="lesson-practice__title">'
                 f'{self.inline(block["title"], block["line"])}</span>',
                 f'{indent}  </div>']
        inner = self.render(block['body'], indent + '    ')
        if inner:
            lines += ['', inner]
        lines.append(f'{indent}</div>')
        return '\n'.join(lines)

    def render_quiz(self, block, indent):
        """按锚点从题库取题；锚点没题时必须 empty_reason，否则报错（绝不静默出一个空块）。"""
        questions = self.quiz.get(block['anchor']) if isinstance(self.quiz, dict) else None
        if isinstance(questions, list) and questions:
            if block['empty_reason']:
                self.problems.add(self.path, block['line'],
                                  f'锚点「{block["anchor"]}」在题库里有 {len(questions)} 道题，'
                                  'empty_reason 是给无题锚点用的（删掉它）')
            payload = json.dumps(questions, ensure_ascii=False, indent=2)
            return f'{indent}<div class="quiz" data-quiz=\'{escape_quiz_attr(payload)}\'></div>'
        if block['empty_reason']:
            note(f'{self.path}:{block["line"]} 锚点「{block["anchor"]}」没有题：{block["empty_reason"]}')
            return ''
        self.problems.add(self.path, block['line'],
                          f'锚点「{block["anchor"]}」在 {self.quiz_name} 里没有题——'
                          '要么让出题角色补题，要么写一行 `empty_reason: <理由>`')
        return ''

    def render_figure(self, block, indent):
        src, line = block['src'], block['line']
        local_path = unquote(src.split('#', 1)[0].split('?', 1)[0])
        if SCHEME_RE.match(src) or os.path.isabs(local_path):
            self.problems.add(self.path, line, f'::: figure 只接受本地相对路径（现在是 {src}）——'
                                               '图从科目图片库 assets/img/pool/ 挑')
        else:
            target = os.path.normpath(os.path.join(self.lessons_dir, local_path))
            if not os.path.isfile(target):
                self.problems.add(self.path, line,
                                  f'图片文件不存在：{src}（解析到 {target}）——'
                                  '从科目图片库 assets/img/pool/ 挑一张，或先采图')
        alt = block['alt']
        # alt: 是属性值（纯文本，不解析行内标记），但和 caption: 一样**不许真标签**：文档把
        # alt: 列进了「会报错的位置」，代码就得真查（`<b>`/`<script>` 曾经静默进属性出厂）。
        self.check_inline_html(alt, block.get('alt_line', line), '::: figure 的 alt:')
        caption = self.numbered_caption(block['caption'])
        if '来源：' not in caption:                    # 作者自己写了来源就不重复补
            caption += self.pool_source(src)
        lines = [f'{indent}<figure class="lesson-figure">',
                 f'{indent}  <img src="{gen_home.esc(src, attr=True)}" '
                 f'alt="{gen_home.esc(alt, attr=True)}">']
        if caption:
            lines.append(f'{indent}  <figcaption>'
                         f'{self.inline(caption, block.get("caption_line", line))}</figcaption>')
        lines.append(f'{indent}</figure>')
        return '\n'.join(lines)

    def render_svg(self, block, indent):
        attr = ''
        if block['alt']:
            self.check_inline_html(block['alt'], block.get('alt_line', block['line']),
                                   '::: svg 的 alt:')
            attr = f' role="img" aria-label="{gen_home.esc(block["alt"], attr=True)}"'
        lines = [f'{indent}<figure class="lesson-figure lesson-figure--inline"{attr}>',
                 block['raw']]
        caption = self.numbered_caption(block['caption'])
        if caption:
            lines.append(f'{indent}  <figcaption>'
                         f'{self.inline(caption, block.get("caption_line", block["line"]))}'
                         f'</figcaption>')
        lines.append(f'{indent}</figure>')
        return '\n'.join(lines)

    def render_links(self, block, indent):
        line = block['line']
        if block['name'] == 'related':
            lines = [f'{indent}<div class="lesson-related">']
            lines += [f'{indent}  <a href="{gen_home.esc(item["href"], attr=True)}">'
                      f'{self.inline(item["title"], item["line"])}</a>' for item in block['items']]
            lines.append(f'{indent}</div>')
            return '\n'.join(lines)
        lines = [f'{indent}<ul class="lesson-resources">']
        for item in block['items']:
            meta = (f'<span class="lesson-resources__meta">{self.inline(item["meta"], item["line"])}'
                    '</span>') if item['meta'] else ''
            head = (f'<a href="{gen_home.esc(item["href"], attr=True)}">'
                    f'{self.inline(item["title"], item["line"])}</a>') if item['href'] else \
                self.inline(item['title'], item['line'])
            lines.append(f'{indent}  <li>{head}{meta}</li>')
        lines.append(f'{indent}</ul>')
        return '\n'.join(lines)

    def pool_source(self, src):
        """图片库里的图：题注自动补「（来源：…，许可：…）」（读 assets/img/pool.md 的索引行）。"""
        local_path = unquote(src.split('#', 1)[0].split('?', 1)[0])
        row = self.pool.get(os.path.basename(local_path))
        if not row:
            return ''
        return f'（来源：{row["url"]}，许可：{row["license"]}）'


def quiz_has_math(quiz):
    """题库里有没有 `$…$` 公式——有就得让页面注入离线 KaTeX。

    题目正文（题面/选项/答案/判分要点/解析）由 `quiz.js` 在浏览器里排版，渲染产物里只有
    `data-quiz` 属性，静态看是看不出公式的；而「注不注入 KaTeX」必须在渲染时就定下来，
    所以这里扫一遍字符串字段。判据与 `math_close()` 同源，够用即可——多注入一份没害处，
    少注入就是公式排不出来。
    """
    for problems in (quiz or {}).values():
        if not isinstance(problems, list):
            continue
        for item in problems:
            if not isinstance(item, dict):
                continue
            for value in item.values():
                values = value if isinstance(value, list) else [value]
                for text in values:
                    if isinstance(text, str) and MATH_PAIR_RE.search(text):
                        return True
    return False


def load_quiz(path, problems, referenced=None):
    """题库：`{"锚点文本": [题, …]}`；结构不对就报错（渲染器不猜）。

    `referenced` 给了就顺手做**反方向**的对账：题库里多出来的锚点（没有任何题目位置引用）
    一道题都不会出现在页面上，也要带行号报出来——出题角色的全部交付就是这份 JSON，
    这个方向的漂移同样不许静默。
    """
    if not os.path.isfile(path):
        problems.add(path, 1, '内容里有 ::: quiz，但找不到题库文件（出题角色产出 .quiz.json）')
        return None
    raw = read_text(path, problems, '题库文件')
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except ValueError as exc:
        problems.add(path, getattr(exc, 'lineno', 1) or 1, f'题库不是合法 JSON：{exc}')
        return None
    if not isinstance(data, dict):
        problems.add(path, 1, '题库结构应为 {"锚点文本": [题, …]}（最外层是对象）')
        return None
    for anchor, questions in data.items():
        if not isinstance(questions, list) or not questions:
            problems.add(path, line_of(raw, f'"{anchor}"'),
                         f'锚点「{anchor}」的值应是非空的题目数组')
    if referenced is not None:
        for anchor in data:
            if anchor in referenced:
                continue
            problems.add(path, line_of(raw, json.dumps(anchor, ensure_ascii=False)),
                         f'题库里的锚点「{anchor}」没有任何 ::: quiz 题目位置引用它——'
                         '这些题不会出现在页面上（删掉这个键，或让讲解角色在正文里补题目位置）')
    return data


def check_duplicate_anchors(md_path, blocks, problems):
    """同一个锚点被两个题目位置引用 → 同一批题会渲染两遍，按错拦下（锚点是一对一的接头）。"""
    first_line = {}
    for block in blocks:
        if block.get('name') != 'quiz':
            continue
        anchor = block['anchor']
        if anchor in first_line:
            problems.add(md_path, block['line'],
                         f'锚点「{anchor}」重复：第 {first_line[anchor]} 行已经用过同一个锚点——'
                         '同一批题会被渲染两遍（一个锚点只留一个题目位置）')
        else:
            first_line[anchor] = block['line']


def load_pool(subject_dir, problems):
    """图片池索引 `assets/img/pool.md` → {文件名: {'url':…, 'license':…}}（缺文件不是错）。"""
    path = os.path.join(subject_dir, 'assets', 'img', 'pool.md')
    if not os.path.isfile(path):
        return {}
    raw = read_text(path, problems, '图片池索引')
    if raw is None:
        return {}
    pool = {}
    for line in raw.split('\n'):
        if not line.strip().startswith('|'):
            continue
        cells = split_cells(line)
        if len(cells) < 5 or cells[0] in ('文件', '') or SEPARATOR_CELL_RE.match(cells[0]):
            continue
        pool[cells[0]] = {'url': cells[3], 'license': cells[4]}
    return pool


def load_template(path, problems):
    """模板壳：占位符必须齐全，且不许剩下没替换的（缺了就报错，防止静默出残缺页面）。

    只取 `<!DOCTYPE` 起的内容：模板开头给维护者看的说明注释留在仓库里，不随每个页面出厂
    （学生查看源码时不该读到写给模型的说明）。定位 DOCTYPE 前先把注释**遮掉**——说明注释里
    自己会提到 `<!DOCTYPE`，直接 find 会切在注释中间、把半截说明漏进页面。
    """
    raw = read_text(path, problems, '课件模板')
    if raw is None:
        return None
    masked = mask_comments(raw)                        # 等长遮罩：注释里的 DOCTYPE 不算数的
    start = masked.find('<!DOCTYPE')
    if start < 0:
        problems.add(path, 1, '模板里找不到 <!DOCTYPE（课件页必须是一份完整 HTML）')
        return None
    base_line = raw[:start].count('\n')                # 切片前的行数：报错行号要映射回原文件
    raw = raw[start:]
    for name, count in TEMPLATE_PLACEHOLDERS.items():
        placeholder = PLACEHOLDER.format(name)
        found = raw.count(placeholder)
        if found != count:
            problems.add(path, base_line + line_of(raw, placeholder),
                         f'模板里 {placeholder} 应出现 {count} 次，实际 {found} 次（模板被改坏了）')
    return raw


# ══════════════════════════════════════════════════════════════════
# 组装页面：模板占位符 + 渲染器自己产出的部分
# ══════════════════════════════════════════════════════════════════

def render_nav(outline, index):
    """上/下节课指针按 curriculum.yaml 的 nodes 顺序算：第一课无 --prev、最后一课无 --next。"""
    lines = ['  <nav class="lesson-nav" aria-label="上一课 / 下一课">']
    for direction, neighbor in zip(('prev', 'next'), outline.neighbors(index)):
        if not neighbor:
            continue
        number = outline.index_of(neighbor)
        label = '上节课' if direction == 'prev' else '下节课'
        lines += [f'    <a class="lesson-nav__link lesson-nav__link--{direction}"'
                  f' href="{number:04d}-{neighbor}.html">',
                  f'      <span class="lesson-nav__dir">{label}</span>',
                  f'      <span class="lesson-nav__title">{gen_home.esc(outline.title_of(neighbor))}'
                  '</span>',
                  '    </a>']
    lines.append('  </nav>')
    return '\n'.join(lines)


def math_refs_html(enabled):
    """有数学式的页面才注入 KaTeX 三个引用；没有就返回空串（模板那一行整行消失）。"""
    if not enabled:
        return ''
    base = '../../../assets/'
    lines = []
    for ref in MATH_REFS:
        if ref.endswith('.css'):
            lines.append(f'<link rel="stylesheet" href="{base}{ref}">')
        else:
            lines.append(f'<script src="{base}{ref}" defer></script>')
    return '\n'.join(lines)


def fill_template(template, path, fields, problems):
    """用 gen_home 的 replace_block/replace_field 口径套模板（缺占位符即报错）。"""
    html = template
    html = gen_home.replace_field(html, PLACEHOLDER.format('TITLE'), fields['title'], path)
    html = gen_home.replace_field(html, PLACEHOLDER.format('SUBJECT'), fields['subject'], path)
    for name in ('NUMBER', 'EYEBROW', 'GOAL', 'BODY', 'NAV', 'FOOTER', 'MATH'):
        html = gen_home.replace_block(html, PLACEHOLDER.format(name), fields[name.lower()], path)
    for name in TEMPLATE_PLACEHOLDERS:
        leftover = PLACEHOLDER.format(name)
        if leftover in html:
            problems.add(path, line_of(html, leftover), f'模板里的 {leftover} 没有被替换')
    return html


# ══════════════════════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════════════════════

def parse_args(argv):
    """`<科目目录> <节点id> [--check]`；`--help` 直接打印用法退 0，用法不对回 None（调用方退 2）。"""
    positionals, check_only = [], False
    for arg in argv:
        if arg == '--check':
            check_only = True
        elif arg in ('-h', '--help'):
            print(__doc__)
            raise SystemExit(0)
        elif arg.startswith('-'):
            print(f'未知参数 {arg}\n{USAGE}', file=sys.stderr)
            return None
        else:
            positionals.append(arg)
    if len(positionals) != 2:
        print(f'用法错误：要 <科目目录> 与 <节点id> 两个参数\n{USAGE}', file=sys.stderr)
        return None
    return positionals[0], positionals[1], check_only


def main(argv):
    parsed = parse_args(argv)
    if parsed is None:
        return 2
    subject_dir, node_id, check_only = parsed
    problems = Problems()

    outline = load_outline(subject_dir, problems)
    if outline is None:
        problems.report()
        return 1
    index = outline.index_of(node_id)
    if index is None:
        problems.add(outline.path, 1, f'节点 {node_id} 不在 curriculum.yaml 的 nodes: 里——'
                                      '课件归属与编号都按它算（核对节点 id 是否写对）')
        problems.report()
        return 1

    lessons_dir = os.path.join(subject_dir, 'lessons')
    md_path = os.path.join(lessons_dir, f'{index:04d}-{node_id}.md')
    quiz_path = os.path.join(lessons_dir, f'{index:04d}-{node_id}.quiz.json')
    out_path = os.path.join(lessons_dir, f'{index:04d}-{node_id}.html')
    if not os.path.isfile(md_path):
        problems.add(md_path, 1, '找不到内容文件（讲解角色先产出这一课的 .md，再渲染）')
        problems.report()
        return 1

    raw = read_text(md_path, problems, '内容文件')
    template = load_template(TEMPLATE, problems)
    if raw is None or template is None:
        problems.report()
        return 1

    lines = raw.split('\n')
    front, body_start, front_lines = parse_front_matter(md_path, lines, problems)
    check_title_match(md_path, node_id, front, front_lines, outline, problems)
    blocks = parse_blocks(md_path, lines, body_start, len(lines), problems)

    needs_quiz = any(block.get('name') == 'quiz' for block in blocks)
    check_duplicate_anchors(md_path, blocks, problems)
    referenced = {block['anchor'] for block in blocks if block.get('name') == 'quiz'}
    if needs_quiz:
        quiz = load_quiz(quiz_path, problems, referenced)
    else:
        quiz = None
        if os.path.isfile(quiz_path):
            # 内容里一个题目位置都没有、题库文件却还在：出题角色的整份交付没人用（题目全丢）。
            # `kind: 实验` 的说明页本来就不交题库，所以只有「文件真的存在」时才查这一条。
            problems.add(quiz_path, 1,
                         '内容文件里没有任何 ::: quiz 题目位置，但题库文件还在——这些题一道也不会'
                         '出现在页面上（删掉题库文件，或在正文里补上题目位置）')
    pool = load_pool(subject_dir, problems) if any(block.get('name') == 'figure' for block in blocks) else {}

    renderer = Renderer(md_path, problems, lessons_dir, quiz,
                        os.path.basename(quiz_path), pool)
    if quiz_has_math(quiz):
        renderer.has_math = True      # 公式只在题库里出现时，壳里也得注入 KaTeX
    body_html = renderer.render(blocks)
    title = front.get('title', '')
    goal_line = front_lines.get('goal', 1)
    # front matter 的值也是散文：goal 走 inline()（自带检查），title 是纯文本，单独查一遍
    renderer.check_inline_html(title, front_lines.get('title', 1), 'front matter 的 title')
    fields = {
        'title': gen_home.esc(title),
        'subject': gen_home.esc(load_subject_name(subject_dir)),
        'number': f'{index:04d}',
        'eyebrow': f'{index:04d} · {gen_home.esc(title)}',
        'goal': renderer.inline(front.get('goal', ''), goal_line),
        'body': body_html,
        'nav': render_nav(outline, index),
        'footer': f'StudyMate · {index:04d} {gen_home.esc(title)} · 本地学习工作区',
        'math': math_refs_html(renderer.has_math),
    }
    page = fill_template(template, TEMPLATE, fields, problems)

    if problems:
        problems.report()
        return 1
    if check_only:
        print(f'OK   {md_path}（只校验，没有写盘）')
        return 0
    with open(out_path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(page)
    print(f'OK   {out_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
