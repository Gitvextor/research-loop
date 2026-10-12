#!/usr/bin/env python3
"""科目图片库的机器校验：索引 `pool.md` 与图片库目录 `assets/img/pool/` 对不对得上。

用法：
  python3 scripts/check_pool.py <subject_path>

落点（与 `image-scout`、`lesson-design` 里的路径逐字一致，R15）：
  · 图片目录：`<subject_path>/assets/img/pool/`（只放图片）
  · 索引：`<subject_path>/assets/img/pool.md`——图片库目录的**兄弟**，不是 `pool/pool.md`

校验五条：
  ① 索引存在，表头七列齐全且与固定表头逐字一致：
     `| 文件 | 主题标签 | 一句话说明 | 来源 URL | 许可 | 尺寸 | 抓取日期 |`
     （Markdown 的分隔行 `|---|---|…` 会跳过，不当数据行）
  ② 每行 `文件` 在图片库目录里真实存在
  ③ 文件名匹配命名规则（`<主题>-<子主题>-<要点>-<来源缩写>-<NN>.<ext>`，只用
     `[0-9A-Za-z\\u4e00-\\u9fa5-]`、无空格）且总长 ≤60 字符
  ④ `来源 URL`、`许可` 与 `抓取日期` 都非空（页面没标注也要写「未标注」；抓取日期写
     `YYYY-MM-DD`，与 `image-scout` 第 6 步一致，否则课件写不出 figcaption）
  ⑤ 单张 ≤500 KB——按**磁盘上的文件字节**判；`尺寸` 列是「宽×高」（像素），
     与体积无关，不参与判定

输出：每条问题一行 `<索引路径>:<行号> <问题>`（行号 0 = 索引整体的问题）；
全部合格时一行 `OK   <索引路径>（N 张）`。图片库为空（索引只有表头、抓不到图）**算合格**——
采集不到不阻塞大纲与课件，只记 `Gaps`。
退出码：有问题非零；合格 0。没给参数时把本用法打到 stderr 并退出 1。

依赖：Python 标准库（不联网、不解码图片、不用 Pillow）。
"""
import os
import re
import sys
from datetime import date

INDEX_REL = os.path.join('assets', 'img', 'pool.md')
POOL_REL = os.path.join('assets', 'img', 'pool')

# ① 固定表头：七列逐字（与 image-scout 的 `| 文件 | 主题标签 | … |` 一字不差）
REQUIRED_COLUMNS = ('文件', '主题标签', '一句话说明', '来源 URL', '许可', '尺寸', '抓取日期')

# ③ 命名规则：字符集逐字取自 image-scout 的 `[0-9A-Za-z\u4e00-\u9fa5-]`（字母、数字、
# 汉字、连字符），不许更宽——`\w` 会放进下划线、`.` 会放进任何字符。首字符不是连字符；
# 末段 `<NN>` 是 2 位以上数字；中间几段自己带不带连字符切不干净，所以只要求「至少 5 段」。
POOL_NAME_CHARS = r'0-9A-Za-z\u4e00-\u9fa5'
POOL_NAME_EXT = 'png|jpg|jpeg|webp|gif'      # image-scout 只抓这几种位图
POOL_NAME_RE = re.compile(
    r'^[{chars}]+(?:-[{chars}]+){{3,}}-[0-9]{{2,}}\.(?:{ext})$'.format(
        chars=POOL_NAME_CHARS, ext=POOL_NAME_EXT))
POOL_NAME_MAX = 60                            # 总长（字符）
POOL_NAME_SHAPE = '<主题>-<子主题>-<要点>-<来源缩写>-<NN>.<ext>'

# ⑤ 单张体积上限（字节）：与 lesson-design 的课件硬约束（单张 ≤500 KB）同一个数
MAX_BYTES = 500 * 1024

# 表头下的 Markdown 分隔行：|---|---|、| :--- | ---: |
SEPARATOR_RE = re.compile(r'^:?-{2,}:?$')


def split_row(line):
    """把 `| a | b |` 拆成 ['a', 'b']（去首尾空单元格、逐格 strip）。"""
    cells = [cell.strip() for cell in line.strip().split('|')]
    if cells and cells[0] == '':
        cells.pop(0)
    if cells and cells[-1] == '':
        cells.pop()
    return cells


def is_separator(cells):
    """分隔行不是数据行（评审口径：索引可以按标准 Markdown 写一行 `|---|---|`）。"""
    return bool(cells) and all(SEPARATOR_RE.match(cell) for cell in cells)


def find_header(lines):
    """找表头行：第一行含「文件」这一格的表格行。返回 (行号, 格子)；找不到是 (0, None)。"""
    for number, line in enumerate(lines, 1):
        if '|' not in line:
            continue
        cells = split_row(line)
        if '文件' in cells:
            return number, cells
    return 0, None


