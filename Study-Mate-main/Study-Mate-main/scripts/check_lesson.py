#!/usr/bin/env python3
r"""课件质量检查：只阻断工程/结构缺项；内容风格类问题只提示，不影响放行。

用法：
  python3 scripts/check_lesson.py <课件路径> [<课件路径> ...] [--subject <科目目录>] [--node <节点id>]

`--subject` 与 `--node` 一起给，才能判定"这课该不该有 lab"：读 `<科目>/curriculum.yaml` 里该节点的
`kind`——`实操` 与 `实验` 必须有 lab 与产物，`概念` 不该有 lab。不给这两个参数时跳过实操判定并回显一条提示。

输出：每个文件——无阻断项时一行 `OK   <path>`；有阻断项时 `FAIL <path>: 问题1；问题2`；
另有提示项时再补一行 `WARN <path>: 提示1；提示2`（两类可以同时出现）。
退出码：**只看阻断项**——全部文件无阻断项 0；任一文件有阻断项 1；无参数时把本用法打到 stderr 并退出 1。
总控在 xdg-open 打开课件之前跑一次：`FAIL` 的工程/结构缺项打回对应角色修
（题目相关 → practice-evaluator；版式/链接 → learning-coach），`WARN` 只自己心里有数。

判定规则：
  阻断项（失败即打回）——只判工程/结构：
    1 文件名：匹配 NNNN-dash-case.html（四位数字-小写字母数字短横线）。编号规则：
      被检文件在同目录内是最大编号 → 必须等于其它文件最大编号 + 1（目录内只有它时必须是 0001）；
      否则（复检旧课件）→ 只要求该编号在目录内唯一。
    2 共享层引用：href/src 属性值里齐全 sayo.css、learn-theme.css、learn-theme.js、sayo.js。
    3 科目组件引用：href/src 属性值里齐全 ../assets/style.css、../assets/quiz.js。
    4 题目（结构，题型不同要求不同；字段契约见 templates/assets/quiz.js 顶部注释）：
       每个 .quiz[data-quiz] 块是合法 JSON 非空数组；每题：
         · 都有非空 `q`（题面）；
         · 选择题（写了 opts/ans）：`opts` 是 ≥2 项的数组、`ans` 是范围内的整数、`why` 非空；
         · 开放题（写了 answer/criteria）：`answer`（参考答案）与 `criteria`（判分要点）都非空；
         · 两组字段不能同时出现在一题里；都没有则题型不明。
         · `q`/`answer`/`criteria`/`why` 里的 ``` 围栏必须成对（不成对后半段会被渲染成代码块）。
       普通课件至少要有一道题；`kind: 实验` 的说明页是任务书，没有题目块不算缺项。
       三条**属性值写法**的检查（浏览器口径与取值正则不一致，必须单独拦）：
         · 裸的同类引号（`'` 包属性又出现裸 `'`）：浏览器在那里截断属性；
         · 单引号包裹时，JSON 字符串内部写了实体引号 `&quot;`：解码后是裸 `"`，提前闭合字符串；
         · 双引号包裹时，值里出现裸 `"`（含 `\"`）：浏览器同样在那里截断属性。
    5 实操（按节点的 `kind` 条件判定，需 --subject 与 --node）：
       · `kind: 实操` 或 `kind: 实验`：必须有 href 含 lab/ 的链接，且 `<科目>/lab/<本课编号>-*/`
         存在、里面有任务文件、`<科目>/lab/solutions/` 非空；
       · `kind: 概念`：链接了 lab/ 只提示（规范上概念课不配实操），不阻断。
    6 主题开关：存在 id="lesson-theme-checkbox" 的 <input type="checkbox">，
       且有 LearnTheme.wire(...) 引用该 id（骨架里的主题开关不能被改丢）。
    7 题目位置残留：`lessons/` 目录下的课件里不得留着 `<!-- 题目位置：… -->` 标记
       （那是手写课件时代留占位的写法；新流程写内容文件、由渲染器出页面，产物里不会有它）。
    8 命名与上/下节课指针（需 --subject 与 --node，邻居取自 curriculum.yaml 的 nodes 顺序）：
       · 节点必须真实存在于 `nodes:` 里——归属查不出来即 FAIL（否则课件在主页路线图上不存在，
         而主页只按文件名归属，见 gen_home.py 的 lesson_node_id）；
       · 文件名必须是 `<序号>-<节点id>.html`，序号 = 节点在 `nodes:` 里的位置（从 1 起）；
         上一课的「下节课」指针就按这条规则预写，名字错了那根指针就是死链。
       · `.lesson-nav` 里的 `--prev` / `--next` 必须正好指向大纲里的前后邻居
         （有邻居就得写、没有邻居就不许写；href 是同目录下的文件名）。
       · 指针指向的文件不存在只提示不阻断——下节课通常还没产出，落空是设计内的。
    9 图片：<img> 引用的**本地**文件必须真实存在——学生看到裂图是工程缺陷，必须拦。
       gen_home 的链接自检只管它自己写出的主页（根主页 + 科目主页），课件页不在它范围内。
       内联 <svg> 不引用文件，这条不管。
   10 本地引用可达：页面里所有 href/src 的**本地**目标必须真实存在——组件、图片、正文里的
       链接、lab 链接都算。第 9 项只管 <img>，这条管其余全部：页面缺了组件文件、或正文里那条
       lab 链接指错了文件名，检查照样全绿而学生点开是白板 / 404。
       跳过三类：外链与锚点（http(s)、协议相对 //、mailto:、data:、`#…`）；HTML 注释里的
       示例路径；上/下节课指针（落空是设计内的，第 8 项只提示）。
       另有一条**生成产物**：指向 `index.html`（壳里那条「返回课程」回链，目标是 gen_home.py
       的产物）而它还没生成时只提示——作者产不出这个文件，缺了是流水线顺序问题，不是课件缺陷。
   11 数学式：页面里有 `.math-inline` / `.math-block` **或**题库数据（`data-quiz`）里带 `$…$`
       公式时，壳里必须引用离线 KaTeX 三件（katex/katex.min.css、katex/katex.min.js、
       lesson-math.js）。**条件判定**：都没有就不要求——老课件与非数学课因此零改动。
       少了引用，公式只显示 TeX 原文（题面里的也一样），等于没排版。
  提示项（只回显、退出码不受影响）——质量线，值得看一眼：
    · 题面/答案的散文里出现 Markdown/HTML 标记（`**加粗**`、行内反引号、`# 标题`、`- 列表`、
      `<b>`）：字段是**纯文本**，这些会原样显示（换行用 `\n`、代码用 ``` 围栏）。
    · 选项长度差：每题 max(len(opt)) - min(len(opt)) > MAX_OPT_LEN_GAP 时提示。
    · 实操判定被跳过（没给 --subject/--node，或 progress.yaml 读不出来）。
    · 小节标题超过 14 字：它会进左侧目录（220px 宽），长了要换行。
    · 上/下节课指针指向的课件还没产出（悬空指针，正常）。
    · 图片用了外链（http/https 或其他 scheme）：离线打开会裂；建议从科目图片库
      `assets/img/pool/` 挑一张本地文件引用。
    · 图片缺 alt：裂图时学生只看到空白，读屏软件也读不出。
    · 方程组少了 `\left\{ … \right.` 大括号（aligned 里 ≥2 行等式却没被包住）：
      KaTeX 不会自己加，少了读者会当成几个独立结论。

本检查**不判内容风格**：真实场景、术语来历、怎么分节与标题怎么写，都是 lesson-design 的
着眼点与倾向，由讲解角色按内容与学生偏好现场定；检查不用关键词词表去替它做判断——那种代理会把
课件逼成套模板。题目**出得好不好**（难度、覆盖、与 `objective` 的对应）也不由检查判，那是
layered-practice 的规范与 practice-evaluator 的活；检查只判结构完整。

已知且预期：templates/lesson.html 骨架本身过不了阻断项（组件示例改成注释形式后没有真的
`.quiz[data-quiz]`，也没有指向 lab/ 的链接；校验前会先剥掉注释）——骨架只给工程外壳与组件示例，
正文与题目由各角色按规范补齐，这不是检查缺陷。

依赖：标准库 + pyyaml（与 gen_home.py 一致）；没装 pyyaml 时实操判定跳过并回显提示。
"""
import json
import html
import os
import re
import sys
from html.parser import HTMLParser
from urllib.parse import unquote

