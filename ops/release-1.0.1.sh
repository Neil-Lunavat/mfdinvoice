#!/usr/bin/env bash
# The 1.0.1 release notes (9 Oct; Neil rewrites the words). Run after `uv run python packaging/build.py` in client/.
cd "$(dirname "$0")/.." && uv run --project client python ops/release.py \
  "Runs carry on past what used to stop them, and tell you at the end what went differently." \
  --better "One registrar's trouble never stops the other; a status word we haven't seen is shown as the registrar wrote it." \
  --better "When CAMS or KFintech doesn't respond, the software tries again and shows you it is doing so." \
  --better "Run is always on Overview, for both registrars or either one." \
  --new "Forwarding CAMS's mails from Gmail, step by step with pictures, and no code to type." \
  --new "Any CAMS mail with your invoices is read in, also one you asked for on CAMS's own site." \
  --better "Setup keeps what you have done if the software closes, and opens where you left it." \
  --better "Previews show the real invoice, with your DSC token's mark where it goes." \
  --new "Uninstalling asks whether to remove your data from this PC too." \
  --fixed "The software reaches MFDInvoice on networks that block its address."
