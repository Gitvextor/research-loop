// 题目里的代码块：在真实 Chrome 里验渲染与上色
//   node scripts/tests/browser/quiz_code_test.mjs
//
// 钉住两件在假 DOM 里测不到的事：
//   1. 围栏渲染出的 <pre><code> 真的按等宽 + 保留缩进排（缩进靠 Range 量左边界）
//   2. quiz.js 建完块会**自己**触发一次上色——learn-theme.js 的自动扫描挂在 head、
//      DOMContentLoaded 先注册，扫描跑在 quiz.js 建块之前，不显式再扫就没有 syn-* 类
import { spawn } from 'node:child_process';
import { rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';

const HERE = dirname(fileURLToPath(import.meta.url));
const FIXTURE = 'file://' + join(HERE, 'quiz-code-fixture.html');
const PORT = 9500 + Math.floor(Math.random() * 300);
const PROFILE = join(tmpdir(), 'smtest-quizcode-' + Date.now());

const chrome = spawn('google-chrome', ['--headless=new', '--disable-gpu', '--hide-scrollbars',
  '--no-first-run', `--user-data-dir=${PROFILE}`, `--remote-debugging-port=${PORT}`,
  '--window-size=1200,900', 'about:blank'], { stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function pageTarget() {
  for (let i = 0; i < 60; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      const p = list.find((t) => t.type === 'page');
      if (p) return p;
    } catch {}
    await sleep(200);
  }
  throw new Error('chrome 没起来');
}

async function killChrome() {
  // 等 chrome 真的退出再删 profile：kill() 只是发信号，进程还在写盘时删会被它重建
  await new Promise((resolve) => {
    const done = () => resolve();
    chrome.once('exit', done);
    setTimeout(done, 3000);
    chrome.kill();
  });
  try { rmSync(PROFILE, { recursive: true, force: true }); } catch {}
}

let failures = 0;
function check(label, ok, extra = '') {
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}${extra ? '  — ' + extra : ''}`);
  if (!ok) failures++;
}

const page = await pageTarget();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0;
const pending = new Map();
ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); }
};
const send = (method, params = {}) =>
  new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });

await send('Page.enable');
await send('Page.navigate', { url: FIXTURE });
await sleep(1800);

const probe = `(() => {
  const textNodes = (root) => {
    const nodes = [];
    (function rec(el) { for (const c of el.childNodes) { if (c.nodeType === 3) nodes.push(c); else rec(c); } })(root);
    return nodes;
  };
  // 上色会把一行拆进多个 span，按字符建映射再量——否则 indexOf 永远找不到整行。
  // 注意：这段是要传给 Runtime.evaluate 的模板字符串，里面不能有反斜杠转义（模板会先吃掉），
  // 所以换行用 String.fromCharCode(10)，缩进用纯空格正则。
  const NL = String.fromCharCode(10);
  const lineLefts = (root) => {
    const map = [];
    for (const node of textNodes(root)) {
      for (let i = 0; i < node.textContent.length; i++) map.push([node, i]);
    }
    const text = map.map((pair) => pair[0].textContent[pair[1]]).join('');
    const lefts = [];
    let start = 0;
    for (const line of text.split(NL)) {
      const stripped = line.replace(/^ +/, '');
      if (stripped) {
        const at = line.length - stripped.length;
        const pair = map[start + at];
        const r = document.createRange();
        r.setStart(pair[0], pair[1]); r.setEnd(pair[0], pair[1] + 1);
        lefts.push({ text: stripped.slice(0, 22), left: Math.round(r.getBoundingClientRect().left) });
      }
      start += line.length + 1;
    }
    return lefts;
  };

  const q1 = document.getElementById('q1');
  const q2 = document.getElementById('q2');
  const pre = q1.querySelector('.quiz__code');
  const code = pre && pre.querySelector('code');
  const cs = code && getComputedStyle(code);
  return {
    hasPre: !!pre,
    lang: pre && pre.getAttribute('data-lang'),
    codeText: code && code.textContent,
    mono: cs && /mono/i.test(cs.fontFamily),
    weight: cs && cs.fontWeight,
    syn: code ? code.querySelectorAll('[class^="syn-"]').length : 0,
    kw: code ? [...code.querySelectorAll('.syn-keyword')].map((e) => e.textContent) : [],
    lines: code ? lineLefts(code) : [],
    proseBefore: q1.textContent.includes('这段为什么死循环'),
    proseAfter: q1.textContent.includes('① 变量谁没变'),
    q2Code: q2.querySelectorAll('.quiz__code').length,
    q2Text: q2.textContent,
  };
})()`;

const res = await send('Runtime.evaluate', { expression: probe, returnByValue: true });
if (res.exceptionDetails) {
  console.log('FAIL  探测脚本自身报错：' + (res.exceptionDetails.exception
    ? res.exceptionDetails.exception.description : res.exceptionDetails.text));
  ws.close();
  await killChrome();
  process.exit(1);
}
const v = res.result.value || {};

check('围栏渲染出 .quiz__code', v.hasPre);
check('data-lang=cpp 传到 pre 上', v.lang === 'cpp', String(v.lang));
check('代码原文与缩进一字不动', v.codeText === 'int i = 1;\nwhile (i <= 100) {\n    ++cnt;\n    if (cnt > 9) break;\n}',
      JSON.stringify(v.codeText));
check('代码用等宽字体', v.mono === true);
check('代码不是粗体（不继承题面的 600）', v.weight === '400', String(v.weight));
check('自动上色：出现 syn-* 类', v.syn > 0, `${v.syn} 个`);
check('关键字着色（while/if 等）', v.kw.includes('while') && v.kw.includes('if'), JSON.stringify(v.kw));
{
  const l = v.lines || [];
  const base = l.length ? l[0].left : null;
  const same = l.filter((x) => x.left === base).length;
  const indented = l.filter((x) => x.left > base);
  check('缩进保留：5 行里 3 行顶格、2 行缩进且同一列',
        l.length === 5 && same === 3 && indented.length === 2 && indented[0].left === indented[1].left,
        l.map((x) => `${x.left}:${x.text}`).join(' | '));
}
check('代码块前后的散文都在（没被吞掉）', v.proseBefore && v.proseAfter);
check('没有围栏的题面不产生代码块', v.q2Code === 0, `实际 ${v.q2Code}`);
check('纯散文题面的换行仍保留', v.q2Text.includes('n 是 5。') && v.q2Text.includes('循环体跑几次'));

console.log(failures === 0 ? '\n全部通过' : `\n${failures} 项失败`);
ws.close();
chrome.kill();
await killChrome();
process.exit(failures === 0 ? 0 : 1);
