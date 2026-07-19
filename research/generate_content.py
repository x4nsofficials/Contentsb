#!/usr/bin/env python3
"""Turn a shortlisted story into carousel-ready slide copy: backstory -> news -> why it matters -> engagement question.

Uses Claude with the web_search server tool to deepen research beyond the RSS summary (history, stakes, what's
next) before writing copy, matching the "research first, don't just restate the headline" requirement.
"""
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE.parent / ".env", override=True)

DATA_DIR = Path(os.environ.get("DATA_DIR", str(HERE)))
DIGESTS_DIR = DATA_DIR / "digests"
CONTENT_DIR = DATA_DIR / "content"
CONTENT_DIR.mkdir(parents=True, exist_ok=True)

API_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com") + "/v1/messages"
API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = "claude-sonnet-4-6"
TOP_N_DEFAULT = 5

SYSTEM_PROMPT = """You are writing a 5-slide Instagram carousel for an India-focused business/growth page. \
The audience is broad, including people who are not fluent English readers — so use short, everyday words and \
short sentences. Write like you're texting a smart friend the news, not like a report or a press release. \
Every slide should be understandable to someone with zero prior context on the topic, while still feeling \
substantive to someone who follows business news closely.

Before writing, use web search to verify and deepen the story beyond the headline you were given: confirm the \
key facts, find the background/history that led here, and find out what happens next or what's at stake. Do not \
invent numbers, quotes, or facts that you cannot find support for — if you cannot verify a detail, leave it out \
rather than guessing.

STYLE RULES (important — these fix real problems from earlier drafts):
- Keep it SHORT. Slides 2 and 3 bodies: ONE short sentence, occasionally two if both are short. Never three. \
Think "caption under a photo," not "paragraph."
- Simple words over fancy ones. "Started" not "commenced." "Grew" not "witnessed a surge." "Now" not "presently."
- Vary sentence rhythm like a person talks: mix a short punchy sentence with a slightly longer one. Do not make \
every sentence the same clause-heavy shape.
- Never use an em dash (—) or en dash (–) anywhere in any field, in headlines or body text. Use a period, comma, \
or "and"/"but" instead. Dashes are the #1 tell that copy is AI-written — avoid them completely.
- Avoid semicolons. Avoid stacked commas that build one long sentence out of three ideas, split them into \
separate short sentences instead.
- slide4_why "bullets": each bullet is a short punchy phrase (5-10 words), not a full formal sentence. Think \
label-style, like a headline fragment, not "This will lead to X which means Y."
- Do not open sentences with "Additionally," "Moreover," "Furthermore," "In fact," "Notably," "It is worth \
noting" or other stiff transition phrases. If you need a connector, use "and," "but," "so," "also," or just \
start a new sentence.
- The slide5 engagement question should stay sharp, specific and debate-provoking (that part is working well) \
but keep its wording just as plain and simple as the rest.

BRAND HEADLINE MARKUP — the carousel renderer implements a "two-typeface headline": every headline/label \
renders in bold sans by default, and wrapping a short phrase in double asterisks (**like this**) switches just \
that phrase to italic orange serif for a single emphatic beat. In every "label"/"headline" field below (slide1 \
label, slide2/3/4 headline, slide5 headline — NOT body/bullets/cta), wrap exactly ONE short phrase (1-3 words, \
prefer 1-2, never more than 3) in ** markers. It renders at a large display size, so a longer phrase will wrap \
across multiple lines and stop reading as one emphatic beat — keep it tight: a single number, a single sharp \
word, or a two-word outcome, not a clause. Pick the phrase that most deserves the emphasis, e.g. "Two Stanford \
Dropouts Are **Listing**" or "Anchor Book Nearing Close at **$5.1 Billion**". \
Never wrap more than one phrase per field, and never wrap body/bullets/cta text.

Then write a 5-slide carousel as JSON with exactly this shape:

{
  "slide1_hook": {
    "label": "cover headline, max 7 words, punchy, all the drama of the story compressed into one line, simple words, with one **phrase** marked for emphasis",
    "subhead": "one short supporting line, max 10 words"
  },
  "slide2_backstory": {
    "label": "THE BACKSTORY",
    "headline": "max 6 words, with one **phrase** marked for emphasis",
    "body": "ONE short sentence (max ~20 words) of plain history/context — what was true before this, so the news lands with full weight. A second short sentence only if truly needed, never a third."
  },
  "slide3_news": {
    "label": "THE UPDATE",
    "headline": "max 6 words, with one **phrase** marked for emphasis",
    "body": "ONE short sentence stating exactly what just happened, concretely (numbers, names, dates where relevant). A second short sentence only if truly needed, never a third."
  },
  "slide4_why": {
    "label": "WHY IT MATTERS",
    "headline": "max 7 words, outcome-focused, with one **phrase** marked for emphasis",
    "bullets": ["2-3 short punchy phrases (5-10 words each) on real-world impact or what happens next"]
  },
  "slide5_engage": {
    "label": "YOUR TAKE",
    "headline": "a genuine, specific, debate-provoking question about this story that invites comments, in plain simple words, not a generic 'thoughts?' filler, with one **phrase** marked for emphasis",
    "cta": "one short follow/engagement prompt line"
  },
  "sources_used": ["list of URLs or source names you actually drew on, including the original source and anything found via web search"]
}

Output ONLY the JSON object, nothing else — no markdown fences, no commentary. Before outputting, re-read your \
own draft and cut any word or clause that isn't doing real work. If a sentence has a dash, an em dash, or a \
stiff transition word in it, rewrite that sentence."""


