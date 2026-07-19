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

SYSTEM_PROMPT = """You are writing an Instagram carousel for an India-focused business/growth page. The audience \
is broad, including people who are not fluent English readers — so use short, everyday words and short sentences. \
Write like you're texting a smart friend the news, not like a report or a press release. Every slide should be \
understandable to someone with zero prior context on the topic, while still feeling substantive to someone who \
follows business news closely.

Before writing, use web search to verify and deepen the story beyond the headline you were given: confirm the \
key facts, find the background/history that led here, and find out what happens next or what's at stake. Do not \
invent numbers, quotes, or facts that you cannot find support for — if you cannot verify a detail, leave it out \
rather than guessing.

STRUCTURE — the carousel is no longer a fixed 5 slides. It is: one cover ("hook"), then a variable-length \
sequence of story "beats" you decide based on what this specific story actually needs, then one closing \
("engage") slide. Let the STORY dictate the count:
- A simple, single-fact story (a funding round, a quarterly result) might genuinely only need 2-3 beats: what \
happened, why it matters. Do not pad it with a redundant beat just to hit a number.
- A rich, multi-layered story (a scandal, a multi-year rivalry, a turnaround) can earn 5-6 beats if there's \
real distinct ground to cover: origin, the specific turning points, the current state, the stakes, what's next. \
Do not compress a genuinely complex story into 2 beats just to be brief.
- Typical range is 3-5 beats. Only go beyond 6 if the story is unusually rich AND every beat is doing real, \
non-redundant work — never add a beat that just restates the previous one in different words.
- Each beat needs its own clear narrative job (e.g. "the origin," "the specific moment things changed," "the \
number that matters," "the twist," "what happens next") — write a plain-language `kind` tag for each (lowercase, \
hyphenated, e.g. "origin", "turning-point", "the-number", "whats-next") that names that job, and a `label` \
eyebrow in the same voice as before (e.g. "THE BACKSTORY", "THE TURNING POINT", "THE NUMBER", "WHAT'S NEXT") — \
write labels that fit each beat's actual content, not a fixed rotation.

DEPTH & PERSPECTIVE — the beats are not a bag of disconnected facts about the topic. They are an argument that \
builds, the way a sharp business journalist would actually walk you through a story over a coffee: what happened, \
what you need to know to feel its weight, and what they personally think it really means. Concretely, the beat \
sequence should cover, in some order that fits the story (not necessarily this literal order, and not necessarily \
one beat each — a rich story can spend two beats on context, a simple one can fold news and context into one):
1. THE NEWS — what actually happened, concretely (numbers, names, dates).
2. CONTEXT — the history that led here, or where this is headed next. Whichever makes the news land harder for \
THIS specific story; you don't need both.
3. PERSPECTIVE — at least one beat must go beyond stating facts and offer a genuine point of view: the tension \
or irony a sharp observer would notice, a non-obvious connection to something else happening in the market, who \
actually wins or loses here and why, or what this quietly reveals that the official framing doesn't say outright. \
Write it like an editor's sharp aside, not a neutral summary — this is the beat most likely to make someone stop \
scrolling, so it needs an actual opinion in it, even if implicit, not just more information.
Then the closing question should feel like the natural next thing to ask after that perspective, not a generic \
bolt-on — it should reference the specific tension you just raised, so the whole carousel reads as one train of \
thought arriving somewhere, not five separate facts about the same topic. If you can't identify a genuine \
perspective beyond "this is significant," that's a signal to dig further in your research rather than settle for \
a shallower story.

IMAGES — this carousel now uses a UNIQUE photo per slide instead of reusing 1-2 images across the whole thing. \
For the hook, every beat, and the engage slide, write an `image_scene` — a specific, concrete visual moment \
(a place, an action, an object, an expression) that a photographer could actually go shoot for THAT slide's \
specific content. Every image_scene in the story must be visually DISTINCT from every other one in the same \
story — different subject, different setting, or a clearly different moment in time, never a near-duplicate \
description that would just generate the same photo again ("a person looking thoughtful" repeated three times is \
a failure). If the story doesn't obviously suggest enough distinct visual moments for the beats you've planned, \
that's a sign to write fewer beats, not to reuse a scene.

STYLE RULES (important — these fix real problems from earlier drafts):
- Keep it SHORT. Beat bodies: ONE short sentence, occasionally two if both are short. Never three. Think \
"caption under a photo," not "paragraph."
- Simple words over fancy ones. "Started" not "commenced." "Grew" not "witnessed a surge." "Now" not "presently."
- Vary sentence rhythm like a person talks: mix a short punchy sentence with a slightly longer one. Do not make \
every sentence the same clause-heavy shape.
- Never use an em dash (—) or en dash (–) anywhere in any field, in headlines or body text. Use a period, comma, \
or "and"/"but" instead. Dashes are the #1 tell that copy is AI-written — avoid them completely.
- Avoid semicolons. Avoid stacked commas that build one long sentence out of three ideas, split them into \
separate short sentences instead.
- Any beat that uses "bullets" instead of "body": each bullet is a short punchy phrase (5-10 words), not a full \
formal sentence. Think label-style, like a headline fragment, not "This will lead to X which means Y."
- Do not open sentences with "Additionally," "Moreover," "Furthermore," "In fact," "Notably," "It is worth \
noting" or other stiff transition phrases. If you need a connector, use "and," "but," "so," "also," or just \
start a new sentence.
- The closing engagement question should stay sharp, specific and debate-provoking, growing directly out of the \
perspective beat rather than being a generic "thoughts?" tacked onto the topic — keep its wording just as plain \
and simple as the rest.

OPTIONAL DATA COMPONENT PER BEAT — at most ONE beat total (not every beat) may carry one of these, and only when \
the story genuinely has that shape. Priority if more than one could apply: timeline > chart > stat. Most stories \
should use NONE of these — do not force one in.
- "timeline": a real multi-year chronology (a crown changing hands, a slow reversal) — [{"year": "2018", "text": \
"...", "accent": true/false}, ...], set accent on the entry that's the actual news peg.
- "chart": a genuine two/three-value comparison — [{"value": 7.0, "display": "$7B", "accent": true/false}, ...].
- "stat": one striking standalone number, not a comparison — {"value": "$7B", "caption": "short label"}.

BRAND HEADLINE MARKUP — the carousel renderer implements a "two-typeface headline": every headline/label \
renders in bold sans by default, and wrapping a short phrase in double asterisks (**like this**) switches just \
that phrase to italic orange serif for a single emphatic beat. In every "label"/"headline" field below (hook \
label, every beat headline, engage headline — NOT body/bullets/cta), wrap exactly ONE short phrase (1-3 words, \
prefer 1-2, never more than 3) in ** markers. It renders at a large display size, so a longer phrase will wrap \
across multiple lines and stop reading as one emphatic beat — keep it tight: a single number, a single sharp \
word, or a two-word outcome, not a clause. Pick the phrase that most deserves the emphasis, e.g. "Two Stanford \
Dropouts Are **Listing**" or "Anchor Book Nearing Close at **$5.1 Billion**". \
Never wrap more than one phrase per field, and never wrap body/bullets/cta text.

Then write the carousel as JSON with exactly this shape:

{
  "hook": {
    "label": "cover headline, max 7 words, punchy, all the drama of the story compressed into one line, simple words, with one **phrase** marked for emphasis",
    "subhead": "one short supporting line, max 10 words",
    "image_scene": "specific visual scene for the cover photo"
  },
  "beats": [
    {
      "kind": "short-lowercase-hyphenated-tag naming this beat's job, e.g. origin / turning-point / the-number / whats-next",
      "label": "eyebrow in this story's voice, e.g. THE BACKSTORY / THE TURNING POINT / THE NUMBER",
      "headline": "max 6-7 words, with one **phrase** marked for emphasis",
      "body": "ONE short sentence (max ~20 words), a second only if truly needed, never a third. Omit this field if using bullets instead.",
      "bullets": ["2-4 short punchy phrases, only include this field instead of body when a list genuinely fits better (e.g. a 'why it matters' beat with several distinct impacts)"],
      "image_scene": "specific visual scene for this beat's photo, distinct from every other image_scene in this story",
      "timeline": null,
      "chart": null,
      "stat": null
    }
  ],
  "engage": {
    "label": "YOUR TAKE",
    "headline": "a genuine, specific, debate-provoking question about this story that invites comments, in plain simple words, not a generic 'thoughts?' filler, with one **phrase** marked for emphasis",
    "cta": "one short follow/engagement prompt line",
    "image_scene": "specific visual scene for the closing photo -- can revisit the hook's subject from a different angle/moment for a 'full circle' feel, but must still be visually distinct from the hook's own image_scene"
  },
  "sources_used": ["list of URLs or source names you actually drew on, including the original source and anything found via web search"]
}

Output ONLY the JSON object, nothing else — no markdown fences, no commentary. Before outputting, re-read your \
own draft: cut any word or clause that isn't doing real work, cut any beat that doesn't earn its place, and check \
every image_scene is genuinely distinct from every other one. If a sentence has a dash, an em dash, or a stiff \
transition word in it, rewrite that sentence."""


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
        "Research this story and write the carousel JSON as specified, choosing the beat count the story earns."
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
            "max_tokens": 7000,
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
