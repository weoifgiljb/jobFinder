# jobFinder

`jobFinder` 是一个用于搜集应届生校园招聘信息的本地 Codex 插件项目。当前插件名为 `campus-recruiting-finder`，目标是帮助你查找、核验、整理和导出校招岗位线索。

## 功能

- 搜集校招、应届生、新毕业生、管培生、春招、秋招、new grad、graduate program 等招聘信息。
- 优先核验企业官网、公司招聘页、高校就业网和官方发布渠道。
- 整理公司、岗位、城市、投递状态、截止时间、申请链接和来源链接。
- 对岗位线索做去重、相关性评分，并导出 Markdown 和 JSON 文件。
- 支持中文和英文关键词，适合互联网、AI、算法、后端、产品、数据分析等方向。

## 目录结构

```text
jobFinder/
├─ .agents/
│  └─ plugins/
│     └─ marketplace.json
└─ plugins/
   └─ campus-recruiting-finder/
      ├─ .codex-plugin/
      │  └─ plugin.json
      ├─ scripts/
      │  └─ campus_jobs.py
      └─ skills/
         └─ campus-recruiting/
            └─ SKILL.md
```

## 安装到 Codex

先添加项目内 marketplace：

```powershell
codex plugin marketplace add D:\jobFinder\.agents\plugins
```

再安装插件：

```powershell
codex plugin add campus-recruiting-finder@jobfinder
```

安装后建议新开一个 Codex 线程使用，这样 Codex 能加载最新插件能力。

## 使用示例

可以直接向 Codex 提问：

```text
帮我搜集互联网/AI方向的2026届校招岗位，城市优先上海、杭州、北京，输出表格并标出还能投递的链接。
```

```text
按城市整理最近仍可投递的校招信息，岗位方向是后端开发和数据分析。
```

```text
核验这些公司的应届生招聘入口和截止日期：字节跳动、腾讯、阿里、百度、美团。
```

## 本地脚本

插件内置脚本位于：

```text
plugins/campus-recruiting-finder/scripts/campus_jobs.py
```

从插件目录运行示例：

```powershell
cd D:\jobFinder\plugins\campus-recruiting-finder
python .\scripts\campus_jobs.py collect --query "AI 2026 campus recruiting Shanghai" --out-dir .\out
```

直接整理已有链接或线索：

```powershell
python .\scripts\campus_jobs.py normalize --input raw-links.json --out-dir .\out
```

输出文件：

- `campus_jobs.json`：结构化岗位线索，适合后续处理。
- `campus_jobs.md`：Markdown 表格，适合直接阅读。

## 注意事项

- 校招信息变化很快，岗位开放状态和截止日期需要以实时官网或官方招聘入口为准。
- 脚本可以辅助去重和导出，但最终核验仍应优先使用 Codex 的联网搜索和官方来源。
- 如果搜索结果过少，可以扩大关键词，例如同时使用中文 `校招`、`应届生` 和英文 `new grad`、`early career`。
