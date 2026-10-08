"""KFintech: every page a run touches, and what its files mean. `run.py` calls these in order; nothing here decides
what comes next.

KFintech differs from CAMS in four ways that matter here.

**There is a password, and a captcha.** The username and password are typed here. The captcha is typed only by the
person at the machine: its picture is cropped from the page and shown to them, and what they type goes into the box.
A wrong captcha gets a new image, three times at most.

**The invoices are downloaded, not emailed.** No waiting.

**The upload is the page itself.** One file per fund in a grid, and its one button uploads whatever the grid holds.

**The session survives navigation**, so unlike CAMS this flow opens its pages by address.

One portal bug is worked around on purpose, because it eats the newest month: the upload page builds its month list
with `toISOString()`, which is UTC, so between midnight and 05:30 IST the list starts a month early and the month
wanted is missing. The option is added back and KFintech accepts it (verified 20 Sep 2026).
"""

from __future__ import annotations

import calendar
import contextlib
import re
from collections.abc import Awaitable, Callable
from datetime import date
from pathlib import Path

from playwright.async_api import Error as PWError, Page, expect

from client.automation import files, signature, widgets as w, words
from client.automation.invoices import parties
from client.automation.page import SLOW_MS, Changed, Refused, Stop, arns_in, arns_shown, seen, texts
from client.automation.widgets import KFIN as K, missing
from client.automation.words import KFIN as REG, MONTHS

C, L, D, U, PR = K["common"], K["login"], K["download"], K["upload"], K["profile"]

DATA = "/dssapi/GetGeneric"   # the call that fills the upload page's table: as the page opens, and per month chosen
LOGIN_API = "/dssapilogin/login/loginAPI"   # the sign-in's call: statusCode 10000 signed in, 10001 "Invalid Password"
TAB_CLICKS = 10            # a tab clicked too soon after the page loads is dropped; ~2 s between clicks
CAPTCHA_TRIES = 3          # each wrong captcha is another image for the person to read; keep it small

# (the captcha's picture, which attempt this is, what to say above it) -> {"text": what they typed, "refresh": bool}
AskCaptcha = Callable[[bytes, int, str], Awaitable[dict]]


class Cancelled(Exception):
    """The person closed the captcha without an answer."""


# --- the month, in the spellings KFintech uses ----------------------------------------------------------------------

def trail_month(period: str) -> tuple[int, int]:
    """Payment month 'SEP-2026' -> trail month (2026, 8). KFintech's menus list the trail month, and getting this
    backwards fetches the wrong month's invoices."""
    m, y = period.split("-")
    i = MONTHS.index(m.upper())
    return (int(y), i) if i else (int(y) - 1, 12)


def download_label(period: str) -> str:
    """'SEP-2026' -> 'August-2026', for the Download page's month options."""
    y, m = trail_month(period)
    return f"{calendar.month_name[m]}-{y}"


def upload_value(period: str) -> str:
    """'SEP-2026' -> '2026-08', for the upload page's month select."""
    y, m = trail_month(period)
    return f"{y}-{m:02}"


def _month_before(d: date) -> str:
    """The newest month the upload page would offer on a given day: date(2026, 9, 20) -> '2026-08'."""
    return f"{d.year - (d.month == 1)}-{(d.month - 2) % 12 + 1:02}"


# --- getting on the portal ------------------------------------------------------------------------------------------

async def go(page: Page, name: str) -> None:
    await page.goto(K["urls"][name], timeout=SLOW_MS)


async def alerts(page: Page) -> list[str]:
    return await w.toasts(page, C["alert"])


async def _errors(page: Page) -> list[str]:
    return await w.toasts(page, C["error_alert"])


# Does KFintech's header show "Sign Up" only to a browser that is not signed in? Learnt each time a tab is seen to be
# signed in (the button must be gone then). Until it has been learnt, the button is not read as anything.
_sign_up_means_out: bool | None = None


async def dropped(page: Page) -> bool:
    """Has the session ended? When the sign-in form's username box can be seen, or the header's "Sign Up" (KFintech
    shows a signed-out browser its pages' empty shells, not the sign-in form: an ended session must never be read as
    "nothing listed"). A wrong "dropped" asks the person for a captcha they should never be asked for, so anything
    unclear means carry on."""
    if await w.visible(page.locator(L["username"])):
        return True
    return bool(_sign_up_means_out) and await w.visible(page.locator(L["signed_out"]))


