#!/usr/bin/env python3
"""Build a static local HTML preview of all generated carousel content pieces (text-only, pre-image-gen).

Styled to the StoryB brand system (colors/fonts pulled from
/Users/anshulmishra/Downloads/StoryB Home Page.html):
  ink/bg:      #0B0B0C (--ink)
  brand orange:#E9480F (--orange-500), gradient #F26A2E -> #E9480F -> #DA3C06
  paper/cream: #FAF8F6 / #F3F0EC / #E7E2DC (--warm-50/100/200)
  display font: 'Playfair Display' (serif, headlines)
  body/UI font: 'Hanken Grotesk' (sans, everything else)
"""
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
CONTENT_DIR = HERE / "content"


def load_pieces():
    pieces = []
    for f in sorted(CONTENT_DIR.glob("content_*.json")):
        try:
            data = json.loads(f.read_text())
            data["_file"] = f.name
            pieces.append(data)
        except Exception as e:
            print(f"skip {f.name}: {e}")
    pieces.sort(key=lambda p: p.get("source_item", {}).get("score") or 0, reverse=True)
    return pieces


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>StoryB — Business & Markets India — Content Preview</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;0,800;1,600&family=Hanken+Grotesk:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {{
    --ink: #0B0B0C;
    --warm-900: #141211;
    --warm-700: #3B3532;
    --warm-500: #7C736B;
    --warm-300: #D3CCC4;
    --warm-200: #E7E2DC;
    --warm-100: #F3F0EC;
    --warm-50:  #FAF8F6;
    --white: #FFFFFF;
    --orange-500: #E9480F;
    --orange-400: #EE6E3A;
    --orange-600: #D33C08;
    --orange-100: #FCE2D6;
    --brand-gradient: linear-gradient(135deg, #F26A2E 0%, #E9480F 48%, #DA3C06 100%);
    --font-serif: 'Playfair Display', 'Times New Roman', Georgia, serif;
    --font-sans: 'Hanken Grotesk', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  }}
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html {{ -webkit-text-size-adjust: 100%; }}
  body {{ background: var(--ink); color: var(--white); font-family: var(--font-sans); padding: 32px 20px 100px; }}
  @media (min-width: 640px) {{ body {{ padding: 48px 40px 100px; }} }}

  .page-header {{ display: flex; align-items: center; gap: 14px; margin-bottom: 8px; flex-wrap: wrap; }}
  .page-logo {{ height: 26px; width: auto; display: block; }}
  .page-title {{ font-size: 15px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: rgba(255,255,255,0.55); border-left: 1px solid rgba(255,255,255,0.2); padding-left: 14px; }}
  .page-sub {{ font-size: 12.5px; color: rgba(255,255,255,0.4); margin-top: 10px; }}

  .story {{ margin-bottom: 56px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 26px; }}
  .story-meta {{ display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 18px; gap: 16px; }}
  .story-rank {{ font-size: 10.5px; font-weight: 700; letter-spacing: 2px; color: var(--orange-400); text-transform: uppercase; }}
  .story-title {{ font-size: 16px; font-weight: 600; color: #fff; margin-top: 4px; max-width: 640px; line-height: 1.35; }}
  .story-src {{ font-size: 11px; color: rgba(255,255,255,0.4); margin-top: 6px; }}
  .story-src a {{ color: rgba(255,255,255,0.5); text-decoration: none; border-bottom: 1px dotted rgba(255,255,255,0.25); }}
  .score-badge {{ flex-shrink: 0; background: rgba(233,72,15,0.15); border: 1px solid rgba(233,72,15,0.4); color: var(--orange-400);
    font-size: 18px; font-weight: 700; padding: 6px 13px; border-radius: 10px; }}

  /* Slides: horizontal snap-scroll strip on every screen size. This is the fix for the
     mobile "cropped" bug — cards no longer force a fixed aspect-ratio + overflow:hidden
     (which clipped long copy on narrow viewports). Instead each card has a natural,
     content-driven height and the row scrolls sideways like a real IG carousel. */
  .row {{
    display: flex;
    gap: 12px;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    padding-bottom: 6px;
    -webkit-overflow-scrolling: touch;
  }}
  .row::-webkit-scrollbar {{ height: 6px; }}
  .row::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.15); border-radius: 4px; }}

  .slide {{
    position: relative;
    scroll-snap-align: start;
    flex: 0 0 78vw;
    max-width: 300px;
    min-height: 340px;
    background: var(--warm-50);
    border-radius: 16px;
    padding: 20px 18px 18px;
    display: flex;
    flex-direction: column;
  }}
  @media (min-width: 640px) {{ .slide {{ flex-basis: 240px; }} }}
  @media (min-width: 1100px) {{ .slide {{ flex-basis: calc(20% - 10px); }} }}

  .slide-num {{ position: absolute; top: 10px; right: 14px; font-size: 38px; font-weight: 800; color: rgba(20,18,17,0.06); line-height: 1; font-family: var(--font-serif); z-index: 2; }}
  .slide-label {{ font-size: 10px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: var(--orange-500); margin-bottom: 10px; }}
  .slide-headline {{ font-family: var(--font-serif); font-weight: 700; color: var(--warm-900); line-height: 1.22; margin-bottom: 8px; }}
  .slide1 .slide-headline {{ font-size: 20px; }}

  /* Cover slide with a generated hero image: photo fills the card, a bottom-up dark
     gradient (matches the brand's --img-warm-overlay token) protects text legibility,
     and headline/label/subhead sit on top in white instead of the cream-card ink. */
  .slide.has-cover {{ background: var(--warm-900); justify-content: flex-end; }}
  .slide.has-cover .cover-img {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; z-index: 0; }}
  .slide.has-cover .cover-scrim {{ position: absolute; inset: 0; background: linear-gradient(180deg, rgba(11,11,12,0) 35%, rgba(11,11,12,0.9) 100%); z-index: 1; }}
  .slide.has-cover .slide-label, .slide.has-cover .slide-num {{ position: relative; z-index: 2; color: var(--orange-400); }}
  .slide.has-cover .slide-headline {{ position: relative; z-index: 2; color: #fff; }}
  .slide.has-cover .slide-sub, .slide.has-cover .slide-body {{ position: relative; z-index: 2; color: rgba(255,255,255,0.7); }}
  .slide.has-cover .slide-bullets {{ position: relative; z-index: 2; color: rgba(255,255,255,0.85); }}
  .slide.has-cover .slide-cta {{ position: relative; z-index: 2; color: var(--orange-400); }}

  /* Fully-baked Canva slide: the exported PNG already contains all headline/logo/badge/footer
     pixels, so the card becomes a pure image frame with zero HTML text overlay and no padding. */
  .slide.has-baked {{ padding: 0; overflow: hidden; }}
  .slide.has-baked .cover-img.baked {{ position: static; width: 100%; height: 100%; object-fit: cover; display: block; }}
  .slide2 .slide-headline, .slide3 .slide-headline, .slide4 .slide-headline {{ font-size: 16px; }}
  .slide5 .slide-headline {{ font-size: 16px; }}
  .slide-rule {{ width: 30px; height: 3px; background: var(--brand-gradient); margin-bottom: 10px; border-radius: 2px; }}
  .slide-body {{ font-size: 13px; color: var(--warm-700); line-height: 1.5; }}
  .slide-sub {{ font-size: 13px; color: var(--warm-500); line-height: 1.45; }}
  .slide-bullets {{ list-style: none; font-size: 12.5px; color: var(--warm-700); line-height: 1.5; }}
  .slide-bullets li {{ margin-bottom: 7px; padding-left: 14px; position: relative; }}
  .slide-bullets li::before {{ content: ""; position: absolute; left: 0; top: 6px; width: 6px; height: 6px; border-radius: 50%; background: var(--orange-500); }}
  .slide-cta {{ margin-top: auto; font-size: 12px; font-weight: 700; color: var(--orange-600); padding-top: 10px; }}
  .slide-handle {{ font-size: 9px; color: var(--warm-500); margin-top: 4px; }}
  .scroll-hint {{ font-size: 10px; color: rgba(255,255,255,0.3); margin: 6px 2px 10px; letter-spacing: 0.5px; }}

  .sources {{ margin-top: 14px; font-size: 10px; color: rgba(255,255,255,0.25); line-height: 1.6; }}
  .sources summary {{ cursor: pointer; color: rgba(255,255,255,0.4); font-size: 10.5px; }}
  .sources ul {{ margin-top: 6px; padding-left: 16px; }}
  .sources a {{ color: rgba(255,255,255,0.35); }}
</style>
</head>
<body>

<div class="page-header">
  <img class="page-logo" src="assets/storyb-logo.png" alt="StoryB">
  <p class="page-title">Business & Markets — India</p>
</div>
<p class="page-sub">Generated {generated_at} · {count} carousels · shortlisted from {digest_name}</p>

{story_sections}

</body>
</html>
"""

STORY_TEMPLATE = """
<section class="story">
  <div class="story-meta">
    <div>
      <p class="story-rank">Story {rank:02d}</p>
      <p class="story-title">{title}</p>
      <p class="story-src">{source} · <a href="{link}" target="_blank" rel="noopener">source ↗</a></p>
    </div>
    <div class="score-badge">{score}</div>
  </div>

  <p class="scroll-hint">swipe →</p>
  <div class="row">
    <div class="slide slide1{slide1_class}">
      {slide1_inner_html}
    </div>
    <div class="slide slide2{slide2_class}">
      {slide2_inner_html}
    </div>
    <div class="slide slide3{slide3_class}">
      {slide3_inner_html}
    </div>
    <div class="slide slide4{slide4_class}">
      {slide4_inner_html}
    </div>
    <div class="slide slide5{slide5_class}">
      {slide5_inner_html}
    </div>
  </div>

  <details class="sources">
    <summary>Sources ({n_sources})</summary>
    <ul>{sources_list}</ul>
  </details>
</section>
"""


def esc(s):
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_slide(slide, slide_num, label_default, body_html):
    """Return (css_class, inner_html) for one carousel slide, handling the three cases:
    a fully-baked Canva image (text already in the pixels), an AI-generated backdrop with
    HTML text overlaid on a scrim, or a plain text-only card. `body_html` is the HTML for
    whatever this slide's own content looks like (headline+sub, headline+body, bullets, cta)
    and is only used in the non-baked cases, since baked images need zero HTML overlay.
    """
    cover_image = slide.get("cover_image")
    cover_source = slide.get("cover_source")  # "canva"/"code" = fully designed, text baked into image
    is_baked = bool(cover_image) and cover_source in ("canva", "code")

    if is_baked:
        css_class = " has-cover has-baked"
        inner_html = (
            f'<img class="cover-img baked" src="{esc(cover_image)}" '
            f'alt="{esc(slide.get("headline") or slide.get("label") or label_default)}">'
        )
    elif cover_image:
        css_class = " has-cover"
        inner_html = (
            f'<img class="cover-img" src="{esc(cover_image)}" alt=""><div class="cover-scrim"></div>'
            f'<div class="slide-num">{slide_num}</div>'
            f'<p class="slide-label">{esc(slide.get("label", label_default))}</p>'
            + body_html
        )
    else:
        css_class = ""
        inner_html = (
            f'<div class="slide-num">{slide_num}</div>'
            f'<p class="slide-label">{esc(slide.get("label", label_default))}</p>'
            + body_html
        )
    return css_class, inner_html


def render_story(piece, rank):
    src = piece.get("source_item", {})
    slides = piece.get("slides", {})
    hook = slides.get("slide1_hook", {})
    backstory = slides.get("slide2_backstory", {})
    news = slides.get("slide3_news", {})
    why = slides.get("slide4_why", {})
    engage = slides.get("slide5_engage", {})
    sources = slides.get("sources_used", []) or []

    bullets_html = "".join(f"<li>{esc(b)}</li>" for b in (why.get("bullets") or []))
    sources_html = "".join(
        f'<li><a href="{esc(s)}" target="_blank" rel="noopener">{esc(s)}</a></li>' for s in sources
    )

    slide1_class, slide1_inner_html = build_slide(
        hook, 1, "Cover",
        f'<p class="slide-headline">{esc(hook.get("label"))}</p>'
        f'<p class="slide-sub">{esc(hook.get("subhead"))}</p>',
    )
    slide2_class, slide2_inner_html = build_slide(
        backstory, 2, "THE BACKSTORY",
        f'<p class="slide-headline">{esc(backstory.get("headline"))}</p>'
        f'<div class="slide-rule"></div>'
        f'<p class="slide-body">{esc(backstory.get("body"))}</p>',
    )
    slide3_class, slide3_inner_html = build_slide(
        news, 3, "THE UPDATE",
        f'<p class="slide-headline">{esc(news.get("headline"))}</p>'
        f'<div class="slide-rule"></div>'
        f'<p class="slide-body">{esc(news.get("body"))}</p>',
    )
    slide4_class, slide4_inner_html = build_slide(
        why, 4, "WHY IT MATTERS",
        f'<p class="slide-headline">{esc(why.get("headline"))}</p>'
        f'<div class="slide-rule"></div>'
        f'<ul class="slide-bullets">{bullets_html}</ul>',
    )
    slide5_class, slide5_inner_html = build_slide(
        engage, 5, "YOUR TAKE",
        f'<p class="slide-headline">{esc(engage.get("headline"))}</p>'
        f'<p class="slide-cta">{esc(engage.get("cta"))}</p>',
    )

    return STORY_TEMPLATE.format(
        rank=rank,
        title=esc(src.get("title")),
        source=esc(src.get("source")),
        link=esc(src.get("link")),
        score=int(src.get("score") or 0),
        slide1_class=slide1_class,
        slide1_inner_html=slide1_inner_html,
        slide2_class=slide2_class,
        slide2_inner_html=slide2_inner_html,
        slide3_class=slide3_class,
        slide3_inner_html=slide3_inner_html,
        slide4_class=slide4_class,
        slide4_inner_html=slide4_inner_html,
        slide5_class=slide5_class,
        slide5_inner_html=slide5_inner_html,
        n_sources=len(sources),
        sources_list=sources_html,
    )


def main():
    pieces = load_pieces()
    if not pieces:
        print("No content pieces found in", CONTENT_DIR)
        return

    sections = "\n".join(render_story(p, i + 1) for i, p in enumerate(pieces))
    html = PAGE_TEMPLATE.format(
        generated_at=datetime.now().strftime("%b %d, %Y %H:%M"),
        count=len(pieces),
        digest_name="digest_2026-07-18_scored.json",
        story_sections=sections,
    )

    out_path = HERE / "preview.html"
    out_path.write_text(html)
    print(f"Wrote {out_path} with {len(pieces)} stories.")
    print(f"\nRun this to view it:\n  cd \"{HERE}\" && python3 -m http.server 3456\n  then open http://localhost:3456/preview.html")


if __name__ == "__main__":
    main()
