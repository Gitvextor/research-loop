---
title: 矩阵与线性变换
goal: 能把矩阵读成对空间的变换，并说出秩与零空间的含义。
---

## 一张照片被拉斜

修图软件里有一根「斜切」滑杆。拉动它时，照片上每个像素的坐标 $(x, y)$ 按同一条规则搬到新位置：
横坐标变成 $x + 2y$，纵坐标不变。原来落在 $(0, 0)$ 与 $(1, 0)$ 上的两个点不动；原来落在 $(0, 1)$
上的点跑到 $(2, 1)$。画面里竖直的边被推斜，水平的边保持水平，整张图像一块被压扁的方格纸。

把每个点按同一条规则搬走，这件事在 19 世纪被称为一次**变换**（transformation）——当时研究的是
几何图形的整体搬动，后来发现只要规则足够简单，整个空间的行为可以由很少几条信息定下来。这节课要做
两件事：把「矩阵」与「变换」对上号，再用两个数（秩与零空间维数）说清一次变换压掉了什么。

## 只有两条规矩的映射

把平面上的点搬到平面上的点，这样的规则称为映射。若映射 $T$ 满足下面两条，就称它是**线性变换**
（linear transformation）：对任意向量 $u, v$ 与任意实数 $c$，

$$
T(u + v) = T(u) + T(v), \qquad T(cv) = c\,T(v)
$$

第一条说「先加再搬」与「先搬再加」结果相同，第二条说数乘可以先提出来。两条合起来还能得到一个推论：
取 $c = 0$ 得 $T(0) = 0$，原点在任何线性变换下都不动。斜切满足这两条：两个点先相加再斜切，与
分别斜切再相加，落点一样。

::: warn 平移不是线性变换
把所有点向右挪一格，规则是 $T(x, y) = (x + 1, y)$。它把原点送到 $(1, 0)$，不满足 $T(0) = 0$，
所以它不是线性变换。修图软件里的「平移」滑杆、神经网络里的偏置项，都属于这一类「仿射」动作——
带一个不动的偏移，要单独处理。
:::

## 矩阵是基向量的落点

平面上任意一个向量都能写成两个基向量的组合。标准基是 $e_1 = (1, 0)$ 与 $e_2 = (0, 1)$：

$$
\begin{bmatrix} x \\ y \end{bmatrix}
= x \begin{bmatrix} 1 \\ 0 \end{bmatrix} + y \begin{bmatrix} 0 \\ 1 \end{bmatrix}
$$

把线性变换的两条规矩用上去，$T$ 作用在这个组合上时，系数可以原样提出来：

$$
T \begin{bmatrix} x \\ y \end{bmatrix}
= x\, T \begin{bmatrix} 1 \\ 0 \end{bmatrix} + y\, T \begin{bmatrix} 0 \\ 1 \end{bmatrix}
$$

右边只有两个未知量：两个基向量被搬到了哪里。也就是说，**一次线性变换完全由基向量的落点决定**。
把这两个落点并排写成一个数表，就得到**矩阵**（matrix，拉丁文原意是「母体」，19 世纪的西尔维斯特
借它表示「数的出生地」）。斜切的两个落点是 $T(e_1) = (1, 0)$ 与 $T(e_2) = (2, 1)$，所以

$$
A = \begin{bmatrix} 1 & 2 \\ 0 & 1 \end{bmatrix}
\qquad\Longrightarrow\qquad
A \begin{bmatrix} x \\ y \end{bmatrix}
= \begin{bmatrix} x + 2y \\ y \end{bmatrix}
$$

矩阵的第一列是 $e_1$ 的落点，第二列是 $e_2$ 的落点。乘法规则不用背：$Ax$ 就是「用 $A$ 的各列按
$x$ 的分量加权拼出来」，这是上一课已经会做的事。代几个具体向量进去：$A(1, 1) = (3, 1)$，
$A(2, 1) = (4, 1)$，$A(0, 1) = (2, 1)$。

::: svg
alt: 左边是单位方格与两个基向量，右边是斜切之后的平行四边形与两个落点
caption: 斜切：$e_1$ 不动，$e_2$ 向右倒，单位方格被拉成平行四边形

<svg viewBox="0 0 380 176" role="img" aria-hidden="true" font-family="sans-serif" font-size="11">
  <g stroke="currentColor" stroke-width="1" opacity="0.35">
    <line x1="20" y1="128" x2="170" y2="128"/><line x1="60" y1="24" x2="60" y2="150"/>
    <line x1="210" y1="128" x2="364" y2="128"/><line x1="238" y1="24" x2="238" y2="150"/>
  </g>
  <path d="M60 128 L100 128 L100 88 L60 88 Z" fill="currentColor" opacity="0.12"/>
  <path d="M238 128 L278 128 L338 88 L298 88 Z" fill="currentColor" opacity="0.12"/>
  <g stroke="currentColor" stroke-width="2" fill="none">
    <line x1="60" y1="128" x2="100" y2="128"/><line x1="60" y1="128" x2="60" y2="88"/>
    <line x1="238" y1="128" x2="278" y2="128"/><line x1="238" y1="128" x2="298" y2="88"/>
  </g>
  <g fill="currentColor">
    <circle cx="60" cy="128" r="2.5"/><circle cx="238" cy="128" r="2.5"/>
  </g>
  <g fill="currentColor" opacity="0.9">
    <text x="102" y="124">e1</text><text x="44" y="86">e2</text>
    <text x="280" y="124">(1, 0)</text><text x="302" y="86">(2, 1)</text>
    <text x="60" y="166">斜切之前</text><text x="252" y="166">斜切之后</text>
  </g>
