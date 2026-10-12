#!/usr/bin/env python3
"""生成根主页与全部科目主页：读模板 → 替换占位符 → 输出到学习工作区。

占位符约定见 docs/工程约束.md 的「模板与生成器的占位符契约」（区块级 SUBJECT_CARDS/ROADMAP/PROJECT/ATTACHMENTS
+ 字段级 TITLE/STATUS/MISSION）；每个占位符要生成的结构见模板里的注释——那份注释是**权威规范**，
改模板与改这里必须同步。

用法：
    python3 scripts/gen_home.py              # 工作区取环境变量或配置（详见 learn_workspace）
    python3 scripts/gen_home.py <workspace>  # 显式指定工作区（验证时可指向 examples/ 的镜像副本）

工作区优先级：位置参数 > STUDYMATE_WORKSPACE > LEARN_WORKSPACE > 配置中的 workspace。
配置可由 STUDYMATE_CONFIG 指定；默认兼容 $DSH_HOME/studymate-config.yaml（~/.dsh）。
显式工作区不需要安装 DSH，也不会读取 DSH 配置。所有相对路径均按当前目录解析。

读：可选工作区配置、<WS>/.learning/subjects/*/、templates/{home-index,subject-index}.html
写：<WS>/index.html、<WS>/.learning/subjects/<slug>/index.html、<WS>/.learning/assets/（幂等覆盖）

写完所有页面后有一道链接自检（find_broken_links）：只扫**本次写出的页面**（根主页 + 各科目主页），
只取**标签里的 href/src 属性**（HTMLParser 的起始标签回调）——正文文本、其它属性的值、
<script>/<style> 里的字符串、HTML 注释都不参与，页面里出现 href= 字样不等于链接；
跳过外部链接（任何 scheme: 或协议相对 //）/ 页内锚点 / 空值，把相对链接按页面所在目录解析；
解析到不存在路径的逐条报到 stderr，并以退出码 1 结束（“少一级目录”这类断链不再静默通过）。
lessons/*.html 是讲解角色写出来的课件、不属于本脚本产物（可能合法地引用尚未生成的文件），不在自检范围内。

只依赖标准库 + pyyaml。缺 curriculum.yaml / progress.yaml 的科目按“没有大纲 / 没有进度”渲染
（不抛异常、不中断整次生成）；模板占位符缺失则报错退出（防止模板被改坏后静默生成残缺页面）。
"""
import glob
import html
import html.parser
import os
import re
import shutil
import sys
import urllib.parse

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, 'templates')

# ══════════════════════════════════════════════════════════════════
# 占位符（区块级：整块替换；字段级：单值，可能多处出现 → 全替换）
# ══════════════════════════════════════════════════════════════════

PLACEHOLDER_HOME_CARDS = '<!-- @LEARN:SUBJECT_CARDS -->'
PLACEHOLDER_ROADMAP = '<!-- @LEARN:ROADMAP -->'
PLACEHOLDER_PROJECT = '<!-- @LEARN:PROJECT -->'
PLACEHOLDER_ATTACHMENTS = '<!-- @LEARN:ATTACHMENTS -->'
PLACEHOLDER_TITLE = '<!-- @LEARN:TITLE -->'
PLACEHOLDER_STATUS = '<!-- @LEARN:STATUS -->'
PLACEHOLDER_MISSION = '<!-- @LEARN:MISSION -->'

# ══════════════════════════════════════════════════════════════════
# 口径（全部来自模板里占位符上方的注释；要调整只改这里）
# ══════════════════════════════════════════════════════════════════

# 科目状态（subject.yaml）→ (徽标 class 后缀, 色点后缀)；徽标文本写 status 原值
SUBJECT_STATUS_TAG = {
    '进行中': ('active', 'blue'),
    '暂停': ('paused', 'yellow'),
    '已完成': ('done', 'green'),
}
# 根主页卡片顺序：正在学的排前面（同状态按科目名）
SUBJECT_STATUS_ORDER = {'进行中': 0, '暂停': 1, '已完成': 2}

# 大纲节点状态（与 schemas/curriculum.schema.json 的 enum 同序；顺序即掌握程度）→ 节点卡 class 后缀
NODE_STATUSES = ('未开始', '学习中', '初步理解', '能独立应用', '需要复习', '已通过项目验证')
NODE_STATUS_CLASS = {
    '未开始': 'todo',
    '学习中': 'learning',
    '初步理解': 'learning',
    '能独立应用': 'done',
    '需要复习': 'review',
    '已通过项目验证': 'verified',
}
# “完成” = 状态达“能独立应用”及以上（按上面的枚举顺序取后半段）
DONE_STATUSES = frozenset(NODE_STATUSES[NODE_STATUSES.index('能独立应用'):])
# 当前节点 = 状态为“学习中”的节点；没有就写“还没开始”
CURRENT_STATUS = '学习中'
NOT_STARTED_TEXT = '还没开始'

# 卡片字段的**软上限**：超了不阻断生成，只在 stderr 提醒（卡片上标题一行省略号、目标两行截断，
# 太长就只剩省略号——大纲是地图，不是教案）。判定规则写在 templates/subject-index.html 的渲染规范里。
TITLE_SOFT_LIMIT = 16          # 节点标题建议 ≤16 个字符（全角按 1 计）
OBJECTIVE_SOFT_LIMIT = 34      # objective 建议 ≤34 个字符

# 模板注释里写死的两段提示文案
PROJECT_NONE_HTML = ('<p class="learn-project__none">还没有挂项目。告诉 agent 你想做什么，'
                     '它会把项目排进路线图，并把里程碑插成实验课。</p>')
ATTACH_EMPTY_HTML = ('<p class="learn-attachments__empty">还没有附件。速查文档、术语表、'
                     '学习记录都会出现在这里。</p>')

# ══════════════════════════════════════════════════════════════════
# HTML 片段模板（结构与 class 照模板注释逐字写）
# ══════════════════════════════════════════════════════════════════

CARD_TEMPLATE = '''<article class="syo-card learn-subject-card" data-status="{status}" data-progress="{progress}" data-mastery="{mastery}">
  <a class="learn-subject-card__link" href=".learning/subjects/{slug}/index.html">
    <div class="learn-subject-card__head">
      <h3 class="learn-subject-card__name">{name}</h3>
      {badge}
    </div>
    <p class="learn-subject-card__current">
      <span class="learn-subject-card__label">当前节点</span>
      <span class="learn-subject-card__value">{current}</span>
    </p>
    {meta}
    <div class="learn-progress">
      <div class="learn-progress__track"><div class="learn-progress__bar" style="width:{pct}"></div></div>
      <div class="learn-progress__meta">
        <span>{done}/{total} 节点 · 掌握度 {mastery_pct}</span>
        <span class="learn-subject-card__go" aria-hidden="true">→</span>
      </div>
    </div>
  </a>
</article>'''

# 有课件的节点：details.learn-slot > summary.learn-node.learn-node--<状态>.learn-node--expandable
NODE_SLOT_TEMPLATE = '''<details class="learn-slot" data-id="{node_id}">
  <summary class="learn-node learn-node--{kind} learn-node--expandable">
    {row}
    {objective}
    {foot}
  </summary>
  <div class="learn-node__children">
{children}
  </div>
</details>'''

