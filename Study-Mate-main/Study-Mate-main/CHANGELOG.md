# 更新日志

<!-- studymate-release:v0.2.0 -->
## [0.2.0](https://github.com/Miaotofu01/Study-Mate/releases/tag/v0.2.0) - 2026-09-24

### 所有提交

- feat(gpt插件)：新增的codex/gpt插件支持 ([7e2552e](https://github.com/Miaotofu01/Study-Mate/commit/7e2552e8823d4c6423ba3c799cf26607fe3932b0))
- feat(gpt插件)：新增的codex/gpt插件支持 ([838604f](https://github.com/Miaotofu01/Study-Mate/commit/838604f0916e85006efb645bb7ba1276f397d0a2))

  > 修复 Windows Node 22.19 中文路径下测试示例复制，保留插件导出和课件渲染回归。


[完整比较](https://github.com/Miaotofu01/Study-Mate/compare/v0.1.5...v0.2.0)
<!-- /studymate-release:v0.2.0 -->

<!-- studymate-release:v0.1.5 -->
## [0.1.5](https://github.com/Miaotofu01/Study-Mate/releases/tag/v0.1.5) - 2026-09-24

### 已合并的 Pull Request

- fix(attachments): render GLOSSARY and RESOURCES markdown to static HTML ([#12](https://github.com/Miaotofu01/Study-Mate/pull/12))
- fix(lesson-design): restore practice stage naming rule ([#15](https://github.com/Miaotofu01/Study-Mate/pull/15))

### 所有提交

- fix(安装): install.ps1 加 UTF-8 BOM，PowerShell 5.1 不再按 GBK 解码 ([26c2c08](https://github.com/Miaotofu01/Study-Mate/commit/26c2c083ebd594dceffd801c0c0bf6dd18f8f7ce))
- fix(attachments): render GLOSSARY and RESOURCES markdown to static HTML ([c9f919c](https://github.com/Miaotofu01/Study-Mate/commit/c9f919c515a74e9331fae7eb225378a47b5d10f6))
- Merge pull request \#12 from yMvvL/fix/attachment-markdown-rendering ([2cdba17](https://github.com/Miaotofu01/Study-Mate/commit/2cdba178914ee12515c110cb58eb87fa077c004d))

  > fix(attachments): render GLOSSARY and RESOURCES markdown to static HTML

- refactor(大纲)!: 删掉节点「过关标准」字段，判分锚下移到 objective 与题目判分要点 ([78393eb](https://github.com/Miaotofu01/Study-Mate/commit/78393eb6e7d1d2aadd683afe2e9cbfa7f3c72fbc))
- refactor(提示词): SKILL 正文改用「代称」指代文件（见 docs/文件归属.md） ([326e6f4](https://github.com/Miaotofu01/Study-Mate/commit/326e6f49a1cba76c2aef4c8228aa03c1a4b8ecb0))
- fix(lesson-design): restore practice stage naming rule ([ff50185](https://github.com/Miaotofu01/Study-Mate/commit/ff50185be2528b54fbaed8e12161682ae84efbc4))
- Merge pull request \#15 from GodBlessRen/fix/lesson-design-stage-name-rule ([ffc2b02](https://github.com/Miaotofu01/Study-Mate/commit/ffc2b022e16af10b89c7e94ad4666f98b6e2fb4d))

  > fix(lesson-design): restore practice stage naming rule

- refactor(提示词): 精简搜图的提示词 ([cf9a72a](https://github.com/Miaotofu01/Study-Mate/commit/cf9a72a74deaebd9c00367104f5f861da5423be1))
- refactor(提示词): 精简搜图的提示词 ([6575500](https://github.com/Miaotofu01/Study-Mate/commit/6575500dc4ecd5d9df89ed2ddbd832d8ce77f7b8))
- refactor(提示词): 精简 11 份规格并统一措辞 ([62865ee](https://github.com/Miaotofu01/Study-Mate/commit/62865eef1f23ac19d8f466aa3c8ab15644ed622f))

  > - 删掉 frontmatter 已经强制的机械约束重复（学生不会直接调用你、只能由总控加载、三条边界副本）
  > - 派工给的值收进 docs/文件归属.md 的角色表，删掉 learning-system 的值映射表
  > - 目录树、owner 声明、输入节标题三处去重；五份角色统一「\#\# 输入（总控在 prompt 里给）」
  > - 措辞统一：落盘→写盘、课件三件→课件三份产物、对位→对照、口径→标准

- test(提示词): 补回「中文阶段名」钉串（规则随 PR \#15 恢复） ([08163e7](https://github.com/Miaotofu01/Study-Mate/commit/08163e78ad0b1f6ce0e5b835e921b4dbd92d8e41))
- docs(设计): 修样例节点字段（补必填 kind、resources 改成对象数组、删已移除的 evidence） ([0e343ce](https://github.com/Miaotofu01/Study-Mate/commit/0e343ce2da64bcb59f58e94cb4f8aebc6916b3c1))

  > - kind 是 schema 必填项，样例里缺了
  > - resources 的元素是 {title,type} 对象，原来写成字符串数组
  > - evidence 字段已随「过关标准」一并移除，且 schema 是 additionalProperties: false，
  >   这份样例原本过不了 check\_curriculum.py（现在只剩样例本身的悬空前置引用）

- docs(设计): 目录树与角色计数对齐现状，工作区树改用真名 ([d58ec68](https://github.com/Miaotofu01/Study-Mate/commit/d58ec685082ba051f1a0b32c26c6af1160b81b1d))

  > - 技能份数 9 → 11，「三个角色」→ 五个角色（资料收集 / 采图 / 课程设计 / 讲解 / 练习评估），共 5 处
  > - 区域二把预设目录写了两遍，其中一遍漏了点；合并成 ~/.dsh/.agent-presets/learning/
  > - 区域三的汉化文件名（科目信息.md / 大纲.yaml …）换成真实文件名，并修掉指向
  >   工程约束的失效指针（那份清单现在在《文件归属》）
  > - docs/ 的注释补齐（课件内容格式、文件归属）；版本行 v1.3 → v1.4

- docs: 脚本清单收敛到《工程约束》§四 一处 ([7accbfe](https://github.com/Miaotofu01/Study-Mate/commit/7accbfe45f2b9da9f1c49131b50be213758e947e))

  > - 工程约束把「脚本一览」从占位符契约里拆出来，独立成 §四（前端选型、实测坑顺延为五、六）
  > - 使用说明 §五 删掉与它重复的 6 条命令，只留「什么时候跑 + 阻断项 + 退出码」+ 指针
  > - 使用说明 §三 的脚本指针改成直接指 §四，少一跳

- docs(导航): 把《文件归属》接进 README 与使用说明 ([3765841](https://github.com/Miaotofu01/Study-Mate/commit/376584108c050287d6aa777b991e7195da094eaa))

  > 它此前只被《工程约束》引用一次，属于半孤儿文档：
  > - README 的文档清单、使用说明的「相关文档」都加上它（含一句话定位）
  > - 使用说明 §六 的目录树旁声明「权威清单在文件归属」，避免两份树各说一套
  > - 顺带把 README 里工程约束的说明补上「脚本一览」

- docs(使用说明): 措辞对齐（落盘→写盘、落成→写成、修旧标题指针） ([9a8707f](https://github.com/Miaotofu01/Study-Mate/commit/9a8707f15e926b401fe93f2eeb29256944d65690))

  > - 落盘 → 写盘 5 处，落成 → 写成 4 处（与 SKILL 那批统一）
  > - 「课件三件」→「课件三份产物」，两处指针改指 record-keeping 现在的标题
  >   「课件三份产物的归属（lessons/）」（旧标题已不存在）
  > - 口径 → 标准 2 处

- docs: 措辞对齐（设计方案、课件内容格式） ([61f6414](https://github.com/Miaotofu01/Study-Mate/commit/61f64143b0c874af1aa0d3e9eaee145e71a4d681))

  > - 设计方案：落盘 → 写盘 4 处
  > - 课件内容格式：落成 → 写成 3 处、核心口径 → 核心约定
  > - 至此 docs/ 全目录 落盘 / 落成 / 课件三件 / 口径 清零

- docs(测试): 修自述失真的条数与套件数，补上漏掉的附件渲染套件 ([64f6919](https://github.com/Miaotofu01/Study-Mate/commit/64f6919b326037765fad9293dee760d3d11f7b5c))

  > 实测（run\_tests.sh 全绿）对照后修正：
  > - run\_tests.sh：快测 11 → 12 套、含浏览器 13 → 14 套；安装脚本 30 → 39 项、
  >   提示词规则 417 → 410 条、附件 Markdown 渲染 29 → 32 项
  > - tests/README：安装脚本 30 → 39 项、位次重排 21 → 22 例、规则条数 417 → 410 条；
  >   表格里补上 test\_attachment\_render.py（此前整份套件没进表）
  > - 「evidence 字段映射仍留在使用说明」这句不成立：字段本身已删，判分锚是节点
  >   objective + 每题 criteria，改指使用说明 §四

- refactor(提示词): 总控盘问优先推荐jupyter ([9b0f551](https://github.com/Miaotofu01/Study-Mate/commit/9b0f551fc0402842b58a9f204b1afb92d288ad6f))
- feat(示例): 线性代数示例科目（大纲、三节课、lab、档案） ([40edb98](https://github.com/Miaotofu01/Study-Mate/commit/40edb981715cd575e3e437be0100d4cacb4f1183))

  > - 5 个节点：向量与线性组合 / 矩阵与线性变换 / 高斯消元与解的结构（实操）/ 基、维数与坐标 / 特征值与特征向量（实验）
  > - 前三课各一份内容文件 + 题库（每课 3 个锚点，共 11 道题）+ 渲染产物；正文 186/217/237 行
  > - lab 0003：只用标准库实现 rref / pivot\_columns / rank / solve，留白态 20 条红、参考解 22 条全绿
  > - 三张自产示意图（脚本 assets/img/gen/linear-algebra-diagrams.py 可复现）+ 完整图片库索引
  > - 档案：评估记录（节点 1 通过，含缺口与追问）、学习记录（节点 2 带学生原话）、会话摘要、两处误解双落点
  > - 科目组件三件（style.css / quiz.js / lesson-toc.js）与 templates/assets/ 逐字节一致

- feat(示例): 计算机网络示例科目（大纲、三节课、lab、档案） ([23aab5f](https://github.com/Miaotofu01/Study-Mate/commit/23aab5f22cc92fb1d98872759ad2169872399337))

  > - 5 个节点：分层模型与封装 / 链路层与以太网帧 / IP 地址、子网与路由（实操）/ TCP 与可靠传输 / 实验：TCP 回显客户端与抓包
  > - 前三课各一份内容文件 + 题库（每课 3 个锚点，共 12 道题）+ 渲染产物；贯穿线索是「一次网页请求」
  > - lab 0003：只用标准库（ipaddress）实现 parse\_cidr / same\_subnet / split\_subnet，留白态 30 条红、参考解 17 条全绿
  > - 档案：评估记录（含学生先漏了帧尾 4 字节、追问后补上）、学习记录、会话摘要、三处误解双落点
  > - 科目组件三件与 templates/assets/ 逐字节一致；图片库为空索引（三节课全用内联 SVG）

- chore(示例): 生成示例工作区的页面与共享层（clone 即可点开） ([3d2a31f](https://github.com/Miaotofu01/Study-Mate/commit/3d2a31f72d5255096c065600c08af077ecdd02f4))

  > - 6 个课件页 + 2 个科目主页 + 根主页 + 术语表/资源清单/学习记录/会话摘要的附件页
  > - examples/.learning/assets/：整份共享层（sayo + 主题层 + 图标），离线打开不依赖网络
  > - gen\_home.py 链接自检通过；正文里只剩两处「下节课还没产出」的悬空指针（节点 4 规格是暂无课件）

- feat(检查): check\_lesson 增加「本地引用可达」（检查项 10） ([629ad38](https://github.com/Miaotofu01/Study-Mate/commit/629ad381724fae5d6cf6c53db00599858f818c52))

  > 页面可以同时「通过全部检查」和「点开是白板 / 404」：检查项 2/3 只核对引用写没写齐、
  > 第 9 项只管 &lt;img&gt;，而 gen\_home 的断链自检不管课件页。示例工作区里真踩到两次——
  > 科目 assets/ 缺 quiz.js 与 style.css（页面没样式、题点不动、侧栏出不来），
  > 以及正文里那条 lab 链接指向不存在的 README。
  > 
  > - check\_lesson.py：新增检查项 10，页面里所有 href/src 的本地目标必须真实存在；
  >   跳过外链/锚点/协议相对 //、HTML 注释里的示例路径、上下节课指针（落空是设计内的），
  >   ?查询串 与 \#片段 先剥掉、%xx 先解码（与第 9 项同口径）
  > - fixtures.py：临时科目改成真实布局（&lt;root&gt;/.learning/subjects/&lt;slug&gt;/），
  >   并铺共享层、科目组件与科目主页的占位文件——路径写歪了这套测试自己就红
  > - test\_lesson\_links.py：10 例（拦 4：正文死链、quiz.js / lesson-toc.js / 共享层缺失；
  >   放行 6：齐全、存在、外链锚点、注释内、带查询串、下节课未产出）
  > - learning-system：检查 FAIL 的归属补一条——缺科目组件或共享层文件是总控自己补齐，不打回角色
  > - README / 使用说明：阻断项清单补上这一条

- test(模板): 新增「模板与规格一致」套件，钉住规格与模板的静默漂移 ([29aeabb](https://github.com/Miaotofu01/Study-Mate/commit/29aeabb295a9af4ea6630006283c437611a54a91))

  > 规格是散文（写在 SKILL 与 docs/ 里），模板是另一份文件，两者之间没有测试连着。真出过事：
  > templates/GLOSSARY.md 一直写 \`\#\# Terms\`，而 docs/文件归属.md、learning-system、image-scout
  > 三处都按 \`\#\# 待掌握\` / \`\#\# 已掌握\` 读词——照模板建出来的术语表，采图查不到主题词、
  > 主页也没有那两节可读。这类漂移不会报任何错，只能靠交叉阅读发现。
  > 
  > - test\_templates.py：两边一起钉——规格侧仍要求这些分节名，模板侧必须真有；
  >   subject.yaml 的键与 subject.schema.json 完全一致，status 取值在 enum 里（8 项）
  > - run\_tests.sh / tests/README：登记为第 14 套快测（含浏览器 16 套）
  > 
  > 顺带：templates/GLOSSARY.md 本身已在示例重建那批里改成两节式，这条测试防它漂回去。

- feat(渲染器): 图注编号交给渲染器（作者只写描述，页内顺序自动编号） ([c05a104](https://github.com/Miaotofu01/Study-Mate/commit/c05a10458d0ea82cf8375c4941afa6518751dffe))

  > 编号是可推导的信息（这一页第几张图），要求作者手写必然漂移——示例里就出过同页两张图都写
  > 「图 1」，两门课的编号口径还不一致（一门整门连续、一门每课重开）。现在渲染器按页内出现顺序
  > 给号，::: figure 与 ::: svg 共用一条序列，输出形如「图 1 · 收拢过程」。
  > 
  > - render\_lesson.py：新增页内计数器与 numbered\_caption()；已写「图 N ·」的旧课件会剥掉旧号重编
  >   （所以重渲染幂等，老写法不改也不会重号）；没写 caption 的图不编号、也不占号（不出现跳号）
  > - docs/课件内容格式.md：figure/svg 的例子改成只写描述，补上编号规则与「正文里见图 N 要对一遍」的提醒
  > - learning-coach：caption 口径改成「只写一句话，编号由渲染器加，别自己写图 N」（钉串同步更新）
  > - test\_render\_lesson.py：新增 ⑬′ 一组（页内顺序 / 两类图共用序列 / 旧号剥掉重编 / 重渲染幂等 /
  >   空白 caption 不生成图注 / 只数有说明的图）
  > - 示例 6 份课件的 11 处手写编号去掉后重渲染：产物\*\*逐字节相同\*\*，6 页全过检查

- feat(公式): 课件支持数学排版（$…$ 行内 / $$…$$ 块级，离线 KaTeX） ([845d8d9](https://github.com/Miaotofu01/Study-Mate/commit/845d8d96e4cc8046cc74f2a0086e1984ce918005))

  > 线代示例暴露的真问题：系统里从来没有数学排版这条路（格式文档原来写「要排数学式写 ::: svg，
  > 或用纯文本」），于是矩阵写成 \`\`\`text 围栏、公式写成纯文本 + Unicode 下标——语法合规，看着就是没排版。
  > 
  > - render\_lesson.py：行内 \`$…$\`、块级 \`$$…$$\`（整段只有它时出 &lt;div class="math-block"&gt;，
  >   段落中间出 &lt;span class="math-block"&gt;）；判据是「开 $ 后、收 $ 前都不能是空白，中间不跨行」，
  >   散文里的价格写法不误判；没收尾按行号报错（页面只会显示 TeX 原文，看不出错，所以必须拦下）；
  >   \`\\$\` 是字面美元号；代码围栏与行内代码里的 \`$\` 不受影响
  > - 按需注入：只有页面里真有公式时才在壳里加 KaTeX 三件（katex.min.css / katex.min.js /
  >   lesson-math.js）——非数学课与老课件产物零 diff（模板新增 &lt;!-- @LEARN:MATH --&gt; 占位符）
  > - templates/assets/katex/：KaTeX 0.18.7（MIT）整体 vendor，只留 woff2 字体（20 个，CSS 里去掉
  >   woff/ttf 回退），共 600 KB；templates/assets/lesson-math.js 负责排版，KaTeX 没加载成功时
  >   元素里留着的 TeX 原文照样可读（降级不白屏）
  > - check\_lesson.py：新增检查项 11（条件判定）——页面里有 .math-inline / .math-block 就必须带这三个引用
  > - 共享层清单同步：gen\_home.ensure\_shared\_assets、preview\_templates、templates/assets/README.md
  > - 测试：渲染器 ⑬″ 一组（行内/块级/代码里不解析/\\$ 转义/没收尾报错/无公式不注入）、引用套件两条
  >   条件断言、新增真 Chrome 套件 browser/math\_test.mjs（断言 .katex 真出现、块级走 display、
  >   KaTeX 字体生效、写错的公式不炸整页）；套件 16 → 17
  > - 文档：课件内容格式第 3 节新增「数学式」、已知边界那条改写；learning-coach 加公式口径；
  >   使用说明与工程约束各补一句

- refactor(提示词): 优化课设规范 ([11669ef](https://github.com/Miaotofu01/Study-Mate/commit/11669ef177ce26f68f9a72a289757465be012060))
- docs(示例): 线性代数的公式改成 LaTeX 排版（矩阵、消元链、下标） ([31291ba](https://github.com/Miaotofu01/Study-Mate/commit/31291ba083a8b022c799b33b9f035e1ecae60590))

  > 引擎刚支持 $…$ / $$…$$，这三节课原来把数学写成「\`\`\`text 围栏 + 行内代码 + Unicode 下标」——
  > 语法合规但读起来是代码。现在：
  > 
  > - 0001 向量与线性组合：19 条行内 + 3 个块级（方程组与向量等式双列 aligned、矩阵 bmatrix、
  >   线性无关的通式）
  > - 0002 矩阵与线性变换：38 条行内 + 6 个块级（线性变换两条定义、T(x,y)=x·T(1,0)+y·T(0,1)、
  >   列落点示意图、斜切矩阵、秩-零化度定理、练习里的 C/D 矩阵）；表格里的 ASCII 矩阵也进单元格公式
  > - 0003 高斯消元：27 条行内 + 7 个块级。增广矩阵用 \\left\[\\begin{array}{ccc|c}…\\right\]（bmatrix
  >   画不出增广竖线），三段消元链改成 aligned + \\xrightarrow{\\text{第 2 行} - \\text{第 1 行}} 竖直链
  >   （横排会撑破版面）
  > - 判断标准：\*\*圆括号 (1, 2) 是数学向量 → 转公式；方括号 \[\[2, 1\], \[1, -1\]\] 是 Python 字面量、
  >   函数名与路径 → 留代码\*\*；print 输出、报错原文、练习答案清单保持代码块
  > - examples/.learning/assets/：入库共享层的 KaTeX（katex/ 与 lesson-math.js），示例页因此
  >   clone 下来就能离线看排版
  > 
  > 验收：三页 check\_lesson 全 OK（只剩既有的「下节课未产出」WARN）；三份产物在真实 headless Chrome
  > 里 0 个未渲染、0 个 katex-error、块级全 display、字体 KaTeX\_\*；全量 17 套测试通过。

- fix(检查): 「科目主页还没生成」不再拦课件（生成产物不是作者的错） ([d396086](https://github.com/Miaotofu01/Study-Mate/commit/d3960869bf82a06d363a3636b2186f0af88af03e))

  > 重跑示例时子 agent 撞到的真问题：课件壳里那条固定回链 \`../index.html\` 指向的是
  > \`&lt;科目&gt;/index.html\`，它是 \`gen\_home.py\` 的产物——检查项 10 把它判成课件的引用缺陷，
  > 于是每门新科目在跑生成器之前，三节课全都带一条拦不下来的 FAIL。
  > 
  > 作者的活产不出这个文件，缺了是流水线顺序问题。改成：目标不存在且文件名是 \`index.html\` 时
  > 出一条提示（「科目主页还没生成：跑一次 gen\_home.py 就有了」），不阻断；其余本地引用照旧拦。
  > 
  > - check\_lesson.py：check\_local\_refs 返回 (problems, notes)，index.html 走 notes；
  >   文档串第 10 项写明这条例外
  > - test\_lesson\_links.py：加第 13 条（删掉科目的 index.html → 放行 + 提示）；
  >   套件计数同步到 13

- docs(示例): 线性代数科目按新规格重跑（公式全 LaTeX、图全 SVG） ([9de7728](https://github.com/Miaotofu01/Study-Mate/commit/9de772826fba82007d3fc863c8ef79451c6b9ee9))

  > 推倒重来的一版：让子 agent 只按现在的规格（docs/课件内容格式.md + lesson-design +
  > layered-practice）重写，不用上一版的手工修补。这一版顺带是对「数学排版 + 图注自动编号 +
  > 术语表两节 + 检查项 10/11」这轮规格改动的验收。
  > 
  > - 公式 157 条全走 LaTeX（行内 50/71/30、块级 6/7/11）：矩阵 bmatrix、增广矩阵
  >   \\left\[\\begin{array}{ccc|c}…\\right\]、消元链 aligned + \\xrightarrow
  > - 图全用 ::: svg（张成、列视角落点、斜切前后网格、秩 1 压扁、三种解的情形）；
  >   上一版自产的 3 张 PNG 与生成脚本删掉——本机没有 matplotlib，SVG 也更符合规范
  > - 档案自洽：同一个失误在四处指得出来（抄错右端项 = 课件 warn 卡 = 题库排错题锚点 = session
  >   weakness；秩-零化度记成行数 = 学习记录 = progress 误解 = 排错题）；节点 3 的 0.3 与
  >   「rref 跑通、solve 未实现」在 progress / session / lab 三处对得上
  > - lab：留白态 21 条红 exit 1、参考解 23 条全绿 exit 0（没有跳过开关）
  > - 正文非空行 196/184/196；组件三件与 templates/assets/ 逐字节一致；pool.md 空索引 + Gaps

- docs(示例): 计算机网络科目按新规格重跑 ([86bc388](https://github.com/Miaotofu01/Study-Mate/commit/86bc3886a3f548931da6591fe8e9de10a3205de9))

  > 同一轮重跑的另外半门：网络零基础的学生画像、五个节点（分层/链路/IP/实验）、前 3 课成课。
  > 
  > - 公式 76 条走 LaTeX（行内 35/15/21、块级 2/1/2）；IP 地址、掩码、命令与抓包输出留代码
  >   （读者要逐字对），只有算式（如块大小 $2^6 = 64$）用公式
  > - 6 张内联 SVG（分层图、帧结构、子网划分、逐跳转发的路径图），每课 2 张；最小字号 ≥2% viewBox 宽
  > - 每课 1 个 ::: practice + 3 个 quiz 锚点、题库 5 题/课，键与锚点逐字一致
  > - lab：留白态 85 条 error exit 1、参考解 22 条全绿 exit 0；用法只用标准库（unittest + ipaddress）
  > - 档案自洽：/26 块大小算成 26、跨网段 MAC 这些真实错法同时出现在误解库、progress 与会话摘要里
  > - 正文非空行 174/165/191；组件三件与 templates/assets/ 逐字节一致；pool.md 空索引 + Gaps

- feat(公式): 题库里的公式也排版（题面/选项/答案/解析走同一套 KaTeX） ([0ac4bb7](https://github.com/Miaotofu01/Study-Mate/commit/0ac4bb7220b5ab3f8870f86744742464503f044f))

  > 上一轮只做了课件正文的数学；题库是纯文本字段、由 quiz.js 在运行时插入 DOM，\`$…$\` 原样显示
  > ——线代作业因此一道矩阵题都写不了（示例里只能平铺成「x + 2y = 1、2x + 4y = 2」）。
  > 
  > - quiz.js：新增 mathInto()，把字段按 \`$…$\` 切成文本节点 + &lt;span class="math-inline"&gt;（仍是纯
  >   文本路径，不走 innerHTML）；选项、点选后才出现的解析同样处理；建块完成与动态插入后各调一次
  >   LessonMath.render()
  > - lesson-math.js：暴露 window.LessonMath.render(root)，给排过的节点打标记——重复调用不会把
  >   上一次的产物当成 TeX 再排一遍
  > - render\_lesson.py：quiz\_has\_math() 扫题库的字符串字段；公式\*\*只出现在题面里\*\*时壳里也要注入
  >   KaTeX，否则题面排不出来
  > - check\_lesson.py：第 11 项的「页面有数学式」放宽到 data-quiz 属性里的 \`$…$\`（顺带修了自己一个
  >   正则 bug：属性引号必须配对捕获，否则 JSON 里的双引号会把内容截断）
  > - 测试：DOM 套件加场景九（40 项）· 浏览器套件加题面公式四态并把 fixture 改成\*\*生产脚本顺序\*\*
  >   （验的正是 quiz.js 自己排版那条路，10 项）· 渲染器加「公式只在题库里也注入」（29 例）·
  >   引用套件加「题库公式也算数学式」（14 例）
  > - 文档：课件内容格式（数学式节说明题面也支持 + quiz 节）、assets README 的 quiz.js 行、
  >   layered-practice 的题面写法 + 钉串（412 条）

- feat(数学): 方程组必须带大括号——写进规格，并加一条形态提示 ([62a8e80](https://github.com/Miaotofu01/Study-Mate/commit/62a8e80f8ebc2ae150c7ca93eecbbae7c3283d8d))

  > 示例线代课件里的方程组排成了三行等式、\*\*没有大括号\*\*：KaTeX 不会自己加，读者第一眼会把它们
  > 当成三个独立结论。根因不是"模型不会"——它在 chat 里默认会带 \`cases\`；是这里的三个信号把它
  > 压下去了：① 规格从没提过大括号（0 处）；② 派工 brief 示范的形状（bmatrix / array|c / aligned）
  > 全都不带括号，示例的权重比规则大；③ 验收看不见（当时的检查器管结构、引用、题目，不管这个）。
  > 产出正好是"我示范过的那套词汇"：5 处 aligned + 4 处 array、大括号 0 处。
  > 
  > - docs/课件内容格式.md：数学式一节新增「方程组要带大括号」——\`\\left\\{\\begin{aligned}…\\end{aligned}\\right.\`
  >   （等号对齐，中文教材排法）；分段函数/分类讨论用 \`\\begin{cases}…\\end{cases}\`；并说明为什么不能省
  > - learning-coach / layered-practice：公式口径各补一句（正文与题面都适用）
  > - check\_lesson.py：新增\*\*形态提示\*\*（只 WARN，不阻断）——\`aligned\` 里 ≥2 行带 \`&amp;=\` 却没被
  >   \`\\left\\{ … \\right.\` 包住就提示。判据保守：推导链（\`\\xrightarrow\`）与单条恒等式都不命中；
  >   这是"形态类"判据，不依赖逐条枚举约定
  > - 测试：引用套件加两条（缺括号 → 提示；带括号 → 不提示）→ 16 例；钉串 +3 → 414 条
  > 
  > 顺带说明：这条只覆盖"多行等式缺包裹"这一种形态。其余形态类问题（ASCII 伪矩阵、Unicode 下标、
  > 空格对齐数表）与"把约定固化成宏"是下一步，另开一笔。

- docs(示例): 线代的方程组补上大括号、题库数学改 LaTeX ([c827270](https://github.com/Miaotofu01/Study-Mate/commit/c82727057d784b85548b7db6aa4d577cb328086c))

  > 两件事一起做（都在示例里，产物由渲染器重生成）：
  > 
  > \*\*方程组补大括号\*\*：0001 两处、0003 五处（\`\\left\\{\\begin{aligned}…\\end{aligned}\\right.\`）。
  > 消元链那种推导不加括号——它不是方程组。补完 0003 的 11 个块级公式里有 5 个以 \`{\` 起头。
  > 
  > \*\*题库数学改 LaTeX\*\*（219 处公式，含 9 处矩阵）：题面/选项/参考答案/判分要点/解析里的
  > \`\[\[1, 2\], \[2, 4\]\]\` 变成 \`\\begin{bmatrix}…\\end{bmatrix}\`，\`(… | …)\` 数表变成
  > \`\\left\[\\begin{array}{ccc|c}…\\right\]\`（分数写 \`\\frac{1}{2}\`），\`e1\`/\`x·e1 + y·e2\` 变成
  > \`$e\_1$\` / \`$x e\_1 + y e\_2$\`。得分、量词、"N 倍"、中文说法写的算术、序数标签都保持散文——
  > 它们不是算式。
  > 
  > \*\*组件副本同步\*\*：quiz.js（两门各一份）与共享层 lesson-math.js 是 templates/assets/ 的副本，
  > 引擎改过就得覆盖（record-keeping 第 4 条），否则科目里的副本还是旧版、题面公式排不出来。
  > 
  > 验证：三页渲染 + 检查全 OK（只剩既有的「下节课未产出」WARN）；真实 Chrome 里
  > 题面公式 13/14/10 条、选项 16/12/0 条、解析 5/8/3 条全部排出来，块级公式分别有 2/0/5 个以
  > 大括号起头，katex-error 0。

- docs(数学): 方程组只写判据、不指定形状（\`cases\` 与 \`\\left\\{…\\right.\` 都行） ([e8c3a1c](https://github.com/Miaotofu01/Study-Mate/commit/e8c3a1c95175a7a6c7581117db39d3a1403a658c))

  > 做了一次对照实验（两臂只给"规格路径 + 值 + 验收"，一个字不提形状）：
  > 
  > | 大括号规则 | 我的形状清单 | 产出 |
  > |---|---|---|
  > | 无 | 有（派工时列的 bmatrix / array|c / aligned） | 0 处括号 |
  > | 无 | 无 | \*\*\`cases\` 10 处，一次没漏\*\* |
  > | 有 | 无 | \`\\left{\\begin{aligned}\` 5 处 |
  > 
  > 结论：\*\*先验自带大括号\*\*，元凶是我在派工 prompt 里列的形状清单（不完整的清单把正确的先验
  > 替换成了有缺口的模仿目标）；而规格里那条"必须用 \`\\left\\{…aligned…\\right.\`、\`cases\` 留给分段函数"
  > 是同一个毛病的另一种形态——过度指定形状。
  > 
  > - 课件内容格式：改成「方程组要带大括号（不写就没有）；\`cases\` 与 \`\\left\\{…aligned…\\right.\` 都行，
  >   前者省事、后者对齐等号」，并把两种写法并列举例
  > - learning-coach / layered-practice：同样只留判据（钉串不受影响，仍 414 条）

- fix(CI): 修掉 Python 3.12+ 的非法转义警告——它在 3.13 上把一条断言撑破了 ([37942fc](https://github.com/Miaotofu01/Study-Mate/commit/37942fc7233cdbdbb58b3a44d8dbbde68aa6662c))

  > CI 只在 Node 24 / Python 3.13 那三档红，Node 22.19.0 / Python 3.9 全绿。根因不是 Node：
  > 
  > - Python 3.12 起，字符串里的\*\*非法转义序列\*\*（\`'\\l'\` 这种）从静默变成 \`SyntaxWarning\`；
  > - 我在 check\_lesson.py 的模块文档串与一条提示语里写了 \`\\left\\{\`，3.13 下警告打到 stderr，
  >   而警告会\*\*回显那行源码\*\*（那行本来就含「大括号」三个字）；
  > - \`test\_lesson\_links.py\` 里那条断言写的是 \`'大括号' not in out\`（out = stdout + stderr），
  >   于是被警告文本撑破 → 该套件 exit 1 → checks.mjs 失败。
  > - 本地一直是绿的，因为本机 python 是 3.11（还没有这个警告）。
  > 
  > 改法（两处都修，缺一不可）：
  > - check\_lesson.py / test\_lesson\_links.py：含反斜杠的文档串与提示字符串改成\*\*原始字符串\*\*
  > - 那条断言改成只看 \`WARN\` / \`FAIL\` 行——解释器警告回显源码不该撑破断言
  > 
  > 验证：
  > - \`python -W error::SyntaxWarning -m compileall scripts/ templates/\`（3.13）干净
  > - \`uv run --python 3.13 node scripts/release/checks.mjs\`（完整模拟 CI 那一档）退出码 0
  > - 本地 14 套快测仍全绿

- test(CI): 加一道「全部 .py 能编译过」的静态体检——把这类问题根治在编译期 ([0bc2447](https://github.com/Miaotofu01/Study-Mate/commit/0bc24474b6756ac0ea458fc16064dbfaa2c6d3d9))

  > 上一提交修掉了那两处非法转义，但没有防住复发。这道补的是\*\*机制\*\*，不是某一行：
  > 
  > - 新 \`scripts/tests/test\_python\_syntax.py\`：把 \`scripts/\` 与 \`examples/\` 下\*\*全部 34 个 .py\*\*
  >   解析一遍，有语法级问题（含 3.12+ 的非法转义 SyntaxWarning）就带 \`文件:行号\` 报错。
  >   不依赖"测试正好跑到那个文件"——那正是这次漏掉的原因：\`check\_lesson.py\` 的转义是被别的测试
  >   间接跑出来的，报错信息还伪装成了断言失败。
  > - 自动进 CI：\`checks.mjs\` 按 \`test\_\*.py\` 通配跑全部套件，\*\*不用改 workflow\*\*。
  > - 版本盲区写在明面上：本机 Python &lt;3.12 不会为非法转义发警告，脚本自己打一行提示，
  >   并给出 \`uv run --python 3.13 …\` 的提前自查命令——免得"本地绿"被当成"没问题"。
  > - 本地套件 14 → 15 套（run\_tests.sh 与 tests/README 同步）。
  > 
  > 反向验证：往 check\_lesson.py 里注入一行 \`BROKEN = "\\left\\{"\` →
  >   3.13（CI 档）exit 1，报 \`scripts/check\_lesson.py:1088 invalid escape sequence '\\l'\`；
  >   3.11 通过并打印版本盲区提示。恢复后两边都绿。
  > 
  > （上一提交里"断言只看 WARN/FAIL 行"的改动保留：它不是遮问题——转义已在源头修掉，
  > 它只是让无关输出（解释器警告回显源码）不再撑破断言。）


[完整比较](https://github.com/Miaotofu01/Study-Mate/compare/v0.1.4...v0.1.5)
<!-- /studymate-release:v0.1.5 -->

<!-- studymate-release:v0.1.4 -->
## [0.1.4](https://github.com/Miaotofu01/Study-Mate/releases/tag/v0.1.4) - 2026-09-23

### 已合并的 Pull Request

- Fix/dsh old host graceful degrade ([#7](https://github.com/Miaotofu01/Study-Mate/pull/7))

### 所有提交

- Update README to remove studymate commands ([14c44f1](https://github.com/Miaotofu01/Study-Mate/commit/14c44f144738ba83850d6bfa98338dc431a12881))

  > Removed installation and upgrade instructions for studymate.

- fix: let old DSH hosts skip native plugin loading ([fbf7399](https://github.com/Miaotofu01/Study-Mate/commit/fbf7399148d13fb7e9c62f4efcbde1af8dd24b11))
- test: cover graceful fallback on old DSH hosts ([c42e81c](https://github.com/Miaotofu01/Study-Mate/commit/c42e81c2d349c087c34539d6712467d349358406))
- Merge pull request \#7 from GodBlessRen/fix/dsh-old-host-graceful-degrade ([f839b93](https://github.com/Miaotofu01/Study-Mate/commit/f839b9359943b7eaa7115040d48110bfb8d19a24))

  > Fix/dsh old host graceful degrade

- docs(README):新增配图 ([263dd5f](https://github.com/Miaotofu01/Study-Mate/commit/263dd5f3585cd7dd4697a2c75f64faea84ec0e24))
- docs(README):新增配图 ([1f0953a](https://github.com/Miaotofu01/Study-Mate/commit/1f0953a366a665d99755ca44da8677efd504c73e))
- docs(README):新增配图 ([c9667b8](https://github.com/Miaotofu01/Study-Mate/commit/c9667b8dfe4c4343d497b659e9755798d99a9181))
- fix(lesson-design):优化课件提示词 ([7813fb1](https://github.com/Miaotofu01/Study-Mate/commit/7813fb136eee3221ab31d84c030592699a904e05))
- fix(layered-practice):优化课件提示词 ([9da9090](https://github.com/Miaotofu01/Study-Mate/commit/9da909011349f6f9c1ed538d7465995812745887))
- 添加项目交流群 ([dc53a7c](https://github.com/Miaotofu01/Study-Mate/commit/dc53a7c74b7b21ad262d20b6dcbe3c7049288008))
- fix: protect DSH downgrades and make installer migration explicit ([883829f](https://github.com/Miaotofu01/Study-Mate/commit/883829ffcb5a5d77cc08e43a769c8c823fcb06dc))
- 修复：调整 CI 临时目录变量的使用位置 ([ca9bec0](https://github.com/Miaotofu01/Study-Mate/commit/ca9bec070cc452136149a15ae9d474f6f8dbd111))

  > 将 DSH 测试路径从作业级环境变量移到对应测试步骤，避免 runner.temp 在工作流校验阶段不可用，恢复兼容性检查的执行。

- fix：Readme 安装引导 ([261f15f](https://github.com/Miaotofu01/Study-Mate/commit/261f15f9bc8640b6e153e04f9dbb5b0a5faa8aae))

  > Updated installation instructions and added emphasis on npm installation.

- fix(ci)：等待 DSH 预设检查的异步结果 ([8dcc4fa](https://github.com/Miaotofu01/Study-Mate/commit/8dcc4fa82d12930d3638f6010b39312d407c8416))

  > 为两处 inactiveRows 检查补充 await，兼容 DSH 0.1.6 的异步返回值及旧版同步返回值，修复发布流程中的测试失败。
  > 
  > 验证：DSH 0.1.6-alpha.2 的运行时和 CLI 测试 5 项通过；DSH 0.1.5-rc.2 的运行时测试 2 项通过。

- fix(发布)：纠正修复代码后的重试说明 ([d868364](https://github.com/Miaotofu01/Study-Mate/commit/d8683643e328693ab27b6933966506fba766d7b1))

  > 检查失败后若已有修复提交且尚未创建版本 tag，应从最新 main 新建发布；重跑旧任务不会包含新提交。已有版本 commit/tag 的任务仍重跑原任务，保留原版本的恢复机制。


[完整比较](https://github.com/Miaotofu01/Study-Mate/compare/v0.1.3...v0.1.4)
<!-- /studymate-release:v0.1.4 -->

<!-- studymate-release:v0.1.3 -->
## [0.1.3](https://github.com/Miaotofu01/Study-Mate/releases/tag/v0.1.3) - 2026-09-23

### 所有提交

- ci: 等待 npm 完成异步包处理再核验发布 ([0862d57](https://github.com/Miaotofu01/Study-Mate/commit/0862d57178b312026dea69af8146c5923e61b758))
- feat: 支持 DSH 原生插件安装与更新 ([476f566](https://github.com/Miaotofu01/Study-Mate/commit/476f566df5f140c124991edb818aae68d5217535))
- Update README with upgrade instructions and version info ([cf1e2dd](https://github.com/Miaotofu01/Study-Mate/commit/cf1e2ddc7a975d9d87e21ac069bb423f3fad65d3))

  > Added upgrade instructions and updated version information.


[完整比较](https://github.com/Miaotofu01/Study-Mate/compare/v0.1.2...v0.1.3)
<!-- /studymate-release:v0.1.3 -->

<!-- studymate-release:v0.1.2 -->
## [0.1.2](https://github.com/Miaotofu01/Study-Mate/releases/tag/v0.1.2) - 2026-09-23

### 已合并的 Pull Request

- 修复若干问题 ([#3](https://github.com/Miaotofu01/Study-Mate/pull/3))

### 所有提交

- 修复安装路径含单引号、方括号等字符时安装失败或配置损坏的问题。 修复重复安装时无法正确沿用带特殊字符工作区的问题。 修复主页漏扫文件、特殊字符链接失效和空大纲显示旧进度的问题。 修复学习目标悬停提示显示成节点标题的问题。 修复非法大纲导致校验崩溃、重复节点造成编号异常及依赖方向提示错误的问题。 修复题目属性误报、多个题目块漏检和异常题库导致渲染崩溃的问题。 修复图片目录被误放行、编码路径误报和绝对路径漏拦的问题。 修复异常题目中断后续练习、无效题目参与计分的问题。 修复题号和反馈前缀破坏代码围栏，以及 Windows 换行解析失败的问题。 修复代码高亮误判字符串、破坏原文及未知语言触发异常的问题。 修复平板侧栏无法展开，以及切换手机布局后上下课导航消失的问题。 修复无题理由回填破坏换行格式、写入失败可能损坏原文件的问题。 修复课件重编号临时文件冲突、失败回滚不完整及恢复提示错误的问题。 修复技能调用开关判断错误、异常元数据中断批量检查的问题。 修复图片池索引放行错误列数、无效日期及非法文件名的问题。 修复 Windows 无法自动打开预览页面的问题。 修正示例答案路径和错误类型声明，并同步示例前端资源。 ([d3ff025](https://github.com/Miaotofu01/Study-Mate/commit/d3ff025e6d12b49d1d5eb7d01d67ef5ca8c5db21))
- fix:修复 MAC 在运行 install.sh 时将紧邻的中文括号误读为变量名 ([fb6ffd0](https://github.com/Miaotofu01/Study-Mate/commit/fb6ffd0ed628bc1c3e00a6df1c6ea99cf984a26c))
- 增加 npm 安装方式 ([61fc675](https://github.com/Miaotofu01/Study-Mate/commit/61fc6759164fea73ee1123fdfd638e844f954c34))
- Merge pull request \#3 from guoweiyi/main ([c69a768](https://github.com/Miaotofu01/Study-Mate/commit/c69a768597e08a2b83fb6ed672849f9ca75e5e2a))

  > 修复若干问题

- docs: 新增待办清单,方便人工维护 ([c8cb604](https://github.com/Miaotofu01/Study-Mate/commit/c8cb604a9acba16b6762d1c390bda840a61f2faf))
- README:新增前言 ([8af8275](https://github.com/Miaotofu01/Study-Mate/commit/8af8275a6977216923e356abceda03148372cc4c))
- README:修改readme ([b7e662f](https://github.com/Miaotofu01/Study-Mate/commit/b7e662f446a5949028698bb54a287cb3f56d959c))
- fix(提示词): 按 issue \#5 的实测反馈改课件与采图规则 ([a4ecc2c](https://github.com/Miaotofu01/Study-Mate/commit/a4ecc2c82a674979ee18009c567a6ce3c1904ee4))

  > - curriculum-designer：第一个节点改成用具体材料/案例开场，不再先上全景图
  > - lesson-design：术语与配图两条改成可执行的要求
  > - learning-coach：用图前必须先打开图片核对图注；补 SVG 不许写死宽度、字号下限
  > - image-scout：交稿前跑 check\_pool.py 并改到没有为止；主题词以 GLOSSARY.md 为准
  > - learning-system：开课先写 GLOSSARY.md 的「待掌握」，采图与课件共用同一套词
  > 
  > Refs \#5

- 修改:测试文件 ([84f3af7](https://github.com/Miaotofu01/Study-Mate/commit/84f3af7cea35ed83165d449728b196c2468063d6))
- fix(提示词): 第一课禁用学科定义/发展史/本课结构 ([632b441](https://github.com/Miaotofu01/Study-Mate/commit/632b441b28d78102965e93fff4f18919ec4d4d2b))
- feat(校验): check\_curriculum 报依赖位次倒挂 ([93d7923](https://github.com/Miaotofu01/Study-Mate/commit/93d7923182e95e111df3e8d994f8bb0c18fd9ff6))

  > 示例科目 typescript-web-api 现有一处倒挂（exp.pg-and-tests 依赖 test.api），本次未修。

- docs(README): 加 Star 趋势图 ([c79f2cd](https://github.com/Miaotofu01/Study-Mate/commit/c79f2cdd84739f44fc01e49ad68e01c237f61c28))
- fix: 兼容 DSH 新版预设与工作流插件 ([cb9e448](https://github.com/Miaotofu01/Study-Mate/commit/cb9e448d12a4de43cef4cfeef5412ef14ee33a25))

  > 分别适配 0.1.6 工作流更名和 0.1.7 声明式预设，保留旧版安装方式及用户配置。Refs \#4

- ci: 自动生成发布日志并发布 npm 包 ([88be504](https://github.com/Miaotofu01/Study-Mate/commit/88be504a3eb992daf1f1cffbc8851380256aed00))

  > 手动选择版本增量，经三平台检查后整理合并 PR 和全部提交，更新 CHANGELOG、版本标签和 GitHub Release，通过 npm OIDC 发布。

- test: 兼容 Windows 临时目录的短路径表示 ([0da4ca7](https://github.com/Miaotofu01/Study-Mate/commit/0da4ca7a8c5af38daef0d37571e0d7a1fb720b98))
- fix: 绕过 Node 22 在 Windows 复制中文目录时的崩溃 ([c4b2613](https://github.com/Miaotofu01/Study-Mate/commit/c4b2613116a5dc46c9796426749792f15501a42f))

[完整比较](https://github.com/Miaotofu01/Study-Mate/compare/v0.1...v0.1.2)
<!-- /studymate-release:v0.1.2 -->

## v0.1 — 首个可交付版本（2026-09-21）

- **学习模式预设 + 11 个技能**：1 个总控、5 个角色（找资料／采图／课程设计／讲解／出题评估）、5 份规范；配套大纲、进度、评估、会话摘要、科目五份数据结构。
- **三件套页面**：课程总览页、科目主页（大纲路线图）、课件页，共用一套主题（默认暗色，右上角可切）。课件由「内容文件 + 题库」渲染产出，四道校验（大纲／课件／图片库／技能）把关。
- **一条命令安装**：macOS/Linux 跑 `./install.sh`，Windows 跑 `.\install.ps1`——装预设、建学习工作区、写好配置。
- **13 套回归测试**：钉住渲染、题目、命名与上下节课指针、图片库、提示词规则与两个前端组件。
