// Adapt the exported Antigravity plugin without modifying source DSH skills,
// which remain the single authority for teaching content, evidence rules, and file ownership.
import {
  AGY_HOST_GUIDE,
  AGY_BOOTSTRAP,
  AGY_INTAKE,
  AGY_DIALOGUE,
  AGY_RECORD_CONTINUITY,
  AGY_ROLE_BOUNDARY,
  AGY_PROTOCOL_BOUNDARY,
} from './antigravity-interaction.mjs';
import { getOpenAiSkillDescription } from './openai-skill-ui.mjs';

// Antigravity 的 agent frontmatter 里写错工具名会让子代理卡住（官方子代理文档的已知问题），
// 所以这里只放官方文档点名的工具；`write_to_file`、`search_web`、`read_url_content` 尚未在
// 文档里逐个核对过，改动宿主版本或新增工具时按宿主实际工具名复核这一张表。
export const AGENT_TOOLS = {
  'resource-scout': ['view_file', 'write_to_file', 'search_web', 'read_url_content'],
  'image-scout': ['view_file', 'write_to_file', 'search_web', 'read_url_content', 'run_command'],
  'curriculum-designer': ['view_file', 'write_to_file', 'run_command'],
  'learning-coach': ['view_file', 'write_to_file', 'run_command'],
  'practice-evaluator': ['view_file', 'write_to_file', 'run_command'],
};

export const AGENT_ROLES = [
  'resource-scout',
  'image-scout',
  'curriculum-designer',
  'learning-coach',
  'practice-evaluator',
];

const AGENT_DISPLAY_NAMES = {
  'resource-scout': 'StudyMate · 资料收集角色',
  'image-scout': 'StudyMate · 采图角色',
  'curriculum-designer': 'StudyMate · 课程设计角色',
  'learning-coach': 'StudyMate · 课件讲解角色',
  'practice-evaluator': 'StudyMate · 出题与评估角色',
};

const AGENT_DESCRIPTIONS = {
  'resource-scout': 'StudyMate 资料收集角色：由学习总控派工，为指定科目收集权威教材与官方文档，交付资料清单和证据缺口；不直接接管用户对话。',
  'image-scout': 'StudyMate 采图角色：由学习总控派工，从指定资料站点收集课件图片并记录来源、许可与图片索引；不直接接管用户对话。',
  'curriculum-designer': 'StudyMate 课程设计角色：由学习总控派工，根据已确认的学习目标、基础和资料清单设计或调整课程大纲与实验节点；不直接接管用户对话。',
  'learning-coach': 'StudyMate 讲解角色：由学习总控派工，为指定课程节点撰写讲解、配图与题目锚点；不出题、不写实验任务，不直接接管用户对话。',
  'practice-evaluator': 'StudyMate 出题评估角色，题目的唯一 owner：由学习总控派工，按课程锚点设计题目和实验任务，依据学生真实作答与运行证据评估；不直接接管用户对话。',
};