async def _in_as(page: Page) -> None:
    """This tab is signed in right now: note whether "Sign Up" is gone, as it should be."""
    global _sign_up_means_out
    _sign_up_means_out = not await w.visible(page.locator(L["signed_out"]))


async def who(page: Page, within_s: int = 15) -> set[str]:
    """The ARNs this tab is signed in as, asked of the Dashboard (the page known to print them). Empty when it is not
    signed in: the Dashboard then shows the sign-in form."""
    with contextlib.suppress(PWError):
        await go(page, "dashboard")
        for _ in range(within_s * 2):
            if await w.visible(page.locator(L["username"])):
                return set()
            shown = arns_in(await page.locator("body").inner_text())
            if shown:
                await _in_as(page)
                return shown
            await page.wait_for_timeout(500)
    return set()


async def enter(page: Page, username: str, password: str, ask_captcha: AskCaptcha, want: str) -> set[str]:
    """Be signed in to KFintech on this tab, and return every ARN the signed-in page shows.

    The session a run before this one left is used when it is this ARN's: that saves the person a captcha. One signed
    in as another ARN is dropped first.
    """
    await page.add_locator_handler(page.locator(C["promo_close"]).first, lambda b: b.click())
    shown = await who(page)
    if want in shown:
        return shown
    await _forget(page)
    return await sign_in(page, username, password, ask_captcha)


async def _forget(page: Page) -> None:
    """Forget everything KFintech kept in this browser: cookies, and the site's own storage, where its firewall's bot
    check keeps its state. A sign-in cut off by the network left that state bad, and every later sign-in from this
    browser was turned away ("Request Rejected") while a fresh browser got in (8 Oct). Done before every fresh
    sign-in; a session still good was used before this is reached."""
    await page.context.clear_cookies(domain=re.compile(r"kfintech\.com$"))
    cdp = await page.context.new_cdp_session(page)
    try:
        for origin in ("https://dss.kfintech.com", "https://www.kfintech.com", "https://kfintech.com"):
            await cdp.send("Storage.clearDataForOrigin", {"origin": origin, "storageTypes": "all"})
    finally:
        await cdp.detach()


async def _snack(page: Page) -> str:
    """What KFintech's snackbar says. It is orange (a warning), never the red `.MuiAlert-colorError`, so it is read by
    what it is, not by colour."""
    return " ".join(await w.toasts(page, C["snackbar"]))


