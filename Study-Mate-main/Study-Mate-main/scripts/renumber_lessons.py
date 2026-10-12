#!/usr/bin/env python3
"""课件位次重命名器：大纲里插了/删了节点以后，把 `lessons/` 的文件名序号按大纲重排。

用法：
    python3 scripts/renumber_lessons.py <科目目录> [--dry-run] [--render]

读：
    <科目>/curriculum.yaml                        `nodes:` 的顺序 = 课件位次（与 render_lesson.py 同口径）
    <科目>/lessons/<4 位序号>-<节点id>.<后缀>      后缀 ∈ md | quiz.json | html
写：
    <科目>/lessons/<正确序号>-<节点id>.<后缀>      同一个节点的三件一起落到同一个序号
    --render 时再跑 render_lesson.py 重渲染（页面里到处是序号：eyebrow、导航指针、页脚）

口径：
  · 先规划后执行：目标名已经被别的文件占着（不是本次要改走的）就整批不动、退出 1。
  · 序号已经对的文件跳过：不改名、也不重渲染。
  · 认不出的命名（没有 4 位序号、后缀不是那三种、节点 id 不在大纲里）一律不动，列进末尾的
    「未处理」清单并说明原因——它们是别人家的文件，不影响退出码（仍是 0），只在 stderr 上提示一行。
  · --render 的渲染失败**不回滚改名**（改名是对的，渲染可以再来一次），照实报错、退出 1。
  · `--dry-run` 只打印计划，一个字都不动盘；输出每行前缀 `[dry-run] `。

输出（stdout）：
    0002-cpp.types.md → 0003-cpp.types.md                     一行一个「旧名 → 新名」
    未处理 2 个文件（没动它们）：                              认不出的命名，逐条给原因（没有就整段不印）
      notes.md —— 没有「4 位序号-」前缀
    改了 3 个节点的 9 个文件 / 渲染 3 个页面                    末尾一行汇总（渲染几个页面只在 --render 时非零）
退出码：0 成事（含「有未处理项」）；1 有问题（大纲读不了 / 目标名被占 / 渲染失败）；用法错误 2。

依赖：标准库 + pyyaml（与 render_lesson.py / check_pool.py 同口径，不引新依赖）。本脚本只改
文件名，不改文件内容；文件内容与题库的对账是渲染器与检查的活。
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:                                   # pragma: no cover - 环境缺 pyyaml
    yaml = None

ROOT = Path(__file__).resolve().parent.parent
RENDER = ROOT / 'scripts' / 'render_lesson.py'
RENDER_REL = 'scripts/render_lesson.py'
USAGE = '用法：python3 scripts/renumber_lessons.py <科目目录> [--dry-run] [--render]'

# 三件套的后缀：长的在前——`.quiz.json` 是双扩展名，节点 id 自己也可以带点（`cpp.array`）
EXTS = ('.quiz.json', '.md', '.html')
EXT_ORDER = {'md': 0, 'quiz.json': 1, 'html': 2}
NAME_RE = re.compile(r'^(?P<num>\d+)-(?P<rest>.+)$')
NUM_WIDTH = 4
LESSONS = 'lessons'


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


def note(message):
    """提示（不影响退出码）：只往 stderr 打一行，别混进产物。"""
    print(f'提示: {message}', file=sys.stderr)


def parse_args(argv):
    """`<科目目录> [--dry-run] [--render]`；`--help` 打印用法退 0，用法不对回 None（调用方退 2）。"""
    positionals, dry_run, render = [], False, False
    for arg in argv:
        if arg == '--dry-run':
            dry_run = True
        elif arg == '--render':
            render = True
        elif arg in ('-h', '--help'):
            print(__doc__)
            raise SystemExit(0)
        elif arg.startswith('-'):
            print(f'未知参数 {arg}\n{USAGE}', file=sys.stderr)
            return None
        else:
            positionals.append(arg)
    if len(positionals) != 1:
        print(f'用法错误：要 <科目目录> 一个参数\n{USAGE}', file=sys.stderr)
        return None
    return positionals[0], dry_run, render


def load_order(subject_path, problems):
    """`curriculum.yaml` 的 `nodes:` 顺序 → {节点 id: 1 起位次}；读不了回 None。

    位次的口径与 render_lesson.py 的 Outline 一致：**第一个节点是 0001**，与 prerequisites、
    edges 都无关——它们是依赖图，不改课件位次。
    """
    path = os.path.join(subject_path, 'curriculum.yaml')
    if yaml is None:                                  # pragma: no cover - 环境缺 pyyaml
        problems.add(path, 1, '读不了 curriculum.yaml：需要 pyyaml（python3 -m pip install pyyaml）')
        return None
    if not os.path.isfile(path):
        problems.add(path, 1, f'找不到大纲文件（科目目录 {subject_path} 里应有 curriculum.yaml）')
        return None
    try:
        text = Path(path).read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as exc:
        problems.add(path, 1, f'大纲文件读不出来（要 UTF-8）：{exc}')
        return None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, 'problem_mark', None)
        problems.add(path, getattr(mark, 'line', 0) + 1, f'大纲不是合法 YAML：{exc}')
        return None
    nodes = data.get('nodes') if isinstance(data, dict) else None
    if nodes is not None and not isinstance(nodes, list):
        problems.add(path, 1, '大纲的 nodes: 必须是列表')
        return None
    order, duplicated = {}, []
    for node in nodes or []:
        if not (isinstance(node, dict) and node.get('id')):
            continue
        node_id = str(node['id'])
        if node_id in order:
            duplicated.append(node_id)
            continue
        order[node_id] = len(order) + 1
    if not order:
        problems.add(path, 1, '大纲里没有 nodes:（课件序号与位次都按它算）')
        return None
    for node_id in duplicated:
        order.pop(node_id, None)
        problems.add(path, 1, f'节点 id「{node_id}」在 nodes: 里出现两次——'
                              '位次算不出来，先跑 scripts/check_curriculum.py 把大纲修好')
    return order


def split_name(name):
    """`0008-cpp.array.quiz.json` → ('0008', 'cpp.array', 'quiz.json')；认不出回 None。"""
    for ext in EXTS:
        if name.endswith(ext) and len(name) > len(ext):
            head = name[: -len(ext)]
            break
    else:
        return None
    match = NAME_RE.match(head)
    if match is None:
        return None
    return match.group('num'), match.group('rest'), ext[1:]


def unknown_reason(name):
    """认不出的命名给一句原因（它只是没被本脚本接管，不是错误）。"""
    head = re.match(r'^(\d+)-', name)
    if head is None:
        return '没有「4 位序号-」前缀'
    if len(head.group(1)) != NUM_WIDTH:
        return f'序号 {head.group(1)} 不是 {NUM_WIDTH} 位补零'
    return '认不出的命名（后缀要正好是 md / quiz.json / html）'


def scan(lessons_dir, order):
    """扫 `lessons/`：分拣出要改名的、一个节点多份的、认不出的三类。

    返回 (renames, duplicates, untouched)：
      renames    —— [{'node', 'ext', 'old', 'new'}]，按大纲位次 + 后缀顺序排好
      duplicates —— [(节点 id, 后缀, [文件名, …])]，一个节点一件，多份就分不清该改哪份
      untouched  —— [(文件名, 原因)]，认不出的命名，原样留着
    """
    found, untouched = {}, []
    for name in sorted(os.listdir(lessons_dir)):
        path = os.path.join(lessons_dir, name)
        if os.path.isdir(path):
            untouched.append((name, '是目录，不是课件文件'))
            continue
        if not os.path.isfile(path):                  # 断链的符号链接之类：既不认、也不动
            continue
        parsed = split_name(name)
        if parsed is None:
            untouched.append((name, unknown_reason(name)))
            continue
        num, node, ext = parsed
        if len(num) != NUM_WIDTH:
            untouched.append((name, f'序号 {num} 不是 {NUM_WIDTH} 位补零'))
            continue
        if node not in order:
            untouched.append((name, f'节点 id「{node}」不在 curriculum.yaml 的 nodes: 里'))
            continue
        found.setdefault((node, ext), []).append((name, num))

    renames, duplicates = [], []
    for (node, ext), items in sorted(found.items(),
                                     key=lambda item: (order[item[0][0]], EXT_ORDER[item[0][1]])):
        if len(items) > 1:
            duplicates.append((node, ext, [name for name, _ in items]))
            continue
        name, num = items[0]
        want = f'{order[node]:0{NUM_WIDTH}d}'
        if num == want:
            continue                                  # 序号已经对：跳过
        renames.append({'node': node, 'ext': ext, 'old': name, 'new': f'{want}-{node}.{ext}'})
    return renames, duplicates, untouched


def apply_renames(lessons_dir, renames):
    """按计划改名：目标名空着的直接改；被本次要改走的文件占着的（换位）先过临时名。

    出错时尽力把已经改的改回去（先规划后执行已经挡住了绝大部分错，这里是兜底）。
    返回出错说明（成功回 None）。
    """
    def path_of(name):
        return os.path.join(lessons_dir, name)

    direct = [item for item in renames if not os.path.lexists(path_of(item['new']))]
    staged = [item for item in renames if os.path.lexists(path_of(item['new']))]
    done = []                                         # 每次实际改名，回滚时逐步逆序撤销
    temp_dir = None
    try:
        for item in direct:
            os.rename(path_of(item['old']), path_of(item['new']))
            done.append([path_of(item['new']), path_of(item['old'])])
        pending = []
        if staged:
            temp_dir = tempfile.mkdtemp(prefix='.renumber-tmp-', dir=lessons_dir)
        for position, item in enumerate(staged):      # 换位（0002 → 0003、0003 → 0002 这类）
            temp = os.path.join(temp_dir, str(position))
            os.rename(path_of(item['old']), temp)
            record = [temp, path_of(item['old'])]
            done.append(record)
            pending.append((record, item))
        for record, item in pending:
            os.rename(record[0], path_of(item['new']))
            done.append([path_of(item['new']), record[0]])
    except OSError as exc:
        for current, original in reversed(done):
            try:
                os.rename(current, original)
            except OSError:                           # pragma: no cover - 回滚也失败就只能如实说
                pass
        return str(exc)
    finally:
        if temp_dir is not None:
            try:
                os.rmdir(temp_dir)                    # 回滚失败时留下文件，供手工恢复
            except OSError:
                pass
    return None


def render_nodes(subject_path, node_ids):
    """对改过名的节点跑渲染器（调它的 CLI，不复制渲染逻辑）；返回渲染失败的节点数。"""
    failed = 0
    for node_id in node_ids:
        try:
            proc = subprocess.run([sys.executable or 'python3', str(RENDER), str(subject_path), node_id],
                                  capture_output=True, text=True, encoding='utf-8')
        except OSError as exc:                        # pragma: no cover - 渲染器不见了
            failed += 1
            print(f'{RENDER_REL}:1 起不了渲染器（{exc}）——改名已经做完、不回滚', file=sys.stderr)
            continue
        if proc.returncode == 0:
            continue
        failed += 1
        shown = (proc.stdout + proc.stderr).strip()
        if shown:                                     # 渲染器的 `<文件>:<行> 问题` 原样转出来
            print(shown, file=sys.stderr)
        print(f'{RENDER_REL}:1 节点 {node_id} 渲染失败（退出码 {proc.returncode}）——'
              f'改名已经做完、不回滚；修好后直接运行 {RENDER_REL} <科目目录> {node_id} 重渲染',
              file=sys.stderr)
    return failed


def main(argv):
    parsed = parse_args(argv)
    if parsed is None:
        return 2
    subject_path, dry_run, render = parsed

    problems = Problems()
    order = load_order(subject_path, problems)
    if order is None:
        problems.report()
        return 1
    lessons_dir = os.path.join(subject_path, LESSONS)
    if not os.path.isdir(lessons_dir):
        problems.add(lessons_dir, 1, f'找不到课件目录（科目目录 {subject_path} 里应有 {LESSONS}/）')
        problems.report()
        return 1

    try:
        renames, duplicates, untouched = scan(lessons_dir, order)
    except OSError as exc:
        problems.add(lessons_dir, 1, f'课件目录读不出来：{exc}')
        problems.report()
        return 1
    for node_id, ext, names in duplicates:
        problems.add(os.path.join(lessons_dir, names[0]), 1,
                     f'节点 {node_id} 的 .{ext} 有 {len(names)} 份（{"、".join(names)}）——'
                     '一个节点一件，分不清该改哪份（先删掉多余的那份再重跑）')
    sources = {os.path.join(lessons_dir, item['old']) for item in renames}
    for item in renames:
        target = os.path.join(lessons_dir, item['new'])
        if os.path.lexists(target) and target not in sources:
            problems.add(target, 1, f'目标名已存在，且它不是本次要改走的文件——先处理它再重跑'
                                    f'（`{item["old"]}` 要改成它）')
    if problems:
        problems.report()
        return 1

    emit = (lambda line: print(f'[dry-run] {line}')) if dry_run else print
    for item in renames:
        emit(f'{item["old"]} → {item["new"]}')

    changed = sorted({item['node'] for item in renames}, key=lambda node_id: order[node_id])
    rendered, failed = 0, 0
    if renames and not dry_run:
        failure = apply_renames(lessons_dir, renames)
        if failure is not None:
            print(f'{lessons_dir}:1 改名中途出错：{failure}——已经改的已尽力改回去，'
                  '请核对上面的清单后重跑', file=sys.stderr)
            return 1
        if render:
            failed = render_nodes(subject_path, changed)
            rendered = len(changed) - failed
    elif render:
        rendered = len(changed)                       # --dry-run：把「会渲染几个页面」照实报出来

    if untouched:
        emit(f'未处理 {len(untouched)} 个文件（没动它们）：')
        for name, reason in untouched:
            emit(f'  {name} —— {reason}')
        note(f'{len(untouched)} 个文件没被接管（见上面的「未处理」清单）——它们的命名不在'
             f'「{NUM_WIDTH} 位序号-<节点id>.<md|quiz.json|html>」里，脚本一个字都没动它们')

    emit(f'改了 {len(changed)} 个节点的 {len(renames)} 个文件 / 渲染 {rendered} 个页面')

    if failed:
        print(f'{len(changed)} 个节点改了名，其中 {failed} 个没渲染成功——'
              f'改名不回滚，把问题修好后用 {RENDER_REL} 重渲染上面失败的节点', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
