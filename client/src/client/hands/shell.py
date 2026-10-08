"""`uv run app`: the app, with its window.

    uv run app                                      (the website in brand.json; SITE=http://127.0.0.1:8787 for a local one)

One process, two threads. The window (pywebview over WebView2, showing `client/window/dist/` from disk) owns the main
thread, as Windows requires. Everything else (the website, the portal steps, the files, the mailbox, and the window's
side of the boundary, `window.Window`) runs on one asyncio loop in the other thread.

Submit, in a checkout: `uv run app` does everything a run does and stops just before pressing Submit, unless
`config.toml` in the folder it is started from says `[dev]` `submit = true`. The installed app always submits.

The two meet in two places only:

  - the window calls `pywebview.api.call(method, args)`; that runs the `App` method on the loop and returns its answer
  - the app pushes with `window.__automation.push(p)`, in order, through one thread of its own

The installed app is this, frozen by PyInstaller (`client/packaging/`), with the window's built files inside it. Two
more ways it starts belong to updating (`update`): `--finish-update` (the old version's copy, with no window,
installing the new one) and `--updated-from` / `--update-failed` (how the new one, or the old one back again, is told).
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import logging.handlers
import queue
import shutil
import sys
import threading
from pathlib import Path

from client.brand import DATA, NAME
from client.config import Config, Distributor, Paths, load
from client.hands import browser, ops_picture, update
from client.hands.hands import Hands
from client.hands.window import Window
from client.store.db import Store

log = logging.getLogger(__name__)

# The built window: inside the exe when installed, client/window/dist/ in a checkout.
DIST = (Path(getattr(sys, "_MEIPASS", "")) / "window" if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parents[3] / "window" / "dist")

# The window's method name -> (the Window coroutine, how its arguments arrive). "kw": one object, spread as keywords.
METHODS = {
    "load": ("load", "pos"), "sendCode": ("send_code", "pos"), "verifyCode": ("verify_code", "pos"),
    "testMailbox": ("test_mailbox", "kw"), "testCams": ("test_cams", "kw"), "testKfintech": ("test_kfintech", "kw"),
    "prepareSignature": ("prepare_signature", "kw"), "rotateSignature": ("rotate_signature", "pos"),
    "dropSignatureDraft": ("drop_signature_draft", "pos"),
    "findCertificates": ("find_certificates", "pos"), "testCertificate": ("test_certificate", "kw"),
    "tokenHere": ("token_here", "pos"), "reconnect": ("reconnect", "pos"),
    "finishSetup": ("finish_setup", "pos"), "saveDetails": ("save_details", "pos"), "switchArn": ("switch_arn", "pos"),
    "month": ("month", "pos"), "preview": ("preview", "pos"),
    "exportMonth": ("export_month", "pos"), "openPdf": ("open_pdf", "pos"), "showInFolder": ("show_in_folder", "pos"),
    "openFolder": ("open_folder", "pos"), "uninstall": ("uninstall", "pos"), "sendIdea": ("send_idea", "kw"), "answerSurvey": ("answer_survey", "pos"), "skipCams": ("skip_cams", "pos"), "forwardStart": ("forward_start", "pos"), "forwardVerify": ("forward_verify", "pos"), "forwardGmailCode": ("forward_gmail_code", "pos"), "startRun": ("start_run", "kw"), "stopRun": ("stop_run", "pos"),
    "closeRun": ("close_run", "pos"),
    "markNotesRead": ("mark_notes_read", "pos"),
    "sendSupport": ("send_support", "kw"), "open": ("open", "pos"),
    "checkForUpdates": ("check_for_updates", "pos"), "updateNow": ("update_now", "pos"),
    "previewInvoice": ("preview_invoice", "pos"), "previewRegistrar": ("preview_registrar", "kw"),
    "signOut": ("sign_out", "pos"),
    "activateTrial": ("activate_trial", "pos"), "checkPlan": ("check_plan", "pos"), "agree": ("agree", "pos"),
    "here": ("here", "pos"), "pickFile": ("pick_file", "pos"), "dropFile": ("drop_file", "kw"),
    "camsFilesStart": ("cams_files_start", "pos"), "chooseCamsFiles": ("choose_cams_files", "pos"),
    "dropCamsFiles": ("drop_cams_files", "pos"),
    "booksLook": ("books_look", "kw"), "booksImport": ("books_import", "kw"), "booksNext": ("books_next", "kw"), "refreshBooks": ("refresh_books", "pos"),
    "booksSetup": ("books_setup", "kw"), "booksUse": ("books_use", "kw"), "booksForget": ("books_forget", "pos"),
    "zohoConnect": ("zoho_connect", "pos"), "zohoCancel": ("zoho_cancel", "pos"), "zohoDisconnect": ("zoho_disconnect", "pos"),
}


class Pushes:
    """Pushes to the window, in order, from a thread of their own (evaluating script waits on the window). Held until
    the window says it is listening, so nothing said before the page loaded is lost."""

    def __init__(self):
        self.window = None
        self.ready = threading.Event()
        self.q: queue.Queue = queue.Queue()
        threading.Thread(target=self._pump, daemon=True, name="pushes").start()

    def __call__(self, push: dict) -> None:
        self.q.put(push)

    def _pump(self) -> None:
        while True:
            push = self.q.get()
            self.ready.wait()
            try:
                self.window.evaluate_js(f"window.__automation && window.__automation.push({json.dumps(push)})")
            except Exception as e:                        # the window is closing
                log.debug("push not delivered: %s", e)


class Api:
    """What the window's script can reach: `pywebview.api.call(...)`, and nothing else."""

    def __init__(self, loop: asyncio.AbstractEventLoop, win: Window, pushes: Pushes, close):
        self._loop, self._win, self._pushes, self._close = loop, win, pushes, close

    def call(self, method: str, args: list | None = None):
        args = args or []
        if method == "listen":
            self._pushes.ready.set()
            asyncio.run_coroutine_threadsafe(self._win.opened(), self._loop)
            return None
        if method == "answer":
            self._loop.call_soon_threadsafe(self._win.answer, *args)
            return None
        if method == "quit":
            self._close()
            return None
        name, how = METHODS[method]
        fn = getattr(self._win, name)
        coro = fn(**args[0]) if how == "kw" else fn(*args)
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()