# 没有课件的节点：普通 article，标题行写“课件待生成”，不写 caret
NODE_ARTICLE_TEMPLATE = '''<article class="learn-node learn-node--{kind}" data-id="{node_id}" data-status="{status}" data-mastery="{mastery}">
  {row}
  {objective}
  {foot}
</article>'''

LESSON_CHILD_TEMPLATE = '''    <a class="learn-child" href="lessons/{file}">
      <span class="learn-child__dot" aria-hidden="true"></span>
      <span class="learn-child__no">{number}</span>
      <span class="learn-child__title">{title}</span>
    </a>'''

LEVEL_TEMPLATE = '''  <div class="learn-level">
    <div class="learn-level__rail"><span class="learn-level__dot"></span></div>
    <div class="learn-level__body">
      <div class="learn-level__label">第 {level} 层 · {count} 个知识点</div>
      <div class="learn-level__grid">
{cards}
      </div>
    </div>
  </div>'''

PROJECT_CARD_TEMPLATE = '''<div class="learn-project__card">
  <span class="learn-project__label">在做的项目</span>
  <p class="learn-project__current">{current}</p>
  <div class="learn-project__lists">
{lists}
  </div>
</div>'''

PROJECT_LIST_TEMPLATE = '''    <div>
      <span class="learn-project__sub">{label}</span>
      <ul>{items}</ul>
    </div>'''

ATTACH_GROUP_TEMPLATE = '''  <div class="learn-attachments__group">
    <div class="learn-attachments__label">{label}</div>
{rows}
  </div>'''

ATTACH_ROW_TEMPLATE = '''    <a class="learn-attachment" href="{href}">
      <span class="learn-attachment__title">{title}</span>
      <span class="learn-attachment__meta">{meta}</span>
    </a>'''

ATTACHMENT_PAGE_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · {subject_name}</title>
<link rel="stylesheet" href="{assets_rel}/sayo/sayo.css">
<link rel="stylesheet" href="{assets_rel}/learn-theme.css">
{extra_style}
<script src="{assets_rel}/learn-theme.js"></script>
<script>LearnTheme.apply();</script>
<style>
.lesson h1 {{
  margin: var(--syo-space-2, 8px) 0 var(--syo-space-4, 16px);
  font-size: clamp(1.6rem, 3.2vw, 2.25rem);
  font-weight: 700;
  line-height: 1.25;
  letter-spacing: -0.02em;
  color: var(--syo-fg-default);
}}
</style>
</head>
<body class="lesson-body">
<nav class="lesson-bar">
  <a href="{back_href}">← 返回科目</a>
  <span>{subject_name}</span>
  <span class="lesson-bar__no">{tag_name}</span>
  <label class="syo-toggle syo-toggle--theme lesson-bar__toggle" title="切换深浅主题" aria-label="切换深浅主题">
    <input type="checkbox" id="attachment-theme-checkbox" checked>
    <span class="syo-toggle-track"></span>
    <span class="syo-toggle-knob">
      <svg class="syo-toggle-sun" viewBox="0 0 20 20" fill="none" aria-hidden="true"><circle cx="10" cy="10" r="3.5" stroke="#f57c00" stroke-width="1.5"/><path d="M10 2v2.5M10 15.5V18M2 10h2.5M15.5 10H18M4.34 4.34l1.77 1.77M13.89 13.89l1.77 1.77M4.34 15.66l1.77-1.77M13.89 6.11l1.77-1.77" stroke="#f57c00" stroke-width="1.2" stroke-linecap="round"/></svg>
      <svg class="syo-toggle-moon" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M16.5 12.5A6 6 0 019 4.5a6 6 0 007.5 8z" stroke="#5c6bc0" stroke-width="1.5" stroke-linejoin="round"/></svg>
    </span>
  </label>
</nav>

<article class="lesson">
{body}
  <footer class="lesson-footer">
    StudyMate · {footer_title} · 本地学习工作区
  </footer>
</article>

