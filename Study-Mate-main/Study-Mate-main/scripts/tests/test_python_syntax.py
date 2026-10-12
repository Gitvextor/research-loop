#!/usr/bin/env python3
r"""全部 .py 都要能编译过：非法转义序列在 Python 3.12+ 是 SyntaxWarning，会顺着输出捣乱。

为什么单独有这道：`checks.mjs` 只跑得到"被测试覆盖的文件"，而**没被任何测试跑到的脚本**出问题
就没人知道。这类问题的真身是**编译期**的，不需要运行——静态扫一遍最省事。

真发生过一次：`check_lesson.py` 的说明文字里写了 `\left\{`（本意是 LaTeX）。Python 3.12 起
非法转义是默认可见的 `SyntaxWarning`，3.13 会把警告打到 stderr **并回显那行源码**；而那行源码
里有「大括号」三个字，正好撑破了另一条「输出里不该出现大括号」的断言。本地 Python 3.11 不发这个
警告，所以一直全绿，直到 CI 的 3.13 才红。

判据只一条：**把每个 .py 解析一遍**，有 `SyntaxError`（含被升级的 `SyntaxWarning`）就报，
带文件名与行号。覆盖 `scripts/`（引擎）与 `examples/`（示例里的 lab 代码）；`workspace/` 是学生
数据、`.venv` 与 `node_modules` 是第三方，都不扫。

用法：python3 scripts/tests/test_python_syntax.py
"""
import ast
import pathlib
import sys
import warnings

REPO = pathlib.Path(__file__).resolve().parents[2]
ROOTS = ('scripts', 'examples')
SKIP_DIRS = {'__pycache__', '.venv', 'node_modules', 'workspace', '.git', '.superpowers'}

failures = 0
total = 0


def check(label, ok, detail=''):
    global failures, total
    total += 1
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f'  — {detail}' if detail and not ok else ''))
    failures += not ok


def python_files():
    for root in ROOTS:
        base = REPO / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob('*.py')):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            yield path


def main():
    # 让 3.12+ 的非法转义直接抛错，而不是打一行警告混进输出（3.11 发的是 DeprecationWarning，
    # 类别对不上，所以这条在旧版本上不会因为转义而红——新版本才拦得住，这正是要的效果）
    warnings.simplefilter('error', SyntaxWarning)

    scanned = 0
    bad = []
    for path in python_files():
        scanned += 1
        try:
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        except SyntaxError as exc:          # SyntaxWarning 被升级后也是 SyntaxError
            where = f'{path.relative_to(REPO)}:{exc.lineno}'
            bad.append(f'{where} {exc.msg}')

    check(f'扫到的 .py 数量合理（{scanned} 个）', scanned >= 20,
          f'只扫到 {scanned} 个——检查 ROOTS 或跳过规则是不是写错了')
    check('每个 .py 都能编译过（含非法转义这类编译期问题）', not bad, '\n'.join(bad[:8]))

    if sys.version_info < (3, 12):
        print(f'提示：本机 Python {sys.version_info.major}.{sys.version_info.minor} 不会为非法转义发 '
              'SyntaxWarning，所以这一类问题在本地**看不见**（3.6 起只是被弃用、默认不显示）——'
              '请用 Python 3.12+ 运行此项检查，例如 '
              '`uv run --python 3.13 python scripts/tests/test_python_syntax.py`。')

    print(f'\n{total - failures}/{total} 通过（扫了 {scanned} 个文件）')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
