#!/usr/bin/env python3
"""Fetch RSS feeds from sources.json, normalize into candidate items, write a dated digest."""
import html
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import mktime

import feedparser
import requests

HERE = Path(__file__).parent
# DATA_DIR separates mutable, runtime-generated state (digests, content, rendered
# slides, preview.html) from the read-only code/static assets in HERE. Locally they're
# the same directory (unset falls back to HERE); in production DATA_DIR points at a
# mounted persistent disk, so generated stories survive container restarts/redeploys.
DATA_DIR = Path(os.environ.get("DATA_DIR", str(HERE)))
SOURCES_FILE = HERE / "sources.json"
DIGESTS_DIR = DATA_DIR / "digests"
LOOKBACK_HOURS = 48
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}


def load_sources():
    return json.loads(SOURCES_FILE.read_text())


def entry_published(entry):
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            return datetime.fromtimestamp(mktime(val), tz=timezone.utc)
    return None


def fetch_feed(feed):
    try:
        resp = requests.get(feed["url"], headers=HEADERS, timeout=15, allow_redirects=True)
        status = resp.status_code
        parsed = feedparser.parse(resp.content)
    except requests.RequestException as e:
        return {
            "name": feed["name"], "url": feed["url"], "http_status": f"error: {e}",
            "parse_error": True, "entry_count": 0, "items": [],
        }
    bozo = parsed.bozo
    items = []
    for entry in parsed.entries:
        published = entry_published(entry)
        # Some feeds (e.g. LiveMint) double-encode entities in their raw XML, so
        # feedparser's one decode pass still leaves a literal "&amp;" in the text; a
        # second html.unescape() cancels that out. It's a no-op for normal feeds, since
        # there's no entity left to decode once feedparser has already done it once.
        items.append({
            "title": html.unescape(entry.get("title", "").strip()),
            "link": entry.get("link", "").strip(),
            "summary": html.unescape(entry.get("summary", "").strip()[:500]),
            "published": published.isoformat() if published else None,
            "source": feed["name"],
            "category": feed["category"],
        })
    return {
        "name": feed["name"],
        "url": feed["url"],
        "http_status": status,
        "parse_error": bool(bozo) and not parsed.entries,
        "entry_count": len(items),
        "items": items,
    }


def main():
    sources = load_sources()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)

    all_items = []
    feed_report = []
    seen_links = set()

    # Feeds are independent network requests -- fetching them one at a time meant a
    # single slow/hanging source (each has its own 15s timeout) held up every feed
    # behind it. Concurrent fetch keeps executor.map's output in the same order as
    # sources.json, so nothing else about the pipeline changes.
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(fetch_feed, sources["rss_feeds"]))

    for result in results:
        feed_report.append({
            "name": result["name"],
            "http_status": result["http_status"],
            "parse_error": result["parse_error"],
            "entry_count": result["entry_count"],
        })
        for item in result["items"]:
            if item["link"] in seen_links:
                continue
            seen_links.add(item["link"])
            if item["published"]:
                pub_dt = datetime.fromisoformat(item["published"])
                if pub_dt < cutoff:
                    continue
            all_items.append(item)

    all_items.sort(key=lambda x: x["published"] or "", reverse=True)

    DIGESTS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    digest_path = DIGESTS_DIR / f"digest_{today}.json"
    digest_path.write_text(json.dumps({
        "pillar": sources["pillar"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_hours": LOOKBACK_HOURS,
        "feed_report": feed_report,
        "item_count": len(all_items),
        "items": all_items,
    }, indent=2))

    print(f"Wrote {len(all_items)} items to {digest_path}\n")
    print("Feed health:")
    for f in feed_report:
        flag = "OK" if not f["parse_error"] and f["entry_count"] > 0 else "FAILED/EMPTY"
        print(f"  [{flag:12}] {f['name']:30} status={f['http_status']} entries={f['entry_count']}")


if __name__ == "__main__":
    main()
