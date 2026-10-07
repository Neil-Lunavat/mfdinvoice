"""The browser the app owns.

Hardened against every way a real PC's browser turns out to be odd. All of it comes from lab F1,
which tested 17 different kinds of machine over about 400 launches:

1. **Never run a browser to ask its version.** On Windows `--version` opens a visible window in the user's own
   profile. Read the exe's file-version resource instead.
2. **Find every browser, not the first path that exists.** Known paths, the per-user install folders, and Windows'
   own App Paths registry, in the decided order (Edge, Chrome, our Chromium).
3. **A browser that exists but does not work is skipped, not fatal.** A half-removed Edge (exe present, DLLs gone),
   a corrupt exe, a policy that blocks headless or remote debugging: each fails fast and the next browser is tried.
4. **Only ever talk to our own browser.** A stale copy of ours (the app was killed) is closed before launch; a
   stranger on our port makes us pick another port instead of driving someone else's browser.
5. **The browser dies with the app.** It is put in a Windows job object that is closed when the app's process ends,
   so a crash or a Task Manager kill cannot leave an invisible browser running for days.
6. **Belt and braces on the window.** The browser is started with SW_HIDE, and a guard thread hides any visible
   top-level window our browser ever owns (a headless browser owns none - F1 measured zero in 120 launches), and
   records that it had to.
7. **Our own browser is downloaded only if it is genuinely needed** - see `ensure_own_chromium`. The 99% with a
   working Edge or Chrome never pay the ~150 MB.

The order is Edge, then Chrome, then ours. Edge first because on a Windows PC it is the browser that machine really
has, so its identity matches what the portals see from everyone else. That margin is small - the labs proved both
portals only object to the word "Headless" in the user agent - so the order is about the margin, not the outcome.
What the ladder actually buys is that a locked-down office PC never dead-ends.
"""

from __future__ import annotations

import asyncio
import ctypes
import ctypes.wintypes as wt
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from client.brand import DATA
from client import errors

log = logging.getLogger(__name__)

