# The app as PyInstaller builds it: one folder, the exe and `_internal/` beside it (`build.py` runs this).
#
# A folder, not one self-unpacking file: it starts at once, and an update keeps the old version by copying the folder.
#
# The portal steps (`client.automation`) are left out on purpose: an installed app downloads the current ones, checks
# our signature on them and runs them from a folder (`client/hands/loader.py`). PyInstaller therefore never reads what
# the steps import, so everything they may need is named here:
#   - every module of ours outside the steps
#   - the libraries the steps use, whole
#   - the whole standard library, so a later version of the steps can use a module this version does not, without
#     an update of the app
#
# Also inside: the window's built files (`window/`), the brand (`client/brand.json`), the client's METADATA file (the
# version is read from it: `client/pyproject.toml` is the one place it is written; the rest of that folder is uv's
# bookkeeping, which differs from build to build), and Playwright's driver. pywebview's WebView2 pieces come through
# its hook. A USB token's driver is loaded only when one is used (`tokenpin`), so the token library's compiled half
# and its submodules are named. No signing of the app itself.

import importlib.util
import json
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

HERE = Path(SPECPATH)
CLIENT = HERE.parent
NAME = json.loads((CLIENT / "src" / "client" / "brand.json").read_text(encoding="utf-8"))["name"]
META = Path(copy_metadata("client")[0][1]).name          # client-<version>.dist-info, as it is named inside the exe

STEPS = "client.automation"
# The checkout's test bench (`uv run app`: no website, the dev panel's calls) is never in the exe; build.py checks.
DEV_ONLY = ["client.hands.devstart", "client.hands.devsite", "client.hands.devtools"]
OURS = [m for m in collect_submodules("client")
        if m != STEPS and not m.startswith(STEPS + ".") and m not in DEV_ONLY]
STEP_LIBRARIES = ["openpyxl", "pdfplumber", "pdfminer", "xlrd", "pypdf", "reportlab", "PIL", "playwright"]

# The standard library, whole, but for what no step has a use for on a person's PC.
NOT_NEEDED = {"tkinter", "turtle", "turtledemo", "idlelib", "lib2to3", "test", "ensurepip", "venv", "pydoc_data",
              "antigravity", "this", "distutils"}


def _there(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _whole(name: str) -> list[str]:
    spec = importlib.util.find_spec(name)
    if spec is None or not spec.submodule_search_locations:
        return [name]
    return collect_submodules(name, filter=lambda m: ".test" not in m and ".idle_test" not in m, on_error="ignore")


STANDARD = [m for top in sorted(sys.stdlib_module_names)
            if not top.startswith("_") and top not in NOT_NEEDED and _there(top) for m in _whole(top)]
LIBRARIES = [m for lib in STEP_LIBRARIES for m in collect_submodules(lib, on_error="ignore")]

a = Analysis(
    [str(HERE / "app.py")],
    datas=[(str(CLIENT / "window" / "dist"), "window"),
           (str(CLIENT / "src" / "client" / "brand.json"), "client"),
           (str(CLIENT / "src" / "client" / "zoho.json"), "client"),
           *copy_metadata("client"),
           *collect_data_files("playwright", includes=["driver/**"]),
           *collect_data_files("pdfminer"), *collect_data_files("reportlab"), *collect_data_files("openpyxl")],
    hiddenimports=[*collect_submodules("pkcs11"), *OURS, *LIBRARIES, *STANDARD],
    excludes=[STEPS, *DEV_ONLY, "pytest", "tkinter"],
)
a.datas = [d for d in a.datas if Path(d[0]).parent.name != META or Path(d[0]).name == "METADATA"]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=NAME, console=False, upx=False, icon=str(HERE / "icon.ico"),
          version=os.environ.get("APP_VERSION_FILE") or None)
coll = COLLECT(exe, a.binaries, a.datas, upx=False, name=NAME)
