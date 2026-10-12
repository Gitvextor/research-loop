const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const ASSET = path.join(__dirname, '..', '..', 'templates', 'assets', 'quiz.js');

function makeEl(tag) {
  const el = {
    tagName: tag, className: '', hidden: false, type: '', _data: null, _attrs: {}, _text: '',
    children: [], _handlers: {},
    classList: {
      _set: new Set(),
      toggle(name, force) {
        const on = force === undefined ? !this._set.has(name) : !!force;
        if (on) this._set.add(name); else this._set.delete(name);
      },
      contains(n) { return this._set.has(n); },
      add(n) { this._set.add(n); },
      remove(n) { this._set.delete(n); },
    },
    appendChild(c) { this.children.push(c); return c; },
    addEventListener(t, fn) { (this._handlers[t] = this._handlers[t] || []).push(fn); },
    click() { (this._handlers.click || []).forEach(fn => fn()); },
    getAttribute(n) { return n === 'data-quiz' ? this._data : (n in this._attrs ? this._attrs[n] : null); },
    setAttribute(n, v) { this._attrs[n] = String(v); },
  };
  // 真实 DOM 的 textContent：设值清空子节点，读值把整棵子树的文本拼起来。
  // quiz.js 现在用 createTextNode + <pre><code> 渲染围栏代码块，两条语义都要有，
  // 否则断言读到的是空串。
  Object.defineProperty(el, 'textContent', {
    get() { return this._text + this.children.map(c => c.textContent || '').join(''); },
    set(v) { this._text = String(v == null ? '' : v); this.children.length = 0; },
  });
  return el;
}

function makeText(text) {
  const node = makeEl('#text');
  node.nodeType = 3;
  node.textContent = text;
  return node;
}

function makeBlock(items) {
  const b = makeEl('div');
  b._data = JSON.stringify(items);
  return b;
}

