// Adapt the exported plugin without changing the DSH skills, which remain the
// authority for teaching content and file ownership.
import { INTAKE, DIALOGUE, RECORD_CONTINUITY, ROLE_BOUNDARY, PROTOCOL_BOUNDARY } from './openai-interaction.mjs';
import { getOpenAiSkillDescription } from './openai-skill-ui.mjs';

const HOST_GUIDE = `## OpenAI 宿主约定（导出时生成）

- **引擎定位**：本文件位于 \`<root>/skills/<技能名>/SKILL.md\`；从实际文件路径定位包含 \`skills/\`、\`scripts/\`、\`templates/\`、\`schemas/\`、\`docs/\` 的插件根目录，记为 \`<root>\`。引擎与插件缓存只读，学习数据写入另一个可写工作区。所有相对的脚本、模板、schema、文档路径均相对 \`<root>\`；参考文档中的旧宿主安装说明不参与本插件启动。
- **加载协议**：正文说“加载某技能”时，用宿主文件读取工具读 \`<root>/skills/<技能名>/SKILL.md\`；不需要专门的技能调用工具。缺少文件读取能力时说明具体缺项，不声称已加载。所有角色的教学职责与文件归属保持不变。
- **工作区**：总控传入的 \`<LEARN_WORKSPACE>\` 与 \`subject_path\` 必须是实际绝对路径；新会话按总控的“会话开场”恢复。不要把插件目录、缓存或未知的当前目录当作学习数据目录。角色不另选工作区。
- **工具能力**：只使用宿主实际提供的提问、浏览、文件读写、图片查看、命令执行、委派与预览工具。提问工具不可用时总控用普通对话提问；角色把待问事项交给总控。检索不可用时记录未核验来源与 Gaps，不编造核验结果；图片不可取得时允许空图片库。文件或执行工具不可用时可以继续讨论，但具体生成、持久化与校验必须如实标为未完成。
- **角色执行**：本项的调度动作只由总控执行。有委派工具时按总控规范分工；没有委派工具时由总控按角色规格串行执行，每段读取对应规格，以“准备讲解/核对练习”等工作内容报告进度，完成产物与检查后才切回总控。不得假称启动了子 agent；串行执行仍保留正文→出题→原样搬运→渲染的顺序、题目唯一 owner 与档案归属，不能用总控身份随手改角色产物。角色阶段不再委派。
- **暂存位置**：总控在宿主允许的可写临时目录，或工作区内专用暂存目录，分配每会话唯一的 \`<STUDYMATE_SCRATCH>\`，再按角色与节点分目录并传绝对路径。不同会话、不同角色不共享固定草稿目录；不要假定任何操作系统的临时目录路径。
- **Python 与命令**：先探测 Python 3.9+、PyYAML（\`yaml\`）与 JSON Schema 校验器（\`jsonschema\`）可用；\`<python>\` 表示已验证的解释器调用，可为 \`python3\`、\`python\`、\`py -3\` 或绝对路径；后续调用加 \`-X utf8\`。PowerShell 调用带引号的可执行文件路径要加 \`&\`；路径参数使用宿主 shell 的字面值引用与转义（PowerShell 单引号内的单引号写两次）。优先使用工具的参数数组，不能把路径或学生文本拼成未引用的命令。按当前操作系统选择可用的 lab 测试命令。依赖缺失由总控在获准的可写环境内处理，角色不建环境，插件缓存内不装依赖。
- **逐次显式传参**：调用主页生成器始终传 \`'<LEARN_WORKSPACE>'\`；各命令都传脚本与数据的绝对路径。环境变量、工作目录与 shell 状态不保证跨工具调用保留，确需设置时在每次调用内设置。跨会话只信实际存在的文件，不能以聊天记忆替代磁盘恢复。
- **原样搬运**：用宿主文件复制工具，或 Python 标准库 \`shutil.copy2\`（文件）、\`shutil.copytree(..., dirs_exist_ok=True)\`（目录合并）完成；保留 \`deliver/\` 中相对路径，不经模型重写题面、答案与长产物。Windows 可用 PowerShell 的 \`Copy-Item -LiteralPath\`；不要依赖别的平台的复制、摘要或打开页面命令。
- **展示与持续保存**：页面写盘并校验后用宿主可用的文件预览/浏览器展示，同时给可点击的绝对文件链接；沙箱文件使用宿主支持的下载/附件链接。无预览能力时仍交付文件链接与位置。ChatGPT Work 或其他临时沙箱中，先核实文件是否能跨会话保留；不确定就明确说明，并在结束时交付包含 \`index.html\` 与完整 \`.learning/\`（含隐藏目录）的可下载归档，下一次从用户提供的归档恢复，不承诺本机目录或沙箱会永久保留。
`;

