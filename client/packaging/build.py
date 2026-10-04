"""The build: a commit in, `MFDInvoice-Setup.exe` out.

    cd client && uv run python packaging/build.py            (HEAD)
    cd client && uv run python packaging/build.py <commit>

It builds from `git archive <commit>`, never from the working tree, so what ships is exactly what is in git. The
steps:

1. the commit's `client/` into `packaging/build/src/`
2. the window: `bun install --frozen-lockfile`, `bun run build`
3. the exe: the locked dependencies (`uv sync --frozen`), then PyInstaller with `app.spec`. The portal steps
   (`client.automation`) are left out: an installed app downloads them, signed (`app.spec` says how)
4. the exe's own check: it gets the steps from the software's server the way an installed app does, checks our
   signature and imports every module in them (`--check-steps`). A build whose exe cannot is not packed
5. the installer: Inno Setup with `installer.iss`, into `packaging/dist/`

The same commit gives the same inputs every time: locked dependencies on both sides, a fixed hash seed, and the
commit's own time as every timestamp (`SOURCE_DATE_EPOCH`, Inno's `TouchDate`). Unsigned, on purpose: no step here
expects a certificate.

It ends by printing the installer's SHA-256 and writing `packaging/dist/release.json` (version, sha256, size,
commit), which the release routine reads (`ops/release.py`).

Needs on this PC: git, uv, bun, and Inno Setup 6 (`winget install JRSoftware.InnoSetup`).
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tomllib
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = HERE / "build"
OUT = HERE / "dist"
ISCC = ("ISCC.exe", r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe", r"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe",
        r"%ProgramFiles%\Inno Setup 6\ISCC.exe")


def run(*args: str, cwd: Path, env: dict | None = None) -> None:
    print(f"\n> {' '.join(args)}", flush=True)
    subprocess.run(args, cwd=cwd, env=env, check=True)      # noqa: S603


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()  # noqa: S603, S607


def iscc() -> str:
    for candidate in ISCC:
        found = shutil.which(os.path.expandvars(candidate))
        if found:
            return found
    sys.exit("Inno Setup 6 is not on this PC: winget install JRSoftware.InnoSetup")


def version_file(path: Path, name: str, version: str) -> None:
    """The exe's Windows version resource, so Explorer and the installer show the version."""
    nums = tuple((*[int(x) for x in version.split(".")], 0, 0, 0, 0)[:4])
    path.write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
                    date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
          StringStruct('CompanyName', '{name}'), StringStruct('FileDescription', '{name}'),
          StringStruct('FileVersion', '{version}'), StringStruct('InternalName', '{name}'),
          StringStruct('OriginalFilename', '{name}.exe'), StringStruct('ProductName', '{name}'),
          StringStruct('ProductVersion', '{version}')])]),
        VarFileInfo([VarStruct('Translation', [1033, 1200])])])
""", encoding="utf-8")


def check_steps(exe: Path) -> None:
    """Run the built exe's own check, with its data in a folder of this build's, so nothing of the person's is
    touched: it must get the published steps, check our signature and import all of them."""
    said = WORK / "check-steps.txt"
    env = {**os.environ, "LOCALAPPDATA": str(WORK / "appdata")}
    (WORK / "appdata").mkdir(exist_ok=True)
    print(f"\n> {exe.name} --check-steps", flush=True)
    code = subprocess.run([str(exe), "--check-steps", str(said)], env=env, timeout=300).returncode  # noqa: S603
    text = said.read_text(encoding="utf-8") if said.exists() else "(it wrote nothing)"
    print(text)
    if code != 0:
        sys.exit("The built app could not get and load the published steps. Not packed.")


def main() -> None:
    commit = git("rev-parse", sys.argv[1] if len(sys.argv) > 1 else "HEAD")
    when = int(git("show", "-s", "--format=%ct", commit))
    if git("status", "--porcelain", "--", "client"):
        print("Note: client/ has changes that are not committed. They are NOT in this build.")

    shutil.rmtree(WORK, ignore_errors=True)
    src = WORK / "src"
    src.mkdir(parents=True)
    tar = subprocess.run(["git", "archive", "--format=tar", commit, "client"], cwd=ROOT,  # noqa: S603, S607
                         check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        t.extractall(src, filter="data")
    client = src / "client"
    brand = json.loads((client / "src" / "client" / "brand.json").read_text(encoding="utf-8"))
    name, site = brand["name"], brand["site"].rstrip("/")
    version = tomllib.loads((client / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    print(f"Building {name} {version} from {commit[:7]}")

    run("bun", "install", "--frozen-lockfile", cwd=client / "window")
    run("bun", "run", "build", cwd=client / "window")

    version_file(WORK / "version.txt", name, version)
    env = {**os.environ, "PYTHONHASHSEED": "0", "SOURCE_DATE_EPOCH": str(when),
           "APP_VERSION_FILE": str(WORK / "version.txt")}
    env.pop("VIRTUAL_ENV", None)                       # the archive's own environment, not the checkout's
    run("uv", "sync", "--frozen", "--no-dev", "--group", "build", cwd=client, env=env)
    run("uv", "run", "--frozen", "--no-dev", "--group", "build", "pyinstaller", "packaging/app.spec", "--noconfirm",
        "--clean", "--distpath", str(WORK / "exe"), "--workpath", str(WORK / "pyinstaller"), cwd=client, env=env)

    check_steps(WORK / "exe" / name / f"{name}.exe")

    OUT.mkdir(exist_ok=True)
    stamp = datetime.fromtimestamp(when, UTC)
    run(iscc(), "/Qp", f"/DAppName={name}", f"/DAppVersion={version}", f"/DSite={site}",
        f"/DSourceDir={WORK / 'exe' / name}", f"/DOutputDir={OUT}", f"/DTouchDate={stamp:%Y-%m-%d}",
        f"/DTouchTime={stamp:%H:%M:%S}", str(client / "packaging" / "installer.iss"), cwd=client)

    installer = OUT / f"{name}-Setup.exe"
    digest = hashlib.sha256(installer.read_bytes()).hexdigest()
    (OUT / f"{name}-Setup.sha256").write_text(f"{digest}  {installer.name}\n", encoding="utf-8")
    (OUT / "release.json").write_text(json.dumps({
        "version": version, "sha256": digest, "bytes": installer.stat().st_size, "commit": commit,
        "installer": str(installer)}, indent=1), encoding="utf-8")
    print(f"""
{installer}
{name} {version}, commit {commit[:7]}, {installer.stat().st_size / 1e6:.0f} MB
SHA-256 {digest}

Next, to release it (uploads it to the website and writes the release into its pages; you then deploy):
  uv run --project client python ops/release.py "<what is new, in one sentence>"
""")


if __name__ == "__main__":
    main()
