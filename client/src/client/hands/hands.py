"""What the app has on this PC, as one object: the hidden browser it owns and the one door for signing. The window
(`window.Window`) uses it, and hands the portal steps what they need of it (`host.Host`).
"""

from __future__ import annotations

import importlib.metadata
import json
import logging

from client.config import Config
from client.hands import browser as browser_mod, ops_sign
from client.store.db import Store

log = logging.getLogger(__name__)

APP_VERSION = importlib.metadata.version("client")    # the one place it is written: client/pyproject.toml
CDP_PORT = 9222


class Hands:
    def __init__(self, cfg: Config, store: Store):
        self.cfg = cfg
        self.store = store
        self.asker = None                 # the window, once there is one: it asks the person for a token's PIN
        self.browser = browser_mod.Browser(CDP_PORT, cfg.paths.workspace / "browser-profile", self._ua_cache())
        # Which ARN this app is working for, and where its signature is. The window replaces both (Add ARN, the
        # switcher).
        self.arn = lambda: cfg.distributor.arn or ""
        self.signature_path = lambda: cfg.paths.signature
        self.hwnd = lambda: 0             # the window's handle, set by the shell: a token's PIN box opens over it
        self.browser_used_at = 0.0        # when a run last let go of the browser (monotonic); 0: not yet
        self.door = ops_sign.Door(lambda: self.signature_path(), lambda: self.hwnd(), self._ask_pin)

    def _ua_cache(self) -> dict:
        raw = self.store.get("browser_ua_cache")
        return json.loads(raw) if raw else {}

    def save_ua_cache(self) -> None:
        """Each browser's own user agent is worked out once and kept, so the next start is quicker."""
        self.store.put("browser_ua_cache", json.dumps(self.browser.ua_cache))

    async def _ask_pin(self, said: str) -> str | None:
        """A token's PIN, typed in the window: only for a token Windows cannot reach. It goes to the token and
        nowhere else."""
        ask = getattr(self.asker, "pin", None)
        return await ask(said) if ask is not None else None

    def shutdown(self) -> None:
        self.door.release()
        self.browser.close()
