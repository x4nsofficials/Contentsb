#!/usr/bin/env python3
"""Code-rendered (Playwright + HTML/CSS) carousel slide designer.

v5 -- "bold & human" pass. Direct response to feedback that v3/v4 (magazine-editorial,
then "wire desk") had drifted into small, decorative meta-text everywhere -- folios,
tickers, dossier tabs, swipe hints, footers, proof bars, chart axis captions -- the exact
tell of "designing for an AI reviewer, not a human thumb scrolling past in half a second."

This pass strips every slide down to just two things: a HEADLINE (huge, bold, the actual
hook) and CONTENT (body copy / bullets / a real number). Nothing else earns a place on
the page. In exchange, the things that stay get real scale: logos are big and unboxed,
headlines are large enough to read at a glance mid-scroll, and every slide carries at
least one considered "component" -- an oversized ghost numeral, a real bar-chart
infographic, a filled/lifted stat card, a soft brand-color glow -- something with actual
visual weight instead of another line of small tracked-caps text.

Real fetched assets (logos/founder photos/screenshots) or Higgsfield-generated backdrops
slot in as slide backgrounds; text placement/sizing/wrapping is handled deterministically
by code, with an autofit pass that shrinks a --scale CSS var until copy fits with zero
overflow.
"""
import base64
import mimetypes
import re
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
STORYB_LOGO = HERE / "assets" / "storyb-logo.png"

CANVAS_W = 1080
CANVAS_H = 1350

INK = "#0B0B0C"
WARM_900 = "#141211"
WARM_700 = "#3B3532"
ORANGE = "#E9480F"
ORANGE_LIGHT = "#EE6E3A"
ORANGE_DARK = "#D33C08"
CREAM = "#FAF8F6"
WHITE = "#FFFFFF"
BRAND_GRADIENT = "linear-gradient(135deg, #F26A2E 0%, #E9480F 48%, #DA3C06 100%)"

# Subtle fractal-noise grain, tiled over every slide for photographic/print depth instead
# of the flat "vector poster" look of a plain gradient or photo.
_GRAIN_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='220' height='220'>"
    "<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/>"
    "<feColorMatrix type='saturate' values='0'/></filter>"
    "<rect width='100%' height='100%' filter='url(#n)'/></svg>"
)
GRAIN_DATA_URI = "data:image/svg+xml," + quote(_GRAIN_SVG)

FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,wght@0,500;0,600;0,700;0,800;1,500;1,600;1,700;1,800'
    '&family=Hanken+Grotesk:wght@400;500;600;700;800'
    '&family=JetBrains+Mono:wght@700;800&display=swap" rel="stylesheet">'
)

