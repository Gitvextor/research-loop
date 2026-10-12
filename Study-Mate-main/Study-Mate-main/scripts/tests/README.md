# 回归测试

默认检查与 GitHub Actions 共用一个入口：

```sh
npm test
```

需要 Node.js、Python 3.9+ 和 PyYAML。默认检查只跑 npm 安装、插件打包、课件和工作区功能、DOM 与发布逻辑，不安装真实 DSH、pnpm 或浏览器，不调用模型。Actions 只在 Ubuntu / Node 24 / Python 3.13 上运行一次，不再展开系统和运行时矩阵。

测试使用临时目录，不读写学生的 `workspace/`。Python 会按 `python3`、`python`、Windows 的 `py -3` 顺序查找可用解释器。

## 按需运行

| 命令 | 范围 |
| --- | --- |
| `npm test` | 全部默认功能回归，与 CI 一致 |
| `npm run test:installer` | npm 安装入口、预设与 Bundle |
| `npm run test:openai` | OpenAI 插件 ZIP、完整性、独立运行与导出保护 |
| `npm run test:antigravity` | Antigravity 插件 ZIP、原生 agents、导出保护与重复构建 |
| `npm run test:release` | 版本、changelog、重试和发布保护 |
| `npm run test:static` | Python 语法、提示词与模板文案契约、OpenAI 与 Antigravity skill 转换及 UI 元数据 |
| `npm run test:browser` | 三套真实 Chrome 渲染测试，需要 `google-chrome` |
| `npm run test:dsh` | 真实 DSH 启动与 Web 预设，需要指定 DSH 包目录 |
| `npm run test:dsh-cli` | 真实 DSH CLI 安装、更新、卸载，还需要 `pnpm` |

语法、文案与真实宿主兼容检查保留为本地按需命令，不作为每次提交和发布的默认门禁。改动相应模块时可以单独运行。`scripts/release/checks.mjs` 显式列出默认功能套件，新增测试文件不会自动扩张 Actions 检查范围。

旧入口继续可用：

```sh
bash scripts/tests/run_tests.sh            # 等同 npm test
bash scripts/tests/run_tests.sh --static   # 仅静态检查
bash scripts/tests/run_tests.sh --browser  # 默认功能回归 + 浏览器测试
```

## 默认功能套件

| 套件 | 覆盖行为 |
| --- | --- |
| `test_installer.mjs`、`test_bundle.mjs` | npm 安装、更新与安装模式切换，Bundle 激活和清理，临时工作区数据保留 |
| `test_openai_plugin.mjs` | ZIP 解压后不依赖源码或 DSH 即可初始化工作区、恢复交互和渲染课件；构建可重复，失败时保留已有产物 |
| `test_antigravity_plugin.mjs` | Antigravity 插件包含 5 个原生子代理与 12 个技能、无 0 字节文件、占用的输出目录不被清空、构建可重复 |
| `test_dsh_presets.py` | 预设写入、profile 适配、迁移和重复安装 |
| `test_workspace_config.py`、`test_interaction_state.py` | 工作区来源优先级、旧配置兼容、交互状态与恢复 |
| `test_quiz_attr.py`、`test_quiz_code.py` | 题库属性转义、JSON 与代码围栏处理 |
| `test_lesson_figure.py`、`test_lesson_links.py`、`test_naming_nav.py` | 图片和本地引用可达、课件命名与导航 |
| `test_pool.py`、`test_lesson_scripts.py` | 图片库校验、课件重排、空题理由写入与失败保护 |
| `test_render_lesson.py`、`test_attachment_render.py` | 课件和附件渲染、题库锚点、转义、数学式、输出与检查器对接 |
| `quiz_dom_test.js`、`toc_dom_test.js` | 题目判分、展开、代码和公式展示，侧栏目录与移动端行为 |
| `scripts/release/release.test.mjs` | 版本计算、更新记录、历史 tag、PR 去重、制品校验与重试保护 |

## DSH 实际安装与启动

兼容性改动时，在独立目录安装要检查的 DSH，然后指定其包目录：

```sh
npm install --prefix /tmp/studymate-dsh @deepseek-ai/dsh@0.1.7-alpha.2
export STUDYMATE_DSH_PACKAGE=/tmp/studymate-dsh/node_modules/@deepseek-ai/dsh
npm run test:dsh
npm run test:dsh-cli
```

