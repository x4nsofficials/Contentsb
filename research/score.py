#!/usr/bin/env python3
"""Score a raw ingestion digest for business-audience relevance using Claude, output a ranked shortlist."""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE.parent / ".env", override=True)

DATA_DIR = Path(os.environ.get("DATA_DIR", str(HERE)))
DIGESTS_DIR = DATA_DIR / "digests"
API_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com") + "/v1/messages"
API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = "claude-sonnet-4-6"
BATCH_SIZE = 300
TOP_N = 25

SYSTEM_PROMPT = """You score content candidates for an INDIA-FOCUSED business/growth Instagram carousel page that \
runs TWO content pillars, and both need real representation in what you shortlist, not just the easier-to-find one:
1. Business & Markets (India) — funding, policy, market-moving company news.
2. Entrepreneurship & founder-building — content that helps someone building a company actually get better at it:
   lessons, tactics, mistakes, turnarounds, hiring/growth/leadership advice, founder stories. This pillar is \
   NOT reactive news about a triggering event — an evergreen "how we scaled hiring" or "the mistake that nearly \
   killed our startup" essay belongs here and should score just as high as a funding headline when it's well told.

HARD REQUIREMENT — India relevance, no exceptions for either pillar: some of the entrepreneurship-pillar sources \
are global (Entrepreneur.com, Inc.com, Y Combinator's blog etc.) and most of what they publish has ZERO India \
connection — a US founder's company, a Silicon Valley essay with no Indian angle at all. That content does NOT \
belong on this page no matter how well-written or universally useful the lesson is. Score an item above 4 ONLY if \
at least one of these is true: (a) the company/founder/story is Indian or India-based, (b) the story is explicitly \
about India's market, regulation, or economy, or (c) it's global but has a clear, specific, and obvious hook for \
an Indian entrepreneurship audience that you could name in one phrase (e.g. "the exact playbook Indian D2C brands \
are now copying") — a vague "founders everywhere can learn from this" is NOT enough, that's true of almost any \
founder-lessons piece and is not a real India hook. When in doubt, score it low — India relevance is the gate you \
check FIRST, before judging narrative quality at all.

The goal is maximum reach and engagement on social media, NOT just informing industry insiders of hard news — so \
score for carousel/content-worthiness, not just business seriousness.

Value multiple content types, not only funding/policy news:
- Funding rounds, IPOs, M&A — especially with a clear narrative (comeback, underdog, record-breaking)
- Founder-building lessons and advice — a specific, concrete tactic or hard-won lesson (hiring, scaling, pivoting, \
surviving a near-failure), not generic listicle filler ("5 tips for success")
- Founder stories, pivots, turnarounds, human-interest angles behind a company or entrepreneur
- Milestones and firsts (record-breaking launches, historic achievements, cultural moments)
- Marketing campaigns or culturally resonant business moves
- Policy/regulatory changes — but only ones with a clear before/after stakes story, not routine notices

Judge each item less as "is this important to a professional reader" and more as "does this lend itself to a \
compelling carousel that gives context/history, states the news (or the lesson), explains why it matters or what \
happens next, and ends on a question that sparks debate/comments." Prioritize items with a clear narrative arc and \
mass relatability — someone outside the industry should still find it interesting. De-prioritize routine, same-format \
news repeated across many companies with no distinguishing story (e.g. yet another bank's unremarkable quarterly \
beat with nothing narratively distinct), personal finance tips/explainers, and specialist-only news with no human \
or narrative hook.

Quarterly/annual results specifically: a YoY profit or revenue percentage swing is NOT on its own a distinguishing \
narrative, no matter how large the number looks — swings are common every earnings season and a big percentage is \
often just base-effect math, not a story. Score a results item above 5 ONLY if it carries something beyond the \
number itself: a historic first, a company-defining turnaround (e.g. a near-collapse to recovery arc), a strategic \
pivot investors are debating, or a figure that changes the sector's balance of power. If several results items this \
batch only really differ by which percentage moved, treat them as a cluster the same way you treat duplicates — \
keep your best 0-10 score on the single most exceptional one and score the rest no higher than 4.

IMPORTANT — duplicate detection: many items are the same underlying story covered by multiple outlets (e.g. the \
same IPO filing or earnings report reported by 3-4 different sources). Identify these clusters yourself across \
the ENTIRE list given. Within each duplicate cluster, give your normal 0-10 score to ONLY the single best-written \
version (most complete/most authoritative source), and give every other item in that same cluster a score of 0 \
with reason "duplicate of item N" (referencing the item number you kept).

For each item given (numbered), respond with ONE line per item in this exact format:
N|score|one-line reason
- N is the item number
- score is 0-10 (10 = must-cover, highly shareable carousel material; 0 = irrelevant or duplicate, discard)
- reason is <15 words explaining the score, naming the narrative angle if there is one

Only output these lines, nothing else. One line per item, in the same order given."""


def build_batch_prompt(items, start_idx):
    lines = []
    for i, item in enumerate(items, start=start_idx):
        lines.append(f"{i}. [{item['source']}] {item['title']} — {item['summary'][:200]}")
    return "\n".join(lines)


def call_claude(prompt):
    resp = requests.post(
        API_URL,
        headers={
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODEL,
            "max_tokens": 8000,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=300,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Anthropic API {resp.status_code}: {resp.text[:500]}")
    return resp.json()["content"][0]["text"]


def parse_scores(text, items, start_idx):
    scored = []
    for line in text.strip().splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        try:
            n = int(parts[0].strip())
            score = float(parts[1].strip())
        except ValueError:
            continue
        idx = n - start_idx
        if 0 <= idx < len(items):
            item = dict(items[idx])
            item["score"] = score
            item["reason"] = parts[2].strip()
            scored.append(item)
    return scored


def main():
    if len(sys.argv) > 1:
        digest_path = Path(sys.argv[1])
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        digest_path = DIGESTS_DIR / f"digest_{today}.json"

    digest = json.loads(digest_path.read_text())
    items = digest["items"]
    print(f"Scoring {len(items)} items in batches of {BATCH_SIZE}...")

    all_scored = []
    for start in range(0, len(items), BATCH_SIZE):
        batch = items[start:start + BATCH_SIZE]
        prompt = build_batch_prompt(batch, start + 1)
        text = call_claude(prompt)
        scored = parse_scores(text, batch, start + 1)
        all_scored.extend(scored)
        print(f"  scored {start + 1}-{start + len(batch)} ({len(scored)} parsed)")

    all_scored.sort(key=lambda x: x["score"], reverse=True)
    shortlist = [i for i in all_scored if i["score"] >= 6][:TOP_N]

    out_path = digest_path.with_name(digest_path.stem + "_scored.json")
    out_path.write_text(json.dumps({
        "pillar": digest["pillar"],
        "source_digest": str(digest_path.name),
        "scored_at": datetime.now().isoformat(),
        "total_scored": len(all_scored),
        "shortlist_count": len(shortlist),
        "shortlist": shortlist,
        "all_scored": all_scored,
    }, indent=2))

    print(f"\nWrote shortlist ({len(shortlist)} items, score>=6) to {out_path}\n")
    for item in shortlist:
        print(f"  [{item['score']:.0f}] ({item['category']}/{item['source']}) {item['title']}")
        print(f"        -> {item['reason']}")


if __name__ == "__main__":
    main()