def check_row(cells, index, pool_dir, number):
    """② 文件存在 + ③ 文件名 + ④ 来源/许可/抓取日期非空 + ⑤ 体积。返回 [(行号, 问题)]。"""
    problems = []

    def cell(name):
        position = index.get(name)
        return cells[position] if position is not None and position < len(cells) else ''

    name = cell('文件')
    if not name:
        return [(number, '`文件` 是空的（每行要写图片库里的文件名）')]

    target = os.path.join(pool_dir, name)
    exists = os.path.isfile(target)
    if not exists:
        problems.append((number, f'文件缺失：图片库里没有 {POOL_REL}/{name}'))
    if len(name) > POOL_NAME_MAX:
        problems.append((number, f'文件名不合规：{len(name)} 字符 > {POOL_NAME_MAX} 字符（{name}）'))
    elif not POOL_NAME_RE.match(name):
        problems.append((number, f'文件名不合规：要 `{POOL_NAME_SHAPE}`（只用 {POOL_NAME_CHARS}、'
                                 f'无空格）：{name}'))
    # ④ 三列都非空：来源 URL、许可、抓取日期（抓取日期此前漏在校验外，空着也印 OK，
    # 而计划 Global Constraints 与 image-scout 第 6 步都要求三列齐）
    for column, hint in (('来源 URL', '这条图所在页面的地址，不是图片文件地址'),
                         ('许可', '页面没标注也要写「未标注」'),
                         ('抓取日期', '抓取那天，要写成 `YYYY-MM-DD` 这样的日期')):
        if index.get(column) is not None and not cell(column):
            problems.append((number, f'`{column}` 为空（{hint}）'))
    captured = cell('抓取日期')
    if captured:
        try:
            if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', captured):
                raise ValueError
            date.fromisoformat(captured)
        except ValueError:
            problems.append((number, '`抓取日期` 要写成有效的 YYYY-MM-DD 日期'))
    if exists:
        size = os.path.getsize(target)
        if size > MAX_BYTES:
            # 只报字节：四舍五入成 KB 时 512001 B 会印成「500 KB > 500 KB」，自相矛盾
            problems.append((number, f'超体积：{name} {size} B > {MAX_BYTES} B'
                                     f'（{MAX_BYTES // 1024} KB 上限；不缩放、超了就放弃）'))
    return problems


def check_pool(subject_path):
    """校验一个科目的图片库。返回 (problems, 行数)：problems 是 [(行号, 说明)]。"""
    index_path = os.path.join(subject_path, INDEX_REL)
    pool_dir = os.path.join(subject_path, POOL_REL)
    if not os.path.isfile(index_path):
        problems = [(0, f'索引不存在：{INDEX_REL}（索引是图片库的唯一检索入口）')]
        if os.path.isfile(os.path.join(pool_dir, 'pool.md')):
            problems.append((0, f'索引写错了地方：找到 {POOL_REL}/pool.md——'
                                f'它应是图片库目录的兄弟 {INDEX_REL}'))
        return problems, 0

    try:
        with open(index_path, 'rb') as handle:
            raw = handle.read()
    except OSError as error:
        return [(0, f'索引读不出来：{error}')], 0
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as error:
        # 非 UTF-8 也要守住输出契约（`<索引路径>:<行号> <问题>`，不抛回溯）：先定位坏字节在第几行
        number = raw[:error.start].count(b'\n') + 1
        return [(number, f'索引不是 UTF-8：第 {number} 行解不开（{error.reason}）——'
                         f'索引必须是 UTF-8，否则表头与数据行都读不出来')], 0
    lines = text.splitlines()
    header_number, columns = find_header(lines)
    if columns is None:
        return [(0, f'索引里没有表头行（逐字应为 | {" | ".join(REQUIRED_COLUMNS)} |）')], 0

    problems = []
    missing = [name for name in REQUIRED_COLUMNS if name not in columns]
    if missing:
        problems.append((header_number, '索引缺列：' + '、'.join(missing)))
    elif columns != list(REQUIRED_COLUMNS):
        problems.append((header_number, f'表头与固定表头不一致（逐字应为 '
                                        f'| {" | ".join(REQUIRED_COLUMNS)} |）：'
                                        f'| {" | ".join(columns)} |'))
    index = {name: columns.index(name) for name in columns}

    rows = 0
    for number, line in enumerate(lines[header_number:], header_number + 1):
        if line.strip().startswith('#'):
            break                       # 表到此为止（索引末尾是 `## Gaps` 小节）
        if '|' not in line:
            continue
        cells = split_row(line)
        if is_separator(cells):
            continue
        rows += 1
        if len(cells) != len(columns):
            problems.append((number, f'数据行列数不对：应为 {len(columns)} 列，实际 {len(cells)} 列'))
        try:
            problems += check_row(cells, index, pool_dir, number)
        except OSError as error:
            problems.append((number, f'图片文件读不出来：{error}'))
    return problems, rows


def main(argv):
    if len(argv) != 1 or argv[0].startswith('-'):
        raise SystemExit(__doc__)
    subject_path = argv[0]
    index_path = os.path.join(subject_path, INDEX_REL)
    problems, rows = check_pool(subject_path)
    for number, message in problems:
        print(f'{index_path}:{number} {message}')
    if problems:
        print(f'\n{len(problems)} 个问题（索引 {rows} 行）')
        return 1
    print(f'OK   {index_path}（{rows} 张）')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
