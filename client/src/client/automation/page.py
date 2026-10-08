"""The three ways a portal step ends early, and the small things every page read uses.

`Refused`: the portal said no, in its own words, which are quoted to the person unchanged and never interpreted.
`Changed`: the page or a file is not what these steps expect (a portal changed, or did not load). That one is ours.
`Stop`: a stop these steps understand, with the words the person reads: a heading, one or two plain sentences, and the
portal's own words where it gave any.
"""

from __future__ import annotations

import logging
import re

from playwright.async_api import Locator, Page, expect

log = logging.getLogger(__name__)

SLOW_MS = 60_000                 # the portals are slow; nothing here gives up sooner


class Refused(Exception):
    def __init__(self, said: list[str] | str, who: str = ""):
        words = said if isinstance(said, list) else [said]
        self.said = "; ".join(w.strip() for w in words if w.strip())
        self.who = who
        super().__init__(self.said)


class Changed(Exception):
    pass


class Stop(Exception):
    def __init__(self, kind: str, title: str, *lines: str, said: str = "", registrar: str = ""):
        self.kind, self.title, self.lines, self.said, self.registrar = kind, title, list(lines), said, registrar
        super().__init__(f"{kind}: {title}")


async def quiet(page: Page, still_ms: int = 800, within_ms: int = 20_000) -> None:
    """Wait until the page has stopped fetching: no call of its own (fetch, XHR) under way, and none started or ended
    for `still_ms`. CAMS's pages load their data after they draw, and a click made meanwhile is swallowed, or undone
    when the data lands (8 Oct: the fund house list wiped, the GST tab not opened). Gives up quietly after
    `within_ms`: what follows checks its own result."""
    import time
    going: set = set()
    last = [time.monotonic()]

    def began(r) -> None:
        if r.resource_type in ("fetch", "xhr"):
            going.add(r)
            last[0] = time.monotonic()

    def ended(r) -> None:
        if r in going:
            going.discard(r)
            last[0] = time.monotonic()

    page.on("request", began)
    page.on("requestfinished", ended)
    page.on("requestfailed", ended)
    try:
        end = time.monotonic() + within_ms / 1000
        while time.monotonic() < end:
            if not going and (time.monotonic() - last[0]) * 1000 >= still_ms:
                return
            await page.wait_for_timeout(100)
        log.debug("the page was still fetching after %d s: %d calls", within_ms // 1000, len(going))
    finally:
        page.remove_listener("request", began)
        page.remove_listener("requestfinished", ended)
        page.remove_listener("requestfailed", ended)


async def seen(locator: Locator, timeout: int = SLOW_MS) -> None:
    """Wait until this is on screen."""
    log.debug("> seen %s", locator)
    try:
        await expect(locator).to_be_visible(timeout=timeout)
    except AssertionError:
        log.debug("x never seen: %s", locator)
        raise Changed(f"{locator} did not appear within {timeout // 1000} s") from None


async def texts(page: Page, selector: str) -> list[str]:
    return [t.strip() for t in await page.locator(selector).all_inner_texts() if t.strip()]


def arns_in(text: str) -> set[str]:
    """Every ARN a page's text shows, as 'ARN-104512'."""
    return {f"ARN-{n}" for n in re.findall(r"ARN[-\s]?(\d{4,})", text or "", re.I)}


async def arns_shown(page: Page, who: str, within_s: int = 20) -> set[str]:
    """The ARNs a signed-in page shows, read from its text (a selector for the header would be one more thing to go
    stale). The header is drawn a moment after the page, so it is looked for until it is there."""
    for _ in range(within_s * 2):
        found = arns_in(await page.locator("body").inner_text())
        if found:
            return found
        await page.wait_for_timeout(500)
    raise Changed(f"{who} signed in but showed no ARN")