def _config(path: Path | None) -> Config:
    """Where the app keeps everything: %LOCALAPPDATA%/<name>/workspace, for an installed app and for `uv run app`
    alike, so what is set up once stays set up through every update. `--config` names a config.toml to use another
    place instead."""
    if path is not None:
        return load(path)
    ws = DATA / "workspace"
    return Config(distributor=Distributor(arn=""),
                  paths=Paths(signature=ws / "signature.png", workspace=ws, inbox=ws / "inbox", db=ws / "client.db"))


def _submits() -> bool:
    """Does a run press Submit? Always, installed. In a checkout only when `config.toml` here says so."""
    if getattr(sys, "frozen", False):
        return True
    try:
        import tomllib
        return tomllib.loads(Path("config.toml").read_text(encoding="utf-8-sig")).get("dev", {}).get("submit") is True
    except (OSError, ValueError):
        return False


def _build_window(dist: Path) -> None:
    """In a checkout, build the window again when its source is newer than the build: a change to the window went
    unseen by `uv run app` until someone remembered `bun run build` (8 Oct)."""
    src = dist.parent
    newest = max((p.stat().st_mtime for p in [*(src / "src").rglob("*"), *src.glob("*.*")]
                  if p.is_file() and p.name != "bun.lock"), default=0)
    index = dist / "index.html"
    if index.exists() and index.stat().st_mtime >= newest:
        return
    import subprocess
    bun = shutil.which("bun")
    if not bun:
        sys.exit("The window needs building and bun is not on PATH: run `bun run build` in client/window.")
    print("Building the window (its source changed)...", flush=True)
    if subprocess.run([bun, "run", "build"], cwd=src).returncode != 0:
        sys.exit("Building the window failed: see above.")


def _check_steps(out: Path) -> int:
    """The build's own check (`packaging/build.py`): can this app get the steps the way an installed one does,
    check our signature on them and import every module in them, and is the standard library here for steps that
    come later? What happened is written to `out`: an exe with no console has nowhere else to say it."""
    import importlib
    import pkgutil
    import traceback

    from client.hands import loader
    lines: list[str] = []
    code = 0
    try:
        auto = asyncio.run(loader.latest())
        lines.append(f"steps {loader.version()} from {'this checkout' if loader.from_checkout() else 'the server'}")
        for m in pkgutil.walk_packages(auto.__path__, auto.__name__ + "."):
            importlib.import_module(m.name)
            lines.append(f"ok {m.name}")
        for name in ("csv", "sqlite3", "email.mime.text", "html.parser", "xml.etree.ElementTree", "zoneinfo",
                     "statistics", "difflib", "http.client", "concurrent.futures", "imaplib", "gzip"):
            importlib.import_module(name)
        lines.append("ok the standard library")
    except BaseException:                              # noqa: BLE001 - whatever it was, the build must hear of it
        lines.append(traceback.format_exc())
        code = 1
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return code