# Where each browser usually is, machine-wide then per-user. The App Paths registry is consulted too (see _registered).
CANDIDATES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("edge", (r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
              r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
              r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe")),
    ("chrome", (r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
                r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
                r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")),
)
REGISTERED = (("edge", "msedge.exe"), ("chrome", "chrome.exe"))

# Flags every launch gets. Nothing here is about hiding: they stop the browser doing things that make no sense for a
# window nobody is looking at (first-run tours, default-browser nagging, background updaters).
BASE_FLAGS = (
    "--no-first-run",
    "--no-default-browser-check",
    "--no-service-autorun",
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-breakpad",
    "--disable-features=Translate,OptimizationHints,MediaRouter",
    "--password-store=basic",
    "--use-mock-keychain",
)

HEADLESS_RE = re.compile(r"Headless", re.I)
START_TIMEOUT_S = 20.0
# The browser is hidden. `uv run app --show-browser` shows its window, so a run can be watched on the portals.
SHOWN = False


@dataclass(frozen=True)
class Found:
    engine: str        # edge | chrome | chromium
    exe: Path
    version: str


@dataclass
class Attempt:
    engine: str
    exe: str
    error: str


# --- finding ---------------------------------------------------------------------------------------------------------

def _registered(exe_name: str) -> list[Path]:
    """Where Windows itself says the browser is (the App Paths key installers write)."""
    import winreg

    out = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}") as k:
                v, _ = winreg.QueryValueEx(k, "")
                out.append(Path(os.path.expandvars(v.strip('"'))))
        except OSError:
            pass
    return out


def find_all() -> list[Found]:
    """Every browser we could use, in the decided order, each exe once."""
    seen: set[str] = set()
    found: list[Found] = []
    registered = dict(REGISTERED)
    for engine, paths in CANDIDATES:
        exes = [Path(os.path.expandvars(p)) for p in paths] + _registered(registered[engine])
        for exe in exes:
            key = str(exe).lower()
            if key in seen or "%" in key:
                continue
            seen.add(key)
            if exe.is_file():
                found.append(Found(engine, exe, _version_of(exe)))
    own = _own_chromium()
    if own:
        found.append(Found("chromium", own, _version_of(own)))
    return found


def find() -> Found | None:
    """The first browser we can use, in the decided order."""
    allf = find_all()
    return allf[0] if allf else None


OWN_BROWSER_DIR = DATA / "browser"


def _own_chromium() -> Path | None:
    """The Chromium we downloaded ourselves, if we ever did.

    `chrome.exe` only. Playwright also ships a headless shell, which is smaller and can never show a window, but it
    is not a real browser and its identity would not match anything a portal sees from a person.
    """
    if not OWN_BROWSER_DIR.exists():
        return None
    hits = sorted(OWN_BROWSER_DIR.glob("chromium-*/chrome-win/chrome.exe")) or \
        sorted(OWN_BROWSER_DIR.glob("**/chrome.exe"))
    return hits[-1] if hits else None                      # the newest, if several versions were ever downloaded


def own_chromium_needed() -> bool:
    """Is a download the only way this PC gets a browser?

    True only when nothing else is installed. It deliberately does **not** consider whether the installed browsers
    actually *start* - that is answered by trying them, in `ensure`, because trying is the only honest test and it
    costs a second.
    """
    return not [f for f in find_all() if f.engine != "chromium"]


def download_own_chromium(on_progress=None) -> Path:
    """Download a browser of our own. Called only when this PC has no other way to run one.

    About 150 MB, once, ever. The 99% of people with a working Edge or Chrome never pay it, which is the whole reason
    this is a fallback and not the default: an office PC on a slow line should not be handed a 150 MB download for a
    job the browser it already has can do.

    It uses the downloader that already ships inside the app, so there is no second mechanism to keep working, and it
    lands in our own folder rather than anywhere shared - if the person uninstalls us, it goes with us.
    """
    from playwright._impl._driver import compute_driver_executable, get_driver_env

    OWN_BROWSER_DIR.mkdir(parents=True, exist_ok=True)
    node, cli = compute_driver_executable()
    env = {**get_driver_env(), "PLAYWRIGHT_BROWSERS_PATH": str(OWN_BROWSER_DIR)}
    if on_progress:
        on_progress("Downloading a browser (about 150 MB). This happens once.")
    log.info("no browser on this PC: downloading our own into %s", OWN_BROWSER_DIR)
    try:
        r = subprocess.run([str(node), str(cli), "install", "chromium"], env=env,
                           capture_output=True, text=True, timeout=45 * 60,
                           creationflags=subprocess.CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as e:
        raise errors.Failure(errors.BROWSER_DOWNLOAD.code,
                             "We could not download a browser for this PC.",
                             errors.Detail(extra={"reason": str(e)[:200]})) from e
    exe = _own_chromium()
    if r.returncode != 0 or not exe:
        tail = (r.stderr or r.stdout or "").strip().splitlines()[-1:] or [""]
        raise errors.Failure(
            errors.BROWSER_DOWNLOAD.code,
            "We could not download a browser for this PC. Check the internet connection and try again.",
            errors.Detail(extra={"reason": tail[0][:200]}))
    log.info("downloaded our own browser: %s", exe)
    return exe


def _file_version(exe: Path) -> str | None:
    ver = ctypes.windll.version
    size = ver.GetFileVersionInfoSizeW(str(exe), None)
    if not size:
        return None
    buf = ctypes.create_string_buffer(size)
    if not ver.GetFileVersionInfoW(str(exe), 0, size, buf):
        return None
    ptr, n = ctypes.c_void_p(), ctypes.c_uint()
    if not ver.VerQueryValueW(buf, "\\", ctypes.byref(ptr), ctypes.byref(n)) or not n.value:
        return None
    ms, ls = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_uint32 * 4)).contents[2:4]
    v = f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
    return None if v == "0.0.0.0" else v


def _version_of(exe: Path) -> str:
    """The browser's version, read from the file. Never by running it: on Windows `--version` opens a real window."""
    try:
        v = _file_version(exe)
        if v:
            return v
    except OSError:
        pass
    try:
        dirs = [d.name for d in exe.parent.iterdir() if d.is_dir() and re.fullmatch(r"\d+(\.\d+)+", d.name)]
    except OSError:
        dirs = []
    return max(dirs, key=lambda s: tuple(int(x) for x in s.split("."))) if dirs else "unknown"


def clean_ua(raw: str) -> str:
    """The browser's own user agent with the headless token taken out."""
    return HEADLESS_RE.sub("", raw).replace("  ", " ").strip()


# --- Windows plumbing: job object, window guard, ports, stale copies ------------------------------------------------

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_u32 = ctypes.WinDLL("user32", use_last_error=True)
_EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


class _JobLimits(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wt.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wt.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wt.DWORD), ("SchedulingClass", wt.DWORD)]


