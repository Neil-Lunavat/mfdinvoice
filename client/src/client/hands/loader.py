"""Getting the portal steps: the newest ones, from the software's own server, checked, then run on this PC.

The steps (`client.automation`) are not part of the installed app. Before any portal work the app asks the server which
version is current (`latest`). If this PC does not have it, it is downloaded as one zip, and the zip must carry our
signature: an Ed25519 signature over its bytes, made with a key only we hold and checked against the public key below.
A zip that does not check is never run. No answer from the server means no portal work: a portal may have changed, and
steps that are behind could do the wrong thing.

The zip and its manifest (`{"sha256", "signature"}`) are kept beside the extracted folders: `KEPT/<version>.zip`,
`KEPT/<version>.json`. Every time steps are taken from disk the zip is checked again and extracted fresh into the
folder, so a file changed on this PC since the download is gone before anything is imported. A folder without its zip
and manifest (an older install) is not used.

In a checkout (`uv run app`) the steps are the ones in `client/src/client/automation/`, so a change is tried at once.
Set AUTOMATION=server to make a checkout fetch them the way an installed app does.

The previews in setup and Settings draw with the steps this PC already has (`current`), without asking the server.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import importlib
import importlib.util
import io
import json
import logging
import os
import shutil
import sys
import zipfile
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from client.brand import DATA
from client.hands import server

log = logging.getLogger(__name__)

PACKAGE = "client.automation"
# The public half of the key the steps are signed with (`ops/automation.py key`). The private half never leaves the
# owner's PC.
PUBLIC_KEY = "03d496afaf654a5cbc2959d4aa3c8c3a60f47c244e2826dae3e2e258d371b51b"
KEPT = DATA / "automation"

_loaded: dict = {"version": "", "module": None}


class Unreachable(Exception):
    """The server gave no answer, so the newest steps cannot be told."""


class NotOurs(Exception):
    """What was downloaded is not what we signed."""


def from_checkout() -> bool:
    return not getattr(sys, "frozen", False) and os.environ.get("AUTOMATION") != "server"


def version() -> str:
    return _loaded["version"] or ("checkout" if from_checkout() else "")


async def latest():
    """The current steps, for portal work. Raises `Unreachable` when the server does not answer."""
    if from_checkout():
        return _checkout()
    manifest = await asyncio.to_thread(server.manifest)
    if manifest is None:
        raise Unreachable()
    return await asyncio.to_thread(_have, manifest)


async def current():
    """The steps this PC has, for a preview: no question asked of the server unless it has none at all."""
    if from_checkout():
        return _checkout()
    if _loaded["module"] is not None:
        return _loaded["module"]
    kept = sorted((p for p in KEPT.glob("*.json") if p.with_suffix(".zip").is_file()),
                  key=lambda p: p.with_suffix(".zip").stat().st_mtime)
    if kept:
        try:
            return _from_kept(kept[-1].name.removesuffix(".json"))
        except (NotOurs, OSError, ValueError, KeyError, zipfile.BadZipFile) as e:
            log.warning("the kept steps %s do not check (%s)", kept[-1].name, e)
    return await latest()


def _checkout():
    if _loaded["module"] is None:
        _loaded.update(module=importlib.import_module(PACKAGE), version="checkout")
    return _loaded["module"]


def _have(manifest: dict):
    """The steps this manifest names: already loaded, already on this PC, or downloaded and checked now."""
    want = str(manifest["version"])
    if _loaded["version"] == want:
        return _loaded["module"]
    name = _safe(want)
    try:
        if _manifest_of(name).get("sha256", "").lower() == str(manifest["sha256"]).lower():
            return _from_kept(name)
    except (NotOurs, OSError, ValueError, KeyError, zipfile.BadZipFile) as e:
        log.info("the kept steps %s are not usable (%s); downloading them again", want, e)
    data = server.download(str(manifest["file"]))
    if data is None:
        raise Unreachable()
    check(data, str(manifest["sha256"]), str(manifest["signature"]))
    KEPT.mkdir(parents=True, exist_ok=True)
    (KEPT / f"{name}.zip").write_bytes(data)
    (KEPT / f"{name}.json").write_text(
        json.dumps({"sha256": str(manifest["sha256"]), "signature": str(manifest["signature"])}), encoding="utf-8")
    before = _safe(_loaded["version"])
    module = _from_kept(name)
    log.info("the steps %s were downloaded and checked", want)
    for old in KEPT.glob("*"):                            # the one before is kept, in case; the rest go
        stem = old.name.removesuffix(".part").removesuffix(".zip").removesuffix(".json")
        if stem not in (name, before) or old.name.endswith(".part"):
            if old.is_dir():
                shutil.rmtree(old, ignore_errors=True)
            else:
                old.unlink(missing_ok=True)
    return module


def _manifest_of(name: str) -> dict:
    got = json.loads((KEPT / f"{name}.json").read_text(encoding="utf-8"))
    if not isinstance(got, dict) or not (KEPT / f"{name}.zip").is_file():
        raise NotOurs("the kept steps have no zip or no manifest")
    return got


def _from_kept(name: str):
    """The steps kept under this name: the zip is checked again, extracted fresh into its folder, and imported."""
    kept = _manifest_of(name)
    data = (KEPT / f"{name}.zip").read_bytes()
    check(data, str(kept["sha256"]), str(kept["signature"]))
    folder = KEPT / name
    tmp = folder.with_name(folder.name + ".part")
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist():
            target = (tmp / info.filename).resolve()
            if tmp.resolve() not in target.parents and target != tmp.resolve():
                raise NotOurs(f"a path in the zip leaves its folder: {info.filename}")
        z.extractall(tmp)
    shutil.rmtree(folder, ignore_errors=True)
    tmp.replace(folder)
    return _use(folder, name)


def check(data: bytes, sha256: str, signature: str) -> None:
    """Is this zip the one the manifest names, and did we sign it?"""
    if hashlib.sha256(data).hexdigest() != sha256.lower():
        raise NotOurs("the download is not the file the server named")
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(PUBLIC_KEY)).verify(base64.b64decode(signature), data)
    except (InvalidSignature, ValueError) as e:
        raise NotOurs("the download does not carry our signature") from e


def _use(folder: Path, name: str):
    """Make the steps in this folder the `client.automation` package, in place of any loaded before."""
    for mod in [m for m in sys.modules if m == PACKAGE or m.startswith(PACKAGE + ".")]:
        del sys.modules[mod]
    spec = importlib.util.spec_from_file_location(PACKAGE, folder / "__init__.py",
                                                  submodule_search_locations=[str(folder)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(PACKAGE, None)
        raise
    import client
    client.automation = module
    _loaded.update(module=module, version=name)
    return module


def _safe(version_: str) -> str:
    return "".join(c for c in version_ if c.isalnum() or c in ".-_") or "unnamed"