def main() -> None:
    ap = argparse.ArgumentParser(description=f"{NAME}, with its window")
    ap.add_argument("--config", type=Path, default=None, help="a config.toml naming another place for the data")
    ap.add_argument("--window", type=Path, default=DIST, help="the built window (bun run build in client/window)")
    ap.add_argument("--show-browser", action="store_true", help="show the browser a run drives, to watch it")
    ap.add_argument("--check-steps", type=Path, default=None, help=argparse.SUPPRESS)   # the build's own check
    ap.add_argument("--updated-from", default="", help=argparse.SUPPRESS)       # the new version, just installed
    ap.add_argument("--update-failed", default="", help=argparse.SUPPRESS)      # the old version, back again
    ap.add_argument("--finish-update", type=Path, default=None, help=argparse.SUPPRESS)   # the old version's copy
    ap.add_argument("--to", default="", help=argparse.SUPPRESS)
    ap.add_argument("--sha256", default="", help=argparse.SUPPRESS)
    ap.add_argument("--from", dest="was", default="", help=argparse.SUPPRESS)
    ap.add_argument("--app", type=Path, default=None, help=argparse.SUPPRESS)
    ap.add_argument("--pid", type=int, default=0, help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.finish_update:
        sys.exit(update.finish(a.finish_update, a.to, a.sha256, a.was, a.app, a.pid))
    if a.check_steps:
        sys.exit(_check_steps(a.check_steps))

    if not getattr(sys, "frozen", False) and a.window == DIST:
        _build_window(DIST)
    index = a.window / "index.html"
    if not index.exists():
        sys.exit(f"The window is not built: {index} is missing. Run `bun run build` in client/window.")
    cfg = _config(a.config)
    cfg.paths.workspace.mkdir(parents=True, exist_ok=True)
    (cfg.paths.workspace / "logs").mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s",
                        handlers=[logging.handlers.RotatingFileHandler(
                                      cfg.paths.workspace / "logs" / "app.log", maxBytes=5_000_000, backupCount=2,
                                      encoding="utf-8"),
                                  *([logging.StreamHandler()] if sys.stderr else [])])   # installed: no console
    # Every step a run takes on a page is logged, into the file: it is what we read when something of ours broke.
    logging.getLogger("client").setLevel(logging.DEBUG)
    browser.SHOWN = a.show_browser

    import webview

    store = Store(cfg.paths.db)
    hands = Hands(cfg, store)
    pushes = Pushes()
    win = Window(hands, store, pushes)
    win.updated_from, win.update_failed_to = a.updated_from, a.update_failed
    win.submit = _submits()
    log.info("a run on this PC %s", "presses Submit" if win.submit else "stops just before Submit (config.toml)")

    loop = asyncio.new_event_loop()
    ready = threading.Event()

    def run_loop():
        asyncio.set_event_loop(loop)
        loop.call_soon(win.start)                      # once the loop is running: it creates tasks
        loop.call_soon(ready.set)
        loop.run_forever()

    threading.Thread(target=run_loop, daemon=True, name="app").start()
    ready.wait()

    # The window reaches WebView2 over http://127.0.0.1, and WebView2 keeps what it was served: a new build, or an
    # update, went on showing the old window (7 Oct). What it kept is thrown away at every start; nothing else is.
    for kept in ("Cache", "Code Cache"):
        shutil.rmtree(cfg.paths.workspace / "webview" / "EBWebView" / "Default" / kept, ignore_errors=True)

    quitting = threading.Event()
    window = webview.create_window(NAME, url=str(index), js_api=None, width=1376, height=860,
                                   min_size=(1100, 700), background_color="#FAFAF7")

    def close():
        quitting.set()
        window.destroy()

    win.exit = close

    def choose_file(title: str, types: tuple[str, ...]) -> str:
        got = window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=types)
        return str(got[0]) if got else ""

    win.choose_file = choose_file

    def choose_files(title: str, types: tuple[str, ...]) -> list[str]:
        got = window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True, file_types=types)
        return [str(p) for p in got or ()]

    win.choose_files = choose_files
    hands.hwnd = lambda: ops_picture.handle_of(window, NAME)     # a token's PIN box opens over the window
    window.expose(Api(loop, win, pushes, close).call)
    pushes.window = window

    def on_closing():
        # The window's ✕: the window asks once if a run is going, then calls quit. Closing quits; no tray.
        if quitting.is_set():
            return True
        pushes({"type": "close_requested"})
        return False

    window.events.closing += on_closing
    try:
        webview.start(gui="edgechromium", private_mode=False, storage_path=str(cfg.paths.workspace / "webview"))
    finally:
        with contextlib.suppress(Exception):
            asyncio.run_coroutine_threadsafe(_shutdown(hands), loop).result(10)
        loop.call_soon_threadsafe(loop.stop)
        store.close()


async def _shutdown(hands: Hands) -> None:
    hands.shutdown()


if __name__ == "__main__":
    main()