<script src="{assets_rel}/sayo/sayo.js"></script>
<script>LearnTheme.wire(document.getElementById('attachment-theme-checkbox'));</script>
</body>
</html>'''

# ══════════════════════════════════════════════════════════════════
# 小工具
# ══════════════════════════════════════════════════════════════════

# 公共正则
COMMENT_RE = re.compile(r'<!--.*?-->', re.S)
TITLE_RE = re.compile(r'<title\b[^>]*>(.*?)</title>', re.S | re.I)
H1_RE = re.compile(r'<h1\b[^>]*>(.*?)</h1>', re.S | re.I)
FRONTMATTER_RE = re.compile(r'^---\r?\n.*?\r?\n---\r?\n', re.S)
MD_HEADING_RE = re.compile(r'^#\s+(.+?)\s*$', re.M)
WHY_RE = re.compile(r'^##\s*Why\s*$', re.M | re.I)
ANY_HEADING_RE = re.compile(r'^#{1,6}\s', re.M)
SENTENCE_RE = re.compile(r'^(.+?[。！？!?])')
DATE_RE = re.compile(r'(\d{4}-\d{2}-\d{2})')
LESSON_FILE_RE = re.compile(r'^(\d{4})-.*\.html$')
RECORD_FILE_RE = re.compile(r'^(\d{4})-')
SESSION_FILE_RE = re.compile(r'^(\d{4}-\d{2}-\d{2})')
# 链接自检跳过的值：外部链接（任何 scheme:，如 http:/mailto:/ftp:/file:/blob:，
# 以及协议相对地址 //）、页内锚点（#…）、空值
SCHEME_RE = re.compile(r'^(?:[A-Za-z][A-Za-z0-9+.\-]*:|//)')


_WARNED = set()


def warn(message, key=None):
    """警告走 stderr：单个科目出问题不中断整次生成（T13-R4）。

    key 相同的警告只报一次——同一份坏文件会被根主页卡片与科目主页各读一遍。
    """
    if key is not None:
        if key in _WARNED:
            return
        _WARNED.add(key)
    print(f'警告: {message}', file=sys.stderr)


def esc(value, attr=False):
    """HTML 转义：文本节点转义 &<>，属性值再多转义引号。"""
    return html.escape(str(value), quote=attr)


def read_text_once(path):
    """严格 UTF-8 读（仓库自有的模板走这条）；内容文件的异常由 read_text_quiet() 降级。"""
    with open(path, encoding='utf-8') as f:
        return f.read()


def read_text_replace(path):
    """容错读：非 UTF-8 字节替换成 U+FFFD，保证坏编码文件也能读出一份文本。"""
    with open(path, encoding='utf-8', errors='replace') as f:
        return f.read()


def read_text_quiet(path, what):
    """读内容文件（课件 / 附件 / MISSION）：解码失败或读不了都降级，绝不断送整页生成。

    真实下载下来的 reference/*.html 很可能是 GBK 等非 UTF-8 编码（agent 写下的文件同理）：
    严格 UTF-8 会抛 UnicodeDecodeError，一路冒泡到 main 的科目级 except，导致**整个科目页**
    不再更新（路线图停在旧版本、新课件卡片消失）。这里改成：先按 errors='replace' 读入（坏字节
    变问号，标题取不完全但不影响这一页的其它部分），仍失败（权限等 OSError）则返回空串——调用方
    各自退回文件名 / 结构性标题。两种情况都往 stderr 打一条中文警告说明是哪个文件。
    """
    try:
        return read_text_once(path)
    except UnicodeDecodeError as exc:
        warn(f'{what} 不是 UTF-8 编码，按替换字符（?）读入，标题可能不全：{path}（{exc}）')
        try:
            return read_text_replace(path)
        except OSError as exc2:
            warn(f'{what} 读不出来，按“没有内容”处理（退回文件名/结构标题）：{path}（{exc2}）')
            return ''
    except OSError as exc:
        warn(f'{what} 读不出来，按“没有内容”处理（退回文件名/结构标题）：{path}（{exc}）')
        return ''


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)


def load_yaml(path):
    """读 YAML；文件不存在按“没有这份数据”返回 None（缺文件是正常情况，不抛异常）。"""
    if not os.path.isfile(path):
        return None
    with open(path, encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else None


def load_yaml_quiet(path, what):
    """读 YAML：缺文件 / 解析失败都返回 None，解析失败额外告警（坏文件不掀翻整次生成）。"""
    try:
        return load_yaml(path)
    except (yaml.YAMLError, OSError, UnicodeDecodeError) as exc:
        warn(f'{what} 读不出来，按“没有数据”处理：{path}（{exc}）', key=('yaml', path))
        return None


def clamp01(value):
    """0–1 数值兜底：非法值按 0，越界值截断。"""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(1.0, max(0.0, num))


def num_text(value):
    """0–1 的数值写法，如 0.375 / 0.62 / 0（模板注释里的 data-* 就长这样）。"""
    return f'{clamp01(value):g}'


def ratio_text(value):
    """0–1 → 百分比文本，如 0.375 → '37.5%'、0.62 → '62%'、0 → '0%'。"""
    return f'{round(clamp01(value) * 100, 1):g}%'


def date_part(value):
    """updated_at → 日期部分（YYYY-MM-DD）；取不到返回空串（不编造日期）。"""
    if value is None:
        return ''
    if hasattr(value, 'strftime'):        # pyyaml 会把不带引号的 ISO 时间解析成 datetime
        return value.strftime('%Y-%m-%d')
    match = DATE_RE.search(str(value))
    return match.group(1) if match else ''


def strip_comments(text):
    return COMMENT_RE.sub('', text)


def strip_tags(markup):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]*>', '', markup)).strip()


# ══════════════════════════════════════════════════════════════════
# 工作区与共享资源
# ══════════════════════════════════════════════════════════════════

def learn_workspace():
    """优先使用宿主无关的工作区变量；无覆盖时兼容现有 DSH 配置。"""
    for name in ('STUDYMATE_WORKSPACE', 'LEARN_WORKSPACE'):
        ws = os.environ.get(name)
        if ws:
            return os.path.abspath(os.path.expanduser(ws))

    cfg_path = os.environ.get('STUDYMATE_CONFIG') or os.path.join(
        os.environ.get('DSH_HOME') or os.path.expanduser('~/.dsh'), 'studymate-config.yaml')
    cfg_path = os.path.abspath(os.path.expanduser(cfg_path))
    try:
        with open(cfg_path, encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise SystemExit(
            f'无法读取工作区配置 {cfg_path}：{exc}\n'
            '请显式传入工作区路径、设置 STUDYMATE_WORKSPACE，或设置 STUDYMATE_CONFIG。') from None
    if not isinstance(cfg, dict):
        raise SystemExit(f'{cfg_path} 必须是包含 workspace 字段的 YAML 映射')
    ws = cfg.get('workspace')
    if not isinstance(ws, str) or not ws.strip():
        raise SystemExit(f'{cfg_path} 缺少有效的 workspace 路径（必须是非空字符串）')
    return os.path.abspath(os.path.expanduser(ws))


def ensure_shared_assets(ws):
    """把共享层拷进 <WS>/.learning/assets/（幂等覆盖）：sayo/ 与 katex/ 两个整目录，
    加 learn-theme.css/js、learn-mascot.png、lesson-math.js（公式排版，按需被页面引用）。

    缺共享层页面会退化成无样式裸 HTML，所以这一步是硬要求；已存在则覆盖同名文件。
    科目自己的 assets/{style.css,quiz.js} 由建科目流程负责，这里不碰（T13-R3）。
    """
    src = os.path.join(TEMPLATES, 'assets')
    dst = os.path.join(ws, '.learning', 'assets')
    os.makedirs(dst, exist_ok=True)
    for name in ('sayo', 'katex'):
        directory = os.path.join(src, name)
        if not os.path.isdir(directory):
            raise SystemExit(f'缺少共享资源目录 {directory}，请检查模板目录是否完整')
        shutil.copytree(directory, os.path.join(dst, name), dirs_exist_ok=True)
    for name in ('learn-theme.css', 'learn-theme.js', 'learn-mascot.png', 'lesson-math.js'):
        path = os.path.join(src, name)
        if not os.path.isfile(path):
            raise SystemExit(f'缺少共享资源 {path}，请检查模板目录是否完整')
        shutil.copy2(path, os.path.join(dst, name))


# ══════════════════════════════════════════════════════════════════
# 占位符替换（区块级整行替换 / 字段级全替换；缺失即报错退出）
# ══════════════════════════════════════════════════════════════════

def replace_block(template_html, placeholder, html_block, template_name):
    """区块占位符整行替换；缺失则报错（防止模板被改坏后静默残缺）。"""
    if placeholder not in template_html:
        raise SystemExit(f'{template_name} 缺少占位符 {placeholder}，请检查模板与 Global Constraints 约定')
    return template_html.replace(placeholder, html_block, 1)


def replace_field(template_html, placeholder, value, template_name):
    """字段占位符全替换（可能多处出现，如 TITLE 在 <title> 和 <h1>）；缺失同样报错。"""
    if placeholder not in template_html:
        raise SystemExit(f'{template_name} 缺少占位符 {placeholder}，请检查模板与 Global Constraints 约定')
    return template_html.replace(placeholder, value)


# ══════════════════════════════════════════════════════════════════
# 科目数据：subject.yaml + curriculum.yaml + progress.yaml → 卡片/路线图字段
# ══════════════════════════════════════════════════════════════════

def subject_dir(ws, slug):
    return os.path.join(ws, '.learning', 'subjects', slug)


def progress_map(prog):
    """progress.yaml 的 nodes → {节点id: {'status':…, 'mastery':…}}（字段缺省就不放进去）。"""
    raw = (prog or {}).get('nodes')
    out = {}
    if not isinstance(raw, dict):
        return out
    for node_id, state in raw.items():
        if not isinstance(state, dict):
            continue
        item = {}
        if state.get('status'):
            item['status'] = str(state['status'])
        if 'mastery' in state:
            item['mastery'] = state['mastery']
        out[str(node_id)] = item
    return out


def curriculum_nodes(cur, prog, slug=None):
    """大纲节点列表（顺序即展示顺序），状态/掌握度用 progress.yaml 覆盖。

    progress.yaml 里多出来的 id 不属于本大纲：告警后忽略（大纲是课程结构的真值来源）。
    没有大纲时返回 []（调用方据此渲染空路线图）。
    """
    raw_nodes = (cur or {}).get('nodes')
    if not isinstance(raw_nodes, list):
        return []
    live = progress_map(prog)
    nodes = []
    for raw in raw_nodes:
        if not isinstance(raw, dict) or not raw.get('id'):
            continue
        node_id = str(raw['id'])
        state = live.pop(node_id, {})
        status = str(state.get('status') or raw.get('status') or '未开始')
        if slug and status not in NODE_STATUS_CLASS:
            warn(f'{slug}: 节点 {node_id} 的状态 {status!r} 不在 schema 枚举里'
                 f'（按“未开始”的样式渲染，状态文本仍写原值）', key=('node-status', slug, status))
        nodes.append({
            'id': node_id,
            'title': str(raw.get('title') or node_id),
            'kind': str(raw.get('kind') or ''),
            'objective': str(raw.get('objective') or ''),
            'prerequisites': [str(p) for p in (raw.get('prerequisites') or [])],
            'status': status,
            'mastery': clamp01(state['mastery'] if 'mastery' in state else raw.get('mastery', 0)),
        })
    if live and slug:
        warn(f'{slug}: progress.yaml 里有 curriculum.yaml 之外的节点，已忽略：{"、".join(sorted(live))}')
    if slug:
        # 卡片字段的软上限：只提醒，不阻断（细节写进 problem/practice，那些不上卡片）
        long_titles = [n for n in nodes if len(n['title']) > TITLE_SOFT_LIMIT]
        if long_titles:
            sample = '、'.join(f'{n["title"]}（{len(n["title"])}）' for n in long_titles[:3])
            warn(f'{slug}: {len(long_titles)} 个节点标题超过 {TITLE_SOFT_LIMIT} 字，卡片上会被省略号截断'
                 f'（标题写短，细节留给 objective/problem）：{sample}'
                 + ('…' if len(long_titles) > 3 else ''), key=('node-title', slug))
        long_objectives = [n for n in nodes if len(n['objective']) > OBJECTIVE_SOFT_LIMIT]
        if long_objectives:
            sample = '、'.join(f'{n["title"]}（{len(n["objective"])}）' for n in long_objectives[:3])
            warn(f'{slug}: {len(long_objectives)} 个节点的 objective 超过 {OBJECTIVE_SOFT_LIMIT} 字，'
                 f'卡片上只显示两行（建议一句话说清）：{sample}'
                 + ('…' if len(long_objectives) > 3 else ''), key=('node-objective', slug))
    return nodes


def progress_nodes(prog):
    """没有大纲时的节点视图：只有 id 与实时状态（标题缺省用 id），仅供卡片统计。"""
    nodes = []
    for node_id, state in progress_map(prog).items():
        nodes.append({
            'id': node_id,
            'title': node_id,
            'objective': '',
            'prerequisites': [],
            'status': state.get('status') or '未开始',
            'mastery': clamp01(state.get('mastery', 0)),
        })
    return nodes


def subject_nodes(cur, prog, slug=None):
    """卡片统计用的节点视图：有课程大纲就用它；没有就退回 progress.yaml 自己的节点。"""
    if isinstance((cur or {}).get('nodes'), list):
        return curriculum_nodes(cur, prog, slug)
    return progress_nodes(prog)


def node_stats(nodes):
    """(总节点数, 完成节点数, 掌握度平均, 当前节点标题)。

    “完成”= 状态达“能独立应用”及以上；掌握度 = 各节点 mastery 平均（0–1）；
    当前节点 = 状态为“学习中”的节点标题，没有就“还没开始”。没有节点时全部按零值。
    """
    if not nodes:
        return 0, 0, 0.0, NOT_STARTED_TEXT
    done = sum(1 for node in nodes if node['status'] in DONE_STATUSES)
    mastery = sum(node['mastery'] for node in nodes) / len(nodes)
    current = NOT_STARTED_TEXT
    for node in nodes:
        if node['status'] == CURRENT_STATUS:
            current = node['title']
            break
    return len(nodes), done, mastery, current


def subject_summary(slug, ws):
    """读 subject.yaml + curriculum.yaml + progress.yaml，返回根主页卡片字段。

    缺 curriculum / progress 不报错：总节点数按 0、掌握度按 0、日期缺省（T13-R4）。
    """
    sdir = subject_dir(ws, slug)
    subj = load_yaml_quiet(os.path.join(sdir, 'subject.yaml'), f'{slug}/subject.yaml') or {}
    if subj.get('slug') and str(subj['slug']) != slug:
        warn(f'{slug}/subject.yaml 的 slug 是 {subj["slug"]!r}，与目录名不一致'
             f'（页面按目录名生成，请修正数据）', key=('slug', slug))
    cur = load_yaml_quiet(os.path.join(sdir, 'curriculum.yaml'), f'{slug}/curriculum.yaml')
    prog = load_yaml_quiet(os.path.join(sdir, 'progress.yaml'), f'{slug}/progress.yaml')
    status = str(subj.get('status') or '')
    if status and status not in SUBJECT_STATUS_TAG:
        warn(f'{slug}/subject.yaml 的状态 {status!r} 不在 schema 枚举里'
             f'（徽标不带颜色，状态文本仍写原值）', key=('subject-status', slug, status))
    total, done, mastery, current = node_stats(subject_nodes(cur, prog))
    return {
        'slug': slug,
        'name': str(subj.get('name') or slug),
        'status': status,
        'total': total,
        'done': done,
        'progress': (done / total) if total else 0.0,
        'mastery': mastery,
        'current': current,
        'date': date_part((prog or {}).get('updated_at')),
    }


# ══════════════════════════════════════════════════════════════════
# 渲染：根主页（科目卡片）
# ══════════════════════════════════════════════════════════════════

def status_tag(status, classes):
    """科目状态徽标：文本写 subject.yaml 原值；未知状态只出中性徽标，不编造颜色。"""
    tag = SUBJECT_STATUS_TAG.get(status)
    if not tag:
        return f'<span class="{esc(classes, attr=True)}">{esc(status or "未知状态")}</span>'
    kind, dot = tag
    return (f'<span class="{esc(classes, attr=True)} learn-status--{kind}">{esc(status)}'
            f'<span class="syo-tag-dot syo-tag-dot--{dot}"></span></span>')


def render_cards_html(subjects):
    """全部科目卡片（learn-subject-list > syo-card.learn-subject-card）；无科目也输出空列表。"""
    cards = []
    for item in subjects:
        meta = (f'<p class="learn-subject-card__meta">上次学习 <time>{esc(item["date"])}</time></p>'
                if item['date'] else
                '<p class="learn-subject-card__meta">还没开始学习</p>')
        cards.append(CARD_TEMPLATE.format(
            status=esc(item['status'], attr=True),
            progress=num_text(item['progress']),
            mastery=num_text(item['mastery']),
            slug=esc(urllib.parse.quote(item['slug'], safe=''), attr=True),
            name=esc(item['name']),
            badge=status_tag(item['status'], 'syo-tag learn-subject-card__status'),
            current=esc(item['current']),
            meta=meta,
            pct=ratio_text(item['progress']),
            done=item['done'],
            total=item['total'],
            mastery_pct=f'{round(item["mastery"] * 100)}%',
        ))
    if not cards:
        return '<div class="learn-subject-list"></div>'
    return '<div class="learn-subject-list">\n' + '\n'.join(cards) + '\n</div>'


def render_home_index(subjects, ws):
    """读 templates/home-index.html → 替换占位符 → 写 <WS>/index.html。"""
    template = read_text_once(os.path.join(TEMPLATES, 'home-index.html'))
    page = replace_block(template, PLACEHOLDER_HOME_CARDS, render_cards_html(subjects), 'home-index.html')
    write_text(os.path.join(ws, 'index.html'), page)


# ══════════════════════════════════════════════════════════════════
# 渲染：科目主页（使命 / 状态 / 项目 / 路线图 / 附件）
# ══════════════════════════════════════════════════════════════════

def mission_excerpt(slug, ws):
    """使命一句话：MISSION.md 的 Why 第一句（没有 Why 段就退回正文第一段）；取不到返回空串。"""
    path = os.path.join(subject_dir(ws, slug), 'MISSION.md')
    if not os.path.isfile(path):
        return ''
    text = read_text_quiet(path, 'MISSION.md')
    match = WHY_RE.search(text)
    if match:
        rest = text[match.end():]
        nxt = ANY_HEADING_RE.search(rest)
        body = rest[:nxt.start()] if nxt else rest
    else:
        body = text
    paragraph = ''
    for line in body.splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            paragraph = line
            break
    sentence = SENTENCE_RE.match(paragraph)
    return sentence.group(1).strip() if sentence else paragraph


def milestone_text(item):
    """旧结构里里程碑条目 → 文案（纯字符串或 {text, nodes, done}）；新模型已经没有里程碑条目。"""
    if isinstance(item, dict):
        return str(item.get('text') or '').strip()
    return str(item or '').strip()


def milestone_done(item):
    """新结构看 `done` 布尔；旧结构（字符串）一律算未完成。"""
    return bool(item.get('done')) if isinstance(item, dict) else False


def render_project_html(prog):
    """「在做的项目」卡片（progress.yaml 的 `project.current`）；没有项目时输出 .learn-project__none 提示。

    里程碑**不在这里**——它们是 curriculum.yaml 里 `kind: 实验` 的节点，由路线图渲染（带「实验」徽标）。
    旧结构（`project.milestones` / `project.done` 字符串数组）仍然兼容读，便于工作区数据迁移期间页面不空。
    """
    project = (prog or {}).get('project')
    if not isinstance(project, dict) or not str(project.get('current') or '').strip():
        return PROJECT_NONE_HTML

    milestones = project.get('milestones')
    if not isinstance(milestones, list):
        milestones = []
    done_items = []
    todo_items = []
    for item in milestones:
        text = milestone_text(item)
        if not text:
            continue
        (done_items if milestone_done(item) else todo_items).append(text)

    legacy_done = project.get('done')
    if isinstance(legacy_done, list):
        done_items = [str(item).strip() for item in legacy_done if str(item or '').strip()] + done_items

    lists = []
    for label, items in (('已完成', done_items), ('待推进', todo_items)):
        if not items:
            continue          # 空列表整块省略
        lis = ''.join(f'<li>{esc(item)}</li>' for item in items)
        lists.append(PROJECT_LIST_TEMPLATE.format(label=esc(label), items=lis))
    if not lists:
        return ('<div class="learn-project__card">\n'
                '  <span class="learn-project__label">在做的项目</span>\n'
                f'  <p class="learn-project__current">{esc(str(project["current"]).strip())}</p>\n'
                '</div>')
    return PROJECT_CARD_TEMPLATE.format(current=esc(str(project['current']).strip()),
                                        lists='\n'.join(lists))


def lesson_files(slug, ws):
    """lessons/*.html → [(编号, 文件名, 完整路径)]，按编号升序。"""
    rows = []
    for path in glob.glob(os.path.join(glob.escape(subject_dir(ws, slug)), 'lessons', '*.html')):
        name = os.path.basename(path)
        match = LESSON_FILE_RE.match(name)
        rows.append((match.group(1) if match else '', name, path))
    rows.sort(key=lambda row: (row[0] or 'zzzz', row[1]))
    return rows


def lesson_title(path):
    """课件标题：<h1> → <title> → 文件名；先剥注释，免得吃到头部说明里的示例标签。"""
    text = strip_comments(read_text_quiet(path, '课件'))
    for pattern in (H1_RE, TITLE_RE):
        match = pattern.search(text)
        if match:
            title = html.unescape(strip_tags(match.group(1)))
            if title:
                return title
    return os.path.splitext(os.path.basename(path))[0]


def lesson_node_id(name, known_ids):
    """课件归属的节点 id：**只认文件名** `<序号>-<节点id>.html`（认不出返回 None）。

    归属只有一个来源，别再从页头文字反推：文件名里编号与节点 id 都是硬规则
    （`lesson-design` 管着、`check_lesson.py` 的检查项 8 按 curriculum.yaml 校验），
    而页头是写给学生看的可读文字（「0001 · 第一份能提交的代码」）。两个来源各推一次，
    对不上时谁也看不出来——归属只留这一个。
    """
    match = LESSON_FILE_RE.match(name)
    if not match:
        return None
    node_id = name[len(match.group(1)) + 1:-len('.html')]
    return node_id if node_id in known_ids else None


def lessons_by_node(slug, ws, nodes):
    """节点 id → [(编号, 文件名, 标题)]（按编号升序）；挂不上节点的课件告警后跳过。"""
    grouped = {}
    known_ids = {str(node['id']) for node in nodes if node.get('id')}
    for number, name, path in lesson_files(slug, ws):
        node_id = lesson_node_id(name, known_ids)
        if node_id is None:
            match = LESSON_FILE_RE.match(name)
            got = name[len(match.group(1)) + 1:-len('.html')] if match else None
            reason = (f'文件名里的节点 id {got!r} 不在 curriculum.yaml 的 nodes: 里'
                      if got else '文件名不是 <序号>-<节点id>.html（4 位序号）')
            warn(f'{slug}: 课件 {name} 挂不到路线图上（已跳过）——{reason}')
            continue
        grouped.setdefault(node_id, []).append((number, name, lesson_title(path)))
    return grouped


def node_levels(nodes):
    """按 prerequisites 算最长路径层级（第 1 层 = 无前置）；未知前置忽略，成环也不死循环。"""
    known = {node['id'] for node in nodes}
    prereq = {node['id']: [p for p in node['prerequisites'] if p in known] for node in nodes}
    depth, on_stack = {}, set()
    for node in nodes:
        if node['id'] in depth:
            continue
        stack = [(node['id'], False)]
        while stack:
            node_id, resolved = stack.pop()
            if resolved:
                on_stack.discard(node_id)
                parents = [depth[p] for p in prereq[node_id] if p in depth]
                depth[node_id] = 0 if not parents else 1 + max(parents)
                continue
            if node_id in depth or node_id in on_stack:
                continue                  # 回边：跳过这条，别绕圈
            on_stack.add(node_id)
            stack.append((node_id, True))
            for parent in prereq[node_id]:
                if parent not in depth and parent not in on_stack:
                    stack.append((parent, False))
    levels = {}
    for node in nodes:
        levels.setdefault(depth.get(node['id'], 0), []).append(node)
    return levels


def prereq_chips(node, nodes):
    """前置标签：写 prerequisites 里每个 id 对应的节点 title；没有前置写“无”。"""
    titles = {n['id']: n['title'] for n in nodes}
    chips = ''.join(f'<span class="learn-node__chip">{esc(titles.get(p, p))}</span>'
                    for p in node['prerequisites'])
    return chips or '<span class="learn-node__chip learn-node__chip--none">无</span>'


def render_node_html(node, nodes, lessons):
    """一张节点卡：有课件 → details.learn-slot + summary.learn-node + 子卡片组；没有 → article。"""
    status = node['status']
    kind = NODE_STATUS_CLASS.get(status, 'todo')
    pct = f'{round(node["mastery"] * 100)}%'
    now = '<span class="learn-node__now">当前</span>' if status == CURRENT_STATUS else ''
    badge = ('<span class="learn-node__kind">实验</span>'
             if str(node.get('kind') or '').strip() == '实验' else '')
    # 卡片上标题一行省略号、目标两行截断；全文放进 title 属性，鼠标悬停能看全（截断只影响显示，信息不丢）
    title_attr = f' title="{esc(node["title"], attr=True)}"'
    objective = (f'<span class="learn-node__objective" title="{esc(node["objective"], attr=True)}">{esc(node["objective"])}</span>'
                 if node['objective'] else '')
    foot = ('<span class="learn-node__foot">'
            f'<span class="learn-node__prereq">前置 {prereq_chips(node, nodes)}</span>'
            f'<span class="learn-node__mastery"><i style="width:{pct}"></i></span>'
            f'<span class="learn-node__pct">{pct}</span>'
            '</span>')
    if lessons:
        row = ('<span class="learn-node__row">'
               '<span class="learn-node__dot"></span>'
               f'<span class="learn-node__title"{title_attr}>{esc(node["title"])}</span>'
               f'{badge}'
               f'{now}'
               f'<span class="learn-node__status">{esc(status)}</span>'
               '<span class="learn-node__caret" aria-hidden="true"></span>'
               '</span>')
        children = '\n'.join(LESSON_CHILD_TEMPLATE.format(
            file=esc(urllib.parse.quote(name, safe=''), attr=True), number=esc(number), title=esc(title))
            for number, name, title in lessons)
        return NODE_SLOT_TEMPLATE.format(node_id=esc(node['id'], attr=True), kind=kind,
                                         row=row, objective=objective, foot=foot, children=children)
    row = ('<span class="learn-node__row">'
           '<span class="learn-node__dot"></span>'
           f'<span class="learn-node__title"{title_attr}>{esc(node["title"])}</span>'
           f'{badge}'
           f'{now}'
           '<span class="learn-node__nolesson">课件待生成</span>'
           '</span>')
    return NODE_ARTICLE_TEMPLATE.format(node_id=esc(node['id'], attr=True), kind=kind,
                                        status=esc(status, attr=True),
                                        mastery=num_text(node['mastery']),
                                        row=row, objective=objective, foot=foot)


def render_roadmap_html(slug, cur, prog, ws):
    """分层路线图（learn-roadmap > learn-level > learn-node）；没有大纲时返回空字符串。

    （ws 是骨架之外必须补的参数：课件在 <WS>/.learning/subjects/<slug>/lessons/ 下。）
    """
    nodes = curriculum_nodes(cur, prog, slug)
    if not nodes:
        return ''
    lessons = lessons_by_node(slug, ws, nodes)
    levels = node_levels(nodes)
    blocks = []
    for level in sorted(levels):
        cards = '\n'.join(render_node_html(node, nodes, lessons.get(node['id'], []))
                          for node in levels[level])
        blocks.append(LEVEL_TEMPLATE.format(level=level + 1, count=len(levels[level]), cards=cards))
    return '<div class="learn-roadmap">\n' + '\n'.join(blocks) + '\n</div>'


def reference_items(sdir):
    """参考文档：reference/*.html（标题取页面标题，退文件名；meta 写所在目录）。"""
    items = []
    for path in sorted(glob.glob(os.path.join(glob.escape(sdir), 'reference', '*.html'))):
        name = os.path.basename(path)
        title = os.path.splitext(name)[0]
        match = TITLE_RE.search(strip_comments(read_text_quiet(path, '参考文档')))
        if match:
            title = html.unescape(strip_tags(match.group(1))) or title
        items.append((f'reference/{name}', title, 'reference/'))
    return items


def render_inline_markdown(text):
    code_spans = []

    def save_code(m):
        code_spans.append(m.group(1))
        return f'\x00CODE_{len(code_spans)-1}\x00'

    text = re.sub(r'`([^`]+)`', save_code, text)
    text = html.escape(text, quote=False)

    def make_img(m):
        alt, src = m.group(1), m.group(2)
        clean_src = esc(src.strip(), attr=True)
        clean_alt = esc(alt.strip(), attr=True)
        return f'<img src="{clean_src}" alt="{clean_alt}">'

    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', make_img, text)

    def make_link(m):
        label, url = m.group(1), m.group(2)
        clean_url = esc(url.strip(), attr=True)
        extra = ' target="_blank" rel="noopener"' if SCHEME_RE.match(url.strip()) else ''
        return f'<a href="{clean_url}"{extra}>{label}</a>'

    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', make_link, text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\w)_([^_]+)_(?!\w)', r'<em>\1</em>', text)
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', text)
    text = re.sub(r'~~([^~]+)~~', r'<del>\1</del>', text)

    def restore_code(m):
        idx = int(m.group(1))
        return f'<code>{html.escape(code_spans[idx], quote=False)}</code>'

    text = re.sub(r'\x00CODE_(\d+)\x00', restore_code, text)
    return text


def markdown_to_html(md_text):
    md_text = FRONTMATTER_RE.sub('', md_text, count=1)
    lines = md_text.replace('\r\n', '\n').split('\n')
    output = []
    i = 0
    n = len(lines)

    in_list = False
    list_type = 'ul'

    def close_list():
        nonlocal in_list, list_type
        if in_list:
            output.append(f'</{list_type}>')
            in_list = False

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith('```'):
            close_list()
            lang = stripped[3:].strip()
            code_lines = []
            i += 1
            while i < n and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            i += 1
            code_str = html.escape('\n'.join(code_lines))
            cls = f' class="language-{esc(lang, attr=True)}"' if lang else ''
            output.append(f'<pre><code{cls}>{code_str}</code></pre>')
            continue

        if not stripped:
            close_list()
            i += 1
            continue

        if re.match(r'^(?:---|\*\*\*|___)\s*$', stripped):
            close_list()
            output.append('<hr>')
            i += 1
            continue

        h_match = re.match(r'^(#{1,6})\s+(.*)$', stripped)
        if h_match:
            close_list()
            level = len(h_match.group(1))
            h_content = render_inline_markdown(h_match.group(2))
            output.append(f'<h{level}>{h_content}</h{level}>')
            i += 1
            continue

        if stripped.startswith('>'):
            close_list()
            quote_lines = []
            while i < n and lines[i].strip().startswith('>'):
                quote_lines.append(re.sub(r'^>\s?', '', lines[i].strip()))
                i += 1
            q_paras = []
            cur_p = []
            for ql in quote_lines:
                if not ql:
                    if cur_p:
                        q_paras.append('<br>'.join(render_inline_markdown(x) for x in cur_p))
                        cur_p = []
                else:
                    cur_p.append(ql)
            if cur_p:
                q_paras.append('<br>'.join(render_inline_markdown(x) for x in cur_p))
            q_html = ''.join(f'<p>{p}</p>' for p in q_paras)
            output.append(f'<blockquote>{q_html}</blockquote>')
            continue

        if stripped.startswith('|') and i + 1 < n and re.match(r'^\s*\|?[\s\-:|]+\|?\s*$', lines[i+1].strip()):
            close_list()
            headers = [c.strip() for c in stripped.strip('|').split('|')]
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith('|'):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                rows.append(cells)
                i += 1

            tbl = ['<div class="syo-table-wrap"><table class="syo-table"><thead><tr>']
            for h in headers:
                tbl.append(f'<th>{render_inline_markdown(h)}</th>')
            tbl.append('</tr></thead><tbody>')
            for r in rows:
                tbl.append('<tr>')
                for idx, c in enumerate(r):
                    cell_html = render_inline_markdown(c) if idx < len(r) else ''
                    tbl.append(f'<td>{cell_html}</td>')
                tbl.append('</tr>')
            tbl.append('</tbody></table></div>')
            output.append(''.join(tbl))
            continue

        ul_match = re.match(r'^[-*+]\s+(.*)$', stripped)
        ol_match = re.match(r'^\d+\.\s+(.*)$', stripped)
        if ul_match or ol_match:
            cur_type = 'ol' if ol_match else 'ul'
            content = [ol_match.group(1) if ol_match else ul_match.group(1)]
            i += 1
            while i < n:
                next_raw = lines[i]
                next_s = next_raw.strip()
                if not next_s:
                    if i + 1 < n and (lines[i+1].startswith('  ') or lines[i+1].startswith('\t')):
                        i += 1
                        continue
                    else:
                        break
                if re.match(r'^([-*+]|\d+\.)\s+', next_s):
                    break
                if next_raw.startswith('  ') or next_raw.startswith('\t'):
                    content.append(next_s)
                    i += 1
                else:
                    break

            if in_list and list_type != cur_type:
                close_list()
            if not in_list:
                in_list = True
                list_type = cur_type
                output.append(f'<{list_type}>')
            item_html = '<br>'.join(render_inline_markdown(c) for c in content)
            output.append(f'<li>{item_html}</li>')
            continue

        close_list()
        para_lines = [stripped]
        i += 1
        while i < n:
            next_s = lines[i].strip()
            if not next_s or next_s.startswith('#') or next_s.startswith('>') or next_s.startswith('```') or re.match(r'^([-*+]|\d+\.)\s+', next_s) or next_s.startswith('|'):
                break
            para_lines.append(next_s)
            i += 1
        p_content = '<br>'.join(render_inline_markdown(pl) for pl in para_lines)
        output.append(f'<p>{p_content}</p>')

    close_list()
    return '\n'.join(output)


def compile_attachment(sdir, rel_md_path, title, subject_name, tag_name):
    """把 md 附件编译为同名 html，返回相对 sdir 的 html 路径；出错则告警并退回原 md 路径。"""
    md_abs = os.path.join(sdir, rel_md_path)
    if not os.path.isfile(md_abs):
        return rel_md_path
    rel_base, _ = os.path.splitext(rel_md_path)
    rel_html = f'{rel_base}.html'
    html_abs = os.path.join(sdir, rel_html)
    try:
        raw_text = read_text_quiet(md_abs, f'附件 {rel_md_path}')
        clean_text = FRONTMATTER_RE.sub('', raw_text, count=1)
        body = markdown_to_html(raw_text)
        if not MD_HEADING_RE.search(clean_text):
            body = f'<h1>{esc(title)}</h1>\n' + body

        parts = os.path.normpath(rel_html).split(os.sep)
        depth = len(parts) - 1
        assets_rel = ('../' * (depth + 2)) + 'assets'
        back_href = ('../' * depth) + 'index.html'

        style_abs = os.path.join(sdir, 'assets', 'style.css')
        if os.path.isfile(style_abs):
            style_rel = ('../' * depth) + 'assets/style.css'
            extra_style = f'<link rel="stylesheet" href="{esc(style_rel, attr=True)}">'
        else:
            extra_style = ''

        rendered = ATTACHMENT_PAGE_TEMPLATE.format(
            title=esc(title),
            subject_name=esc(subject_name),
            assets_rel=esc(assets_rel, attr=True),
            extra_style=extra_style,
            back_href=esc(back_href, attr=True),
            tag_name=esc(tag_name),
            body=body,
            footer_title=esc(title),
        )
        write_text(html_abs, rendered)
        return rel_html
    except Exception as exc:
        warn(f'编译附件 {rel_md_path} 到 HTML 失败，回退到原文件：{exc}')
        return rel_md_path


def resource_items(sdir, subject_name=None):
    """术语与资源：GLOSSARY.md / RESOURCES.md（存在才列，编译成 HTML 保证本地浏览器排版正常）。"""
    items = []
    subj_name = subject_name or os.path.basename(sdir)
    for name, title in (('GLOSSARY.md', '术语表'), ('RESOURCES.md', '资源清单')):
        if os.path.isfile(os.path.join(sdir, name)):
            href = compile_attachment(sdir, name, title, subj_name, title)
            items.append((href, title, name))
    return items


def md_title(path, fallback):
    """md 附件标题：正文首个一级标题 → 结构性回退标题（如“学习记录 0012”）。"""
    text = FRONTMATTER_RE.sub('', read_text_quiet(path, '附件'), count=1)
    match = MD_HEADING_RE.search(text)
    return match.group(1).strip() if match else fallback


def learning_record_items(sdir, subject_name=None):
    """学习记录：learning-records/*.md，按编号升序（编译为 HTML 离线查看）。"""
    rows = []
    for path in glob.glob(os.path.join(glob.escape(sdir), 'learning-records', '*.md')):
        name = os.path.basename(path)
        match = RECORD_FILE_RE.match(name)
        rows.append((match.group(1) if match else 'zzzz', name, path))
    rows.sort(key=lambda row: (row[0], row[1]))
    items = []
    subj_name = subject_name or os.path.basename(sdir)
    for number, name, path in rows:
        fallback = f'学习记录 {number}' if number != 'zzzz' else os.path.splitext(name)[0]
        title = md_title(path, fallback)
        rel_md = f'learning-records/{name}'
        href = compile_attachment(sdir, rel_md, title, subj_name, '学习记录')
        items.append((href, title, rel_md))
    return items


def session_items(sdir, subject_name=None):
    """会话摘要：sessions/*.md，按日期倒序（最新的在前，编译为 HTML 离线查看）。"""
    rows = []
    for path in glob.glob(os.path.join(glob.escape(sdir), 'sessions', '*.md')):
        name = os.path.basename(path)
        match = SESSION_FILE_RE.match(name)
        rows.append((match.group(1) if match else '', name, path))
    rows.sort(key=lambda row: (row[0], row[1]), reverse=True)
    items = []
    subj_name = subject_name or os.path.basename(sdir)
    for date, name, path in rows:
        fallback = f'{date} 会话摘要' if date else os.path.splitext(name)[0]
        title = md_title(path, fallback)
        rel_md = f'sessions/{name}'
        href = compile_attachment(sdir, rel_md, title, subj_name, '会话摘要')
        items.append((href, title, rel_md))
    return items


def render_attachments_html(slug, ws, subject_name=None):
    """附件分组（参考文档/术语与资源/学习记录/会话摘要）；空分组整组省略，全空出空状态。"""
    sdir = subject_dir(ws, slug)
    if not subject_name:
        subj = load_yaml_quiet(os.path.join(sdir, 'subject.yaml'), f'{slug}/subject.yaml') or {}
        subject_name = str(subj.get('name') or slug)
    groups = (
        ('参考文档', reference_items(sdir)),
        ('术语与资源', resource_items(sdir, subject_name)),
        ('学习记录', learning_record_items(sdir, subject_name)),
        ('会话摘要', session_items(sdir, subject_name)),
    )
    blocks = []
    for label, items in groups:
        if not items:
            continue
        rows = '\n'.join(ATTACH_ROW_TEMPLATE.format(
            href=esc(urllib.parse.quote(href), attr=True), title=esc(title), meta=esc(meta))
            for href, title, meta in items)
        blocks.append(ATTACH_GROUP_TEMPLATE.format(label=esc(label), rows=rows))
    if not blocks:
        return ATTACH_EMPTY_HTML
    return '\n'.join(blocks)


def render_subject_index(slug, cur, prog, ws):
    """读 templates/subject-index.html → 替换区块+字段占位符 → 写科目目录 index.html。"""
    sdir = subject_dir(ws, slug)
    subj = load_yaml_quiet(os.path.join(sdir, 'subject.yaml'), f'{slug}/subject.yaml') or {}
    subj_name = str(subj.get('name') or slug)
    template = read_text_once(os.path.join(TEMPLATES, 'subject-index.html'))
    page = replace_field(template, PLACEHOLDER_TITLE, esc(subj_name), 'subject-index.html')
    page = replace_field(page, PLACEHOLDER_STATUS,
                         status_tag(subj.get('status'), 'syo-tag learn-status'), 'subject-index.html')
    page = replace_field(page, PLACEHOLDER_MISSION, esc(mission_excerpt(slug, ws)), 'subject-index.html')
    page = replace_block(page, PLACEHOLDER_PROJECT, render_project_html(prog), 'subject-index.html')
    page = replace_block(page, PLACEHOLDER_ROADMAP, render_roadmap_html(slug, cur, prog, ws), 'subject-index.html')
    page = replace_block(page, PLACEHOLDER_ATTACHMENTS, render_attachments_html(slug, ws, subj_name), 'subject-index.html')
    write_text(os.path.join(sdir, 'index.html'), page)


# ══════════════════════════════════════════════════════════════════
# 生成后自检：页内 href/src 相对链接是否解析到真实存在的路径
# ══════════════════════════════════════════════════════════════════

class LinkAttrParser(html.parser.HTMLParser):
    """只收起始标签里的 href/src 属性值（双引号 / 单引号 / 不带引号三种写法都收）。

    正文文本、其它属性的值、<script>/<style> 里的字符串都不是标签属性，不会走到
    handle_starttag；HTML 注释同样不经过它——所以页面里出现 href= 字样不等于链接。
    属性值里的字符实体由 HTMLParser 反转义（这里不再调 html.unescape，免得双重反转义）。
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if value and name.lower() in ('href', 'src'):
                self.links.append(value)


def page_links(page_path):
    """单页里的 (属性原值, 去锚点/查询串后的链接路径) 列表。

    只扫标签里的 href/src 属性：正文文本、其它属性的值、<script>/<style> 里的字符串、
    HTML 注释都不参与（注释本来就不会走 handle_starttag）。跳过空值、页内锚点（#…）
    与外部链接（任何 scheme: 或协议相对 //）。
    """
    parser = LinkAttrParser()
    parser.feed(read_text_quiet(page_path, '生成页面'))
    parser.close()
    links = []
    for value in parser.links:
        value = value.strip()
        if not value or value.startswith('#'):
            continue
        if SCHEME_RE.match(value):
            continue
        path = value.split('#', 1)[0].split('?', 1)[0]
        if path:
            links.append((value, path))
    return links


def resolve_link_target(page_path, link_path, ws):
    """链接路径 → 绝对路径：相对链接按页面所在目录解析；以 / 开头的按站点根（工作区）解析。

    百分号转义先解码（文件名可能带中文 / 空格）；只做存在性判断，不要求目标是文件（目录也算命中）。
    """
    link_path = urllib.parse.unquote(link_path)
    if link_path.startswith('/'):
        return os.path.normpath(os.path.join(ws, link_path.lstrip('/')))
    return os.path.normpath(os.path.join(os.path.dirname(page_path), link_path))


def find_broken_links(pages, ws):
    """自检：返回 [(页面, 属性原值, 解析后的目标路径)]，只收解析到不存在路径的那些。

    pages 传生成器自己写出的页面（根主页 + 各科目主页）——课件由讲解角色写、不属于本脚本
    产物，可能合法地引用尚未生成的文件，不在这里扫。
    """
    broken = []
    for page in pages:
        for value, link_path in page_links(page):
            target = resolve_link_target(page, link_path, ws)
            if not os.path.exists(target):
                broken.append((page, value, target))
    return broken


# ══════════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════════

def main(argv):
    if any(arg in ('-h', '--help') for arg in argv):
        print(__doc__)
        return 0
    args = [arg for arg in argv if not arg.startswith('-')]
    if len(args) > 1:
        raise SystemExit('用法：python3 scripts/gen_home.py [workspace]')
    # 显式路径优先于环境变量和配置，适合插件宿主或多个独立学习工作区。
    ws = os.path.abspath(os.path.expanduser(args[0])) if args else learn_workspace()
    if not os.path.isdir(ws):
        raise SystemExit(f'工作区不存在：{ws}（请先创建目录，或传入正确的工作区路径）')

    subjects_dir = os.path.join(ws, '.learning', 'subjects')
    os.makedirs(subjects_dir, exist_ok=True)
    ensure_shared_assets(ws)

    slugs = sorted(name for name in os.listdir(subjects_dir)
                   if os.path.isdir(os.path.join(subjects_dir, name)))
    failed = 0
    summaries = []
    for slug in slugs:
        if not os.path.isfile(os.path.join(subjects_dir, slug, 'subject.yaml')):
            warn(f'{slug}/ 没有 subject.yaml，不算科目，已跳过')
            continue
        try:
            summaries.append(subject_summary(slug, ws))
        except Exception as exc:                      # 单个科目出问题不中断整次生成
            failed += 1
            warn(f'{slug}: 读科目数据失败，根主页暂缺这张卡片：{exc}')
    summaries.sort(key=lambda item: (SUBJECT_STATUS_ORDER.get(item['status'], 9), item['name']))
    render_home_index(summaries, ws)

    pages = 0
    written = [os.path.join(ws, 'index.html')]        # 自检对象：本次真正写出的页面
    for item in summaries:
        slug = item['slug']
        try:
            cur = load_yaml_quiet(os.path.join(subjects_dir, slug, 'curriculum.yaml'), f'{slug}/curriculum.yaml')
            prog = load_yaml_quiet(os.path.join(subjects_dir, slug, 'progress.yaml'), f'{slug}/progress.yaml')
            render_subject_index(slug, cur, prog, ws)
            pages += 1
            written.append(os.path.join(subjects_dir, slug, 'index.html'))
        except Exception as exc:                      # 同上：坏一个科目就跳过它，其余照常
            failed += 1
            warn(f'{slug}: 科目主页生成失败，已跳过：{exc}')

    # 生成后自检：页面全部写完之后再验链接，断链逐条报 stderr 并以退出码 1 结束
    broken = find_broken_links(written, ws)
    for page, value, target in broken:
        warn(f'坏链接：{page} 里的 {value!r} 解析到不存在的路径 {target}')
    if broken:
        raise SystemExit(f'链接自检未通过：{len(broken)} 条坏链接（页面已写出，清单见上）')

    print(f'主页已生成到: {ws}（链接自检通过：{len(written)} 个页面）')
    print(f'  根主页 1 个（{len(summaries)} 门科目）· 科目主页 {pages} 个 · 共享资源 {ws}/.learning/assets/')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