async def sign_in(page: Page, username: str, password: str, ask_captcha: AskCaptcha) -> set[str]:
    """Username and password typed here, the captcha by the person. KFintech's answer is read from the server's reply
    to the sign-in (statusCode 10000 signed in, 10001 "Invalid Password", anything else is refused in its own words)
    and from the snackbar. A wrong captcha is caught by the page itself ("Captcha Does Not Match"), never reaches
    the server and so costs no sign-in attempt: the person is shown a new one."""
    await go(page, "base")
    replies: list[dict] = []

    async def on_response(r) -> None:
        if LOGIN_API in r.url:
            try:
                replies.append(await r.json())
            except Exception:
                replies.append({"statusCode": "?", "message": await r.text()})
    page.on("response", on_response)
    try:
        for attempt in range(1, CAPTCHA_TRIES + 1):
            await seen(page.locator(L["username"]).first)
            await page.locator(L["username"]).fill(username)
            await page.locator(L["password"]).fill(password)
            picture = await page.locator(L["captcha_image"]).first.screenshot()
            answer = await ask_captcha(picture, attempt, "" if attempt == 1 else "Not quite. Here's a new one.")
            if answer.get("refresh"):
                await page.reload()
                continue
            typed = (answer.get("text") or "").strip()
            if not typed:
                raise Cancelled()
            await page.locator(L["captcha"]).fill(typed)
            replies.clear()
            await page.locator(L["submit"]).click()
            said = ""
            for _ in range(SLOW_MS // 500):               # the dashboard, a reply from the server, or a snackbar
                if page.url.rstrip("/").endswith("/Dashboard") or replies:
                    break
                said = await _snack(page)
                if said:
                    break
                await page.wait_for_timeout(500)
            else:
                raise Changed("KFintech gave no dashboard, no reply and no snackbar within a minute of Sign In")
            await page.wait_for_timeout(800)              # a reply's snackbar trails it
            said = said or await _snack(page)
            reply = replies[-1] if replies else None
            if reply and "Request Rejected" in str(reply.get("message") or ""):
                # KFintech's firewall answered instead of KFintech, with an HTML page: never shown as their words.
                raise Stop("refused", "KFintech's site turned the sign-in away. Wait a few minutes, then try again.",
                           "Nothing was submitted.", registrar=REG)
            if page.url.rstrip("/").endswith("/Dashboard") or (reply and str(reply.get("statusCode")) == "10000"):
                await page.wait_for_url("**/Dashboard", timeout=SLOW_MS)
                shown = await arns_shown(page, "KFintech")
                await _in_as(page)
                return shown
            if reply is None and re.search(r"captcha", said, re.I):
                continue                                  # nothing reached the server: not an attempt
            if reply is None:
                raise Changed(f"KFintech's sign-in page said {said!r}, and the server was not asked")
            message = reply.get("message")
            words_ = (message.get("message") if isinstance(message, dict) else message) or said
            words_ = str(words_ or f"statusCode {reply.get('statusCode')}").strip()
            if re.search(r"lock|block|disabled|attempt", words_, re.I):
                raise Stop("account_locked", "KFintech has locked this login",
                           "Nothing was submitted. KFintech's own words say what to do next.",
                           said=words_, registrar=REG)
            raise Stop("refused", "KFintech didn't accept the sign-in",
                       "Nothing was submitted. Check the KFintech username and password in Settings.",
                       said=words_, registrar=REG)
        raise Refused("KFintech did not accept the characters", "KFintech")
    finally:
        page.remove_listener("response", on_response)


async def arn_of(page: Page, username: str, password: str, ask_captcha: AskCaptcha) -> set[str]:
    """Setup's Verify login: sign in afresh and return every ARN the dashboard shows. What KFintech kept from before
    is forgotten first, as `enter` does."""
    await page.add_locator_handler(page.locator(C["promo_close"]).first, lambda b: b.click())
    await _forget(page)
    return await sign_in(page, username, password, ask_captcha)


GSTIN = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]")


async def profile_of(page: Page) -> dict:
    """Setup, after Verify login: the name on Distributor Profile and the GSTIN View Uploaded fills in once a month
    is picked. {"name": ..., "gstin": ...}, each "" when it could not be read: neither is needed to be signed in."""
    got = {"name": "", "gstin": ""}
    with contextlib.suppress(PWError, Changed):
        await go(page, "profile")
        box = page.locator(PR["name"]).first
        for _ in range(40):                                   # the inputs are filled after the page draws
            got["name"] = (await box.input_value()).strip()
            if got["name"]:
                break
            await page.wait_for_timeout(500)
    with contextlib.suppress(PWError, Changed):
        await go(page, "submitted")
        await page.locator(PR["month_select"]).click()
        option = page.locator(PR["month_option"]).filter(has_text=re.compile(r"\w+-\d{4}")).first
        await seen(option, 30_000)
        await option.click()
        for _ in range(40):
            values = await page.locator("input").evaluate_all("is => is.map(i => i.value.trim())")
            if found := [v for v in values if GSTIN.fullmatch(v)]:
                got["gstin"] = found[0]
                break
            await page.wait_for_timeout(500)
    return got


async def inside(page: Page) -> None:
    if await dropped(page):
        raise Stop("session_ended", "KFintech signed this run out",
                   "KFintech ends a session that sits idle. Run again: it signs in afresh, reads what KFintech has, "
                   "and carries on with the files already on this PC.", registrar=REG)


# --- what KFintech already has ----------------------------------------------------------------------------------------

@contextlib.asynccontextmanager
async def _answered(page: Page, wait: bool):
    """Around a step that makes the upload page ask KFintech for its table: left once KFintech has answered."""
    if not wait:
        yield
        return
    async with page.expect_response(lambda r: DATA in r.url, timeout=SLOW_MS):
        yield


