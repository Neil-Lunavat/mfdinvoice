#!/usr/bin/env bash
# The 1.0.0 release notes, in Neil's words (8 Oct). Run after `uv run python packaging/build.py` in client/.
cd "$(dirname "$0")/.." && uv run --project client python ops/release.py \
  "The first release: your CAMS and KFintech commission invoices, made, signed, submitted, and imported into the bookkeeping software of your choice." \
  --new "Your ARN, name and GSTIN are read from CAMS and KFintech. Nothing is typed that the portals already know." \
  --new "Each month's invoices come from CAMS, by its email (forwarded from Gmail, read with a Gmail app password, or added by hand), and from KFintech." \
  --new "Your own invoices, numbered as GST asks, or the registrars' own." \
  --new "Signed with a photo of your signature, or with your DSC token." \
  --new "Your check before anything is sent: only what you tick goes." \
  --new "Submitted to CAMS and KFintech, and what each has is read back." \
  --new "Tally and Zoho Books: invoice numbers come from your books, and each invoice is entered in them." \
  --new "Downloads of any months, with every figure." \
  --new "When CAMS or KFintech change something on their portals, we fix it on our side as fast as we can, most often without an update, so the service stays reliable."
