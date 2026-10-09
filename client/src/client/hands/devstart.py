"""`uv run app` in a checkout: the test bench (Neil, 9 Oct), then the app itself (`shell.main`).

Everything is real (the portals, the mailbox forwarded through the software's server, Tally, Submit when switched on)
except the website, which is never called (`devsite.py`: test@mfdinvoice.co.in with 000000, the plan always on,
nothing bound, nothing sent to support). The data is `%LOCALAPPDATA%/MFDInvoice-dev/` (`brand.DATA`). The window is
built with the dev panel into `client/window/dist-dev/` (`VITE_DEVAPP=1`); the panel's calls are `devtools.py`. A
run stops just before pressing Submit unless `config.toml` says `[dev]` `submit = true` or the panel switches it on.

This module, `devsite.py` and `devtools.py` are the whole bench, and none of them is in the installed software: the
exe starts at `shell.main` (`packaging/app.py`), `app.spec` leaves the three out, and `packaging/build.py` fails a build
that packs any of them. `shell.py` holds nothing of the bench, only a place to hook in.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from client.brand import DATA
from client.hands import devsite, devtools, server, shell, site

WINDOW = Path(__file__).resolve().parents[3] / "window"
DIST_DEV = WINDOW / "dist-dev"


def _build_window() -> None:
    """Build the window (with the dev panel, into `dist-dev/`) again when its source is newer than the build: a change
    to the window went unseen by `uv run app` until someone remembered to build (8 Oct)."""
    newest = max((p.stat().st_mtime for p in [*(WINDOW / "src").rglob("*"), *(WINDOW / "public").rglob("*"),
                                              *WINDOW.glob("*.*")]
                  if p.is_file() and p.name != "bun.lock"), default=0)
    index = DIST_DEV / "index.html"
    if index.exists() and index.stat().st_mtime >= newest:
        return
    bun = shutil.which("bun")
    if not bun:
        sys.exit("The window needs building and bun is not on PATH: run `bun run build:dev` in client/window.")
    print("Building the window (its source changed)...", flush=True)
    if subprocess.run([bun, "run", "build:dev"], cwd=WINDOW, env={**os.environ, "VITE_DEVAPP": "1"}).returncode != 0:
        sys.exit("Building the window failed: see above.")


def _submits() -> bool:
    """Does a run press Submit? Only when `config.toml` here says `[dev]` `submit = true`."""
    try:
        return tomllib.loads(Path("config.toml").read_text(encoding="utf-8-sig")).get("dev", {}).get("submit") is True
    except (OSError, ValueError):
        return False


class Bench:
    """What `shell.main` is handed: the dev window, and the dev parts put in at start."""

    window = DIST_DEV

    @staticmethod
    def started() -> None:
        """The website answered on this PC, and nothing sent to support. `site.py` and `server.py` hold none of it:
        their functions are replaced here."""
        for name in ("send_code", "verify", "me", "bind", "sign_out", "survey_reply"):
            setattr(site, name, getattr(devsite, name))
        server.report = devsite.report
        shell.log.info("dev bench: the website is not called; data in %s", DATA)

    @staticmethod
    def install(win, hands, store) -> None:
        """The dev panel's methods, on the window and in shell's METHODS; Submit as config.toml says."""
        win.submit = _submits()
        devsite.arns = lambda: list(win.profiles())
        shell.METHODS.update(devtools.install(win, hands, store))


def main() -> None:
    if "--window" not in sys.argv and not any(a.startswith(("--finish-update", "--check-steps")) for a in sys.argv):
        _build_window()
    shell.main(Bench)