async def _select_tab(page: Page, tab: str) -> None:
    """Click an upload page's tab until it is the selected one. KFintech drops a click made in the first seconds after
    the page loads (seen 7 Oct), so a click proves nothing: `aria-selected` does."""
    button = page.locator(U["tab"].format(name=tab))
    await seen(button)
    for _ in range(TAB_CLICKS):
        await button.click()
        for _ in range(10):
            if await button.get_attribute("aria-selected") == "true":
                return
            await page.wait_for_timeout(200)
    shows = await texts(page, f"{C['alert']}, {C['snackbar']}")
    raise Changed(f"the {tab!r} tab never became selected after {TAB_CLICKS} clicks; the page shows {shows or 'no message'}")


async def open_upload_tab(page: Page, period: str, tab: str, table: bool = False) -> bool:
    """Open the upload page on one tab with this run's month selected. False when the month is not offered at all.
    `table`: the tab's table is about to be read, so KFintech's answer is waited for, first for the month the page
    opens on and then for this one. That takes over six seconds, and until then the table shows the other month."""
    async with _answered(page, table):
        await go(page, "upload")
        await inside(page)
        await _select_tab(page, tab)
    select = page.locator(U["month"]).filter(visible=True).first
    value = upload_value(period)
    listed = [v for v in await select.locator("option").evaluate_all("os => os.map(o => o.value)") if v]
    if value not in listed:
        # The page's own UTC bug: between midnight and 05:30 IST its list starts a month early. Put the month back.
        # Anything else is a month KFintech does not offer yet.
        newest = _month_before(date.today())
        one_before = _month_before(date(int(newest[:4]), int(newest[5:]), 1))
        if not listed or value != newest or listed[0] != one_before:
            await inside(page)                            # an ended session lists no months either
            return False
        await select.evaluate(
            "(s, v) => { const o = document.createElement('option'); o.value = v; o.text = v;"
            " s.insertBefore(o, s.options[1] || null) }", value)
    async with _answered(page, table):
        await select.select_option(value)
    return True


async def read_status(page: Page, period: str) -> list[dict] | None:
    """The upload page's Excel tab, which is KFintech's fullest view of the month: every fund with an invoice, under
    KFintech's own headings, as [{key, status, remarks, taxable, gst, amc, code}]. None when KFintech does not list
    the month yet. Read-only and safe to repeat."""
    if not await open_upload_tab(page, period, "Excel Based Upload", table=True):
        return None
    label = download_label(period)
    # KFintech has answered for this month, and the table is redrawn a moment later: with the month's rows (the month
    # cell says so), or with "No invoice details available for the selected month." (seen live 4 Oct, for a month
    # KFintech had raised nothing for yet). That sentence may also be left over from the month the page opened on,
    # so it is believed only when it is still there a second after the answer.
    shows = ("label => { const c = document.querySelector('main table tbody tr td'); const t = c ? c.innerText.trim() : '';"
             " return t === label ? 'rows' : /^no invoice details/i.test(t) ? 'none' : '' }")
    try:
        for last in (False, True):
            shown = await (await page.wait_for_function(shows, arg=label, timeout=SLOW_MS)).json_value()
            if shown == "rows":
                break
            if last:
                return None
            await page.wait_for_timeout(1000)
    except PWError:
        # The month is in the list and the table showed neither: only a page with no table at all is a page that
        # changed.
        await inside(page)                                # an ended session shows an empty table too
        if not await page.locator("main table").count():
            raise missing(U["table_rows"], f"KFintech never showed {label} in its status table") from None
        return None
    rows = await w.grid(page, U["table_rows"], U["table_header"], tidy=True)
    return [{"key": r.get("Invoice Ref No", "").strip(), "status": r.get("Current Status", ""),
             "remarks": r.get("Remarks", ""), "amc": r.get("AMC", ""), "code": r.get("Fund Code", ""),
             "taxable": words.amount(r.get("Taxable Income")), "gst": words.amount(r.get("GST Amount"))}
            for r in rows if r.get("Invoice Ref No", "").strip()]


# --- the download -----------------------------------------------------------------------------------------------------

