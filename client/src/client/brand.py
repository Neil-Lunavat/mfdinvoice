"""The product's name and the website's address, for the whole app.

Both live in `brand.json` beside this file, the one place the app holds them: the Python half reads it here, and the
window is built with the same file (`client/window/vite.config.ts`). Launch day is one line there.

`DATA` is where the installed app keeps everything on the PC, named for the product: `%LOCALAPPDATA%/MFDInvoice`
(`workspace/` the person's months, settings and vault; `browser/` a browser of our own; `update/` the updater's).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_BRAND = json.loads(Path(__file__).with_name("brand.json").read_text(encoding="utf-8"))

NAME: str = _BRAND["name"]
SITE: str = _BRAND["site"].rstrip("/")          # the website: accounts and plans
SERVER: str = _BRAND["server"].rstrip("/")      # the software's own server: the portal steps, and what is sent to support
FORWARD: str = _BRAND.get("forward", "")        # where a person's Gmail forwards CAMS's mailbacks (hands/forward.py)
DATA: Path = Path(os.environ.get("LOCALAPPDATA", Path.home())) / NAME