try:
    import yaml
except ImportError:      # pragma: no cover - 环境缺 pyyaml 时降级
    yaml = None

# ── 判定口径（要调整只改这里）─────────────────────────────────────────────

# 检查项 1：课件文件名与同目录编号（R4）
# 节点 id 允许点号分段（如 hello.first、exp.first-blood、cpp.stl），文件名沿用同一 id，
# 所以短横线之外还要容许点号；分隔符不许连续、不许落在结尾。
LESSON_NAME_RE = re.compile(r'^(\d{4})-(?:[a-z0-9]+[.-])*[a-z0-9]+\.html$')
NUMBERED_NAME_RE = re.compile(r'^(\d{4})-.*\.html$')

# 检查项 2/3：共享层与科目组件引用（按 href/src 属性值比对，不吃注释里的路径）
SHARED_REFS = ('sayo.css', 'learn-theme.css', 'learn-theme.js', 'sayo.js')
SUBJECT_REFS = ('../assets/style.css', '../assets/quiz.js')

# 检查项 4（提示）：字段是纯文本，这些 Markdown/HTML 标记不会被解析、会原样显示。
# 保守集合：`1. ` 这类行首编号**不算**——作者的枚举写法本来就是这样；围栏里的内容不看。
MARKDOWN_RE = (
    re.compile(r'\*\*[^*\n]+\*\*'),          # **加粗**
    re.compile(r'`[^`\n]+`'),                  # `行内代码`
    re.compile(r'^#{1,6} ', re.M),             # # 标题
    re.compile(r'^- ', re.M),                  # - 列表
    re.compile(r'\[[^\]\n]+\]\([^)\n]+\)'),  # [链接](url)
    re.compile(r'</?[a-zA-Z][a-zA-Z0-9]*[ >/]'),  # <b> 之类
)

# 检查项 9/10：引用是否外链（任何 scheme: 或协议相对 //，与 gen_home 的 SCHEME_RE 同口径）
SCHEME_RE = re.compile(r'^(?:[A-Za-z][A-Za-z0-9+.\-]*:|//)')

# 检查项 4：题目结构里的 ``` 围栏（与 templates/assets/quiz.js 的渲染口径一致）
# 围栏行 = 行首可有缩进 + 三个反引号 + 可选语言标签；行内的单个反引号不算。
QUIZ_FENCE_RE = re.compile(r'^[ \t]*```[ \t]*[A-Za-z0-9+#.-]*[ \t]*$')

# 检查项 4：每题选项最长与最短的长度差**提示**阈值（R5）——超过只提示，不阻断
MAX_OPT_LEN_GAP = 4

# 检查项 8：小节标题长度**提示**阈值——目录侧栏 220px，14 个汉字一行放得下
MAX_H2_CHARS = 14

# 检查项 6：主题开关元素 id
THEME_CHECKBOX_ID = 'lesson-theme-checkbox'

# 检查项 11：有数学式的页面必须引用离线 KaTeX（渲染器写出的 .math-inline / .math-block）
MATH_MARK_RE = re.compile(r'class="[^"]*\bmath-(?:inline|block)\b', re.I)
MATH_REFS = ('katex/katex.min.css', 'katex/katex.min.js', 'lesson-math.js')
# 题目正文（data-quiz 里）的公式：静态看不到 .math-inline 元素，得扫属性
QUIZ_ATTR_RE = re.compile(r'data-quiz\s*=\s*(["\'])(.*?)\1', re.S)
MATH_PAIR_RE = re.compile(r'\$[^\s$][^$\n]*[^\s$]\$|\$[^\s$]\$')

# 检查项 7：手写课件时代留下的题目位置标记（新流程由渲染器出页面；骨架注释里是示例，路径不同）
PLACEHOLDER_RE = re.compile(r'^[ \t]*<!--[ \t]*题目位置', re.M)
LESSONS_DIR_MARK = '/lessons/'

# ── 公共正则 ────────────────────────────────────────────────────────────

REF_ATTR_RE = re.compile(r'(?:href|src)\s*=\s*["\']([^"\']*)["\']', re.I)
COMMENT_RE = re.compile(r'<!--.*?-->', re.S)
LAB_LINK_RE = re.compile(r'href\s*=\s*["\'][^"\']*lab/', re.I)
INPUT_RE = re.compile(r'<input\b[^>]*>', re.I)


def strip_comments(text):
    """剥掉 HTML 注释，避免把注释里的示例标记当成真标记。"""
    return COMMENT_RE.sub('', text)


def ref_values(text):
    """取出所有 href/src 属性值，供引用类检查比对。"""
    return REF_ATTR_RE.findall(text)


def local_target(path, value):
    """把页面里的引用值解析成磁盘路径；外链、锚点、空值返回 None。

    与检查项 9 同口径：先去掉 `#…` 与 `?…`，`%xx` 解码，再按页面所在目录解析。
    """
    raw = html.unescape(value).strip()
    if not raw or raw.startswith('#') or SCHEME_RE.match(raw):
        return None
    relative = unquote(raw.split('#', 1)[0].split('?', 1)[0])
    if not relative:
        return None
    return os.path.normpath(os.path.join(os.path.dirname(path) or '.', relative))