BASE_CSS = f"""
* {{ margin:0; padding:0; box-sizing:border-box; }}
html,body {{ width:{CANVAS_W}px; height:{CANVAS_H}px; overflow:hidden; background:{INK}; }}
body {{ font-family:'Hanken Grotesk',sans-serif; }}
.canvas {{ width:{CANVAS_W}px; height:{CANVAS_H}px; position:relative; overflow:hidden; }}
.bg-photo {{ position:absolute; inset:0; width:100%; height:100%; object-fit:cover; z-index:0; display:block; }}
.bg-solid {{ position:absolute; inset:0; z-index:0; }}
.scrim {{ position:absolute; inset:0; z-index:1;
  background: linear-gradient(180deg, rgba(11,11,12,0) 10%, rgba(11,11,12,0.5) 48%, rgba(11,11,12,0.96) 100%); }}
.grain {{ position:absolute; inset:0; z-index:3; opacity:0.05; mix-blend-mode:overlay;
  background-image:url('{GRAIN_DATA_URI}'); background-size:220px 220px; pointer-events:none; }}

/* StoryB's own mark -- the one piece of brand furniture that stays on every slide.
   Sized to read clearly, not shrunk into a corner afterthought. */
.storyb-mark {{ position:absolute; top:50px; right:56px; z-index:6; height:34px; display:flex; align-items:center; }}
.storyb-mark img {{ height:100%; width:auto; display:block; }}

/* Soft radial glow -- a brand-orange depth cue behind a hero element (a logo, a big
   stat), giving an otherwise flat vector page a sense of dimension without reaching for
   a literal 3D render. Used once per slide, never as generic wallpaper. */
.glow-blob {{ position:absolute; z-index:1; border-radius:50%; filter:blur(70px); pointer-events:none; }}

.accent {{ font-family:'Newsreader',serif; font-style:italic; font-weight:700;
  color:var(--accent-color, {ORANGE_LIGHT}); }}

/* Oversized ghost-italic numeral / glyph -- a bold graphic anchor, the opposite of small
   text clutter: one giant, quiet shape that gives the page a point of view. */
.ghost {{ position:absolute; z-index:2; font-family:'Newsreader',serif; font-style:italic;
  font-weight:800; line-height:0.82; pointer-events:none; user-select:none; }}

/* Indexed list -- on the why-slide the numbers ARE the content structure, not decoration. */
.e-item {{ display:grid; grid-template-columns:64px 1fr; column-gap:26px; padding:26px 0;
  border-top:1px solid var(--e-line, rgba(255,255,255,0.14)); }}
.e-item:first-child, .e-item.e-item-first {{ border-top:none; padding-top:0; }}
.e-num {{ font-family:'Newsreader',serif; font-style:italic; font-weight:700; font-size:36px; color:{ORANGE}; }}

/* Numeral card -- a real component: a filled, lifted stat block with actual visual
   weight (solid color + soft shadow), replacing a bare number floating over a tiny
   caption. This is one of the carousel's reusable "stands out" pieces. */
.numeral-card {{ display:inline-block; padding:38px 46px; border-radius:22px;
  box-shadow: 0 22px 48px -14px rgba(11,11,12,0.4); }}
.numeral-card-val {{ font-family:'Hanken Grotesk',sans-serif; font-weight:800; letter-spacing:-0.02em;
  font-size:104px; line-height:0.9; }}
.numeral-card-cap {{ font-size:19px; font-weight:700; letter-spacing:0.4px; margin-top:12px; }}

/* Timeline -- a vertical chronology for news-slide asides that are really a multi-year
   sequence of turning points (a crown changing hands) rather than a single two-value
   comparison a bar chart could show. Real HTML, not SVG, so event text wraps naturally. */
.timeline {{ display:flex; flex-direction:column; width:100%; }}
.tl-item {{ display:grid; grid-template-columns:92px 28px 1fr; column-gap:0;
  align-items:start; padding-bottom:40px; position:relative; }}
.tl-item.tl-item-last {{ padding-bottom:0; }}
.tl-year {{ font-family:'JetBrains Mono',monospace; font-weight:800; font-size:22px;
  color:rgba(11,11,12,0.5); padding-top:3px; }}
.tl-marker {{ position:relative; display:flex; justify-content:center; }}
.tl-marker::before {{ content:''; width:14px; height:14px; border-radius:50%;
  background:{WARM_700}; margin-top:5px; position:relative; z-index:2; }}
.tl-item:not(.tl-item-last) .tl-marker::after {{ content:''; position:absolute;
  top:19px; bottom:-40px; left:50%; width:2px; background:rgba(11,11,12,0.16);
  transform:translateX(-50%); z-index:1; }}
.tl-item.accent .tl-marker::before {{ background:{ORANGE}; width:18px; height:18px;
  margin-top:3px; box-shadow:0 0 0 6px rgba(233,72,15,0.16); }}
.tl-text {{ font-size:23px; font-weight:600; line-height:1.38; color:{INK}; padding-top:2px; }}
.tl-item.accent .tl-text {{ font-weight:800; color:{ORANGE_DARK}; }}

/* Solid pill button -- the brand guide's own documented CTA component. */
.pill-btn {{ display:inline-flex; align-items:center; gap:12px; padding:22px 40px;
  border-radius:999px; font-weight:800; font-size:23px; letter-spacing:0.2px; width:fit-content; }}

.logo-plate img {{ display:block; }}
"""


