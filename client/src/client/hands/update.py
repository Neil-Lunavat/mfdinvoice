"""Updating the app: software to software.

The website says which version is current, with its installer's SHA-256 (`/api/app/me`). Current is also the minimum: an
older app must update, and there are no optional updates. The window shows the update screen once no run is going on
this PC, and [Update now] does the rest:

1. **Download** the installer from the website (`GET /api/download`) with the app's own token, and **check it** against
   the website's SHA-256 before anything runs. A file that does not match is deleted, never run.
2. **Keep the old version:** this install folder is copied to `update/previous`.
3. **Hand over to that copy.** It runs with `--finish-update` and no window. Because it runs from the copy, the install
   folder is free to be replaced. This app quits.
4. The copy waits for this app to be gone, checks the installer again, and runs it silently (`/VERYSILENT`).
5. It starts the new version and waits for it to say it is up (its window loaded: `started(version)`).
6. **If the installer fails, or the new version exits or never says it is up, the old one comes back:** the new one is
   stopped, the install folder is put back from the copy, and the old version starts with `--update-failed`.

Nothing here runs from a source checkout (`uv run app`): there is nothing installed to replace.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import sys
import time
import urllib.error
from pathlib import Path

from client.brand import DATA, NAME
from client.hands import site

log = logging.getLogger(__name__)

HOME = DATA / "update"
PREVIOUS = HOME / "previous"          # the old version's install folder, while an update is under way
START_WAIT_S = 120.0                  # how long the new version has to open its window
GONE_WAIT_S = 60.0                    # how long the old app has to quit before the copy gives up
CHUNK = 1 << 16
DETACHED = 0x00000008 | 0x00000200    # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP


def installed() -> Path | None:
    """The install folder, when this is the installed app; None from a source checkout."""
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else None


def installer_for(version: str) -> Path:
    return HOME / f"{NAME}-Setup-{version}.exe"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def download(token: str, dest: Path, sha256: str, progress=lambda pct: None) -> str:
    """Fetch the installer into `dest` and check it. "" when it is there and matches, otherwise why not, as the
    update screen words it: no_plan (the plan ended), signed_out, missing (the website has none), unreachable,
    mismatch (it is not the file the website announced)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and sha256_of(dest) == sha256.lower():
        progress(100)
        return ""
    part = dest.with_suffix(".part")
    h = hashlib.sha256()
    try:
        with site.reach.open("/api/download", timeout=60, headers={
                "Authorization": f"Bearer {token}", "User-Agent": site.USER_AGENT}) as r, part.open("wb") as out:
            size, got, said = int(r.headers.get("content-length") or 0), 0, -1
            while chunk := r.read(CHUNK):
                out.write(chunk)
                h.update(chunk)
                got += len(chunk)
                pct = int(got * 100 / size) if size else 0
                if pct != said:
                    progress(min(pct, 99))
                    said = pct
    except urllib.error.HTTPError as e:
        part.unlink(missing_ok=True)
        log.warning("update: the website answered %s to the download", e.code)
        return {401: "signed_out", 403: "no_plan", 503: "missing"}.get(e.code, "unreachable")
    except Exception as e:                           # no connection, a timeout, a name that does not resolve
        part.unlink(missing_ok=True)
        log.warning("update: the download did not finish: %s", e)
        return "unreachable"
    if h.hexdigest() != sha256.lower():
        part.unlink(missing_ok=True)
        log.error("update: the download's SHA-256 is %s, the website announced %s: deleted, not run", h.hexdigest(),
                  sha256)
        return "mismatch"
    part.replace(dest)
    progress(100)
    return ""


def begin(installer: Path, version: str, sha256: str, now: str) -> None:
    """Steps 2 and 3: keep the old version, and hand over to it. The caller quits the app straight after."""
    app = installed()
    if app is None:
        raise RuntimeError("not an installed app")
    shutil.rmtree(PREVIOUS, ignore_errors=True)
    shutil.copytree(app, PREVIOUS)
    exe = PREVIOUS / Path(sys.executable).name
    args = [str(exe), "--finish-update", str(installer), "--to", version, "--sha256", sha256, "--from", now,
            "--app", str(app), "--pid", str(os.getpid())]
    log.info("update: handing over to %s", args)
    subprocess.Popen(args, creationflags=DETACHED, close_fds=True, cwd=str(PREVIOUS))     # noqa: S603


