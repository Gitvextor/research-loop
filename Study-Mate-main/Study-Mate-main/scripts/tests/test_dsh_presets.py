"""DSH preset migration tests; every installation uses an isolated temporary home."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / 'scripts' / 'install_preset.py'
PLUGIN = '@deepseek-ai/dsh-agent-preset'
BEGIN = '# BEGIN STUDYMATE LEARNING PRESET'
BUNDLE = '@yunmiao/studymate'


def rows(value):
    if isinstance(value, list):
        for item in value:
            yield from rows(item)
    elif isinstance(value, dict):
        yield value
        for item in value.values():
            yield from rows(item)


class CordisLoader(yaml.SafeLoader):
    pass


CordisLoader.add_constructor('tag:yaml.org,2002:js', lambda loader, node: loader.construct_scalar(node))


class PresetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='studymate-preset-test-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "dsh O'Brien 中文"
        self.preset = self.home / 'staged-learning'
        self.target = self.home / '.agent-presets' / 'learning'
        shutil.copytree(ROOT / 'preset' / 'learning', self.preset)
        self.patch = self.home / 'profiles' / 'web' / 'cordis.patch.yml'
        self.patch.parent.mkdir(parents=True)

    def invoke(self, version='0.1.7-alpha.1', extra=(), success=True, env=None):
        args = [sys.executable, str(HELPER), '--preset-dir', str(self.preset),
                '--preset-target', str(self.target), '--dsh-home', str(self.home)]
        if version is not None:
            args += ['--dsh-version', version]
        result = subprocess.run(args + list(extra), capture_output=True, text=True,
                                encoding='utf-8', env={**os.environ, 'PYTHONUTF8': '1',
                                                     'PYTHONIOENCODING': 'utf-8', **(env or {})})
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        return result.stderr

    def parsed(self, path=None):
        return yaml.load((path or self.patch).read_text(encoding='utf-8'), Loader=CordisLoader)

    def test_version_boundaries_are_independent(self):
        cases = [('0.1.5-rc.2', 'worker-thread', 'legacy'),
                 ('0.1.6-alpha.0', 'worker-thread', 'legacy'),
                 ('0.1.6-alpha.1', 'ptc', 'legacy'),
                 ('0.1.6-alpha.2', 'ptc', 'legacy'),
                 ('0.1.7-alpha.0', 'ptc', 'legacy'),
                 ('0.1.7-alpha.1', 'ptc', 'declarative'),
                 ('0.1.7', 'ptc', 'declarative')]
        for version, workflow, mode in cases:
            with self.subTest(version=version):
                result = self.invoke(version)
                self.assertEqual(result['mode'], mode)
                self.assertIn(f"name: '@deepseek-ai/dsh-workflow-{workflow}'",
                              (self.preset / 'agent.cordis.yml').read_text(encoding='utf-8'))
        result = self.invoke('0.1.5-rc.2')
        self.assertEqual(result['mode'], 'legacy')
        self.assertNotIn(BEGIN, self.patch.read_text(encoding='utf-8'))

    def test_existing_patch_shapes_are_preserved_and_idempotent(self):
        cases = ['', '[]\n', '[# empty comment\n]\n',
                 '[{id: unrelated}]\n', '[{id: unrelated}, # trailing comment\n]\n',
                 '# retained\n- id: unrelated\n  disabled: !!js process.platform === \'win32\'\n',
                 '\ufeff# retained\r\n[{id: unrelated, disabled: !!js "process.platform === \'win32\'"}]\r\n',
                 '---\n- id: unrelated\n...\n']
        for original in cases:
            with self.subTest(patch=original):
                self.patch.write_bytes(original.encode('utf-8'))
                expected = yaml.load(original, Loader=CordisLoader) or []
                self.assertTrue(self.invoke()['patchChanged'])
                first = self.patch.read_bytes()
                self.assertEqual(self.parsed()[:-1], expected)
                if '!!js' in original:
                    self.assertIn(b'!!js', first)
                if '\r\n' in original:
                    self.assertIn(b'# retained\r\n', first)
                self.assertFalse(self.invoke()['patchChanged'])
                self.assertEqual(self.patch.read_bytes(), first)
                self.invoke('0.1.5-rc.2')
                self.assertEqual(self.parsed() or [], expected)
                self.assertNotIn(BEGIN, self.patch.read_text(encoding='utf-8'))

    def test_staging_keeps_active_patch_and_embeds_live_plugin_definitions(self):
        original = b'# user patch\n[]\n'
        self.patch.write_bytes(original)
        output = self.home / 'staged.patch.yml'
        result = self.invoke(extra=['--patch-output', str(output)])
        self.assertEqual(result['patchPath'], str(output))
        self.assertEqual(self.patch.read_bytes(), original)
        registration = self.parsed(output)[-1]['insert'][0]
        self.assertEqual(registration['name'], PLUGIN)
        self.assertEqual(registration['config']['id'], 'learning')
        plugins = registration['config']['plugins']
        self.assertEqual(plugins[0]['name'], '@deepseek-ai/dsh-persona')
        self.assertNotIn('cordis:include', [row['name'] for row in plugins])
        bash = next(row for row in plugins if row['id'] == 'tool-bash')
        self.assertEqual(bash['disabled'], {'__jsExpr': "process.platform === 'win32'"})
        delegation = next(row for row in plugins if row['id'] == 'delegation')
        self.assertTrue(any(row['name'] == '@deepseek-ai/dsh-workflow-ptc'
                            for row in delegation['config']))

    def test_manual_learning_declaration_is_not_overwritten(self):
        original = (f'- insert:\n  - id: user-learning\n    name: "{PLUGIN}"\n'
                    '    config: {id: learning, name: Custom, plugins: []}\n')
        self.patch.write_text(original, encoding='utf-8')
        before = (self.preset / 'agent.cordis.yml').read_bytes()
        self.assertIn('learning', self.invoke(success=False))
        self.assertEqual(self.patch.read_text(encoding='utf-8'), original)
        self.assertEqual((self.preset / 'agent.cordis.yml').read_bytes(), before)

    def test_invalid_or_conflicting_patches_fail_without_writes(self):
        declaration = f'- name: "{PLUGIN}"\n  config: {{id: learning, plugins: []}}\n'
        duplicate = declaration.replace('- name:', '- id: first\n  name:')
        cases = ['{}\n', 'null\n', '[]\n---\n[]\n', BEGIN + '\n- id: incomplete\n',
                 declaration, duplicate + duplicate.replace('first', 'second'),
                 '- id: studymate-learning-preset\n  name: user-plugin\n']
        for content in cases:
            with self.subTest(patch=content):
                self.patch.write_text(content, encoding='utf-8')
                before = (self.preset / 'agent.cordis.yml').read_bytes()
                self.invoke(success=False)
                self.assertEqual(self.patch.read_text(encoding='utf-8'), content)
                self.assertEqual((self.preset / 'agent.cordis.yml').read_bytes(), before)
        self.patch.write_text('[]\n', encoding='utf-8')
        (self.home / 'cordis.patch.yml').write_text(duplicate, encoding='utf-8')
        self.assertIn('全局声明', self.invoke(success=False))
        self.assertEqual(self.patch.read_text(encoding='utf-8'), '[]\n')

    def test_profile_names_cannot_escape_or_target_reserved_locations(self):
        for profile in ['../web', 'a/b', 'a\\b', '.', '..', '', 'node_modules', 'desktop']:
            with self.subTest(profile=profile):
                self.assertIn('--profile', self.invoke(extra=['--profile', profile], success=False))
                self.assertFalse(self.patch.exists())
        custom = 'study.local 中文'
        self.invoke(extra=['--profile', custom])
        self.assertTrue((self.home / 'profiles' / custom / 'cordis.patch.yml').exists())
        self.assertFalse(self.patch.exists())

    def test_source_install_without_dsh_retains_legacy_setup(self):
        result = self.invoke(version=None, env={'PATH': str(self.home / 'no-programs')})
        self.assertEqual(result['mode'], 'legacy')
        self.assertFalse(result['patchChanged'])
        self.assertFalse(self.patch.exists())

    def test_bundle_reads_definition_without_dsh_or_profile_writes(self):
        result = self.invoke(version=None, extra=['--bundle'],
                             env={'PATH': str(self.home / 'no-programs')})
        self.assertEqual(result['mode'], 'bundle')
        self.assertFalse(result['patchChanged'])
        self.assertFalse(self.patch.exists())
        config = result['config']
        self.assertEqual(config['id'], 'learning')
        self.assertEqual(config['name'], '学习模式')
        bash = next(row for row in config['plugins'] if row['id'] == 'tool-bash')
        self.assertEqual(bash['disabled'], {'__jsExpr': "process.platform === 'win32'"})
        delegation = next(row for row in config['plugins'] if row['id'] == 'delegation')
        self.assertTrue(any(row['name'] == '@deepseek-ai/dsh-workflow-ptc'
                            for row in delegation['config']))

    def test_bundle_startup_refuses_implicit_migration_without_writes(self):
        self.patch.write_bytes(b'# retained\n[]\n')
        self.invoke()
        registered = self.patch.read_bytes()
        before = (self.preset / 'agent.cordis.yml').read_bytes()
        output = self.home / 'bundle.patch.yml'
        error = self.invoke(extra=['--bundle', '--patch-output', str(output)], success=False)
        self.assertIn('--mode native', error)
        self.assertEqual(self.patch.read_bytes(), registered)
        self.assertEqual((self.preset / 'agent.cordis.yml').read_bytes(), before)
        self.assertFalse(output.exists())

    def test_explicit_native_switch_removes_only_the_managed_block(self):
        manifest = self.patch.parent / 'package.json'
        manifest_text = json.dumps({'dsh': {'profile': {'bundles': [BUNDLE]}}})
        manifest.write_text(manifest_text, encoding='utf-8')
        for original in ['# retained\n[]\n',
                         '\ufeff# retained\r\n[{id: other, disabled: !!js "false"}]\r\n',
                         '# retained\n- id: other\n  disabled: !!js false\n']:
            with self.subTest(patch=original):
                self.patch.write_bytes(original.encode('utf-8'))
                self.invoke()
                registered = self.patch.read_bytes()
                output = self.home / 'native.patch.yml'
                result = self.invoke(extra=['--mode', 'native', '--patch-output', str(output)])
                self.assertEqual(result['mode'], 'bundle')
                self.assertTrue(result['patchChanged'])
                self.assertEqual(self.patch.read_bytes(), registered)
                expected = yaml.load(original, Loader=CordisLoader) or []
                self.assertEqual(self.parsed(output) or [], expected)
                self.assertNotIn(BEGIN, output.read_text(encoding='utf-8'))
                self.assertIn(b'# retained', output.read_bytes())
                if '\r\n' in original:
                    self.assertIn(b'# retained\r\n', output.read_bytes())
                if '!!js' in original:
                    self.assertIn(b'!!js', output.read_bytes())
                self.patch.write_bytes(output.read_bytes())
                before = self.patch.read_bytes()
                self.assertFalse(self.invoke(extra=['--mode', 'native'])['patchChanged'])
                self.assertEqual(self.patch.read_bytes(), before)
                self.assertFalse(self.invoke(extra=['--bundle'])['patchChanged'])
                self.assertEqual(self.patch.read_bytes(), before)
                self.assertEqual(manifest.read_text(encoding='utf-8'), manifest_text)

    def test_native_handoff_keeps_empty_or_comment_only_patch_a_valid_list(self):
        manifest = self.patch.parent / 'package.json'
        manifest.write_text(json.dumps({'dsh': {'profile': {'bundles': [BUNDLE]}}}), encoding='utf-8')
        for original in ['', '# keep this comment\n', '\ufeff# keep this comment\r\n', '---\n[]\n...\n']:
            with self.subTest(patch=original):
                self.patch.write_bytes(original.encode('utf-8'))
                self.invoke()
                self.invoke(extra=['--mode', 'native'])
                self.assertEqual(self.parsed(), [])
                self.assertIsInstance(yaml.compose(self.patch.read_text(encoding='utf-8')), yaml.SequenceNode)
                if '# keep this comment' in original:
                    self.assertIn('# keep this comment', self.patch.read_text(encoding='utf-8'))
                self.assertNotIn(BEGIN, self.patch.read_text(encoding='utf-8'))

    def test_default_cli_keeps_ownership_when_a_bundle_is_selected(self):
        manifest = self.patch.parent / 'package.json'
        original = '# keep\n- id: unrelated\n  disabled: true\n'
        manifest_text = json.dumps({'dsh': {'profile': {'bundles': [
            '@deepseek-ai/dsh-base', BUNDLE]}}})
        manifest.write_text(manifest_text, encoding='utf-8')
        for version, mode in [('0.1.7-alpha.1', 'declarative'), ('0.1.5-rc.2', 'legacy')]:
            with self.subTest(version=version):
                self.patch.write_text(original, encoding='utf-8')
                result = self.invoke(version)
                self.assertEqual(result['mode'], mode)
                self.assertIn(BEGIN, self.patch.read_text(encoding='utf-8'))
                data = list(rows(self.parsed()))
                guards = [row for row in data if row.get('id') == 'studymate']
                self.assertEqual(guards, [{'id': 'studymate', 'name': BUNDLE, 'disabled': True}])
                learning = [row for row in data if row.get('name') == PLUGIN]
                self.assertEqual(len(learning), 1 if mode == 'declarative' else 0)
                self.assertEqual(self.parsed()[0], yaml.safe_load(original)[0])
                self.assertNotIn('config', result)
                self.assertFalse(self.invoke(version)['patchChanged'])
                self.assertEqual(manifest.read_text(encoding='utf-8'), manifest_text)
        # Merely installing a dependency does not enable its bundle.
        manifest.write_text(json.dumps({'dependencies': {BUNDLE: '*'},
                                        'dsh': {'profile': {'bundles': []}}}), encoding='utf-8')
        self.assertEqual(self.invoke()['mode'], 'declarative')
        self.assertFalse(any(row.get('id') == 'studymate' for row in rows(self.parsed())))
        self.assertEqual(self.invoke('0.1.5-rc.2')['mode'], 'legacy')
        self.assertNotIn(BEGIN, self.patch.read_text(encoding='utf-8'))

    def test_native_switch_requires_supported_host_and_selected_bundle(self):
        self.invoke()
        before = self.patch.read_bytes()
        self.assertIn(BUNDLE, self.invoke(extra=['--mode', 'native'], success=False))
        self.assertEqual(self.patch.read_bytes(), before)
        manifest = self.patch.parent / 'package.json'
        manifest.write_text(json.dumps({'dsh': {'profile': {'bundles': [BUNDLE]}}}), encoding='utf-8')
        for version in ['0.1.5-rc.2', '0.1.6-alpha.1', '0.1.6-alpha.2', '0.1.7-alpha.0']:
            with self.subTest(version=version):
                self.assertIn('0.1.7-alpha.1', self.invoke(version, extra=['--mode', 'native'], success=False))
                self.assertEqual(self.patch.read_bytes(), before)
        self.invoke(extra=['--bundle', '--mode', 'native'], success=False)
        self.assertEqual(self.patch.read_bytes(), before)

    def test_native_switch_respects_manual_disable_in_profile_or_home_patch(self):
        manifest = self.patch.parent / 'package.json'
        manifest.write_text(json.dumps({'dsh': {'profile': {'bundles': [BUNDLE]}}}), encoding='utf-8')
        home_patch = self.home / 'cordis.patch.yml'
        for location in [self.patch, home_patch]:
            for disabled in ['true', '!!js process.platform === \'win32\'']:
                with self.subTest(location=location, disabled=disabled):
                    self.patch.write_text('[]\n', encoding='utf-8')
                    home_patch.write_text('[]\n', encoding='utf-8')
                    manual = f'- id: studymate\n  disabled: {disabled}\n'
                    location.write_text(manual, encoding='utf-8')
                    self.invoke(extra=['--mode', 'native'], success=False)
                    self.assertEqual(location.read_text(encoding='utf-8'), manual)

    def test_studymate_group_entries_are_not_treated_as_disablable_plugins(self):
        manifest = self.patch.parent / 'package.json'
        manifest.write_text(json.dumps({'dsh': {'profile': {'bundles': [BUNDLE]}}}), encoding='utf-8')
        home_patch = self.home / 'cordis.patch.yml'
        for location in [self.patch, home_patch]:
            for options in [[], ['--mode', 'native'], ['--bundle']]:
                with self.subTest(location=location, options=options):
                    self.patch.write_text('[]\n', encoding='utf-8')
                    home_patch.write_text('[]\n', encoding='utf-8')
                    manual = '- id: studymate\n  group: true\n  config: []\n'
                    location.write_text(manual, encoding='utf-8')
                    before = (self.preset / 'agent.cordis.yml').read_bytes()
                    output = self.home / 'blocked-group.patch.yml'
                    self.invoke(extra=[*options, '--patch-output', str(output)], success=False)
                    self.assertEqual(location.read_text(encoding='utf-8'), manual)
                    self.assertEqual((self.preset / 'agent.cordis.yml').read_bytes(), before)
                    self.assertFalse(output.exists())

    def test_declarative_guard_disables_missing_packages_before_import(self):
        self.invoke()
        registration = next(row for row in rows(self.parsed()) if row.get('name') == PLUGIN)
        expression = registration['disabled']['__jsExpr']
        script = r'''const assert = require('node:assert/strict');
const expression = JSON.parse(process.argv[1]);
const evaluate = ctx => new Function('ctx', 'return (' + expression + ');')(ctx);
assert.equal(evaluate({}), true);
assert.equal(evaluate({get: () => undefined}), true);
assert.equal(evaluate({get: () => ({packageOf: () => undefined})}), true);
assert.equal(evaluate({get: () => ({packageOf: () => {throw new Error('missing package');}})}), true);
const baseUrl = 'file:///dsh/profiles/web/';
assert.equal(evaluate({baseUrl, get: name => {
  assert.equal(name, 'pluginPackages');
  return {packageOf: (name, base) => {
    assert.equal(name, '@deepseek-ai/dsh-agent-preset');
    assert.equal(base, baseUrl);
    return {name};
  }};
}}), false);'''
        result = subprocess.run(['node', '-e', script, json.dumps(expression)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_bundle_refuses_manual_declarations_without_writes(self):
        declaration = (f'- insert:\n  - id: user-learning\n    name: "{PLUGIN}"\n'
                       '    config: {id: learning, name: Custom, plugins: []}\n')
        for global_patch in [False, True]:
            for native in [False, True]:
                with self.subTest(global_patch=global_patch, native=native):
                    self.patch.write_text('[]\n', encoding='utf-8')
                    home_patch = self.home / 'cordis.patch.yml'
                    home_patch.write_text('[]\n', encoding='utf-8')
                    conflict = home_patch if global_patch else self.patch
                    conflict.write_text(declaration, encoding='utf-8')
                    (self.patch.parent / 'package.json').write_text(json.dumps({
                        'dsh': {'profile': {'bundles': ['@yunmiao/studymate']}}}), encoding='utf-8')
                    before = (self.preset / 'agent.cordis.yml').read_bytes()
                    output = self.home / 'blocked.patch.yml'
                    error = self.invoke(extra=(["--bundle"] if native else []) +
                                        ['--patch-output', str(output)], success=False)
                    self.assertIn('learning', error)
                    self.assertEqual(conflict.read_text(encoding='utf-8'), declaration)
                    self.assertEqual((self.preset / 'agent.cordis.yml').read_bytes(), before)
                    self.assertFalse(output.exists())

    def test_invalid_bundle_manifest_or_patch_fails_without_writes(self):
        manifest = self.patch.parent / 'package.json'
        self.patch.write_text('[]\n', encoding='utf-8')
        for value in ['{broken', '[]', '{"dsh": null}',
                      '{"dsh":{"profile":{"bundles":"@yunmiao/studymate"}}}',
                      '{"dsh":{"profile":{"bundles":[null]}}}']:
            with self.subTest(manifest=value):
                manifest.write_text(value, encoding='utf-8')
                before = (self.preset / 'agent.cordis.yml').read_bytes()
                self.assertIn('package.json', self.invoke(success=False))
                self.assertEqual(self.patch.read_text(encoding='utf-8'), '[]\n')
                self.assertEqual((self.preset / 'agent.cordis.yml').read_bytes(), before)
        manifest.unlink()
        self.patch.write_text(BEGIN + '\n- id: incomplete\n', encoding='utf-8')
        self.assertIn('标记', self.invoke(extra=['--bundle'], success=False))


if __name__ == '__main__':
    unittest.main()
