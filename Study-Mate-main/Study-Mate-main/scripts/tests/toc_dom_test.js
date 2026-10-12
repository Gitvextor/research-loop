const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const ASSET = path.join(__dirname, '..', '..', 'templates', 'assets', 'lesson-toc.js');

function el(tag, cls = '', text = '') {
  const e = {
    tagName: tag.toUpperCase(), className: cls, id: '', textContent: text, href: '',
    children: [], parentNode: null, _attrs: {}, _handlers: {}, style: {},
    setAttribute(k, v) { this._attrs[k] = v; },
    getAttribute(k) { return this._attrs[k] ?? null; },
    set innerHTML(v) { const c = el('svg'); c.parentNode = this; this.children = [c]; },
    get firstChild() { return this.children[0] || null; },
    get nextSibling() {
      if (!this.parentNode) return null;
      const i = this.parentNode.children.indexOf(this);
      return this.parentNode.children[i + 1] || null;
    },
    detach(c) {                       // 真 DOM 的语义：一个节点只能有一个父节点
      if (c.parentNode) {
        const old = c.parentNode.children.indexOf(c);
        if (old !== -1) c.parentNode.children.splice(old, 1);
      }
    },
    appendChild(c) { this.detach(c); c.parentNode = this; this.children.push(c); return c; },
    insertBefore(c, ref) {
      this.detach(c);
      c.parentNode = this;
      const i = ref ? this.children.indexOf(ref) : -1;
      if (i === -1) this.children.push(c); else this.children.splice(i, 0, c);
      return c;
    },
    addEventListener(type, fn) { (this._handlers[type] = this._handlers[type] || []).push(fn); },
    fire(type) { (this._handlers[type] || []).forEach(fn => fn({})); },
    querySelectorAll(sel) {
      const m = /^([a-zA-Z][\w-]*)?((?:\.[\w-]+)*)$/.exec(sel) || ['', '', ''];
      const tag = (m[1] || '').toUpperCase();
      const classes = m[2] ? m[2].split('.').filter(Boolean) : [];
      const out = [];
      (function walk(n) {
        (n.children || []).forEach(c => {
          const cls = (c.className || '').split(/\s+/);
          if ((!tag || c.tagName === tag) && classes.every(k => cls.includes(k))) out.push(c);
          walk(c);
        });
      })(this);
      return out;
    },
    querySelector(sel) { return this.querySelectorAll(sel)[0] || null; },
  };
  e.classList = {
    add: (k) => { const s = new Set((e.className || '').split(/\s+/).filter(Boolean)); s.add(k); e.className = [...s].join(' '); },
    remove: (k) => { const s = new Set((e.className || '').split(/\s+/).filter(Boolean)); s.delete(k); e.className = [...s].join(' '); },
    contains: (k) => (e.className || '').split(/\s+/).includes(k),
    toggle: (k, force) => {
      const on = force === undefined ? !e.classList.contains(k) : !!force;
      on ? e.classList.add(k) : e.classList.remove(k); return on;
    },
  };
  return e;
}

function page(h2s, withBar = true, nav = null) {
  const body = el('body');
  const bar = el('nav', 'lesson-bar');
  const article = el('article', 'lesson');
  h2s.forEach(([text, id]) => { const h = el('h2', '', text); h.id = id || ''; article.appendChild(h); });
  let navEl = null;
  if (nav) {                                  // nav = [['prev','0001-x.html'], ['next','0003-y.html']]
    navEl = el('nav', 'lesson-nav');
    nav.forEach(([dir, href]) => {
      const a = el('a', `lesson-nav__link lesson-nav__link--${dir}`);
      a.href = href;
      navEl.appendChild(a);
    });
    article.appendChild(navEl);
  }
  if (withBar) body.appendChild(bar);
  body.appendChild(article);
  return { body, article, bar, navEl };
}

