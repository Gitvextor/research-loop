"""StudyMate · 实操 0003-system-elimination（与课件 0003「高斯消元与解的结构」对齐）

节点：system.elimination　载体：源码 + 测试（只用 Python 标准库）

怎么用
------
1. 先跑一遍看结果：

       python3 -m unittest -v

   交付状态下是红的：教程部分的 2 条通过（`augment` 已经写好），本文件里四个标了
   ``▸ 你的任务`` 的函数抛 NotImplementedError，测试以非零退出码结束。
2. 一次只做一个函数：实现一个 → 跑一次测试 → 看对应的那几条从 error 转绿。
3. 卡住了按这个顺序来：先读断言的报错原文（期望与实际并排打出来）→ 再看函数 docstring 里的
   「边界」那几行 → 还不行就把报错原文贴回会话（不直接给答案，会先问你哪一行不对）。
4. 参考解在 ``../solutions/0003-system-elimination/gauss.py``，做完再对照。

约定的返回结构（测试就是按它断言的）
------------------------------------
``solve(A, b)`` 返回一个 dict，三种情形各带哪些键：

* ``kind='unique'``：``{'kind': 'unique', 'solution': [x1, x2, …]}``，按未知量顺序排；
* ``kind='none'``：``{'kind': 'none'}``（出现矛盾行，形如左边全零、右边非零）；
* ``kind='infinite'``：``{'kind': 'infinite', 'particular': [...], 'null_basis': [[...], …],
  'free_count': n}``。

``particular`` 是自由变量全取 0 时得到的那个特解；``null_basis`` 是零空间的一组基，长度等于
自由变量个数，每个基向量把对应的自由变量取成 1。元素用 ``fractions.Fraction``，不要用 float
做相等比较：``1/3`` 在浮点里是 ``0.333…``，一次除法就会带进误差。
"""

from fractions import Fraction


def augment(A, b):
    """把系数矩阵 A 与右端项 b 拼成增广矩阵（教程部分，已经写好）。

    ``augment([[1, 2], [3, 4]], [5, 6])`` 得到 ``[[1, 2, 5], [3, 4, 6]]``。
    行数与 b 的长度不一致时抛 ValueError——增广矩阵的最后一列是每一行的一部分，
    行与右端项必须一一对应。
    """
    if len(A) != len(b):
        raise ValueError(f'A 有 {len(A)} 行，b 有 {len(b)} 个数，两者必须一样多')
    return [list(row) + [rhs] for row, rhs in zip(A, b)]


def rref(A):
    """▸ 你的任务 1：把矩阵化成最简行阶梯形（reduced row echelon form）。

    A 是行列表，例如 ``[[1, 2], [3, 4]]``。返回同形状的新矩阵（**不要改到调用方传进来的
    那个列表**），每一行都是新列表。

    最简行阶梯形要求三件事：

    * 每个非零行的第一个非零元（主元）是 1；
    * 主元所在列的其他位置全是 0；
    * 主元逐行右移：下一行的主元一定在上一行主元的右边；全零行排在最后。

    例：``rref([[2, 4, 2, 8], [1, 2, 3, 9]])`` 应得到
    ``[[1, 2, 0, Fraction(3, 2)], [0, 0, 1, Fraction(5, 2)]]``。

    边界：``rref([])`` 返回 ``[]``。元素先转成 Fraction 再算——用整除的写法遇到
    ``3/2`` 这类结果会悄悄出错。某一列从当前行往下全是 0 时，这一列没有主元，
    换到下一列继续。
    """
    raise NotImplementedError('▸ 任务 1 未实现：rref')


def pivot_columns(A):
    """▸ 你的任务 2：给出主元所在列的下标（从 0 开始，升序）。

    例：``pivot_columns([[1, 2, 0, 1.5], [0, 0, 1, 2.5]])`` 返回 ``[0, 2]``；
    空矩阵返回 ``[]``。

    提示：主元的个数就是秩，所以这个函数的返回值取 ``len()`` 就是 ``rank()``。
    """
    raise NotImplementedError('▸ 任务 2 未实现：pivot_columns')


def rank(A):
    """▸ 你的任务 3：矩阵的秩。

    秩在这一课里有三种说法，指的是同一个数：非零行的个数、线性无关的列的最多个数、
    变换后剩下的维数。用 ``pivot_columns`` 把它数出来。
    """
    raise NotImplementedError('▸ 任务 3 未实现：rank')


def solve(A, b):
    """▸ 你的任务 4：解线性方程组 Ax = b，返回解的结构（见模块 docstring 的约定）。

    三种情形：

    * 出现矛盾行（左边全零、右边非零）→ ``{'kind': 'none'}``；
    * 没有矛盾行，且主元个数等于未知量个数 → ``{'kind': 'unique', 'solution': [...]}``；
    * 没有矛盾行，且主元少于未知量个数 → ``{'kind': 'infinite', ...}``，其中
      ``free_count = 列数 − 主元个数``。

    做法：用 ``augment`` 拼出增广矩阵，用 ``rref`` 化简，再按上面两条判据把结果读出来。
    主元列对应的未知量取值写在最后一列；没有主元的列是自由变量，取 0 得到特解。

    边界：

    * ``A`` 为空、或 ``A`` 的某一行为空时抛 ValueError（没有未知量谈不上解方程组）；
    * ``A`` 的行数必须等于 ``len(b)``，否则抛 ValueError，信息里写清两个长度；
    * 不要修改传进来的 ``A`` 与 ``b``；
    * 系数与结果都用 Fraction，不要用 float 做相等比较。
    """
    raise NotImplementedError('▸ 任务 4 未实现：solve')


if __name__ == '__main__':
    print('把本文件当模块用：python3 -m unittest -v（见模块 docstring 的「怎么用」）')
