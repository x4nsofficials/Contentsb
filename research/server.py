#!/usr/bin/env python3
"""Server that puts the "Generate New Post" button directly on the preview page.

Run with `python3 server.py`, then open http://localhost:3456 (serves preview.html,
which now carries its own generate widget). Clicking the button runs new_post.py's
full pipeline (fresh news -> score -> research+write copy -> generate two AI images
-> render 5 slides -> append to preview.html) in a background thread; the widget polls
/status for progress and reloads the page once the new story has been appended.

In production (Render), the app code lives in the read-only container image while
generated stories (preview.html, content/, digests/, assets/covers, assets/code_pilot)
live on a mounted persistent disk at DATA_DIR, so new stories survive redeploys/restarts
-- see new_post.py's DATA_DIR comment. PORT is injected by the platform.
"""
import json
import os
import shutil
import threading
import traceback
import zipfile
from io import BytesIO
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory

import new_post
import publish_post

HERE = Path(__file__).parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(HERE)))
PORT = int(os.environ.get("PORT", 3456))
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN")


def bootstrap_data_dir():
    """On a fresh persistent disk (DATA_DIR != HERE and not yet populated), seed the
    small, git-committed baseline -- preview.html plus the existing content/digests JSON
    -- so the site isn't blank on first boot. The large rendered slide PNGs under
    assets/code_pilot aren't committed to git (they're regenerated per-story going
    forward, or restored once via the /admin/restore endpoint for pre-existing stories).
    A no-op locally, where DATA_DIR already equals HERE."""
    if DATA_DIR == HERE:
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not (DATA_DIR / "preview.html").exists() and (HERE / "preview.html").exists():
        shutil.copy2(HERE / "preview.html", DATA_DIR / "preview.html")
    for sub in ("content", "digests"):
        src, dst = HERE / sub, DATA_DIR / sub
        if src.is_dir() and not dst.exists():
            shutil.copytree(src, dst)


bootstrap_data_dir()

app = Flask(__name__)

STATE = {"running": False, "done": False, "error": None, "log": [], "result": None}
LOCK = threading.Lock()

PUBLISH_STATE = {"running": False, "done": False, "error": None, "log": [], "result": None}
PUBLISH_LOCK = threading.Lock()


def log(msg):
    print(f"[server] {msg}", flush=True)
    with LOCK:
        STATE["log"].append(msg)


def run_pipeline():
    with LOCK:
        STATE.update({"running": True, "done": False, "error": None, "log": [], "result": None})
    try:
        result = new_post.run(log=log)
        with LOCK:
            STATE["result"] = result
    except Exception as e:
        log(f"FAILED: {e}")
        traceback.print_exc()
        with LOCK:
            STATE["error"] = str(e)
    finally:
        with LOCK:
            STATE["running"] = False
            STATE["done"] = True


@app.route("/")
def index():
    return send_from_directory(DATA_DIR, "preview.html")


