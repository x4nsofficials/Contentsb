#!/usr/bin/env python3
"""One-off driver: render the Zepto pilot's 5 slides through carousel_render's editorial-pass
templates (magazine folio instead of a badge, flat hairline logo plate on the cover, ghost-italic
numeral graphic anchors, a cream two-column "reading page" for the backstory/news/why beats, and
a real flat bar-chart infographic for the valuation drop on the news slide) so the result can be
reviewed against the prior pass before scaling to the rest of the stories."""
import json
from pathlib import Path

from carousel_render import (
    cover_slide, backstory_slide, news_slide, why_slide, engage_slide, render_to_png,
)

HERE = Path(__file__).parent
CONTENT = HERE / "content" / "content_2026-07-18_zepto-ipo-anchor-book-nears-closure-norges-motilal-oswal-may.json"
OUT = HERE / "assets" / "code_pilot"

data = json.loads(CONTENT.read_text())
s = data["slides"]
STORY_NUM = 1

ZEPTO_LOGO = HERE / "assets" / "real" / "zepto-logo-clean.png"
COVER_BG = HERE / "assets" / "covers" / "zepto-night-delivery.png"
FOUNDER_PHOTO = HERE / "assets" / "real" / "aadit-palicha-composited.jpg"

# This pilot's content JSON predates the **phrase** accent-markup convention (now baked
# into generate_content.py's prompt for all future stories), so retrofit it here by hand
# to demonstrate the brand guide's "two-typeface headline" signature element: bold sans
# base copy with a single italic-orange Playfair phrase for emphasis.
HEADLINES = {
    "slide1_label": "Two Stanford Dropouts Are **About to List**",
    "slide2_headline": "From Lockdown Grocery Problem to **Unicorn**",
    "slide3_headline": "Anchor Book Nearing Close at **$5.1 Billion**",
    "slide4_headline": "First Pure-Play **Quick Commerce IPO** in India",
    "slide5_headline": (
        "Zepto is going public at $5.1 billion, nearly $2 billion below its valuation "
        "from months ago. Is that a healthy reality check, or a **warning sign** for "
        "quick commerce?"
    ),
}

# The second signature element from the brand guide: a press/proof bar of real outlet
# names. Built from this story's own sources_used (already captured during research) so
# credibility becomes a visible design element instead of a hidden citation list.
PROOF_NAMES = ["Economic Times", "CNBC", "Wikipedia"]
PROOF_EXTRA = max(0, len(s["sources_used"]) - len(PROOF_NAMES))

# The explicitly-requested "graphs / visual infographics" element: a real flat bar chart
# on the news slide, visualizing the valuation drop that the story is actually about.
VALUATION_CHART = [
    {"value": 7.0, "display": "$7B", "caption": "months ago"},
    {"value": 5.1, "display": "$5.1B", "caption": "anchor book now", "accent": True},
]

# Rewritten copy pass: deeper, more cinematic/analytical voice than the flat fact-recitation
# of the source JSON, per the "no template, no forced infographics, more critical thinking"
# feedback. Grounded in the same facts as the original JSON, just told with more narrative
# tension and sharper analysis. Overrides the source JSON body/bullets at render time only;
# the JSON itself is untouched.
BODIES = {
    "slide2_body": (
        "In 2020, two Stanford freshmen stuck in Mumbai lockdown watched their families "
        "struggle to get groceries and decided the problem was solvable in minutes, not "
        "hours. Aadit Palicha and Kaivalya Vohra dropped out, renamed their app Zepto, and "
        "built dark stores dense enough to promise delivery before the milk went warm. By "
        "2023, that promise had made them India's youngest unicorn founders."
    ),
    "slide3_body": (
        "Zepto's ₹11,000 crore anchor book is nearly locked, with sovereign fund Norges and "
        "Motilal Oswal alone set to absorb 40-45% of it. But the price they're paying tells "
        "the real story: $5.1 billion, nearly $2 billion below the $7 billion tag Zepto "
        "carried just months ago."
    ),
    "slide4_bullets": [
        "India's first pure-play quick-commerce IPO, so there's no local playbook to follow",
        "A $2 billion haircut is the market openly pricing growth-at-any-cost lower than it did a year ago",
        "Whatever multiple Zepto lists at becomes the reference price for Blinkit and Instamart's own listings",
    ],
    "slide5_headline": (
        "Zepto is going public at $5.1 billion, nearly $2 billion below what it was worth "
        "months ago. Is that the market finally pricing quick commerce like a real "
        "**business**, or the first crack in India's hottest consumer sector?"
    ),
}

jobs = []

inner, css, autofit = cover_slide(
    headline=HEADLINES["slide1_label"],
    subhead=s["slide1_hook"]["subhead"],
    bg_src=COVER_BG,
    logo_src=ZEPTO_LOGO,
    story_num=STORY_NUM,
    badge_num=1,
)
jobs.append((inner, css, OUT / "zepto-cover.png", autofit))

inner, css, autofit = backstory_slide(
    label=s["slide2_backstory"]["label"],
    headline=HEADLINES["slide2_headline"],
    body=BODIES["slide2_body"],
    bg_src=FOUNDER_PHOTO,
    story_num=STORY_NUM,
    badge_num=2,
)
jobs.append((inner, css, OUT / "zepto-backstory.png", autofit))

inner, css, autofit = news_slide(
    label=s["slide3_news"]["label"],
    headline=HEADLINES["slide3_headline"],
    body=BODIES["slide3_body"],
    story_num=STORY_NUM,
    badge_num=3,
    proof=(PROOF_NAMES, PROOF_EXTRA),
    chart=VALUATION_CHART,
    chart_caption="Zepto's IPO valuation, in one story",
)
jobs.append((inner, css, OUT / "zepto-news.png", autofit))

inner, css, autofit = why_slide(
    label=s["slide4_why"]["label"],
    headline=HEADLINES["slide4_headline"],
    bullets=BODIES["slide4_bullets"],
    story_num=STORY_NUM,
    badge_num=4,
    stat=("₹11,000 Cr", "Total IPO Size"),
)
jobs.append((inner, css, OUT / "zepto-why.png", autofit))

inner, css, autofit = engage_slide(
    label=s["slide5_engage"]["label"],
    headline=BODIES["slide5_headline"],
    cta=s["slide5_engage"]["cta"],
    story_num=STORY_NUM,
    badge_num=5,
)
jobs.append((inner, css, OUT / "zepto-engage.png", autofit))

for inner, css, out_path, autofit in jobs:
    render_to_png(inner, css, out_path, autofit=autofit)
    print(f"-> {out_path}")

print("done")
