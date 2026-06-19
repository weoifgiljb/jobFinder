#!/usr/bin/env python3
"""
Create a daily campus recruiting digest from config.json.

The digest keeps a small history file so repeated automation runs only surface
new official-looking career/campus links by default.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

from campus_jobs import (
    Lead,
    canonical_key,
    dedupe,
    direct_url_lead,
    is_official_lead,
    lead_matches_config,
    load_config,
    queries_from_config,
    render_markdown,
    search_bing,
)


def load_seen(path: Path) -> set[str]:
    if not path.exists():
        return set()
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(raw, list):
        return {str(item) for item in raw}
    if isinstance(raw, dict):
        return {str(item) for item in raw.get("seen", [])}
    return set()


def save_seen(path: Path, seen: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "seen": sorted(seen),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def collect_daily(config_path: Path, limit_per_query: int | None = None, delay: float = 1.0) -> list[Lead]:
    config = load_config(config_path)
    queries = queries_from_config(config)
    query_limit = limit_per_query or config.limit_per_query
    leads: list[Lead] = []
    for query in queries:
        leads.extend(search_bing(query, limit=query_limit))
        time.sleep(delay)
    for url in config.direct_urls:
        leads.append(direct_url_lead(url))
    normalized = dedupe(leads)
    return [
        lead
        for lead in normalized
        if lead_matches_config(lead, config) and is_official_lead(lead, config)
    ]


def write_digest(leads: list[Lead], out_dir: Path, seen_path: Path) -> Path:
    today = dt.date.today().isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    digest_path = out_dir / f"daily_digest_{today}.md"
    json_path = out_dir / f"daily_digest_{today}.json"
    seen = load_seen(seen_path)
    new_leads = [lead for lead in leads if canonical_key(lead) not in seen]
    for lead in new_leads:
        seen.add(canonical_key(lead))
    save_seen(seen_path, seen)

    if new_leads:
        body = render_markdown(new_leads)
        header = f"# Daily Campus Recruiting Digest - {today}\n\n新增官网/招聘官网线索：{len(new_leads)} 条。\n\n"
    else:
        body = "今天没有发现新的官网/招聘官网岗位线索。\n"
        header = f"# Daily Campus Recruiting Digest - {today}\n\n"
    digest_path.write_text(header + body, encoding="utf-8")
    json_path.write_text(
        json.dumps([asdict(lead) for lead in new_leads], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return digest_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a daily campus recruiting digest.")
    parser.add_argument("--config", default="config.json", help="Path to config JSON.")
    parser.add_argument("--out-dir", default="out/daily", help="Directory for digest files.")
    parser.add_argument("--seen", default="out/seen.json", help="History file for seen leads.")
    parser.add_argument("--limit-per-query", type=int, help="Override per-query result limit.")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between search requests.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"config not found: {config_path}", file=sys.stderr)
        return 2
    leads = collect_daily(config_path, limit_per_query=args.limit_per_query, delay=args.delay)
    digest_path = write_digest(leads, Path(args.out_dir), Path(args.seen))
    print(f"wrote {digest_path}")
    safe_print(digest_path.read_text(encoding="utf-8"))
    return 0


def safe_print(value: str) -> None:
    try:
        print(value)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(value.encode("utf-8", errors="replace"))
        sys.stdout.buffer.write(b"\n")


if __name__ == "__main__":
    raise SystemExit(main())
