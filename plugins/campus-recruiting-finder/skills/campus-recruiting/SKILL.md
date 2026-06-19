---
name: campus-recruiting
description: Find and organize up-to-date campus recruiting, new graduate, graduate program, internship-to-full-time, and 应届生/校招 opportunities. Use when the user wants Codex to search for campus hiring information, verify company recruitment pages, compare deadlines, collect job leads, export a job list, or monitor/refresh early-career roles for students and recent graduates.
---

# Campus Recruiting

Use this skill to collect current campus recruiting leads for students and new graduates. Campus hiring changes quickly, so always browse or otherwise verify live sources before presenting openings, deadlines, eligibility, or application links. Prefer a configuration-driven workflow when the user wants repeatable filtering.

## Config Workflow

When the user asks to create, fill, adjust, or use a job-search config, work with `config.json` in the plugin root. Use `config.example.json` as the schema reference.

Ask concise questions only for missing decision fields:

1. Graduation year: for example `2026届`, `2027届`, `2026`.
2. Role targets: for example `算法工程师`, `后端开发`, `产品经理`, `数据分析`.
3. Cities or regions: include whether `全国`, `多地`, or remote roles are acceptable.
4. Industry focus: for example `互联网`, `AI`, `大模型`, `云计算`, `金融科技`.
5. Target companies: optional company allowlist for focused searches.
6. Degree and employment type: bachelor/master/PhD, full-time, internship, internship-to-full-time.
7. Must-have and nice-to-have keywords: for example `大模型`, `LLM`, `Python`, `C++`.
8. Exclusions: roles, industries, cities, or sources to avoid.
9. Internship preference: whether internships or internship-to-full-time postings count.

After collecting answers, update `config.json` with valid JSON. Keep user-provided Chinese text unchanged. Preserve existing fields that the user did not change.

## Workflow

1. Clarify the target only when needed: graduation year, major/function, cities, industries, language preference, and whether internships count.
2. Search current sources using a mix of Chinese and English terms:
   - `校招`, `校园招聘`, `应届生`, `毕业生项目`, `管培生`, `秋招`, `春招`
   - `new grad`, `graduate program`, `campus recruitment`, `early career`
   - add role terms such as `算法`, `后端`, `产品经理`, `数据分析`, `软件工程师`
3. Prioritize primary or near-primary sources:
   - company career sites and official WeChat/招聘 pages
   - university employment boards
   - official job board postings with company-owned application links
4. For each lead, capture: company, role/title, location, graduation/eligibility, deadline or batch timing, application URL, source URL, posted/updated date when visible, and notes.
5. Mark uncertainty explicitly. Do not infer that a role is still open unless a current source confirms it.
6. Use `config.json` for repeatable search preferences when available.
7. Use the bundled script for normalization, deduplication, scoring, and Markdown/JSON export.

## Bundled Script

Run from the plugin root:

```powershell
python .\scripts\campus_jobs.py collect --query "AI算法 2026届 校招 上海" --query "new grad software engineer China 2026" --out-dir .\out
```

Useful modes:

```powershell
python .\scripts\campus_jobs.py collect --config .\config.json
python .\scripts\campus_jobs.py collect --query "后端 2026届 校招 北京" --city 北京 --role 后端 --out-dir .\out
python .\scripts\campus_jobs.py collect --url https://example.com/careers/campus --company Example --out-dir .\out
python .\scripts\campus_jobs.py normalize --input raw-links.json --config .\config.json --out-dir .\out
```

The script accepts config files, web search queries, and direct URLs. It fetches pages where possible, extracts titles/snippets/links, scores campus-recruiting relevance, deduplicates by URL and title, applies config filters, and writes `campus_jobs.json`, `campus_jobs.md`, and `query_plan.md`.

For daily monitoring and push-style summaries:

```powershell
python .\scripts\daily_digest.py --config .\config.json --out-dir .\out\daily --seen .\out\seen.json
```

The daily digest keeps `seen.json`, filters for official-looking career/campus links, writes `daily_digest_YYYY-MM-DD.md`, and prints the digest so Codex automations can send it to the user.

## Config Fields

- `languages`: search language hints, usually `["zh", "en"]`.
- `filters.graduation_years`: target graduation years or class labels.
- `filters.roles`: target job functions.
- `filters.cities`: preferred cities.
- `filters.industries`: industry keywords.
- `filters.target_companies`: optional company allowlist.
- `filters.company_aliases`: aliases and English names for target companies.
- `filters.keywords`: extra positive search terms.
- `filters.must_have_keywords`: every result must contain these terms.
- `filters.nice_to_have_keywords`: boost matching results.
- `filters.exclude_keywords`: negative filters.
- `filters.degrees`: degree constraints.
- `filters.employment_types`: full-time, internship, or new-grad labels.
- `filters.include_internships`: include internship and internship-to-full-time roles.
- `filters.include_reposts`: keep non-official repost sources as leads.
- `filters.remote_ok`: accept remote, national, or multi-city postings.
- `sources.sites`: domains to search with `site:`.
- `sources.direct_urls`: known career/campus URLs to fetch directly.
- `output`: output directory and query/result limits.

## Output Standard

Present results as a concise table sorted by confidence and deadline urgency:

| Company | Role | City | Status | Deadline | Evidence |
| --- | --- | --- | --- | --- | --- |

Include links to sources. Add a short "Next actions" section with application steps, missing info to verify, and suggested search refinements.

## Quality Rules

- Prefer official application links over reposts.
- For daily pushes, include only new official-looking career/campus links unless the user explicitly asks for reposts.
- Keep reposts only when they reveal a lead not yet found on an official page, and label them as reposts.
- Treat stale pages from previous recruiting years as historical unless the page clearly covers the user's target year.
- For China campus recruiting, check both web pages and likely official account article titles when search results surface them.
- If the user asks for "latest", "currently open", "还能投", or similar, verify on the current date before answering.
