"""The door: sign this invoice, the person's way.

A run and setup speak only to this: is a way set up (`info`), get it ready (`unlock`), sign this PDF where its own
words say the signature goes (`sign_file`), or sign the invoice being drawn (`ops_pdf.render_to`, through `draws` and
`finish`). Which way is the person's choice, kept beside their signature on this PC, and each way is a module behind
the door:

    image   the cleaned photo of the handwritten signature, stamped         `sign_image`
    dsc     a USB token's certificate: a real PDF signature, with a mark    `sign_dsc`

A token is reached through Windows' certificate store, where its own software asks for the PIN in its own box and our
code never sees it (`certstore`). Only for a token that cannot be reached that way is the PIN typed in our window
(`tokenpin`): it goes straight to the token, lives in the token's open session for that run, and is never stored or
sent up.

What is kept for a token is which certificate was picked (its name, issuer and expiry, for the window) and the route
that reached it. Never a key, never a PIN.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Awaitable, Callable
from datetime import date
from pathlib import Path

from client import errors
from client.hands import certstore, sign_dsc, sign_image
from client.hands.certstore import StoreError

log = logging.getLogger(__name__)

IMAGE, DSC = "image", "dsc"
WINDOWS, PIN = "windows", "pin"          # the two routes to a token


def ways() -> list[str]:
    """The ways this PC has. A token needs Windows' certificate store."""
    return [IMAGE, DSC] if certstore.available() else [IMAGE]


class Door:
    def __init__(self, signature: Callable[[], Path], hwnd: Callable[[], int] = lambda: 0,
                 ask_pin: Callable[[str], Awaitable[str | None]] | None = None):
        self.signature = signature               # where this ARN's signature is kept; its .json says which way
        self.hwnd = hwnd                         # our window, so a token's PIN box opens over it
        self.ask_pin = ask_pin                   # the window's PIN question, for the second route
        self._open: tuple[str, object] | None = None      # (thumbprint, the open key), for the run that unlocked it

    # --- which way --------------------------------------------------------------------------------------------

    def setup(self) -> dict:
        return sign_image.meta_of(self.signature())

    def way(self) -> str:
        return DSC if self.setup().get("way") == DSC else IMAGE

    def info(self) -> dict:
        """Is a way set up, which, and the shape the signature is placed by."""
        if self.way() == DSC:
            return {**sign_dsc.info(self.setup().get("cert")), "way": DSC}
        return {**sign_image.info(self.signature()), "way": IMAGE}

    # --- getting ready ----------------------------------------------------------------------------------------

    async def unlock(self) -> dict:
        """`sig.unlock`: the person's way, ready to sign for this run. The image is always ready. A token is found and
        made to sign once, so its PIN is asked for now - by its own software, or in our window on the second route -
        and not in the middle of the month's invoices."""
        if self.way() == IMAGE:
            sign_image.image(self.signature())                  # no signature set up: says so
            return {"ready": True, "way": IMAGE}
        s = self.setup()
        cert = s.get("cert") or {}
        if not cert.get("thumbprint"):
            raise errors.Failure(errors.NO_SIGNATURE.code, "No signing certificate has been picked on this PC yet.")
        if cert.get("expires") and cert["expires"] < date.today().isoformat():
            raise errors.Failure(errors.SIGNING_REFUSED.code,
                                 f"Your signing certificate expired on {_day(cert['expires'])}. Pick the new one in "
                                 "Settings › Signature.")
        if self._open and self._open[0] == cert["thumbprint"]:
            return {"ready": True, "way": DSC}
        self.release()
        try:
            key = await open_token(s.get("route") or WINDOWS, s.get("driver") or "", cert["thumbprint"], self.hwnd(),
                                   self.ask_pin)
        except StoreError as e:
            raise failure(e) from e
        self._open = (cert["thumbprint"], key)
        return {"ready": True, "way": DSC}

    def here(self) -> bool:
        """Is the person's way there to sign with right now? The image always is. A token: only a plain no is no
        (`certstore.here`)."""
        s = self.setup()
        thumbprint = (s.get("cert") or {}).get("thumbprint") or ""
        if self.way() == IMAGE or not thumbprint:
            return True
        if s.get("route") == PIN:
            from client.hands import tokenpin
            return tokenpin.here(s.get("driver") or "", thumbprint)
        return certstore.here(thumbprint)

    def release(self) -> None:
        """The run is over, or the signature changed: let the token go."""
        if self._open:
            try:
                self._open[1].close()
            except Exception:
                log.info("letting the token go", exc_info=True)
        self._open = None

    # --- signing ----------------------------------------------------------------------------------------------

    def sign_file(self, src: Path, out: Path, places: list[dict]) -> str:
        """Sign this PDF where `places` say, into `out`. Returns the way it was signed."""
        out.parent.mkdir(parents=True, exist_ok=True)
        return self._sign(src, out, places)

    def _sign(self, src: Path, out: Path, places: list[dict]) -> str:
        if self.way() == IMAGE:
            sign_image.stamp(self.signature(), src, out, places)
            return IMAGE
        try:
            sign_dsc.sign(src, out, places, self._token(), (self.setup().get("cert") or {}).get("name") or "")
        except StoreError as e:
            raise failure(e) from e
        return DSC

    def _token(self) -> sign_dsc.Token:
        """The open token, as the PDF signer wants it. Through Windows it can be opened here if `unlock` was not
        called (its software asks for the PIN itself); the second route needs the PIN that `unlock` asked for."""
        s = self.setup()
        thumbprint = (s.get("cert") or {}).get("thumbprint") or ""
        if not self._open or self._open[0] != thumbprint:
            if s.get("route") == PIN or not thumbprint:
                raise errors.Failure(errors.SIGNING_REFUSED.code, "The token was not unlocked for this run.")
            self.release()
            self._open = (thumbprint, certstore.Key(thumbprint, self.hwnd()))
        key = self._open[1]
        return sign_dsc.Token(key.cert, certstore.chain(key.cert), key.sign)

    # --- the person's own invoice, being drawn (`ops_pdf.render`) ----------------------------------------------

    def draws(self, c, op: dict) -> dict | None:
        """The signature's place in a draw-list. The image is drawn now; a token signs the finished file, so its box
        is handed back for `finish`."""
        if self.way() == IMAGE:
            sign_image.draw(c, self.signature(), op)
            return None
        return {"page": int(op["page"]), "x": op["x"], "y": op["y"], "w": op.get("w") or 0, "h": op.get("h") or 0}

    def finish(self, out: Path, boxes: list[dict]) -> str:
        """The drawn invoice is on disk: a token signs it now, in place. Returns the way it was signed."""
        if not boxes:
            return IMAGE
        return self._sign(out, out, boxes)


