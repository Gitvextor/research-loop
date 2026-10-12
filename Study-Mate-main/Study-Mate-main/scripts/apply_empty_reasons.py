#!/usr/bin/env python3
"""把出题角色这一轮的 `empty_reason` 打进内容文件：`::: quiz` 无题锚点的理由。

用法：
    python3 scripts/apply_empty_reasons.py <科目目录> <节点id> <TSV 文件> [--dry-run]

读：
    <科目>/curriculum.yaml                    节点位次（内容文件名是 <4 位序号>-<节点id>.md）
    <科目>/lessons/<4 位序号>-<节点id>.md      讲解角色的内容文件（块语法见 docs/课件内容格式.md §4）
    <TSV 文件>                                每行两列 `<锚点文本>\\t<理由>`；空行与 `#` 开头的行跳过
写：
    <科目>/lessons/<4 位序号>-<节点id>.md      在锚点所在 `::: quiz` 块里、收尾 `:::` 之前插一行
                                              `empty_reason: <理由>`（块的缩进原样，行尾跟原文件一致）

口径：
  · 先全量校验再写：错一条就报错退出 1，**一个文件都不改**。会拦下——锚点在内容文件里找不到、
    同一个锚点被两个 `::: quiz` 块引用、那个块已经有 `empty_reason:`、TSV 里同一个锚点出现两次、
    锚点文本为空、理由为空（含理由列里再写 `empty_reason:` 前缀、TSV 行多出第三列）。
  · 锚点在两个文件之间**逐字**匹配（`锚点：` 与 `锚点:` 两种冒号都认，两侧空白不算），口径与
    render_lesson.py 的 `build_quiz` 一致；围栏（```）里的 `::: quiz` 是代码原文，不算题目位置。
  · 只在确实需要时写盘：校验全过、真有要插的行时一次性写回；UTF-8 与每行行尾逐字保持
    （CRLF 文件里插进去的那行也是 CRLF），末尾换行不动。
  · `--dry-run` 只打印将插入的行与位置，一个字都不动盘；输出每行前缀 `[dry-run] `。

输出（stdout）：
    插入了 empty_reason: 分档数组版 → <科目>/lessons/0003-cpp.io.md:42
    2 处 / 跳过 2 行                              末尾汇总（跳过 = TSV 里的空行与 `#` 注释行）
退出码：0 成事；1 有问题（校验不过 / 写盘失败）；用法错误 2。

依赖：标准库 + pyyaml（与 render_lesson.py / check_pool.py 同口径，不引新依赖）。
"""
import os
import re
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:                                   # pragma: no cover - 环境缺 pyyaml
    yaml = None

USAGE = '用法：python3 scripts/apply_empty_reasons.py <科目目录> <节点id> <TSV 文件> [--dry-run]'

LESSONS = 'lessons'
NUM_WIDTH = 4
FENCE = '```'
EMPTY_REASON = 'empty_reason'
FIELD_RE = re.compile(r'^([a-z_]+):\s*(.*)$')                        # 与 render_lesson.py 同口径
DIRECTIVE_RE = re.compile(r'^:::\s*([a-zA-Z][a-zA-Z0-9_-]*)\s*(.*)$')  # 与 render_lesson.py 同口径
ANCHOR_RE = re.compile(r'^(.*?)锚点[：:]\s*(.+)$')                    # 与 build_quiz 同口径


class Problems:
    """收集问题：每条都是 `文件:行 问题`，一次跑完把所有问题都报出来。"""

    def __init__(self):
        self.items = []

    def add(self, path, line, message):
        self.items.append((str(path), max(int(line or 1), 1), message))

    def __bool__(self):
        return bool(self.items)

    def report(self):
        for path, line, message in self.items:
            print(f'{path}:{line} {message}', file=sys.stderr)


def parse_args(argv):
    """`<科目目录> <节点id> <TSV 文件> [--dry-run]`；`--help` 打印用法退 0，用法不对回 None。"""
    positionals, dry_run = [], False
    for arg in argv:
        if arg == '--dry-run':
            dry_run = True
        elif arg in ('-h', '--help'):
            print(__doc__)
            raise SystemExit(0)
        elif arg.startswith('-'):
            print(f'未知参数 {arg}\n{USAGE}', file=sys.stderr)
            return None
        else:
            positionals.append(arg)
    if len(positionals) != 3:
        print(f'用法错误：要 <科目目录> <节点id> <TSV 文件> 三个参数\n{USAGE}', file=sys.stderr)
        return None
    return positionals[0], positionals[1], positionals[2], dry_run