</svg>
:::

::: quiz 理解 锚点：矩阵的列是基向量的落点
:::

## 术语：秩

秩（rank）这个说法由 19 世纪末的德国学派引入，原意是「等级、排位」，中文译名取「次序、等级」之义。
一个矩阵的**秩**是它的列向量里线性无关的最多个数；用上一课的话说，就是这些列一共提供了几个独立
方向。几何上它是**变换之后剩下的维数**：整个平面被搬到几维的东西上，秩就是几。

- 斜切矩阵 $A = \begin{bmatrix} 1 & 2 \\ 0 & 1 \end{bmatrix}$ 的两列 $(1, 0)$ 与 $(2, 1)$ 不成比例，秩为 $2$，平面被搬到整个平面上；
- $\begin{bmatrix} 1 & 2 \\ 2 & 4 \end{bmatrix}$ 的第二列是第一列的两倍，秩为 $1$，整个平面被搬到直线 $y = 2x$ 上；
- 零矩阵的两列都是零向量，秩为 $0$，所有点被搬到原点。

三种说法的同一个数：线性无关的列数、变换后空间的维数、化简成行阶梯形之后主元的个数。第一种是定义，
第三种是算法，第二种是为什么值得关心它。

| 矩阵 | 列向量的关系 | 秩 | 平面被搬到哪 |
| --- | --- | --- | --- |
| $\begin{bmatrix} 1 & 2 \\ 0 & 1 \end{bmatrix}$ | 两列不成比例 | 2 | 整个平面 |
| $\begin{bmatrix} 1 & 2 \\ 2 & 4 \end{bmatrix}$ | 第二列是第一列的 2 倍 | 1 | 一条过原点的直线 |
| $\begin{bmatrix} 0 & 0 \\ 0 & 0 \end{bmatrix}$ | 两列都是零向量 | 0 | 原点 |

::: quiz 理解 锚点：秩的几何含义
:::

## 术语：零空间

变换把一些输入压到了零向量上。所有被送到零向量的输入向量构成的集合，称为矩阵的**零空间**
（null space）：

$$
N(A) = \{\, v : Av = 0 \,\}
$$

零空间衡量的是「这次变换丢掉了多少信息」。以 $\begin{bmatrix} 1 & 2 \\ 2 & 4 \end{bmatrix}$ 为例，
$Av = 0$ 就是两个方程 $x + 2y = 0$ 与 $2x + 4y = 0$；第二个方程只是第一个的两倍，所以解集由
$x + 2y = 0$ 决定：

$$
\begin{bmatrix} 1 & 2 \\ 2 & 4 \end{bmatrix}
\begin{bmatrix} x \\ y \end{bmatrix}
= \begin{bmatrix} 0 \\ 0 \end{bmatrix}
\qquad\Longrightarrow\qquad
(x, y) = t\,(-2, 1), \quad t \in \mathbb{R}
$$

零空间是过原点的一条直线，维数 $1$。注意 $(-2, 1)$ 这个方向：$A(-2, 1) = (-2 + 2, -4 + 4) = (0, 0)$，
它正好是让画面被压扁的那个方向。

秩与零空间维数之间的关系是这个节点的核心结论：

$$
\operatorname{rank}(A) + \dim N(A) = n
$$

其中 $n$ 是矩阵的**列数**，也就是输入向量的分量个数、未知量的个数。直观解释：输入的 $n$ 个方向分成
两部分，一部分被压没了（零空间，$\dim N(A)$ 个），另一部分活了下来（像空间，$\operatorname{rank}(A)$
个）。上面那个矩阵：$1 + 1 = 2$，正好是列数。

::: svg
alt: 左图是平面被矩阵压到一条直线上的两支列向量，右图是零空间方向被压到原点
caption: 秩 1 的矩阵：整个平面压到直线 $y = 2x$ 上（左），方向 $(-2, 1)$ 被压成零（右）

