#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pymupdf==1.28.2"]
# ///
"""Assemble the GitHub Pages site from the submitted thesis PDF"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pymupdf

REPO = Path(__file__).resolve().parent.parent
TOOLS = REPO / "template" / "tools"
SOURCE = REPO / "master_thesis.pdf"
NAME = "msc_thesis_AndrejOrsula"
EDITIONS = {"DIGITAL": f"{NAME}.pdf", "FULL": f"{NAME}_full.pdf"}
# The digital budget of the template's build.py
DPI, QUALITY, MAX_BYTES, MIN_PSNR = 300, 90, 25_000_000, 30.0


def uv_script(script: str, *args: object) -> None:
    command = ["uv", "run", "--no-project", "--script", str(TOOLS / script), *map(str, args)]
    subprocess.run(command, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("site", type=Path, help="directory to write the site to (replaced)")
    parser.add_argument("--revision", required=True, help="commit the site is built from")
    args = parser.parse_args(argv)

    site = args.site.resolve()
    # The site directory is deleted and recreated, so it must hold nothing else.
    if site in (REPO, *REPO.parents) or any(
        site.is_relative_to(REPO / kept) for kept in (".git", "template")
    ):
        print(
            f"error: refusing to replace {site}, which holds the repository or the template",
            file=sys.stderr,
        )
        return 1
    for tool in ("optimize_pdf.py", "check_pdf.py"):
        if not (TOOLS / tool).is_file():
            print(
                f"error: {TOOLS / tool} is missing; run `git submodule update --init`",
                file=sys.stderr,
            )
            return 1

    if site.exists():
        shutil.rmtree(site)
    site.mkdir(parents=True)

    full, digital = site / EDITIONS["FULL"], site / EDITIONS["DIGITAL"]
    shutil.copyfile(SOURCE, full)
    uv_script("optimize_pdf.py", full, digital, "--dpi", DPI, "--quality", QUALITY)
    uv_script(
        "check_pdf.py",
        full,
        digital,
        "--max-bytes",
        MAX_BYTES,
        "--min-psnr",
        MIN_PSNR,
        "--min-dpi",
        DPI,
    )

    values = {"REVISION": args.revision, "REVISION_SHORT": args.revision[:7]}
    for key, published in EDITIONS.items():
        target = site / published
        with pymupdf.open(target) as document:
            values[f"{key}_PAGES"] = str(document.page_count)
        values[f"{key}_SIZE"] = f"{target.stat().st_size / 1e6:.1f} MB"

    page = (REPO / "index.html").read_text()
    page = re.sub(r"\{\{(\w+)\}\}", lambda match: values.get(match[1], match[0]), page)
    left = sorted(set(re.findall(r"\{\{\w+\}\}", page)))
    if left:
        print(f"error: index.html has unfilled placeholders: {', '.join(left)}", file=sys.stderr)
        return 1
    for name in sorted(set(re.findall(r'href="([^":#/]+\.pdf)"', page))):
        if not (site / name).is_file():
            print(f"error: index.html links to {name}, which is not in the site", file=sys.stderr)
            return 1
    (site / "index.html").write_text(page)

    for path in sorted(site.iterdir()):
        print(f"{path.name}: {path.stat().st_size / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
