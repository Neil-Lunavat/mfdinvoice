"""CAMS: every page a run touches, and what its files mean. `run.py` calls these in order; nothing here decides what
comes next.

Two CAMS facts shape all of it.

**One sign-in, and it locks.** Email only: no password and no captcha. CAMS allows one session per email: if an old
one is alive it says so, "click here" ends it and hands back an empty form, and the email is submitted again. Signing
in too often in a short while locks the email for half an hour, so a run signs in once and uses the tab it is already
signed in on whenever there is one. A reload drops the session, so the flow moves by clicking CAMS's own menus and
never by address.

**The upload is CAMS's whole-month template.** Part of a month is sent by omission: the rows left out keep their place
but get no FILE NAME and no PDF in the zip.
"""

from __future__ import annotations

import contextlib
import re
import time
from pathlib import Path

from playwright.async_api import Error as PWError, Page, expect

from client.automation import files, signature, widgets as w, words
from client.automation.invoices import parties
from client.automation.page import SLOW_MS, Changed, Refused, Stop, arns_in, arns_shown, seen, texts
from client.automation.widgets import CAMS as S, grid, missing, toasts
from client.automation.words import CAMS as REG, MONTHS

C, L, F = S["common"], S["login"], S["invoice_form"]
D, ST, U = S["download"], S["status"], S["upload"]
T = S["texts"]

MENUS = {
    "download": (T["menu_download"], D["route"]),
    "upload": (T["menu_upload"], U["route"]),
    "status": (T["menu_status"], ST["route"]),
}

# The emailed report's columns, in order. A difference means CAMS changed the format, which must be heard about at
# once and not by uploading nonsense.
FILE_NAME, CAMS_INVOICE, BROKER_INVOICE = "FILE NAME", "CAMS INVOICE NUMBER", "BROKER INVOICE NUMBER"
REPORT_COLUMNS = [
    "AMC CODE", "AMC NAME", "BROKER CODE", BROKER_INVOICE, CAMS_INVOICE, "PAYMENT MONTH YEAR",
    "BROKER GST NUMBER", "IGST AMOUNT", "CGST AMOUNT", "SGST AMOUNT", "TAXABLE VALUE", FILE_NAME,
]


def month_year(period: str) -> tuple[str, str]:
    m, y = period.split("-")
    return m.upper(), y


def mmyyyy(period: str) -> str:
    """What the report calls a payment month: SEP-2026 -> '092026'. Text, never a number."""
    m, y = period.split("-")
    return f"{MONTHS.index(m.upper()) + 1:02}{y}"


# ---------------------------------------------------------------------------------------------------------------
# getting on the portal and staying there
# ---------------------------------------------------------------------------------------------------------------

async def dropped(page: Page) -> bool:
    """Are we back on the sign-in form? True only when the form can be positively seen: its Submit button, with the
    Email box editable and no sign-out icon. (The signed-in landing page shows the same Email box, filled and
    read-only.) Saying "dropped" when we are not costs a sign-in; saying "still in" when we are not just fails the next
    step with a clear message. So anything that cannot be told means carry on."""
    try:
        if not await page.locator(L["submit"]).first.is_visible():
            return False
        if await page.locator(L["logout"]).first.is_visible():
            return False
        box = page.locator(L["email"]).first
        return await box.is_visible() and await box.is_editable()
    except PWError:
        return False


async def enter(page: Page, email: str, want: str) -> set[str]:
    """Be signed in to CAMS on this tab, and return every ARN the signed-in page shows.

    The tab a run before this one left signed in is used as it is, when it is this ARN's: that costs no sign-in. One
    signed in as another ARN (another of the person's ARNs was run before) is signed out first.
    """
    await w.dismiss_cookie_banner_when_seen(page)
    if "camsonline.com" in page.url and not await dropped(page):
        with contextlib.suppress(PWError, Changed):
            await page.keyboard.press("Escape")                  # a list left open would cover the page
            shown = arns_in(await page.locator("body").inner_text())
            if want in shown and await _on_invoice_pages(page):
                return shown
            if shown:
                await sign_out(page)
    return await sign_in(page, email)


