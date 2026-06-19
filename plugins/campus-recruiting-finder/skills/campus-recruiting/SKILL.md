---
name: campus-recruiting
description: Find and organize up-to-date campus recruiting, new graduate, graduate program, internship-to-full-time, and 应届生/校招 opportunities. Use when the user wants Codex to search for campus hiring information, verify company recruitment pages, compare deadlines, collect job leads, export a job list, or monitor/refresh early-career roles for students and recent graduates.
---

# Campus Recruiting

Use this skill to collect current campus recruiting leads for students and new graduates. Campus hiring changes quickly, so always browse or otherwise verify live sources before presenting openings, deadlines, eligibility, or application links.

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
6. Use the bundled script for normalization, deduplication, scoring, and Markdown/JSON export.

## Bundled Script

Run from the plugin root:

```powershell
python .\scripts\campus_jobs.py collect --query "AI算法 2026届 校招 上海" --query "new grad software engineer China 2026" --out-dir .\out
```

Useful modes:

```powershell
python .\scripts\campus_jobs.py collect --query "后端 2026届 校招 北京" --city 北京 --role 后端 --out-dir .\out
python .\scripts\campus_jobs.py collect --url https://example.com/careers/campus --company Example --out-dir .\out
python .\scripts\campus_jobs.py normalize --input raw-links.json --out-dir .\out
```

The script accepts web search queries and direct URLs. It fetches pages where possible, extracts titles/snippets/links, scores campus-recruiting relevance, deduplicates by URL and title, and writes `campus_jobs.json` plus `campus_jobs.md`.

## Output Standard

Present results as a concise table sorted by confidence and deadline urgency:

| Company | Role | City | Status | Deadline | Evidence |
| --- | --- | --- | --- | --- | --- |

Include links to sources. Add a short "Next actions" section with application steps, missing info to verify, and suggested search refinements.

## Quality Rules

- Prefer official application links over reposts.
- Keep reposts only when they reveal a lead not yet found on an official page, and label them as reposts.
- Treat stale pages from previous recruiting years as historical unless the page clearly covers the user's target year.
- For China campus recruiting, check both web pages and likely official account article titles when search results surface them.
- If the user asks for "latest", "currently open", "还能投", or similar, verify on the current date before answering.