def _style_headline(text):
    """Implements the brand system's 'two-typeface headline': the base copy renders in
    bold Hanken Grotesk (the slide's default sans), while any **phrase** marked in the
    source copy switches to italic orange Newsreader for a single emphatic beat."""
    parts = re.split(r"\*\*(.+?)\*\*", text)
    out = []
    for i, part in enumerate(parts):
        if not part:
            continue
        out.append(f'<span class="accent">{part}</span>' if i % 2 == 1 else part)
    return "".join(out)


def _detone_overpowering_accents(page):
    """A marked **phrase** is meant to be a single emphatic beat -- one clean line (or
    part of one) in a different color/typeface. That reads fine even when it fills an
    entire line. It stops working when the phrase itself is long enough to wrap across
    a line break internally: at that point it's no longer "one beat", it's a multi-line
    block of orange italics that looks arbitrary rather than deliberate -- the
    "unnecessary highlight" complaint. Detect that directly (the span's own rendered
    height vs. its own line-height, not vs. the whole headline, so a legitimate
    single-line highlight that happens to fill a whole line is never penalized) and fall
    back the wrapped span to plain styling (inherits the headline's own color/weight)."""
    page.evaluate(
        """
        () => {
          document.querySelectorAll('.headline .accent').forEach((span) => {
            const cs = getComputedStyle(span);
            let lineHeight = parseFloat(cs.lineHeight);
            if (!lineHeight || Number.isNaN(lineHeight)) {
              lineHeight = parseFloat(cs.fontSize) * 1.2;
            }
            const spanH = span.getBoundingClientRect().height;
            if (lineHeight > 0 && spanH / lineHeight > 1.6) {
              span.classList.remove('accent');
              span.removeAttribute('style');
            }
          });
        }
        """
    )


def numeral_card_html(value, caption, bg=ORANGE, fg=WHITE, cap_color="rgba(255,255,255,0.85)"):
    """A filled, lifted stat component -- the number gets real visual weight (a solid
    card + soft shadow) instead of sitting as bare text over a tiny tracked-caps line."""
    return (
        f'<div class="numeral-card" style="background:{bg};">'
        f'<div class="numeral-card-val" style="color:{fg}">{value}</div>'
        f'<div class="numeral-card-cap" style="color:{cap_color}">{caption}</div>'
        f"</div>"
    )


def glow_blob_html(top, right=None, left=None, size=460, color=ORANGE, opacity=0.35):
    """A soft, blurred brand-color glow -- gives a hero element (logo, stat) a sense of
    depth/dimension. Used sparingly, one per slide at most."""
    pos = f"top:{top}px;"
    pos += f"right:{right}px;" if right is not None else f"left:{left}px;"
    return (
        f'<div class="glow-blob" style="{pos} width:{size}px; height:{size}px; '
        f'background:{color}; opacity:{opacity};"></div>'
    )


def storyb_mark_html(variant="light"):
    """StoryB's own brand mark, placed consistently on every slide (top-right). 'light'
    for dark/photo backgrounds, 'dark' (flattened to solid ink) for cream reading pages."""
    style = "" if variant == "light" else "filter:brightness(0); opacity:0.86;"
    return f'<div class="storyb-mark"><img src="{_img_src(STORYB_LOGO)}" style="{style}"></div>'


def logo_plate_html(logo_src, height=140):
    """The story's own subject logo (e.g. the company the story is about) -- big and
    unboxed, a real presence on the page rather than a small bordered credential chip."""
    logo = _img_src(logo_src)
    return f'<div class="logo-plate"><img src="{logo}" style="height:{height}px; width:auto;"></div>'


def pill_button_html(text, style="ink", arrow=True):
    """The brand guide's own documented pill-button component (solid orange 'Apply Now',
    solid ink 'See if you qualify', outline 'Learn more')."""
    styles = {
        "ink": (INK, WHITE, "none"),
        "orange": (ORANGE, WHITE, "none"),
        "cream": (CREAM, INK, "none"),
        "outline-ink": ("transparent", INK, f"1.5px solid {INK}"),
        "outline-white": ("transparent", WHITE, "1.5px solid rgba(255,255,255,0.75)"),
    }
    bg, fg, border = styles.get(style, styles["ink"])
    arrow_html = ' <span>&rarr;</span>' if arrow else ""
    return (
        f'<div class="pill-btn" style="background:{bg}; color:{fg}; border:{border};">'
        f"{text}{arrow_html}</div>"
    )