async def _on_invoice_pages(page: Page) -> bool:
    """Signed in, with CAMS's invoice menu on screen: finishing the landing page if a run stopped there."""
    if await w.visible(w.left_menu(page, T["menu_status"])):
        return True
    if await w.visible(page.locator(L["mf_select"])):
        await _land(page)
        return True
    return False


async def sign_in(page: Page, email: str) -> set[str]:
    """Sign in with the email: one press of Submit, or two when CAMS says the old session is still active."""
    await page.goto(S["urls"]["mailback"], timeout=SLOW_MS)
    for attempt in range(2):
        box = page.locator(L["email"]).first
        await seen(box)                       # CAMS draws its form a moment after the page loads
        await box.fill(email)
        await page.locator(L["submit"]).first.click()
        ok = page.locator(L["mf_select"]).first
        active = page.locator(L["session_active"]).first
        field_err = page.locator(L["field_error"]).filter(has_text=re.compile(r"\S"))
        await seen(ok.or_(active).or_(field_err.first).or_(page.locator(C["toast"]).first).first)
        if await ok.is_visible():
            shown = await arns_shown(page, "CAMS")
            await _land(page)
            return shown
        if await active.is_visible() and attempt == 0:
            await page.locator(L["end_session"]).first.click()
            continue
        said = await texts(page, C["toast"]) or [t.strip() for t in await field_err.all_inner_texts()]
        # "Your email ID is locked. Please try again after 30 minutes" is not a wrong email. Only a lock that waiting
        # fixes counts: "access has been suspended" is CAMS's to explain, in its own words.
        if re.search(r"lock(ed)?\b|try again after|after \d+ minute", " ".join(said), re.I):
            raise Stop("account_locked", "CAMS is locked for now",
                       "CAMS locks an email when it is signed in to too many times in a short while. "
                       "Try again in 15 minutes.", said="; ".join(said), registrar=REG)
        raise Refused(said or "CAMS did not accept the email", "CAMS")
    raise Refused("Your session is still active.", "CAMS")


async def _land(page: Page) -> None:
    """From the page CAMS shows right after a sign-in to its GST invoice pages: every fund house, then the GST tab."""
    await page.wait_for_url(L["logged_in_url"], timeout=SLOW_MS)
    await w.mat_select_all(page, L["mf_select"])
    await w.nav_tab(page, T["gst_tab"]).click()
    await page.wait_for_url(D["route"], timeout=SLOW_MS)


async def sign_out(page: Page) -> None:
    """The power icon by the ARN header: signs out at once, so the next sign-in is one press and not two."""
    with contextlib.suppress(PWError, Changed):
        await page.locator(L["logout"]).first.click(timeout=5_000)
        await seen(page.locator(L["submit"]).first, 10_000)


async def arn_of(page: Page, email: str) -> set[str]:
    """Setup's Verify sign-in: sign in with this email and return every ARN the signed-in page shows."""
    await w.dismiss_cookie_banner_when_seen(page)
    return await sign_in(page, email)


async def open_menu(page: Page, name: str) -> None:
    if await dropped(page):
        raise Stop("session_ended", "CAMS signed this run out",
                   "CAMS ends a session that sits idle. Run again: it signs in afresh, reads what CAMS has, and "
                   "carries on with the files already on this PC.", registrar=REG)
    text, route = MENUS[name]
    await w.left_menu(page, text).click()
    await page.wait_for_url(route, timeout=SLOW_MS)


def holder_in(text: str, arn: str) -> str:
    """The holder's name as CAMS shows it, in its header beside the ARN ("ARN-123456 / R K MEHTA")."""
    number = re.sub(r"\D", "", arn)
    m = re.search(r"ARN[-\s]?" + number + r"\s*/\s*([^\n/]{2,120})", text or "", re.I)
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------------------------------------------------------
# what CAMS already has, and what it lists
# ---------------------------------------------------------------------------------------------------------------

async def _pick_month(page: Page, period: str) -> None:
    month, year = month_year(period)
    await w.mat_select_all(page, F["amc"])
    await w.ng_pick(page, F["month"], month)
    await w.ng_pick(page, F["year"], year)


