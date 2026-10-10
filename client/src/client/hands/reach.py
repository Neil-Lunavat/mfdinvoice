"""Reaching one of our two servers when a network blocks our domain by name (some Indian ISPs do, subdomains with it).

Each server has a second address on Cloudflare's workers.dev (`brand.json`: `site_fallback`, `server_fallback`).
A call tries the main address first; only when it could not connect (no route, reset, timeout, DNS) is the second
tried. An HTTP answer of any status means the server was reached and is returned as it is. Whichever answered is
used for the rest of the session. In a checkout (`uv run app`) an environment override (`SITE`, `SERVER`) points the
calls elsewhere, with no second address; in the installed software it is ignored.
"""

from __future__ import annotations

import logging
import os
import sys
import urllib.error
import urllib.request

log = logging.getLogger(__name__)


class Reach:
    def __init__(self, label: str, env: str, main: str, fallback: str):
        self.label, self.env, self.main, self.fallback = label, env, main, fallback
        self.on_fallback = False

    def override(self) -> str:
        """The developer's address for this server, only in a checkout: the installed software ignores it."""
        return "" if getattr(sys, "frozen", False) else os.environ.get(self.env, "")

    def base(self) -> str:
        """The address calls go to now."""
        override = self.override()
        if override:
            return override.rstrip("/")
        return self.fallback if self.on_fallback and self.fallback else self.main

    def open(self, path: str, *, data: bytes | None = None, method: str | None = None,
             headers: dict | None = None, timeout: float = 15.0):
        """The open response (use as a context manager). HTTPError is raised as urlopen does."""
        def attempt(base: str):
            req = urllib.request.Request(base + path, data=data, method=method, headers=headers or {})
            return urllib.request.urlopen(req, timeout=timeout)         # noqa: S310 - our own server

        if self.override() or not self.fallback:
            return attempt(self.base())
        first, second = (self.fallback, self.main) if self.on_fallback else (self.main, self.fallback)
        try:
            return attempt(first)
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, OSError):
            r = attempt(second)
            self.on_fallback = second == self.fallback
            log.info("the %s answered on its %s address", self.label, "second" if self.on_fallback else "main")
            return r