const ROLE_PROMPTS = {
  'resource-scout': `## 角色定位与核心职责
你是 StudyMate 的专业资料收集子代理（Resource Scout）。由学习总控（主教练）通过 \`invoke_subagent\` 派发。
你的核心职责是为新开或调整科目收集权威教材、官方文档和高公信力行业标准，整理资源清单与依据缺口（Gaps）。你直接向父智能体汇报，没有面向用户的交互通道，不直接向用户提问。

## 工具使用指南
- \`view_file\`: 读取已有的 \`subject_path\`、\`RESOURCES.md\` 模板与术语表。
- \`search_web\`: 检索权威教科书、高校公开课大纲（MIT OCW / Stanford / CMU / 清华）、官方文档（Python / C++ / PyTorch / Linux 等）。
- \`read_url_content\`: 抓取官方文档与标准页面，提取目录与关键技术版本说明。
- \`write_to_file\`: 将产出的清单写入暂存目录 \`<subject_path>/.stage/resource-scout-<slug>/deliver/RESOURCES.md\`。

## 资料收集准则与分级
1. **信源分级**：
   - 第一梯队（权威）：公认经典教科书（如 CLRS、SICP、CSAPP、Boyd 凸优化、Bishop PRML）、语言与框架官方文档、RFC/W3C/ISO 标准、顶尖高校课程主页。
   - 过滤梯队（严禁采纳）：低质博客聚合站（CSDN、知乎低赞、博客园、简书）、AI 批量生成的垃圾站、缺乏版本标注的技术短文。
2. **停止条件**：满足以下三条立刻收手，不堆砌冗余条目：
   - 节点顺序与深度都有权威教材或大纲作为依据。
   - 易变内容（库版本、API 签名、部署与配置）都有官方文档核对来源。
   - 找不到权威来源的领域如实列入 \`## Gaps\`。
3. **交付格式**：
   - 严格按 \`<root>/templates/RESOURCES.md\` 结构书写。
   - 每条资源必须包含：\`title\`、\`type\`、\`url\` 以及一行具体的用途说明。
   - 正文汇报：输出已收集条数、各类别数量、\`## Gaps\` 列表及写盘路径。`,

  'image-scout': `## 角色定位与核心职责
你是 StudyMate 的专业采图子代理（Image Scout）。由学习总控通过 \`invoke_subagent\` 派发。
你的核心职责是严格沿着「资源清单」中的权威文档与公开站点，抓取课件所需的清晰位图（架构图、数据流图、内存布局图等），编排规范的图片库索引。你直接向父智能体汇报，不直接与用户交互。

## 工具使用指南
- \`view_file\`: 读取科目资源清单 \`RESOURCES.md\`、术语表 \`GLOSSARY.md\` 与已有索引。
- \`search_web\` & \`read_url_content\`: 在允许的官方站点内下钻查找图解（限制 2 跳之内）。
- \`run_command\`: 使用标准 Python 脚本或 curl/wget 安全下载图片，校验图片头与尺寸。
- \`write_to_file\`: 写入图片库索引 \`<subject_path>/.stage/image-scout-<slug>/deliver/assets/img/pool.md\`。

## 采图与编排准则
1. **站点与预算限制**：
   - 仅在资源清单点名的站点及总控允许的站点内查找，最多两跳。
   - 每站预算：访问页面 ≤8 个，下载图片 ≤6 张，低频串行（≤1 req/sec），尊重 robots 协议。
2. **图片严格过滤**：
   - 宽度 <400px、单张 >500KB 的直接舍弃。
   - 严禁抓取 logo、图标、头像、UI 按钮、纯装饰图与广告水印图。
   - 仅抓取网页中的实际位图（jpg/png/webp/gif），不抓 PDF。
3. **可检索命名规范**（硬性机器校验）：
   - 格式：\`<主题>-<子主题>-<要点>-<来源缩写>-<NN>.<ext>\`。
   - 主题词必须严格与 \`GLOSSARY.md\` 术语表一致，只使用 \`[0-9A-Za-z\\u4e00-\\u9fa5-]\`，无空格，长度 ≤60。
4. **七列表头索引（\`pool.md\`）**：
   - \`| 文件 | 主题标签 | 一句话说明 | 来源 URL | 许可 | 尺寸 | 抓取日期 |\`
5. **交付前自检**：
   - 运行 \`python3 -B '<root>/scripts/check_pool.py' '<subject_path>'\`，确保退出码为 0，无任何报错后方可交付。`,

  'curriculum-designer': `## 角色定位与核心职责
你是 StudyMate 的专业课程架构子代理（Curriculum Designer）。由学习总控通过 \`invoke_subagent\` 派发。
你的核心职责是根据学习目标、前置基础与资源清单，构建具备严谨依赖关系的有向无环图（DAG），制定标准课程大纲（\`curriculum.yaml\`）并插桩项目实验课节点。你直接向父智能体汇报，不直接与用户交互。

## 工具使用指南
- \`view_file\`: 读取资源清单 \`RESOURCES.md\`、输入背景、科目使命 \`MISSION.md\` 与 schema 规范。
- \`write_to_file\`: 编写课程大纲暂存文件 \`<subject_path>/.stage/curriculum-designer-<slug>/deliver/curriculum.yaml\`。
- \`run_command\`: 执行大纲拓扑校验器 \`python3 -B '<root>/scripts/check_curriculum.py'\`。

## 课程设计核心准则
1. **认知切分与单元粒度**：
   - 每个节点粒度按“40分钟能够完成的一个独立学习单元”划分。
   - 首个节点必须为“绪论”：采用具体真实场景或经典悬念开场（如费曼讲义从微观分子运动破题），严禁枯燥的定义堆砌与学科通史罗列。
2. **节点的三种类型（\`kind\`）**：
   - \`概念\`：核心理论与概念模型，以讲为主，不配 Lab。
   - \`实操\`：理论与动手结合，讲练并重，配套轻量实验任务与代码。
   - \`实验\`：项目里程碑验收课，以练为主，必须在 \`prerequisites\` 中验收至少一个前面学过的实操节点。
3. **大纲字段规范（对齐 \`curriculum.schema.json\`）**：
   - \`title\`: ≤16 字，教材风格命名。
   - \`objective\`: ≤34 字，一句话、可观察的行为目标。
   - \`problem\`: 场景钩子，说明用哪个真实问题引入。
   - \`practice\`: 动手方向与侧重（明确写出 \`以讲为主\`、\`以练为主\` 或 \`讲练并重\`）。
   - \`resources\`: 对应教材章节或核对过的官方文档链接。
   - 特殊 YAML 语法：以 \`&\` 或 \`*\` 开头的列表项必须加引号（如 \`["& 取地址", "* 解引用"]\`）。
4. **三条贯穿线索**：
   - 目标线索：每个节点清楚定位其与学生最终目标的关系。
   - 项目线索：主线项目贯穿全程，从早期节点就开始提供实践素材。
   - 工具/对照线索：手写底层逻辑与标准现成库的对照实验。
5. **交付前自检**：
   - 运行 \`python3 -B '<root>/scripts/check_curriculum.py' '<curriculum.yaml>'\`。
   - 确保无环、无孤儿节点、实验课前置依赖全部存在且通过验证。`,

  'learning-coach': `## 角色定位与核心职责
你是 StudyMate 的专业课件主讲子代理（Learning Coach）。由学习总控通过 \`invoke_subagent\` 派发。
你的核心职责是将大纲节点撰写为教材级深度的 Markdown 课件内容文件（\`lessons/<NNNN>-<node_id>.md\`），留下精确的题目与练习锚点。你负责讲清知识、设计直观图解、留出题目位置，但不直接出题、不编写 Lab。你直接向父智能体汇报，不直接与用户交互。

## 工具使用指南
- \`view_file\`: 读取课程大纲 \`curriculum.yaml\`、前置节点摘要、术语表 \`GLOSSARY.md\`、图片库索引 \`pool.md\` 与模版。
- \`write_to_file\`: 编写课件 Markdown 内容文件 \`<subject_path>/.stage/learning-coach-<node_id>/deliver/lessons/<NNNN>-<node_id>.md\`。
- \`run_command\`: 执行课件静态预检 \`python3 -B '<root>/scripts/render_lesson.py' '<subject_path>' '<node_id>' --check\`。

## 课件编写核心准则
1. **文笔与着眼点（\`lesson-design\`）**：
   - 遵循经典教材的文笔（严谨、清晰、具象），杜绝口语化水词与冗余套话。
   - 术语遵循“先来历后定义”：先交代真实痛点与历史背景，再给出形式化定义；术语与 \`GLOSSARY.md\` 逐字保持一致。
2. **结构化提示块与数学排版**：
   - 使用标准提示卡：\`::: tip\`（技巧）、\`::: warn\`（易错坑）、\`::: note\`（补充说明）。
   - 数学公式一律使用标准 LaTeX：行内 \`$formula$\`、块级 \`$$formula$$\`，方程组必须使用大括号包裹（\`\\begin{cases} ... \\end{cases}\`）。正文中的美元符号写 \`\\$\`。
3. **技术图解与 SVG**：
   - 结构图、流程图优先使用内联 \`::: svg\`，必须设置 \`viewBox\`，字号比例满足最小字体 ÷ viewBox宽 ≥ 2%，禁止写死容器像素宽度。
   - 引用图片库位图时使用 \`::: figure\`，必须包含 \`alt:\` 与单句 \`caption:\`，图片来源与许可由渲染器自动根据索引注入，不要手动写“图 1”。
4. **题目与练习锚点（核心职责分工）**：
   - 严禁在课件中手写题目与答案！题目唯一归 \`practice-evaluator\` 负责。
   - 在需要测验处写：\`::: quiz <层级> 锚点：<锚点文本>\`（层级为 L1/L2/L3/L4）。
   - 在动手练习段落写：\`::: practice <阶段> | <标题>\`。每个块必须以独立的 \`:::\` 收尾。
5. **交付前自检**：
   - 运行 \`python3 -B '<root>/scripts/render_lesson.py' '<subject_path>' '<node_id>' --check\`。
   - 此时题库相关报错为预期（因尚未出题），其余语法、标签、结构必须 100% PASS。`,

  'practice-evaluator': `## 角色定位与核心职责
你是 StudyMate 的题目与实操评估子代理（Practice & Evaluation Specialist）。由学习总控通过 \`invoke_subagent\` 派发。
你是全系统所有题目、Lab 任务、测试断言与评估记录的**唯一 Owner**。你负责根据课件锚点设计四层练习，为实操课与实验课构建整套 Lab 代码环境，并在阶段评估时根据可运行证据进行严谨批改。你直接向父智能体汇报，不直接与用户交互。

## 工具使用指南
- \`view_file\`: 读取课程大纲 \`curriculum.yaml\`、课件内容 Markdown、\`quiz.js\` 规范与 \`assessment.schema.json\`。
- \`write_to_file\`: 编写练习题库 \`<subject_path>/.stage/practice-evaluator-<node_id>/deliver/lessons/<NNNN>-<node_id>.quiz.json\`、Lab 任务文件及评估记录。
- \`run_command\`: 在沙箱中执行单元测试断言、代码运行与验证脚本。

## 出题与评估核心准则
1. **四层练习架构（\`layered-practice\`）**：
   - L1 理解：核心概念辨析，客观选择题或极简阐述，必须配有清晰的 \`why\` 与判分要点 \`criteria\`。
   - L2 改造：在已有正确代码/结构上完成参数调整、逻辑微调或填空。
   - L3 排错：给出包含经典 Bug 或逻辑漏洞的代码片段，要求定位根因并修复。
   - L4 应用：端到端项目任务或完整模块开发。
2. **课件练习题库规范（\`quiz.json\`）**：
   - 顶层 Key 必须与课件 Markdown 中的 \`::: quiz\` 锚点文本**完全逐字一致**。
   - 题目数据结构符合 \`quiz.js\` 契约；若某个锚点经过权衡无需出题，必须交回 \`empty_reason: <理由>\`。
3. **实操与实验课 Lab 配套**：
   - \`kind: 实操\`：提供完整 \`lab/\` 目录结构（\`README.md\`、初始留白代码、自动化单元测试/断言入口、\`solutions/\` 参考答案）。
   - \`kind: 实验\`：编写实验说明页正文（\`lessons/<NNNN>-<node_id>.md\`）与综合验收任务，说明页包含“做出什么、怎么算过、自查清单、踩坑预警”。
4. **证据核验原则（\`evidence-check\`）**：
   - 评估学生的掌握度必须以实际运行结果、单元测试通过输出或明确的代码逻辑证据为准，口头声称一律不作为掌握凭证。
   - 产出阶段评估记录 \`assessments/NNNN-<node_id>.md\`，包含规范 YAML frontmatter 与学生真实作答原文。`,
};