<svg viewBox="0 0 380 176" role="img" aria-hidden="true" font-family="sans-serif" font-size="11">
  <g stroke="currentColor" stroke-width="1" opacity="0.35">
    <line x1="24" y1="120" x2="168" y2="120"/><line x1="84" y1="20" x2="84" y2="152"/>
    <line x1="212" y1="120" x2="362" y2="120"/><line x1="276" y1="20" x2="276" y2="152"/>
  </g>
  <g stroke="currentColor" fill="none">
    <line x1="36" y1="144" x2="160" y2="82" stroke-width="1.5" opacity="0.8"/>
    <line x1="84" y1="120" x2="114" y2="105" stroke-width="2"/>
    <line x1="84" y1="120" x2="144" y2="90" stroke-width="2" stroke-dasharray="5 3"/>
    <line x1="228" y1="144" x2="352" y2="82" stroke-width="1.5" opacity="0.8"/>
    <line x1="276" y1="120" x2="306" y2="105" stroke-width="2"/>
    <line x1="276" y1="120" x2="246" y2="135" stroke-width="2"/>
    <line x1="336" y1="90" x2="246" y2="135" stroke-width="1" stroke-dasharray="3 3" opacity="0.7"/>
  </g>
  <g fill="currentColor">
    <circle cx="84" cy="120" r="2.5"/><circle cx="276" cy="120" r="2.5"/>
  </g>
  <g fill="currentColor" opacity="0.9">
    <text x="118" y="102">(1, 2)</text><text x="146" y="86">(2, 4)</text>
    <text x="60" y="164">两列共线，像是一条线</text>
    <text x="310" y="102">(1, 2)</text><text x="228" y="150">(−2, 1)</text>
    <text x="230" y="164">这个方向被压成零</text>
  </g>
</svg>
:::

::: quiz 排错 锚点：零空间维数
:::

## 边界与反例

- 秩不是「矩阵里非零数的个数」，也不是「原矩阵非零行的行数」。$\begin{bmatrix} 1 & 2 \\ 2 & 4 \end{bmatrix}$ 两行都有非零数，秩却是 $1$——数非零行只有在化成行阶梯形之后才等于秩。
- 零空间永远包含零向量，所以它永远不是空集。满秩矩阵的零空间里只有零向量，维数是 $0$；「非空」与「有非零向量」是两件事。
- 秩-零化度定理右边是列数。一个 $3 \times 2$ 的矩阵有两列，秩最多是 $2$，零空间维数最多也是 $2$，与它有几行无关。
- 变换的复合写成矩阵乘法时顺序不能交换：先斜切再旋转，与先旋转再斜切，通常得到不同的画面。$AB$ 与 $BA$ 是两个不同的矩阵。

## 用 Python 看一次压扁

```python
A = [[1, 2], [2, 4]]            # 两列成比例，秩为 1

def apply(matrix, vector):
    return [sum(a * v for a, v in zip(row, vector)) for row in matrix]

for v in ([1, 1], [2, 0], [3, -1], [-2, 1]):
    print(v, '->', apply(A, v))
```

四行输出依次是 `(3, 6)`、`(2, 4)`、`(1, 2)`、`(0, 0)`。前三个落点都落在直线 $y = 2x$ 上，
最后一个落在原点：$(-2, 1)$ 正是零空间里的那个方向。

::: practice 上手做 | 第 1 步 · 让几个向量过一遍矩阵

把上面那段存成 `transform.py` 跑一遍，然后做两件事：

1. 把 `A` 换成斜切矩阵 `[[1, 2], [0, 1]]`，看四个落点分别在哪；哪个方向落回了零向量？
2. 把 `apply(A, [1, 0])` 与 `apply(A, [0, 1])` 打印出来，与 `A` 的两列对照。

第 1 步会发现斜切矩阵的零空间里只有零向量：它的两列不成比例，秩为 2，没有方向被压掉。
:::

## 练习：从落点反推矩阵

::: practice 练习 | 第 2 步 · 从落点写出矩阵

一个线性变换把 $e_1$ 送到 $(2, 1)$，把 $e_2$ 送到 $(-1, 3)$。

1. 写出它的矩阵 $A$；
2. 用「各列按分量加权」的规则算出 $A(1, 1)$；
3. 判断它的秩是几，并说明零空间里除了零向量还有没有别的向量。

第 3 问的结论可以先用两列是否成比例来判断，下一课会给出通用的算法（消元数主元）。
:::

## 这一课的一个模型

矩阵在这一课里换了一个身份：它是一个动作。两列记下基向量被搬到哪里，整个平面随之被搬动。这一次变换
压掉了多少，由秩回答；被压掉的那些方向，由零空间回答；两个数加起来等于输入的维数。下一课把解一般
方程组的过程写成算法，让「有没有解、解有几个」变成两次计数。

::: resources
- [3Blue1Brown · 线性变换与矩阵](https://www.3blue1brown.com/lessons/linear-transformations) | 视频 · 每一列是基向量的落点
- [MIT 18.06 第 5~9 讲（列空间与零空间）](https://ocw.mit.edu/courses/18-06sc-linear-algebra-fall-2011/) | 视频 · 秩与零空间的课堂推导
- [Mathematics for Machine Learning 第 2 章](https://mml-book.github.io/) | 书 · 第 2.7 节讲线性映射与矩阵的对应
- [NumPy 官方文档 · numpy.linalg.matrix_rank](https://numpy.org/doc/stable/reference/generated/numpy.linalg.matrix_rank.html) | 官方文档 · 想核对现成库怎么数秩时看它
:::
