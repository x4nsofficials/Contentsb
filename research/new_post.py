#!/usr/bin/env python3
"""Full "Generate New Post" pipeline, invoked by server.py's button.

Fetches fresh RSS news, scores it for carousel-worthiness, picks the next story that
hasn't already been turned into a carousel, researches + writes its 5-slide copy
(reusing generate_content.py's Claude+web_search pipeline), generates two distinct
AI images for it (cover + backstory, via OpenAI gpt-image-1 so no chat-session-only
tool is required), renders all 5 slides through carousel_render's shared templates
with no chart/timeline/stat aside (auto-picking a real infographic reliably is out of
scope for an unattended run -- keep it a clean headline+body "none" layout, consistent
with this project's "don't force a component" rule), and appends the result to the
live preview.html.

Can be run standalone (`python3 new_post.py`) or imported and called via `run()`.
"""
import base64
import html
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE.parent / ".env", override=True)

sys.path.insert(0, str(HERE))
from generate_content import call_claude, extract_json, slugify  # noqa: E402
from carousel_render import (  # noqa: E402
    cover_slide, backstory_slide, news_slide, why_slide, engage_slide, render_to_png,
)

DATA_DIR = Path(os.environ.get("DATA_DIR", str(HERE)))
CONTENT_DIR = DATA_DIR / "content"
DIGESTS_DIR = DATA_DIR / "digests"
COVERS_DIR = DATA_DIR / "assets" / "covers"
CODE_OUT = DATA_DIR / "assets" / "code_pilot"
PREVIEW_HTML = DATA_DIR / "preview.html"
CONTENT_DIR.mkdir(parents=True, exist_ok=True)
DIGESTS_DIR.mkdir(parents=True, exist_ok=True)
SCORE_THRESHOLD = 6

IMAGE_STYLE = (
    "Cinematic editorial business-news photograph. Natural lighting, shallow depth of "
    "field, documentary realism, no on-image text, no logos or watermarks, no cartoon "
    "or illustration style. Vertical portrait composition."
)


def _default_log(msg):
    print(f"[new_post] {msg}", flush=True)


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def strip_markup(text):
    return re.sub(r"\*\*(.+?)\*\*", r"\1", text or "")


def existing_slugs():
    slugs = set()
    for p in CONTENT_DIR.glob("content_*.json"):
        m = re.match(r"content_\d{4}-\d{2}-\d{2}_(.+)\.json$", p.name)
        if m:
            slugs.add(m.group(1))
    return slugs


def run_subprocess(args, log):
    log("running: " + " ".join(args))
    result = subprocess.run(
        [sys.executable] + args, cwd=HERE, capture_output=True, text=True, timeout=300,
    )
    if result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            log(f"  {line}")
    if result.returncode != 0:
        stderr = result.stderr.strip()
        log(stderr[-2000:])
        # Pull the last non-empty line of the traceback (the actual exception message,
        # e.g. an Anthropic API error body) so the widget's error banner is diagnosable
        # on its own, not just "exited with code 1".
        last_line = next((ln for ln in reversed(stderr.splitlines()) if ln.strip()), "")
        detail = f": {last_line}" if last_line else ""
        raise RuntimeError(f"{args[0]} failed with exit code {result.returncode}{detail}")


def pick_next_story(log):
    today = today_str()
    log("fetching fresh news (ingest.py)...")
    run_subprocess(["ingest.py"], log)
    log("scoring today's digest (score.py)...")
    run_subprocess(["score.py"], log)

    scored_path = DIGESTS_DIR / f"digest_{today}_scored.json"
    if not scored_path.exists():
        raise RuntimeError(f"expected {scored_path.name} after scoring, not found")
    scored = json.loads(scored_path.read_text())

    done_slugs = existing_slugs()
    seen_links = set()
    candidates = list(scored.get("shortlist", []))
    candidates += [i for i in scored.get("all_scored", []) if (i.get("score") or 0) >= SCORE_THRESHOLD]

    for item in candidates:
        link = item.get("link", "")
        if link and link in seen_links:
            continue
        seen_links.add(link)
        slug = slugify(item["title"])
        if slug in done_slugs:
            continue
        return item, slug

    return None, None