def ghost_glyph_html(glyph, top, right=None, left=None, size=420, opacity=0.08, color=INK):
    pos = f"top:{top}px;"
    pos += f"right:{right}px;" if right is not None else f"left:{left}px;"
    return (
        f'<div class="ghost" style="{pos} font-size:{size}px; '
        f'color:{color}; opacity:{opacity};">{glyph}</div>'
    )


def stat_compare_svg(bars, width=320, height=360, bar_w=88, gap=56,
                      base_color=WARM_700, accent_color=ORANGE, ink=INK,
                      annotate=False, mark_color=ORANGE_DARK):
    """A real flat bar-chart infographic -- not a decorative icon -- comparing 2-3 numeric
    values on a shared baseline: plain rectangles, one big bold value numeral per bar. No
    axis captions, no tiny category labels underneath -- the headline/body already say
    what the bars are; the chart's only job is to make the number land visually.

    When `annotate=True` and the bars contain one baseline value and one accent value,
    the accent figure gets a hand-marked dashed circle plus a bold delta callout (the way
    an editor circles the number that actually matters on a printed sheet).

    bars: [{"value": 7.0, "display": "$7B"}, ...]. Set "accent": True on the bar that
    should read in brand orange.
    """
    max_val = max(b["value"] for b in bars) or 1
    n = len(bars)
    total_w = n * bar_w + (n - 1) * gap
    start_x = (width - total_w) / 2
    baseline_y = height - 40
    top_pad = 90
    plot_h = baseline_y - top_pad
    parts = [
        f'<line x1="0" y1="{baseline_y}" x2="{width}" y2="{baseline_y}" '
        f'stroke="{ink}" stroke-opacity="0.28" stroke-width="1.5"/>'
    ]
    accent_cx = accent_cy = None
    base_val = accent_val = None
    for i, b in enumerate(bars):
        x = start_x + i * (bar_w + gap)
        h = max(10, (b["value"] / max_val) * plot_h)
        y = baseline_y - h
        is_accent = bool(b.get("accent"))
        fill = accent_color if is_accent else base_color
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w}" height="{h:.1f}" fill="{fill}"/>')
        parts.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{y - 22:.1f}" text-anchor="middle" '
            f'font-family="JetBrains Mono" font-weight="800" font-size="34" fill="{ink}">{b["display"]}</text>'
        )
        if is_accent:
            accent_cx, accent_cy = x + bar_w / 2, y - 34
            accent_val = b["value"]
            accent_display = b["display"]
        else:
            base_val = b["value"] if base_val is None else base_val

    if annotate and accent_cx is not None and base_val and accent_val is not None:
        pct = round((accent_val - base_val) / base_val * 100)
        arrow = "▼" if pct < 0 else "▲"
        tag = f"{arrow} {abs(pct)}%"
        rx, ry = max(82, 12 * len(accent_display)), 36
        parts.append(
            f'<ellipse cx="{accent_cx:.1f}" cy="{accent_cy:.1f}" rx="{rx}" ry="{ry}" '
            f'fill="none" stroke="{mark_color}" stroke-width="2.5" stroke-dasharray="6 5" '
            f'transform="rotate(-4 {accent_cx:.1f} {accent_cy:.1f})"/>'
        )
        tagx, tagy = accent_cx, accent_cy - ry - 18
        parts.append(
            f'<text x="{tagx:.1f}" y="{tagy:.1f}" text-anchor="middle" '
            f'font-family="JetBrains Mono" font-weight="800" font-size="24" '
            f'fill="{mark_color}" transform="rotate(-4 {tagx:.1f} {tagy:.1f})">{tag}</text>'
        )
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" overflow="visible">{"".join(parts)}</svg>'
    )


