// 在真实 Chrome 里验公式排版：node scripts/tests/browser/math_test.mjs
//
// 为什么要有这一条：渲染器与检查器只能保证"语法对、引用在"，**排不排得出来只有浏览器知道**——
// KaTeX 加载失败、字体路径写错、lesson-math.js 的顺序不对（先跑后加载），页面都会安静地
// 显示 TeX 原文。这条断言的就是"真的排出来了"。
import { spawn } from 'node:child_process';
import { rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';

const HERE = dirname(fileURLToPath(import.meta.url));
const FIXTURE = 'file://' + join(HERE, 'math-fixture.html');
const PROFILE = join(tmpdir(), 'smtest-math-' + Date.now());
const PORT = 9900 + Math.floor(Math.random() * 90);

const chrome = spawn('google-chrome', [
  '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
  `--user-data-dir=${PROFILE}`,
  `--remote-debugging-port=${PORT}`, '--window-size=1000,900', 'about:blank',
], { stdio: 'ignore' });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let failures = 0;
let total = 0;

function check(label, ok, detail = '') {
  total += 1;
  failures += ok ? 0 : 1;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}${ok || !detail ? '' : `  — ${detail}`}`);
}

async function killChrome() {
  await new Promise((resolve) => {
    const done = () => resolve();
    chrome.once('exit', done);
    setTimeout(done, 3000);
    chrome.kill();
  });
  try { rmSync(PROFILE, { recursive: true, force: true }); } catch {}
}

async function pageTarget() {
  for (let i = 0; i < 60; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      const page = list.find((t) => t.type === 'page');
      if (page) return page;
    } catch {}
    await sleep(200);
  }
  throw new Error('chrome 没起来');
}

try {
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
  await sleep(1500);          // 等 defer 脚本跑完、KaTeX 排版完成

  const probe = await send('Runtime.evaluate', {
    returnByValue: true,
    expression: `(() => {
      const out = {};
      out.katexNodes = document.querySelectorAll('.katex').length;
      out.inlineRendered = !!document.querySelector('.math-inline .katex');
      out.blockDisplay = !!document.querySelector('.math-block .katex-display');
      out.inlineHasDisplay = !!document.querySelector('.math-inline .katex-display');
      const first = document.querySelector('.math-inline .katex');
      out.fontFamily = first ? getComputedStyle(first).fontFamily : '';
      out.errorShown = !!document.querySelector('.katex-error');
      out.tailText = document.body.textContent.includes('后面这段正常文字还要在');
      // 题目里的公式：由 quiz.js 建块时插入，所以这里验的是「运行时插进来的也被排了」
      out.quizBuilt = !!document.querySelector('.quiz__q');
      out.quizMath = document.querySelectorAll('.quiz__q .math-inline').length;
      out.quizRendered = document.querySelectorAll('.quiz__q .katex').length;
      out.optRendered = document.querySelectorAll('.quiz__opt .katex').length;
      // 选项点开后解析里的公式
      const wrong = [...document.querySelectorAll('.quiz__opt')].pop();
      if (wrong) wrong.click();
      out.whyRendered = document.querySelectorAll('.feedback .katex').length;
      return JSON.stringify(out);
    })()`,
  });
  const out = JSON.parse(probe.result.value);

  check('行内公式真的排出来了（.math-inline 里有 .katex）', out.inlineRendered, JSON.stringify(out));
  check('块级公式走 display 模式（.math-block 里有 .katex-display）', out.blockDisplay, JSON.stringify(out));
  check('行内公式不是 display 模式', !out.inlineHasDisplay, JSON.stringify(out));
  check('KaTeX 样式生效（字体族是 KaTeX_*）', /KaTeX_/.test(out.fontFamily), out.fontFamily);
  check('两处以上公式都排了（不是只处理第一个）', out.katexNodes >= 3, `katex 节点 ${out.katexNodes}`);
  check('写错的公式按错误显示、不炸整页', out.errorShown && out.tailText, JSON.stringify(out));
  check('题目建块了（quiz.js 跑到）', out.quizBuilt, JSON.stringify(out));
  check('题面里的公式也排出来了（运行时插入的）', out.quizRendered >= 1, JSON.stringify(out));
  check('选项里的公式排出来了', out.optRendered >= 2, JSON.stringify(out));
  check('点选后解析里的公式排出来了', out.whyRendered >= 1, JSON.stringify(out));
} catch (error) {
  check('浏览器套件跑完（chrome 起来、页面能打开）', false, String(error));
} finally {
  await killChrome();
}

console.log(failures ? `\n${total - failures}/${total} 通过` : `\n${total}/${total} 通过`);
process.exit(failures ? 1 : 0);