# ── 科目数据：节点的课型（curriculum.yaml 的 kind）──────────────────────────


class SubjectData:
    """读 <科目>/curriculum.yaml，记下每个节点的 `kind`（概念／实操／实验）。

    课型决定检查怎么判实操：`概念` 不配 lab；`实操` 与 `实验` 必须有 lab 与产物。
    """

    def __init__(self, subject_dir):
        self.dir = subject_dir
        self.kinds = {}
        self.order = []
        self.error = None
        if yaml is None:
            self.error = '未安装 pyyaml'
            return
        path = os.path.join(subject_dir, 'curriculum.yaml')
        try:
            with open(path, encoding='utf-8') as handle:
                curriculum = yaml.safe_load(handle) or {}
        except (OSError, UnicodeDecodeError) as exc:
            self.error = f'读不出 {path}（{exc}）'
            return
        except Exception as exc:                      # yaml.YAMLError 及结构异常
            self.error = f'{path} 不是合法 YAML（{exc}）'
            return
        nodes = curriculum.get('nodes') if isinstance(curriculum, dict) else None
        if not isinstance(nodes, list):
            self.error = f'{path} 的 nodes 必须是节点数组'
            return
        for position, node in enumerate(nodes, 1):
            node_id = node.get('id') if isinstance(node, dict) else None
            if not isinstance(node_id, str) or not re.fullmatch(r'[a-z0-9]+([.-][a-z0-9]+)*', node_id):
                self.error = f'{path} 的 nodes 第 {position} 项缺少合法的节点 id'
                return
            if node_id in self.kinds:
                self.error = f'{path} 里有重复 id: {node_id}'
                return
            self.kinds[node_id] = str(node.get('kind') or '').strip()
            self.order.append(node_id)

    def kind_of(self, node):
        return self.kinds.get(str(node)) or None

    def index_of(self, node):
        """节点在 `nodes:` 里的序号（从 1 起；课件编号就用它）；不在大纲里返回 None。"""
        try:
            return self.order.index(str(node)) + 1
        except ValueError:
            return None

    def neighbors(self, node):
        """(上一个节点 id, 下一个节点 id)——到头的那个是 None。"""
        index = self.index_of(node)
        if index is None:
            return None, None
        prev_id = self.order[index - 2] if index >= 2 else None
        next_id = self.order[index] if index < len(self.order) else None
        return prev_id, next_id


def lab_number_of(path):
    """课件编号（0002 → 2）；文件名不合格时返回 None，交给检查项 1 报。"""
    match = LESSON_NAME_RE.match(os.path.basename(path))
    return int(match.group(1)) if match else None


def check_lab_artifacts(subject_dir, number):
    """实操课的 lab 产物是否齐全：lab/<编号>-*/ 有任务文件、lab/solutions/ 非空。"""
    problems = []
    lab_dir = os.path.join(subject_dir, 'lab')
    if not os.path.isdir(lab_dir):
        return [f'实操课缺少 lab/ 目录（{lab_dir}）']

    entries = sorted(os.listdir(lab_dir))
    mine = [name for name in entries
            if re.match(rf'^0*{number}(?![0-9])', name) and name != 'solutions']
    if not mine:
        problems.append(f'lab/ 下没有与课件 {number:04d} 对应的 <编号>-主题 目录或文件')
    else:
        target = os.path.join(lab_dir, mine[0])
        if os.path.isdir(target):
            files = [name for name in os.listdir(target)
                     if not name.startswith('.') and name != '__pycache__']
            if not files:
                problems.append(f'{os.path.join("lab", mine[0])}/ 是空的（没有任务文件）')
        elif os.path.getsize(target) == 0:
            problems.append(f'{os.path.join("lab", mine[0])} 是空文件')

    solutions = os.path.join(lab_dir, 'solutions')
    if not os.path.isdir(solutions):
        problems.append('lab/solutions/ 缺失（参考答案要与任务分开放）')
    elif not [name for name in os.listdir(solutions) if not name.startswith('.')]:
        problems.append('lab/solutions/ 是空的（参考答案要与任务分开放）')
    return problems


def check_lab(text, path, subject, node):
    """检查项 5：实操引用与产物——按节点的 `kind` 条件判定。

    `kind: 实操` / `kind: 实验` → 必须有 lab 链接，且 lab 产物齐全；
    `kind: 概念` → 不该有 lab 链接（有就提示，不阻断）。
    """
    problems = []
    notes = []
    has_link = bool(LAB_LINK_RE.search(text))

    if subject is None or node is None:
        notes.append('跳过实操判定：没给 --subject/--node，无法核对这课该不该有 lab')
        return problems, notes
    if subject.error:
        notes.append(f'跳过实操判定：{subject.error}')
        return problems, notes

    kind = subject.kind_of(node)
    if kind is None:
        notes.append(f'跳过实操判定：大纲里找不到节点 {node}（核对 --node 是否写对）')
        return problems, notes

    if kind in ('实操', '实验'):
        if not has_link:
            problems.append(f'{kind}课缺少实操引用：节点 {node} 的 kind 是「{kind}」，'
                            '页面里必须有 href 指向 lab/ 的链接')
            return problems, notes
        number = lab_number_of(path)
        if number is not None:
            problems += check_lab_artifacts(subject.dir, number)
        return problems, notes

    if kind != '概念':
        notes.append(f'节点 {node} 的 kind 是 {kind!r}，不在「概念/实操/实验」里——按概念课处理')
    if has_link:
        notes.append(f'概念课却链接了 lab/：节点 {node} 的 kind 是「概念」，'
                     '按规范概念课不配实操（只有轻量练习）')
    return problems, notes


# ── 各检查项：阻断项返回问题列表，提示项单独返回 ──────────────────────────


def check_name(path):
    """检查项 1：文件名 NNNN-dash-case.html + 同目录编号规则（R4）。"""
    problems = []
    name = os.path.basename(path)
    match = LESSON_NAME_RE.match(name)
    if not match:
        problems.append(f'文件名 {name!r} 不符合 NNNN-dash-case.html（四位数字 + 小写短横线）')
        return problems

    number = int(match.group(1))
    directory = os.path.dirname(path) or '.'
    try:
        entries = os.listdir(directory)
    except OSError as exc:
        problems.append(f'无法列出所在目录 {directory!r} 以核对编号：{exc.strerror or exc}')
        return problems

    others = []
    for entry in entries:
        if entry == name:
            continue
        other = NUMBERED_NAME_RE.match(entry)
        if other:
            others.append(int(other.group(1)))

    if not others:
        if number != 1:
            problems.append(f'编号 {number:04d} 应为 0001（同目录内这是第一份课件，不能跳号）')
    elif number > max(others):
        expected = max(others) + 1
        if number != expected:
            problems.append(f'编号 {number:04d} 与现有最大编号 {max(others):04d} 不连续，新课件应为 {expected:04d}')
    elif number in others:
        problems.append(f'编号 {number:04d} 在同目录内不唯一（另有 {others.count(number)} 份同编号课件）')
    return problems