def generate_story_json(item, slug, log):
    log(f"researching + writing copy for: {item['title'][:70]}")
    response = call_claude(item)
    slides = extract_json(response)
    out = {
        "generated_at": datetime.now().isoformat(),
        "source_item": {
            "title": item["title"],
            "source": item.get("source", ""),
            "link": item.get("link", ""),
            "category": item.get("category", ""),
            "score": item.get("score"),
        },
        "slides": slides,
    }
    out_path = CONTENT_DIR / f"content_{today_str()}_{slug}.json"
    out_path.write_text(json.dumps(out, indent=2))
    log(f"wrote {out_path.name}")
    return out


def generate_image(client, prompt, out_path, log):
    log(f"generating image -> {out_path.name}")
    resp = client.images.generate(model="gpt-image-1", prompt=prompt, size="1024x1536", n=1)
    b64 = resp.data[0].b64_json
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(b64))
    return out_path


def generate_images(data, slug, log):
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    s = data["slides"]
    cover_scene = f"{strip_markup(s['slide1_hook']['label'])}. {s['slide1_hook']['subhead']}"
    backstory_scene = (
        f"{strip_markup(s['slide2_backstory'].get('headline', ''))}. {s['slide2_backstory']['body']}"
    )
    cover_prompt = f"{IMAGE_STYLE} Scene: {cover_scene}"
    backstory_prompt = (
        f"{IMAGE_STYLE} This must depict a different, earlier moment in the same story than "
        f"the cover image, a distinct scene, not a repeat of it. Scene: {backstory_scene}"
    )
    cover_path = generate_image(client, cover_prompt, COVERS_DIR / f"{slug}-cover.png", log)
    backstory_path = generate_image(client, backstory_prompt, COVERS_DIR / f"{slug}-backstory.png", log)
    return cover_path, backstory_path


def render_slides(data, slug, cover_bg, backstory_bg, log):
    s = data["slides"]
    out_dir = CODE_OUT / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = []

    inner, css, autofit = cover_slide(
        headline=s["slide1_hook"]["label"], subhead=s["slide1_hook"]["subhead"],
        bg_src=cover_bg, logo_src=None, badge_num=1,
    )
    jobs.append((inner, css, out_dir / f"{slug}-cover.png", autofit))

    inner, css, autofit = backstory_slide(
        label=s["slide2_backstory"]["label"], headline=s["slide2_backstory"]["headline"],
        body=s["slide2_backstory"]["body"], bg_src=backstory_bg, badge_num=2,
    )
    jobs.append((inner, css, out_dir / f"{slug}-backstory.png", autofit))

    # Slides 3-5 now go photo-driven too (bg_src), same cinematic treatment as the cover/
    # backstory slides, instead of switching to a flat cream/orange background partway
    # through the carousel. Reusing the same two generated photos (alternating cover/
    # backstory rather than repeating one back-to-back) keeps this at zero extra image-
    # generation cost -- see news_slide/why_slide/engage_slide's cinematic-mode docstrings.
    inner, css, autofit = news_slide(
        label=s["slide3_news"]["label"], headline=s["slide3_news"]["headline"],
        body=s["slide3_news"]["body"], badge_num=3, bg_src=cover_bg,
    )
    jobs.append((inner, css, out_dir / f"{slug}-news.png", autofit))

    inner, css, autofit = why_slide(
        label=s["slide4_why"]["label"], headline=s["slide4_why"]["headline"],
        bullets=s["slide4_why"]["bullets"], badge_num=4, bg_src=backstory_bg,
    )
    jobs.append((inner, css, out_dir / f"{slug}-why.png", autofit))

    inner, css, autofit = engage_slide(
        label=s["slide5_engage"]["label"], headline=s["slide5_engage"]["headline"],
        cta=s["slide5_engage"]["cta"], badge_num=5, bg_src=cover_bg,
    )
    jobs.append((inner, css, out_dir / f"{slug}-engage.png", autofit))

    for inner, css, out_path, autofit in jobs:
        render_to_png(inner, css, out_path, autofit=autofit)
        log(f"rendered {out_path.relative_to(DATA_DIR)}")

    return out_dir


