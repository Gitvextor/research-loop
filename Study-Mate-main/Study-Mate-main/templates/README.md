# templates/ — 模板（生成器的输入，不是能直接打开的页面）

## ⚠️ 先看这条

`home-index.html`、`subject-index.html` **直接双击打开只有裸 HTML、没有样式**，这是设计如此：

- 模板引用的是**生成后的学习工作区相对路径**
  - 根主页：`.learning/assets/sayo/sayo.css`（生成到 `<WS>/index.html`）
  - 科目页：`../../assets/sayo/sayo.css`（生成到 `<WS>/.learning/subjects/<slug>/index.html`）
- 仓库里的 `templates/` 旁边并没有 `.learning/` 目录，浏览器自然找不到这些文件

**想看效果**，跑预览脚本（用假数据渲染成一个模拟工作区）：

```bash
python3 scripts/preview_templates.py          # 生成到 <root>/.preview/
python3 scripts/preview_templates.py --open   # 生成并直接打开
```

产出：`.preview/index.html`（根主页）、`.preview/.learning/subjects/typescript-web-api/index.html`（科目页）、
`.preview/.../lessons/0001-http-basics.html`（课件页——预览写一份示例内容文件交给 `scripts/render_lesson.py`
渲染，与真实课件是同一条产出路径）、以及两份空状态页。
地址栏加 `?theme=dark` 看暗色。`.preview/` 已在 `.gitignore` 里。

真实生成器是 **`scripts/gen_home.py`**（读真数据、输出到学习工作区），预览脚本只负责看样式与交互。

## 模板与生成器的契约

- 模板 = **骨架 + 样式**；数据位置放 `<!-- @LEARN:XXX -->` 占位符，由生成器替换
- **区块级占位符必须独立成行**（生成器按整行替换）；**字段级可嵌在标签内**（如 `<title><!-- @LEARN:TITLE --> · 课程主页</title>`）
- 生成器**原样保留模板其余内容**（样式、脚本、文案），区块占位符缺失时报错退出
- 模板里**不放真实课程数据**：规范注释里的示例一律用字段名（`节点标题`、`NNNN`、`NN%`），避免被误当成数据
- 占位符清单与每个占位符必须生成的结构：**两个主页模板**见 `docs/工程约束.md` 的「模板与生成器的占位符契约」，
  以及模板里占位符上方那段注释（那是权威规范，改模板要同步改）；**课件壳 `lesson.html`** 的 8 个
  占位符见 `docs/课件内容格式.md` §5 与模板自己的注释。

| 模板 | 占位符 | 权威在哪 |
|------|--------|----------|
| `home-index.html` | `SUBJECT_CARDS` | `docs/工程约束.md` 的「模板与生成器的占位符契约」+ 模板注释 |
| `subject-index.html` | `TITLE` · `STATUS` · `MISSION` · `PROJECT` · `ROADMAP` · `ATTACHMENTS` | 同上 |
| `lesson.html` | `TITLE`（两处）· `SUBJECT`（两处）· `NUMBER` · `EYEBROW` · `GOAL` · `BODY` · `NAV` · `FOOTER` | `docs/课件内容格式.md` §5 + 模板自己的注释 |

## 其他文件

- `lesson.html`：**课件页的占位符壳**——**不要手工拷贝这个文件**。课件 HTML 由渲染器产出：
  `python3 scripts/render_lesson.py <科目目录> <节点id>` 读内容文件 `<科目>/lessons/<序号>-<节点id>.md`
  + 题库 `<序号>-<节点id>.quiz.json` + `<科目>/curriculum.yaml`，渲染成 `<序号>-<节点id>.html`。
  顶栏（含亮/暗主题开关）、共享层与科目组件的引用、页头、上/下节课指针、页脚、三个 `<script>` 与
  `LearnTheme.wire(...)` 全是**渲染器产出**，模板只提供占位符与给维护者看的注释（注释留在
  `<!DOCTYPE` 之前，不进产物）。正文语法与组件写法以 **`docs/课件内容格式.md`** 为准（唯一规格）；
  交出前跑一次 `python3 scripts/check_lesson.py <课件路径> --subject <科目目录> --node <节点id>`。
  学生常被总控用 `xdg-open` 直接打开课件，所以**主题开关必须长在课件自己身上**——它由渲染器按模板
  产出，要改就改模板或渲染器，别去手改 `<序号>-<节点id>.html`。
- `MEMORY.md` / `subject.yaml` / `MISSION.md` / `RESOURCES.md` / `GLOSSARY.md`：科目与记忆模板（由对应会话产出）
- `assets/`：前端资源（Sayo UI、共享主题层与主题逻辑、课件层组件、公式排版用的 KaTeX）——**摆放位置与各页面引用路径见 `assets/README.md`**
