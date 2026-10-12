// 截图工具：整页截图 + 记录目标元素位置（浅色/深色各一张），供人工验收与文档配图。
//   node scripts/tests/browser/shot.mjs <file-url> <out-prefix> <css-selector>
// 产出：<out-prefix>-<theme>-full.png（整页）与 <out-prefix>-box.json（各主题下目标元素的框），
// 由调用方按 box.json 裁图——headless 的 clip 原点不可靠，所以"整页截 + 事后裁"。
// 失败路径（chrome 起不来 / 选择器没命中）也要收尾：非零退出、不留 profile、不留孤儿 chrome。
import { spawn } from 'node:child_process';
import { rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const [url, prefix, selector] = process.argv.slice(2);
if (!url || !prefix || !selector) {
  console.error('用法：node scripts/tests/browser/shot.mjs <file-url> <out-prefix> <css-selector>');
  process.exit(2);
}
const PORT = 9950 + Math.floor(Math.random() * 40);
const PROFILE = join(tmpdir(), 'smshot-' + Date.now());
const chrome = spawn('google-chrome', ['--headless=new', '--disable-gpu', '--hide-scrollbars',
  '--no-first-run', `--user-data-dir=${PROFILE}`, `--remote-debugging-port=${PORT}`,
  '--window-size=820,900', 'about:blank'], { stdio: 'ignore' });
// 没装 chrome / 起不来时 spawn 抛的是未捕获的 ENOENT（带回溯），把文档里那条失败路径变成死代码。
// 接住 'error' 存下来，交给 target() 抛出去 —— 还是同一个 catch：一行可读报错 + 非零退出 + 收尾
let spawnError = null;
chrome.on('error', (error) => { spawnError = error; });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function target() {
  for (let i = 0; i < 60; i++) {
    if (spawnError) throw new Error(`chrome 起不来：${spawnError.message}`);
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      const page = list.find((t) => t.type === 'page');
      if (page) return page;
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

let ws = null;
try {
  const page = await target();
  ws = new WebSocket(page.webSocketDebuggerUrl);
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
  await send('Emulation.setDeviceMetricsOverride', { width: 820, height: 900, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url });
  await sleep(2000);

  const boxes = {};
  for (const theme of ['light', 'dark']) {
    // 走 LearnTheme 自己的接口：直接改 data-theme 会被 apply() 按 localStorage 覆盖
    await send('Runtime.evaluate', { expression:
      `window.LearnTheme ? LearnTheme.set('${theme}') : document.documentElement.setAttribute('data-theme', '${theme}')` });
    await sleep(500);
    const box = await send('Runtime.evaluate', { expression: `(() => {
      const el = document.querySelector(${JSON.stringify(selector)});
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { top: Math.max(0, Math.round(r.top + window.scrollY - 24)),
               height: Math.round(r.height + 48),
               pageH: document.documentElement.scrollHeight };
    })()`, returnByValue: true });
    boxes[theme] = box.result.value;
    if (!boxes[theme]) {
      // 不能把 null 写进 box.json 还 exit 0：调用方会在 box['top'] 上炸，且"截了个空"没人知道
      throw new Error(`选择器没命中任何元素：${selector}（${theme} 主题下）——先确认这个页面上真有它`);
    }
    const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
    writeFileSync(`${prefix}-${theme}-full.png`, Buffer.from(shot.data, 'base64'));
    console.log(`  ${theme}: ${JSON.stringify(boxes[theme])}`);
  }
  writeFileSync(`${prefix}-box.json`, JSON.stringify(boxes, null, 1));
} catch (e) {
  // 可读的失败行（不抛回溯）：chrome 起不来 / 选择器没命中都走这里，退出码非零
  console.error('截图失败：' + e.message);
  process.exitCode = 1;
} finally {
  if (ws) ws.close();
  await killChrome();
}