async def fetch(page: Page, period: str, folder: Path) -> Path | None:
    """Download the month's invoices as KFintech's one combined zip, into `folder`. None when KFintech does not offer
    the month on its Download page yet."""
    label = download_label(period)
    for _attempt in range(2):
        await go(page, "download")
        await inside(page)
        await page.locator(D["report_invoice"]).check()
        await _pick_all_funds(page)
        if await _pick_month(page, label):
            break
    else:
        await inside(page)
        return None

    await page.locator(D["submit"]).click()
    # The progress snackbars come first ("Preparing to download 7 files...", "Creating combined zip file...").
    final = page.locator(C["alert"]).filter(has_not_text=re.compile(r"Preparing|Creating|Downloading"))
    await seen(final.first)
    told = " ".join(await alerts(page))
    if not await page.locator(D["fetched"]).count():
        raise Refused(told or f"KFintech would not fetch {label}", "KFintech")
    if await page.locator(D["rows"]).count() == 0:
        return None

    link = page.locator(f"{D['combined_row']} {D['row_link']}")
    if await link.count() == 0:
        if await page.locator(D["rows"]).count() != 1:
            raise missing(D["combined_row"], "several files listed but no combined zip")
        link = page.locator(f"{D['rows']} {D['row_link']}")
    folder.mkdir(parents=True, exist_ok=True)
    async with page.expect_download(timeout=600_000) as got:
        await link.first.click()
    download = await got.value
    failure = await download.failure()
    if failure:
        raise Changed(f"KFintech's download did not finish: {failure}")
    out = folder / download.suggested_filename
    await download.save_as(out)
    return out


async def _pick_all_funds(page: Page) -> int:
    await page.locator(D["funds"]).click()
    options = page.locator(C["option"])
    try:
        await seen(options.first, 30_000)
    except Changed:
        raise missing(C["option"], "the fund list did not open") from None
    total = await options.count() - 1                     # minus the "All funds" row itself
    value = page.locator(D["funds_value"])
    if len([v for v in (await value.input_value()).split(",") if v]) != total:
        await page.locator(D["all_funds_box"]).click()
    await expect(value).to_have_value(re.compile(r"^[^,]+(,[^,]+){%d}$" % (total - 1)))
    await page.keyboard.press("Escape")
    return total


async def _pick_month(page: Page, label: str) -> bool:
    """True when the month is offered. The list is fetched once per page load, on the first fund selection, so an
    empty list after that needs the page opened again and not a retry."""
    await page.locator(D["month"]).click()
    option = page.locator(f"{C['option']}[data-value='{label}']")
    try:
        await seen(option, 15_000)
    except Changed:
        await page.keyboard.press("Escape")
        return False
    await option.click()
    await expect(page.locator(D["month_value"])).to_have_value(label)
    return True


# --- the files: a zip of per-fund zips, each the same invoice as a PDF and as a spreadsheet ---------------------------

def read_zip(outer: Path, folder: Path) -> list[dict]:
    """Unpack the download and read every invoice in it. The spreadsheet is the data (exact values, no reading of a
    PDF's text); the PDF is what gets signed and uploaded. One dict per invoice, with its PDF."""
    got = files.zip_extract(outer, folder)
    inner = [f for f in got if f.name.lower().endswith(".zip")]
    loose = [f for f in got if not f.name.lower().endswith(".zip")]
    pdfs: dict[str, Path] = {}
    sheets: dict[str, Path] = {}
    for z in inner:
        for f in files.zip_extract(z, folder):
            (pdfs if f.name.lower().endswith(".pdf") else sheets)[f.name] = f
        z.unlink()                                           # the per-fund zip is unpacked; its two files are kept
    for f in loose:
        if f.name.lower().endswith(".pdf"):
            pdfs[f.name] = f
        elif f.name.lower().endswith((".xlsx", ".xls")):
            sheets[f.name] = f
    if not pdfs:
        raise Changed("the KFintech download held no invoices")

    invoices = []
    for name, sheet in sorted(sheets.items()):
        one = _invoice_from_sheet(files.sheet_read(sheet, sheet="GST INVOICE"), name)
        if not one:
            continue
        one["pdf"] = _matching_pdf(name, pdfs)
        if not one["pdf"]:
            raise Changed(f"{name} has no matching PDF in the KFintech download")
        invoices.append(one)
    if not invoices:
        raise Changed("none of the KFintech spreadsheets could be read; their layout may have changed")
    # One payment can carry two invoices under one reference: GST on top ("ExclusiveGST", with KFintech's serial) and
    # GST within ("InclusiveGST", no serial). Seen 8 Oct, Bank of India, June 2026. KFintech's status lists the reference
    # once: it is one invoice here, its figures the two together, its PDF the one with the serial, and `parts` both.
    by_ref: dict[str, list[dict]] = {}
    for one in invoices:
        by_ref.setdefault(one["ref"], []).append(one)
    out = []
    for ref, parts in by_ref.items():
        if len(parts) == 1:
            out.append(parts[0])
            continue
        main = max(parts, key=lambda p: (bool(p.get("serial")), p["taxable"]))
        merged = {**main, "parts": parts}
        for k in ("taxable", "cgst", "sgst", "igst"):
            merged[k] = round(sum(p[k] for p in parts), 2)
        out.append(merged)
    return out