async def read_status(page: Page, period: str) -> list[dict]:
    """The Invoice Status table: [{key, status, remarks}]. Read-only and safe to repeat.

    The query fires as soon as fund house, month and year are set. The page lists an invoice only once it has been
    uploaded, so an empty answer means nothing is with CAMS yet.
    """
    await open_menu(page, "status")
    await _pick_month(page, period)
    await w.either(page, ST["rows"], C["toast"])
    rows = await grid(page, ST["rows"], ST["header_cells"])
    if not rows:
        told = await toasts(page, C["toast"])
        if any(ST["empty_text"].lower().rstrip(".") in t.lower() for t in told):
            return []
        raise Refused(told or "the status query returned nothing", "CAMS")
    kept = [{"key": invoice_key(r), "status": r.get("Status", ""), "remarks": r.get("Remarks", "")} for r in rows]
    return [k for k in kept if k["key"]]


def invoice_key(row: dict) -> str:
    """The CAMS invoice number, which is this registrar's key for an invoice. Its pages show it with the ARN appended
    ('BM/26-27/E/5 / ARN-123456')."""
    for name in ("Invoice No", "Invoice No.", "CAMS Invoice Number", "INVOICE"):
        if row.get(name):
            return str(row[name]).partition(" / ")[0].strip()
    return ""


async def list_month(page: Page, period: str) -> list[str] | None:
    """The invoices CAMS lists for the month on its Download page, by number. None when it lists none yet. Leaves the
    page ready for `request_mailback`."""
    await open_menu(page, "download")
    await _pick_month(page, period)
    await w.either(page, D["invoice_rows"], C["toast"])
    listed = await grid(page, D["invoice_rows"], D["invoice_header_cells"])
    if not listed:
        told = await toasts(page, C["toast"])
        # CAMS's ways of saying the month is not listed yet: "No Invoice Number Found." (seen live 2 Oct), "No Invoice
        # found against this month." (4 Oct)
        if not told or any("no invoice" in t.lower() for t in told):
            return None
        raise Refused(told, "CAMS")
    return sorted({invoice_key(r) for r in listed} - {""})


async def ready_to_ask(page: Page) -> bool:
    """Is the Download page still showing the month's listing, as `list_month` left it?"""
    with contextlib.suppress(PWError):
        return "/IR1" in page.url and await page.locator(D["invoice_rows"]).count() > 0
    return False


async def request_mailback(page: Page) -> str:
    """Ask CAMS to email the month just listed: always "Separate PDF for each AMC (ZIP)". Returns CAMS's reference
    for the request, or '' when CAMS says the same request is already queued (the first email is still coming).

    Not safe to repeat: each request emails a fresh zip. Submit sends the email at once, with no confirmation.
    """
    await w.mat_radio(page, D["format_group"], D["format_zip"])
    await page.locator(D["submit"]).click()
    await w.either(page, D["success"], C["toast"])
    if not await w.visible(page.locator(D["success"])):
        told = await toasts(page, C["toast"])
        if re.search(r"already queued|same input", " ".join(told), re.I):
            return ""
        raise Refused(told or "CAMS did not accept the request", "CAMS")
    await expect(page.locator(D["success_title"]).first).to_have_text("Success")
    return re.sub(r"\s+", " ", await page.locator(D["confirmation_no"]).first.inner_text()).strip()


# ---------------------------------------------------------------------------------------------------------------
# the files CAMS emails: an Excel report (its upload template) and a zip of one PDF per invoice
# ---------------------------------------------------------------------------------------------------------------

def read_report(xls: Path, period: str) -> list[dict]:
    """The report as rows keyed by CAMS's own column headings: every invoice of the month, in CAMS's order. Its
    columns must be exactly the twelve known, and every row must be for this payment month."""
    cells = files.sheet_read(xls)
    headers = [h.strip() for h in (cells[0] if cells else [])]
    if headers != REPORT_COLUMNS:
        raise Changed(f"the CAMS report's columns are not the ones expected: {headers}")
    # each row keeps its place in CAMS's own sheet (`_row`, 0 the first under the headings): the upload writes into it
    rows = [{**dict(zip(headers, r)), "_row": i} for i, r in enumerate(cells[1:]) if any(c.strip() for c in r)]
    want = mmyyyy(period)
    months = {str(r["PAYMENT MONTH YEAR"]).strip() for r in rows}
    if months != {want}:
        label = words.labels(period)[0]
        raise Stop("wrong_files", f"These files aren't {label}'s",
                   f"The Excel report is for {', '.join(_month_of(m) for m in sorted(months)) or 'no month'}. "
                   f"Choose the zip and the Excel from CAMS's email for {label}.", registrar=REG)
    return rows


