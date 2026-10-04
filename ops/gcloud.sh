#!/usr/bin/env bash
# gcloud, from Git Bash on Windows, without going through gcloud.cmd. The .cmd wrapper runs through cmd.exe, which
# mangles quoted arguments when the SDK's own path has a space in it ("C:\Users\Neil Lunavat\..."). This calls the
# SDK's bundled Python directly. Anywhere gcloud is on PATH and works, use that instead.
#
#   GCLOUD=ops/gcloud.sh ops/deploy.sh staging
set -euo pipefail
SDK="${CLOUDSDK_ROOT:-${LOCALAPPDATA:-}/gcloud-cli/google-cloud-sdk}"
SDK="$(cygpath -u "$SDK" 2>/dev/null || echo "$SDK")"
if [[ ! -f "$SDK/lib/gcloud.py" ]]; then
  exec gcloud "$@"
fi
# Git Bash rewrites arguments that look like paths when it starts a Windows program ("/readyz" became
# "C:/Program Files/Git/readyz" in a startup probe). None of gcloud's arguments here is a local path to convert.
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*"
export CLOUDSDK_PYTHON="$SDK/platform/bundledpython/python.exe"
exec "$CLOUDSDK_PYTHON" "$(cygpath -w "$SDK/lib/gcloud.py" 2>/dev/null || echo "$SDK/lib/gcloud.py")" "$@"
