# 线性代数 Resources

> 定位：**延伸阅读 + 易变内容的核对来源**，不是「知识来源清单」——稳定的定义与定理模型已经掌握。
> 这里放两类东西：某一课想换个人再讲一遍的延伸材料；以及屏幕上的名词（库的函数名、返回值、异常）
> 需要核实时去哪儿查。

## Knowledge

- [3Blue1Brown · 线性代数的本质（主题页）](https://www.3blue1brown.com/topics/linear-algebra)
  一行说明：整套动画把向量、线性组合、矩阵乘法、特征向量画成可以看的几何过程；课件里几何图像过不去
  时用它换一个讲法。
- [3Blue1Brown · 向量究竟是什么](https://www.3blue1brown.com/lessons/vectors)
  一行说明：同一个向量在物理、计算机、数学三种语境下的读法，第 1 课开场用。
- [3Blue1Brown · 线性组合、张成与基向量](https://www.3blue1brown.com/lessons/span)
  一行说明：张成与线性无关的动画解释；看完能自己判断三个三维向量是否共面。
- [3Blue1Brown · 线性变换与矩阵](https://www.3blue1brown.com/lessons/linear-transformations)
  一行说明：「矩阵的每一列是基向量变换后的落点」这句话的画面版，配合第 2 课的网格示意图看。
- [3Blue1Brown · 基变换](https://www.3blue1brown.com/lessons/change-of-basis)
  一行说明：第 4 课（基、维数与坐标）的预备读物；坐标是相对于一组基才有的东西，这集讲得最直观。
- [MIT 18.06 Linear Algebra（Gilbert Strang，Fall 2011）](https://ocw.mit.edu/courses/18-06sc-linear-algebra-fall-2011/)
  一行说明：MIT 本科线代公开课，视频、讲稿与习题齐全。第 1~2 讲消元、第 5~9 讲列空间与零空间、
  第 21~22 讲特征值，正好对应本课各节点。它的顺序是先讲消元再讲向量空间，与本大纲相反——用来补
  推导，不用来排学习顺序。
- [Mathematics for Machine Learning（Deisenroth 等，剑桥大学出版社）](https://mml-book.github.io/)
  一行说明：机器学习方向的数学教材，官方 PDF 免费。第 2 章覆盖向量、矩阵与线性方程组，第 4 章讲
  矩阵分解；记号偏工程，适合当「论文里的符号长什么样」的对照读物。
- [SymPy 官方文档 · 矩阵模块（含 rref / rank / columnspace）](https://docs.sympy.org/latest/modules/matrices/matrices.html)
  一行说明：**易变内容的核对来源**。要查现成库怎么表示矩阵、`rref()` 返回什么、主元列下标长什么
  样子时看这一页；这类返回值与参数名在大版本之间调整过，别凭记忆写。
- [NumPy 官方文档 · numpy.linalg.solve](https://numpy.org/doc/stable/reference/generated/numpy.linalg.solve.html)
  一行说明：**易变内容的核对来源**。核对 `solve` 的签名与异常：方阵奇异或不是方阵时抛
  `LinAlgError`，这一条以页面为准（本课 lab 自己处理无解与无穷多解，不抛这个异常）。
- [NumPy 官方文档 · 线性代数例程总览](https://numpy.org/doc/stable/reference/routines.linalg.html)
  一行说明：核对 `matrix_rank` / `eig` / `lstsq` 的准确函数名与返回顺序，第 2 课与第 5 课写核对脚本时用。
- [Python 官方文档 · fractions.Fraction](https://docs.python.org/zh-cn/3/library/fractions.html)
  一行说明：**易变内容的核对来源**。本课 lab 用分数做精确消元的依据；`Fraction` 与 `float` 混算会
  退化成浮点，构造器接受 `float` 的行为与规范化用的 `math.gcd()` 都在版本间变过，以页面为准。

## Wisdom (Communities)

- [Mathematics Stack Exchange · linear-algebra 标签](https://math.stackexchange.com/questions/tagged/linear-algebra)
  一行说明：拿一个具体矩阵去问「为什么这一步消元不改变解集」这类问题；把矩阵原样贴出来，比描述更快
  得到回答。提问前先搜，重复率很高。
- [r/3Blue1Brown](https://www.reddit.com/r/3blue1brown/)
  一行说明：某集动画里跳过去的那一步想找别人补推导时用；属于闲聊型社区，适合问「这个直观解释对不对」。

## Gaps

- 没有找到「以图像压缩为线索讲特征分解」的高质量中文材料：第 5 课实验要用的真实过程，目前只能拿
  人口迁移这类离散迭代自己造数据，图像那一侧还缺一个能跑、能看的样例。
- 手写消元的排错材料（人工消元常错在哪、怎么自检）没有权威来源，本课 lab 的自检清单是自己总结的，
  以后在教材里找到对应小节再替换。
- 暂无中文的「线性代数与 Python 标准库对照」材料：lab 里只用标准库是有意为之，与 numpy 的对照目前
  靠 `RESOURCES.md` 里那两条官方文档手工完成。
