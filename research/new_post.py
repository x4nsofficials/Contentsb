#!/usr/bin/env python3
"""Full "Generate New Post" pipeline, invoked by server.py's button.

Fetches fresh RSS news, scores it for carousel-worthiness, picks the next story that
hasn't already been turned into a carousel, researches + writes its copy (reusing
generate_content.py's Claude+web_search pipeline) -- a cover ("hook"), a variable-length
sequence of story "beats" Claude decides the count/shape of based on what the story
actually needs, and a closing ("engage") slide. Generates ONE distinct AI image per
slide (via OpenAI gpt-image-1) instead of reusing 1-2 photos across the whole carousel,
renders every slide through carousel_render's shared templates, and appends the result
to the live preview.html.

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
    cover_slide, story_beat_slide, engage_slide, render_batch_to_png,
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


def _beat_kind(beat, pos):
    raw = beat.get("kind") or f"beat-{pos}"
    kind = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    return kind or f"beat-{pos}"


def slide_specs(s):
    """Flatten hook + beats + engage into an ordered list of (position, name, spec)
    where `name` (e.g. "01-cover", "03-turning-point", "06-engage") is the shared key
    used for both the raw generated background (COVERS_DIR) and the final rendered PNG
    (CODE_OUT) -- numbered so a plain filename sort always gives the right slide order,
    unlike the old fixed slide1..slide5 naming which broke once slide count varied."""
    beats = s["beats"]
    total = len(beats) + 2
    specs = [(1, "01-cover", "hook", s["hook"])]
    for i, beat in enumerate(beats, start=2):
        specs.append((i, f"{i:02d}-{_beat_kind(beat, i)}", "beat", beat))
    specs.append((total, f"{total:02d}-engage", "engage", s["engage"]))
    return specs


def generate_image(client, prompt, out_path, log):
    log(f"generating image -> {out_path.name}")
    resp = client.images.generate(model="gpt-image-1", prompt=prompt, size="1024x1536", n=1)
    b64 = resp.data[0].b64_json
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(b64))
    return out_path


def generate_images(data, slug, log):
    """One distinct AI image per slide (hook, every beat, engage) instead of reusing 1-2
    photos across the whole carousel -- each call gets that slide's own `image_scene`
    plus an explicit "must be visually distinct from the others in this sequence"
    instruction, since gpt-image-1 doesn't see the other prompts in the same story.
    Fired concurrently (bounded pool) rather than one at a time -- with up to 7-8 images
    per story now instead of a fixed 2, sequential generation was the single biggest
    contributor to "generate new post" taking too long; each call is an independent
    network request, so there's no reason to wait for one to finish before starting the
    next."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    s = data["slides"]
    specs = slide_specs(s)

    def build_prompt(role, spec):
        scene = spec.get("image_scene", "")
        role_desc = {
            "hook": "the cover / opening shot of a multi-image carousel telling one story",
            "beat": f"an inside shot of the same carousel story (beat: {spec.get('label', '')})",
            "engage": "the closing shot of the same carousel story",
        }[role]
        return (
            f"{IMAGE_STYLE} This is {role_desc}. It must be visually distinct from every "
            f"other image in this same story sequence, a different subject, setting, or "
            f"moment, not a near-repeat. Scene: {scene}"
        )

    paths = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_name = {
            executor.submit(
                generate_image, client, build_prompt(role, spec), COVERS_DIR / f"{slug}-{name}.png", log,
            ): name
            for pos, name, role, spec in specs
        }
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            paths[name] = future.result()
    return paths


def render_slides(data, slug, image_paths, log):
    s = data["slides"]
    out_dir = CODE_OUT / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    specs = slide_specs(s)
    total = len(specs)
    jobs = []

    for pos, name, role, spec in specs:
        bg_src = image_paths[name]
        if role == "hook":
            inner, css, autofit = cover_slide(
                headline=spec["label"], subhead=spec["subhead"],
                bg_src=bg_src, logo_src=None, badge_num=pos, total=total,
            )
        elif role == "engage":
            inner, css, autofit = engage_slide(
                label=spec.get("label", "YOUR TAKE"), headline=spec["headline"], cta=spec["cta"],
                badge_num=pos, total=total, bg_src=bg_src,
            )
        else:
            stat = spec.get("stat")
            inner, css, autofit = story_beat_slide(
                kind=_beat_kind(spec, pos), label=spec.get("label", ""), headline=spec["headline"],
                bg_src=bg_src, body=spec.get("body"), bullets=spec.get("bullets"),
                stat=(stat["value"], stat["caption"]) if stat else None,
                chart=spec.get("chart"), timeline=spec.get("timeline"),
                badge_num=pos, total=total,
            )
        jobs.append((inner, css, out_dir / f"{slug}-{name}.png", autofit))

    # One shared browser instance for the whole batch instead of launching/closing
    # Chromium per slide -- render_batch_to_png logs each slide as it completes.
    render_batch_to_png(jobs, log=lambda msg: log(msg))

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

    slides_html = ""
    for pos, name, role, spec in slide_specs(s):
        alt = strip_markup(spec.get("headline") or spec.get("label") or "")
        slides_html += (
            f'    <div class="slide slide{pos} has-cover has-baked">\n'
            f'      <img class="cover-img baked" src="assets/code_pilot/{slug}/{slug}-{name}.png" alt="{esc(alt)}">\n'
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
    image_paths = generate_images(data, slug, log)
    out_dir = render_slides(data, slug, image_paths, log)
    rank = append_to_preview(data, slug, item, log)

    slide_files = [f"assets/code_pilot/{slug}/{slug}-{name}.png" for _, name, _, _ in slide_specs(data["slides"])]
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
