import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { adaptOpenAiSkill } from '../../bin/openai-skill-compat.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const skillRoot = path.join(root, '.dsh', 'skills');
const skills = fs.readdirSync(skillRoot, { withFileTypes: true })
  .filter(entry => entry.isDirectory()).map(entry => entry.name).sort();
const sources = new Map(skills.map(name => [name,
  fs.readFileSync(path.join(skillRoot, name, 'SKILL.md'), 'utf8')]));
const adapted = new Map(skills.map(name => [name, adaptOpenAiSkill(sources.get(name), name)]));

test('all bundled skills export only portable metadata and no DSH tool requirements', () => {
  assert.equal(skills.length, 12);
  for (const [name, content] of adapted) {
    const frontmatter = content.match(/^---\n([\s\S]*?)\n---\n/);
    assert.ok(frontmatter, name);
    assert.deepEqual(frontmatter[1].split('\n').map(line => line.split(':')[0]),
      ['name', 'description'], name);
    assert.ok(frontmatter[1].startsWith(`name: ${name}\n`));
    assert.ok(JSON.parse(frontmatter[1].split('\n')[1].slice('description: '.length)));
    for (const stale of [
      /~\/\.dsh/, /\.dsh\/skills/, /install\.sh/, /\/tmp(?:\/|`)/,
      /`(?:skill|subagent|subagent_fork|present|ask_user_question|read)`/,
      /md5sum/, /xdg-open/, /`cp(?: -r)?`/, /`grep`/,
      /python3 <root>/, /disable-model-invocation/, /user-invocable/,
      /\x00/,
    ]) assert.doesNotMatch(content, stale, `${name}: ${stale}`);
    assert.match(content, /<root>\/skills\/<技能名>\/SKILL\.md/, name);
    assert.match(content, /没有委派工具时.*串行执行/, name);
    assert.match(content, /ChatGPT Work.*临时沙箱/, name);
    assert.match(content, /环境变量、工作目录与 shell 状态不保证跨工具调用保留/, name);
  }
});

test('bootstrap initializes a separate workspace without requiring legacy config', () => {
  const controller = adapted.get('learning-system');
  assert.match(controller, /用户本次明确指定的目录 → 非空环境变量 `STUDYMATE_WORKSPACE` → 非空 `LEARN_WORKSPACE` → 用户显式设置的 `STUDYMATE_CONFIG`/);
  assert.match(controller, /只有用户明确要求复用旧 DSH 工作区时才读取其指定的旧配置/);
  assert.match(controller, /没有 DSH 配置不影响启动/);
  assert.match(controller, /仅在缺失时从 `<root>\/templates\/MEMORY\.md` 复制为 `\.learning\/MEMORY\.md`/);
  assert.match(controller, /插件根目录只读/);
  assert.match(controller, /完整 `\.learning\/`（含隐藏目录）的可下载归档/);
  assert.doesNotMatch(adapted.get('record-keeping'), /开场从.*config\.yaml/);
});

test('renderer commands quote paths and always give gen_home an explicit workspace', () => {
  let homeCalls = 0;
  for (const [name, content] of adapted) {
    // `-B` 之类的标志可出现在 `-X utf8` 之后（源技能要求跑引擎脚本一律加 `-B`），
    // 所以这里不能假定 `utf8` 后面紧跟脚本路径的引号。
    for (const match of content.matchAll(/`(<python> -X utf8(?: -[A-Za-z]+)* '[^`]+)`/g)) {
      const command = match[1];
      if (command.includes('/gen_home.py')) {
        homeCalls += 1;
        assert.match(command, /gen_home\.py' '<LEARN_WORKSPACE>'$/, name);
      }
      assert.doesNotMatch(command, /(?<!')<(?:subject_path|节点id|页面路径|curriculum\.yaml|tsv)>/, name);
    }
  }
  // 每个出现的 gen_home 调用都已在上面断言过「必须带显式工作区」；这里只钉住
  // 「学习系统总控 + 档案维护」两处主场，暂存模式的收尾会再引一次（当前共 3 处）。
  assert.ok(homeCalls >= 2, `gen_home 调用偏少：${homeCalls}`);
  assert.match(adapted.get('learning-system'), /hashlib\.md5\(pathlib\.Path\(sys\.argv\[1\]\)\.read_bytes\(\)\)/);
  assert.match(adapted.get('learning-system'), /practice-evaluator-<节点id>\/deliver\/.*目录内容原样合并复制/);
});

test('teaching contracts and role ownership survive export', () => {
  for (const name of ['evidence-check', 'lesson-design', 'local-qa']) {
    const originalBody = sources.get(name).replaceAll('\r\n', '\n')
      .replace(/^---\n[\s\S]*?\n---\n/, '').trim();
    assert.ok(adapted.get(name).endsWith(`${originalBody}\n`), `${name} teaching text changed`);
  }
  for (const [name, terms] of [
    ['learning-coach', ['你只写内容、留题目位置', '尤其别补 `empty_reason`', '**内容文件里只有内容格式。**']],
    ['practice-evaluator', ['全系统的题都由你出', '作答原文', '题目的唯一 owner']],
    ['learning-system', ['锚点是讲解的产物', '题面与答案一个字都不改', '同一科目同时只有一个写入者']],
    ['record-keeping', ['建课时的初始快照', '已通过项目验证', '写一条当且仅当出现可观察的证据']],
    ['layered-practice', ['参考解必须自包含', '只有 `::: quiz` 的层级是元信息', '每条结论必须指向一条具体证据']],
  ]) {
    for (const term of terms) assert.ok(adapted.get(name).includes(term), `${name}: ${term}`);
  }
  // Export must never mutate the DSH source files or depend on their line endings.
  for (const [name, source] of sources) {
    assert.equal(fs.readFileSync(path.join(skillRoot, name, 'SKILL.md'), 'utf8'), source);
    assert.equal(adaptOpenAiSkill(source.replaceAll('\r\n', '\n'), name), adapted.get(name));
  }
});

test('invalid metadata and changed bootstrap fail instead of shipping stale instructions', () => {
  assert.throws(() => adaptOpenAiSkill('body', 'learning-system'), /frontmatter/);
  assert.throws(() => adaptOpenAiSkill(sources.get('local-qa'), '../local-qa'), /directory name/);
  assert.throws(() => adaptOpenAiSkill(sources.get('local-qa'), 'another-name'), /metadata/);
  assert.throws(() => adaptOpenAiSkill(sources.get('learning-system')
    .replace('0. **定位工作区与引擎**', '0. **新的启动结构**'), 'learning-system'), /adaptation needs updating/);
});