def _invoice_from_sheet(cells: list[list[str]], name: str) -> dict | None:
    """One KFintech invoice, out of the spreadsheet's cells. The sheet is a printed invoice, not a table: the serial
    and the date sit beside their labels, the fund house is the first line under "Details of Recipient (Billed to)",
    and the figures are the one line item whose first cell is 1: taxable, CGST, SGST and IGST in columns 3, 5, 7, 9."""
    label: dict[str, str] = {}
    all_texts: list[str] = []
    line: list[str] | None = None
    recipient = ""
    for i, row in enumerate(cells):
        for j, v in enumerate(row):
            s = str(v or "").replace("\xa0", " ").strip()
            if not s:
                continue
            all_texts.append(s)
            if s in ("Date :", "Inv serial No. :"):
                label[s] = next((str(x).strip() for x in row[j + 1:] if str(x or "").strip()), "")
            if s == "Details of Recipient (Billed to)" and not recipient:
                recipient = next((str(g[0]).strip() for g in cells[i + 1:] if g and str(g[0] or "").strip()), "")
        if row and _is_one(row[0]) and len(row) >= 10:
            line = row
    gstins = [t.split(":", 1)[1].strip() for t in all_texts if t.startswith("GSTIN:")]
    ref = next((t.split(":", 1)[1].strip() for t in all_texts if t.startswith("Reference Number")), "")
    if not ref or not re.fullmatch(r"[A-Z0-9]+\d{12}", ref) or line is None or not recipient:
        return None
    return {
        "party": parties.kfin(cells), "ref": ref, "fund_code": ref[:-12],
        "serial": label.get("Inv serial No. :", ""), "date": label.get("Date :", ""),
        "amc_name": recipient, "amc_gstin": gstins[1] if len(gstins) > 1 else "",
        "taxable": _money(line[3]), "cgst": _money(line[5]), "sgst": _money(line[7]), "igst": _money(line[9]),
        "sheet": name,
    }


def _is_one(v) -> bool:
    try:
        return float(str(v).strip()) == 1.0
    except ValueError:
        return False


def _money(text: str) -> float:
    try:
        return float(re.sub(r"[^\d.\-]", "", text or "") or 0)
    except ValueError:
        return 0.0


def _matching_pdf(sheet_name: str, pdfs: dict[str, Path]) -> Path | None:
    stem = re.sub(r"\.(xlsx|xls)$", "", sheet_name, flags=re.I)
    return pdfs.get(stem + ".pdf") or next((f for n, f in pdfs.items() if n.startswith(stem[:20])), None)


def read_pdf(one: dict) -> dict:
    """Where the signature goes on one KFintech invoice, after checking the PDF is this row's: it must print this
    row's serial and reference. One that belongs to another row must never go up in its place."""
    got = files.text_layer(one["pdf"])
    text = " ".join(str(i.get("text") or "") for i in got["items"])
    absent = [what for what, value in (("serial", one.get("serial") or ""), ("reference", one["ref"]))
              if not value or value not in text]
    if absent:
        raise Changed(f"{one.get('amc_name') or one['ref']}: the PDF {one['pdf'].name} does not print its "
                      f"spreadsheet's {' or '.join(absent)}")
    return {"gap": signature.gap(got["items"], got["page_w"], got["page_h"]), "page_h": got["page_h"]}


def upload_name(name: str) -> str:
    """KFintech refuses a file name with a space in it. Its own names have none today; this keeps it so."""
    return re.sub(r"\s+", "_", name.strip())


# --- the upload: fill the grid, read it back, press its one button ----------------------------------------------------

