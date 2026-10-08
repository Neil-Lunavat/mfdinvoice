"""The person's books, as a run and the Books tab see them: Tally or Zoho Books, one per ARN, through the same few calls.

With own invoices and books connected, the run goes into the books first: each ticked invoice is written in, one at a
time in date order, and the invoice number the books hold is the one drawn on the PDF, sent to the registrar, and
kept. What a books class must do:

    glance(keys)        read only. {state: ready | off | closed | pick, company, rows (action, note, block, why),
                        asks, first, after, peek, renumbers}. Anything but ready means the books are not answering.
    predict(keys, first)    read only. {numbers, where}: the numbers the invoices about to be written will carry.
    place(key, first)   write one invoice and read its number back: {number, mid, date, fresh, adopted}. An invoice
                        already there under our id is found, not written again. Raises `Refused` (the books' own
                        words) for that one invoice, and `Off` (with `.said`) when the books stop answering.
    answer(answers)     the person's answers to the books' questions, remembered at once.
    after_sign(key, pdf)    the signed PDF has been drawn: put it with the invoice in the books. Tally: nothing.
    after_submit(key)       the registrar has taken the invoice: the books may call it sent. Tally: nothing.
    look() / bring_in(adopt)    the Books tab: the month's registrar invoices into the books.

Nothing here ever changes, cancels or deletes what the person has in their books beyond the invoices it writes
itself, and a hand-typed invoice it adopts. `tally.py` and `zoho.py` have the two halves.
"""

from __future__ import annotations

from pathlib import Path

from client.automation import tally, zoho
from client.automation.tally import Off, Refused  # noqa: F401 - what a caller catches

NAMES = {"tally": "Tally", "zoho": "Zoho Books"}


def connected(base: Path) -> str:
    """Which books this ARN has connected ('tally' or 'zoho'), or ''."""
    return "tally" if tally.remembered(base)["company"] else "zoho" if zoho.remembered(base)["company"] else ""


def kept(base: Path) -> dict:
    """What the Books tab and Settings show: {kind, company, gstin, ledgers (fund houses matched)}."""
    kind = connected(base)
    return {"kind": kind, **(tally.remembered(base) if kind == "tally" else zoho.remembered(base) if kind else
                             {"company": "", "gstin": "", "ledgers": 0})}


def company(base: Path) -> str:
    return kept(base)["company"]


def name(kind: str) -> str:
    return NAMES.get(kind, "your books")


class Tally:
    """One run's (or one tab's) use of the person's TallyPrime."""

    kind = "tally"
    name = "Tally"

    def __init__(self, base: Path, period: str, profile: dict, token=None, *, company: str = "",
                 org_id: str = "", which: str = "submitted", last: str = "", answers: dict | None = None):
        self.base, self.period, self.profile = base, period, profile
        self.company, self.which, self.last = company, which, last
        self.answers: dict[str, str] = dict(answers or {})
        self.session: tally.Session | None = None

    def _new(self) -> tally.Session:
        self.session = tally.Session(self.base, self.period, self.profile, company=self.company, which=self.which,
                                     last=self.last, answers=self.answers)
        return self.session

    def glance(self, keys: list[str]) -> dict:
        return self._new().glance(keys)

    def place(self, key: str, first: str = "") -> dict:
        if self.session is None:
            raise Refused("Tally wasn't looked at first.")
        return self.session.place(key, first)

    def predict(self, keys: list[str], first: str = "") -> dict:
        return self.session.predict(keys, first) if self.session else {"numbers": [], "where": ""}

    def answer(self, answers: dict[str, str]) -> None:
        self.answers.update(answers)
        tally.keep_answers(self.base, answers, (self.session.books.get("gstin", "") if self.session else ""))

    def after_sign(self, key: str, pdf: Path) -> dict:
        return {}

    def after_submit(self, key: str) -> dict:
        return {}

    def look(self) -> dict:
        return self._new().look()

    def bring_in(self, adopt: list[str] | None = None) -> dict:
        return self._new().bring_in(adopt or [])


class Zoho:
    """One run's (or one tab's) use of the person's Zoho Books. `token(fresh=False)` is the software's: it holds the
    grant and hands an hour's access token, or says it is gone."""

    kind = "zoho"
    name = "Zoho Books"

    def __init__(self, base: Path, period: str, profile: dict, token, *, company: str = "", org_id: str = "",
                 which: str = "submitted", last: str = "", answers: dict | None = None):
        self.base, self.period, self.profile, self.token = base, period, profile, token
        self.company, self.org_id, self.which = company, org_id, which
        self.answers: dict[str, str] = dict(answers or {})
        self.session: zoho.Session | None = None

    def _new(self) -> zoho.Session:
        self.session = zoho.Session(self.base, self.period, self.profile, self.token, company=self.company,
                                    org_id=self.org_id, which=self.which, answers=self.answers)
        return self.session

    def glance(self, keys: list[str]) -> dict:
        return self._new().glance(keys)

    def place(self, key: str, first: str = "") -> dict:
        if self.session is None:
            raise Refused("Zoho Books wasn't looked at first.")
        return self.session.place(key, first)

    def predict(self, keys: list[str], first: str = "") -> dict:
        return self.session.predict(keys, first) if self.session else {"numbers": [], "where": ""}

    def answer(self, answers: dict[str, str]) -> None:
        self.answers.update(answers)
        zoho.keep_answers(self.base, answers, (self.session.books_gstin if self.session else ""))

    def after_sign(self, key: str, pdf: Path) -> dict:
        if self.session is None:
            raise Refused("Zoho Books wasn't looked at first.")
        return self.session.after_sign(key, pdf)

    def after_submit(self, key: str) -> dict:
        if self.session is None:
            raise Refused("Zoho Books wasn't looked at first.")
        return self.session.after_submit(key)

    def look(self) -> dict:
        return self._new().look()

    def bring_in(self, adopt: list[str] | None = None) -> dict:
        return self._new().bring_in(adopt or [])


def open(kind: str, base: Path, period: str, profile: dict, token=None, **more) -> Tally | Zoho:  # noqa: A001
    return (Zoho if kind == "zoho" else Tally)(base, period, profile, token, **more)


def setup_look(kind: str, token, gstin: str) -> dict:
    """Setup's Books step: is it answering, and the companies (Tally) or organisations (Zoho Books) with their GSTINs.
    Tally: {state, companies: [{name, guid, gstin, same}]}. Zoho Books: {state, said, orgs: [{id, name, gstin, same}]}."""
    return zoho.setup_look(token, gstin) if kind == "zoho" else tally.setup_look(gstin)


def books_next(kind: str, token, base: Path, company: str = "", org_id: str = "") -> dict:
    return zoho.books_next(token, base, org_id) if kind == "zoho" else tally.books_next(base, company)


def keep(kind: str, base: Path, pick: dict) -> None:
    """The books chosen at setup: the first look goes straight to it. Only one kind is kept for an ARN.
    Tally: {company, guid, gstin, sure}. Zoho Books: {orgId, org, gstin, sure}."""
    forget(base)
    if kind == "zoho":
        zoho.keep_org(base, str(pick["orgId"]), str(pick.get("org") or ""), str(pick.get("gstin") or ""),
                      bool(pick.get("sure")))
    else:
        tally.keep_company(base, pick["company"], pick["guid"], str(pick.get("gstin") or ""), bool(pick.get("sure")))


def forget(base: Path) -> None:
    """Forget what was remembered of both: the next connect asks again."""
    tally.forget(base)
    zoho.forget(base)
