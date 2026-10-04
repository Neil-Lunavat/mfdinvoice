"""The fund house an invoice is billed to, read off the registrar's own invoice every month.

Its name, GSTIN and address are never typed by the person and never kept from month to month: the registrar's invoice
for the month says who it is billed to, so that is what the person's own invoice says too. CAMS's report leaves AMC
NAME empty, which is why this reads the invoice itself (the text layer the PC already sent up for the signature).

    CAMS       the line under "Invoice No" that carries "GSTIN :<gstin>", then the address lines under it, left of
               that GSTIN column, down to "Address of Supply"
    KFintech   the lines under "Details of Recipient (Billed to)" in the invoice's own spreadsheet, down to "State:"

A trailing line that is only the state's name is dropped from the address: the invoice prints the state on its own line.
"""

from __future__ import annotations

import re

from client.automation.invoices.layout import Party, state_name

GSTIN = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b")


def _lines(items: list[dict]) -> list[list[dict]]:
    """Page 1's words as lines, top of the page first, each left to right."""
    rows: dict[int, list[dict]] = {}
    for w in items:
        if int(w.get("page", 1)) == 1:
            rows.setdefault(round(float(w["y"])), []).append(w)
    return [sorted(ws, key=lambda w: float(w["x"])) for _y, ws in sorted(rows.items(), key=lambda kv: -kv[0])]


def _drop_state(address: list[str], gstin: str) -> list[str]:
    state = state_name(gstin[:2]).lower()
    if address and state and address[-1].strip().lower() == state:
        return address[:-1]
    return address


def cams(items: list[dict]) -> Party | None:
    """The fund house on a CAMS invoice, or None when the layout is not the one we know."""
    lines = _lines(items)
    at = next((i for i, ws in enumerate(lines) if [w["text"] for w in ws[:2]] == ["Invoice", "No"]
               or (ws and ws[0]["text"].startswith("Invoice") and len(ws) > 1 and ws[1]["text"].startswith("No"))),
              None)
    if at is None:
        return None
    for i in range(at + 1, len(lines)):
        ws = lines[i]
        g = next((k for k, w in enumerate(ws) if w["text"].startswith("GSTIN")), None)
        if g is None:
            continue
        column = float(ws[g]["x"]) - 5
        name = " ".join(w["text"] for w in ws[:g]).strip()
        found = GSTIN.search(" ".join(w["text"] for w in ws[g:]).replace(":", " "))
        if not name or not found:
            return None
        address = []
        for more in lines[i + 1:]:
            if more and more[0]["text"].startswith("Address"):
                break
            left = " ".join(w["text"] for w in more if float(w["x"]) < column).strip()
            if left:
                address.append(left)
        return Party(name=name, gstin=found.group(0), address=_drop_state(address, found.group(0)))
    return None


def kfin(grid: list[list[str]]) -> Party | None:
    """The fund house on a KFintech invoice, from the invoice's own spreadsheet (`sheet.read`'s cells)."""
    rows = [[str(c or "").replace("\xa0", " ").strip() for c in r] for r in grid]
    firsts = [next((c for c in r if c), "") for r in rows]
    try:
        at = firsts.index("Details of Recipient (Billed to)")
    except ValueError:
        return None
    name, address, gstin = "", [], ""
    for text in firsts[at + 1:]:
        if not text:
            continue
        if not name:
            name = text
        elif text.startswith(("State:", "State Code", "GSTIN", "PAN", "Place of supply")):
            if text.startswith("GSTIN"):
                found = GSTIN.search(text)
                gstin = found.group(0) if found else ""
                break
        else:
            address.append(text)
    if not name or not gstin:
        return None
    return Party(name=name, gstin=gstin, address=_drop_state(address, gstin))
