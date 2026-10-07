"""What the app has sent to support, read back from the software's server.

    uv run --project client python ops/reports.py              the latest 30
    uv run --project client python ops/reports.py ours         only the ones the app sent by itself (ours to fix)
    uv run --project client python ops/reports.py 12           report 12 in full, and its run record unpacked into
                                                               ~/.mfdinvoice/reports/12/
    uv run --project client python ops/reports.py pull         every open "ours" and "from a person" report, with its
                                                               log and record, into ~/.mfdinvoice/reports/pull-<when>/,
                                                               grouped by what went wrong, with an INDEX.md to start at

What is pulled holds real invoices: it stays in ~/.mfdinvoice and never goes in the repo.

The admin key is in ~/.mfdinvoice/server-admin.key (made by `bun run first` in server/).
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
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


def every() -> list[dict]:
    """Every report the server keeps (the last 90 days), newest first, 200 at a time."""
    rows: list[dict] = []
    while True:
        page = json.loads(get("/admin/reports?limit=200" + (f"&before={rows[-1]['id']}" if rows else "")))["reports"]
        rows += page
        if len(page) < 200:
            return rows


def slug(text: str, n: int = 60) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text or "").strip("-")[:n] or "no-words"


def pull() -> None:
    """Open reports into one folder: ours (the software stopped on our side) grouped by its words, and what people
    sent, each with report.json, log.txt and its record unpacked. INDEX.md lists the groups, biggest first."""
    rows = [r for r in every() if r.get("state") != "fixed"
            and (r["kind"] in ("ours", "problem") or r.get("ended") == "ours")]
    if not rows:
        print("Nothing open.")
        return
    out = HOME / "reports" / f"pull-{datetime.now():%Y-%m-%d-%H%M}"
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups["from-a-person" if r["kind"] == "problem" else f"ours--{slug(r.get('message') or '')}"].append(r)
    index = [f"# Open reports, pulled {datetime.now():%d %b %Y %H:%M} from {SERVER}", "",
             f"{len(rows)} reports in {len(groups)} groups, biggest first. Each folder: report.json, log.txt, record/.", ""]
    for name, rs in sorted(groups.items(), key=lambda g: -len(g[1])):
        versions = sorted({r.get("version") or "?" for r in rs})
        index.append(f"## {name} ({len(rs)})")
        index.append(f"{(rs[0].get('message') or '').strip()[:300]}")
        index.append(f"Place: {rs[0].get('place') or '-'} · versions {', '.join(versions)} · "
                     f"newest {rs[0]['created_at'][:16]} · people: {len({r.get('email') for r in rs})}")
        for r in rs:
            d = out / name / str(r["id"])
            d.mkdir(parents=True, exist_ok=True)
            full = json.loads(get(f"/admin/reports/{r['id']}"))
            rep = full["report"]
            (d / "log.txt").write_text(rep.pop("log", "") or "", encoding="utf-8")
            (d / "report.json").write_text(json.dumps({**rep, "same_run": full.get("same", [])}, indent=1,
                                                      ensure_ascii=False), encoding="utf-8")
            if r.get("record"):
                zipfile.ZipFile(io.BytesIO(get(f"/admin/reports/{r['id']}/record"))).extractall(d / "record")
            index.append(f"- #{r['id']} {r['created_at'][:16]} {r.get('email') or ''} {r.get('arn') or ''} "
                         f"v{r.get('version') or '?'}{' · record' if r.get('record') else ''}")
        index.append("")
    (out / "INDEX.md").write_text("\n".join(index), encoding="utf-8")
    print(f"{len(rows)} open reports in {len(groups)} groups: {out}")


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "pull":
        pull()
        return
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