def _month_of(mmyyyy_: str) -> str:
    try:
        return f"{words.LONG[int(mmyyyy_[:2]) - 1]} {mmyyyy_[2:]}"
    except (ValueError, IndexError):
        return mmyyyy_


def file_name(row: dict) -> str:
    """CAMS's own name for an invoice's PDF in the zip: unique per invoice."""
    return f"{row['AMC CODE']}_{row['BROKER CODE']}_{str(row[CAMS_INVOICE]).replace('/', '')}.pdf"


def match_pdfs(rows: list[dict], extracted: list[Path]) -> dict[str, Path]:
    """Each report row's PDF, by CAMS's own naming of the files in the zip, `<AMC CODE>_<BROKER CODE>_<invoice number
    without slashes>.pdf`. Not by the report's FILE NAME column: CAMS sends that column empty (it is the one filled in
    for the upload). If CAMS ever does fill it, what it says is used."""
    in_zip = {p.name: p for p in extracted}
    found, absent = {}, []
    for r in rows:
        name = str(r.get(FILE_NAME) or "").strip() or file_name(r)
        if name in in_zip:
            found[r[CAMS_INVOICE]] = in_zip[name]
        else:
            absent.append(name)
    if absent:
        raise Stop("wrong_files", "The zip and the Excel don't belong together",
                   f"The zip has no PDF for {words.plural(len(absent), 'invoice')} in the Excel report "
                   f"({', '.join(absent[:3])}). Choose both files from the same CAMS email.", registrar=REG)
    return found


def read_pdf(pdf: Path) -> dict:
    """What one CAMS invoice says, from its text: where the signature goes, who it is billed to, and its date.
    CAMS's report can leave AMC NAME empty; the invoice itself always names the fund house, with its GSTIN and
    address, which the person's own invoice is billed to."""
    got = files.text_layer(pdf)
    items = got["items"]
    party = parties.cams(items)
    return {"gap": signature.gap(items, got["page_w"], got["page_h"]), "page_h": got["page_h"],
            "party": party, "name": party.name if party else words.name_on_invoice(items),
            "date": words.date_on_invoice(items)}


def pack(sending: list[str], report_all: list[dict], report_file: Path, signed: dict[str, Path],
         numbers: dict[str, str] | None, out_zip: Path, out_sheet: Path) -> None:
    """The upload pair for the invoices in `sending`: CAMS's whole template, every row kept, FILE NAME written only
    into the rows being sent, and a zip of only their PDFs. `numbers` is given on the own-invoice path: CAMS's rule
    for a custom format is to fill the Broker Invoice column, and it must be the number printed in that row's PDF."""
    wanted = set(sending)
    files.make_zip(out_zip, [signed[r[CAMS_INVOICE]] for r in report_all if r[CAMS_INVOICE] in wanted])
    edits = []
    for r in report_all:
        key = r[CAMS_INVOICE]
        if key not in wanted:
            continue
        edits.append({"row": r["_row"], "column": FILE_NAME, "value": signed[key].name})
        if numbers is not None:
            edits.append({"row": r["_row"], "column": BROKER_INVOICE, "value": numbers[key]})
    files.sheet_fill(report_file, out_sheet, edits)


# ---------------------------------------------------------------------------------------------------------------
# the upload page: attach, CAMS's review, Continue (its validation), Submit
# ---------------------------------------------------------------------------------------------------------------

