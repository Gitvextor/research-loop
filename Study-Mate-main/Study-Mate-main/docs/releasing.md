# 发布 npm 包和 OpenAI 插件

发布入口是 GitHub Actions 的 **Release**，对应 `.github/workflows/release.yml`。只接受 `Miaotofu01/Study-Mate` 的 `main` 分支，手动选择 `patch`、`minor` 或 `major`。流程不会合并 Pull Request。

一份代码、一个版本、两种分发产物：

| 使用方 | 获取方式 | 发布位置 |
| --- | --- | --- |
| DSH | `npx -y @yunmiao/studymate@latest install` | npm 包 |
| Codex / ChatGPT Work | 下载 `studymate-openai.zip`，通过客户端提供的插件导入入口安装 | 同版本 GitHub Release 附件 |

无需另外申请 npm 包名。ZIP 内的插件 manifest 版本在构建时跟随 `package.json`；不要手动提前递增版本或添加本次正式发布的 changelog，Release 流程会生成它们。

## 首次配置

在 npm 的 [`@yunmiao/studymate` 设置](https://www.npmjs.com/package/@yunmiao/studymate/access)里添加 GitHub Actions Trusted Publisher：

| 字段 | 值 |
| --- | --- |
| Organization or user | `Miaotofu01` |
| Repository | `Study-Mate` |
| Workflow filename | `release.yml` |
| Environment name | `npm` |
| Allowed actions | 允许直接 `npm publish` |

不配置 `NPM_TOKEN` 或 `NODE_AUTH_TOKEN`。发布 job 使用 GitHub 托管 runner、Node 24、npm 11 和 `id-token: write`，由 npm 获取本次任务的短期凭据。`npm whoami` 不能用来判断 OIDC 是否成功，认证发生在 `npm publish` 时。参见 [npm Trusted Publishing](https://docs.npmjs.com/trusted-publishers/)。

GitHub 发布 job 引用 `npm` environment，不要求设置审批人。仓库需要允许 Actions 使用 `GITHUB_TOKEN` 写入版本 commit、tag 和 Release；如果仓库的分支或标签规则禁止该写入，流程会停止，不会绕过保护，也不会使用个人访问令牌。

## 每次发布

1. 将希望发布的修改按正常方式合入 `main`。
2. 打开 **Actions → Release → Run workflow**，分支选择 `main`，选择版本增量。例如 `0.1.1` 选择 `patch` 会得到 `0.1.2`。
3. 等待检查和发布完成。任务摘要会给出 npm 包、GitHub Release 和 OpenAI 插件 ZIP 链接。DSH 用户重跑安装命令；Codex 用户下载 ZIP，在已有插件页面上传新版本。

发布前复用 **Checks**：在单个 Ubuntu runner 上使用 Node 24 / Python 3.13 运行 `npm test`，覆盖安装、OpenAI 插件打包、Python 功能测试、DOM 和发布逻辑。日常提交也使用这套检查，不再自动运行多系统、多版本或真实 DSH 的重复矩阵。当前包无 npm 依赖和 lockfile，因此不运行 `npm ci`。

维护静态约束时可手动运行 `npm run test:static`；需要核对真实 DSH 兼容性时运行 `npm run test:dsh` 或 `npm run test:dsh-cli`。用法见 [测试说明](../scripts/tests/README.md)。

检查通过后，流程读取自上一版本 tag 以来的全部 commit，以及 GitHub 关联到这些 commit、已经合入 `main` 的 PR。提交标题和正文都会原样保留（提交写法见 [参与 StudyMate](../CONTRIBUTING.md)；发布流程只做归类，不校验格式）。现有 `CHANGELOG.md` 内容保留，新条目放在前面。兼容历史 `v0.1` tag；若仓库没有版本 tag，则首次记录完整提交历史。

随后更新 `package.json`（若有 npm lockfile，也同步根版本），原子推送版本 commit 和 `vX.Y.Z` tag。若 `main` 在检查期间发生变化，发布会停止，需要从最新 `main` 重新触发。正式发包前构建并核对同版本 OpenAI ZIP。包内容经过清单与完整性检查后，使用 `npm pack` 的同一个 tarball 发布到官方 npm registry，附带 provenance；确认 registry 的 SHA-512 完整性相同后创建 GitHub Release，并上传 `studymate-openai.zip`。

## 失败后重试

重跑旧任务仍使用当时的 commit，不会包含后来推送的修复。如果检查失败后已修复代码，且本次版本 tag 尚未创建，请在 **Actions → Release → Run workflow** 从最新 `main` 新建一次发布。

如果只是网络等临时故障，代码没有变化，或本次版本 commit/tag 已经推送，在原任务点击 **Re-run failed jobs**。版本 tag 保存了源 commit 和发布信息，流程会继续这个版本；如果 npm 已经发布相同 tarball，则跳过发布并补齐 Release 和 ZIP。已有同名 ZIP 必须通过 SHA-256 内容核对；相同则复用，冲突则停止，不删除或覆盖。若同一 npm 版本内容不同、tag 来源不同、registry 状态不明，流程也会失败并保留现场。

如果 npm 的 `latest` 已经是更高版本，旧任务不会补发较低版本并把 `latest` 降回去。

本次版本 tag 已创建但发布尚未完成时，应重跑原任务，不要新开一次发布。已成功发布且没有新 commit 时，不会空增一个版本。发布流程使用全仓库固定 concurrency group，同一时间只运行一轮发布；GitHub 对等待队列的行为见 [concurrency 文档](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)。

本地可运行 `node --test scripts/release/release.test.mjs` 检查版本计算、历史 tag、更新记录、PR 去重和重试保护。这些测试只在临时目录建立 Git 仓库，不会发布。CI 使用的 action 版本依据官方 [checkout](https://github.com/actions/checkout)、[setup-node](https://github.com/actions/setup-node) 和 [setup-python](https://github.com/actions/setup-python) 文档。
