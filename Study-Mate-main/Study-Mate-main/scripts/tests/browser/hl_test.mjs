// 在真实 Chrome 里跑代码块高亮的断言：node scripts/tests/browser/hl_test.mjs
import { spawn } from 'node:child_process';
import { rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';

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

const HERE = dirname(fileURLToPath(import.meta.url));

const FIXTURE = 'file://' + join(HERE, 'highlight-fixture.html');
const PROFILE = join(tmpdir(), 'smtest-hl-' + Date.now());
const PORT = 9800 + Math.floor(Math.random() * 300);

const chrome = spawn('google-chrome', [
  '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
  `--user-data-dir=${PROFILE}`,
  `--remote-debugging-port=${PORT}`, '--window-size=1000,900', 'about:blank',
], { stdio: 'ignore' });

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
await sleep(1500);

const probe = `(() => {
  const syn = (sel) => Array.from(document.querySelectorAll(sel + ' .syn-keyword, ' + sel + ' .syn-string, ' + sel + ' .syn-type, ' + sel + ' .syn-func, ' + sel + ' .syn-comment, ' + sel + ' .syn-number, ' + sel + ' .syn-macro, ' + sel + ' .syn-operator'));
  const texts = (sel, cls) => Array.from(document.querySelectorAll(sel + ' .' + cls)).map(e => e.textContent);
  return {
    b1: texts('#b1', 'syn-keyword').concat(texts('#b1', 'syn-type')),
    b1num: document.querySelectorAll('#b1 .syn-number').length,
    b1comment: texts('#b1', 'syn-comment').length,
    b2func: texts('#b2', 'syn-func'),
    b2comment: texts('#b2', 'syn-comment'),
    b2op: texts('#b2', 'syn-operator'),
    b2var: texts('#b2', 'syn-type'),
    b3kw: texts('#b3', 'syn-keyword'),
    b3warn: texts('#b3', 'syn-macro'),
    b3file: texts('#b3', 'syn-func'),
    b4count: syn('#b4').length,
    b5kw: texts('#b5', 'syn-type').concat(texts('#b5', 'syn-keyword')),
    b5comment: texts('#b5', 'syn-comment').length,
    b6spans: document.querySelectorAll('#b6 [class^="syn-"]').length,
    b6text: document.querySelector('#b6 .line').textContent,
    b7: texts('#b7', 'syn-func').concat(texts('#b7', 'syn-operator')),
    b8count: syn('#b8').length,
    b9: texts('#b9', 'syn-func').concat(texts('#b9', 'syn-comment')),
    b10: texts('#b10', 'syn-type').concat(texts('#b10', 'syn-string')),
    b11func: texts('#b11', 'syn-func'),
    b11macro: texts('#b11', 'syn-macro'),
    b12func: texts('#b12', 'syn-func'),
    b13count: syn('#b13').length,
    b14count: syn('#b14').length,
    b15kw: texts('#b15', 'syn-keyword'),
    b16: texts('#b16', 'syn-type').concat(texts('#b16', 'syn-func'), texts('#b16', 'syn-string')),
    b17key: texts('#b17', 'syn-func'),
    b17kw: texts('#b17', 'syn-keyword'),
    b18kw: texts('#b18', 'syn-keyword'),
    b11html: document.querySelector('#b11 code').innerHTML,
    textIntact: document.querySelector('#b2 code').textContent.indexOf('mkdir -p ~/cpp && cd ~/cpp') === 0,
    noNul: document.body.innerHTML.indexOf('\\u0000') === -1,
  };
})()`;

const { result } = await send('Runtime.evaluate', { expression: probe, returnByValue: true });
const r = result.value;

const checks = [
  ['cpp：关键字/类型着色（int 出现≥5 次）', r.b1.filter((t) => ['int', 'double', 'for', 'return'].includes(t)).length >= 5],
  ['cpp：数字着色', r.b1num >= 4],
  ['cpp：注释着色', r.b1comment >= 1],
  ['sh：命令行着色', r.b2func.includes('mkdir') && r.b2func.includes('g++') && r.b2func.includes('./hello')],
  ['sh：行内注释着色', r.b2comment.some((t) => t.startsWith('#'))],
  ['sh：选项着色', r.b2op.includes('-o')],
  ['sh：变量着色', r.b2var.includes('$PATH')],
  ['term：error 着色', r.b3kw.includes('error')],
  ['term：warning 着色', r.b3warn.includes('warning')],
  ['term：文件名:行:列 着色', r.b3file.includes('hello.cpp:5:40')],
  ['普通输出不动（0 个 span）', r.b4count === 0],
  ['编辑器块自动着色', r.b5kw.includes('int') && r.b5comment === 1],
  ['手写高亮块跳过（仍是 1 个 span）', r.b6spans === 1],
  ['手写块文字未被破坏', r.b6text.includes('expected')],
  ['data-lang 生效', r.b7.includes('npm') || r.b7.length > 0],
  ['data-lang=text 不上色', r.b8count === 0],
  ['纯文本没被改动（连字符没被吃）', r.textIntact],
  ['没有占位符残留', r.noNul],
  ['sh：未在命令表里的行也认得出（hello / ./hello）', r.b9.includes('hello') && r.b9.some((t) => t.startsWith('#'))],
  ['cpp：片段（无 include）也认得出', r.b10.includes('cout') && r.b10.some((t) => t.includes('Hello'))],
  ['sh：&& 后面的命令也着色', r.b11func.includes('mkdir') && r.b11func.includes('cd') && r.b11func.includes('cat')],
  ['sh：混合命令 && 着色', r.b12func.includes('g++') && r.b12func.includes('./hello')],
  ['程序输出不动', r.b13count === 0],
  ['题面文字不动', r.b14count === 0],
  ['js 认得出', r.b15kw.includes('const')],
  ['html：标签名/属性/属性值着色', r.b16.includes('nav') && r.b16.includes('class') && r.b16.includes('"syo-nav"')],
  ['json：键着色', r.b17key.includes('"name"')],
  ['json：字面量着色', r.b17kw.includes('true')],
  ['ts：interface 着色', r.b18kw.includes('interface')],
];

let bad = 0;
for (const [name, ok] of checks) {
  if (!ok) bad++;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}`);
}
console.log(`\n${checks.length - bad}/${checks.length} 通过`);
if (bad) console.log('detail:', JSON.stringify(r));

ws.close();
await killChrome();
process.exit(bad ? 1 : 0);
