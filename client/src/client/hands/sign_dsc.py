"""Signing with a USB DSC: a real PDF digital signature (PAdES), with a visible mark where the stamped image would
sit. One of the two ways behind the door (`ops_sign`).

The signature is made by the token. This module builds the PDF around it (pyHanko): it adds a signature field at the
box the steps worked out, draws the mark in it ("Digitally signed by <name>", the date), has the token sign the
document's digest through whichever route reached it (`certstore.Key`, or `tokenpin.Session`), and writes the result
as an update to the registrar's own PDF, whose bytes are kept as they were.

The signing time is this PC's clock. No time-stamping service and no revocation lookup is called: the app talks to
nothing but our own service and the portals.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

from asn1crypto import algos, x509
from pyhanko.pdf_utils import layout, text
from pyhanko.pdf_utils.font.basic import SimpleFontEngineFactory
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import fields, signers
from pyhanko.stamp import TextStamp, TextStampStyle
from pyhanko_certvalidator.registry import SimpleCertificateStore

FIELD = "Signature1"
# The mark: three lines of 9 pt Helvetica at the top-left of its box, shrunk to fit a smaller one.
LINES = ("Digitally signed by", "%(name)s", "Date: %(ts)s")
WHEN = "%d %b %Y, %H:%M:%S %z"                 # 03 Oct 2026, 13:42:30 +0530
SIZE, LEADING, AVERAGE = 9, 11, 0.5            # AVERAGE: a letter's width over the font size, as pyHanko measures
MARK = TextStampStyle(
    stamp_text="\n".join(LINES),
    timestamp_format=WHEN,
    border_width=0,
    text_box_style=text.TextBoxStyle(font=SimpleFontEngineFactory("Helvetica", AVERAGE), font_size=SIZE,
                                     leading=LEADING),
    inner_content_layout=layout.SimpleBoxLayoutRule(x_align=layout.AxisAlignment.ALIGN_MIN,
                                                    y_align=layout.AxisAlignment.ALIGN_MAX),
)


def aspect(name: str) -> float:
    """The mark's shape, width over height, for this name: placed as the image's is. The same
    arithmetic pyHanko lays the text out with, so a box of this shape is filled exactly."""
    longest = max(len("Digitally signed by"), len(name), len("Date: 03 Oct 2026, 13:42:30 +0530"))
    return round(min(max(longest * AVERAGE * SIZE / (len(LINES) * LEADING), 3.0), 6.6), 4)


def info(cert: dict | None) -> dict:
    """What placing the mark needs: that a certificate is picked, and the mark's shape. Never whose it is."""
    return {"present": bool(cert and cert.get("thumbprint")), "aspect": aspect((cert or {}).get("name") or ""),
            "ink_cx": 0.5, "ink_cy": 0.5, "scale": 1.0}


class Token(signers.Signer):
    """The token, as pyHanko signs with it. `sign(digest, algorithm)` is the route that reached the token."""

    def __init__(self, cert: bytes, issuers: list[bytes], sign):
        registry = SimpleCertificateStore()
        registry.register_multiple(x509.Certificate.load(c) for c in issuers)
        super().__init__(signing_cert=x509.Certificate.load(cert), cert_registry=registry, embed_roots=False)
        self._sign = sign

    async def async_sign_raw(self, data: bytes, digest_algorithm: str, dry_run=False) -> bytes:
        key = self.signing_cert.public_key
        rsa = key.algorithm == "rsa"
        if dry_run:                                      # pyHanko asks how much room to leave; the token is not asked
            return bytes(key.byte_size if rsa else 2 * key.byte_size + 16)
        raw = self._sign(hashlib.new(digest_algorithm, data).digest(), digest_algorithm)
        return raw if rsa else algos.DSASignature.from_p1363(raw).dump()


def box_of(place: dict) -> tuple[float, float, float, float]:
    """The mark's box on its page (left, bottom, right, top), from the place the steps worked out."""
    x, y = float(place["x"]), float(place["y"])
    return (round(x, 2), round(y, 2), round(x + float(place["w"]), 2), round(y + float(place["h"]), 2))


def mark_only(src: Path, out: Path, places: list[dict], name: str) -> None:
    """A preview of `sign`: the same mark, in the same box, drawn with the same style and lines - and no signature.
    It never reaches the token and never asks for a PIN."""
    p = places[0]
    x0, y0, x1, y1 = box_of(p)
    writer = IncrementalPdfFileWriter(io.BytesIO(src.read_bytes()), strict=False)
    stamp = TextStamp(writer, MARK, text_params={"name": name},
                      box=layout.BoxConstraints(width=x1 - x0, height=y1 - y0))
    stamp.apply(int(p["page"]) - 1, x0, y0)
    buf = io.BytesIO()
    writer.write(buf)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(buf.getvalue())


def sign(src: Path, out: Path, places: list[dict], token: Token, name: str) -> None:
    """Sign one PDF: a real signature over the whole document, its mark in the first box. A document signature has
    one mark, so one box is used."""
    p = places[0]
    box = box_of(p)
    writer = IncrementalPdfFileWriter(io.BytesIO(src.read_bytes()), strict=False)
    meta = signers.PdfSignatureMetadata(field_name=FIELD, md_algorithm="sha256", name=name,
                                        subfilter=fields.SigSeedSubFilter.PADES)
    signer = signers.PdfSigner(meta, token, stamp_style=MARK,
                               new_field_spec=fields.SigFieldSpec(FIELD, on_page=int(p["page"]) - 1, box=box))
    buf = io.BytesIO()
    signer.sign_pdf(writer, output=buf, appearance_text_params={"name": name})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(buf.getvalue())
