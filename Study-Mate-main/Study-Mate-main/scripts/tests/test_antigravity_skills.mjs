import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { adaptAntigravitySkill, adaptAntigravityAgent, AGENT_ROLES, AGENT_TOOLS } from '../../bin/antigravity-skill-compat.mjs';
import { AGY_HOST_GUIDE } from '../../bin/antigravity-interaction.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const skillsDir = path.join(root, '.dsh', 'skills');
const skills = fs.readdirSync(skillsDir).filter(name => fs.statSync(path.join(skillsDir, name)).isDirectory()).sort();
const sources = new Map(skills.map(name => [name, fs.readFileSync(path.join(skillsDir, name, 'SKILL.md'), 'utf8')]));
const adapted = new Map(skills.map(name => [name, adaptAntigravitySkill(sources.get(name), name)]));
const agents = new Map(AGENT_ROLES.map(role => [role, adaptAntigravityAgent(sources.get(role), role)]));
// Host-level placeholders an agent cannot resolve on its own must be defined in the host guide.
const HOST_PLACEHOLDERS = ['<root>', '<LEARN_WORKSPACE>', '<SESSION_DIR>', '<STUDYMATE_SCRATCH>'];
const DSH_ONLY = ['~/.dsh/studymate-config.yaml', '<WS>', 'xdg-open', 'disable-model-invocation', 'user-invocable', 'ask_user_question', 'bwrap'];
// Lines containing these get rewritten on purpose, so they cannot act as "text survived" sentinels.
const REWRITTEN = ['/tmp', '<WS>', 'python3', '`cp', '`grep', 'ask_user_question', '`present`', 'xdg-open', '`read`', './run_tests.sh'];

test('teaching text survives export for every skill', () => {
  assert.equal(skills.length, 12);
  for (const [name, content] of adapted) {
    const body = sources.get(name).replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, '');
    const tail = body.split('\n').filter(line => line.trim())
      .reverse().find(line => !REWRITTEN.some(token => line.includes(token)));
    assert.ok(tail && content.includes(tail), `${name}: teaching text at the end of the skill was lost`);
    assert.ok(content.length > body.length, `${name}: exported skill is shorter than its source`);
  }
});

test('exported skills only carry the frontmatter Antigravity understands', () => {
  for (const [name, content] of adapted) {
    const frontmatter = content.match(/^---\n([\s\S]*?)\n---\n/)?.[1];
    assert.ok(frontmatter, `${name}: missing frontmatter`);
    const keys = frontmatter.split('\n').map(line => line.split(':')[0].trim());
    assert.deepEqual(keys, ['name', 'description'], `${name}: unexpected frontmatter keys`);
  }
});

test('no DSH-only fact leaks into the Antigravity skills or agents', () => {
  for (const [name, content] of [...adapted, ...agents]) {
    for (const token of DSH_ONLY) {
      assert.ok(!content.includes(token), `${name}: DSH-only text leaked: ${token}`);
    }
  }
});

test('every host placeholder used in the export is defined in the host guide', () => {
  for (const [name, content] of [...adapted, ...agents]) {
    for (const placeholder of HOST_PLACEHOLDERS) {
      if (!content.includes(placeholder)) continue;
      assert.ok(AGY_HOST_GUIDE.includes(placeholder), `${name}: ${placeholder} is used but never defined`);
    }
  }
});

test('engine scripts are always invoked as python3 -B', () => {
  for (const [name, content] of [...adapted, ...agents]) {
    assert.doesNotMatch(content, /python3\s+(?!-B)/, `${name}: python3 invoked without -B`);
  }
});

test('generated agents declare the host frontmatter and stay complete', () => {
  assert.equal(AGENT_ROLES.length, 5);
  for (const [role, content] of agents) {
    assert.match(content, /^---\nname: [\w-]+\ndescription: ".+"\n/);
    assert.match(content, /^subagent: true$/m);
    assert.match(content, /^mainAgent: false$/m);
    assert.match(content, /^commandExecutionPolicy: auto$/m);
    for (const tool of AGENT_TOOLS[role]) assert.ok(content.includes(`  - ${tool}\n`), `${role}: tool ${tool} missing`);
    assert.ok(content.includes('<subject_path>/.stage/'), `${role}: staging path missing`);
  }
});

test('adaptation fails loudly when a skill anchor drifts', () => {
  assert.throws(
    () => adaptAntigravitySkill(sources.get('learning-system').replace('0. **定位工作区与引擎**', '0. **新的启动结构**'), 'learning-system'),
    /Antigravity skill adaptation error/
  );
  assert.throws(
    () => adaptAntigravitySkill(sources.get('record-keeping').replace('路径以**工作区根 `<WS>`** 为前缀', '路径以工作区根为前缀'), 'record-keeping'),
    /Antigravity skill adaptation error/
  );
  assert.throws(() => adaptAntigravitySkill('没有 frontmatter 的正文', 'learning-system'), /Antigravity skill adaptation error/);
});