def timeline_html(events, accent_color=ORANGE):
    """A vertical chronology component -- real HTML (not SVG) so year/event text wraps
    naturally. Used on the news slide when a story's 'infographic' beat is really a
    multi-year sequence of turning points (a crown changing hands, a slow reversal) that
    a two-bar comparison can't actually show.

    events: [{"year": "2018", "text": "Apple first to hit $1 trillion"}, ...]. Set
    "accent": True on the entry that is the story's actual news peg (usually the most
    recent/decisive one) -- it renders in bold brand orange with a bigger marker.
    """
    n = len(events)
    items = []
    for i, e in enumerate(events):
        cls = "tl-item"
        if e.get("accent"):
            cls += " accent"
        if i == n - 1:
            cls += " tl-item-last"
        items.append(
            f'<div class="{cls}">'
            f'<div class="tl-year">{e["year"]}</div>'
            f'<div class="tl-marker"></div>'
            f'<div class="tl-text">{e["text"]}</div>'
            f"</div>"
        )
    return f'<div class="timeline">{"".join(items)}</div>'


def _data_uri(path):
    """Inline a local image as a base64 data: URI so Playwright can load it with no
    dependency on a running HTTP server."""
    path = Path(path)
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _img_src(src):
    if src is None:
        return None
    s = str(src)
    if s.startswith("http://") or s.startswith("https://") or s.startswith("data:"):
        return s
    return _data_uri(s)


def render_to_png(inner_html, extra_css, out_path, autofit=None):
    """autofit: list of dicts {"selector": "#stack", "min": 0.55, "max": 1.0, "step": 0.05}
    Shrinks the element's --scale custom property until scrollHeight <= clientHeight."""
    doc = f"""<!DOCTYPE html><html><head><meta charset="utf-8">{FONTS_LINK}
<style>{BASE_CSS}
{extra_css}</style></head><body>
<div class="canvas">{inner_html}</div>
</body></html>"""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": CANVAS_W, "height": CANVAS_H})
        page.set_content(doc, wait_until="networkidle")
        if autofit:
            for rule in autofit:
                sel = rule["selector"]
                scale = rule.get("max", 1.0)
                min_scale = rule.get("min", 0.55)
                step = rule.get("step", 0.05)
                if page.query_selector(sel) is None:
                    continue
                while scale > min_scale:
                    page.eval_on_selector(sel, "(el, s) => el.style.setProperty('--scale', s)", scale)
                    overflow = page.eval_on_selector(sel, "el => el.scrollHeight > el.clientHeight + 2")
                    if not overflow:
                        break
                    scale = round(scale - step, 3)
        _detone_overpowering_accents(page)
        page.screenshot(path=str(out_path))
        browser.close()
    return out_path


# ---------------------------------------------------------------------------
# Slide-type builders. Each returns (inner_html, extra_css, autofit_config).
# Every slide is now just: [big logo, where relevant] + HEADLINE + CONTENT + one bold
# graphic component. No eyebrows, no folios, no tickers, no footers, no swipe hints.
# ---------------------------------------------------------------------------


