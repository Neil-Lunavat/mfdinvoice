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
