"""The person's own invoice number series.

- A number is text with one part that goes up by 1, exactly as the person prints it ("73/26-27"). Zero padding is
  kept (073 -> 074).
- With books connected (Tally or Zoho Books) the books give the numbers: `books.py` reads the highest of the person's
  own shape and writes each invoice in. Here `shape`, `highest` and `next_year` work out the series from the numbers
  they hold.
- Without books a run starts from the last number the person confirmed. The software keeps the highest it has used
  this financial year (`Issued.top`); the guard against going below it lives in the software (the window's
  `local.below`), not here.
- Only the invoices ticked at Your check get numbers, in order, CAMS's first, with no gap. One left out has none.
- Without books a number is given to its invoice for good when Submit is pressed (`Issued.lock`); with books, when it
  is in the books. The same invoice always carries the same number afterwards, sent again or not, and that number is
  never given to another.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path


class NumberError(ValueError):
    """The number has no part that can go up by 1 there."""


RULE_46 = "GST allows up to 16 characters: letters, digits, - and / only."


def rule_46(text: str) -> str:
    """"" when the invoice number may be used (GST Rule 46: at most 16 characters, only letters, digits, - and /; empty
    is not set yet), else the words to refuse it with. The window checks the same at its box (logic/numbering.ts)."""
    return "" if re.fullmatch(r"[A-Za-z0-9/-]{0,16}", (text or "").strip()) else RULE_46


def counter_at(text: str, at: int) -> tuple[int, int]:
    """The run of digits that starts at `at`: (start, end). Raises if there is none."""
    if not 0 <= at < len(text) or not text[at].isdigit() or (at > 0 and text[at - 1].isdigit()):
        raise NumberError(f"no number starts at position {at} of {text!r}")
    end = at
    while end < len(text) and text[end].isdigit():
        end += 1
    return at, end


def count(text: str, at: int) -> int:
    start, end = counter_at(text, at)
    return int(text[start:end])


def bump(text: str, at: int, by: int = 1) -> str:
    """The number `by` after this one, keeping the counting part's zero padding: 'RKM/26-27/073' -> '.../074'."""
    start, end = counter_at(text, at)
    digits = text[start:end]
    return text[:start] + str(int(digits) + by).zfill(len(digits)) + text[end:]


def default_counter(text: str) -> int:
    """Which part goes up, when the person has not tapped one: the last run of digits that is not part of a year pair
    like 26-27 or 2026-27. -1 when there is none."""
    runs = [(m.start(), m.end()) for m in re.finditer(r"\d+", text)]

    def in_year_pair(i: int) -> bool:
        s, e = runs[i]
        after = i + 1 < len(runs) and text[e:runs[i + 1][0]] == "-"
        before = i > 0 and text[runs[i - 1][1]:s] == "-"
        return after or before

    for i in range(len(runs) - 1, -1, -1):
        if not in_year_pair(i):
            return runs[i][0]
    return runs[-1][0] if runs else -1


def used_line(numbers: list[str], at: int, verb: str = "Used") -> str:
    """"Used 74/26-27 to 78/26-27": the first and the last when they run on, else each one."""
    if not numbers:
        return ""
    if len(numbers) == 1:
        return f"{verb} {numbers[0]}"
    try:
        ints = [count(n, at) for n in numbers]
    except NumberError:
        ints = []
    if ints and ints == list(range(ints[0], ints[0] + len(ints))):
        return f"{verb} {numbers[0]} to {numbers[-1]}"
    return f"{verb} " + ", ".join(numbers)


def fy_of(day: str | date) -> str:
    """The financial year a date falls in: '2026-04-01' -> '2026-27'."""
    d = day if isinstance(day, date) else date.fromisoformat(str(day)[:10])
    y = d.year if d.month >= 4 else d.year - 1
    return f"{y}-{(y + 1) % 100:02d}"


def shape(text: str, at: int) -> tuple[str, str]:
    """What stays the same along a series: the text before and after the counting digits."""
    start, end = counter_at(text, at)
    return text[:start], text[end:]