async def fill_grid(page: Page, period: str, invoices: list[dict], signed: dict[str, Path],
                    numbers: dict[str, str] | None) -> list[dict]:
    """Open the upload page afresh and fill the On Screen grid for these invoices: the source, each row's file, the
    number and date on the own-invoice path (`numbers` given), the declarations. Returns what was filled, row by row.

    Rows are matched to the invoices by the amounts the row itself shows, because the row order is KFintech's. The
    page is always opened afresh, so nothing an earlier fill attached is left behind. Nothing is submitted here.
    """
    if not await open_upload_tab(page, period, "On Screen Upload"):
        raise Stop("not_listed", f"KFintech doesn't list {words.labels(period)[1]} yet",
                   "Nothing was sent to KFintech.", registrar=REG)
    own_path = numbers is not None
    await page.locator(U["source_mfd"] if own_path else U["source_kfin"]).check()
    heading = download_label(period).replace("-", " ")
    await seen(page.locator(U["details_heading"]).filter(has_text=heading))

    # The rows lag the heading, like the status table. Wait until every taxable amount about to be matched is in the
    # grid, or the matching below would read last month's numbers.
    await page.wait_for_function(
        """want => { const got = [...document.querySelectorAll('main table tbody tr')]
               .filter(r => r.offsetParent)
               .flatMap(r => [...r.cells].map(c => parseFloat(c.innerText.replace(/,/g, ''))));
             return want.every(v => got.some(g => Math.abs(g - v) < 0.005)) }""",
        arg=[i["taxable"] for i in invoices], timeout=SLOW_MS)

    table = page.locator("main table").filter(visible=True).first
    columns = {h.strip(): i for i, h in enumerate(await table.locator("thead th").all_inner_texts())}
    for needed in ("Taxable Income", "GST Amount", "Current Status", "Invoice Number"):
        if needed not in columns:
            raise missing(f"the column {needed!r} in KFintech's upload grid", f"it has {list(columns)}")
    rows = table.locator("tbody tr")
    shown = [list(r.values()) for r in await w.grid(page, "main table tbody tr", tidy=True)]

    filled = []
    for one in invoices:
        gst = one["cgst"] + one["sgst"] + one["igst"]
        # KFintech keeps GST unrounded in the grid while the invoice rounds it, so two paise of slack. Taxable is
        # exact: it is what identifies the row.
        hits = [i for i, cells in enumerate(shown)
                if abs(words.amount(cells[columns["Taxable Income"]]) - one["taxable"]) < 0.005
                and abs(words.amount(cells[columns["GST Amount"]]) - gst) <= 0.02]
        if not own_path:           # on the own path the row's number box is ours to fill, not KFintech's serial
            hits = [i for i in hits if one["serial"] and one["serial"] in shown[i][columns["Invoice Number"]]]
        house = words.fund_house(one["amc_name"], one["fund_code"], REG)
        if len(hits) != 1:
            raise Stop("mismatch", f"{house}'s figures don't match KFintech's page",
                       f"KFintech's upload page shows {len(hits) or 'no'} "
                       f"{'row' if len(hits) == 1 else 'rows'} with taxable {words.inr(one['taxable'])} and GST "
                       f"{words.inr(gst)}. Nothing was sent to KFintech. Run again: the invoices are fetched afresh.",
                       registrar=REG)
        at = hits[0]
        row = rows.nth(at)
        box = row.locator(U["row_file"])
        # A row KFintech has closed (pending its verification, or processed) is greyed with `pointer-events: none` on
        # the file box's parent; the box itself is not `disabled`. Not an error: the invoice cannot be sent now.
        if await box.is_disabled() or not await box.evaluate("b => getComputedStyle(b.parentElement).pointerEvents !== 'none'"):
            raise Stop("refused", f"KFintech isn't taking an upload for {house} now",
                       "Its row is closed: KFintech is still verifying an earlier upload, or has finished with it. "
                       "Nothing was sent to KFintech. Untick it at Your check and run again.",
                       said=shown[at][columns["Current Status"]], registrar=REG)
        if own_path:
            # The number printed in the PDF, and the registrar's invoice date, which the drawn invoice carries.
            field = row.locator(U["row_invoice_no"])
            await field.fill(numbers[one["ref"]])
            await expect(field).to_have_value(numbers[one["ref"]])
            await _type_date(page, row.locator(U["row_invoice_date"]), _dmy(one["date"]))
        await box.set_input_files(str(signed[one["ref"]]))
        filled.append({"key": one["ref"], "row": shown[at][0]})

    for box in U["declarations"]:
        await page.locator(box).check()
    bad = await _errors(page)
    if bad:
        raise Refused(bad, "KFintech")
    return filled