def check_shared_refs(text):
    """检查项 2：共享层引用齐全（sayo.css / learn-theme.css / learn-theme.js / sayo.js）。"""
    refs = ref_values(text)
    return [f'共享层引用缺失：{required}' for required in SHARED_REFS
            if not any(required in ref for ref in refs)]


def check_subject_refs(text):
    """检查项 3：科目组件引用齐全（../assets/style.css、../assets/quiz.js）。"""
    refs = ref_values(text)
    return [f'科目组件引用缺失：{required}' for required in SUBJECT_REFS
            if not any(required in ref for ref in refs)]


def check_placeholder(text, path):
    """检查项 7：课件里不得残留手写时代的 `<!-- 题目位置：… -->` 标记（看原文，注释未剥）。"""
    if LESSONS_DIR_MARK not in path.replace(os.sep, '/'):
        return []
    if PLACEHOLDER_RE.search(text):
        return ['课件里还留着未替换的题目位置标记（手写课件留下的占位没删；新流程由渲染器出页面，不会有它）']
    return []


# 检查项 8：上/下节课指针
NAV_ANCHOR_RE = re.compile(r'<a\b[^>]*>', re.I)
CLASS_ATTR_RE = re.compile(r'class\s*=\s*["\']([^"\']*)["\']', re.I)
HREF_ATTR_RE = re.compile(r'href\s*=\s*["\']([^"\']*)["\']', re.I)


def nav_links(text):
    """正文里的上/下节课指针 → {'prev': href, 'next': href}（缺哪个就没有哪个键）。

    只认 class 里带 `lesson-nav__link--prev/--next` 的 <a>；属性顺序不限。
    """
    found = {}
    for tag in NAV_ANCHOR_RE.findall(text):
        classes = CLASS_ATTR_RE.search(tag)
        if not classes or 'lesson-nav__link' not in classes.group(1):
            continue
        direction = None
        if 'lesson-nav__link--prev' in classes.group(1):
            direction = 'prev'
        elif 'lesson-nav__link--next' in classes.group(1):
            direction = 'next'
        if not direction or direction in found:
            continue
        href = HREF_ATTR_RE.search(tag)
        found[direction] = html.unescape(href.group(1)) if href else ''
    return found


def check_naming_and_nav(text, path, subject, node):
    """检查项 8：文件名 = `<序号>-<节点id>.html`，且上/下节课指针正好指向大纲里的邻居。

    这条链路是「悬空指针」成立的前提：上一课的「下节课」按同一命名规则预写，下一课只要照规则起名，
    链接自己就通了（零回填）。所以要拦的就是**名字**与**指针**——名字错了，上一课的指针就是死链；
    指针漏写或指错，链子从中间断掉。

    指向的文件不存在只提示不阻断：下节课通常还没产出，链接着落空是设计内的事。
    """
    problems = []
    notes = []
    if subject is None or node is None:
        notes.append('跳过命名与上下节课指针检查：没给 --subject/--node')
        return problems, notes
    if subject.error:
        if yaml is None:
            notes.append(f'跳过命名与上下节课指针检查：{subject.error}')
        else:
            problems.append(f'无法核对课件归属：{subject.error}')
        return problems, notes

    index = subject.index_of(node)
    if index is None:
        # 归属查不出来 = 这份课件在主页路线图上不存在（曾经的沉默失败：只回显一条提示就放行）
        problems.append(f'节点 {node} 不在 curriculum.yaml 的 nodes: 里——课件必须归属到一个真实存在的节点'
                        f'（否则科目主页的路线图上没有它）；核对 --node 与文件名里的节点 id')
        return problems, notes

    name = os.path.basename(path)
    expected = f'{index:04d}-{node}.html'
    if name != expected:
        problems.append(f'文件名 {name!r} 与大纲不符：节点 {node} 是 nodes: 里第 {index} 个，'
                        f'文件名必须是 {expected}（上一课的「下节课」指针就按这条规则预写）')

    links = nav_links(text)
    prev_id, next_id = subject.neighbors(node)
    for direction, neighbor, number in (('prev', prev_id, index - 1), ('next', next_id, index + 1)):
        label = '上节课' if direction == 'prev' else '下节课'
        want = f'{number:04d}-{neighbor}.html' if neighbor else None
        got = links.get(direction)
        if want is None:
            if got is not None:
                tail = '前面没有节点' if direction == 'prev' else '后面没有节点'
                problems.append(f'这课不该有{label}指针：节点 {node} 在大纲里是第 {index} 个，{tail}'
                                f'——把 .lesson-nav 里 --{direction} 那条删掉')
            continue
        if got is None:
            problems.append(f'缺{label}指针：.lesson-nav 里要有一条 --{direction} 指向 {want}')
            continue
        if got != want:
            problems.append(f'{label}指针指向 {got!r}，应为 {want!r}'
                            '（邻居取自 curriculum.yaml 的 nodes 顺序，标题用该节点 title）')
            continue
        if not os.path.exists(os.path.join(os.path.dirname(path) or '.', want)):
            notes.append(f'{label} {want} 还没产出——悬空指针，属正常（那一课一按此名产出就通）')
    return problems, notes


class HeadingScanner(HTMLParser):
    """收集 <h2> 的文本——小节标题会进侧边目录，太长就换行/扫读变差。"""

    def __init__(self):
        super().__init__()
        self.titles = []
        self._inside = False
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag == 'h2':
            self._inside = True
            self._buf = []

    def handle_endtag(self, tag):
        if tag == 'h2' and self._inside:
            self._inside = False
            text = ''.join(self._buf).strip()
            if text:
                self.titles.append(text)

    def handle_data(self, data):
        if self._inside:
            self._buf.append(data)


def check_section_titles(text):
    """检查项 8（提示）：小节标题长度 ≤ MAX_H2_CHARS；超了只提示，不阻断。"""
    notes = []
    scanner = HeadingScanner()
    scanner.feed(text)
    for title in scanner.titles:
        if len(title) > MAX_H2_CHARS:
            notes.append(f'小节标题「{title}」{len(title)} 字 > {MAX_H2_CHARS}'
                         '（会进左侧目录，窄了要换行）')
    return notes


