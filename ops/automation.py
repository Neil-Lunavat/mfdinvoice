"""The portal steps, signed and put live.

    uv run --project client python ops/automation.py key        once: make the signing key (locked with a passphrase)
    uv run --project client python ops/automation.py lock       once: put a passphrase on an older, unlocked key
    uv run --project client python ops/automation.py publish    zip what is committed of client/src/client/automation,
                                                                sign it, and deploy the server with it

The app runs only steps that carry our signature (`client/src/client/hands/loader.py`). The key that makes it is one
file on the owner's PC, outside this repository: ~/.mfdinvoice/automation.key, locked with a passphrase. Whoever holds
that file and its passphrase can put code on every user's PC, so it is never committed, never sent anywhere, and is
backed up somewhere safe. Its public half is written into loader.py by `key`.

`publish` asks for the passphrase, so run it in your own terminal (PowerShell), not through an agent or `!`. It ships
what is committed (the steps are taken from HEAD) and refuses while the steps or the server have uncommitted changes.
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
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


PEM_HEAD = b"-----BEGIN ENCRYPTED PRIVATE KEY-----"
NEEDS_TERMINAL = ("Publishing asks for the signing key's passphrase: run it in your own terminal (PowerShell), "
                  "not through an agent or `!`.")


def is_pem(data: bytes) -> bool:
    return data.lstrip().startswith(PEM_HEAD)


def private_key() -> Ed25519PrivateKey:
    if not KEY.is_file():
        sys.exit(f"No signing key at {KEY}. Run `key` first (once), or restore it from your backup.")
    data = KEY.read_bytes()
    if not is_pem(data):
        sys.exit("The signing key isn't locked yet. Run `uv run --project client python ops/automation.py lock` "
                 "once, in your own terminal.")
    if not sys.stdin.isatty():
        sys.exit(NEEDS_TERMINAL)
    password = getpass.getpass("Passphrase for the signing key: ").encode()
    try:
        key = serialization.load_pem_private_key(data, password=password)
    except ValueError:
        sys.exit("That passphrase doesn't open the signing key.")
    if not isinstance(key, Ed25519PrivateKey):
        sys.exit("The signing key file isn't an Ed25519 key.")
    return key


def new_passphrase() -> bytes:
    first = getpass.getpass("New passphrase for the signing key (at least 12 characters): ")
    if len(first) < 12:
        sys.exit("The passphrase needs at least 12 characters.")
    if getpass.getpass("Again: ") != first:
        sys.exit("The two passphrases are not the same.")
    return first.encode()


def write_locked(key: Ed25519PrivateKey, password: bytes) -> None:
    """The key as an encrypted PEM at KEY: written beside it, read back with the passphrase, then moved into place."""
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.BestAvailableEncryption(password))
    KEY.parent.mkdir(parents=True, exist_ok=True)
    tmp = KEY.with_name(KEY.name + ".new")
    tmp.write_bytes(pem)
    try:
        back = serialization.load_pem_private_key(tmp.read_bytes(), password=password)
        if not isinstance(back, Ed25519PrivateKey) or public_hex(back) != public_hex(key):
            sys.exit("The locked key did not read back the same. Nothing was changed.")
        os.replace(tmp, KEY)
    finally:
        tmp.unlink(missing_ok=True)


def lock_key() -> None:
    if not KEY.is_file():
        sys.exit(f"No signing key at {KEY}.")
    data = KEY.read_bytes()
    if is_pem(data):
        print("The signing key is already locked.")
        return
    if not sys.stdin.isatty():
        sys.exit(NEEDS_TERMINAL)
    key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(data.decode("utf-8").strip()))
    write_locked(key, new_passphrase())
    print("Locked. Your backup of the key is the old, unlocked one: replace it with this file.")


def public_hex(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()


def make_key() -> None:
    if KEY.is_file():
        key = private_key()
        print(f"The key is already there: {KEY}")
    else:
        if not sys.stdin.isatty():
            sys.exit(NEEDS_TERMINAL)
        key = Ed25519PrivateKey.generate()
        write_locked(key, new_passphrase())
        print(f"Made the signing key: {KEY}\nBack this file up somewhere safe. It is the only copy.")
    text = LOADER.read_text(encoding="utf-8")
    new = re.sub(r'PUBLIC_KEY = "[0-9a-f]{64}"', f'PUBLIC_KEY = "{public_hex(key)}"', text)
    if new != text:
        LOADER.write_bytes(new.encode("utf-8"))
        print("Its public half is now in client/src/client/hands/loader.py")


STEPS_GIT = "client/src/client/automation"
GUARDED = [STEPS_GIT, "server/src", "server/wrangler.jsonc", "server/package.json"]


def git(*args: str) -> bytes:
    done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    if done.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed: {done.stderr.decode(errors='replace').strip()}")
    return done.stdout


def changed_lines(porcelain: str) -> list[str]:
    return [ln for ln in porcelain.splitlines() if ln.strip()]


def uncommitted() -> list[str]:
    """What `git status` lists for the steps and the server: empty when all of it is committed."""
    return changed_lines(git("status", "--porcelain", "--", *GUARDED).decode("utf-8", "replace"))


def bundle() -> bytes:
    """The committed steps (HEAD) as one zip, the package's own files at its root. The same commit always makes the
    same bytes."""
    files: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(git("archive", "--format=tar", "HEAD", STEPS_GIT))) as t:
        for m in t.getmembers():
            if not m.isfile() or not m.name.startswith(STEPS_GIT + "/"):
                continue
            name = m.name[len(STEPS_GIT) + 1:]
            if "__pycache__" in name.split("/") or name.endswith(".pyc"):
                continue
            files[name] = t.extractfile(m).read()  # type: ignore[union-attr]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, files[name])
    return buf.getvalue()


def publish() -> None:
    left = uncommitted()
    if left:
        sys.exit("Commit these first: publish ships what is committed, and deploys the server with it:\n" + "\n".join(left))
    key = private_key()
    if public_hex(key) not in LOADER.read_text(encoding="utf-8"):
        sys.exit("The app's public key is not this key's. Run `key` to write it into loader.py, and ship that app.")
    commit = git("rev-parse", "--short", "HEAD").decode().strip()
    data = bundle()
    version = datetime.now(timezone.utc).strftime("%Y.%m.%d.%H%M")
    OUT.mkdir(parents=True, exist_ok=True)
    name = f"{version}.zip"
    (OUT / name).write_bytes(data)
    manifest = {"version": version, "commit": commit, "file": name, "sha256": hashlib.sha256(data).hexdigest(),
                "signature": base64.b64encode(key.sign(data)).decode(), "size": len(data)}
    (OUT / "latest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    for old in sorted(OUT.glob("*.zip"))[:-KEPT]:
        old.unlink()
    print(f"Steps {version} (commit {commit}): {len(data) // 1024} KB, signed. Deploying the server.")
    bun = shutil.which("bun")
    if not bun:
        sys.exit("bun isn't on PATH: run `cd server && bun run deploy` by hand.")
    if subprocess.run([bun, "run", "deploy"], cwd=ROOT / "server").returncode != 0:
        sys.exit("Signed but not live: run `cd server && bun run deploy`.")
    print(f"Steps {version} (commit {commit}) are live.")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what == "key":
        make_key()
    elif what == "lock":
        lock_key()
    elif what == "publish":
        publish()
    else:
        sys.exit(__doc__)