def slugify(title):
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:60]


def call_claude(item):
    prompt = (
        f"Source: {item['source']}\n"
        f"Title: {item['title']}\n"
        f"Summary: {item['summary']}\n"
        f"Link: {item.get('link', '')}\n"
        f"Category: {item.get('category', '')}\n"
        f"Why this was shortlisted: {item.get('reason', '')}\n\n"
        "Research this story and write the 5-slide carousel JSON as specified."
    )
    resp = requests.post(
        API_URL,
        headers={
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODEL,
            "max_tokens": 4000,
            "system": SYSTEM_PROMPT,
            "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=180,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Anthropic API {resp.status_code}: {resp.text[:500]}")
    return resp.json()


def extract_json(response):
    text_blocks = [b["text"] for b in response["content"] if b.get("type") == "text"]
    full_text = "\n".join(text_blocks)
    match = re.search(r"\{.*\}", full_text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in response text:\n{full_text}")
    return json.loads(match.group(0))


def main():
    args = sys.argv[1:]
    if args and args[0].endswith(".json"):
        scored_path = Path(args[0])
        args = args[1:]
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        scored_path = DIGESTS_DIR / f"digest_{today}_scored.json"

    scored = json.loads(scored_path.read_text())
    shortlist = scored["shortlist"]

    if args:
        indices = [int(a) - 1 for a in args]
    else:
        indices = list(range(min(TOP_N_DEFAULT, len(shortlist))))

    today = datetime.now().strftime("%Y-%m-%d")
    written = []

    for idx in indices:
        item = shortlist[idx]
        print(f"[{idx + 1}] Researching + writing: {item['title'][:70]}...")
        try:
            response = call_claude(item)
            slides = extract_json(response)
        except Exception as e:
            print(f"    FAILED: {e}")
            continue

        out = {
            "generated_at": datetime.now().isoformat(),
            "source_item": {
                "title": item["title"],
                "source": item["source"],
                "link": item.get("link", ""),
                "category": item.get("category", ""),
                "score": item.get("score"),
            },
            "slides": slides,
        }
        slug = slugify(item["title"])
        out_path = CONTENT_DIR / f"content_{today}_{slug}.json"
        out_path.write_text(json.dumps(out, indent=2))
        written.append(out_path)
        print(f"    -> {out_path.name}")

    print(f"\nWrote {len(written)} content piece(s) to {CONTENT_DIR}/")


if __name__ == "__main__":
    main()
