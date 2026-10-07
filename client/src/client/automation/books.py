"""The person's books, as a run sees them. Tally today; Zoho Books later through the same few calls.

With own invoices and books connected, the run goes into the books first: each ticked invoice is written in, one at a
time in date order, and the invoice number the books hold is the one drawn on the PDF, sent to the registrar, and
kept. What a books class must do:

    glance(keys)        read only. {state: ready | off | closed | pick, company, rows (action, note, block, why),
                        asks, first, after, peek, renumbers}. Anything but ready means the books are not answering.
    place(key, first)   write one invoice and read its number back: {number, mid, date, fresh, adopted}. An invoice
                        already there under our id is found, not written again. Raises `Refused` (the books' own
                        words) for that one invoice, and `Off` when the books stop answering.
    answer(answers)     the person's answers to the books' questions, remembered at once.

Nothing here ever changes, cancels or deletes what the person has in their books beyond the invoices it writes
itself, and a hand-typed invoice it adopts. `tally.py` has the Tally half.
"""

from __future__ import annotations

from pathlib import Path

from client.automation import tally
from client.automation.tally import Off, Refused  # noqa: F401 - what a caller catches

KIND = "tally"


def connected(base: Path) -> str:
    """Which books this ARN has connected ('tally', later 'zoho'), or ''."""
    return KIND if tally.remembered(base)["company"] else ""


def company(base: Path) -> str:
    return tally.remembered(base)["company"]


class Tally:
    """One run's use of the person's TallyPrime."""

    def __init__(self, base: Path, period: str, profile: dict):
        self.base, self.period, self.profile = base, period, profile
        self.answers: dict[str, str] = {}
        self.session: tally.Session | None = None

    def _new(self) -> tally.Session:
        self.session = tally.Session(self.base, self.period, self.profile, answers=self.answers)
        return self.session

    def glance(self, keys: list[str]) -> dict:
        return self._new().glance(keys)

    def place(self, key: str, first: str = "") -> dict:
        if self.session is None:
            raise Refused("Tally wasn't looked at first.")
        return self.session.place(key, first)

    def answer(self, answers: dict[str, str]) -> None:
        self.answers.update(answers)
        tally.keep_answers(self.base, answers, (self.session.books.get("gstin", "") if self.session else ""))
