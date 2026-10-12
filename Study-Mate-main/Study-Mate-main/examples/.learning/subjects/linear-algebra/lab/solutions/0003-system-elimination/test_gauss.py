"""StudyMate · 实操 0003-system-elimination 的自检（python3 -m unittest -v）

跑法：先进入本文件所在目录，再跑

    python3 -m unittest -v

交付状态下是**红的**：教程部分（增广矩阵的拼装与校验）那 2 条通过，标了「任务」的四个函数此刻
抛 NotImplementedError，整份测试以非零退出码结束。这就是起点——一次实现一个函数，跑一次测试，
看对应的那几条转绿。

四个函数都实现完之后，全部断言应当通过（python3 -m unittest 退出码 0）。

断言的形状就是交付要求：解的结构是一个 dict，三种 kind 各带哪些键，见 gauss.py 的模块
docstring。用 Fraction 做相等比较，别用 float。
"""

import unittest
from fractions import Fraction

from gauss import augment, pivot_columns, rank, rref, solve

F = Fraction


class TestTutorial(unittest.TestCase):
    """教程部分：augment 已经写好，这两条一直是绿的。"""

    def test_augment_puts_rhs_in_the_last_column(self):
        self.assertEqual(augment([[1, 2], [3, 4]], [5, 6]), [[1, 2, 5], [3, 4, 6]])

    def test_augment_rejects_length_mismatch(self):
        with self.assertRaises(ValueError):
            augment([[1, 2], [3, 4]], [5])


class TestRref(unittest.TestCase):
    """任务 1：化成最简行阶梯形。"""

    def test_result_is_reduced(self):
        got = rref([[2, 4, 2, 8], [1, 2, 3, 9]])
        self.assertEqual(got, [[1, 2, 0, F(3, 2)], [0, 0, 1, F(5, 2)]])

    def test_lesson_example_becomes_identity(self):
        got = rref([[1, 1, 1, 6], [2, 1, 3, 13], [1, 3, 1, 10]])
        self.assertEqual(got, [[1, 0, 0, 1], [0, 1, 0, 2], [0, 0, 1, 3]])

    def test_zero_rows_go_last(self):
        got = rref([[1, 2, 3], [2, 4, 6]])
        self.assertEqual(got, [[1, 2, 3], [0, 0, 0]])

    def test_zero_matrix_stays_zero(self):
        self.assertEqual(rref([[0, 0], [0, 0]]), [[0, 0], [0, 0]])

    def test_does_not_touch_the_input(self):
        matrix = [[2, 4], [1, 3]]
        rref(matrix)
        self.assertEqual(matrix, [[2, 4], [1, 3]])

    def test_empty_matrix(self):
        self.assertEqual(rref([]), [])


class TestPivotsAndRank(unittest.TestCase):
    """任务 2 与任务 3：主元列与秩。"""

    def test_pivot_columns(self):
        self.assertEqual(pivot_columns([[1, 2, 0, 1.5], [0, 0, 1, 2.5]]), [0, 2])

    def test_pivot_columns_of_degenerate_matrix(self):
        self.assertEqual(pivot_columns([[1, 2, 3], [2, 4, 6]]), [0])
        self.assertEqual(pivot_columns([[0, 0], [0, 0]]), [])
        self.assertEqual(pivot_columns([]), [])

    def test_rank_counts_independent_columns(self):
        self.assertEqual(rank([[1, 2], [2, 4]]), 1)
        self.assertEqual(rank([[2, 1], [1, 3]]), 2)
        self.assertEqual(rank([[1, 1, 1], [2, 2, 2], [1, -1, 0]]), 2)
        self.assertEqual(rank([[0, 0], [0, 0]]), 0)


class TestSolveUnique(unittest.TestCase):
    """任务 4 的一种情形：唯一解。"""

    def test_three_by_three_integers(self):
        got = solve([[1, 1, 1], [2, 1, 3], [1, 3, 1]], [6, 13, 10])
        self.assertEqual(got['kind'], 'unique')
        self.assertEqual(got['solution'], [1, 2, 3])

    def test_two_by_two_gives_exact_fractions(self):
        got = solve([[2, 1], [1, 3]], [1, 2])
        self.assertEqual(got['kind'], 'unique')
        self.assertEqual(got['solution'], [F(1, 5), F(3, 5)])
        self.assertIsInstance(got['solution'][0], Fraction)

    def test_input_is_not_modified(self):
        A, b = [[2, 1], [1, 3]], [1, 2]
        solve(A, b)
        self.assertEqual((A, b), ([[2, 1], [1, 3]], [1, 2]))


class TestSolveNone(unittest.TestCase):
    """任务 4 的第二种情形：无解。"""

    def test_contradiction_row_means_none(self):
        got = solve([[1, 2], [2, 4]], [1, 3])
        self.assertEqual(got['kind'], 'none')
        self.assertNotIn('solution', got)

    def test_three_by_three_with_contradiction(self):
        got = solve([[1, 1, 1], [2, 2, 2], [1, -1, 0]], [3, 8, 0])
        self.assertEqual(got['kind'], 'none')


class TestSolveInfinite(unittest.TestCase):
    """任务 4 的第三种情形：无穷多解。"""

    def test_one_free_variable(self):
        got = solve([[1, 2], [2, 4]], [1, 2])
        self.assertEqual(got['kind'], 'infinite')
        self.assertEqual(got['free_count'], 1)
        self.assertEqual(len(got['null_basis']), 1)
        self.assertEqual(got['particular'], [1, 0])
        self.assertEqual(got['null_basis'][0], [-2, 1])

    def test_lesson_practice_system(self):
        got = solve([[1, 1, 1], [2, 2, 2], [1, -1, 0]], [4, 8, 0])
        self.assertEqual(got['kind'], 'infinite')
        self.assertEqual(got['free_count'], 1)
        self.assertEqual(got['particular'], [2, 2, 0])
        self.assertEqual(got['null_basis'][0], [F(-1, 2), F(-1, 2), 1])

    def test_null_basis_vectors_are_solutions(self):
        A = [[1, 1, 1], [2, 2, 2], [1, -1, 0]]
        got = solve(A, [4, 8, 0])
        for vector in got['null_basis']:
            product = [sum(a * v for a, v in zip(row, vector)) for row in A]
            self.assertEqual(product, [0, 0, 0])

    def test_two_free_variables(self):
        got = solve([[0, 0], [0, 0]], [0, 0])
        self.assertEqual(got['kind'], 'infinite')
        self.assertEqual(got['free_count'], 2)
        self.assertEqual(got['particular'], [0, 0])
        self.assertEqual(got['null_basis'], [[1, 0], [0, 1]])


class TestErrors(unittest.TestCase):
    """任务 4 的错误分支：这三条现在就会红，但报的是 NotImplementedError。"""

    def test_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            solve([[1, 2], [3, 4]], [1, 2, 3])

    def test_empty_input_raises(self):
        with self.assertRaises(ValueError):
            solve([], [])

    def test_empty_row_raises(self):
        with self.assertRaises(ValueError):
            solve([[]], [1])


if __name__ == '__main__':
    unittest.main(verbosity=2)