const BOOTSTRAP = `0. **定位工作区与引擎**：按“OpenAI 宿主约定”从本技能文件定位 \`<root>\`。学习工作区按以下顺序选定并记为 \`<LEARN_WORKSPACE>\`：用户本次明确指定的目录 → 非空环境变量 \`STUDYMATE_WORKSPACE\` → 非空 \`LEARN_WORKSPACE\` → 用户显式设置的 \`STUDYMATE_CONFIG\` 配置中的 \`workspace\` → 当前任务/项目中已有的学习工作区（含 \`.learning/\`，或用户提供的已恢复学习档案）。配置的 \`root\` 不覆盖本插件根目录；配置不存在或无效时报告具体问题，不悄悄改用别处的数据。只有用户明确要求复用旧 DSH 工作区时才读取其指定的旧配置；没有 DSH 配置不影响启动。
   - **首次初始化**：已有明确的工作区路径时直接在该目录初始化；尚未选定时，在当前宿主已授权的可写项目/数据目录中建 \`StudyMate/\` 并设为工作区（已有同名目录先检查并复用，避免覆盖）。路径不得位于插件根目录或插件缓存。若宿主没有给出可写位置，只询问保存位置，其他学习目标盘问可以继续。在选定的工作区创建 \`.learning/subjects/\`，仅在缺失时从 \`<root>/templates/MEMORY.md\` 复制为 \`.learning/MEMORY.md\`；保留已有科目与记忆。向学生说明实际保存位置。
   - **执行准备**：探测上述 Python 与依赖，分配本会话的 \`<STUDYMATE_SCRATCH>\`；调用生成器与校验器必须使用实际绝对路径。检查当前宿主的持久化能力；临时沙箱遵守“展示与持续保存”。不要求安装其他聊天宿主或运行旧安装脚本。`;

function replaceRequired(text, pattern, replacement, name) {
  if (!pattern.test(text)) throw new Error(`OpenAI skill adaptation needs updating: ${name}`);
  return text.replace(pattern, replacement);
}

