"""Release the app that `client/packaging/build.py` just built.

    uv run --project client python ops/release.py "What is new, in one sentence"
    uv run --project client python ops/release.py "..." --new "A second line" --better "A third" --fixed "A fourth"

1. uploads `client/packaging/dist/MFDInvoice-Setup.exe` to the website's file store, replacing the one before
   (`bun run installer` in website/site: the live bucket)
2. writes the release at the top of `RELEASES` in `website/site/src/consts.ts`: the version, today's date, the size,
   the installer's SHA-256 and what is new. Downloads, Release notes and the app's update screen all read it

Nothing is live until you deploy the website: `cd website/site; bun run deploy`. From then every older app shows
only Update now. If the steps changed too, publish them first (`ops/automation.py publish`, then deploy `server/`).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "client" / "packaging" / "dist"
SITE = ROOT / "website" / "site"
CONSTS = SITE / "src" / "consts.ts"
MARK = "  /* ops/release.py writes the newest release here */\n"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def ts(text: str) -> str:
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def main() -> None:
    ap = argparse.ArgumentParser(description="Upload the built installer and write the release into the website.")
    ap.add_argument("new", help="what is new, in one sentence: also the sentence on the app's update screen")
    ap.add_argument("--new", dest="more", action="append", default=[], help="another line, tagged New")
    ap.add_argument("--better", action="append", default=[], help="another line, tagged Better")
    ap.add_argument("--fixed", action="append", default=[], help="another line, tagged Fixed")
    ap.add_argument("--no-upload", action="store_true", help="only write consts.ts (the installer is already up)")
    a = ap.parse_args()

    try:
        built = json.loads((DIST / "release.json").read_text(encoding="utf-8"))
    except OSError:
        sys.exit("Nothing is built: run `uv run python packaging/build.py` in client/ first.")
    installer = Path(built["installer"])
    if not installer.is_file():
        sys.exit(f"{installer} is missing: build again.")
    consts = CONSTS.read_text(encoding="utf-8")
    if MARK not in consts:
        sys.exit(f"{CONSTS} has no RELEASES list to write into.")
    if f"version: '{built['version']}'" in consts.split("export const RELEASES", 1)[1].split("];", 1)[0]:
        sys.exit(f"{built['version']} is already released. Raise the version in client/pyproject.toml, commit, build.")

    if not a.no_upload:
        print(f"Uploading {installer.name} ({built['bytes'] / 1e6:.0f} MB) to the website's file store...", flush=True)
        up = subprocess.run(["bun", "run", "installer", "--", str(installer)], cwd=SITE, shell=True, check=False)
        if up.returncode:
            sys.exit("The upload failed. Nothing was written. Are you signed in? (bunx wrangler login)")

    today = date.today()
    changes = [("New", a.new)] + [("New", x) for x in a.more] + [("Better", x) for x in a.better] + [("Fixed", x) for x in a.fixed]
    entry = ("  { version: " + ts(built["version"]) + ", date: " + ts(f"{today.day} {MONTHS[today.month - 1]} {today.year}")
             + ", size: " + ts(f"About {round(built['bytes'] / 1e6)} MB") + ",\n    sha256: " + ts(built["sha256"])
             + ", note: " + ts(a.new) + ",\n    changes: ["
             + ", ".join("{ tag: " + ts(tag) + ", text: " + ts(text) + " }" for tag, text in changes) + "] },\n")
    CONSTS.write_text(consts.replace(MARK, MARK + entry), encoding="utf-8", newline="\n")
    print(f"""
{built['version']} is written into {CONSTS.relative_to(ROOT)}.
Nothing is live yet. To make it live (every older app then shows Update now):

  cd website/site; bun run deploy
""")


if __name__ == "__main__":
    main()