async def verify_grid(page: Page, filled: list[dict]) -> str:
    """KFintech's own count of the funds ready to upload must be the number filled, and it must object to none.
    Returns its words. The whole number: "12 fund(s) ready" is not 2."""
    try:
        await expect(page.locator(U["ready"]).first).to_have_text(re.compile(rf"\b{len(filled)} fund"))
    except AssertionError:
        got = await w.toasts(page, U["ready"]) or ["nothing"]
        raise Stop("mismatch", "KFintech's page doesn't hold what was filled in",
                   f"KFintech says “{got[0]}”, and {words.plural(len(filled), 'fund')} were filled in. Nothing was "
                   "sent to KFintech.", registrar=REG) from None
    bad = await _errors(page)
    if bad:
        raise Refused(bad, "KFintech")
    return (await w.toasts(page, U["ready"]) or [""])[0]


async def _type_date(page: Page, box, dmy: str) -> None:
    """A date field in dd/MM/yyyy sections: typing the digits fills the sections in order. Never seen enabled (it is
    only for the person's own invoice), so it falls back to a plain fill and insists on the result either way."""
    await box.click()
    await page.keyboard.press("Control+a")
    await page.keyboard.type(dmy.replace("/", ""))
    if await box.input_value() != dmy:
        await box.fill(dmy)
    await expect(box).to_have_value(dmy)


def _dmy(iso_or_dmy: str) -> str:
    """KFintech's date field wants dd/MM/yyyy, whatever the spreadsheet gave."""
    text = (iso_or_dmy or "").strip()
    found = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if found:
        return f"{found.group(3)}/{found.group(2)}/{found.group(1)}"
    found = re.match(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", text)
    if found:
        return f"{int(found.group(1)):02}/{int(found.group(2)):02}/{found.group(3)}"
    return text


async def find_submit(page: Page):
    """The one button, "Upload Selected Invoices", which uploads whatever the grid holds."""
    button = page.locator(U["submit"])
    try:
        await expect(button).to_be_enabled()
    except AssertionError:
        said = await _why_disabled(page, button)
        if not said:
            raise
        raise Stop("portal_validation", "KFintech didn't take the invoices", "Nothing was sent to KFintech.",
                   said=said, registrar=REG) from None
    return button


async def _why_disabled(page: Page, button) -> str:
    """KFintech's own reason the Upload button stays disabled: the tooltip on the button's wrapper ("Enter a valid
    invoice number and date for ...") and the badge near it ("4 fund(s) incomplete"). '' when it shows neither."""
    said: list[str] = []
    try:
        await button.locator("xpath=..").hover(force=True, timeout=3_000)
        tip = page.locator("[role=tooltip]").last
        await tip.wait_for(state="visible", timeout=3_000)
        said.append(re.sub(r"\s+", " ", await tip.inner_text()).strip())
    except Exception:                                       # noqa: BLE001 - the reason is a courtesy; no tooltip is fine
        pass
    try:
        near = button.locator("xpath=ancestor::*[position()<=3]").locator("xpath=.//*[contains(., 'incomplete')]").last
        badge = re.sub(r"\s+", " ", await near.inner_text(timeout=2_000)).strip()
        if badge and len(badge) < 80 and badge not in said:
            said.append(badge)
    except Exception:                                       # noqa: BLE001
        pass
    return "\n".join(x for x in said if x)


async def click_submit(page: Page, button) -> tuple[bool, str, bool]:
    """Click the button and wait for KFintech's answer: (did it answer within a minute, its words, did it say every
    invoice went in)."""
    await button.click()
    done = page.locator(C["alert"]).filter(
        has_text=re.compile(f"{U['done_ok']}|{U['done_partial']}|fail|error", re.I))
    try:
        await seen(done.first)
    except Changed:
        return False, " ".join(await alerts(page)), False
    told = " ".join(await alerts(page))
    return True, told, U["done_ok"] in told
