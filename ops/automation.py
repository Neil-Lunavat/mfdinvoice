"""The portal steps, signed and put where the app fetches them.

    uv run --project client python ops/automation.py key        once: make the signing key
    uv run --project client python ops/automation.py publish    zip client/src/client/automation, sign it, and put
                                                                it in server/public/automation/ for the next deploy

The app runs only steps that carry our signature (`client/src/client/hands/loader.py`). The key that makes it is one
file on the owner's PC, outside this repository: ~/.mfdinvoice/automation.key. Whoever holds that file can put code on
every user's PC, so it is never committed, never sent anywhere, and is backed up somewhere safe. Its public half is
written into loader.py by `key`.

`publish` makes nothing live by itself: `bun run deploy` in server/ does.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parent.parent
STEPS = ROOT / "client" / "src" / "client" / "automation"
LOADER = ROOT / "client" / "src" / "client" / "hands" / "loader.py"
OUT = ROOT / "server" / "public" / "automation"
KEY = Path.home() / ".mfdinvoice" / "automation.key"
KEPT = 3                         # how many published versions stay in server/public/automation


def private_key() -> Ed25519PrivateKey:
    if not KEY.is_file():
        sys.exit(f"No signing key at {KEY}. Run `key` first (once), or restore it from your backup.")
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(KEY.read_text(encoding="utf-8").strip()))


def public_hex(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()


def make_key() -> None:
    if KEY.is_file():
        key = private_key()
        print(f"The key is already there: {KEY}")
    else:
        key = Ed25519PrivateKey.generate()
        KEY.parent.mkdir(parents=True, exist_ok=True)
        KEY.write_text(key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                         serialization.NoEncryption()).hex(), encoding="utf-8")
        print(f"Made the signing key: {KEY}\nBack this file up somewhere safe. It is the only copy.")
    text = LOADER.read_text(encoding="utf-8")
    new = re.sub(r'PUBLIC_KEY = "[0-9a-f]{64}"', f'PUBLIC_KEY = "{public_hex(key)}"', text)
    if new != text:
        LOADER.write_bytes(new.encode("utf-8"))
        print("Its public half is now in client/src/client/hands/loader.py")


def bundle() -> bytes:
    """The steps as one zip, the package's own files at its root. The same files always make the same bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(STEPS.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                info = zipfile.ZipInfo(path.relative_to(STEPS).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, path.read_bytes())
    return buf.getvalue()


def publish() -> None:
    key = private_key()
    if public_hex(key) not in LOADER.read_text(encoding="utf-8"):
        sys.exit("The app's public key is not this key's. Run `key` to write it into loader.py, and ship that app.")
    data = bundle()
    version = datetime.now(timezone.utc).strftime("%Y.%m.%d.%H%M")
    OUT.mkdir(parents=True, exist_ok=True)
    name = f"{version}.zip"
    (OUT / name).write_bytes(data)
    manifest = {"version": version, "file": name, "sha256": hashlib.sha256(data).hexdigest(),
                "signature": base64.b64encode(key.sign(data)).decode(), "size": len(data)}
    (OUT / "latest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    for old in sorted(OUT.glob("*.zip"))[:-KEPT]:
        old.unlink()
    print(f"Steps {version}: {len(data) // 1024} KB, signed.\nNot live yet. To put them live: cd server && bun run deploy")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what == "key":
        make_key()
    elif what == "publish":
        publish()
    else:
        sys.exit(__doc__)
