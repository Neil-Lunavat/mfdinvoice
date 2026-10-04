"""Load config.toml into typed, frozen dataclasses."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path("config.toml")


@dataclass(frozen=True)
class Distributor:
    arn: str


@dataclass(frozen=True)
class Paths:
    signature: Path
    workspace: Path
    inbox: Path      # CAMS mailback ZIP + XLS land here first (default <workspace>/inbox)
    db: Path         # SQLite store (default <workspace>/client.db)


@dataclass(frozen=True)
class Config:
    distributor: Distributor
    paths: Paths


def load(path: Path = DEFAULT_PATH) -> Config:
    raw = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    base = path.resolve().parent
    p = raw["paths"]
    workspace = (base / p["workspace"]).resolve()
    return Config(
        distributor=Distributor(arn=raw["distributor"]["arn"]),
        paths=Paths(
            signature=(base / p["signature"]).resolve(),
            workspace=workspace,
            inbox=(base / p["inbox"]).resolve() if "inbox" in p else workspace / "inbox",
            db=(base / p["db"]).resolve() if "db" in p else workspace / "client.db",
        ),
    )