def cover_slide(headline, subhead, bg_src=None, logo_src=None, story_num=1, badge_num=1, total=5):
    """Magazine-cover composition: photo + scrim, a left-aligned column held off the left
    edge by a single orange spine rule. The subject's logo runs big and unboxed with a
    soft brand-glow behind it, and the headline is scaled to actually dominate the frame
    (the hook that has to stop a scrolling thumb) instead of sharing space with a kicker,
    ticker, folio, or swipe hint."""
    bg = _img_src(bg_src)
    bg_html = (
        f'<img class="bg-photo" src="{bg}">' if bg else
        f'<div class="bg-solid" style="background:{WARM_900};"></div>'
    )
    plate_html = (
        f'<div class="cover-plate" style="position:relative;">'
        f'{glow_blob_html(top=-70, left=-70, size=340, color=ORANGE, opacity=0.4)}'
        f'{logo_plate_html(logo_src, height=140)}</div>'
        if logo_src else ""
    )
    extra_css = f"""
.cover-wrap {{ position:absolute; left:56px; right:110px; bottom:110px; z-index:5;
  display:flex; gap:28px; align-items:stretch; --scale:1; --accent-color:{ORANGE_LIGHT}; }}
.cover-wrap .spine {{ width:4px; background:{ORANGE}; flex:0 0 auto; margin-top:8px; margin-bottom:8px; }}
.cover-col {{ flex:1 1 auto; max-height:1020px; overflow:hidden; }}
.cover-plate {{ margin-bottom:36px; }}
.cover-col .headline {{ font-weight:800; letter-spacing:-0.025em; color:#fff;
  font-size: calc(var(--scale) * 172px); line-height:0.96; margin-bottom:26px; }}
.cover-col .subhead {{ font-size: calc(var(--scale) * 30px); color: rgba(255,255,255,0.72);
  font-weight:600; line-height:1.42; max-width:560px; }}
"""
    inner = (
        f'{bg_html}<div class="scrim"></div><div class="grain"></div>{storyb_mark_html()}'
        f'<div class="cover-wrap">'
        f'<div class="spine"></div>'
        f'<div class="cover-col" id="cover-col">'
        f"{plate_html}"
        f'<p class="headline">{_style_headline(headline)}</p>'
        f'<p class="subhead">{subhead}</p>'
        f"</div></div>"
    )
    autofit = [{"selector": "#cover-col", "max": 1.0, "min": 0.5, "step": 0.05}]
    return inner, extra_css, autofit


def backstory_slide(label, headline, body, bg_src, story_num=1, badge_num=2, total=5):
    """Full-bleed photo slide for the origin-story beat. An oversized ghost-italic numeral
    bleeds off the top-right corner as the slide's one graphic component; the headline is
    large enough to read at a glance, with the body as the only supporting text. `label`
    is accepted for compatibility but no longer rendered as a small eyebrow tag -- the
    headline alone carries the beat."""
    bg = _img_src(bg_src)
    extra_css = f"""
.b-stack {{ position:absolute; left:56px; right:170px; bottom:120px; z-index:5;
  max-height:900px; overflow:hidden; --scale:1; --accent-color:{ORANGE_LIGHT}; }}
.b-stack .headline {{ font-weight:800; letter-spacing:-0.015em; color:#fff;
  font-size: calc(var(--scale) * 76px); line-height:1.06; margin-bottom:28px; }}
.b-stack .body {{ font-size: calc(var(--scale) * 31px); color: rgba(255,255,255,0.85);
  font-weight:500; line-height:1.5; }}
"""
    inner = (
        f'<img class="bg-photo" src="{bg}"><div class="scrim"></div>'
        f'{ghost_glyph_html(f"{badge_num:02d}", top=-64, right=-14, size=440, opacity=0.1, color=WHITE)}'
        f'<div class="grain"></div>{storyb_mark_html()}'
        f'<div class="b-stack" id="b-stack">'
        f'<p class="headline">{_style_headline(headline)}</p>'
        f'<p class="body">{body}</p>'
        f"</div>"
    )
    autofit = [{"selector": "#b-stack", "max": 1.0, "min": 0.5, "step": 0.05}]
    return inner, extra_css, autofit


