import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { getOpenAiSkillDescription, getOpenAiSkillUi } from '../../bin/openai-skill-ui.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const names = fs.readdirSync(path.join(root, '.dsh', 'skills'), { withFileTypes: true })
  .filter(entry => entry.isDirectory()).map(entry => entry.name).sort();

// The generator deliberately emits only this YAML subset: two top-level maps,
// JSON-quoted string scalars, and a plain boolean. Parse values rather than
// asserting string fragments, and reject indentation, type or duplicate errors.
function parseMetadata(yaml) {
  const result = {};
  let section;
  for (const line of yaml.trimEnd().split('\n')) {
    if (!line) continue;
    const map = line.match(/^([a-z_]+):$/);
    if (map) {
      assert.equal(Object.hasOwn(result, map[1]), false, `duplicate map: ${map[1]}`);
      section = result[map[1]] = {};
      continue;
    }
    const scalar = line.match(/^  ([a-z_]+): ("(?:[^"\\]|\\.)*"|true|false)$/);
    assert.ok(section && scalar, `invalid scalar: ${line}`);
    assert.equal(Object.hasOwn(section, scalar[1]), false, `duplicate key: ${scalar[1]}`);
    section[scalar[1]] = JSON.parse(scalar[2]);
  }
  return result;
}

test('all twelve skills expose valid quoted UI fields and no tool dependencies', () => {
  assert.equal(names.length, 12);
  const displays = new Set();
  for (const name of names) {
    const metadata = parseMetadata(getOpenAiSkillUi(name));
    assert.deepEqual(Object.keys(metadata), ['interface', 'policy']);
    assert.deepEqual(Object.keys(metadata.interface), ['display_name', 'short_description', 'default_prompt']);
    assert.deepEqual(Object.keys(metadata.policy), ['allow_implicit_invocation']);
    for (const value of Object.values(metadata.interface)) assert.equal(typeof value, 'string', name);
    const { display_name: display, short_description: short, default_prompt: prompt } = metadata.interface;
    assert.match(display, /[\u4e00-\u9fff]/, name);
    assert.equal(displays.has(display), false, `duplicate display name: ${display}`);
    displays.add(display);
    const count = Array.from(short).length;
    assert.ok(count >= 25 && count <= 64, `${name} short_description has ${count} characters`);
    assert.ok(prompt.includes(`$${name}`), `${name} prompt must invoke its skill explicitly`);
    assert.equal((prompt.match(/\$[a-z]+(?:-[a-z]+)*/g) || []).length, 1, name);
  }
});

test('invocation policy preserves the source role flags and implicit shared protocols', () => {
  const explicitOnly = [];
  for (const name of names) {
    const source = fs.readFileSync(path.join(root, '.dsh', 'skills', name, 'SKILL.md'), 'utf8');
    const header = source.match(/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/)?.[1];
    assert.ok(header, `${name} source frontmatter`);
    const disabled = /^disable-model-invocation:[ \t]*true[ \t]*\r?$/m.test(header);
    if (disabled) explicitOnly.push(name);
    const actual = parseMetadata(getOpenAiSkillUi(name)).policy.allow_implicit_invocation;
    assert.equal(typeof actual, 'boolean');
    assert.equal(actual, !disabled, `${name} invocation policy changed from DSH source`);
  }
  assert.deepEqual(explicitOnly, [
    'curriculum-designer', 'image-scout', 'learning-coach', 'practice-evaluator', 'resource-scout',
  ]);
});

test('discovery text routes learning requests and identifies internal roles clearly', () => {
  const entry = getOpenAiSkillDescription('learning-system', 'old');
  for (const intent of ['新科目', '继续', '切换', '恢复练习', '学习进度']) assert.ok(entry.includes(intent));
  assert.match(entry, /普通编程、修复代码或开发项目请求不自动进入学习流程/);
  assert.match(getOpenAiSkillDescription('practice-evaluator', 'old'), /题目的唯一 owner/);
  for (const name of names.filter(name => name !== 'learning-system')) {
    const description = getOpenAiSkillDescription(name, 'old');
    assert.match(description, /学习总控/, name);
    assert.match(description, /派工|内部规范/, name);
    assert.ok(description.length < 140, `${name} discovery text should remain concise`);
  }
});

test('unknown skills preserve discovery text and require an explicit UI policy decision', () => {
  const original = 'A new role: preserve its full original description.';
  assert.equal(getOpenAiSkillDescription('new-role', original), original);
  assert.equal(getOpenAiSkillDescription('toString', original), original);
  assert.throws(() => getOpenAiSkillUi('new-role'), /Unknown StudyMate skill UI metadata: new-role/);
  assert.throws(() => getOpenAiSkillUi('toString'), /Unknown StudyMate skill UI metadata/);
});
