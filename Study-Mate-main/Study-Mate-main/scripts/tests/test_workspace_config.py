#!/usr/bin/env python3
"""宿主无关的工作区选择与旧 DSH 配置兼容；所有读写均使用临时目录。"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import gen_home


class WorkspaceConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='studymate-runtime-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / 'home'
        self.home.mkdir()
        self.env = dict(os.environ)
        for name in ('STUDYMATE_WORKSPACE', 'LEARN_WORKSPACE', 'STUDYMATE_CONFIG', 'DSH_HOME'):
            self.env.pop(name, None)
        self.env.update(HOME=str(self.home), USERPROFILE=str(self.home), PYTHONUTF8='1')
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, self.env, clear=True).start()

    def config(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding='utf-8')
        return path

    def test_default_dsh_config_is_supported(self):
        workspace = self.base / 'existing learning'
        self.config(self.home / '.dsh' / 'studymate-config.yaml', {'workspace': str(workspace)})
        self.assertEqual(gen_home.learn_workspace(), str(workspace))

    def test_custom_dsh_home_is_supported(self):
        dsh_home = self.base / 'dsh custom'
        os.environ['DSH_HOME'] = str(dsh_home)
        workspace = self.base / 'old workspace'
        self.config(dsh_home / 'studymate-config.yaml', {'workspace': str(workspace)})
        self.assertEqual(gen_home.learn_workspace(), str(workspace))

    def test_explicit_workspace_bypasses_invalid_config_and_legacy_variable(self):
        workspace = self.base / "work [1] O'Brien # 中文"
        os.environ.update(STUDYMATE_WORKSPACE=str(workspace), LEARN_WORKSPACE='ignored',
                          STUDYMATE_CONFIG=str(self.base / 'missing.yaml'))
        self.assertEqual(gen_home.learn_workspace(), str(workspace))

    def test_legacy_workspace_variable_bypasses_config(self):
        workspace = self.base / 'legacy override'
        os.environ.update(LEARN_WORKSPACE=str(workspace),
                          STUDYMATE_CONFIG=str(self.base / 'missing.yaml'))
        self.assertEqual(gen_home.learn_workspace(), str(workspace))

    def test_config_override_precedes_dsh_config(self):
        self.config(self.home / '.dsh' / 'studymate-config.yaml', {'workspace': 'ignored'})
        config = self.config(self.base / 'portable.yaml', {'workspace': str(self.base / 'portable')})
        os.environ['STUDYMATE_CONFIG'] = str(config)
        self.assertEqual(gen_home.learn_workspace(), str(self.base / 'portable'))

    def test_missing_explicit_config_does_not_fall_back_to_dsh(self):
        self.config(self.home / '.dsh' / 'studymate-config.yaml', {'workspace': 'ignored'})
        os.environ['STUDYMATE_CONFIG'] = str(self.base / 'missing.yaml')
        with self.assertRaisesRegex(SystemExit, 'missing.yaml'):
            gen_home.learn_workspace()

    def test_tilde_and_relative_paths_are_normalized(self):
        os.environ['STUDYMATE_WORKSPACE'] = '~/learning'
        self.assertEqual(gen_home.learn_workspace(), str(self.home / 'learning'))
        os.environ['STUDYMATE_WORKSPACE'] = 'relative workspace'
        self.assertEqual(gen_home.learn_workspace(), os.path.abspath('relative workspace'))
        del os.environ['STUDYMATE_WORKSPACE']
        self.config(self.home / '.dsh' / 'studymate-config.yaml', {'workspace': '~/learning'})
        self.assertEqual(gen_home.learn_workspace(), str(self.home / 'learning'))

    def test_invalid_config_reports_actionable_errors(self):
        config = self.base / 'invalid.yaml'
        os.environ['STUDYMATE_CONFIG'] = str(config)
        for data in (None, [], {'workspace': []}, {'workspace': 123}, {}, {'workspace': ' '}):
            with self.subTest(data=data):
                self.config(config, data)
                with self.assertRaisesRegex(SystemExit, 'workspace'):
                    gen_home.learn_workspace()
        config.write_text('workspace: [', encoding='utf-8')
        with self.assertRaisesRegex(SystemExit, '无法读取工作区配置'):
            gen_home.learn_workspace()

    def test_missing_config_does_not_create_a_dsh_installation(self):
        with self.assertRaisesRegex(SystemExit, 'STUDYMATE_WORKSPACE'):
            gen_home.learn_workspace()
        self.assertFalse((self.home / '.dsh').exists())

    def run_generator(self, *args, **env):
        return subprocess.run(
            [sys.executable, str(ROOT / 'scripts' / 'gen_home.py'), *map(str, args)],
            cwd=self.base, env=dict(self.env, **env), text=True, encoding='utf-8',
            capture_output=True, timeout=30,
        )

    def test_generates_without_dsh_using_workspace_variable(self):
        workspace = self.base / "learning 中文 [1] O'Brien"
        workspace.mkdir()
        result = self.run_generator(STUDYMATE_WORKSPACE=str(workspace))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((workspace / 'index.html').is_file())
        self.assertTrue((workspace / '.learning' / 'assets' / 'learn-theme.css').is_file())
        self.assertFalse((self.home / '.dsh').exists())

    def test_positional_workspace_precedes_every_environment_override(self):
        workspace = self.base / 'positional'
        workspace.mkdir()
        result = self.run_generator(
            workspace, STUDYMATE_WORKSPACE=str(self.base / 'unused'),
            LEARN_WORKSPACE=str(self.base / 'also-unused'),
            STUDYMATE_CONFIG=str(self.base / 'missing.yaml'),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((workspace / 'index.html').is_file())
        self.assertFalse((self.base / 'unused').exists())


if __name__ == '__main__':
    unittest.main()