function run(body, { readyState = 'interactive', width = 1400, store = new Map() } = {}) {
  const listeners = {};
  const window = {
    innerWidth: width,
    localStorage: {
      getItem: (k) => (store.has(k) ? store.get(k) : null),
      setItem: (k, v) => store.set(k, String(v)),
    },
    addEventListener: (t, fn) => { (listeners[t] = listeners[t] || []).push(fn); },
    resize: (w) => { window.innerWidth = w; (listeners.resize || []).forEach(fn => fn()); },
  };
  const sandbox = {
    console, window,
    document: {
      readyState, body,
      querySelector: (s) => body.querySelector(s),
      querySelectorAll: (s) => body.querySelectorAll(s),
      createElement: (t) => el(t),
      addEventListener() {},
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(ASSET, 'utf8'), sandbox);
  return { window, store };
}

let fails = 0;
const check = (label, ok, extra = '') => { console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}${extra ? '  — ' + extra : ''}`); if (!ok) fails++; };

// ④ 上/下节课指针：正文里的 .lesson-nav 被搬到侧栏最后
{
  const { body, article, navEl } = page([['第一节', ''], ['第二节', '']], true,
    [['prev', '0001-overview-map.html'], ['next', '0003-io-and-vars.html']]);
  run(body);
  const aside = body.querySelector('.doc-sidebar');
  check('nav 被搬进侧栏', navEl.parentNode === aside);
  check('nav 是侧栏最后一个子元素', aside.children[aside.children.length - 1] === navEl);
  check('正文里不再有 nav（只有一份）', !article.querySelector('.lesson-nav'));
  check('两条指针都在', aside.querySelectorAll('.lesson-nav__link').length === 2);
}

// ⑤ 没有 nav / 只有一条：都不能出问题
{
  const { body } = page([['第一节', ''], ['第二节', '']]);
  run(body);
  check('没有 .lesson-nav → 侧栏照常生成', !!body.querySelector('.doc-sidebar') && !body.querySelector('.lesson-nav'));

  const only = page([['第一节', ''], ['第二节', '']], true, [['next', '0003-io-and-vars.html']]);
  run(only.body);
  const aside = only.body.querySelector('.doc-sidebar');
  check('第一课只有下节课 → 只搬一条', aside.querySelectorAll('.lesson-nav__link').length === 1
        && !!aside.querySelector('.lesson-nav__link--next'));
}


// ① 三节：网格外壳 + 遮罩 + 侧栏 + 链接
{
  const { body, article, bar } = page([['第一节', ''], ['第二节', 'has-id'], ['第三节', '']]);
  run(body);
  const grid = body.querySelector('.doc-grid');
  const aside = body.querySelector('.doc-sidebar');
  check('生成 .doc-grid 外壳', !!grid);
  check('article 被搬进网格', article.parentNode === grid);
  check('网格子元素顺序 = 遮罩 / 侧栏 / 正文',
        grid.children[0].className === 'sidebar-backdrop' && grid.children[1].className === 'doc-sidebar' && grid.children[2] === article);
  check('侧栏带 data-syo-scrollspy=100', aside.getAttribute('data-syo-scrollspy') === '100');
  check('有折叠按钮 .sidebar-toggle', !!aside.querySelector('.sidebar-toggle'));
  check('有标题行（图标+文字）', aside.querySelector('.doc-sidebar-title').querySelector('span').textContent === '本节目录');
  const links = aside.querySelectorAll('a');
  check('链接数 = 小节数', links.length === 3, `实际 ${links.length}`);
  check('href 指向小节 id（原 id 保留）', links.map(a => a.href).join() === '#sec-1,#has-id,#sec-3', links.map(a => a.href).join());
  check('顶栏插入了汉堡', !!bar.querySelector('.nav-hamburger') && bar.children[0].className === 'nav-hamburger');
}

// ② 只有一节 / 没有 .lesson：都不生成
{
  const { body } = page([['唯一一节', '']]);
  run(body);
  check('只有一节 → 不生成', !body.querySelector('.doc-sidebar'));
  const bare = el('body');
  run(bare);
  check('没有 .lesson → 不生成', !bare.querySelector('.doc-sidebar'));
}

// ③ 桌面折叠：点一下变 rail 并记忆；再跑一次应恢复折叠
{
  const { body } = page([['A', ''], ['B', '']]);
  const { store } = run(body);
  const aside = body.querySelector('.doc-sidebar');
  aside.querySelector('.sidebar-toggle').fire('click');
  check('点折叠按钮 → 加 .collapsed', aside.classList.contains('collapsed'));
  check('折叠状态已写入 localStorage', store.get('studymate-lesson-toc-collapsed') === '1');
  const second = page([['A', ''], ['B', '']]);
  run(second.body, { store });
  check('重新加载 → 恢复折叠状态', second.body.querySelector('.doc-sidebar').classList.contains('collapsed'));
}

// ④ 移动端：汉堡拉开抽屉 + 遮罩；点遮罩关掉；点链接也关
{
  const { body } = page([['A', ''], ['B', '']]);
  const { window } = run(body, { width: 500 });
  const aside = body.querySelector('.doc-sidebar');
  const backdrop = body.querySelector('.sidebar-backdrop');
  body.querySelector('.nav-hamburger').fire('click');
  check('汉堡 → 抽屉打开 + 遮罩显示', aside.classList.contains('mobile-open') && backdrop.classList.contains('show'));
  check('打开时锁滚动', body.style.overflow === 'hidden');
  backdrop.fire('click');
  check('点遮罩 → 关闭并解锁滚动', !aside.classList.contains('mobile-open') && body.style.overflow === '');
  body.querySelector('.nav-hamburger').fire('click');
  aside.querySelector('a').fire('click');
  check('移动端点链接 → 关闭', !aside.classList.contains('mobile-open'));
  window.resize(1400);
  check('拉宽到桌面 → 不再处于移动打开态', !aside.classList.contains('mobile-open'));
}

// 平板默认折叠，但用户仍可展开；宽度变化不能覆盖已保存的选择。
{
  const { body } = page([['A', ''], ['B', '']]);
  const { window, store } = run(body, { width: 900 });
  const aside = body.querySelector('.doc-sidebar');
  check('平板宽度默认折叠', aside.classList.contains('collapsed'));
  aside.querySelector('.sidebar-toggle').fire('click');
  check('平板点击可展开', !aside.classList.contains('collapsed'));
  window.resize(1400); window.resize(900);
  check('调整宽度保留手动展开状态', !aside.classList.contains('collapsed'));
  const reloaded = page([['A', ''], ['B', '']]);
  run(reloaded.body, { width: 900, store });
  check('平板重新打开保留展开状态', !reloaded.body.querySelector('.doc-sidebar').classList.contains('collapsed'));
}
{
  const { body } = page([['A', ''], ['B', '']]);
  const { window } = run(body);
  const aside = body.querySelector('.doc-sidebar');
  window.resize(900);
  check('没有偏好时缩窄自动折叠', aside.classList.contains('collapsed'));
  window.resize(1400);
  check('没有偏好时拉宽自动展开', !aside.classList.contains('collapsed'));
}

// ⑤ 重复执行不重复建
{
  const { body } = page([['A', ''], ['B', '']]);
  run(body); run(body);
  check('重复执行只建一份侧栏', body.querySelectorAll('.doc-sidebar').length === 1,
        `实际 ${body.querySelectorAll('.doc-sidebar').length}`);
}

// ⑥ loading 态：挂 DOMContentLoaded，不立即建
{
  const { body } = page([['A', ''], ['B', '']]);
  let hooked = false;
  const sandbox = { console, window: { innerWidth: 1400, localStorage: { getItem: () => null, setItem() {} }, addEventListener() {} },
    document: { readyState: 'loading', body,
      querySelector: (s) => body.querySelector(s), querySelectorAll: (s) => body.querySelectorAll(s),
      createElement: (t) => el(t), addEventListener: (t) => { if (t === 'DOMContentLoaded') hooked = true; } } };
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(ASSET, 'utf8'), sandbox);
  check('loading 态 → 挂 DOMContentLoaded 且暂不构建', hooked && !body.querySelector('.doc-sidebar'));
}

console.log(fails === 0 ? '\n全部通过' : `\n${fails} 项失败`);
process.exit(fails === 0 ? 0 : 1);
