// Discovery text and Codex UI policy for exported copies only. Keep the learning
// entry point discoverable without making internal teaching roles claim ordinary
// user requests. JSON-quoted strings are valid YAML double-quoted scalars.
// These five source DSH roles have disable-model-invocation: true. The controller
// and shared protocols retain their existing implicit invocation behavior.
const explicitOnly = new Set([
  'curriculum-designer', 'resource-scout', 'image-scout', 'learning-coach', 'practice-evaluator',
]);

const skills = new Map([
  ['learning-system', {
    description: 'StudyMate 学习入口：用户想学新科目、继续或切换已有科目、恢复练习与学习进度时使用，组织课程、课件和评估。普通编程、修复代码或开发项目请求不自动进入学习流程。',
    display_name: 'StudyMate · 学习总控',
    short_description: '开始新科目、继续或切换学习，恢复课程进度与练习并安排下一步',
    default_prompt: '请用 $learning-system 根据我的目标和已有进度，安排这次的学习与练习。',
  }],
  ['curriculum-designer', {
    description: 'StudyMate 课程设计角色：由学习总控派工，根据已确认的学习目标、基础和资料清单设计或调整课程大纲与实验节点；不直接接管用户对话。',
    display_name: 'StudyMate · 课程设计',
    short_description: '接受学习总控派工，依据学习目标与资料设计课程依赖和实验节点',
    default_prompt: '请用 $curriculum-designer 按学习总控提供的目标、基础和资料清单设计课程大纲。',
  }],
  ['resource-scout', {
    description: 'StudyMate 资料收集角色：由学习总控派工，为指定科目收集权威教材与官方文档，交付资料清单和证据缺口；不直接接管用户对话。',
    display_name: 'StudyMate · 资料收集',
    short_description: '接受学习总控派工，为指定科目整理权威教材、官方文档与资料缺口',
    default_prompt: '请用 $resource-scout 按学习总控给定的科目目标收集权威资料并记录缺口。',
  }],
  ['image-scout', {
    description: 'StudyMate 采图角色：由学习总控派工，从指定资料站点收集课件图片并记录来源、许可与图片索引；不直接接管用户对话。',
    display_name: 'StudyMate · 课件采图',
    short_description: '接受学习总控派工，从指定资料站点收集课件图片并维护来源索引',
    default_prompt: '请用 $image-scout 从学习总控指定的资料站点收集适用图片并更新索引。',
  }],
  ['learning-coach', {
    description: 'StudyMate 讲解角色：由学习总控派工，为指定课程节点撰写讲解、配图与题目锚点；不出题、不写实验任务，不直接接管用户对话。',
    display_name: 'StudyMate · 课件讲解',
    short_description: '接受学习总控派工，为当前课程节点撰写讲解、安排配图并保留题位',
    default_prompt: '请用 $learning-coach 按学习总控指定的课程节点撰写课件讲解并保留题目锚点。',
  }],
  ['practice-evaluator', {
    description: 'StudyMate 出题评估角色，题目的唯一 owner：由学习总控派工，按课程锚点设计题目和实验任务，依据学生真实作答与运行证据评估；不直接接管用户对话。',
    display_name: 'StudyMate · 出题评估',
    short_description: '接受学习总控派工，设计练习与实验任务并依据真实作答和运行证据评估',
    default_prompt: '请用 $practice-evaluator 按学习总控指定的节点和任务阶段完成出题或证据评估。',
  }],
  ['learning-discovery', {
    description: 'StudyMate 方向探索内部规范：学生不知道学什么或主动要求帮选方向时，由学习总控亲自执行探索访谈、给候选方向并在确认后交接原建课流程。明确科目与恢复学习不进入探索。',
    display_name: 'StudyMate · 方向探索',
    short_description: '供学习总控在学生没有明确方向时访谈、给候选并交接建课',
    default_prompt: '请用 $learning-discovery 的内部协议帮我从几个候选学习方向里选一个。',
  }],
  ['record-keeping', {
    description: 'StudyMate 档案维护内部规范：由学习总控读取并执行，规定共享记忆、学习进度、评估记录与会话恢复的文件归属和更新规则。',
    display_name: 'StudyMate · 学习档案',
    short_description: '供学习总控维护共享记忆、科目进度、评估记录与会话恢复状态',
    default_prompt: '请用 $record-keeping 的内部规范核对并更新当前学习工作区的档案。',
  }],
  ['lesson-design', {
    description: 'StudyMate 课件设计内部规范：供学习总控和讲解角色读取，规定课件结构、内容块、行文与配图要求；不承担用户的独立设计任务。',
    display_name: 'StudyMate · 课件规范',
    short_description: '供学习总控和讲解角色使用，统一课件结构、内容块与教材式行文',
    default_prompt: '请用 $lesson-design 的内部规范检查当前 StudyMate 课件的内容设计。',
  }],
  ['layered-practice', {
    description: 'StudyMate 练习设计内部规范：供学习总控和出题评估角色读取，规定练习层级、题型、实验任务与判分要点；由出题评估角色执行出题。',
    display_name: 'StudyMate · 练习规范',
    short_description: '供学习总控和出题角色使用，约定练习层级、题型、实验任务与判分要点',
    default_prompt: '请用 $layered-practice 的内部规范核对当前课程练习的层级、题型和判分要求。',
  }],
  ['evidence-check', {
    description: 'StudyMate 学习证据内部规范：供学习总控和出题评估角色读取，对照课程目标与判分要点核验学生真实产物；不把口头确认视为通过证据。',
    display_name: 'StudyMate · 学习证据',
    short_description: '供学习总控和评估角色使用，对照课程目标核验作答、运行结果与真实产物',
    default_prompt: '请用 $evidence-check 的内部规范核验当前学习任务的真实作答和运行证据。',
  }],
  ['local-qa', {
    description: 'StudyMate 局部答疑内部规范：由学习总控读取并执行，处理学习过程中学生贴回的局部疑问并记录误解；不接管普通编程问答。',
    display_name: 'StudyMate · 学习答疑',
    short_description: '供学习总控处理课程中的局部疑问，记录误解并引导学生回到学习位置',
    default_prompt: '请用 $local-qa 的内部规范解答我在当前 StudyMate 课程中的局部疑问。',
  }],
]);

/** Unknown skills keep their original discovery description. */
export function getOpenAiSkillDescription(name, original) {
  return skills.get(name)?.description ?? original;
}

/** Unknown skills fail explicitly so a new role cannot silently become implicit. */
export function getOpenAiSkillUi(name) {
  const metadata = skills.get(name);
  if (!metadata) throw new Error(`Unknown StudyMate skill UI metadata: ${name}`);
  const lines = ['interface:'];
  for (const key of ['display_name', 'short_description', 'default_prompt']) {
    lines.push(`  ${key}: ${JSON.stringify(metadata[key])}`);
  }
  lines.push('', 'policy:', `  allow_implicit_invocation: ${!explicitOnly.has(name)}`);
  return `${lines.join('\n')}\n`;
}