Windows PowerShell 可用 `$env:STUDYMATE_DSH_PACKAGE = '<独立安装目录>/node_modules/@deepseek-ai/dsh'` 设置包目录。需要 Python 3.9+、PyYAML；CLI 测试另需 `pnpm`。未设置 `STUDYMATE_DSH_PACKAGE` 时跳过，不读取本机默认 DSH 配置。

测试创建临时 HOME、DSH_HOME 和工作区，启动仅监听本机随机端口的 Web，不调用模型。CLI 测试通过临时本地 registry 安装、更新和卸载实际打包的 StudyMate，检查普通模式、学习模式、安装方式切换、缺少 Python 及学习数据保留。

另设 `STUDYMATE_DSH_EXPECTED_VERSION` 可以核对实际宿主版本；设 `STUDYMATE_DSH_DOWNGRADE_PACKAGE` 为旧 DSH 包目录，可以检查旧版安装升级后的显式迁移，以及降级和重新安装恢复。两个 DSH 目录只读。这些兼容场景按需在目标系统和版本上运行，不再由 CI 安装多个宿主版本重复执行。

## 浏览器套件与手动工具

| 文件 | 用途 |
| --- | --- |
| `browser/hl_test.mjs` | 真实 Chrome 代码块高亮、语言识别与已有高亮保留 |
| `browser/quiz_code_test.mjs` | 题目代码块的缩进、等宽字体与高亮 |
| `browser/math_test.mjs` | KaTeX 排版、字体、错误公式与动态题目公式 |
| `browser/measure.mjs` | 对比度、计算样式与 hover 测量 |
| `browser/hovers.mjs` | 批量比较 hover 前后的样式 |
| `browser/shot.mjs` | 浅色/深色截图与元素边界记录 |

后三项是手动工具，不是断言套件；浏览器工具需要提供页面 URL：

```sh
node scripts/tests/browser/measure.mjs <file-url> [--hover ".sel"]
node scripts/tests/browser/shot.mjs <file-url> <out-prefix> <css-selector>
```

## 写新测试

方向探索的验收场景与待验证项见 [学习方向探索验收](../../docs/learning-discovery-validation.md)。这里的规则断言与人工走读均不能代替实际模型对话验证；尤其八问上限、退出后停问、确认前无写入，需要在学习模式中观察对话与工具调用。技能调用面另用 `python3 scripts/check_skill.py .dsh/skills/learning-discovery --expect-model-invocable` 校验。

[learning_discovery_cases.json](fixtures/learning_discovery_cases.json) 提供 12 个合成多轮场景、按问题披露的用户回答与独立评审判据。它是可重复使用的测试数据，**不是通过记录或自动评分器**。真实模型验证按每场景 3 次执行；使用隔离学习目录，保存对话、工具调用和文件变化。不要把 `checks`／`review_only` 作为用户输入发给被测模型，也不要将这些联网、消耗模型额度的运行加入默认快测或发布检查。目标 DSH 版本不同可用界面逐轮执行，无须依赖其内部 API。

`fixtures.py` 负责造一份能过检查的最小科目，测试只注入目标偏差，避免无关错误影响断言。它按真实布局（`<root>/.learning/subjects/<slug>/`）写盘，并铺好共享层与科目组件的占位文件。

```python
import fixtures
subject = fixtures.write_subject(tmp)
path = fixtures.write_lesson(subject, 2, 'first-program',
                             quiz='<div class="quiz" data-quiz=…></div>')
code, out = fixtures.run_gate(path, subject, 'first-program')
```

课件渲染链路使用内容文件、题库、渲染与检查器：

```python
subject = fixtures.write_subject(tmp, name='测试科目')
md = fixtures.write_content(subject, 2, 'first-program',
                            body='## 小节\n\n::: quiz 理解 锚点：本节校验\n:::\n')
fixtures.write_quiz(subject, 2, 'first-program', {
    '本节校验': [{'q': '…', 'answer': '…', 'criteria': '…'}]
})
code, out = fixtures.run_render(subject, 'first-program')
code, out = fixtures.run_gate(fixtures.lesson_html(subject, 2, 'first-program'),
                              subject, 'first-program')
```

默认 fixture 为概念课，不要求 lab；测试实验课时需要自行建立 `lab/` 产物。
