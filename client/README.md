# client: the app on the person's PC

The **hands** half of Automation. It owns a headless browser, the vault, the signature, the month's files and the
mailbox, and does what the brain (`server/`) tells it through the tunnel. It decides nothing. The agreement it speaks
is `contract/`; the whole shape is explained in `../SOFTWARE.md` §4.

## Run

```
uv sync
uv run app --brain ws://127.0.0.1:8787     # the app, with its window (build it first: bun run build in window/)
uv run hands --brain ws://127.0.0.1:8787   # the app with no window: asks on the console (development)
uv run pytest -q                           # the app's tests, including both halves together in a real browser
uv run python packaging/build.py           # the installer, from the last commit (../docs/OPERATIONS.md, "Releasing the app")
```

The brain runs from `../server` (`uv run server --port 8787`). The window is `window/` (Svelte, built to `window/dist/`); `uv run app` shows it with pywebview
over WebView2 and puts every question to the person there. `ask.Console` stays for `uv run hands` and the tests.

## Code: `src/client/hands/`

Every module opens by saying what it is, so there is no list of them here to go stale. Where to start reading:

- `shell.py` is `uv run app`, and `main.py` is `uv run hands`.
- `hands.py` is the dispatch table: every primitive the brain may call, and nothing that is not one.
- `tunnel.py` and `bridge.py` are the two channels, and the last gate a secret would have to get past.
- `window.py` is the window's side of `window/src/bridge/types.ts`.
- `update.py` is the updater: download, check, install, and the old version back if the new one does not start.

## Beside the hands

`config.py` (the development `config.toml`) and `store/` (settings, the DPAPI vault and the activity log) are what
the hands stand on.

## Files

- `config.toml` and `workspace/` hold real personal data and are gitignored.
- `../samples/`: real files the tests use; not in git. Tests that need them skip themselves when it is absent.

How each portal works: `../docs/portals.md`.