class QuizScanner(HTMLParser):
    """找出缺少 data-quiz 的 .quiz 块（用途只剩这一条）。

    **data-quiz 的值不走这里取**：属性值用单引号包裹时，值里若出现裸的直角单引号
    （题面里很常见，例如 `expected ';' before 'return'`、`it's`），HTMLParser 会在第一个
    `'` 处把属性截断，后续 JSON 报「Unterminated string」——错误信息指向 JSON，真凶却在取值。
    HTML5 禁止属性值里出现**同种**引号，所以那种写法在浏览器里同样是截断的（不是「合法」）：
    裸 `'` 在单引号属性里、裸 `"` 在双引号属性里都会截断，**必须写成 `&#39;` / `&quot;`**。
    所以取值改用 scan_quiz_blocks()，并由它附带的 check_quiz_attr_delimiters() 把这类
    写法报成 FAIL——正则取值比浏览器宽松，不查的话检查会 OK 而学生的浏览器里炸。
    """

    def __init__(self):
        super().__init__()
        self.missing = 0
        self.found = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if 'quiz' not in (attributes.get('class') or '').split():
            return
        if attributes.get('data-quiz') is None:
            self.missing += 1
        else:
            self.found += 1


# 开始标签 + 其中的 class 属性值（class 值可以用单引号或双引号包裹）。
# 标签取到第一个 > 为止：HTML 属性值里的裸 > 是无效写法（要写 &gt;），
# 所以这样不会误截断，而且与属性书写顺序无关（class 写在 data-quiz 后面也能匹配）。
QUIZ_TAG_RE = re.compile(
    r'<[a-zA-Z][^>]*\bclass\s*=\s*(["\'])(.*?)\1[^>]*>', re.S)
# 标签范围内的 data-quiz 属性：值取到「同类引号 + 空白/标签结束」为止。
# 用 ([\"'])(.*)\1(?=[\s/>]) 而不是非贪婪 .*?：非贪婪会在值里第一个同类引号处就闭合。
# ⚠️ 这个正则比浏览器**宽松**：属性值里出现裸的同类引号时，浏览器会在那里截断属性，
# 而贪婪匹配会一路跨过去、取出「完整」的值交给 json.loads —— 于是 JSON 解析通过、检查报 OK，
# 学生的浏览器里却看到「题目数据解析失败」。所以取值之后必须再跑 check_quiz_attr_delimiters()。
DATA_QUIZ_ATTR_RE = re.compile(r'\bdata-quiz\s*=\s*(["\'])(.*)\1(?=[\s/>])', re.S)


def json_string_spans(raw):
    """把「JSON 文本里处于字符串字面量内部」与「外部」的片段按顺序返回。

    跟踪引号状态时必须处理反斜杠转义：JSON 里的 `\\"` 是字符串**内部**的一个引号，
    不切换状态——不处理它的话，`"expected \\'; \\' before"` 这类值会被误切成
    字符串外，本函数就漏报了（真实题面里 `\\"` 很常见）。
    """
    parts, buf, in_str, escaped = [], [], False, False
    for ch in raw:
        if escaped:
            buf.append(ch)
            escaped = False
            continue
        if ch == '\\':
            buf.append(ch)
            escaped = True
            continue
        if ch == '"':
            parts.append(''.join(buf))
            buf = []
            in_str = not in_str
        else:
            buf.append(ch)
    parts.append(''.join(buf))
    return parts


# 宽松取值：从 `data-quiz=` 后面的引号一直取到标签末尾（不吃标签自身的 `>`）。
# 比浏览器的取值宽松是故意的——取到值之后，由下面的检查判断这份文档在浏览器里
# 会不会被截断；取值本身不必还原浏览器的截断行为，否则就无从判断了。
QUIZ_ATTR_AS_WRITTEN_RE = re.compile(r'\bdata-quiz\s*=\s*(["\'])([^>]*)', re.S)


def data_quiz_delimiter_span(tag):
    """返回 (定界引号, 值片段)；标签里没有 data-quiz 时返回 (None, None)。

    优先取能解码成完整 JSON 的值，避免把后续属性算进题目；畸形值保留到标签末尾，
    其中「裸的同种引号」供 check_quiz_attr_delimiters() 判定。
    """
    match = QUIZ_ATTR_AS_WRITTEN_RE.search(tag)
    if not match:
        return None, None
    delimiter, raw = match.group(1), match.group(2)
    for end in reversed([index for index, char in enumerate(raw) if char == delimiter]):
        try:
            json.loads(html.unescape(raw[:end]))
        except ValueError:
            continue
        return delimiter, raw[:end]
    return delimiter, raw


def bare_delimiter_in_json_strings(raw, delimiter):
    """JSON 字符串字面量**内部**是否出现了裸的定界引号。

    判据是「包含」而不是「相等」：坏写法下整个题面都在同一个字符串里，
    定界符只是其中一个字符（如 `"expected ';' before"` 里的 `'`）。
    """
    return any(delimiter in span
               for index, span in enumerate(json_string_spans(raw))
               if index % 2 == 1)


# 检查项 4：属性值里被实体化的引号（`&quot;` / `&#34;` / `&#x22;`）。
# 单引号包裹时，值里的 JSON **结构引号是裸写的**，所以按书写原样跟踪引号状态就能判断一个
# 实体引号是落在字符串内部（会提前闭合字符串，必须报）还是当结构引号用（多余但合法，不报）。
ENTITY_QUOTE_RE = re.compile(r'&(?:quot|#0*34|#x0*22);', re.I)


def entity_quotes_in_json_strings(raw):
    """落在 JSON 字符串字面量**内部**的实体引号（按书写原样判定）。"""
    spans, offset = [], 0
    for index, part in enumerate(json_string_spans(raw)):
        if index % 2:
            spans.append((offset, offset + len(part)))
        offset += len(part)
    return [match.group(0) for match in ENTITY_QUOTE_RE.finditer(raw)
            if any(start <= match.start() < end for start, end in spans)]


def check_quiz_attr_entities(tag):
    """单引号包裹的 data-quiz 值里，JSON 字符串内部的引号是否写成了实体。

    这种写法浏览器解码后是一个**裸 `"`**，会提前闭合 JSON 字符串：多数情况 JSON.parse 报错、
    题目块显示「解析失败」，少数情况还能解析成功但把后半句吃掉。原有的「合法 JSON」检查
    只会说一句 `Expecting ',' delimiter`，看的人不知道该怎么改——这条把口径说清楚：
    字符串内部的引号写 JSON 自己的 `\\"`，单引号才写实体 `&#39;`。
    """
    delimiter, raw = data_quiz_delimiter_span(tag)
    if delimiter != "'" or not raw:
        return []
    hits = sorted(set(entity_quotes_in_json_strings(raw)))
    if not hits:
        return []
    return [f'data-quiz 用单引号包裹，值里的 JSON 字符串内部却写了实体引号（{"、".join(hits)}）——'
            f'浏览器解码后是一个裸 "，会提前闭合 JSON 字符串（解析失败，或内容被吃掉一截）。'
            f'字符串内部的引号写 JSON 自己的转义 \\"；单引号才写 &#39;']