def node_index(subject_path, node_id, problems):
    """节点在 `curriculum.yaml` 的 `nodes:` 里的位次（1 起）；读不了 / 不在大纲里回 None。"""
    path = os.path.join(subject_path, 'curriculum.yaml')
    if yaml is None:                                  # pragma: no cover - 环境缺 pyyaml
        problems.add(path, 1, '读不了 curriculum.yaml：需要 pyyaml（python3 -m pip install pyyaml）')
        return None
    if not os.path.isfile(path):
        problems.add(path, 1, f'找不到大纲文件（科目目录 {subject_path} 里应有 curriculum.yaml）')
        return None
    try:
        data = yaml.safe_load(Path(path).read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError) as exc:
        problems.add(path, 1, f'大纲文件读不出来（要 UTF-8）：{exc}')
        return None
    except yaml.YAMLError as exc:
        mark = getattr(exc, 'problem_mark', None)
        problems.add(path, getattr(mark, 'line', 0) + 1, f'大纲不是合法 YAML：{exc}')
        return None
    nodes = data.get('nodes') if isinstance(data, dict) else None
    if nodes is not None and not isinstance(nodes, list):
        problems.add(path, 1, '大纲的 nodes: 必须是列表')
        return None
    ids = [str(node['id']) for node in nodes or []
           if isinstance(node, dict) and node.get('id')]
    if not ids:
        problems.add(path, 1, '大纲里没有 nodes:（内容文件的序号按它算）')
        return None
    if len(ids) != len(set(ids)):
        problems.add(path, 1, '大纲的 nodes: 有重复节点 id，先修好大纲再回填理由')
        return None
    if node_id not in ids:
        problems.add(path, 1, f'节点 {node_id} 不在 curriculum.yaml 的 nodes: 里——'
                              '内容文件名与序号都按它算（核对节点 id 是否写对）')
        return None
    return ids.index(node_id) + 1


def split_line(part):
    """把 `text.split('\\n')` 出来的裸行拆成 (内容, 行尾)：CRLF 文件的行尾是 `\\r`，原样留着。"""
    if part.endswith('\r'):
        return part[:-1], '\r'
    return part, ''


def find_close(parts, start):
    """开块行之后第一行单独的 `:::` 的**下标**（围栏里的不算）；没闭合回 None。"""
    in_fence = False
    for index in range(start + 1, len(parts)):
        content, _ = split_line(parts[index])
        stripped = content.strip()
        if stripped.startswith(FENCE):
            in_fence = not in_fence
            continue
        if not in_fence and stripped == ':::':
            return index
    return None


def quiz_blocks(parts):
    """文件里的 `::: quiz` 题目位置：`{'line', 'anchor', 'indent', 'close'}`（行号 1 起、close 是下标）。

    判定与 render_lesson.py 的 parse_blocks / parse_directive 同口径：`:::` 开头的行才是指令，
    围栏（```）里的 `:::` 是代码原文；收尾是**单独一行** `:::`。锚点按 `锚点：` / `锚点:` 取，
    两侧空白不算——它要与题库/TSV 的键逐字一致。
    """
    blocks, in_fence = [], False
    for index, part in enumerate(parts):
        content, _ = split_line(part)
        stripped = content.strip()
        if stripped.startswith(FENCE):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = DIRECTIVE_RE.match(stripped)
        if not (match and match.group(1) == 'quiz'):
            continue
        anchor_match = ANCHOR_RE.match(match.group(2).strip())
        blocks.append({
            'line': index + 1,
            'anchor': anchor_match.group(2).strip() if anchor_match else None,
            'indent': content[: len(content) - len(content.lstrip())],
            'close': find_close(parts, index),
        })
    return blocks


def existing_empty_reason(parts, block):
    """块里已有的 `empty_reason:` 在第几行（1 起）；没有回 None。"""
    for index in range(block['line'], block['close']):
        content, _ = split_line(parts[index])
        field = FIELD_RE.match(content.strip())
        if field and field.group(1) == EMPTY_REASON:
            return index + 1
    return None


def parse_tsv(path, problems):
    """TSV → ([(行号, 锚点, 理由)], 跳过的行数)：空行与 `#` 开头的行跳过，坏行带行号报错。"""
    if not os.path.isfile(path):
        problems.add(path, 1, '找不到 TSV 文件（每行两列：<锚点文本>\\t<理由>）')
        return [], 0
    try:
        text = Path(path).read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as exc:
        problems.add(path, 1, f'TSV 读不出来（要 UTF-8）：{exc}')
        return [], 0
    if text.startswith('\ufeff'):                     # 表格软件导出的 BOM：它是字节序标记，不是锚点的一部分
        text = text[1:]
    lines = text.split('\n')
    if lines and lines[-1] == '':
        lines.pop()                                   # 末尾的换行不是一行，不该算进「跳过」
    rows, skipped, seen = [], 0, {}
    for number, line in enumerate(lines, 1):
        if not line.strip() or line.strip().startswith('#'):
            skipped += 1
            continue
        columns = line.split('\t')
        anchor = columns[0].strip()
        reason = columns[1].strip() if len(columns) > 1 else ''
        if len(columns) > 2:
            problems.add(path, number, f'TSV 每行只有两列（<锚点文本>\\t<理由>），这一行有 '
                                       f'{len(columns)} 列——理由里不要写制表符')
        elif not anchor:
            problems.add(path, number, '锚点文本是空的（每行两列：<锚点文本>\\t<理由>）')
        elif not reason:
            problems.add(path, number, '理由为空（每行两列：<锚点文本>\\t<理由>）')
        elif reason.startswith(EMPTY_REASON):
            problems.add(path, number, f'理由列不要再写 `{EMPTY_REASON}:` 前缀——'
                                       '插进内容文件时会自动加')
        elif anchor in seen:
            problems.add(path, number, f'锚点「{anchor}」在 TSV 里出现两次'
                                       f'（第 {seen[anchor]} 行、第 {number} 行）——一个锚点只留一行')
        else:
            seen[anchor] = number
            rows.append({'tsv_line': number, 'anchor': anchor, 'reason': reason})
    return rows, skipped


