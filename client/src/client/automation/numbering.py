"""The person's own invoice number series.

- A number is text with one part that goes up by 1, exactly as the person prints it ("73/26-27"). Zero padding is
  kept (073 -> 074).
- A run starts from the last number in the person's books, which they confirm before it starts.
- Only the invoices ticked at Your check get numbers, in order, CAMS's first, with no gap. One left out has none.
- A number is given to its invoice for good the moment the invoice leaves this software: when Submit is pressed, or
  when the month is imported into Tally (`Books.lock`). The same invoice always carries the same number afterwards,
  sent again or not, and that number is never given to another.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


class NumberError(ValueError):
    """The number has no part that can go up by 1 there."""


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


def used_line(numbers: list[str], at: int) -> str:
    """"Used 74/26-27 to 78/26-27": the first and the last when they run on, else each one."""
    if not numbers:
        return ""
    if len(numbers) == 1:
        return f"Used {numbers[0]}"
    try:
        ints = [count(n, at) for n in numbers]
    except NumberError:
        ints = []
    if ints and ints == list(range(ints[0], ints[0] + len(ints))):
        return f"Used {numbers[0]} to {numbers[-1]}"
    return "Used " + ", ".join(numbers)


class Books:
    """One ARN's series: the last number in the person's books, and every number already given to an invoice for
    good. Kept in `books.json` in the ARN's folder."""

    def __init__(self, path: Path, last: str, at: int):
        self.path = path
        self.last = (last or "").strip()
        self.at = at if self.last and _counts(self.last, at) else default_counter(self.last)
        try:
            self.locked: dict[str, str] = dict(json.loads(path.read_text(encoding="utf-8")).get("locked") or {})
        except (OSError, ValueError):
            self.locked = {}

    @property
    def ready(self) -> bool:
        return bool(self.last) and self.at >= 0

    def number_of(self, key: str) -> str:
        return self.locked.get(key, "")

    def hand_out(self, keys: list[str]) -> dict[str, str]:
        """The numbers these invoices get, in the order given. Nothing is written. An invoice that holds a number
        keeps it; the rest take the numbers after the last one in the books, skipping any already given."""
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

    def lock(self, numbers: dict[str, str]) -> str:
        """These invoices are leaving this software with these numbers: theirs for good. Returns the last number in
        the books now (the highest given), so the series goes on from it."""
        self.locked.update(numbers)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"locked": self.locked}, indent=1), encoding="utf-8")
        tmp.replace(self.path)
        top = self.last
        for n in numbers.values():
            if _counts(n, self.at) and count(n, self.at) > count(top, self.at):
                top = n
        self.last = top
        return top


def _counts(text: str, at: int) -> bool:
    try:
        counter_at(text, at)
        return True
    except NumberError:
        return False
