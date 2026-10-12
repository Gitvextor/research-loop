import path from 'node:path';

const CONFIG_REFERENCE = '~/.dsh/studymate-config.yaml';

function shellQuote(value, windows) {
  return windows
    ? `'${value.replaceAll("'", "''")}'`
    : `'${value.replaceAll("'", "'\"'\"'")}'`;
}

function replaceConfig(text, configFile) {
  const frontmatter = text.match(/^(---\r?\n)([\s\S]*?)(\r?\n---(?:\r?\n|$))/);
  if (!frontmatter) return text.replaceAll(CONFIG_REFERENCE, configFile);
  const header = frontmatter[2].replace(/^([\w-]+:\s*)([^\r\n]*)$/gm, (line, field, value) => {
    if (!value.includes(CONFIG_REFERENCE)) return line;
    // The source description is a single-line YAML scalar. Quote its new value
    // so a user path containing ': ', '#', quotes, or braces stays plain text.
    if (value.startsWith('"') && value.endsWith('"')) {
      try { value = JSON.parse(value); } catch { /* Keep unfamiliar YAML intact. */ }
    } else if (value.startsWith("'") && value.endsWith("'")) {
      value = value.slice(1, -1).replaceAll("''", "'");
    }
    return field + JSON.stringify(value.replaceAll(CONFIG_REFERENCE, configFile));
  });
  return frontmatter[1] + header + frontmatter[3] +
    text.slice(frontmatter[0].length).replaceAll(CONFIG_REFERENCE, configFile);
}

/** Adapt only installed skill copies; teaching content remains in the source. */
export function adaptSkill(text, { platform, pythonExecutable, configFile, tempDirectory }) {
  const windows = platform === 'win32';
  const portable = value => windows ? value.replaceAll('\\', '/') : value;
  const quote = value => shellQuote(value, windows);
  const python = `${windows ? '& ' : ''}${quote(portable(pythonExecutable))} -X utf8`;
  const temp = portable(tempDirectory).replace(/\/$/, '');
  const dshHome = portable((windows ? path.win32 : path.posix).dirname(configFile));

  // Replace source references before inserting real paths, which may themselves
  // be below /tmp (for example in tests or a custom Python installation).
  // `/tmp` 在源技能里只剩两处：暂存模式的探测路径与 image-scout 的临时文件；
  // 角色产出的暂存目录改成了科目内的 `.stage/`（它在写边界里，bwrap 下也不会被清），
  // 所以这里不再有 practice-evaluator 的 cp 改写。
  let adapted = text.replaceAll('/tmp', temp);
  adapted = replaceConfig(adapted, portable(configFile));
  adapted = adapted.replace(/python3 (<root>\/scripts\/[\w-]+\.py)([^`\r\n]*)/g,
    (_, script, args) => `${python} ${quote(script)}${args.replace(/<(?:subject_path|curriculum\.yaml|页面路径|tsv)>/g, quote)}`);

  const digest = windows
    ? "(Get-FileHash -LiteralPath '<文件>' -Algorithm MD5).Hash.Substring(0,12).ToLowerInvariant()"
    : `${python} -c ${quote('import hashlib,pathlib,sys; print(hashlib.md5(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest()[:12])')} '<文件>'`;
  adapted = adapted.replaceAll('md5sum <文件> | cut -c1-12', digest);

  const open = windows ? "Start-Process -FilePath '<页面绝对路径>'"
    : `${platform === 'darwin' ? 'open' : 'xdg-open'} '<页面绝对路径>'`;
  adapted = adapted.replaceAll('`xdg-open` / `open`', `\`${open}\``);
  if (windows) {
    adapted = adapted.replaceAll('`cp -r`', '`Copy-Item -Recurse`').replaceAll('`cp`', '`Copy-Item`');
    adapted = adapted.replaceAll('`grep`', '`Select-String`');
  }

  const environment = windows
    ? `$env:DSH_HOME=${quote(dshHome)}; $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'`
    : `export DSH_HOME=${quote(dshHome)} PYTHONUTF8=1 PYTHONIOENCODING=utf-8`;
  const platformNote = windows
    ? `使用 PowerShell；单文件原样搬运：\`Copy-Item -LiteralPath '<源文件>' -Destination '<目标文件>' -Force\`；目录内容原样搬运：\`Get-ChildItem -LiteralPath '<源目录>' -Force | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination '<目标目录>' -Recurse -Force }\`。目录不存在先用 \`[System.IO.Directory]::CreateDirectory('<目录>') | Out-Null\` 创建。`
    : `使用本机 shell；单文件原样搬运用 \`cp '<源文件>' '<目标文件>'\`，目录内容原样搬运用 \`cp -r '<源目录>/.' '<目标目录>/'\`。`;
  return `${adapted.trimEnd()}\n\n## 本机命令约定（安装器生成）\n\n` +
    `只调整命令与路径写法；流程、文件归属和原样搬运要求不变。每次调用 shell 工具执行 Python 时，必须在同一条命令中先设置环境再执行脚本：\`${environment}\`；这次设置不保留到下一次工具调用。Python 使用 \`${python}\`，子进程也继承 UTF-8 编码。\n\n` +
    `${platformNote} 临时与暂存文件先写科目自己的 \`<subject_path>/.stage/\`（它在会话写边界内）；确实需要系统临时目录时用 \`${temp}\`。路径占位符换成实值后必须保持 shell 引用；${windows ? "PowerShell 单引号路径中的单引号写两次" : "POSIX 单引号路径中的单引号用 '\"'\"' 转义"}，不要把路径当作未引用的命令片段。打开页面用 \`${open}\`，无桌面环境时保留可点的页面链接即可。\n`;
}