function run(blocks, windowExtras = {}) {
  const sandbox = {
    console,
    window: { ...windowExtras },
    document: {
      readyState: 'complete',
      addEventListener() {},
      querySelectorAll() { return blocks; },
      createElement: makeEl,
      createTextNode: makeText,
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(ASSET, 'utf8'), sandbox);
}

// 在渲染树里找类名匹配的元素（深度优先，返回全部）
function findAll(root, cls, out = []) {
  if ((root.className || '').split(/\s+/).includes(cls)) out.push(root);
  (root.children || []).forEach(c => findAll(c, cls, out));
  return out;
}

let failures = 0;
function check(label, ok, extra = '') {
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}${extra ? '  — ' + extra : ''}`);
  if (!ok) failures++;
}

// ── 场景一：1 选择 + 1 开放 ─────────────────────────────────────
const b1 = makeBlock([
  { q: '哪层要真跑代码？', opts: ['L1 理解', 'L4 应用', 'L2 改造'], ans: 1, why: 'L4 要求代码跑通加测试通过。' },
  { q: '为什么查询串不参与路由？', answer: '它只说明这次想怎么看。', criteria: '说出与资源身份的区别即算过' },
]);
run([b1]);

const qs = findAll(b1, 'quiz__q');
check('两道题都渲染出题面', qs.length === 2, `实际 ${qs.length}`);
check('题面带序号', qs[0].textContent.startsWith('1. ') && qs[1].textContent.startsWith('2. '), qs.map(q => q.textContent).join(' | '));

const optsWrap = findAll(b1, 'quiz__opts')[0];
check('选择题渲染 3 个选项', optsWrap && optsWrap.children.length === 3);

const feedback = findAll(b1, 'feedback')[0];
check('选择题反馈初始隐藏', feedback && feedback.hidden === true);

optsWrap.children[1].click();
check('点对选项 → 反馈可见且带 why', feedback.hidden === false && feedback.textContent.includes('✓ 对') && feedback.textContent.includes('L4 要求'));
check('点对选项 → 标 is-correct', optsWrap.children[1].classList.contains('is-correct'));
check('点对选项 → 错误选项不标红', !optsWrap.children[0].classList.contains('is-wrong'));

const reveal = findAll(b1, 'quiz__reveal')[0];
const answerBox = findAll(b1, 'quiz__answer')[0];
check('开放题有展开按钮', !!reveal && reveal.textContent === '想好了，看参考答案');
check('答案块初始收起', answerBox && answerBox.hidden === true);
reveal.click();
check('点开 → 显示参考答案与判分要点', answerBox.hidden === false &&
  answerBox.children.some(c => c.textContent === '参考答案') &&
  answerBox.children.some(c => c.textContent === '它只说明这次想怎么看。') &&
  answerBox.children.some(c => c.textContent === '判分要点') &&
  answerBox.children.some(c => c.textContent === '说出与资源身份的区别即算过'));
check('点开 → 按钮变成收起', reveal.textContent === '收起，再自己答一遍');
reveal.click();
check('再点 → 收起且按钮复原', answerBox.hidden === true && reveal.textContent === '想好了，看参考答案');
check('只有 1 道选择题时不显示计分（choiceCount=1）', findAll(b1, 'quiz__score').length === 0);

// ── 场景二：2 选择题 → 计分 ─────────────────────────────────────
const b2 = makeBlock([
  { q: 'A？', opts: ['对', '错'], ans: 0, why: '因为 A。' },
  { q: 'B？', opts: ['对', '错'], ans: 0, why: '因为 B。' },
]);
run([b2]);
const score = findAll(b2, 'quiz__score')[0];
check('两道选择题 → 有计分元素且初始隐藏', !!score && score.hidden === true);
const optWraps = findAll(b2, 'quiz__opts');
optWraps[0].children[0].click();   // 对
optWraps[1].children[1].click();   // 错
check('两题答完 → 计分显示 答对 1 / 2', score.hidden === false && score.textContent === '本题组：答对 1 / 2', score.textContent);

// ── 场景三：全开放题不出现计分 ──────────────────────────────────
const b3 = makeBlock([{ q: '开放题', answer: '答', criteria: '标准' }]);
run([b3]);
check('全开放题 → 不出现计分元素', findAll(b3, 'quiz__score').length === 0);

// ── 场景四：坏数据兜底 ──────────────────────────────────────────
const b4 = makeBlock([{ q: '既不是选择题也不是开放题' }]);
run([b4]);
const hint = findAll(b4, 'feedback')[0];
check('坏数据 → 显示数据不完整提示', !!hint && hint.textContent.includes('数据不完整'));

// ── 场景五：非法 JSON ───────────────────────────────────────────
const b5 = makeEl('div'); b5._data = '{不是 JSON';
run([b5]);
check('非法 JSON → 显示解析失败', b5.textContent.includes('解析失败'), b5.textContent);


// ── 场景六：围栏代码块（```lang）───────────────────────────────
const fenced = makeBlock([{
  q: '下面这段为什么死循环？\n\n```cpp\nwhile (i <= 100) {\n    ++cnt;\n}\n```\n\n① 哪里出问题？',
  opts: ['i 没变', 'cnt 没变', '循环条件写反'],
  ans: 0,
  why: '循环体里没改 i',
}]);
run([fenced]);

const codeBlocks = findAll(fenced, 'quiz__code');
check('围栏 → 生成代码块', codeBlocks.length === 1, `实际 ${codeBlocks.length}`);
const cb = codeBlocks[0] || {};
const cbCode = (cb.children || [])[0] || {};
check('代码块是 <pre>，里面是 <code>', cb.tagName === 'pre' && cbCode.tagName === 'code');
check('data-lang 传到 pre 上', cb.getAttribute('data-lang') === 'cpp', String(cb.getAttribute('data-lang')));
check('代码原文一字不动（含缩进）', cbCode.textContent === 'while (i <= 100) {\n    ++cnt;\n}',
      JSON.stringify(cbCode.textContent));
check(' prose 保留在代码块之外（前后两段都在）',
      fenced.textContent.includes('为什么死循环') && fenced.textContent.includes('① 哪里出问题'),
      JSON.stringify(findAll(fenced, 'quiz__q')[0].textContent));

const noLang = makeBlock([{ q: '看：\n```\nx = 1\n```', opts: ['a', 'b'], ans: 0, why: 'w' }]);
run([noLang]);
check('围栏不写语言 → 不设 data-lang（交给自动识别）',
      findAll(noLang, 'quiz__code')[0].getAttribute('data-lang') === null);

const inlineTick = makeBlock([{ q: 'shell 里 `pwd` 是做什么的？', opts: ['a', 'b'], ans: 0, why: 'w' }]);
run([inlineTick]);
check('行内单个反引号是普通字符（不解析成代码块）',
      findAll(inlineTick, 'quiz__code').length === 0 && inlineTick.textContent.includes('`pwd`'));

const unclosed = makeBlock([{ q: '看：\n```cpp\nx = 1;\ny = 2;', opts: ['a', 'b'], ans: 0, why: 'w' }]);
run([unclosed]);
check('围栏没闭合 → 兜底渲染成代码块到结尾',
      findAll(unclosed, 'quiz__code').length === 1 && unclosed.textContent.includes('y = 2;'));

const openFenced = makeBlock([{ q: '题面', answer: '参考答案：\n\n```cpp\nreturn 0;\n```', criteria: '写出即算过' }]);
run([openFenced]);
check('answer 里的围栏也渲染成代码块', findAll(openFenced, 'quiz__code').length === 1);

// 题号和判分前缀不能拼进围栏首行；JSON 字符串也可能使用 Windows 换行。
const leadingFence = makeBlock([
  { q: '```cpp\nint n = 1;\n```\n结果？', opts: ['1', '2'], ans: 0,
    why: '```cpp\nreturn 1;\n```\n解释' },
  { q: '```text\r\n    保留缩进\r\n```', answer: '答', criteria: '标准' },
]);
run([leadingFence]);
const leadingQuestions = findAll(leadingFence, 'quiz__q');
check('题号不破坏题干开头的围栏',
  findAll(leadingQuestions[0], 'quiz__code')[0]?.textContent === 'int n = 1;' &&
  leadingQuestions[0].textContent.startsWith('1. ') && leadingQuestions[0].textContent.endsWith('结果？'));
findAll(leadingFence, 'quiz__opts')[0].children[0].click();
const leadingFeedback = findAll(leadingFence, 'feedback')[0];
check('反馈前缀不破坏 why 开头的围栏',
  findAll(leadingFeedback, 'quiz__code')[0]?.textContent === 'return 1;' &&
  leadingFeedback.textContent.startsWith('✓ 对') && leadingFeedback.textContent.endsWith('解释'));
check('CRLF 围栏正常渲染且保留缩进',
  findAll(leadingQuestions[1], 'quiz__code')[0]?.textContent === '    保留缩进');

const invalidItems = [
  null, false, 1, '题目', [],
  { q: '越界', opts: ['a', 'b'], ans: 2, why: 'w' },
  { q: '小数', opts: ['a', 'b'], ans: 0.5, why: 'w' },
  { q: '无选项', opts: [], ans: 0, why: 'w' },
  { q: '无解释', opts: ['a', 'b'], ans: 0 },
  { q: '冲突', opts: ['a', 'b'], ans: 0, why: 'w', answer: 'a', criteria: 'c' },
  { q: '空答案', answer: ' ', criteria: 'c' },
  { answer: 'a', criteria: 'c' },
];
const invalid = makeBlock(invalidItems.concat([
  { q: '可答题', opts: ['a', 'b'], ans: 0, why: 'w' },
]));
const afterInvalid = makeBlock([{ q: '后续题组', answer: 'a', criteria: 'c' }]);
let invalidError = '';
try { run([invalid, afterInvalid]); } catch (e) { invalidError = e.message; }
check('非对象题目不抛错且后续题组继续渲染',
  !invalidError && findAll(afterInvalid, 'quiz__reveal').length === 1, invalidError);
check('不完整或冲突题目统一显示兜底',
  findAll(invalid, 'feedback').filter(e => e.textContent.includes('数据不完整')).length === invalidItems.length);
check('坏选择题不提供无效选项且不计入总分',
  findAll(invalid, 'quiz__opts').length === 1 && findAll(invalid, 'quiz__score').length === 0);

// ── 场景九：题面里的公式（`$…$` → .math-inline，排版交给 LessonMath）─────
// 题目正文是**运行时**才插进 DOM 的（lesson-math.js 早就跑完了），所以 quiz.js 必须自己
// 把 `$…$` 切成占位元素、再请 LessonMath 排一次；KaTeX 不在时占位元素里留着的 TeX 原文可读。
let typesetCalls = 0;
const b9 = makeBlock([
  { q: '矩阵 $\\begin{bmatrix} 2 & 1 \\\\ 1 & 3 \\end{bmatrix}$ 的行列式是多少？',
    opts: ['$1$', '$6$'], ans: 1, why: '用 $ad - bc$ 算。' },
  { q: '转义与不成对：\\$5 与 $x 都该是普通文本',
    answer: 'A', criteria: 'C' },
  { q: '代码里的美元号不当公式：\n\n```bash\necho $HOME\n```',
    answer: 'B', criteria: 'D' },
]);
run([b9], { LessonMath: { render() { typesetCalls += 1; } } });

const mathSpans = findAll(b9, 'math-inline');
check('题面里的 $…$ 变成 .math-inline', mathSpans.some(s => s.textContent.includes('begin{bmatrix}')),
  mathSpans.map(s => s.textContent).join(' | '));
check('选项里的 $…$ 也变成 .math-inline',
  findAll(b9, 'quiz__opts')[0].children.every(btn => findAll(btn, 'math-inline').length === 1));
const opts9 = findAll(b9, 'quiz__opts')[0];
opts9.children[1].click();
check('点选后解析里的 $…$ 也变成 .math-inline',
  findAll(b9, 'feedback')[0].children.concat(...findAll(b9, 'feedback')[0].children.map(c => c.children || []))
    .some(c => (c.className || '') === 'math-inline' && c.textContent === 'ad - bc') ||
  findAll(findAll(b9, 'feedback')[0], 'math-inline').some(s => s.textContent === 'ad - bc'));
check('转义 \\$ 与不成对的 $ 都按普通文本（不产生占位元素）',
  findAll(b9, 'quiz__q')[1].textContent.includes('$5 与 $x 都该是普通文本') &&
  findAll(findAll(b9, 'quiz__q')[1], 'math-inline').length === 0);
check('围栏代码块里的 $ 不当公式（代码块是独立节点）',
  findAll(b9, 'quiz__code').some(pre => pre.textContent.includes('echo $HOME')) &&
  findAll(findAll(b9, 'quiz__q')[2], 'math-inline').length === 0);
check('建块后请求过一次排版（LessonMath.render）', typesetCalls > 0, `调用 ${typesetCalls} 次`);

// LessonMath 不在（KaTeX 未加载）时不抛错，占位元素里留着 TeX 原文
let noMathApiError = '';
const b10 = makeBlock([{ q: '公式 $x^2$ 一段', answer: 'a', criteria: 'c' }]);
try { run([b10], {}); } catch (e) { noMathApiError = e.message; }
check('没有 LessonMath 时不抛错，公式原文仍可读',
  !noMathApiError && findAll(b10, 'math-inline').some(s => s.textContent === 'x^2'), noMathApiError);

console.log(failures === 0 ? '\n全部通过' : `\n${failures} 项失败`);
process.exit(failures === 0 ? 0 : 1);
