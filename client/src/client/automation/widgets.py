"""The portals' selector maps, and helpers for the widgets they are built out of.

CAMS is Angular Material and ng-select; KFintech is React and plainer. Each helper here checks its own result, so a
flow stops at the step that went wrong and not three steps later.

Every JavaScript expression is an arrow function: CAMS sends a Content-Security-Policy without `unsafe-eval`, so the
string-expression form of `evaluate` is refused by the page itself.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from playwright.async_api import Error as PWError, Locator, Page, expect

from client.automation.page import SLOW_MS, Changed, seen

HERE = Path(__file__).resolve().parent
CAMS: dict = tomllib.loads((HERE / "cams_selectors.toml").read_text("utf-8"))
KFIN: dict = tomllib.loads((HERE / "kfin_selectors.toml").read_text("utf-8"))
C = CAMS["common"]

# Reading a table cell by cell costs a call per cell. One expression brings the whole grid back at once.
ROWS_TO_GRID = "rows => rows.map(r => [...r.cells].map(c => c.innerText.trim()))"
ROWS_TO_GRID_TIDY = "rows => rows.map(r => [...r.cells].map(c => c.innerText.replace(/\\s+/g, ' ').trim()))"


def missing(what: str, detail: str = "") -> Changed:
    """A page element these steps rely on is not there: the portal has changed."""
    return Changed(f"{what} is not on the page" + (f": {detail}" if detail else ""))


async def grid(page: Page, rows_selector: str, header_selector: str = "", tidy: bool = False) -> list[dict]:
    """A table as a list of dicts keyed by the portal's own column headings."""
    rows = page.locator(rows_selector)
    if await rows.count() == 0:
        return []
    cells = await rows.evaluate_all(ROWS_TO_GRID_TIDY if tidy else ROWS_TO_GRID)
    if not header_selector:
        return [{str(i): v for i, v in enumerate(r)} for r in cells]
    headers = [h.strip() for h in await page.locator(header_selector).all_inner_texts()]
    return [dict(zip(headers, r)) for r in cells]


async def toasts(page: Page, selector: str) -> list[str]:
    return [t.strip() for t in await page.locator(selector).all_inner_texts() if t.strip()]


async def either(page: Page, *selectors: str, timeout: int = SLOW_MS) -> None:
    """Wait for whichever of these appears first: normally "the thing worked" or "an error toast". A wait that only
    looks for success turns a refusal into a mystery."""
    joined = ", ".join(s for s in selectors if s)
    try:
        await expect(page.locator(joined).filter(visible=True).first).to_be_visible(timeout=timeout)
    except AssertionError:
        raise missing(joined, "nothing happened at all") from None


async def type_in(page: Page, selector: str, text: str) -> None:
    """Focus a field and type, key by key, the way a person does. Portals built on React and Angular listen for key
    events, and a pasted value can leave their model empty."""
    await page.locator(selector).first.click()
    await page.keyboard.press("Control+a")
    await page.keyboard.type(text)


# --- Angular Material and ng-select, as CAMS uses them -------------------------------------------------------------

async def dismiss_cookie_banner_when_seen(page: Page) -> None:
    """Click 'Essential only' whenever the cookie banner gets in the way of an action, without a step for it."""
    await page.add_locator_handler(page.locator(C["cookie_essential"]), lambda b: b.click())


async def _opens(page: Page, opener: Locator, inside: Locator, within_ms: int = 30_000) -> bool:
    """Click a list open and wait for what it holds. A click that lands while the page is still loading its data is
    swallowed: the list never opens, and a person would simply click again (8 Oct: CAMS's fund house list sat shut
    until Neil clicked it). So does this: a list not open within 3 s is closed and clicked again, until `within_ms`."""
    tries = max(1, within_ms // 3_000)
    for i in range(tries):
        await opener.click()
        try:
            await expect(inside).to_be_visible(timeout=3_000)
            return True
        except AssertionError:
            if i + 1 < tries:
                await page.keyboard.press("Escape")          # a list half open would swallow the next click
                await page.wait_for_timeout(300)
    return False


async def mat_select_all(page: Page, select: str) -> int:
    """Open a multi mat-select, make sure every option is ticked, close it. Returns how many there were.

    'All Mutual Funds' is a custom option that toggles, so clicking it when everything is already selected would clear
    the lot. Hence the count check and not an unconditional click.
    """
    options = page.locator(C["mat_option"])
    if not await _opens(page, page.locator(select), options.first):
        raise missing(C["mat_option"], "the fund house list did not open") from None
    total = await options.count()
    if await page.locator(C["mat_option_selected"]).count() != total:
        await page.locator(C["mat_select_all"]).click()
    await expect(page.locator(C["mat_option_selected"])).to_have_count(total)
    await page.keyboard.press("Escape")
    await expect(page.locator(C["mat_panel"])).to_be_hidden()
    return total


async def ng_pick(page: Page, select: str, option: str) -> None:
    """Pick an option in an ng-select by its exact text. The visible instance only: the CAMS upload page keeps hidden
    copies of the same control, and filling one of those silently does nothing."""
    pattern = re.compile(rf"^\s*{re.escape(str(option))}\s*$")
    box = page.locator(select).filter(visible=True).first
    choice = page.locator(C["ng_option"]).filter(has_text=pattern)
    if not await _opens(page, box.locator(C["ng_container"]), choice.first):
        raise missing(C["ng_option"], f"the list holding {option!r} did not open")
    await choice.first.click()
    await expect(box.locator(C["ng_value"])).to_have_text(pattern)


async def mat_radio(page: Page, group: str, value: str) -> None:
    """Select a mat-radio-button by its input value, clicking the circle itself. On CAMS's pathway cards the circle is
    the only clickable part; clicking the card body does nothing at all."""
    btn = page.locator(f"{group} mat-radio-button").filter(has=page.locator(f"input[value='{value}']"))
    await btn.locator(".mat-radio-container").click()
    await expect(btn).to_have_class(re.compile(r"\bmat-radio-checked\b"))


def nav_tab(page: Page, text: str) -> Locator:
    return page.locator(C["nav_tab"], has_text=text)


def left_menu(page: Page, text: str) -> Locator:
    return page.locator(C["left_menu_item"], has_text=text)


async def visible(locator: Locator) -> bool:
    """Is it on screen right now? Anything that cannot be told is no."""
    try:
        return await locator.first.is_visible()
    except PWError:
        return False