async def open_upload(page: Page, period: str, own_path: bool) -> None:
    """Upload page, step 1. The order matters: each choice resets the ones after it, and picking the pathway clears
    the period. Individual, source, Manual pathway, Multi-AMC batch, month, year, Proceed."""
    month, year = month_year(period)
    await open_menu(page, "upload")
    await page.locator(U["entity_individual"]).click()
    await expect(page.locator(U["entity_individual"])).to_have_class(re.compile("gst-tb-btn-active"))
    await w.mat_radio(page, U["source_group"], U["source_custom"] if own_path else U["source_cams"])
    await w.mat_radio(page, U["pathway_group"], U["pathway_manual"])
    await w.mat_radio(page, U["method_group"], U["method_multi"])
    await w.ng_pick(page, F["month"], month)
    await w.ng_pick(page, F["year"], year)
    await page.locator(U["proceed"]).click()
    await w.either(page, U["step2_marker"], C["toast"])
    if not await w.visible(page.locator(U["step2_marker"])):
        raise Refused(await toasts(page, C["toast"]) or "CAMS did not open the upload step", "CAMS")
    await expect(page.locator(U["zip_input"])).to_be_attached()
    await expect(page.locator(U["excel_input"])).to_be_attached()


async def attach(page: Page, zip_file: Path, sheet: Path) -> list[dict]:
    """Attach the zip and the Excel, and read back what CAMS made of them: its Review Bulk Invoice Data dialog, one
    section per fund house. Attaching sends nothing."""
    await page.locator(U["zip_input"]).set_input_files(str(zip_file))
    await page.locator(U["excel_input"]).set_input_files(str(sheet))
    dialog = page.locator(U["review_dialog"])
    await w.either(page, U["review_dialog"], C["toast"])
    if not await w.visible(dialog):
        raise Refused(await toasts(page, C["toast"]) or "CAMS showed no review after the files were attached", "CAMS")
    rows: list[dict] = []
    for sec in await dialog.locator(U["review_section"]).all():
        name = re.sub(r"^\s*Section:\s*", "", await sec.locator("h4").inner_text()).strip()
        headers = [h.strip() for h in await sec.locator(U["review_header_cells"]).all_inner_texts()]
        for cells in await sec.locator(U["review_rows"]).evaluate_all(w.ROWS_TO_GRID):
            rows.append({"Section": name, **dict(zip(headers, cells))})
    return rows


def compare(ours_rows: list[dict], theirs_rows: list[dict], unfilled: list[dict],
            numbers: dict[str, str] | None) -> list[dict]:
    """Where CAMS's review of the upload differs from what was put in it. Empty means they agree. This is a check on
    us: the figures are CAMS's own, so a difference means the Excel went up wrong, or CAMS changed an invoice since
    it emailed the month.

    `ours_rows` are the rows filled in (a FILE NAME and a PDF each); every one must be in CAMS's review. `unfilled`
    are the template's other rows, left exactly as CAMS gave them: CAMS may list them or leave them out, and if it
    lists one, its figures must still be the template's. Each difference: {key, what, ours, theirs}.
    """
    ours = {r[CAMS_INVOICE]: r for r in ours_rows}
    others = {r[CAMS_INVOICE]: r for r in unfilled if r[CAMS_INVOICE] not in ours}
    theirs = {str(r.get("CAMS INVOICE NUMBER", "")).strip(): r for r in theirs_rows}
    out = []
    for inv in sorted(ours.keys() - theirs.keys()):
        out.append({"key": inv, "what": "not in CAMS's review", "ours": "", "theirs": ""})
    for inv in sorted(theirs.keys() - ours.keys() - others.keys()):
        out.append({"key": inv, "what": "in CAMS's review but not in the upload", "ours": "", "theirs": ""})
    fields = [("TAXABLE VALUE", "TAXABLE VALUE(₹ INR)"), ("IGST AMOUNT", "IGST(₹ INR)"),
              ("CGST AMOUNT", "CGST(₹ INR)"), ("SGST AMOUNT", "SGST(₹ INR)")]
    for inv in sorted((ours.keys() | others.keys()) & theirs.keys()):
        a, b = ours.get(inv) or others[inv], theirs[inv]
        for mine, portal_column in fields:
            if not _same_amount(a.get(mine), b.get(portal_column)):
                out.append({"key": inv, "what": mine.title(), "ours": a.get(mine), "theirs": b.get(portal_column)})
        mine = (numbers or {}).get(inv) if inv in ours else None      # only the rows filled in carry the own number
        want = str(mine or a.get(BROKER_INVOICE) or "").strip()
        got = (b.get("BROKER INVOICE NUMBER") or "").strip()
        if want != got:
            out.append({"key": inv, "what": "Invoice number", "ours": want, "theirs": got})
    return out