def check_quiz_attr_truncation(tag):
    """双引号包裹的 data-quiz：值里出现裸 `"`（含写成 `\\"` 的）时属性被浏览器截断。

    为什么必须单独查：`DATA_QUIZ_ATTR_RE` 是贪婪取值，能跨过那个裸引号取出「完整」的值、
    JSON 还解析得通——于是检查放行，而学生看到的是「题目数据解析失败」。
    只在「宽松取值能解析、浏览器口径取到的值解析不了」时报，避免与「不是合法 JSON」重复。
    """
    delimiter, raw = data_quiz_delimiter_span(tag)
    if delimiter != '"' or not raw:
        return []
    try:
        json.loads(html.unescape(raw))                # 宽松取值就解析不了 → 交给「合法 JSON」那条报
    except ValueError:
        return []
    try:
        json.loads(html.unescape(raw.split('"', 1)[0]))  # 浏览器口径：值到第一个裸 " 为止
        return []
    except ValueError:
        pass
    return ['data-quiz 用双引号包裹，值里出现了裸的 "（哪怕写成 \\" 也一样）——浏览器在那里就把属性'
            '截断了，题目块会退化成「题目数据解析失败」。本项目一律用单引号包裹；非要用双引号，'
            '字符串内部的引号写 \\&quot;（反斜杠 + 实体，两个都不能少）']


def check_quiz_attr_delimiters(tag):
    """data-quiz 的值片段里是否含**裸的同类引号**（浏览器会在那里把属性截断）。

    为什么必须单独查：正则取值比浏览器宽松（贪婪跨过裸引号，取出「完整」的值），
    于是 JSON 解析通过、检查报 OK，而学生的浏览器里题目块退化成「题目数据解析失败」。
    判定「坏」的原则：**只认能取出 JSON 合法字符串字面量的那种坏**——
    出现在 JSON 字符串值里的裸定界引号必然截断；出现在字符串之外（如属性尾部的
    空白）则不确定，宁可不报，避免误报。
    """
    delimiter, raw = data_quiz_delimiter_span(tag)
    if not delimiter or not bare_delimiter_in_json_strings(raw, delimiter):
        return []
    if delimiter == "'":
        what, entity = "单引号 '", '&#39;'
        hint = (f"题面里含单引号就写成 {entity}（如 expected {entity};{entity} before）；"
                f"含 < / > 写成 &lt; / &gt;")
    else:
        what, entity = '双引号 "', '&quot;'
        hint = f'值里含双引号就写成 {entity}'
    return [f'data-quiz 用{what}包裹，值里却出现了裸的同种引号——'
            f'浏览器会在那里截断属性，题目块会退化成「题目数据解析失败」。{hint}']


def scan_quiz_blocks(text):
    """取出全部 .quiz 块的 data-quiz 值（顺序与文档一致）。

    匹配口径与 QuizScanner 一致：class 属性按**空白分词**后含 `quiz` 才算题目块
    （这样 `class="foo quiz bar"` 也算），避免用 `\\bquiz\\b` 误伤 `quizlet` 这类类名。
    值里的 HTML 实体（`&quot;` / `&#39;`）解码后再交给 JSON，与浏览器把属性值交给 JS 的行为一致。
    """
    blocks = []
    for tag_match in QUIZ_TAG_RE.finditer(text):
        if 'quiz' not in tag_match.group(2).split():
            continue
        delimiter, raw = data_quiz_delimiter_span(tag_match.group(0))
        if delimiter and DATA_QUIZ_ATTR_RE.search(tag_match.group(0)):
            blocks.append(html.unescape(raw))
    return blocks


def check_quiz_fences(item, label):
    """题面/答案里的 ``` 围栏是否成对（不成对 = 后半段全被当成代码渲染）。

    围栏是 quiz.js 渲染真代码块的写法（缩进与等宽都在里面保证），见它顶部契约。
    只查「成对」这一件结构事：语言标签写不写、写什么由作者定，检查不管。
    """
    problems = []
    for field in ('q', 'answer', 'criteria', 'why'):
        value = item.get(field)
        if not isinstance(value, str):
            continue
        fences = sum(1 for line in value.split('\n') if QUIZ_FENCE_RE.match(line))
        if fences % 2:
            problems.append(f'{label}的 `{field}` 里 ``` 围栏没闭合（起止各占一整行，'
                            f'中间才是代码）——不闭合的话后半段会被整段渲染成代码块')
    return problems


def check_quiz_markdown(item, label):
    """题面/答案的散文里是否用了 Markdown / HTML 标记（字段是纯文本，会原样显示）。

    为什么只提示不阻断：这些标记**不是**语法错误，只是排版预期落空——页面上会露出
    `**`、反引号、尖括号。而键盘上打得出这些字符的正常内容也存在（数学的 `a**b`、
    代码片段被围栏包住时的指针 `int **p`），所以不进阻断项；围栏里的内容一律不看。
    """
    notes = []
    for field in ('q', 'answer', 'criteria', 'why'):
        value = item.get(field)
        if not isinstance(value, str):
            continue
        prose, inside = [], False
        for line in value.split('\n'):
            if QUIZ_FENCE_RE.match(line):
                inside = not inside
                continue
            if not inside:
                prose.append(line)
        body = '\n'.join(prose)
        found = [mark.group(0) for pattern in MARKDOWN_RE for mark in pattern.finditer(body)]
        if found:
            notes.append(f'{label}的 `{field}` 里出现 {"、".join(sorted(set(found))[:3])}'
                         f'——字段是**纯文本**，Markdown/HTML 标记会原样显示（换行用 \\n、'
                         f'代码用 ``` 围栏，见 quiz.js 顶部契约）')
    return notes


