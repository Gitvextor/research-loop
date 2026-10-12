# 在 Codex 和 ChatGPT Work 中使用 StudyMate

StudyMate 的 OpenAI 版本是一个技能插件：包含总控 `learning-system`、五个角色、五个规范，以及生成 HTML 课件所需的脚本、模板和数据结构。它不依赖 DSH，也不需要单独的 MCP 服务。

插件使用 OpenAI 仍支持的 `.codex-plugin/plugin.json` 兼容结构。宿主提供子代理时可委派角色，否则由同一助手按顺序执行；提问、文件操作与页面展示使用宿主已有工具。原有 `.dsh/skills/` 与 DSH 安装方式保留。

## 1. 下载、导入与更新

1. 打开 [最新 Release](https://github.com/Miaotofu01/Study-Mate/releases/latest)，下载附件 **studymate-openai.zip**。
2. 通过 Codex 客户端提供的插件导入入口安装该 ZIP。
3. 新建任务，选择 StudyMate 的 `learning-system` 技能。

**更新时下载最新版 ZIP，在浏览器中打开已有插件的链接，选择上传新版本，然后新建任务。** 继续使用原学习工作区，课程、进度和记忆会保留。DSH 的 npm 包与此 ZIP 由同一条 Release 流程发布，版本一致。

如果客户端没有 ZIP 导入入口，可把 ZIP 的本地路径交给 `$plugin-creator`，请它导入完整插件；随后在插件目录安装 StudyMate。

## 2. 选择学习工作区并开始

课件生成和完整校验需要 **Python 3.9+、PyYAML、jsonschema**，依赖应安装在宿主实际使用的 Python 环境中：

```bash
python -m pip install pyyaml jsonschema
```

macOS / Linux 若命令为 `python3`，替换上述 `python` 即可。插件安装目录可能位于客户端缓存中；把课件和学习记录放在独立、可写的目录，例如 `D:/StudyMate-workspace` 或 `~/StudyMate-workspace`。

在新任务中选择 StudyMate 的 `learning-system` 技能并发送：

```text
我想用 StudyMate 学线性代数。我学过高中数学，每周有 4 小时。
学习工作区使用 D:/StudyMate-workspace，请先了解我的目标，再设计课程。
```

Codex 可通过 `$` 选择技能，ChatGPT 可通过 `@` 选择；以客户端列表中的实际技能名称为准。后续说「继续上次的科目」「考考我」或「这里没懂」即可。技能调用方式见 [OpenAI：Skills & Plugins](https://learn.chatgpt.com/docs/skills-and-plugins)。

总控会在工作区恢复进度、生成课程大纲和 HTML 课件，主页位于 `<工作区>/index.html`。学习数据应整体保留，包括隐藏的 `.learning/` 目录；插件升级与学习数据分开管理。

### 接入外部学习简报（可选）

如果先用另一个 skill（例如工作区里的 `learning-loop`）做了五视角调研，可将其交接简报交给 StudyMate 总控：

```text
$learning-system 请接入这份外部学习简报：【文件绝对路径】。
学习工作区：【可写的绝对路径】。先恢复已有科目与进度；复用简报中的目标、基础和可靠来源，只补问会影响建课的选择。
```

总控会把简报当作待核对的输入，由 StudyMate 自己建立课程、课件与评估记录。简报中的能力地图或自述水平不会自动变成已掌握状态。外部 skill 未安装时也能用这段入口，前提是已经有可读的交接文件。

脚本也支持以下定位方式，优先级从上到下：

1. 显式工作区参数，例如 `python scripts/gen_home.py "D:/StudyMate-workspace"`。
2. 环境变量 `STUDYMATE_WORKSPACE`。
3. 兼容环境变量 `LEARN_WORKSPACE`。
4. `STUDYMATE_CONFIG` 指向的 YAML 文件中的 `workspace` 字段；未设置时兼容原有 DSH 配置。

配置文件最小内容如下，无需 DSH 的 `root` 字段：

```yaml
workspace: "D:/StudyMate-workspace"
```

环境变量要在执行脚本的宿主进程中可见。在对话中明确工作区路径通常最直接。手动运行生成器前先创建该目录，并从插件根目录执行命令；也可使用脚本的绝对路径。

## 3. Codex 中的连续选择与续学

日常使用只需选择 **StudyMate · 学习总控**。课程设计、讲解、出题等五个角色由总控调度，避免多个角色各自询问同一件事；直接选择某个角色时也会先接回已有学习流程。

- 一次说明的目标、基础、时间和偏好会一并采纳，只补真正缺失的选项，不再从头盘问。
- 支持提问卡片的宿主会优先使用卡片；一次一个决策，收到选择后直接进入下一项或开始执行，不反复问“开始吗”。没有可用卡片工具或当前模式不支持时，使用普通对话，回复选项或自由文字都可以。
- 弹窗仍在等回答时，不会把默认高亮当成已选择，也不会生成依赖该选择的课程。教学题目仍在课件或对话中作答，避免推荐选项透露答案。
- “继续线代”“刚才那个例子没懂”“换成 Python”“今天到这”分别接到续学、局部答疑、科目切换和保存暂停，不重启整套盘问。
- 工作区会保存当前科目、节点、阶段、已回答选择和待问项。应用重开后先核对这些断点及真实课件；课程已有的进度、作品和评估记录继续保留。状态仅记录流程，不能把看过页面或说“懂了”当成掌握证据。

例如：

```text
我想学 Python 做 CSV 报表，零基础，每周 4 小时。
项目和课件形式按你推荐，直接开始第一课。
```

这时总控应直接采用已给的信息，只在确有影响的歧义处询问。卡片能力和异步回传由客户端提供，插件无法保证每个 Codex / ChatGPT 界面都有同样的弹窗。断点保存在学习工作区的 `.learning/interaction.json`，备份工作区时随隐藏目录一起保留。

## 4. ChatGPT Work

ChatGPT Work 使用同一个 ZIP。若账户提供插件导入入口，选择 `studymate-openai.zip` 并安装，再新建 **Work** 对话，选择 `learning-system`。入口是否可用取决于当前产品功能和管理员设置。

StudyMate 的完整工作流需要可执行 Python、读写文件的环境。云端工作区使用该环境内的可写路径；本机 `D:/...` 不会自动同步过去。需要续学时应把学习工作区文件一并带入，并及时导出保存。

## 更新与排查

- **安装后没有技能**：确认安装的是完整插件；重启客户端并新建任务，在技能列表查找 `learning-system`。
- **更新后仍是旧版**：核对已有插件页面中的版本与下载的 Release 一致，再新建任务。
- **提示缺少 yaml / schema 校验被跳过**：在执行脚本的同一 Python 环境安装 `pyyaml` 和 `jsonschema`。
- **提示没有工作区**：给出明确的可写目录，或配置上述环境变量。OpenAI 版本不需要先安装 DSH。
- **宿主没有联网或子代理**：按现有资料与可用工具执行；角色可以顺序完成，缺失的来源、图片或运行验证应如实说明。

日常课程结构与课件写法仍见 [使用说明](使用说明.md) 和 [课件内容格式](课件内容格式.md)；其中 DSH 专属的预设安装部分不适用于本插件。

## 开发者构建

只在修改或调试插件时需要源码构建。在仓库根目录运行：

```bash
npm run build:plugin
```

生成 `dist/studymate/`（完整插件目录）和 `dist/studymate-openai.zip`（分发包），导入生成的 ZIP 即可验证。ZIP 必须包含完整插件；只复制 `skills/` 会缺少脚本和模板。正式分发见 [Release 流程](releasing.md)。