function adaptController(body) {
  let result = replaceRequired(body, /^0\. \*\*定位工作区与引擎\*\*：[^\n]+/m,
    BOOTSTRAP, 'learning-system bootstrap');
  result = replaceRequired(result, /^1\. \*\*加载 `record-keeping` 并读状态\*\*[^\n]+/m,
    '1. **加载交互与档案协议并恢复**：先读本技能 `references/codex-interaction.md` 与 `record-keeping`；用 `<root>/scripts/interaction_state.py` 读取断点（首次无文件正常），结合最近会话摘要、共享记忆与学习进度恢复。先处理本次消息中的回答、纠正或续学意图，不能一律重跑开场菜单。', 'controller recovery');
  result = replaceRequired(result, /^2\. \*\*没有科目\*\*[^\n]+/m,
    '2. **没有科目**：吸收本次消息已给出的目标、基础与偏好，仅走下方增量盘问；回答当轮保存，不等建完科目才记。不先问一遍三件事再重复盘问。', 'initial intake');
  result = replaceRequired(result, /^3\. \*\*已有科目\*\*[^\n]+/m,
    '3. **已有科目**：用户点名或只有一个有效活跃科目时直接恢复到当前阶段、节点和已存在的材料；多个科目且无法判断意图才给一次选择。用户明确要新科目时保留旧数据，进入增量盘问。', 'subject recovery');
  result = replaceRequired(result, /^5\. \*\*报告 \+ 给下一步[^\n]+/m,
    '5. **简短衔接并执行**：用一两句说明恢复位置或新课程轮廓；用户已要求开始/继续时直接执行对应步骤，只要大纲时交付大纲。只有尚未决定的下一步才给一次选择，不重复问“开始吗”。展示根主页 `<LEARN_WORKSPACE>/index.html` 的可点击绝对路径，有文件预览工具时打开。', 'opening handoff');
  result = replaceRequired(result, /## 新科目盘问[^\n]*\n[\s\S]*?(?=## 对话节奏)/,
    `${INTAKE}\n`, 'Codex intake');
  result = replaceRequired(result, /## 对话节奏[^\n]*\n[\s\S]*?(?=## 学习循环)/,
    `${DIALOGUE}\n`, 'Codex dialogue');
  result = replaceRequired(result, /## 会话结束\n[\s\S]*?(?=## 子 agent 派发规范)/,
    '## 会话结束\n\n学生明确暂停/结束或当前请求已完成时才执行下面的收尾。等待异步回复时即使宿主必须交还控制，也只按交互协议保留 pending 并让出执行，不运行学习结束流程、不输出完成总结。\n\n1. 按 `record-keeping` 写会话摘要，保存当前科目、节点、阶段与下一步；显式结束时交互状态设为 paused 并清除待问项。\n2. 刷新主页，简短说明本次完成内容与续学位置。已有明确授权的偏好正常记录；需要学生确认的新长期观察先保留在摘要，下次相关时再确认，不为此追加弹窗。\n\n', 'Codex session end');
  result = replaceRequired(result, /^1\. 学生同意学当前节点[^\n]+/m,
    '1. 学生明确选择当前节点或已说开始/继续 → 直接进入当前节点并将状态置为“学习中”；先检查已生成材料与断点，只补未完成步骤，不重复确认或重新生成。', 'node start');
  result = replaceRequired(result, /^9\. 刷新主页，然后问学生[^\n]+/m,
    '9. 刷新主页并保存交互断点。学生已明确继续时推进对应下一步；只报告“学完了”而未选择后续时，给一次“下一课 / 补练 / 暂停”选择，不再叠加开始确认。', 'node boundary');
  result = result.replace('直接进下一节点', '按第 9 步衔接下一节点');
  result = result.replace('→ 开始第一课（仍按「对话节奏」问"开始吗"）', '→ 按用户已表达的范围继续第一课或交付大纲');
  result = replaceRequired(result, /   4\. 派 `curriculum-designer` 产大纲[^\n]+/,
    '   4. 接收第 3 步已经派发的 `curriculum-designer` 大纲并校验；不再次派同一份大纲任务。采图缺失按 Gaps 处理，不让可选图片阻塞已可交付的课程', 'single curriculum handoff');
  result = result.replace('并按「对话节奏」给下一步', '并按“Codex 对话衔接”交付当前材料与一个学生行动');
  result = result.replace('1. **你亲自确认**（"所以目标从 A 变成 B，对吗？"），确认后才动文件',
    '1. **核对变更意图**：学生明确要求从 A 改成 B 就执行该范围的变更；只有目标含糊或会扩大范围时才澄清一次，不重复确认已经清楚的指令');
  result = result.replace('- 单会话推进 1-2 个节点；会话变长时主动建议"今天就到这"',
    '- 按学生当前请求推进节点；课件交付后等阅读与证据，不替学生自动刷完整门课。学生要继续就保持衔接，不以回合数强制结束');
  result = replaceRequired(result,
    /  1\. \*\*角色规格的绝对路径\*\*：[^\n]+/,
    '  1. **角色规格的绝对路径**：`<root>/skills/<角色>/SKILL.md`，明说“先用文件读取工具读它、照它执行”；只有下游没有文件工具时才退回内联全文',
    'role specification loading');
  result = replaceRequired(result,
    /- \*\*角色一律用全新上下文[^\n]+/,
    '- **按宿主能力委派**：有委派工具时优先使用全新上下文，并传完整角色路径、值与边界；若宿主只能继承上下文，明确当前角色与任务边界，不让它沿用总控身份。没有委派工具时按“OpenAI 宿主约定”串行切换角色；原本可并行的采图与课设改为串行，其余依赖顺序不变。不要假定宿主预设会自动限制委派深度，角色不再委派的边界由总控明确传达。',
    'delegation fallback');
  result = replaceRequired(result,
    /- \*\*角色不写 `<root>`\*\*：[^\n]+/,
    '- **插件根目录只读**：总控与角色均不在 `<root>` 或插件缓存写临时脚本、数据或环境。派发时明确“临时脚本与中间产物写 `<STUDYMATE_SCRATCH>`；学习产物按角色归属写 `subject_path` 或暂存目录”。发现异常文件先报告，不自动删除或收编插件目录中的文件。',
    'plugin cache writes');
  result = result.replace('**建池与拟大纲并行**——「资源清单」落位后，同时派下面两个（别串着等）：',
    '**建池与拟大纲可并行**——「资源清单」落位后，有委派工具时同时派下面两个；没有时按角色规格串行完成：');
  result = result.replace('→ 同时派两个：', '→ 有委派工具时并行、否则串行执行两角色：');
  result = result.replace(/- \*\*验收不过就退回[^\n]+/,
    '- **验收不过由产出角色自己改**：有角色消息/继续执行工具时，向原角色发送失败原文证据；串行模式切回同一角色规范修正。不要用总控身份代改；无法继续原子 agent 时，重新执行该角色并给原产物路径与失败证据。');
  result = result.replace('（`present` 呈上更好）', '（使用宿主可用的文件预览或附件展示）');
  result = result.replace('`present` 呈上页面 + 文字写明**绝对路径**（`xdg-open` 可能失败，链接才是一定拿得到页面的路）',
    '使用宿主文件预览或附件呈上页面 + 文字写明**实际保存位置**并给可点击的文件链接');
  result = result.replace('再 `xdg-open` / `open` 作补充', '有可用浏览器/页面预览工具时打开页面作补充');
  return result;
}