def check_quiz(text, required=True):
    """检查项 4：题目结构（阻断）＋选项长度差（提示）。字段契约见 quiz.js 顶部注释。

    `required=False`（实验课的说明页）时，没有题目块不算缺项——那是任务书，不是课件。
    返回 (problems, notes)。
    """
    problems = []
    notes = []
    scanner = QuizScanner()
    scanner.feed(text)
    if scanner.missing:
        problems.append(f'题目块 .quiz 缺少 data-quiz 属性（{scanner.missing} 处）')

    blocks = scan_quiz_blocks(text)
    if blocks and len(blocks) < scanner.found:
        problems.append(f'有 {scanner.found - len(blocks)} 个题目块的 data-quiz 值取不出来——'
                        '检查属性值中的裸 >（写成 &gt;）及引号')
    if not blocks:
        if scanner.found:
            # 块在、属性也在（HTMLParser 是浏览器口径），是**检查的取值正则**取不出来：
            # QUIZ_TAG_RE 的标签取到第一个 `>` 为止，属性值里的裸 `>` 会把标签切断。
            # 页面本身能渲染（HTML5 允许属性值里出现 `>`），所以必须说清是写法问题。
            problems.append(f'题目块在，但 data-quiz 的值取不出来（{scanner.found} 处）——'
                            f'属性值里可能有裸的 `>`（写成 &gt;）或裸的同类引号（写成 &#39;）：'
                            f'检查的取值正则到第一个 `>` 就断了')
        elif not problems and required:
            problems.append('缺少 .quiz[data-quiz] 题目块（每份课件至少一道题）')
        return problems, notes

    # 属性值里裸的同类引号：浏览器会截断，而取值正则不会——必须在这里报出来。
    # 去重：畸形标签可能让 QUIZ_TAG_RE 在同一份文档里命中多次，同一件事只报一遍。
    seen_delimiter_problems = set()
    for tag_match in QUIZ_TAG_RE.finditer(text):
        if 'quiz' not in tag_match.group(2).split():
            continue
        for problem in (check_quiz_attr_delimiters(tag_match.group(0))
                        + check_quiz_attr_entities(tag_match.group(0))
                        + check_quiz_attr_truncation(tag_match.group(0))):
            if problem not in seen_delimiter_problems:
                seen_delimiter_problems.add(problem)
                problems.append(problem)

    for block_index, raw in enumerate(blocks, 1):
        prefix = f'第 {block_index} 个 .quiz 块' if len(blocks) > 1 else '.quiz'
        try:
            items = json.loads(raw)
        except ValueError as exc:
            problems.append(f'{prefix} 的 data-quiz 不是合法 JSON：{exc}')
            continue
        if not isinstance(items, list) or not items:
            problems.append(f'{prefix} 的 data-quiz 应为非空 JSON 数组')
            continue

        for question_index, item in enumerate(items, 1):
            label = f'{prefix} 第 {question_index} 题'
            if not isinstance(item, dict):
                problems.append(f'{label}不是 JSON 对象')
                continue

            question = item.get('q')
            if not isinstance(question, str) or not question.strip():
                problems.append(f'{label}缺题面（q 必须是非空字符串）')

            for problem in check_quiz_fences(item, label):
                problems.append(problem)
            for note in check_quiz_markdown(item, label):
                notes.append(note)

            is_choice = 'opts' in item or 'ans' in item
            is_open = 'answer' in item or 'criteria' in item
            if is_choice and is_open:
                problems.append(f'{label}题型冲突：选择题字段（opts/ans）与开放题字段（answer/criteria）'
                                '只能二选一')
                continue

            if is_choice:
                opts = item.get('opts')
                if not isinstance(opts, list) or len(opts) < 2:
                    problems.append(f'{label}选择题选项结构错误（缺 opts 或选项数 < 2）')
                    continue
                ans = item.get('ans')
                if isinstance(ans, bool) or not isinstance(ans, int) or not 0 <= ans < len(opts):
                    problems.append(f'{label}选择题的 ans 必须是从 0 开始、落在选项范围内的整数'
                                    f'（ans={ans!r}，选项数 {len(opts)}）')
                why = item.get('why')
                if not isinstance(why, str) or not why.strip():
                    problems.append(f'{label}选择题缺 why（答完要显示一句解释）')
                lengths = [len(str(opt)) for opt in opts]
                gap = max(lengths) - min(lengths)
                if gap > MAX_OPT_LEN_GAP:
                    notes.append(f'{label}选项长度差 {gap} > {MAX_OPT_LEN_GAP}'
                                 f'（最长 {max(lengths)} / 最短 {min(lengths)} 字符）')
            elif is_open:
                answer = item.get('answer')
                criteria = item.get('criteria')
                if not isinstance(answer, str) or not answer.strip():
                    problems.append(f'{label}开放题缺参考答案（answer）')
                if not isinstance(criteria, str) or not criteria.strip():
                    problems.append(f'{label}开放题缺判分要点（criteria，学生据此自评）')
            else:
                problems.append(f'{label}题型不明：选择题要 opts/ans/why，开放题要 answer/criteria')
    return problems, notes


