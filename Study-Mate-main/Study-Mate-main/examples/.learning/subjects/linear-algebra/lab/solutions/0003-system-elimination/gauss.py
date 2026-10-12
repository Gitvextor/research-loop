"""StudyMate · 实操 0003-system-elimination 的**参考解**（做完任务再对照）

与任务目录的 ``gauss.py`` 是同一套接口，四个函数都已实现：``rref`` 化最简行阶梯形、
``pivot_columns`` 给主元列、``rank`` 数主元、``solve`` 读解的结构。整份文件只用
``fractions`` 一个标准库模块，全程精确算术，不做浮点比较。

跑法：在本文件所在目录执行

    python3 -m unittest -v

全部断言通过（退出码 0）。对照时先看自己卡住的那一个函数，别整份抄——这份实现里的
循环顺序与变量名不是唯一写法，你自己的写法只要断言全绿就成立。
"""

from fractions import Fraction


def augment(A, b):
    """把系数矩阵 A 与右端项 b 拼成增广矩阵（与任务文件同一份教程代码）。"""
    if len(A) != len(b):
        raise ValueError(f'A 有 {len(A)} 行，b 有 {len(b)} 个数，两者必须一样多')
    return [list(row) + [rhs] for row, rhs in zip(A, b)]


def rref(A):
    """把矩阵化成最简行阶梯形：主元为 1、主元列其余为 0、主元逐行右移、全零行垫底。

    逐列扫描：在当前列里从 ``pivot_row`` 往下找第一个非零元，换上来当主元，整行除以它
    变成 1，再用这一行把同列的其他行全部消成 0。找不到非零元就说明这一列没有主元，
    留给自由变量，直接换下一列。
    """
    if not A:
        return []
    matrix = [[Fraction(value) for value in row] for row in A]
    row_count = len(matrix)
    column_count = len(matrix[0])
    pivot_row = 0
    for column in range(column_count):
        if pivot_row >= row_count:
            break
        chosen = None
        for row in range(pivot_row, row_count):
            if matrix[row][column] != 0:
                chosen = row
                break
        if chosen is None:
            continue
        matrix[pivot_row], matrix[chosen] = matrix[chosen], matrix[pivot_row]
        divisor = matrix[pivot_row][column]
        matrix[pivot_row] = [value / divisor for value in matrix[pivot_row]]
        for row in range(row_count):
            if row == pivot_row:
                continue
            factor = matrix[row][column]
            if factor == 0:
                continue
            matrix[row] = [value - factor * pivot
                           for value, pivot in zip(matrix[row], matrix[pivot_row])]
        pivot_row += 1
    return matrix


def pivot_columns(A):
    """主元所在列的下标（升序）。最简行阶梯形里每个非零行的第一个非零元就是主元。"""
    matrix = rref(A)
    columns = []
    for row in matrix:
        for index, value in enumerate(row):
            if value != 0:
                columns.append(index)
                break
    return sorted(columns)


def rank(A):
    """矩阵的秩：主元的个数，也等于线性无关的列数、变换后剩下的维数。"""
    return len(pivot_columns(A))


def solve(A, b):
    """解线性方程组 Ax = b，返回解的结构（键的约定见任务文件的模块 docstring）。"""
    if not A or any(len(row) == 0 for row in A):
        raise ValueError('系数矩阵为空或存在空行：没有未知量，谈不上解方程组')
    if len(A) != len(b):
        raise ValueError(f'系数矩阵有 {len(A)} 行，右端项有 {len(b)} 个数，两者必须一样多')

    unknown_count = len(A[0])
    augmented = rref(augment(A, b))

    for row in augmented:
        coefficients = row[:unknown_count]
        if all(value == 0 for value in coefficients) and row[unknown_count] != 0:
            return {'kind': 'none'}

    pivots = pivot_columns(augmented)
    pivot_row_of = {}
    for row in augmented:
        for index, value in enumerate(row[:unknown_count]):
            if value != 0:
                pivot_row_of[index] = row
                break

    if len(pivots) == unknown_count:
        solution = [pivot_row_of[column][unknown_count] for column in pivots]
        return {'kind': 'unique', 'solution': solution}

    free_columns = [column for column in range(unknown_count) if column not in pivots]
    particular = [Fraction(0)] * unknown_count
    for column in pivots:
        particular[column] = pivot_row_of[column][unknown_count]

    null_basis = []
    for free in free_columns:
        vector = [Fraction(0)] * unknown_count
        vector[free] = Fraction(1)
        for column in pivots:
            vector[column] = -pivot_row_of[column][free]
        null_basis.append(vector)

    return {'kind': 'infinite', 'particular': particular,
            'null_basis': null_basis, 'free_count': len(free_columns)}


if __name__ == '__main__':
    print('把本文件当模块用：python3 -m unittest -v（见模块 docstring 的「跑法」）')