def append_to_preview(data, slug, item, log):
    html_text = PREVIEW_HTML.read_text()
    # Count ALL story sections, not just the un-id'd original ones -- a plain
    # '<section class="story">' (no id) only matches the original static stories, so
    # counting that literal string alone stopped incrementing after the first
    # pipeline-generated story and re-used its rank number (and id) on every run since.
    rank = len(re.findall(r'<section class="story"', html_text)) + 1
    s = data["slides"]

    def esc(t):
        return html.escape(t or "", quote=True)

    title = esc(item["title"])
    source = esc(item.get("source", ""))
    link = item.get("link", "")
    score = item.get("score", "")

    slide_defs = [
        ("slide1", "cover", strip_markup(s["slide1_hook"]["label"])),
        ("slide2", "backstory", strip_markup(s["slide2_backstory"]["headline"])),
        ("slide3", "news", strip_markup(s["slide3_news"]["headline"])),
        ("slide4", "why", strip_markup(s["slide4_why"]["headline"])),
        ("slide5", "engage", strip_markup(s["slide5_engage"]["headline"])),
    ]
    slides_html = ""
    for cls, kind, alt in slide_defs:
        slides_html += (
            f'    <div class="slide {cls} has-cover has-baked">\n'
            f'      <img class="cover-img baked" src="assets/code_pilot/{slug}/{slug}-{kind}.png" alt="{esc(alt)}">\n'
            f"    </div>\n"
        )

    sources = s.get("sources_used", [])
    sources_html = "".join(
        f'<li><a href="{esc(u)}" target="_blank" rel="noopener">{esc(u)}</a></li>' for u in sources
    )

    section = f"""
<section class="story" id="story-{rank:02d}">
  <div class="story-meta">
    <div>
      <p class="story-rank">Story {rank:02d}</p>
      <p class="story-title">{title}</p>
      <p class="story-src">{source} &middot; <a href="{esc(link)}" target="_blank" rel="noopener">source &#8599;</a></p>
    </div>
    <div class="score-badge">{score}</div>
  </div>

  <p class="scroll-hint">swipe &#8594;</p>
  <div class="row">
{slides_html}  </div>

  <details class="sources">
    <summary>Sources ({len(sources)})</summary>
    <ul>{sources_html}</ul>
  </details>
</section>

"""
    # Newest story goes at the top of the feed (right before the first existing
    # <section class="story">), not the bottom, so it's visible without scrolling.
    match = re.search(r'<section class="story"', html_text)
    if match:
        idx = match.start()
        html_text = html_text[:idx] + section.strip("\n") + "\n\n" + html_text[idx:]
    else:
        html_text = html_text.replace("</body>", section + "</body>")
    html_text = re.sub(
        r"(\d+) carousels", lambda m: f"{int(m.group(1)) + 1} carousels", html_text, count=1,
    )
    PREVIEW_HTML.write_text(html_text)
    log(f"appended Story {rank:02d} to preview.html")
    return rank


def run(log=None):
    log = log or _default_log
    item, slug = pick_next_story(log)
    if item is None:
        log("no new not-yet-published story found above the score threshold right now")
        return {"ok": True, "new_story": False}

    log(f"next story: {item['title']} (score {item.get('score')})")
    data = generate_story_json(item, slug, log)
    cover_bg, backstory_bg = generate_images(data, slug, log)
    out_dir = render_slides(data, slug, cover_bg, backstory_bg, log)
    rank = append_to_preview(data, slug, item, log)

    slide_files = [f"assets/code_pilot/{slug}/{slug}-{k}.png" for k in ("cover", "backstory", "news", "why", "engage")]
    log("done")
    return {
        "ok": True,
        "new_story": True,
        "slug": slug,
        "rank": rank,
        "title": item["title"],
        "score": item.get("score"),
        "source": item.get("source", ""),
        "link": item.get("link", ""),
        "slides": slide_files,
        "out_dir": str(out_dir.relative_to(DATA_DIR)),
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
