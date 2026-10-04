"""What the app has sent to support, read back from the software's server.

    uv run --project client python ops/reports.py              the latest 30
    uv run --project client python ops/reports.py ours         only the ones the app sent by itself (ours to fix)
    uv run --project client python ops/reports.py 12           report 12 in full, and its run record unpacked into
                                                               ~/.mfdinvoice/reports/12/

The admin key is in ~/.mfdinvoice/server-admin.key (made by `bun run first` in server/).
"""

from __future__ import annotations

import io
import json
import os
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home() / ".mfdinvoice"
SERVER = (os.environ.get("SERVER")
          or json.loads((ROOT / "client/src/client/brand.json").read_text(encoding="utf-8"))["server"]).rstrip("/")


def get(path: str) -> bytes:
    key = (HOME / "server-admin.key").read_text(encoding="utf-8").strip()
    req = urllib.request.Request(SERVER + path, headers={"x-admin-key": key, "User-Agent": "MFDInvoice-ops"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"{SERVER}{path}: {e.code} {e.read().decode(errors='replace')[:200]}")


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg.isdigit():
        r = json.loads(get(f"/admin/reports/{arg}"))["report"]
        for k in ("id", "created_at", "kind", "email", "arn", "place", "version", "steps", "pc", "message"):
            print(f"{k:11} {r.get(k) or ''}")
        print("\n--- the app's last log lines ---\n" + (r.get("log") or ""))
        if r.get("record"):
            out = HOME / "reports" / arg
            out.mkdir(parents=True, exist_ok=True)
            zipfile.ZipFile(io.BytesIO(get(f"/admin/reports/{arg}/record"))).extractall(out)
            print(f"\nthe run's record: {out}")
        return
    rows = json.loads(get("/admin/reports?limit=30" + (f"&kind={arg}" if arg else "")))["reports"]
    for r in rows:
        print(f"#{r['id']:<4} {r['created_at'][:16]}  {r['kind']:8} {r.get('arn') or '':11} {r.get('version') or '':7} "
              f"{'rec ' if r.get('record') else '    '}{(r.get('place') or '')[:28]:28} {(r.get('message') or '')[:60]}")
    if not rows:
        print("Nothing yet.")


if __name__ == "__main__":
    main()