async def cancel_review(page: Page) -> None:
    with contextlib.suppress(PWError, AssertionError):
        await page.locator(U["review_dialog"]).locator(U["review_cancel"]).click(timeout=5_000)
        await expect(page.locator(U["review_dialog"])).to_be_hidden(timeout=5_000)


async def press_continue(page: Page, sending: list[str]) -> dict:
    """Continue, then CAMS's verdict, row by row. Continue is CAMS's own validation and submits nothing.

    Returns {valid, total, refused: [{key, remarks}], absent: [key]}. Every invoice being sent must be listed and
    valid. The template's other rows are not ours to judge. CAMS first shows a "Waiting for verification..." toast
    while it checks; that is not its answer.
    """
    await page.locator(U["review_dialog"]).locator(U["review_continue"]).click()
    deadline = time.monotonic() + 3 * SLOW_MS / 1000
    while not await w.visible(page.locator(U["validation_marker"])):
        told = [t for t in await toasts(page, C["toast"])
                if not re.search(r"waiting|verification\.\.\.|please wait", t, re.I)]
        if told:
            raise Refused(told, "CAMS")
        if time.monotonic() > deadline:
            raise Refused(await toasts(page, C["toast"]) or "CAMS gave no validation result", "CAMS")
        await page.wait_for_timeout(500)

    counts: dict[str, int | None] = {}
    for h in await page.locator(U["validation_counts"]).all():
        label = (await h.inner_text()).strip().lower()
        around = await h.locator("xpath=..").inner_text()
        found = re.search(r"(\d+)\s*$", around)
        counts[{"total records": "total"}.get(label, label)] = int(found.group(1)) if found else None
    rows = await grid(page, U["validation_rows"], U["validation_header_cells"], tidy=True)
    wanted = set(sending)
    listed = {str(r.get("Cams Invoice Number", "")).strip(): r for r in rows}
    refused = [{"key": k, "remarks": str(r.get("Remarks", "")).strip()} for k, r in listed.items()
               if k in wanted and "SUCCESS" not in str(r.get("Validation", "")).upper()]
    return {"valid": counts.get("valid"), "invalid": counts.get("invalid"), "total": counts.get("total"),
            "refused": refused, "absent": sorted(wanted - listed.keys())}


async def back_to_files(page: Page) -> None:
    """Reupload: back to the file boxes. Nothing was submitted."""
    with contextlib.suppress(PWError):
        await page.locator(U["reupload"]).click(timeout=5_000)


async def find_submit(page: Page):
    """The final Submit, which CAMS draws only once every row has validated. There must be exactly one on screen:
    anything else stops here and nothing is clicked."""
    button = page.locator(U["final_submit"]).filter(visible=True)
    found = await button.count()
    if found != 1:
        raise missing("CAMS's Submit button", f"expected one after validation, found {found}")
    return button


async def click_submit(page: Page, button) -> tuple[bool, str]:
    """Click Submit and wait for something the click itself causes: CAMS's toast, or CAMS leaving the validation
    page. Returns (did CAMS answer within a minute, its words). Not any text saying "Success": the validation table
    just clicked on says SUCCESS on every row."""
    await button.click()
    deadline = time.monotonic() + SLOW_MS / 1000
    while time.monotonic() < deadline:
        with contextlib.suppress(PWError):
            told = await toasts(page, C["toast"])
            if told:
                return True, "; ".join(told)
            if not await page.locator(U["final_submit"]).first.is_visible():
                return True, "; ".join(await toasts(page, C["toast"]))
        await page.wait_for_timeout(300)
    return False, ""


def _same_amount(a, b) -> bool:
    try:
        return abs(float(str(a or 0).replace(",", "")) - float(str(b or 0).replace(",", "").replace("₹", ""))) < 1e-6
    except (TypeError, ValueError):
        return str(a).strip() == str(b).strip()
