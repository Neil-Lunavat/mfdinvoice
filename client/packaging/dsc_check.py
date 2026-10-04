"""Sign with your USB token, the way a run does, on two of this PC's real invoices. Nothing in the app changes.

    uv run python packaging/dsc_check.py

1. finds the signing certificates on the tokens plugged in (Windows' store first, then the token's own driver)
2. opens the token: its own software asks for the PIN, in its own box. If it can only be reached through its driver,
   this asks for the PIN here instead
3. signs one CAMS invoice and one KFintech invoice from the newest month on this PC that has both, with the
   signature where a run puts it, into Desktop\\dsc-check\\ (the month's own files are only read)
4. checks each signed file: the signature covers the whole file, is made by that certificate, and the file is
   unchanged since. Open them in Adobe Reader to see the mark and the signature panel

Not checked here: whether Adobe trusts the certifying authority (that is Adobe's list, not ours).
"""

from __future__ import annotations

import asyncio
import getpass
import sys
from pathlib import Path

from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature

from client.automation import cams, kfin, signature
from client.brand import DATA
from client.hands import certstore, ops_sign, sign_dsc, tokenpin

OUT = Path.home() / "Desktop" / "dsc-check"


def pick_month() -> tuple[Path, Path | None, dict | None]:
    """The newest month with both registrars' PDFs (else the newest with either): one CAMS invoice and one KFintech
    one (its row, so the PDF is checked to be that row's)."""
    found = []
    for arn in sorted((DATA / "workspace" / "arns").iterdir()):
        for month in sorted((p for p in arn.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True):
            cams_pdf = next(iter(sorted((month / "cams" / "invoices").glob("*.pdf"))), None)
            k_zip = next(iter(sorted((month / "kfintech" / "fetched").glob("*.zip"))), None)
            if cams_pdf or k_zip:
                found.append((month, cams_pdf, k_zip))
    if not found:
        sys.exit("No month on this PC has invoices yet: Download invoices for one first.")
    month, cams_pdf, k_zip = next((f for f in found if f[1] and f[2]), found[0])
    ones = kfin.read_zip(k_zip, OUT / "_kfintech") if k_zip else []
    return month, cams_pdf, ones[0] if ones else None


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    certs, route = certstore.certificates(), ops_sign.WINDOWS
    if not certs:
        certs, route = tokenpin.certificates(), ops_sign.PIN
    if not certs:
        sys.exit("No signing certificate was found. Is the token plugged in, and its own software installed?")
    print("Certificates found:")
    for i, c in enumerate(certs):
        print(f"  {i + 1}. {c.name} · {c.issuer} · valid till {c.expires} · through {route}")
    c = certs[0]
    if len(certs) > 1:
        c = certs[int(input(f"Which one (1-{len(certs)})? ") or 1) - 1]

    async def ask_pin(said: str) -> str | None:
        return getpass.getpass(f"{said + ' ' if said else ''}Your token's PIN (not shown): ") or None

    print(f"\nOpening the token for {c.name}. Its PIN box opens now.")
    try:
        key = await ops_sign.open_token(route, c.provider if route == ops_sign.PIN else "", c.thumbprint, 0, ask_pin)
    except certstore.StoreError as e:
        sys.exit(f"The token didn't sign: {ops_sign.failure(e).message}")
    token = sign_dsc.Token(key.cert, certstore.chain(key.cert) if route == ops_sign.WINDOWS else [], key.sign)
    sig = sign_dsc.info(c.view())

    month, cams_pdf, one = pick_month()
    print(f"Signing from {month.parent.name} {month.name}\n")
    jobs = []
    if cams_pdf:
        info = cams.read_pdf(cams_pdf)
        jobs.append(("CAMS", cams_pdf, info))
    if one:
        jobs.append(("KFintech", one["pdf"], kfin.read_pdf(one)))
    try:
        for who, src, info in jobs:
            out = OUT / f"{who} - {src.name}"
            place = signature.place(info["gap"], sig, info["page_h"])
            sign_dsc.sign(src, out, [place], token, c.name)
            with out.open("rb") as f:
                s = PdfFileReader(f).embedded_signatures[0]
                v = validate_pdf_signature(s)
            whole = s.coverage.name
            print(f"{who}: {out}\n   signed by {s.signer_cert.subject.human_friendly}\n"
                  f"   unchanged since signing: {v.intact and v.valid} · covers: {whole} · "
                  f"Adobe would trust the issuer here: {v.trusted}")
    finally:
        key.close()
    print(f"\nOpen the folder: {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