class MarkDoor(Door):
    """A preview's door for a token: the mark where a run stamps it, and nothing signed. It has no token, no route and
    no PIN to reach: `unlock`, `sign_file` and every signing path are shut."""

    def __init__(self, name: str):
        super().__init__(lambda: Path())
        self.name = name

    def way(self) -> str:
        return DSC

    def info(self) -> dict:
        return {**sign_dsc.info({"thumbprint": "preview", "name": self.name}), "way": DSC}

    async def unlock(self) -> dict:
        raise errors.Failure(errors.INTERNAL.code, "a preview never reaches the token")

    def _sign(self, src: Path, out: Path, places: list[dict]) -> str:
        sign_dsc.mark_only(src, out, places, self.name)
        return DSC


async def open_token(route: str, driver: str, thumbprint: str, hwnd: int = 0, ask_pin=None):
    """Open the token that holds this certificate and make it sign once, so that it is known to work and its PIN has
    been asked for. Through Windows the token's own software asks, in its own box; on the second route `ask_pin` is
    the window's question, asked again for as long as the token says the PIN is wrong and the person keeps answering.
    Returns the open key (`certstore.Key` or `tokenpin.Session`); raises `StoreError`."""
    if route == PIN:
        from client.hands import tokenpin
        if not await asyncio.to_thread(tokenpin.here, driver, thumbprint):
            raise StoreError("no_token")
        said = ""
        while True:
            pin = await ask_pin(said) if ask_pin else None
            if not pin:
                raise StoreError("cancelled")
            try:
                key = await asyncio.to_thread(tokenpin.Session, driver, thumbprint, pin)
                break
            except StoreError as e:
                if e.why != "wrong_pin":
                    raise
                said = e.said                  # the token's own answer; the person decides whether to try again
            finally:
                del pin
    else:
        key = await asyncio.to_thread(certstore.Key, thumbprint, hwnd)
    try:                                       # through Windows, the token's PIN box opens here
        await asyncio.to_thread(key.sign, hashlib.sha256(b"ready").digest())
    except StoreError:
        key.close()
        raise
    return key


def _day(iso: str) -> str:
    try:
        return date.fromisoformat(iso).strftime("%d %b %Y").lstrip("0")
    except ValueError:
        return iso


def failure(e: StoreError) -> errors.Failure:
    """What the token, or Windows, said, as the stop the person sees. Its own words where it gave any."""
    if e.why == "no_token":
        return errors.Failure(errors.TOKEN_NOT_FOUND.code,
                              "Your signing token isn't plugged in. Plug it in and try again.")
    said = {"cancelled": "The PIN box was closed, so nothing was signed.",
            "wrong_pin": "The token says that PIN is wrong, so nothing was signed.",
            "locked": "The token says its PIN is locked, so nothing was signed."}.get(e.why)
    if said is None:
        said = "Your token did not sign" + (f'. It says: "{e.said}"' if e.said else ".")
    return errors.Failure(errors.SIGNING_REFUSED.code, said)
