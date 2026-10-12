# 实操：0003-system-elimination

对应节点 `system.elimination`（课件 0003，`kind: 实操`）。把第 3 课讲的消元写成能跑的代码：
**自己实现「化成最简行阶梯形」与「读出解的结构」**，不调用任何现成的线性代数库。

项目线索：这是这门课第一件能反复用的小工具——第 4 课数主元求基、第 5 课解 $(A - \lambda I)v = 0$，
用的都是这两个判断。

## 载体

**源码 + 测试**：`0003-system-elimination/` 里是一份 `gauss.py` 加一份 `test_gauss.py`，
用 Python 自带的 unittest 跑，**只用标准库，不装任何第三方包**。

| 文件 | 是什么 |
| --- | --- |
| `0003-system-elimination/gauss.py` | 你要读和写的源码：一个写好的教程函数 + 四处 `▸ 你的任务` 留白 |
| `0003-system-elimination/test_gauss.py` | 自检脚本：23 条断言。教程那 2 条通过，四个任务函数报错，整份测试现在是**红的** |
| `solutions/0003-system-elimination/gauss.py` | 参考解（做完再对照，别提前看） |
| `solutions/0003-system-elimination/test_gauss.py` | 与任务目录同一份自检，放在参考解旁边，23 条全绿 |

任务文件与答案分开放：`solutions/` 是一份**完整的对照副本**，把它拷过去就能直接跑。

## 环境

- Python **3.8 或更高**（本机 3.11 跑过）：只用到 `unittest` 与 `fractions` 两个标准库模块。
- 不需要网络、不需要 `pip install`，也不需要 numpy。这一点是有意为之：先亲手把消元写一遍，
  以后调 `numpy.linalg.solve` 时才知道它在替你做什么。
- 版本差异提示：本 lab 的 `pivot_columns` 返回的是**列下标列表**，与 SymPy 的 `rref()` 返回
  `(矩阵, 主元列)` 二元组不是同一套接口，别混着记；要核对现成库的写法看
  `../RESOURCES.md` 里那条 SymPy 官方文档。

## 怎么跑

```bash
# 先进入本文件所在的 lab 目录，然后：
cd 0003-system-elimination
python3 -m unittest -v
```

交付状态下应该看到：**2 条通过、21 条报 `NotImplementedError`，`FAILED (errors=21)`、退出码 1**。
这就是起点——教程那 2 条让你先看清断言长什么样、要交的结果是什么形状，剩下的红条就是待办清单。

对照参考解（同一份测试，跑在完整实现上）：

```bash
cd ../solutions/0003-system-elimination
python3 -m unittest -v      # 23 条全过，OK（退出码 0）
```

## 要交的东西（结果的结构）

`solve(A, b)` 返回一个 dict，三种解各带哪些键：

| `kind` | 含义 | 还要带什么 |
| --- | --- | --- |
| `unique` | 唯一解 | `solution`：按未知量顺序排的解 |
| `none` | 无解（出现矛盾行） | ——（不要带 `solution` 键） |
| `infinite` | 无穷多解 | `particular`（自由变量全取 0 的特解）、`null_basis`（零空间的一组基）、`free_count` |

数字用 `fractions.Fraction`，不要用 `float` 做相等比较：`1/3` 在浮点里是 `0.333…`，
化简里的一次除法就会带进误差，第 2 条断言（`([[2, 1], [1, 3]], [1, 2])`）会因此失败。

## 教程部分（已完成，跑一遍就能看见结果）

`augment(A, b)` 把 b 并到每一行末尾，行数不一致时抛 `ValueError`。你后面所有调试都会用到这个形状：
增广矩阵的最后一列是每一行的一部分，行变换要连它一起做——这正是第 3 课那个「忘了同步右端项」的坑。

## ▸ 你的任务

一次只做一个：实现一个函数 → 跑一次 `python3 -m unittest -v` → 看对应的那几条从 error 转绿。
四个函数全做完之后，23 条应当全过（退出码 0）。

| # | 函数 | 做什么 | 算过的标准（测试转绿） |
| --- | --- | --- | --- |
| 1 | `rref(A)` | 化成最简行阶梯形：主元为 1、主元列其余为 0、主元逐行右移、全零行垫底 | `TestRref` 6 条（含「不改入参」与 `rref([])` 返回 `[]`） |
| 2 | `pivot_columns(A)` | 给出主元所在列的下标（升序） | `TestPivotsAndRank` 里 `test_pivot_columns` 与 `test_pivot_columns_of_degenerate_matrix` |
| 3 | `rank(A)` | 矩阵的秩（主元的个数） | `TestPivotsAndRank` 的 `test_rank_counts_independent_columns`（秩 1 / 2 / 0 各一例） |
| 4 | `solve(A, b)` | 三种解的结构，以及空矩阵、空行、行数不一致三个错误分支 | `TestSolveUnique` 3 条、`TestSolveNone` 2 条、`TestSolveInfinite` 4 条、`TestErrors` 3 条 |

卡住了按这个顺序来：**先读断言的报错原文**（`AssertionError` 会把期望与实际并排打出来）→
再看函数 docstring 里的「边界」那几行 → 还不行就把报错原文贴回会话。不直接给答案，会先问你哪一行不对。

## 做完之后

回课件答那三道题（`../lessons/0003-system.elimination.html` 里的题目位置），然后接着上 `space.basis`
（基、维数与坐标）——下一课数主元的方式，就是你这个 `pivot_columns` 已经在做的事。
