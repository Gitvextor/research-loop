// 亮色模式下把所有 hover 态的计算样式列出来（背景/边框/阴影），找"米色底 + 绿色滤镜"
import { spawn } from 'node:child_process';
import { rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

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


const pages = process.argv.slice(2);
const PORT = 9400 + Math.floor(Math.random() * 300);
const PROFILE = join(tmpdir(), 'smtest-hover-' + Date.now());
const chrome = spawn('google-chrome', ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
  `--user-data-dir=${PROFILE}`, `--remote-debugging-port=${PORT}`,
  '--window-size=1280,900', 'about:blank'], { stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function tgt() {
  for (let i = 0; i < 60; i++) {
    try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      const p = l.find((t) => t.type === 'page'); if (p) return p; } catch {}
    await sleep(200);
  }
  throw new Error('no chrome');
}
const page = await tgt();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map();
ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); } };
const send = (method, params = {}) => new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
await send('Page.enable');

const SELECTORS = ['.quiz__opt', '.quiz button', '.learn-filter__btn', '.learn-filter__btn.is-active',
  '.learn-node', '.learn-child', '.learn-attachment', '.learn-subject-card', '.lesson-related a',
  '.doc-sidebar a', '.lesson-nav__link'];

for (const url of pages) {
  await send('Page.navigate', { url });
  await sleep(1500);
  console.log(`\n=== ${url.split('/').pop()}`);
  for (const sel of SELECTORS) {
    const box = await send('Runtime.evaluate', {
      expression: `(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return null;
        const r = e.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + Math.min(r.height / 2, 10) }; })()`,
      returnByValue: true,
    });
    if (!box.result.value) continue;
    const { x, y } = box.result.value;
    const before = await send('Runtime.evaluate', {
      expression: `(() => { const cs = getComputedStyle(document.querySelector(${JSON.stringify(sel)}));
        return [cs.backgroundColor, cs.borderTopColor, cs.boxShadow]; })()`, returnByValue: true });
    await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 5, y: 5 });
    await sleep(120);
    await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y, buttons: 0 });
    await sleep(220);
    const after = await send('Runtime.evaluate', {
      expression: `(() => { const cs = getComputedStyle(document.querySelector(${JSON.stringify(sel)}));
        return [cs.backgroundColor, cs.borderTopColor, cs.boxShadow]; })()`, returnByValue: true });
    const [b0, br0, sh0] = before.result.value;
    const [b1, br1, sh1] = after.result.value;
    const same = b0 === b1 && br0 === br1;
    console.log(`  ${sel.padEnd(28)} hover ${same ? '(无变化)' : ''}`);
    if (!same) {
      if (b0 !== b1) console.log(`      bg     ${b0}  →  ${b1}`);
      if (br0 !== br1) console.log(`      border ${br0}  →  ${br1}`);
    }
  }
}
ws.close();
await killChrome();