/** Build a host-independent exported copy of one bundled DSH skill. */
export function adaptOpenAiSkill(content, name) {
  if (typeof content !== 'string' || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name)) {
    throw new TypeError('Expected skill content and a lowercase skill directory name');
  }
  const source = content.replaceAll('\r\n', '\n');
  const frontmatter = source.match(/^---\n([\s\S]*?)\n---(?:\n|$)/);
  if (!frontmatter) throw new Error(`Missing skill frontmatter: ${name}`);
  const sourceName = frontmatter[1].match(/^name:\s*(\S+)\s*$/m)?.[1];
  let description = frontmatter[1].match(/^description:[ \t]*(.+)$/m)?.[1]?.trim();
  if (sourceName !== name || !description) throw new Error(`Invalid skill metadata: ${name}`);
  if (description.startsWith('"')) description = JSON.parse(description);
  else if (description.startsWith("'") && description.endsWith("'")) {
    description = description.slice(1, -1).replaceAll("''", "'");
  }
  description = getOpenAiSkillDescription(name, description);

  let body = source.slice(frontmatter[0].length).trim();
  if (name === 'learning-system') body = adaptController(body);
  if (name === 'record-keeping') {
    body = replaceRequired(body,
      /路径以\*\*工作区根 `<WS>`\*\* 为前缀[\s\S]*?下面所有路径里的 `<WS>` 都指这一个值：/,
      '路径以 `<LEARN_WORKSPACE>`（总控开场按用户目录、环境变量、显式配置或既有学习数据确定）为前缀；下面所有路径里的 `<LEARN_WORKSPACE>` 都指这一个值：',
      'record-keeping workspace');
    body = body.replace('绝不写会话目录', '不写插件缓存或工作区之外的会话目录');
    // 本插件不读 DSH 的 studymate-config.yaml，工作区根一律记作 `<LEARN_WORKSPACE>`
    body = body.replaceAll('~/.dsh/studymate-config.yaml', '宿主的全局工作区配置')
      .replaceAll('<WS>', '<LEARN_WORKSPACE>');
    body = body.replace('`goal` 先跟学生确认', '`goal` 以学生明确指令为准，有歧义才澄清');
    body = body.replace('`current` 变了先跟学生确认', '`current` 按学生明确选择更新，有歧义才澄清');
    body = body.replace('同时在对话里给一条 `memory_updates` 建议，学生确认后写进「共享记忆」',
      '需要确认的 `memory_updates` 先保留在摘要，不在学生结束时追加弹窗；仅在获得实际确认后写入共享记忆');
    body += `\n\n${RECORD_CONTINUITY}`;
  }
  if (name === 'learning-system') {
    body = body.replace('`goal` 先跟学生确认', '`goal` 以学生明确指令为准，有歧义才澄清');
    body = body.replace('必须学生确认；旧使命留痕', '按学生明确变更指令执行，歧义才澄清；旧使命留痕');
    // 暂存模式：本插件不读 DSH 的 studymate-config.yaml，工作区根一律记作 `<LEARN_WORKSPACE>`。
    // 中文占位符 `<学习工作区>` 先换成 `<WS>`，否则下面 python 命令的占位符替换会把它
    // 拆成「去尖括号 + 保留原引号」的 `''<学习工作区>''`。
    body = body.replaceAll('~/.dsh/studymate-config.yaml', '宿主的全局工作区配置');
    body = body.replaceAll("'<学习工作区>'", "'<WS>'");
    body = body.replaceAll('<WS>', '<LEARN_WORKSPACE>');
  }
  body = body.replaceAll('.dsh/skills/', 'skills/')
    .replaceAll('/tmp', '<STUDYMATE_SCRATCH>')
    .replaceAll('`ask_user_question`', '宿主提问工具')
    .replaceAll('（`read` 那个文件）', '（用宿主图片查看工具打开那个文件）')
    .replaceAll('`md5sum <文件> | cut -c1-12`',
      '`<python> -X utf8 -c \'import hashlib,pathlib,sys; print(hashlib.md5(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest()[:12])\' \'<文件>\'`')
    .replaceAll("`cp -r '<subject_path>/.stage/practice-evaluator-<节点id>/deliver/.' '<subject_path>/'`",
      '把 `<subject_path>/.stage/practice-evaluator-<节点id>/deliver/` 内的目录内容原样合并复制到 `<subject_path>/`')
    .replaceAll('`cp -r`', '目录复制')
    .replaceAll('`cp`', '原样复制')
    .replaceAll('→ cp 落', '→ 原样复制落')
    .replaceAll('你 cp 搬入', '你原样复制搬入')
    .replaceAll('`grep`', '宿主文本搜索工具')
    .replaceAll('(offset/limit/grep)', '（分段读取/文本搜索）')
    .replaceAll('（offset/limit/grep）', '（分段读取/文本搜索）')
    .replaceAll('`./run_tests.sh`', '当前系统可运行的测试入口');
  // `python3` 与脚本路径之间允许 `-B` 这类标志：源技能要求跑引擎脚本一律加 `-B`
  // （否则 Python 往只读的引擎目录写 `__pycache__`），标志要原样带到本机调用里。
  body = body.replace(/python3 ((?:-[A-Za-z]+\s+)*)(<root>\/scripts\/[\w-]+\.py)([^`\n]*)/g,
    (_, flags, script, args) => {
      const argumentsText = script.endsWith('/gen_home.py') && !args.trim()
        ? ' <LEARN_WORKSPACE>' : args;
      return `<python> -X utf8 ${flags}'${script}'${argumentsText.replace(/<[^>]+>/g, value => `'${value}'`)}`;
    });

  // 归一：上面按 `<[^>]+>` 逐个补引号，遇到源文件里已经带引号的占位符会补成 `''<X>''`。
  // 这类重复引号只是写法问题，统一收敛回一层（`python3 -X utf8 -B '<脚本>' '<占位符>'`）。
  body = body.replaceAll("''<", "'<").replaceAll(">''", ">'");

  // DSH-only frontmatter flags are moved to agents/openai.yaml by the builder;
  // role instructions enforce the same ownership when UI policy is unavailable.
  const roleOnly = /^disable-model-invocation:\s*true\s*$/m.test(frontmatter[1]);
  const boundary = name === 'learning-system' ? '' : `${roleOnly ? ROLE_BOUNDARY : PROTOCOL_BOUNDARY}\n`;
  return `---\nname: ${name}\ndescription: ${JSON.stringify(description)}\n---\n\n${HOST_GUIDE}\n${boundary}${body}\n`;
}