class _IoCounters(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in ("r", "w", "o", "rb", "wb", "ob")]


class _ExtLimits(ctypes.Structure):
    _fields_ = [("Basic", _JobLimits), ("Io", _IoCounters), ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t)]


_KILL_ON_JOB_CLOSE = 0x2000
_CREATE_SUSPENDED = 0x4
_ntdll = ctypes.WinDLL("ntdll")
_JobObjectExtendedLimitInformation = 9
_k32.CreateJobObjectW.restype = wt.HANDLE
_k32.OpenProcess.restype = wt.HANDLE


def _kill_with_app(pid: int) -> int | None:
    """Put the browser in a job that Windows closes, killing the browser, when this process ends for any reason."""
    job = _k32.CreateJobObjectW(None, None)
    if not job:
        return None
    info = _ExtLimits()
    info.Basic.LimitFlags = _KILL_ON_JOB_CLOSE
    _k32.SetInformationJobObject(job, _JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info))
    h = _k32.OpenProcess(0x0001 | 0x0100, False, pid)   # PROCESS_TERMINATE | PROCESS_SET_QUOTA
    ok = bool(h) and _k32.AssignProcessToJobObject(job, h)
    if h:
        _k32.CloseHandle(h)
    return job if ok else None


def _tree(pid: int) -> set[int]:
    import psutil

    try:
        p = psutil.Process(pid)
        return {pid} | {c.pid for c in p.children(recursive=True)}
    except psutil.Error:
        return set()


def _visible_windows(pids: set[int]) -> list[tuple[int, str]]:
    hits = []

    def cb(hwnd, _):
        if _u32.IsWindowVisible(hwnd):
            pid = wt.DWORD()
            _u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in pids:
                t = ctypes.create_unicode_buffer(256)
                _u32.GetWindowTextW(hwnd, t, 256)
                hits.append((hwnd, t.value))
        return True

    _u32.EnumWindows(_EnumProc(cb), 0)
    return hits


class _WindowGuard(threading.Thread):
    """Hides any window our browser shows. A headless browser shows none, so this should never fire."""

    def __init__(self, pid: int, every_s: float = 0.1):
        super().__init__(daemon=True)
        self.pid, self.every_s = pid, every_s
        self._stop = threading.Event()
        self._t0 = time.monotonic()

    def run(self):
        while not self._stop.is_set():
            pids = _tree(self.pid)
            if not pids:
                return
            for hwnd, title in _visible_windows(pids):
                _u32.ShowWindow(hwnd, 0)   # SW_HIDE
                log.warning("browser showed a window (%r); hidden", title)
            self._stop.wait(self.every_s if time.monotonic() - self._t0 < 30 else 0.5)

    def stop(self):
        self._stop.set()


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _close_stale(profile: Path) -> int:
    """Close any browser still running on our profile: a leftover from an app that was killed. Returns how many."""
    import psutil

    needle = f"--user-data-dir={profile.resolve()}".lower()
    victims = []
    for p in psutil.process_iter(["cmdline"]):
        try:
            if any(a.lower() == needle for a in (p.info["cmdline"] or [])):
                victims.append(p)
        except psutil.Error:
            pass
    for p in victims:
        try:
            p.kill()
        except psutil.Error:
            pass
    psutil.wait_procs(victims, timeout=5)
    return len(victims)


def _listener_pid(port: int) -> int | None:
    import psutil

    for c in psutil.net_connections("tcp4"):
        if c.laddr and c.laddr.port == port and c.status == psutil.CONN_LISTEN:
            return c.pid
    return None


def _claim(profile: Path):
    """Claim this profile for this app. None means another *running* copy of the app has it.

    A lock on a file next to the profile. Windows drops the lock the instant its owner dies, however it dies, so "it is
    locked" means "a live app is using this browser" and "it is free" means any browser on the profile is a leftover.
    """
    import msvcrt

    profile.parent.mkdir(parents=True, exist_ok=True)
    f = open(profile.with_name(profile.name + ".lock"), "a+b")   # noqa: SIM115 - held for the browser's lifetime
    try:
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        f.close()
        return None
    return f


def _release(f) -> None:
    if f:
        import msvcrt

        try:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        f.close()


