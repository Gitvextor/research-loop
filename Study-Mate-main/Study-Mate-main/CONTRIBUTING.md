# 参与 StudyMate

这是个个人维护的开源项目，欢迎提 issue 和 PR。下面只写这个仓库**特有的**规矩，通用开源礼仪不重复。

## 三条硬规矩

1. **PR 的目标分支只能是 `main`。** 仓库里的 `test` 是遗留分支，落后 `main` 很多；往它上面合并的 PR 不会进主干，也跑不到 CI——PR #10 就这样有 3 个提交至今没合回来。
2. **门禁只有一条：`npm test`。** CI 在 Ubuntu / Node 24 / Python 3.13 上跑的就是它，本地跑通即可，不用模拟其他平台。
3. **合并 PR 不会发布。** 发布由维护者在 Actions 里手动触发；版本号、tag 和 CHANGELOG 都不用你动。

## 改哪块，先读哪份

改之前先读对应那份——它是那块内容唯一的约束来源，别处只给指针。

| 你要改 | 先读 | 改完还要 |
|---|---|---|
| `.dsh/skills/**` 提示词与角色规格 | 该技能自己的 `SKILL.md`；课件规则归 `lesson-design`，题目归 `layered-practice` | `npm run test:static`（逐条核对提示词规则，删掉规则会红） |
| `scripts/*.py` 生成器、渲染器、校验器 | [工程约束](docs/工程约束.md) §三 占位符契约、§四 脚本一览 | `npm test`；动了共享层或模板，按下面「示例是产物」重跑 examples |
| `templates/**` 页面骨架与前端资源 | [工程约束](docs/工程约束.md) §三、§五；[模板说明](templates/README.md) | 同上；新增或改名共享文件要同时改三处清单（§五末条） |
| `schemas/*.json` | 该 schema 本身；[文件归属](docs/文件归属.md) | `npm test` |
| `bin/*.mjs` 安装器与插件构建 | [安装说明](docs/安装.md)；[Codex 与 ChatGPT](docs/Codex与ChatGPT.md) | `npm test` |
| `openai/studymate/**` 插件源 | [Codex 与 ChatGPT](docs/Codex与ChatGPT.md) | `npm run build:plugin`，导入 `dist/studymate-openai.zip` 验证 |
| `docs/**`、`README.md` | 该文件已有的口径；新规则遵循「一处定义，别处只给指针」 | — |

提示词、模板、`schemas/` 和 `scripts/` 里的 Python 会**同时**流进 DSH 预设与 Codex 插件（插件由 `npm run build:plugin` 从这些源转换而来），改完别只验 DSH 一侧。

## 本地怎么验

```bash
npm test              # 与 CI 同一条：安装器、插件打包、课件与工作区功能、DOM、发布逻辑
npm run test:static   # 提示词规则、模板契约、Python 语法、插件技能转换
npm run test:browser  # 三套真实 Chrome 渲染，需要 google-chrome
npm run test:dsh      # 真实 DSH 启动，需要先指定 DSH 包目录
```

需要 Node.js 和 Python 3.9+ / PyYAML。`npm test` 不需要 DSH、浏览器或模型服务，测试自己造临时科目，不碰你的学习工作区。按需命令的完整清单见[测试说明](scripts/tests/README.md)。

单点校验（带行号报错，退出码 1 表示有阻断项）：

```bash
python3 scripts/check_skill.py .dsh/skills/*
python3 scripts/check_curriculum.py examples/.learning/subjects/computer-networks/curriculum.yaml
python3 scripts/check_lesson.py examples/.learning/subjects/linear-algebra/lessons/0001-vector.space.html \
    --subject examples/.learning/subjects/linear-algebra --node vector.space
python3 scripts/check_pool.py <科目目录>
```

`--node` 要用大纲里的节点 id（形如 `vector.space`，带点），不是文件名里的序号。`check_pool.py` 对还没建图片池的科目会报一行「索引不存在」并退出 1——那是图片库还没建，不是命令坏了。

## 提交信息

用 Conventional Commits，描述写中文：

```text
<type>(<scope>): 改了什么
```

- `type` 用 `feat` `fix` `docs` `refactor` `test` `chore` `ci`
- `scope` 用中文模块名，如 `提示词` `渲染器` `检查` `示例` `数学` `CI`，别混英文 scope
- 破坏性改动加 `!`，并在正文写清迁移方式
- 正文说清**为什么**——发布时标题和正文会原样进 CHANGELOG

历史里的好例子：

```text
feat(公式): 课件支持数学排版（$…$ 行内 / $$…$$ 块级，离线 KaTeX）
fix(CI): 修掉 Python 3.12+ 的非法转义警告——它在 3.13 上把一条断言撑破了
refactor(大纲)!: 删掉节点「过关标准」字段，判分锚下移到 objective 与题目判分要点
```

`chore(release): vX.Y.Z` 由发布流程自己生成，不用手写。

## 什么不要提交

- `workspace/`：你自己的学习数据（已 gitignore）
- `dist/`：插件构建产物（已 gitignore）
- `~/.dsh/` 下的安装副本：那是产物，改源不改编产物
- `examples/` 里的 `index.html` 与课件页：它们是生成器写出来的，手改下次重跑就没了

## 示例是产物

`examples/` 是一份 clone 下来就能点开的完整示例工作区，页面全部由引擎生成。改过模板、渲染器、共享资源或科目数据之后，重跑一遍：

```bash
# 根主页 + 两个科目主页
python3 scripts/gen_home.py examples

# 重渲染某一课：科目目录 + 节点 id
python3 scripts/render_lesson.py examples/.learning/subjects/linear-algebra vector.space
```

跑完看 `git status`，只该有你预期的改动。多出别的文件，就说明示例镜像和引擎当前输出已经不一致——这类静默漂移真发生过：`templates/` 加了 KaTeX 字体 LICENSE，示例镜像当时没跟上。

## 发布

维护者手动触发，见[发布流程](docs/releasing.md)。

## License

MIT，见 [LICENSE](LICENSE)。