@app.route("/generate", methods=["POST"])
def generate():
    with LOCK:
        if STATE["running"]:
            return jsonify({"ok": False, "error": "a generation is already running"}), 409
    threading.Thread(target=run_pipeline, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/status")
def status():
    with LOCK:
        return jsonify(dict(STATE))


@app.route("/assets/<path:subpath>")
def assets(subpath):
    # Generated per-story images (covers, rendered slides) live on DATA_DIR; static
    # brand assets (logo, scrim) are baked into the code image under HERE. Try the
    # mutable location first, fall back to the static one.
    if (DATA_DIR / "assets" / subpath).exists():
        return send_from_directory(DATA_DIR / "assets", subpath)
    return send_from_directory(HERE / "assets", subpath)


@app.route("/preview.html")
def preview():
    return send_from_directory(DATA_DIR, "preview.html")


@app.route("/admin/restore", methods=["POST"])
def admin_restore():
    """One-time (or occasional) bootstrap: upload a zip of DATA_DIR's contents (built by
    the local deploy_seed.py script) to populate a fresh persistent disk with existing
    stories' rendered slide images, which aren't committed to git. Token-gated since it
    writes arbitrary files -- set ADMIN_TOKEN in the environment to enable this route at
    all; it's a 404 (not just a 401) when unset so it doesn't advertise itself."""
    if not ADMIN_TOKEN:
        abort(404)
    if request.headers.get("X-Admin-Token") != ADMIN_TOKEN:
        return jsonify({"ok": False, "error": "bad token"}), 401
    upload = request.files.get("bundle")
    if not upload:
        return jsonify({"ok": False, "error": "missing 'bundle' file"}), 400
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(BytesIO(upload.read())) as zf:
        for member in zf.namelist():
            # Reject absolute paths and parent-dir escapes -- this endpoint is trusted
            # (token-gated) but there's no reason to allow writing outside DATA_DIR.
            if member.startswith("/") or ".." in Path(member).parts:
                return jsonify({"ok": False, "error": f"unsafe path in bundle: {member}"}), 400
        zf.extractall(DATA_DIR)
    return jsonify({"ok": True})


@app.route("/admin/rerender", methods=["POST"])
def admin_rerender():
    """Re-run rendering for one already-generated story using the CURRENT deployed
    carousel_render.py, reusing its existing content JSON and raw per-slide background
    photos already on DATA_DIR -- no new Anthropic/OpenAI calls, so a design tweak
    (e.g. removing a ghost-numeral watermark, bumping a font size) can be applied to a
    story generated before that fix shipped, without burning API credit or shuttling
    large image files back and forth. Same token gate as /admin/restore."""
    if not ADMIN_TOKEN:
        abort(404)
    if request.headers.get("X-Admin-Token") != ADMIN_TOKEN:
        return jsonify({"ok": False, "error": "bad token"}), 401
    body = request.get_json(force=True, silent=True) or {}
    slug = body.get("slug")
    if not slug:
        return jsonify({"ok": False, "error": "missing slug"}), 400
    try:
        matches = list(new_post.CONTENT_DIR.glob(f"content_*_{slug}.json"))
        if not matches:
            return jsonify({"ok": False, "error": f"no content json found for slug '{slug}'"}), 404
        data = json.loads(matches[0].read_text())
        specs = new_post.slide_specs(data["slides"])
        image_paths = {}
        missing = []
        for _, name, _, _ in specs:
            p = new_post.COVERS_DIR / f"{slug}-{name}.png"
            if not p.exists():
                missing.append(name)
            image_paths[name] = p
        if missing:
            return jsonify({"ok": False, "error": f"missing raw background image(s): {missing}"}), 404
        log_lines = []
        new_post.render_slides(data, slug, image_paths, log_lines.append)
        return jsonify({"ok": True, "log": log_lines})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/prepare_publish", methods=["POST"])
def prepare_publish():
    body = request.get_json(force=True, silent=True) or {}
    slug = body.get("slug")
    title = body.get("title")
    if not slug:
        return jsonify({"error": "missing slug"}), 400
    try:
        result = publish_post.prepare(slug, title=title)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


def publish_log(msg):
    print(f"[publish] {msg}", flush=True)
    with PUBLISH_LOCK:
        PUBLISH_STATE["log"].append(msg)


def run_publish(slug, base_url, targets, captions):
    with PUBLISH_LOCK:
        PUBLISH_STATE.update({"running": True, "done": False, "error": None, "log": [], "result": None})
    try:
        result = publish_post.publish(slug, base_url, targets, captions, log=publish_log)
        with PUBLISH_LOCK:
            PUBLISH_STATE["result"] = result
    except Exception as e:
        publish_log(f"FAILED: {e}")
        traceback.print_exc()
        with PUBLISH_LOCK:
            PUBLISH_STATE["error"] = str(e)
    finally:
        with PUBLISH_LOCK:
            PUBLISH_STATE["running"] = False
            PUBLISH_STATE["done"] = True


@app.route("/publish", methods=["POST"])
def publish_route():
    body = request.get_json(force=True, silent=True) or {}
    slug = body.get("slug")
    base_url = body.get("base_url")
    targets = body.get("targets") or []
    captions = body.get("captions") or {}
    if not slug or not base_url or not targets:
        return jsonify({"ok": False, "error": "missing slug, base_url, or targets"}), 400
    with PUBLISH_LOCK:
        if PUBLISH_STATE["running"]:
            return jsonify({"ok": False, "error": "a publish is already running"}), 409
    threading.Thread(target=run_publish, args=(slug, base_url, targets, captions), daemon=True).start()
    return jsonify({"ok": True})


@app.route("/publish_status")
def publish_status():
    with PUBLISH_LOCK:
        return jsonify(dict(PUBLISH_STATE))


if __name__ == "__main__":
    print(f"Open http://localhost:{PORT} in your browser.")
    app.run(host="0.0.0.0", port=PORT, debug=False)
