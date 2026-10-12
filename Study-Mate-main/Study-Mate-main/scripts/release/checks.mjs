// Script-style Python suites must run directly; unittest discovery misses them.
// Keep CI's functional suites explicit so optional audits do not grow the gate.
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { findPython } from '../../bin/studymate.mjs';

const groups = {
  core: {
    python: [
      'test_attachment_render.py', 'test_dsh_presets.py', 'test_interaction_state.py',
      'test_lesson_figure.py', 'test_lesson_links.py', 'test_lesson_scripts.py',
      'test_naming_nav.py', 'test_pool.py', 'test_quiz_attr.py', 'test_quiz_code.py',
      'test_render_lesson.py', 'test_workspace_config.py',
    ],
    node: ['quiz_dom_test.js', 'toc_dom_test.js'],
    tests: ['scripts/release/release.test.mjs'],
  },
  '--static': {
    python: ['test_python_syntax.py', 'test_skill_rules.py', 'test_templates.py'],
    tests: ['scripts/tests/test_openai_skills.mjs', 'scripts/tests/test_openai_skill_ui.mjs', 'scripts/tests/test_antigravity_skills.mjs'],
  },
  '--browser': {
    node: ['browser/hl_test.mjs', 'browser/quiz_code_test.mjs', 'browser/math_test.mjs'],
  },
};
const mode = process.argv[2] || 'core';
if (process.argv.length > 3 || !Object.hasOwn(groups, mode)) {
  console.error('Usage: node scripts/release/checks.mjs [--static|--browser]');
  process.exit(2);
}

process.chdir(fileURLToPath(new URL('../../', import.meta.url)));
let failed = false;
function run(command, args) {
  console.log(`\n${command} ${args.join(' ')}`);
  const result = spawnSync(command, args, {
    stdio: 'inherit', windowsHide: true,
    env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' },
  });
  if (result.error) console.error(result.error.message);
  failed ||= result.status !== 0;
}
const group = groups[mode];
if (group.python?.length) {
  let python;
  try { python = findPython(); } catch (error) {
    console.error(error.message);
    process.exit(1);
  }
  for (const file of group.python) run(python.command, [...python.prefix, `scripts/tests/${file}`]);
}
for (const file of group.node || []) run(process.execPath, [`scripts/tests/${file}`]);
if (group.tests?.length) run(process.execPath, ['--test', ...group.tests]);
process.exitCode = failed ? 1 : 0;