def highest(numbers: list[str], sample: str, at: int) -> str:
    """The highest of these numbers that is in the same series as `sample` (the same text round the counting
    digits), or '' when none is."""
    try:
        want = shape(sample, at)
    except NumberError:
        return ""
    best, top = "", -1
    for n in numbers:
        try:
            if shape(n, at) == want and count(n, at) > top:
                best, top = n, count(n, at)
        except NumberError:
            continue
    return best


def next_year(text: str, at: int) -> str:
    """The first number of the next financial year in the style of `text`: the year pair moved on ('73/26-27' ->
    '1/27-28') and the counting part back to 1, with its zero padding kept. '' when `text` has no year pair."""
    found = None
    for m in re.finditer(r"(?<!\d)(\d{2}|\d{4})-(\d{2})(?!\d)", text):
        if (int(m.group(1)[-2:]) + 1) % 100 == int(m.group(2)):
            found = m
    if not found:
        return ""
    a, b = found.group(1), found.group(2)
    moved = str(int(a) + 1).zfill(len(a)) + "-" + str((int(b) + 1) % 100).zfill(2)
    out = text[:found.start()] + moved + text[found.end():]
    try:
        start, end = counter_at(out, at)
    except NumberError:
        return ""
    padded = out[start] == "0"                               # '073' is padded; '73' is not
    return out[:start] + ("1".zfill(end - start) if padded else "1") + out[end:]


class Issued:
    """One ARN's numbers given to invoices for good (`locked`), the highest used in each financial year (`top`), and
    the last number the person confirmed. Kept in `books.json` in the ARN's folder. With books connected it is only
    a cache of what the books hold; without them it is the record."""

    def __init__(self, path: Path, last: str, at: int):
        self.path = path
        self.last = (last or "").strip()
        self.at = at if self.last and _counts(self.last, at) else default_counter(self.last)
        try:
            got = json.loads(path.read_text(encoding="utf-8"))
            self.locked: dict[str, str] = dict(got.get("locked") or {})
            self.top: dict[str, str] = dict(got.get("top") or {})
        except (OSError, ValueError, AttributeError):
            self.locked, self.top = {}, {}

    @property
    def ready(self) -> bool:
        return bool(self.last) and self.at >= 0

    def number_of(self, key: str) -> str:
        return self.locked.get(key, "")

    def hand_out(self, keys: list[str]) -> dict[str, str]:
        """The numbers these invoices get, in the order given. Nothing is written. An invoice that holds a number
        keeps it; the rest take the numbers after the last one, skipping any already given."""
        if not self.ready:
            raise NumberError("the last invoice number in your books is not set")
        out: dict[str, str] = {}
        taken = set(self.locked.values())
        text = bump(self.last, self.at)
        for key in keys:
            have = self.number_of(key)
            if have:
                out[key] = have
                continue
            while text in taken:
                text = bump(text, self.at)
            out[key] = text
            taken.add(text)
        return out

    def lock(self, numbers: dict[str, str], fy: str = "") -> str:
        """These invoices are leaving this software with these numbers: theirs for good. Returns the last number in
        the books now (the highest given), so the series goes on from it. `fy`: the financial year they are in."""
        self.locked.update(numbers)
        top = self.last
        for n in numbers.values():
            if _counts(n, self.at) and (not _counts(top, self.at) or count(n, self.at) > count(top, self.at)):
                top = n
        if fy:
            self.top[fy] = highest([*numbers.values(), self.top.get(fy, "")], top, self.at) or top
        self.save()
        self.last = top
        return top

    def keep(self, numbers: dict[str, str]) -> None:
        """A cache of what the books gave: these invoices have these numbers there."""
        self.locked.update(numbers)
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"locked": self.locked, "top": self.top}, indent=1), encoding="utf-8")
        tmp.replace(self.path)


def _counts(text: str, at: int) -> bool:
    try:
        counter_at(text, at)
        return True
    except NumberError:
        return False