class _LaunchFailed(Exception):
    pass


# --- the browser -----------------------------------------------------------------------------------------------------

class Browser:
    """One headless browser, owned by the app, kept alive across dropped connections (labs B1, B6)."""

    def __init__(self, port: int, profile: Path, ua_cache: dict | None = None,
                 allow_download: bool = True, on_progress=None):
        self.port = port
        self.profile = profile
        self.ua_cache = ua_cache if ua_cache is not None else {}
        self.allow_download = allow_download    # false in tests: a test must never pull 150 MB
        self.on_progress = on_progress          # so setup can say what is happening during the one slow moment
        self.downloaded = False
        self.found: Found | None = None
        self.proc: subprocess.Popen | None = None
        self.user_agent = ""
        self.fingerprint = "portal-sufficient"
        self.attempts: list[Attempt] = []
        self._job = None
        self._guard: _WindowGuard | None = None
        self._claim = None
        self._lock = asyncio.Lock()

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    async def ensure(self, fingerprint: str = "portal-sufficient", width: int = 1440, height: int = 900) -> dict:
        """Start it if it is not up. Idempotent, and safe to call twice at once."""
        async with self._lock:
            if self.running:
                return {"browser": self.info(), "fresh": False}
            self.close()
            self._claim = _claim(self.profile)
            if not self._claim:
                raise errors.Failure(
                    errors.ANOTHER_COPY.code,
                    "Another copy of the software is already running on this PC. Close it and try again.")
            self.fingerprint = fingerprint
            self.attempts = []
            # nobody alive owns this profile, so anything still running on it is a leftover from a killed app
            stale = await asyncio.to_thread(_close_stale, self.profile)
            await asyncio.to_thread(_close_stale, self._probe_profile())
            try:
                browsers = await asyncio.to_thread(find_all)
            except Exception:
                self.close()
                raise
            for found in browsers:
                try:
                    await self._start(found, width, height)
                    return {"browser": self.info(), "fresh": True, "closed_stale": stale,
                            "skipped": [a.__dict__ for a in self.attempts]}
                except _LaunchFailed as e:
                    self.attempts.append(Attempt(found.engine, str(found.exe), str(e)))
                    log.warning("%s at %s would not start headless: %s", found.engine, found.exe, e)
                    self._stop_browser()
                except BaseException:
                    self.close()
                    raise
            # Every browser this PC has either does not exist or would not start. Downloading our own is the last
            # resort, deliberately: it is ~150 MB, and it is only reached when there is genuinely no other way.
            if self.allow_download and not any(a.engine == "chromium" for a in self.attempts):
                exe = await asyncio.to_thread(download_own_chromium, self.on_progress)
                try:
                    await self._start(Found("chromium", exe, _version_of(exe)), width, height)
                    self.downloaded = True
                    return {"browser": self.info(), "fresh": True, "closed_stale": stale, "downloaded": True,
                            "skipped": [a.__dict__ for a in self.attempts]}
                except _LaunchFailed as e:
                    self.attempts.append(Attempt("chromium", str(exe), str(e)))
                    self._stop_browser()

            self.close()
            if not self.attempts:
                raise errors.Failure(
                    errors.NO_BROWSER.code,
                    "This PC has no Microsoft Edge or Google Chrome, and no browser could be downloaded.")
            raise errors.Failure(
                errors.NO_BROWSER.code,
                "No browser on this PC would start: " + "; ".join(f"{a.engine}: {a.error}" for a in self.attempts))

    async def _start(self, found: Found, width: int, height: int) -> None:
        self.found = found
        self.user_agent = await self._user_agent_for(found, width, height)
        if not _port_free(self.port):
            self.port = _free_port()          # someone else is on our port; never talk to their browser
        self.proc, self._job, self._guard = self._launch(found, self.user_agent, width, height, self.profile,
                                                         self.port, shown=SHOWN)
        await self._wait_for_cdp(self.proc, self.port)

    def info(self) -> dict:
        f = self.found
        return {"engine": f.engine if f else "chromium", "version": f.version if f else "unknown",
                "user_agent": self.user_agent, "headless": not SHOWN, "fingerprint": self.fingerprint,
                "channel_ready": self.running}

    def close(self) -> None:
        self._stop_browser()
        _release(self._claim)
        self._claim = None

    def _stop_browser(self) -> None:
        if self._guard:
            self._guard.stop()
        if self.proc and self.proc.poll() is None:
            for pid in _tree(self.proc.pid) - {self.proc.pid}:
                try:
                    os.kill(pid, 9)
                except OSError:
                    pass
            self.proc.kill()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        if self._job:
            _k32.CloseHandle(self._job)
        self.proc, self._job = None, None

    # --- the user agent --------------------------------------------------------------------------------------

    def _probe_profile(self) -> Path:
        return self.profile.with_name(self.profile.name + "-probe")

    async def _user_agent_for(self, found: Found, width: int, height: int) -> str:
        key = f"{found.engine}:{found.version}"
        if key in self.ua_cache:
            return self.ua_cache[key]
        port = _free_port()
        probe, job, guard = self._launch(found, "", width, height, self._probe_profile(), port)
        try:
            raw = (await self._wait_for_cdp(probe, port)).get("User-Agent", "")
        finally:
            guard.stop()
            probe.kill()
            try:
                probe.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
            if job:
                _k32.CloseHandle(job)
        ua = clean_ua(raw)
        self.ua_cache[key] = ua
        return ua

    # --- launching -------------------------------------------------------------------------------------------

    def _launch(self, found: Found, user_agent: str, width: int, height: int, profile: Path, port: int,
                shown: bool = False):
        profile.mkdir(parents=True, exist_ok=True)
        cmd = [str(found.exe),
               f"--remote-debugging-port={port}",
               f"--user-data-dir={profile.resolve()}",
               *([] if shown else ["--headless=new"]),
               f"--window-size={width},{height}",
               *BASE_FLAGS]
        if user_agent:
            cmd.append(f"--user-agent={user_agent}")
        cmd.append("about:blank")
        si = subprocess.STARTUPINFO()
        if not shown:
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0   # SW_HIDE: if anything ever makes this browser headed, its first window starts hidden
        try:
            # started paused, so it is inside the job before it can start any child process
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                                    startupinfo=si, creationflags=subprocess.CREATE_NO_WINDOW | _CREATE_SUSPENDED)
        except OSError as e:
            raise _LaunchFailed(f"could not be started ({e.strerror or e})") from e
        job = _kill_with_app(proc.pid)
        _ntdll.NtResumeProcess(wt.HANDLE(int(proc._handle)))
        guard = None if shown else _WindowGuard(proc.pid)
        if guard:
            guard.start()
        return proc, job, guard

    async def _wait_for_cdp(self, proc: subprocess.Popen, port: int, timeout_s: float = START_TIMEOUT_S) -> dict:
        """Wait for *this* process to answer on its port. Fails fast if it exits; never accepts a stranger."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            code = proc.poll()
            if code is not None:
                raise _LaunchFailed(f"exited straight away (code {code:#x})")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2) as r:
                    data = json.loads(r.read())
                owner = await asyncio.to_thread(_listener_pid, port)
                if owner is not None and owner not in _tree(proc.pid):
                    raise _LaunchFailed(f"port {port} is answered by another program (pid {owner})")
                return data
            except OSError:
                await asyncio.sleep(0.2)
        raise _LaunchFailed(f"did not answer within {timeout_s:.0f} s (remote debugging blocked?)")

    # --- what the run attaches to ---------------------------------------------------------------------------

    def version_json(self) -> dict:
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/version", timeout=5) as r:
            return json.loads(r.read())

    def browser_ws(self) -> str:
        return self.version_json()["webSocketDebuggerUrl"]


def min_spec() -> dict:
    import platform

    try:
        import psutil
        ram = round(psutil.virtual_memory().total / 1e9, 1)
    except Exception:
        ram = 0.0
    free = round(shutil.disk_usage(Path.home().drive + "\\").free / 1e9, 1)
    short = []
    if ram and ram < 4:
        short.append(f"This PC has {ram} GB of memory. The software needs about 4 GB to run a month comfortably.")
    if free < 2:
        short.append(f"There is {free} GB free on this drive. The software keeps every month's invoices, so it needs room.")
    win = platform.version()
    if platform.system() == "Windows" and int(win.split(".")[-1] or 0) < 19041:
        short.append("This version of Windows is older than the software supports.")
    return {"ok": not short, "ram_gb": ram, "free_disk_gb": free,
            "windows": f"{platform.release()} {win}".strip(), "shortfall": short}