class ImgScanner(HTMLParser):
    """收集 <img> 的 src 与 alt（起始标签回调，注释/脚本文本不会进来）。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag != 'img':
            return
        attributes = {name.lower(): value for name, value in attrs}
        self.images.append((attributes.get('src') or '', attributes.get('alt')))


def check_images(text, path):
    """检查项 9：课件里的图片。

    三条，按「学生会不会看到坏东西」判：
      · 本地图不存在 → **阻断**（学生看到裂图；gen_home 的自检只管自己写出的主页，
        课件页明确不在它的范围内，所以这道只能由检查把）
      · 外链图（http/https）→ 提示：离线打开会裂，建议从科目图片库挑一张本地文件
      · 没有 alt → 提示：裂图时学生只看到空白，读屏软件也读不出
    """
    problems = []
    notes = []
    scanner = ImgScanner()
    scanner.feed(text)
    for src, alt in scanner.images:
        value = (src or '').strip()
        if not value:
            problems.append('<img> 没有 src')
            continue
        if SCHEME_RE.match(value):
            notes.append(f'图片用了外链（{value[:60]}）——离线打开会裂；'
                         f'建议从科目图片库 assets/img/pool/ 挑本地文件引用')
        else:
            target = os.path.normpath(os.path.join(os.path.dirname(path) or '.',
                                                   unquote(value.split('#', 1)[0].split('?', 1)[0])))
            if not os.path.isfile(target):
                problems.append(f'图片引用了不存在的文件：{value}（解析到 {target}）')
        if not (alt or '').strip():
            notes.append(f'图片缺 alt（{value[:40]}）：裂图时学生只看到空白')
    return problems, notes


def check_local_refs(text, path):
    """检查项 10：页面里所有本地 href/src 都要能落到真实文件；返回 (problems, notes)。

    gen_home 的断链自检只管它自己写出的主页，课件页不在它的范围内——没有这道，页面缺组件、
    正文里的 lab 链接指错文件，检查全绿而学生点开是白板或 404。

    跳过：外链与锚点（任何 scheme: 或协议相对 //、`#…`）；上/下节课指针（落空是设计内的，
    检查项 8 单独提示）。注释里的路径不会走到这里——`check_file` 传进来的已经是剥过注释的文本。

    **生成产物单算**：`index.html`（壳里那条「返回课程」回链的目标）由 gen_home.py 产出，
    作者产不出来——还没生成时只提示，不阻断（否则每门新科目在跑生成器之前都过不了检查）。
    """
    allowed = {value for value in nav_links(text).values() if value}
    problems = []
    notes = []
    seen = set()
    for value in ref_values(text):
        raw = html.unescape(value).strip()
        if not raw or raw in allowed or raw in seen:
            continue
        target = local_target(path, raw)
        if target is None:
            continue
        seen.add(raw)
        if os.path.exists(target):
            continue
        if os.path.basename(target) == 'index.html':
            notes.append(f'科目主页还没生成（{raw} → {target}）：跑一次 gen_home.py 就有了')
        else:
            problems.append(f'引用了不存在的本地文件：{raw}（解析到 {target}）')
    return problems, notes


def page_has_math(text):
    """页面里有没有数学式：静态占位（`.math-inline` / `.math-block`）**或**题库数据里的 `$…$`。

    题目正文由 quiz.js 在浏览器里排版，渲染产物里只有 `data-quiz` 属性——只看占位元素会漏掉
    「整页的公式都在题面里」那种页面，而那正是线代/概率这类课件的常态。
    """
    if MATH_MARK_RE.search(text):
        return True
    # 属性引号必须**配对**捕获：JSON 的键都是双引号，用 ["'] 会把内容截在第一个 " 上
    return any(MATH_PAIR_RE.search(html.unescape(match.group(2)))
               for match in QUIZ_ATTR_RE.finditer(text))


def check_math_style(text):
    r"""质量线（只提示）：`aligned` 里有两行以上等式，却没被 `\left\{ … \right.` 包住。

    这是方程组最容易被漏掉的一处：KaTeX 不会自己加括号，少了大括号读者会把一列等式当成几个
    独立结论（规格见 docs/课件内容格式.md 第 3 节的「方程组要带大括号」）。判据保守——
    只在「同一段 aligned 里 ≥2 行带 `&=`」且紧邻上文没有 `\left\{` 时提示，推导链
    （`\xrightarrow`）与单条恒等式都不会命中。**只提示，不阻断**：它拦不了交付，只提醒补一下。
    """
    notes = []
    for match in re.finditer(r'\\begin\{aligned\}(.*?)\\end\{aligned\}', text, re.S):
        body = html.unescape(match.group(1))
        if body.count('&=') < 2:
            continue
        if '\\left\\{' in text[max(0, match.start() - 12):match.start()]:
            continue
        notes.append('这段 aligned 有两行以上等式、却没有大括号——方程组要写成 '
                     r'`$$\left\{\begin{aligned} … \end{aligned}\right.$$`'
                     '（KaTeX 不会自己加，见 docs/课件内容格式.md 第 3 节）')
    return notes


def check_math_refs(text):
    """检查项 11：有数学式的页面必须引用离线 KaTeX（三件）。

    条件判定，与检查项 5（按 `kind` 判 lab）同一路数：页面里没有 `.math-inline` / `.math-block`
    就不要求这三个引用。少了它们公式只显示 TeX 原文——能读，但等于没排版。
    """
    if not page_has_math(text):
        return []
    refs = ref_values(text)
    return [f'页面里有数学式，但缺少引用：{required}' for required in MATH_REFS
            if not any(required in ref for ref in refs)]


def check_theme_toggle(text):
    """检查项 6：主题开关元素与接线未丢。"""
    problems = []
    checkbox = None
    for tag in INPUT_RE.findall(text):
        if re.search(r'\bid\s*=\s*["\']' + THEME_CHECKBOX_ID + r'["\']', tag, re.I):
            checkbox = tag
            break
    if checkbox is None:
        problems.append(f'主题开关缺失：找不到 id="{THEME_CHECKBOX_ID}" 的 <input>')
    elif not re.search(r'\btype\s*=\s*["\']checkbox["\']', checkbox, re.I):
        problems.append(f'主题开关损坏：id="{THEME_CHECKBOX_ID}" 的 <input> 不是 type="checkbox"')
    if not re.search(r'LearnTheme\.wire\s*\([^)]*' + THEME_CHECKBOX_ID, text):
        problems.append(f'主题开关接线缺失：没有 LearnTheme.wire(...) 引用 {THEME_CHECKBOX_ID}')
    return problems


def check_file(path, subject=None, node=None):
    """对一个课件跑完所有检查，返回 (problems, notes)：problems 为空 = 无阻断项。"""
    try:
        with open(path, encoding='utf-8') as handle:
            raw = handle.read()
    except UnicodeDecodeError as exc:
        return [f'无法解码文件（需 UTF-8）：{exc.reason}'], []
    except OSError as exc:
        return [f'无法读取文件：{exc.strerror or exc}'], []

    text = strip_comments(raw)
    kind = subject.kind_of(node) if (subject is not None and node is not None
                                     and not subject.error) else None
    quiz_problems, notes = check_quiz(text, required=(kind != '实验'))
    notes += check_section_titles(text)
    lab_problems, lab_notes = check_lab(text, path, subject, node)
    nav_problems, nav_notes = check_naming_and_nav(text, path, subject, node)
    problems = []
    problems += check_name(path)
    problems += check_shared_refs(text)
    problems += check_subject_refs(text)
    problems += quiz_problems
    problems += lab_problems
    problems += nav_problems
    img_problems, img_notes = check_images(text, path)
    problems += img_problems
    ref_problems, ref_notes = check_local_refs(text, path)
    problems += ref_problems
    notes += ref_notes
    notes += check_math_style(text)
    problems += check_math_refs(text)
    problems += check_theme_toggle(text)
    problems += check_placeholder(raw, path)
    return problems, notes + lab_notes + nav_notes + img_notes


def parse_args(argv):
    """位置参数是课件路径；`--subject <科目目录>` 与 `--node <节点id>` 用于实操判定。"""
    paths = []
    subject = None
    node = None
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in ('-h', '--help'):
            print(__doc__)
            raise SystemExit(0)
        if arg in ('--subject', '--node'):
            if index + 1 >= len(argv):
                raise SystemExit(f'{arg} 需要一个值\n\n{__doc__}')
            if arg == '--subject':
                subject = argv[index + 1]
            else:
                node = argv[index + 1]
            index += 2
            continue
        if arg.startswith('-'):
            raise SystemExit(f'未知参数 {arg}\n\n{__doc__}')
        paths.append(arg)
        index += 1
    return paths, subject, node


def main(argv):
    paths, subject_dir, node = parse_args(argv)
    if not paths:
        raise SystemExit(__doc__)
    subject = SubjectData(subject_dir) if subject_dir else None
    failed = False
    for path in paths:
        problems, notes = check_file(path, subject, node)
        if problems:
            failed = True
            print(f'FAIL {path}: ' + '；'.join(problems))
        else:
            print(f'OK   {path}')
        if notes:
            print(f'WARN {path}: ' + '；'.join(notes))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
