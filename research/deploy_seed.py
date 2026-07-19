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


MAX_BATCH_BYTES = 15_000_000  # stay well under Render's proxy request-size limit


def iter_batches():
    """Group files into zip-able batches capped by size (not by story, since story
    folders vary in size) -- a single ~130MB upload got connection-reset, almost
    certainly Render's proxy enforcing a body-size limit well under that."""
    batch, batch_size = [], 0
    for f in sorted(CODE_OUT.rglob("*")):
        if not f.is_file():
            continue
        size = f.stat().st_size
        if batch and batch_size + size > MAX_BATCH_BYTES:
            yield batch
            batch, batch_size = [], 0
        batch.append(f)
        batch_size += size
    if batch:
        yield batch


def zip_batch(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, arcname=str(f.relative_to(HERE)))
    buf.seek(0)
    return buf


def main():
    if len(sys.argv) != 2:
        print("usage: python3 deploy_seed.py https://your-app.onrender.com")
        sys.exit(1)
    if not ADMIN_TOKEN:
        print("ADMIN_TOKEN not set in .env -- add the same value you set in the Render "
              "dashboard for this service, then re-run.")
        sys.exit(1)
    base_url = sys.argv[1].rstrip("/")

    batches = list(iter_batches())
    total_files = sum(len(b) for b in batches)
    print(f"uploading {total_files} files from {CODE_OUT} in {len(batches)} batch(es)...")

    for i, batch in enumerate(batches, 1):
        bundle = zip_batch(batch)
        size_mb = bundle.getbuffer().nbytes / 1_000_000
        print(f"  batch {i}/{len(batches)}: {len(batch)} files, {size_mb:.1f} MB...", end=" ", flush=True)
        resp = requests.post(
            f"{base_url}/admin/restore",
            headers={"X-Admin-Token": ADMIN_TOKEN},
            files={"bundle": ("bundle.zip", bundle, "application/zip")},
            timeout=120,
        )
        if resp.status_code != 200:
            print(f"FAILED ({resp.status_code}): {resp.text[:500]}")
            sys.exit(1)
        print("ok")
    print("done")


if __name__ == "__main__":
    main()
