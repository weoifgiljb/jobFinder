# jobFinder

`jobFinder` 是一个用于搜集应届生校园招聘信息的本地 Codex 插件项目。当前插件名为 `campus-recruiting-finder`，目标是帮助你查找、核验、整理和导出校招岗位线索。

## 功能

- 搜集校招、应届生、新毕业生、管培生、春招、秋招、new grad、graduate program 等招聘信息。
- 优先核验企业官网、公司招聘页、高校就业网和官方发布渠道。
- 整理公司、岗位、城市、投递状态、截止时间、申请链接和来源链接。
- 对岗位线索做去重、相关性评分，并导出 Markdown 和 JSON 文件。
- 支持中文和英文关键词，适合互联网、AI、算法、后端、产品、数据分析等方向。
- 支持 `config.json` 固化你的职业筛选条件，并让 Codex 通过问答辅助填写。
- 支持每日自动化扫描，只推送新增的官网/招聘官网岗位线索。

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
      │  └─ daily_digest.py
      ├─ config.example.json
      ├─ config.json
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
帮我通过问答填写 plugins/campus-recruiting-finder/config.json，用来筛选我的校招目标。
```

```text
帮我搜集互联网/AI方向的2026届校招岗位，城市优先上海、杭州、北京，输出表格并标出还能投递的链接。
```

```text
按城市整理最近仍可投递的校招信息，岗位方向是后端开发和数据分析。
```

```text
核验这些公司的应届生招聘入口和截止日期：字节跳动、腾讯、阿里、百度、美团。
```

## 配置文件

插件支持用 `config.json` 保存你的筛选条件：

```text
plugins/campus-recruiting-finder/config.json
```

可配置内容包括：

- `graduation_years`：毕业届别，例如 `2026届`。
- `roles`：目标岗位，例如 `算法工程师`、`后端开发`、`数据分析`。
- `cities`：目标城市，例如 `上海`、`杭州`、`北京`。
- `industries`：行业方向，例如 `AI`、`大模型`、`互联网`。
- `target_companies`：重点公司名单。
- `company_aliases`：公司别名和英文名，便于搜索和匹配。
- `must_have_keywords`：必须包含的关键词。
- `nice_to_have_keywords`：加分关键词，例如 `大模型`、`LLM`、`Python`。
- `exclude_keywords`：排除词，例如 `外包`、`销售`、`社招`。
- `degrees`：学历要求，例如 `本科`、`硕士`。
- `employment_types`：岗位类型，例如 `全职`、`校招`、`new grad`。
- `include_internships`：是否包含实习或实习转正机会。
- `remote_ok`：是否接受远程、全国或多地岗位。
- `sources.sites`：重点搜索的招聘站点域名。
- `sources.direct_urls`：已知招聘入口链接。

如果不想手写 JSON，可以直接让 Codex 问你几个问题后更新配置：

```text
帮我填写校招筛选 config.json。你先问我需要哪些条件，然后写入文件。
```

## 本地脚本

插件内置脚本位于：

```text
plugins/campus-recruiting-finder/scripts/campus_jobs.py
```

从插件目录运行示例：

```powershell
cd D:\jobFinder\plugins\campus-recruiting-finder
python .\scripts\campus_jobs.py collect --config .\config.json
```

也可以临时用关键词搜索：

```powershell
python .\scripts\campus_jobs.py collect --query "AI 2026 campus recruiting Shanghai" --out-dir .\out
```

直接整理已有链接或线索：

```powershell
python .\scripts\campus_jobs.py normalize --input raw-links.json --config .\config.json --out-dir .\out
```

输出文件：

- `campus_jobs.json`：结构化岗位线索，适合后续处理。
- `campus_jobs.md`：Markdown 表格，适合直接阅读。
- `query_plan.md`：根据配置生成的搜索计划。

## 每日自动推送

日报脚本会读取 `config.json`，搜索符合条件的校招信息，只保留官网或招聘官网倾向的线索，并用 `seen.json` 记录历史，避免每天重复推同一个链接。

从插件目录运行：

```powershell
cd D:\jobFinder\plugins\campus-recruiting-finder
python .\scripts\daily_digest.py --config .\config.json --out-dir .\out\daily --seen .\out\seen.json
```

输出文件：

- `out/daily/daily_digest_YYYY-MM-DD.md`：当天新增岗位官网摘要。
- `out/daily/daily_digest_YYYY-MM-DD.json`：当天新增岗位结构化数据。
- `out/seen.json`：已推送过的链接历史。

在 Codex 里可以创建每日自动化，让它每天执行一次并把摘要推送给你。

## 注意事项

- 校招信息变化很快，岗位开放状态和截止日期需要以实时官网或官方招聘入口为准。
- 脚本可以辅助去重和导出，但最终核验仍应优先使用 Codex 的联网搜索和官方来源。
- 如果搜索结果过少，可以扩大关键词，例如同时使用中文 `校招`、`应届生` 和英文 `new grad`、`early career`。
