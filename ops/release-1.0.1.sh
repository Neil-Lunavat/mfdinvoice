#!/usr/bin/env bash
# The 1.0.1 release notes (Neil, 9 Oct). Run after `uv run python packaging/build.py` in client/.
cd "$(dirname "$0")/.." && uv run --project client python ops/release.py \
  "Major bug fixes and fallback handling." \
  --better "If one registrar has trouble, the other carries on, and you're told at the end what happened." \
  --better "Smoother when CAMS or KFintech is slow." \
  --better "Run is always on Overview, for both registrars or either one." \
  --new "Forwarding CAMS's mails from Gmail, step by step with pictures." \
  --new "CAMS's invoice mails are picked up whenever they arrive." \
  --better "Setup keeps your progress if the software closes." \
  --better "Previews show your real invoice, with your DSC token's mark." \
  --new "Uninstalling asks whether to remove your data from this PC too." \
  --fixed "Works on networks that block our website."