def main(argv):
    parsed = parse_args(argv)
    if parsed is None:
        return 2
    subject_path, node_id, tsv_path, dry_run = parsed
    problems = Problems()

    rows, skipped = parse_tsv(tsv_path, problems)
    index = node_index(subject_path, node_id, problems)
    if index is None:
        problems.report()
        return 1
    md_path = os.path.join(subject_path, LESSONS, f'{index:0{NUM_WIDTH}d}-{node_id}.md')
    if not os.path.isfile(md_path):
        problems.add(md_path, 1, f'找不到内容文件（节点 {node_id} 在大纲里的位次是 '
                                 f'{index:0{NUM_WIDTH}d}）——先让讲解角色产出这一课的 .md')
        problems.report()
        return 1
    try:
        raw = Path(md_path).read_bytes()
    except OSError as exc:
        problems.add(md_path, 1, f'内容文件读不出来：{exc}')
        problems.report()
        return 1
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as exc:
        number = raw[:exc.start].count(b'\n') + 1
        problems.add(md_path, number,
                     f'内容文件不是 UTF-8：第 {number} 行解不开（{exc.reason}）——先把它存成 UTF-8')
        problems.report()
        return 1

    parts = text.split('\n')                          # 行号口径与渲染器一致：只按 \n 切
    by_anchor = {}
    for block in quiz_blocks(parts):
        if block['anchor']:
            by_anchor.setdefault(block['anchor'], []).append(block)

    inserts = []
    for row in rows:
        anchor = row['anchor']
        found = by_anchor.get(anchor) or []
        if not found:
            problems.add(tsv_path, row['tsv_line'],
                         f'锚点「{anchor}」在内容文件里没有对应的 ::: quiz 题目位置'
                         f'（锚点在两个文件之间逐字匹配）：{md_path}')
            continue
        if len(found) > 1:
            problems.add(md_path, found[1]['line'],
                         f'锚点「{anchor}」被 {len(found)} 个 ::: quiz 题目位置引用（第 '
                         + '、'.join(str(block['line']) for block in found)
                         + ' 行）——一个锚点只留一个题目位置')
            continue
        block = found[0]
        if block['close'] is None:
            problems.add(md_path, block['line'],
                         f'锚点「{anchor}」的 ::: quiz 块没有收尾 :::（渲染器会报错）——先补上收尾行')
            continue
        existing = existing_empty_reason(parts, block)
        if existing is not None:
            problems.add(md_path, existing,
                         f'锚点「{anchor}」的块里已经有 empty_reason: 了——不用再插（要改就手改那一行）')
            continue
        inserts.append({'anchor': anchor, 'reason': row['reason'],
                        'at': block['close'], 'indent': block['indent']})

    if problems:
        problems.report()
        return 1

    inserts.sort(key=lambda item: item['at'])
    for offset, item in enumerate(inserts):           # 插在前面几处会把后面的行号往下推
        item['line'] = item['at'] + 1 + offset

    emit = (lambda line: print(f'[dry-run] {line}')) if dry_run else print
    if inserts and not dry_run:                       # 只在确实有东西要插时才写盘
        for item in reversed(inserts):
            # 最后一行 ::: 可能没有换行；此时沿用前一行的 CRLF/LF，避免插入 LF。
            eol_at = item['at'] if item['at'] < len(parts) - 1 else item['at'] - 1
            _, eol = split_line(parts[eol_at])
            parts.insert(item['at'], f'{item["indent"]}{EMPTY_REASON}: {item["reason"]}{eol}')
        temporary = None
        try:
            # 先在同目录完整写好，再原子替换；写入失败不能截断原课件。
            with tempfile.NamedTemporaryFile(dir=os.path.dirname(md_path),
                                             prefix='.empty-reasons-', delete=False) as handle:
                temporary = handle.name
                handle.write('\n'.join(parts).encode('utf-8'))
            os.chmod(temporary, os.stat(md_path).st_mode)
            os.replace(temporary, md_path)
        except OSError as exc:
            print(f'{md_path}:1 写盘失败：{exc}', file=sys.stderr)
            return 1
        finally:
            if temporary is not None and os.path.exists(temporary):
                try:
                    os.unlink(temporary)
                except OSError as exc:
                    print(f'{temporary}:1 临时文件清理失败：{exc}', file=sys.stderr)
    for item in inserts:
        emit(f'插入了 empty_reason: {item["anchor"]} → {md_path}:{item["line"]}')
    emit(f'{len(inserts)} 处 / 跳过 {skipped} 行')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