def news_slide(label, headline, body, story_num=1, badge_num=3, total=5,
               proof=None, chart=None, chart_caption=None, chart_annotate=True,
               timeline=None, stat=None):
    """Cream 'reading page'. A big bold headline, body copy, and one story-appropriate
    aside component in the right column, separated by a single hairline rule. The aside
    is picked per story, not forced -- a bar chart only earns its place when the story is
    genuinely a two-value comparison; a multi-year 'crown changing hands' story gets a
    `timeline` chronology instead, and a story whose real news is one striking number
    (not a comparison) gets a plain `stat` numeral card. Priority when more than one is
    passed: timeline > chart > stat > none (headline/body only, single column). No
    eyebrow label, no press-name pill, no tiny axis captions -- just the headline, the
    copy, and (at most) one number or sequence doing real work."""
    if timeline:
        aside_html = timeline_html(timeline)
        aside_class = "news-timeline"
    elif chart:
        aside_html = stat_compare_svg(chart, width=430, height=560, bar_w=132, gap=76, annotate=chart_annotate)
        aside_class = "news-chart"
    elif stat:
        value, caption = stat
        aside_html = numeral_card_html(value, caption, bg=ORANGE, fg=WHITE)
        aside_class = "news-stat"
    else:
        aside_html = None
        aside_class = ""

    if aside_html is not None:
        aside_col = f'<div class="news-divider"></div><div class="news-aside {aside_class}">{aside_html}</div>'
        grid_cols = "1.05fr 1px 1fr"
    else:
        aside_col = ""
        grid_cols = "1fr"
    extra_css = f"""
.news-grid {{ position:absolute; top:130px; left:56px; right:56px; bottom:100px; z-index:5;
  display:grid; grid-template-columns:{grid_cols}; column-gap:56px; align-items:center; }}
.news-divider {{ background:rgba(11,11,12,0.14); align-self:stretch; }}
.news-text {{ --scale:1; --accent-color:{ORANGE}; overflow:hidden; }}
.news-text .headline {{ font-weight:800; letter-spacing:-0.02em; color:{INK};
  font-size: calc(var(--scale) * 80px); line-height:1.03; margin-bottom:34px; }}
.news-text .body {{ font-size: calc(var(--scale) * 34px); color:rgba(11,11,12,0.8);
  font-weight:500; line-height:1.5; }}
.news-aside {{ display:flex; align-items:center; justify-content:center; }}
"""
    inner = (
        f'<div class="bg-solid" style="background:{CREAM};"></div>'
        f'{ghost_glyph_html(f"{badge_num:02d}", top=-40, left=-24, size=760, opacity=0.045, color=INK)}'
        f'<div class="grain" style="opacity:0.035;"></div>'
        f'{storyb_mark_html("dark")}'
        f'<div class="news-grid">'
        f'<div class="news-text" id="news-text">'
        f'<p class="headline">{_style_headline(headline)}</p>'
        f'<p class="body">{body}</p>'
        f"</div>"
        f"{aside_col}"
        f"</div>"
    )
    autofit = [{"selector": "#news-text", "max": 1.0, "min": 0.55, "step": 0.05}]
    return inner, extra_css, autofit


def why_slide(label, headline, bullets, story_num=1, badge_num=4, total=5, stat=None):
    """Cream reading page, indexed list: an italic orange numeral and a hairline rule
    between rows -- the bullets are the content, so the numbering stays. Optional `stat`
    (value, caption) renders as a filled, lifted numeral-card component: a real stat with
    visual weight instead of a bare number over a tiny caption."""
    items_html = "".join(
        f'<div class="e-item{" e-item-first" if i == 1 else ""}">'
        f'<div class="e-num">{i:02d}</div><p class="e-text">{b}</p></div>'
        for i, b in enumerate(bullets, start=1)
    )
    stat_html = numeral_card_html(stat[0], stat[1].upper()) if stat else ""
    extra_css = f"""
.w-stack {{ position:absolute; left:56px; right:56px; top:150px; bottom:90px; z-index:5;
  display:flex; flex-direction:column; justify-content:center; overflow:hidden;
  --scale:1; --accent-color:{ORANGE}; --e-line:rgba(11,11,12,0.14); }}
.w-stack .headline {{ font-weight:800; letter-spacing:-0.02em; color:{INK};
  font-size: calc(var(--scale) * 82px); line-height:1.05; margin-bottom:50px; }}
.e-item {{ padding:42px 0; }}
.e-text {{ font-size: calc(var(--scale) * 38px); color:rgba(11,11,12,0.86);
  font-weight:600; line-height:1.42; padding-top:2px; }}
.w-stack .e-num {{ font-size:40px; }}
.w-stack .numeral-card {{ margin-top:60px; }}
.w-stack .numeral-card-val {{ font-size:118px; }}
"""
    inner = (
        f'<div class="bg-solid" style="background:{CREAM};"></div>'
        f'{ghost_glyph_html("?", top=-90, right=-40, size=680, opacity=0.045, color=INK)}'
        f'<div class="grain" style="opacity:0.035;"></div>'
        f'{storyb_mark_html("dark")}'
        f'<div class="w-stack" id="w-stack">'
        f'<p class="headline">{_style_headline(headline)}</p>'
        f"{items_html}"
        f"{stat_html}"
        f"</div>"
    )
    autofit = [{"selector": "#w-stack", "max": 1.0, "min": 0.5, "step": 0.05}]
    return inner, extra_css, autofit


