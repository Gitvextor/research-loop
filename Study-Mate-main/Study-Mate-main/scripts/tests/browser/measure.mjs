// 主题测量：对比度扫描 + 指定选择器计算值 + hover 实测
// 用法: node measure.mjs <file-url> [--hover "<selector>"]
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

const url = process.argv[2];
const hoverIdx = process.argv.indexOf('--hover');
const hoverSel = hoverIdx > 0 ? process.argv[hoverIdx + 1] : null;
const PORT = 9100 + Math.floor(Math.random() * 400);
const PROFILE = join(tmpdir(), `smtest-theme-${Date.now()}-${Math.random().toString(36).slice(2)}`);

const chrome = spawn('google-chrome', [
  '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
  `--user-data-dir=${PROFILE}`,
  `--remote-debugging-port=${PORT}`, '--window-size=1280,900', 'about:blank',
], { stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function target() {
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
const page = await target();
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
await send('Runtime.enable');
await send('Page.navigate', { url });
await sleep(1500);

if (process.env.ACT) {
  await send('Runtime.evaluate', { expression: `(() => {
    document.querySelectorAll('.quiz__reveal').forEach((b) => b.click());
    document.querySelectorAll('.quiz__opts').forEach((g, i) => { const b = g.children[i % 2 ? 0 : 1] || g.children[0]; if (b) b.click(); });
  })()` });
  await sleep(600);
}

if (process.env.SCROLL) {
  await send('Runtime.evaluate', { expression: `document.documentElement.style.scrollBehavior = 'auto'; window.scrollTo(0, ${Number(process.env.SCROLL)});` });
  await sleep(800);
}

const SCAN = `(() => {
  const parse = (c) => {
    const m = String(c).match(/rgba?\\(([^)]+)\\)/);
    if (!m) return null;
    const p = m[1].split(',').map((x) => parseFloat(x));
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  };
  const over = (fg, bg) => ({ r: fg.r * fg.a + bg.r * (1 - fg.a), g: fg.g * fg.a + bg.g * (1 - fg.a), b: fg.b * fg.a + bg.b * (1 - fg.a), a: 1 });
  const lum = ({ r, g, b }) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b); const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1]; return (hi + 0.05) / (lo + 0.05); };
  const accOpacity = (el) => {
    let a = 1;
    for (let n = el; n && n !== document.documentElement; n = n.parentElement) {
      const o = parseFloat(getComputedStyle(n).opacity);
      if (!isNaN(o)) a *= o;
    }
    return a;
  };
  const effBg = (el) => {
    let acc = null;
    for (let n = el; n; n = n.parentElement) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (!c || c.a === 0) continue;
      acc = acc ? over(acc, c) : c;
      if (acc.a === 1) break;
    }
    return acc && acc.a === 1 ? acc : over(acc || { r: 255, g: 255, b: 255, a: 1 }, { r: 255, g: 255, b: 255, a: 1 });
  };
  const path = (el) => {
    const bits = [];
    for (let n = el; n && n.tagName !== 'BODY' && bits.length < 4; n = n.parentElement) {
      bits.unshift(n.tagName.toLowerCase() + (n.className && typeof n.className === 'string' ? '.' + n.className.trim().split(/\\s+/).join('.') : ''));
    }
    return bits.join(' > ');
  };
  const fails = [];
  const all = Array.from(document.querySelectorAll('*'));
  let counted = 0;
  for (const el of all) {
    const txt = Array.from(el.childNodes).filter((n) => n.nodeType === 3).map((n) => n.textContent.trim()).join('');
    if (!txt) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) < 0.1) continue;
    const box = el.getBoundingClientRect();
    if (!box.width || !box.height) continue;
    counted++;
    let fg = parse(cs.color);
    if (!fg) continue;
    const bg = effBg(el);   // 从元素自身起合成：文字画在自己的 background 之上
    const op = accOpacity(el);
    if (op < 1) fg = { ...fg, a: fg.a * op };   // 半透明元素：文字向背景靠拢
    const cr = ratio(over(fg, bg), bg);
    const size = parseFloat(cs.fontSize);
    const bold = parseInt(cs.fontWeight, 10) >= 700;
    const large = size >= 18.66 || (bold && size >= 14);
    const need = large ? 3 : 4.5;
    if (cr < need) {
      fails.push({ op: Math.round(op * 100) / 100, sel: path(el), cr: Math.round(cr * 100) / 100, need, size: Math.round(size * 100) / 100, fg: cs.color, bg: 'rgb(' + [bg.r, bg.g, bg.b].map(Math.round).join(',') + ')', text: txt.slice(0, 28) });
    }
  }
  return { counted, fails };
})()`;

const { result } = await send('Runtime.evaluate', { expression: SCAN, returnByValue: true });
const { counted, fails } = result.value;
const theme = await send('Runtime.evaluate', { expression: `document.documentElement.getAttribute('data-theme')`, returnByValue: true });
console.log(`\n=== ${url.split('/').pop()}  theme=${theme.result.value}  含文本元素 ${counted}，不达标 ${fails.length}`);
for (const f of fails) console.log(`  ${String(f.cr).padEnd(5)} (需 ${f.need})${f.op < 1 ? ' op=' + f.op : ''} ${f.size}px  ${f.fg} on ${f.bg}  ${f.sel}  「${f.text}」`);

if (hoverSel) {
  const box = await send('Runtime.evaluate', {
    expression: `(() => { const e = document.querySelector(${JSON.stringify(hoverSel)}); if (!e) return null;
      document.documentElement.style.scrollBehavior = 'auto';
      e.scrollIntoView({ block: 'center' });
      const r = e.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; })()`,
    returnByValue: true,
  });
  if (box.result.value) {
    await sleep(300);
    const box2 = await send('Runtime.evaluate', {
      expression: `(() => { const r = document.querySelector(${JSON.stringify(hoverSel)}).getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; })()`,
      returnByValue: true,
    });
    await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: box2.result.value.x, y: box2.result.value.y, buttons: 0 });
    await sleep(500);
    const st = await send('Runtime.evaluate', {
      expression: `(() => { const e = document.querySelector(${JSON.stringify(hoverSel)}); const cs = getComputedStyle(e);
        return { bg: cs.backgroundColor, border: cs.borderTopColor, color: cs.color, shadow: cs.boxShadow }; })()`,
      returnByValue: true,
    });
    if (st.exceptionDetails) console.log('  hover 异常:', JSON.stringify(st.exceptionDetails.exception));
    console.log(`  hover ${hoverSel} →`, JSON.stringify(st.result && st.result.value));
  }
}

const DUMP = process.env.DUMP;
if (DUMP) {
  const st = await send('Runtime.evaluate', {
    expression: `(() => { const out = {};
    for (const sel of ${JSON.stringify(DUMP)}.split('|')) { const e = document.querySelector(sel); if (!e) { out[sel] = null; continue; }
      const cs = getComputedStyle(e); out[sel] = { color: cs.color, bg: cs.backgroundColor, borderLeft: cs.borderLeftColor, shadow: cs.boxShadow, font: cs.fontSize }; }
    return out; })()`,
    returnByValue: true,
  });
  if (st.exceptionDetails) console.log('  dump 异常:', JSON.stringify(st.exceptionDetails.exception));
  console.log('  dump:', JSON.stringify(st.result && st.result.value, null, 1));
}

ws.close();
await killChrome();
