#!/usr/bin/env python3
"""
Collect and normalize campus recruiting leads.

The script intentionally uses only the Python standard library so it can run in
fresh Codex environments without dependency installation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0 Safari/537.36 CampusRecruitingFinder/0.1"
)

CAMPUS_TERMS = [
    "校招",
    "校园招聘",
    "应届",
    "应届生",
    "毕业生",
    "管培生",
    "秋招",
    "春招",
    "new grad",
    "new graduate",
    "graduate program",
    "campus recruitment",
    "early career",
    "entry level",
]

OFFICIAL_HINTS = [
    "career",
    "careers",
    "jobs",
    "join",
    "recruit",
    "campus",
    "zhaopin",
    "hire",
    "talent",
    "hr",
]

REPOST_HINTS = [
    "nowcoder",
    "牛客",
    "yingjiesheng",
    "应届生求职",
    "kanzhun",
    "boss",
    "liepin",
    "zhipin",
    "linkedin",
]


@dataclass
class Lead:
    title: str
    url: str
    source: str
    snippet: str = ""
    company: str = ""
    role: str = ""
    city: str = ""
    deadline: str = ""
    status: str = "needs verification"
    confidence: int = 0
    collected_at: str = ""


@dataclass
class SearchConfig:
    graduation_years: list[str]
    roles: list[str]
    cities: list[str]
    industries: list[str]
    target_companies: list[str]
    company_aliases: dict[str, list[str]]
    keywords: list[str]
    must_have_keywords: list[str]
    nice_to_have_keywords: list[str]
    exclude_keywords: list[str]
    degrees: list[str]
    employment_types: list[str]
    source_sites: list[str]
    direct_urls: list[str]
    languages: list[str]
    include_internships: bool
    include_reposts: bool
    remote_ok: bool
    min_confidence: int
    limit_per_query: int
    max_queries: int
    output_dir: str


class LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []
        self.title = ""
        self._in_title = False
        self._title_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            attrs_dict = {k.lower(): v or "" for k, v in attrs}
            self._href = attrs_dict.get("href")
            self._text = []
        elif tag.lower() == "title":
            self._in_title = True
            self._title_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            text = normalize_space("".join(self._text))
            if text:
                self.links.append({"href": self._href, "text": text})
            self._href = None
            self._text = []
        elif tag.lower() == "title":
            self._in_title = False
            self.title = normalize_space("".join(self._title_text))

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)
        if self._in_title:
            self._title_text.append(data)


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def fetch_url(url: str, timeout: int = 15) -> tuple[str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        final_url = response.geturl()
        content_type = response.headers.get("content-type", "")
        raw = response.read(1_500_000)
    encoding = "utf-8"
    match = re.search(r"charset=([\w.-]+)", content_type, re.I)
    if match:
        encoding = match.group(1)
    try:
        return raw.decode(encoding, errors="replace"), final_url
    except LookupError:
        return raw.decode("utf-8", errors="replace"), final_url


def search_bing(query: str, limit: int) -> list[Lead]:
    encoded = urllib.parse.urlencode({"q": query, "mkt": "zh-CN", "setlang": "zh-CN"})
    search_url = f"https://www.bing.com/search?{encoded}"
    try:
        body, final_url = fetch_url(search_url)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"warning: search failed for {query!r}: {exc}", file=sys.stderr)
        return []

    extractor = LinkExtractor()
    extractor.feed(body)
    leads: list[Lead] = []
    seen: set[str] = set()
    for item in extractor.links:
        href = clean_search_href(item["href"])
        if not href or href in seen:
            continue
        seen.add(href)
        title = item["text"]
        if should_skip_url(href) or len(title) < 3 or not looks_like_job_result(title, href):
            continue
        lead = Lead(title=title, url=href, source=final_url)
        score_lead(lead)
        if lead.confidence > 0:
            leads.append(lead)
        if len(leads) >= limit:
            break
    return leads


def load_config(path: Path) -> SearchConfig:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError("config JSON must be an object")
    filters = raw.get("filters") or {}
    sources = raw.get("sources") or {}
    output = raw.get("output") or {}
    return SearchConfig(
        graduation_years=list_of_strings(filters.get("graduation_years")),
        roles=list_of_strings(filters.get("roles")),
        cities=list_of_strings(filters.get("cities")),
        industries=list_of_strings(filters.get("industries")),
        target_companies=list_of_strings(filters.get("target_companies")),
        company_aliases=dict_of_string_lists(filters.get("company_aliases")),
        keywords=list_of_strings(filters.get("keywords")),
        must_have_keywords=list_of_strings(filters.get("must_have_keywords")),
        nice_to_have_keywords=list_of_strings(filters.get("nice_to_have_keywords")),
        exclude_keywords=list_of_strings(filters.get("exclude_keywords")),
        degrees=list_of_strings(filters.get("degrees")),
        employment_types=list_of_strings(filters.get("employment_types")),
        source_sites=list_of_strings(sources.get("sites")),
        direct_urls=list_of_strings(sources.get("direct_urls")),
        languages=list_of_strings(raw.get("languages")) or ["zh", "en"],
        include_internships=bool(filters.get("include_internships", False)),
        include_reposts=bool(filters.get("include_reposts", True)),
        remote_ok=bool(filters.get("remote_ok", False)),
        min_confidence=int(output.get("min_confidence", 35)),
        limit_per_query=int(output.get("limit_per_query", 12)),
        max_queries=int(output.get("max_queries", 80)),
        output_dir=str(output.get("dir") or "out"),
    )


def list_of_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def dict_of_string_lists(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, list[str]] = {}
    for key, raw_items in value.items():
        clean_key = str(key).strip()
        if clean_key:
            result[clean_key] = list_of_strings(raw_items)
    return result


def queries_from_config(config: SearchConfig) -> list[str]:
    role_terms = config.roles or [""]
    city_terms = config.cities or [""]
    year_terms = config.graduation_years or [""]
    industry_terms = config.industries or [""]
    company_terms = config.target_companies or [""]
    extra_keywords = list(config.keywords)
    extra_keywords.extend(config.must_have_keywords)
    campus_terms = ["校招", "应届生"] if "zh" in config.languages else []
    if "en" in config.languages:
        campus_terms.extend(["new grad", "campus recruitment", "early career"])
    if config.include_internships:
        campus_terms.extend(["实习转正", "internship"])
    if config.remote_ok:
        extra_keywords.extend(["remote", "远程"])

    queries: list[str] = []
    for role in role_terms:
        for city in city_terms:
            for year in year_terms:
                base_parts = [role, year, city]
                for campus_term in campus_terms or ["campus recruiting"]:
                    queries.append(compact_query([*base_parts, campus_term, *extra_keywords]))
                for company in company_terms:
                    if company:
                        company_terms_for_query = [company, *config.company_aliases.get(company, [])]
                        for company_term in company_terms_for_query:
                            queries.append(compact_query([company_term, *base_parts, "招聘", "career"]))
                for industry in industry_terms:
                    if industry:
                        queries.append(compact_query([industry, *base_parts, "校招"]))
    for site in config.source_sites:
        for role in role_terms:
            for year in year_terms:
                queries.append(compact_query([f"site:{site}", role, year, "校招 OR new grad"]))

    seen: set[str] = set()
    result: list[str] = []
    for query in queries:
        if query and query not in seen:
            seen.add(query)
            result.append(query)
        if len(result) >= config.max_queries:
            break
    return result


def compact_query(parts: Iterable[str]) -> str:
    seen: set[str] = set()
    clean_parts: list[str] = []
    for part in parts:
        if not part or not part.strip():
            continue
        normalized = part.strip()
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        clean_parts.append(normalized)
    return " ".join(clean_parts)


def lead_matches_config(lead: Lead, config: SearchConfig) -> bool:
    haystack = f"{lead.title} {lead.url} {lead.snippet} {lead.company} {lead.role} {lead.city}".lower()
    if lead.confidence < config.min_confidence:
        return False
    if not config.include_reposts and any(hint in haystack for hint in REPOST_HINTS):
        return False
    if config.exclude_keywords and any(term.lower() in haystack for term in config.exclude_keywords):
        return False
    if config.cities and not config.remote_ok:
        city_match = any(city.lower() in haystack for city in config.cities)
        if lead.city:
            city_match = city_match or lead.city in config.cities
        if not city_match and not any(term in haystack for term in ["全国", "多地", "remote", "远程"]):
            return False
    if config.target_companies and not any(company.lower() in haystack for company in config.target_companies):
        aliases = []
        for company in config.target_companies:
            aliases.extend(config.company_aliases.get(company, []))
            aliases.append(domain_company(company))
        if not any(alias.lower() in haystack for alias in aliases):
            return False
    if config.roles and not any(role.lower() in haystack for role in config.roles):
        if not any(term.lower() in haystack for term in config.must_have_keywords):
            return False
    if config.must_have_keywords and not all(term.lower() in haystack for term in config.must_have_keywords):
        return False
    if config.degrees and not any(degree.lower() in haystack for degree in config.degrees):
        if not any(term in haystack for term in ["本科", "硕士", "博士", "bachelor", "master", "phd"]):
            return False
    if config.employment_types and not any(item.lower() in haystack for item in config.employment_types):
        if not any(term in haystack for term in ["全职", "full-time", "full time", "校招", "new grad"]):
            return False
    if config.nice_to_have_keywords and any(term.lower() in haystack for term in config.nice_to_have_keywords):
        lead.confidence = min(100, lead.confidence + 5)
    return True


def is_official_lead(lead: Lead, config: SearchConfig | None = None) -> bool:
    haystack = f"{lead.title} {lead.url} {lead.snippet} {lead.source}".lower()
    parsed = urllib.parse.urlparse(lead.url)
    host = parsed.netloc.lower().removeprefix("www.")
    if config and any(site.lower() in host for site in config.source_sites):
        return True
    if any(hint in haystack for hint in REPOST_HINTS):
        return False
    return any(hint in haystack for hint in OFFICIAL_HINTS)


def domain_company(company: str) -> str:
    return re.sub(r"\s+", "", company).replace("集团", "").replace("股份", "")


def clean_search_href(href: str) -> str:
    href = html.unescape(href)
    if href.startswith("/ck/a"):
        parsed = urllib.parse.urlparse(href)
        qs = urllib.parse.parse_qs(parsed.query)
        for key in ("u", "url"):
            if key in qs and qs[key]:
                value = qs[key][0]
                if value.startswith("a1"):
                    value = value[2:]
                try:
                    return urllib.parse.unquote(value)
                except Exception:
                    return value
    if href.startswith("http://") or href.startswith("https://"):
        parsed = urllib.parse.urlparse(href)
        if "bing.com" in parsed.netloc and parsed.path.startswith("/search"):
            return ""
        return href
    return ""


def should_skip_url(url: str) -> bool:
    lower = url.lower()
    blocked = [
        "microsofttranslator.com",
        "go.microsoft.com",
        "support.microsoft.com",
        "account.microsoft.com",
        "javascript:",
        ".pdf?",
    ]
    return any(part in lower for part in blocked)


def looks_like_job_result(title: str, url: str) -> bool:
    haystack = f"{title} {url}".lower()
    terms = CAMPUS_TERMS + OFFICIAL_HINTS + [
        "招聘",
        "岗位",
        "职位",
        "投递",
        "apply",
        "hiring",
        "job",
        "intern",
    ]
    return any(term.lower() in haystack for term in terms)


def direct_url_lead(url: str, company: str = "", city: str = "", role: str = "") -> Lead:
    title = url
    snippet = ""
    final_url = url
    try:
        body, final_url = fetch_url(url)
        extractor = LinkExtractor()
        extractor.feed(body)
        title = extractor.title or url
        snippet = extract_relevant_snippet(body)
    except (urllib.error.URLError, TimeoutError) as exc:
        snippet = f"fetch failed: {exc}"
    lead = Lead(
        title=normalize_space(title),
        url=final_url,
        source=url,
        snippet=snippet,
        company=company,
        city=city,
        role=role,
    )
    score_lead(lead)
    return lead


def extract_relevant_snippet(body: str) -> str:
    text = re.sub(r"<script\b.*?</script>", " ", body, flags=re.I | re.S)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = normalize_space(text)
    lower = text.lower()
    positions = [lower.find(term.lower()) for term in CAMPUS_TERMS if lower.find(term.lower()) >= 0]
    start = min(positions) if positions else 0
    return text[start : start + 280]


def score_lead(lead: Lead) -> None:
    haystack = f"{lead.title} {lead.url} {lead.snippet}".lower()
    score = 0
    if any(term.lower() in haystack for term in CAMPUS_TERMS):
        score += 45
    if any(hint in haystack for hint in OFFICIAL_HINTS):
        score += 20
    if any(hint in haystack for hint in REPOST_HINTS):
        score -= 10
    if re.search(r"20[2-9]\d", haystack):
        score += 10
    if any(word in haystack for word in ["截止", "deadline", "投递", "apply", "申请"]):
        score += 10
    if lead.company and lead.company.lower() in haystack:
        score += 5
    lead.confidence = max(0, min(100, score))
    if score >= 65:
        lead.status = "likely relevant, verify deadline"
    elif score >= 35:
        lead.status = "possible lead"
    else:
        lead.status = "low relevance"
    lead.collected_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def dedupe(leads: Iterable[Lead]) -> list[Lead]:
    best: dict[str, Lead] = {}
    for lead in leads:
        key = canonical_key(lead)
        current = best.get(key)
        if current is None or lead.confidence > current.confidence:
            best[key] = lead
    return sorted(best.values(), key=lambda item: (-item.confidence, item.title.lower()))


def canonical_key(lead: Lead) -> str:
    parsed = urllib.parse.urlparse(lead.url)
    host = parsed.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+$", "", parsed.path.lower())
    if host and path:
        return f"{host}{path}"
    return normalize_space(lead.title).lower()


def write_outputs(leads: list[Lead], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "campus_jobs.json"
    md_path = out_dir / "campus_jobs.md"
    payload = [asdict(lead) for lead in leads]
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(leads), encoding="utf-8")
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")


def write_query_plan(queries: list[str], config: SearchConfig, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_path = out_dir / "query_plan.md"
    lines = [
        "# Campus Recruiting Query Plan",
        "",
        f"- Roles: {', '.join(config.roles) or '(any)'}",
        f"- Cities: {', '.join(config.cities) or '(any)'}",
        f"- Graduation years: {', '.join(config.graduation_years) or '(any)'}",
        f"- Target companies: {', '.join(config.target_companies) or '(any)'}",
        f"- Must-have keywords: {', '.join(config.must_have_keywords) or '(none)'}",
        f"- Exclude keywords: {', '.join(config.exclude_keywords) or '(none)'}",
        f"- Min confidence: {config.min_confidence}",
        "",
        "## Queries",
        "",
    ]
    lines.extend(f"{index}. `{query}`" for index, query in enumerate(queries, start=1))
    plan_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {plan_path}")


def render_markdown(leads: list[Lead]) -> str:
    today = dt.date.today().isoformat()
    lines = [
        f"# Campus Recruiting Leads",
        "",
        f"Collected: {today}",
        "",
        "| Confidence | Company | Title | City | Status | Link |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for lead in leads:
        company = escape_cell(lead.company or infer_company_from_url(lead.url))
        title = escape_cell(lead.title[:120])
        city = escape_cell(lead.city)
        status = escape_cell(lead.status)
        lines.append(
            f"| {lead.confidence} | {company} | {title} | {city} | {status} | [source]({lead.url}) |"
        )
    lines.extend(["", "## Notes", ""])
    for lead in leads:
        snippet = escape_cell(lead.snippet[:300])
        if snippet:
            lines.append(f"- **{escape_cell(lead.title[:100])}**: {snippet}")
    return "\n".join(lines) + "\n"


def escape_cell(value: str) -> str:
    return normalize_space(value).replace("|", "\\|")


def infer_company_from_url(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    parts = host.split(".")
    if len(parts) >= 2:
        return parts[-2]
    return host


def load_input(path: Path) -> list[Lead]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    leads: list[Lead] = []
    if not isinstance(raw, list):
        raise ValueError("input JSON must be a list")
    for item in raw:
        if isinstance(item, str):
            leads.append(Lead(title=item, url=item, source=str(path)))
        elif isinstance(item, dict):
            leads.append(
                Lead(
                    title=str(item.get("title") or item.get("name") or item.get("url") or ""),
                    url=str(item.get("url") or item.get("link") or ""),
                    source=str(item.get("source") or path),
                    snippet=str(item.get("snippet") or item.get("summary") or ""),
                    company=str(item.get("company") or ""),
                    role=str(item.get("role") or ""),
                    city=str(item.get("city") or ""),
                    deadline=str(item.get("deadline") or ""),
                    status=str(item.get("status") or "needs verification"),
                    confidence=int(item.get("confidence") or 0),
                )
            )
    return leads


def collect(args: argparse.Namespace) -> int:
    leads: list[Lead] = []
    queries = list(args.query)
    urls = list(args.url)
    out_dir = Path(args.out_dir)
    limit_per_query = args.limit_per_query
    active_config: SearchConfig | None = None
    if args.config:
        active_config = load_config(Path(args.config))
        queries.extend(queries_from_config(active_config))
        urls.extend(active_config.direct_urls)
        if args.out_dir == "out":
            out_dir = Path(active_config.output_dir)
        if args.limit_per_query == 12:
            limit_per_query = active_config.limit_per_query
        write_query_plan(queries, active_config, out_dir)
    for query in queries:
        expanded = " ".join(part for part in [query, args.role, args.city] if part)
        leads.extend(search_bing(expanded, limit=limit_per_query))
        time.sleep(args.delay)
    for url in urls:
        leads.append(direct_url_lead(url, company=args.company, city=args.city, role=args.role))
    normalized = dedupe(leads)
    if active_config:
        normalized = [lead for lead in normalized if lead_matches_config(lead, active_config)]
    write_outputs(normalized, out_dir)
    return 0


def normalize(args: argparse.Namespace) -> int:
    leads = load_input(Path(args.input))
    for lead in leads:
        score_lead(lead)
    normalized = dedupe(leads)
    out_dir = Path(args.out_dir)
    if args.config:
        active_config = load_config(Path(args.config))
        normalized = [lead for lead in normalized if lead_matches_config(lead, active_config)]
        if args.out_dir == "out":
            out_dir = Path(active_config.output_dir)
    write_outputs(normalized, out_dir)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect, score, deduplicate, and export campus recruiting leads.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            Examples:
              campus_jobs.py collect --config config.json
              campus_jobs.py collect --query "AI 2026 campus recruiting Shanghai" --out-dir out
              campus_jobs.py collect --url https://company.example/campus --company Example --out-dir out
              campus_jobs.py normalize --input raw-links.json --out-dir out
            """
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect")
    collect_parser.add_argument("--config", help="Filtering config JSON.")
    collect_parser.add_argument("--query", action="append", default=[], help="Search query to run.")
    collect_parser.add_argument("--url", action="append", default=[], help="Direct campus/career URL to fetch.")
    collect_parser.add_argument("--company", default="", help="Company hint for direct URLs.")
    collect_parser.add_argument("--city", default="", help="City filter or hint.")
    collect_parser.add_argument("--role", default="", help="Role/function filter or hint.")
    collect_parser.add_argument("--limit-per-query", type=int, default=12)
    collect_parser.add_argument("--delay", type=float, default=1.0, help="Delay between search requests.")
    collect_parser.add_argument("--out-dir", default="out")
    collect_parser.set_defaults(func=collect)

    normalize_parser = subparsers.add_parser("normalize")
    normalize_parser.add_argument("--input", required=True, help="JSON list of URLs or lead objects.")
    normalize_parser.add_argument("--config", help="Filtering config JSON.")
    normalize_parser.add_argument("--out-dir", default="out")
    normalize_parser.set_defaults(func=normalize)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "collect" and not args.query and not args.url and not args.config:
        parser.error("collect requires at least one --query, --url, or --config")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
