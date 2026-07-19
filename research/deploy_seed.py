#!/usr/bin/env python3
"""One-time (or occasional) helper: zip up the locally-rendered slide images under
assets/code_pilot -- which aren't committed to git, see the repo's .gitignore -- and
upload them to a deployed instance's /admin/restore endpoint, so a fresh Render
persistent disk ends up with the existing stories' images instead of broken links.

Usage:
    python3 deploy_seed.py https://your-app.onrender.com

Requires ADMIN_TOKEN in .env (the same value set in the Render dashboard for this
service) to authenticate the upload.
"""
import io
import os
import sys
import zipfile
from pathlib import Path

import requests
from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE.parent / ".env", override=True)

CODE_OUT = HERE / "assets" / "code_pilot"
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN")


def build_bundle():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        count = 0
        for f in CODE_OUT.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=str(f.relative_to(HERE)))
                count += 1
    buf.seek(0)
    return buf, count


def main():
    if len(sys.argv) != 2:
        print("usage: python3 deploy_seed.py https://your-app.onrender.com")
        sys.exit(1)
    if not ADMIN_TOKEN:
        print("ADMIN_TOKEN not set in .env -- add the same value you set in the Render "
              "dashboard for this service, then re-run.")
        sys.exit(1)
    base_url = sys.argv[1].rstrip("/")

    bundle, count = build_bundle()
    size_mb = bundle.getbuffer().nbytes / 1_000_000
    print(f"bundling {count} files ({size_mb:.1f} MB) from {CODE_OUT}...")

    resp = requests.post(
        f"{base_url}/admin/restore",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        files={"bundle": ("bundle.zip", bundle, "application/zip")},
        timeout=300,
    )
    if resp.status_code != 200:
        print(f"FAILED ({resp.status_code}): {resp.text[:500]}")
        sys.exit(1)
    print("done:", resp.json())


if __name__ == "__main__":
    main()
