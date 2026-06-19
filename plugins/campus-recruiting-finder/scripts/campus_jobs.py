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
from typing import Iterable


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
    for query in args.query:
        expanded = " ".join(part for part in [query, args.role, args.city] if part)
        leads.extend(search_bing(expanded, limit=args.limit_per_query))
        time.sleep(args.delay)
    for url in args.url:
        leads.append(direct_url_lead(url, company=args.company, city=args.city, role=args.role))
    normalized = dedupe(leads)
    write_outputs(normalized, Path(args.out_dir))
    return 0


def normalize(args: argparse.Namespace) -> int:
    leads = load_input(Path(args.input))
    for lead in leads:
        score_lead(lead)
    write_outputs(dedupe(leads), Path(args.out_dir))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect, score, deduplicate, and export campus recruiting leads.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            Examples:
              campus_jobs.py collect --query "AI 2026 campus recruiting Shanghai" --out-dir out
              campus_jobs.py collect --url https://company.example/campus --company Example --out-dir out
              campus_jobs.py normalize --input raw-links.json --out-dir out
            """
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect")
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
    normalize_parser.add_argument("--out-dir", default="out")
    normalize_parser.set_defaults(func=normalize)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "collect" and not args.query and not args.url:
        parser.error("collect requires at least one --query or --url")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