def started(version: str) -> None:
    """The new version is up: its window loaded. The copy that installed it is waiting for this."""
    HOME.mkdir(parents=True, exist_ok=True)
    (HOME / f"started-{version}").write_text(str(os.getpid()), encoding="utf-8")


def tidy() -> None:
    """After a good start: the old version's copy and the installers are not needed any more. Whatever is still in
    use (the copy may take a moment to exit) is left for next time."""
    if installed() is None or not HOME.exists():
        return
    time.sleep(30)
    shutil.rmtree(PREVIOUS, ignore_errors=True)
    for f in HOME.glob("*"):
        if f.is_file():
            f.unlink(missing_ok=True)


# --- the copy, finishing the update (steps 4 to 6) -----------------------------------------------------------------

def finish(installer: Path, to: str, sha256: str, was: str, app: Path, pid: int) -> int:
    HOME.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s",
                        handlers=[logging.FileHandler(HOME / "update.log", encoding="utf-8")], force=True)
    exe = app / Path(sys.executable).name
    log.info("update: %s to %s in %s", was, to, app)
    if not _gone(pid, GONE_WAIT_S):
        log.error("update: the app did not quit; nothing installed (it is still open, on %s)", was)
        return 1
    try:
        same = sha256_of(installer) == sha256.lower()      # checked again: it sat on disk while the app quit
    except OSError as e:
        log.error("update: the installer cannot be read: %s", e)
        same = False
    if not same:
        log.error("update: the installer is not the one that was checked; not run, nothing changed")
        _start(exe, "--update-failed", to)
        return 1
    marker = HOME / f"started-{to}"
    marker.unlink(missing_ok=True)
    try:
        done = subprocess.run([str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/NOCANCEL",  # noqa: S603
                               f"/LOG={HOME / 'install.log'}"], timeout=600, check=False)
    except (OSError, subprocess.SubprocessError) as e:
        log.error("update: the installer did not run: %s", e)
        return _back(app, exe, to)
    if done.returncode != 0:
        log.error("update: the installer exited with %s", done.returncode)
        return _back(app, exe, to)
    new = _start(exe, "--updated-from", was)
    deadline = time.monotonic() + START_WAIT_S
    while time.monotonic() < deadline:
        if marker.exists():
            log.info("update: %s is up", to)
            installer.unlink(missing_ok=True)
            return 0
        if new is None or new.poll() is not None:
            log.error("update: %s exited before its window opened (%s)", to, new.returncode if new else "not started")
            break
        time.sleep(1)
    else:
        log.error("update: %s did not open its window in %.0f s", to, START_WAIT_S)
    if new is not None and new.poll() is None:
        _kill(new.pid)
    return _back(app, exe, to)


def _back(app: Path, exe: Path, to: str) -> int:
    """The old version comes back: the install folder as it was, started again and told the update failed. The
    folder is replaced only from a copy that is really there."""
    if not (PREVIOUS / exe.name).exists():
        log.error("update: there is no copy of the old version in %s; the install folder is left as it is", PREVIOUS)
        return 1
    log.warning("update: putting the old version back")
    for _ in range(10):
        try:
            if app.exists():
                shutil.rmtree(app)
            break
        except OSError as e:                              # a file of the new version still held for a moment
            log.info("update: waiting to remove the new version: %s", e)
            time.sleep(2)
    shutil.copytree(PREVIOUS, app, dirs_exist_ok=True)
    _start(exe, "--update-failed", to)
    return 1


def _start(exe: Path, flag: str, value: str) -> subprocess.Popen | None:
    try:
        return subprocess.Popen([str(exe), flag, value], creationflags=DETACHED, close_fds=True,  # noqa: S603
                                cwd=str(exe.parent))
    except OSError as e:
        log.error("update: could not start %s: %s", exe, e)
        return None


def _gone(pid: int, within: float) -> bool:
    import psutil
    try:
        psutil.Process(pid).wait(within)
    except psutil.NoSuchProcess:
        return True
    except psutil.TimeoutExpired:
        return False
    return True


def _kill(pid: int) -> None:
    import psutil
    try:
        p = psutil.Process(pid)
        for child in p.children(recursive=True):
            child.kill()
        p.kill()
        p.wait(10)
    except psutil.Error:
        pass