def _split_engage_headline(text):
    """Split the engage headline into a quiet, scene-setting lead sentence and the bold
    hook question that follows it. Every engage headline in practice is written as
    "[context sentence]. [question]?" -- one wall of same-weight bold text was the
    complaint; giving the setup its own lighter, smaller, serif-italic register (vs. the
    hook's big bold sans) turns it into an actual two-beat read instead of one dense
    block in a single typeface. Falls back to rendering everything as the hook if no
    clean sentence break is found, so this degrades gracefully on future one-liners."""
    m = re.match(r"^(.*?[.!])\s+(.+)$", text, re.S)
    if not m:
        return None, text
    return m.group(1), m.group(2)


def engage_slide(label, headline, cta, story_num=1, badge_num=5, total=5, pill_text="Drop your take"):
    """Dark brand-gradient bookend, asymmetric like the cover: a left-aligned column with
    an oversized ghost question mark bleeding off the top-right -- a device pulled
    directly from the slide's own content (it's the question slide). The headline reads
    in two registers -- a smaller, quieter lead sentence for context, then the actual
    bold hook question -- but both now share the same sans-serif family (weight/size/
    opacity is what separates them). Splitting that quiet lead into its own italic-serif
    typeface as before meant the same typeface (Newsreader italic) was doing two
    unrelated jobs on one slide -- a hushed aside here, a loud one-beat highlight there
    in the headline's own **accent** span -- which read as confusing/arbitrary rather
    than a deliberate two-typeface system. Content is vertically centered in the space
    below the brand mark (rather than hugging the bottom edge) so a short headline
    doesn't leave a large dead gap above it, the way a bottom-only anchor did on a flat
    gradient background with no photo to justify the empty space. Closes on a real solid-
    ink pill button. No stamp, no ticker, no folio, no footer."""
    lead, hook = _split_engage_headline(headline)
    extra_css = f"""
.eg-wrap {{ position:absolute; left:56px; right:100px; top:170px; bottom:130px; z-index:5;
  max-width:820px; display:flex; flex-direction:column; justify-content:center;
  --scale:1; --accent-color:#fff; }}
.eg-wrap .lead {{ font-weight:600; color:{INK}; opacity:0.6;
  font-size: calc(var(--scale) * 30px); line-height:1.42; margin-bottom:22px; max-width:640px; }}
.eg-wrap .headline {{ font-weight:800; letter-spacing:-0.02em; color:{INK};
  font-size: calc(var(--scale) * 72px); line-height:1.08; margin-bottom:32px; }}
.eg-wrap .cta {{ font-size: calc(var(--scale) * 27px); color:{INK}; font-weight:700; opacity:0.8; margin-bottom:38px; }}
"""
    lead_html = f'<p class="lead">{lead}</p>' if lead else ""
    pill_html = pill_button_html(pill_text, style="ink") if pill_text else ""
    inner = (
        f'<div class="bg-solid" style="background:{BRAND_GRADIENT};"></div>'
        f'{ghost_glyph_html("?", top=-70, right=-30, size=560, opacity=0.09, color=INK)}'
        f'<div class="grain"></div>'
        f'{storyb_mark_html("dark")}'
        f'<div class="eg-wrap" id="eg-wrap">'
        f"{lead_html}"
        f'<p class="headline">{_style_headline(hook)}</p>'
        f'<p class="cta">{cta}</p>'
        f"{pill_html}"
        f"</div>"
    )
    autofit = [{"selector": "#eg-wrap", "max": 1.0, "min": 0.5, "step": 0.05}]
    return inner, extra_css, autofit