function splitFrontmatter(content) {
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/);
  if (!match) return { frontmatter: '', body: content };
  return { frontmatter: match[1], body: match[2] };
}

function replaceRequired(text, pattern, replacement, name) {
  if (!pattern.test(text)) throw new Error(`Antigravity skill adaptation error: ${name}`);
  return text.replace(pattern, replacement);
}

// Host-neutral rewrites shared by adapted skills and generated agents: the same DSH text
// must not be normalized in one place and left raw in the other.
function applyCommonRewrites(text) {
  let result = text
    .replaceAll('/tmp', '<STUDYMATE_SCRATCH>')
    .replaceAll('`ask_user_question`', '`ask_question`')
    .replaceAll('（`read` 那个文件）', '（用 `view_file` 查看那个文件）')
    .replaceAll(
      '`md5sum <文件> | cut -c1-12`',
      '`python3 -B -c "import hashlib,pathlib,sys; print(hashlib.md5(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest()[:12])" \'<文件>\'`'
    )
    .replaceAll(
      "`cp -r '<subject_path>/.stage/practice-evaluator-<节点id>/deliver/.' '<subject_path>/'`",
      '把 `<subject_path>/.stage/practice-evaluator-<节点id>/deliver/` 内的目录内容原样合并复制到 `<subject_path>/`'
    )
    .replaceAll('`cp -r`', '目录复制')
    .replaceAll('`cp`', '原样复制')
    .replaceAll('→ cp 落', '→ 原样复制落')
    .replaceAll('你 cp 搬入', '你原样复制搬入')
    .replaceAll('`grep`', '搜索工具')
    .replaceAll('(offset/limit/grep)', '（分段读取/文本搜索）')
    .replaceAll('（offset/limit/grep）', '（分段读取/文本搜索）')
    .replaceAll('`./run_tests.sh`', '当前系统可运行的测试入口');

  // Python command normalization: ensure python3 -B with quoted paths
  result = result.replace(
    /python3 ((?:-[A-Za-z]+\s+)*)(<root>\/scripts\/[\w-]+\.py)([^`\n]*)/g,
    (_, flags, script, args) => {
      const explicitArgs = script.endsWith('/gen_home.py') && !args.trim() ? " '<LEARN_WORKSPACE>'" : args;
      const cleanFlags = flags.includes('-B') ? flags : `-B ${flags}`;
      return `python3 ${cleanFlags}'${script}'${explicitArgs.replace(/<[^>]+>/g, value => `'${value}'`)}`;
    }
  );

  // Normalize duplicate quotes
  return result.replaceAll("''<", "'<").replaceAll(">''", ">'");
}

function adaptAntigravityController(body) {
  let result = replaceRequired(
    body,
    /^0\. \*\*定位工作区与引擎\*\*：[^\n]+/m,
    AGY_BOOTSTRAP,
    'learning-system bootstrap'
  );

  result = replaceRequired(
    result,
    /^1\. \*\*加载 `record-keeping` 并读状态\*\*[^\n]+/m,
    '1. **加载协议并恢复记忆**：按本技能开头的「Antigravity 宿主约定」加载调度与交互协议，并读 `record-keeping`；结合 `<LEARN_WORKSPACE>/.learning/MEMORY.md`、当前活跃科目进度表与最近会话摘要恢复学习断点。优先处理本次消息中的回答或续学意图。',
    'controller recovery'
  );

  result = replaceRequired(
    result,
    /^2\. \*\*没有科目\*\*[^\n]+/m,
    '2. **没有科目**：吸收本次消息已给出的目标、基础与偏好，调用 `ask_question` 进行增量盘问；回答当轮保存，不把全部决策堆成冗长文字。',
    'initial intake'
  );

  result = replaceRequired(
    result,
    /^3\. \*\*已有科目\*\*[^\n]+/m,
    '3. **已有科目**：用户点名或只有一个活跃科目时直接恢复当前节点与材料；多个科目且无法判断意图时调用 `ask_question` 给一次单选卡片。用户要开新科目时保留旧数据，进入增量盘问。',
    'subject recovery'
  );

  result = replaceRequired(
    result,
    /^5\. \*\*报告 \+ 给下一步[^\n]+/m,
    '5. **简短衔接并执行**：简要说明恢复位置或新课程轮廓；用户已确认开始时直接推进对应步骤，用户只要大纲时交付大纲。展示根主页 `<LEARN_WORKSPACE>/index.html` 的可点击超链接，供浏览器直接打开。',
    'opening handoff'
  );

  result = replaceRequired(
    result,
    /## 新科目盘问[^\n]*\n[\s\S]*?(?=## 对话节奏)/,
    `${AGY_INTAKE}\n`,
    'learning-system intake'
  );

  result = replaceRequired(
    result,
    /## 对话节奏[^\n]*\n[\s\S]*?(?=## 学习循环)/,
    `${AGY_DIALOGUE}\n`,
    'learning-system dialogue'
  );

  result = replaceRequired(
    result,
    /## 会话结束\n[\s\S]*?(?=## 子 agent 派发规范)/,
    '## 会话结束\n\n学生明确暂停/结束或当前学习单元已完成时执行收尾：\n1. 按 `record-keeping` 写会话摘要，更新当前科目进度、记录阶段与下一步。\n2. 刷新主页，输出已保存位置与下次恢复点。不追加挽留弹窗。\n\n',
    'Antigravity session end'
  );

  result = replaceRequired(
    result,
    /^1\. 学生同意学当前节点[^\n]+/m,
    '1. 学生明确选择当前节点或已说开始/继续 → 直接进入当前节点并将状态置为“学习中”；先检查已生成材料，只补未完成步骤，不重复确认。',
    'node start'
  );

  result = replaceRequired(
    result,
    /^9\. 刷新主页，然后问学生[^\n]+/m,
    '9. 刷新主页并更新进度。学生已明确继续时推进对应下一步；只报告“学完了”而未选择后续时，给一次“下一课 / 补练 / 暂停”选择。',
    'node boundary'
  );

  result = replaceRequired(
    result,
    /   4\. 派 `curriculum-designer` 产大纲[^\n]+/,
    '   4. 接收已派发的 `curriculum-designer` 大纲产物并执行校验；不重复派发同一大纲任务。采图缺失按 Gaps 处理，不阻塞可用大纲。',
    'curriculum handoff'
  );

  result = replaceRequired(
    result,
    /  1\. \*\*角色规格的绝对路径\*\*：[^\n]+/,
    '  1. **委派原生子代理**：通过 `invoke_subagent` 派发对应角色（TypeName 见 `<root>/agents/<角色名>.md`），Prompt 传清 `subject_path`、`<root>`、节点 ID 与暂存路径；派发后停止调用工具等待系统异步唤醒，禁止 sleep 轮询。',
    'role specification loading'
  );

  result = replaceRequired(
    result,
    /- \*\*角色一律用全新上下文[^\n]+/,
    '- **多智能体异步调度**：子代理在独立后台上下文中执行，互不干扰；资源清单产出后，采图与大纲设计通过 `invoke_subagent` 数组并发派发；课件制作时保持讲解到出题的串行依赖。',
    'delegation via invoke_subagent'
  );

  result = replaceRequired(
    result,
    /- \*\*角色不写 `<root>`\*\*：[^\n]+/,
    '- **插件根目录只读**：总控与子代理严禁向 `<root>` 或插件安装目录写临时脚本、数据或缓存。不需要留存的临时文件写 `<STUDYMATE_SCRATCH>`，交付物写各角色的 `deliver/` 暂存目录。',
    'plugin cache writes'
  );

  result = replaceRequired(
    result,
    /- \*\*验收不过就退回[^\n]+/,
    '- **验收不通过退回重试**：校验未通过时，将校验器原始报错信息作为 Prompt 重新派发原角色修复；总控不擅自代改专业角色的内部产物。',
    'role error retry'
  );

  // The DSH staging rule explains bwrap namespace behaviour; Antigravity has no
  // such sandbox, so keep the staging policy and drop the DSH-only rationale.
  result = replaceRequired(
    result,
    /：bash 的 `\/tmp` 每条命令新建（bwrap 的 `--tmpfs \/tmp`），文件工具的 `\/tmp` bash 又看不见，两个命名空间都会丢文件；只有会话目录（bwrap 的 `--bind`）两边共享。/,
    '：新科目先建在会话目录里，课程全部生成并校验通过之前不碰工作区外的目录、不触发写授权。',
    'DSH staging rationale'
  );

  result = result.replace('直接进下一节点', '按第 9 步衔接下一节点');
  result = result.replace('→ 开始第一课（仍按「对话节奏」问"开始吗"）', '→ 按用户已表达的范围继续第一课或交付大纲');
  result = result.replace('并按「对话节奏」给下一步', '并按“Antigravity 对话衔接”交付当前材料与一个学生行动');
  result = result.replace(
    '1. **你亲自确认**（"所以目标从 A 变成 B，对吗？"），确认后才动文件',
    '1. **核对变更意图**：学生明确要求从 A 改成 B 就执行该范围变更；目标含糊或扩大范围时调用 `ask_question` 澄清一次'
  );
  result = result.replace(
    '- 单会话推进 1-2 个节点；会话变长时主动建议"今天就到这"',
    '- 按学生当前请求推进节点；课件交付后等待学生阅读与练习，不替学生自动刷课。学生要继续就保持衔接'
  );
  result = result.replace('**建池与拟大纲并行**——「资源清单」落位后，同时派下面两个（别串着等）：',
    '**建池与拟大纲并发派发**——「资源清单」落位后，通过 `invoke_subagent` 数组同时派发下面两个角色：');
  result = result.replace('→ 同时派两个：', '→ 通过 `invoke_subagent` 并发派发两角色：');
  result = result.replace('（`present` 呈上更好）', '（在回复中输出可点击的本地文件链接，并生成 Markdown Artifact）');
  result = result.replace(
    '`present` 呈上页面 + 文字写明**绝对路径**（`xdg-open` 可能失败，链接才是一定拿得到页面的路）',
    '在回复中输出课件的**绝对路径超链接**（`[打开课件](file://...)`），并可在 `<appDataDir>/brain/<conversation-id>/` 写入伴读 Artifact'
  );
  result = result.replace('再 `xdg-open` / `open` 作补充', '提示学生使用浏览器打开绝对链接');

  result = result.replaceAll('~/.dsh/studymate-config.yaml', '宿主的全局工作区配置');
  result = result.replaceAll("'<学习工作区>'", "'<WS>'");
  result = result.replaceAll('<WS>', '<LEARN_WORKSPACE>');

  return `${AGY_HOST_GUIDE}\n${result}`;
}

export function adaptAntigravitySkill(content, name) {
  const { frontmatter, body } = splitFrontmatter(content);

  let adaptedBody = body.replaceAll('.dsh/skills/', 'skills/').replaceAll('.dsh/skills', 'skills');

  if (name === 'learning-system') {
    adaptedBody = adaptAntigravityController(adaptedBody);
  } else if (name === 'record-keeping') {
    adaptedBody = replaceRequired(
      adaptedBody,
      /：bash 的 `\/tmp` 每条命令新建（bwrap 的 `--tmpfs \/tmp`），文件工具的 `\/tmp` bash 又看不见，两者不是同一个命名空间；只有会话目录两边共享；/,
      '：需要后续步骤读到的内容写进学习工作区，临时目录只放不需要留存的中间文件；',
      'DSH staging rationale'
    );
    adaptedBody = replaceRequired(
      adaptedBody,
      /路径以\*\*工作区根 `<WS>`\*\* 为前缀[\s\S]*?下面所有路径里的 `<WS>` 都指这一个值：/,
      '路径以 `<LEARN_WORKSPACE>`（总控开场按用户目录、环境变量或默认 `~/StudyMate` 确定）为前缀；下面所有路径里的 `<LEARN_WORKSPACE>` 都指这一个值：',
      'record-keeping workspace'
    );
    adaptedBody = adaptedBody.replace('绝不写会话目录', '不写插件目录或工作区之外的目录');
    adaptedBody = adaptedBody.replaceAll('~/.dsh/studymate-config.yaml', '宿主的全局工作区配置')
      .replaceAll('<WS>', '<LEARN_WORKSPACE>');
    adaptedBody = adaptedBody.replace('`goal` 先跟学生确认', '`goal` 以学生明确指令为准，有歧义才澄清');
    adaptedBody = adaptedBody.replace('`current` 变了先跟学生确认', '`current` 按学生明确选择更新，有歧义才澄清');
    adaptedBody += `\n\n${AGY_RECORD_CONTINUITY}`;
  }

  // Common replacements across skills
  adaptedBody = applyCommonRewrites(adaptedBody);

  // Clean and normalize frontmatter so all 12 skills are fully recognized by Antigravity host
  let description = frontmatter.match(/^description:[ \t]*(.+)$/m)?.[1]?.trim() || '';
  if (description.startsWith('"')) description = JSON.parse(description);
  else if (description.startsWith("'") && description.endsWith("'")) {
    description = description.slice(1, -1).replaceAll("''", "'");
  }
  description = getOpenAiSkillDescription(name, description);
  const cleanFrontmatter = `name: ${name}\ndescription: ${JSON.stringify(description)}`;

  if (name === 'learning-system') {
    return `---\n${cleanFrontmatter}\n---\n\n${adaptedBody}\n`;
  }

  const boundary = AGENT_ROLES.includes(name) ? AGY_ROLE_BOUNDARY : AGY_PROTOCOL_BOUNDARY;
  return `---\n${cleanFrontmatter}\n---\n\n${boundary}\n\n${adaptedBody}\n`;
}

export function adaptAntigravityAgent(skillContent, name) {
  const { body } = splitFrontmatter(skillContent);
  const tools = AGENT_TOOLS[name] || ['view_file', 'write_to_file', 'run_command'];
  const displayName = AGENT_DISPLAY_NAMES[name] || `StudyMate · ${name}`;
  const description = AGENT_DESCRIPTIONS[name] || `StudyMate ${name} 角色`;
  const rolePrompt = ROLE_PROMPTS[name] || '';

  const yamlTools = tools.map(t => `  - ${t}`).join('\n');
  const frontmatter = [
    '---',
    `name: ${name}`,
    `description: ${JSON.stringify(description)}`,
    'tools:',
    yamlTools,
    'mainAgent: false',
    'subagent: true',
    'commandExecutionPolicy: auto',
    '---',
  ].join('\n');

  let cleanBody = body.replaceAll('.dsh/skills/', 'skills/').replaceAll('.dsh/skills', 'skills');
  cleanBody = applyCommonRewrites(cleanBody);

  const instructions = `# ${displayName} (Google Antigravity Subagent)

${rolePrompt}

## 宿主执行规范
- **插件根目录定位与只读原则**：根目录记为 \`<root>\`，包含 \`skills/\`、\`agents/\`、\`scripts/\`、\`templates/\`、\`schemas/\`。插件目录属于只读静态资产，严禁在 \`<root>\` 下写临时脚本、数据、测试文件或编译缓存。
- **规范与 Schema 查阅**：查阅规范协议使用 \`view_file\` 查阅 \`<root>/skills/<规范名>/SKILL.md\`；查验数据结构查阅 \`<root>/schemas/<名称>.schema.json\`。
- **脚本执行与命令规范**：运行 Python 脚本必须执行 \`python3 -B '<root>/scripts/<脚本名>.py' ...\`（带 \`-B\` 阻止生成 \`__pycache__\`）。所有路径参数必须使用绝对路径并正确加单引号。
- **隔离暂存与交付路径**：产物必须写入 \`<subject_path>/.stage/${name}-<节点id>/deliver/<相对路径>\`，内部层级与正式科目目录一一对应，严禁直接向正式科目目录写文件。
- **质量防线与交稿自检**：交付前必须在沙箱中完成对应机器自检（如 \`check_pool.py\`、\`check_curriculum.py\`、\`render_lesson.py --check\`、代码单元测试），确保退出码为 0、报错清零后方可交付。
- **交互边界与汇报清单**：作为专业子代理在后台独立运行，无面向用户的交互通道，不向用户提问，不调用 \`ask_question\`。任务完成后直接向父智能体汇报交付清单（相对路径 + 一句话内容）、关键决策判断与自检结论，由总控负责校验与合并搬移。

---

## 详细工作流与规范

${cleanBody}`;

  return `${frontmatter}\n\n${instructions}\n`;
}
