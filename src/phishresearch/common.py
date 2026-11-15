"""Small shared helpers: hashing, canonical JSON, config loading, paths."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PKG_DIR = Path(__file__).resolve().parent


class GateError(RuntimeError):
    """A protocol gate failed; CLI turns this into a nonzero exit."""


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_text(s: str) -> str:
    return sha256_bytes(s.encode("utf-8"))


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_ids(ids) -> str:
    """Order-independent hash of a set of record ids."""
    return sha256_text("\n".join(sorted(map(str, ids))))


def write_json(path: Path | str, obj: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_yaml(path: Path | str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Paths:
    root: Path
    raw: Path
    processed: Path
    artifacts: Path

    @classmethod
    def from_config(cls, cfg: dict, root: Path | str = ".") -> "Paths":
        root = Path(root).resolve()
        p = cfg["paths"]
        return cls(root, root / p["raw"], root / p["processed"], root / p["artifacts"])

    @property
    def dev(self) -> Path:
        return self.artifacts / "dev"

    @property
    def eval(self) -> Path:
        return self.artifacts / "eval"

    @property
    def analysis(self) -> Path:
        return self.artifacts / "analysis"

    @property
    def freeze(self) -> Path:
        return self.artifacts / "freeze.json"


def effective_threads(cfg: dict) -> int:
    return max(1, min(int(cfg["models"]["threads"]), os.cpu_count() or 1))


def environment_info() -> dict:
    import psutil

    pkgs = {}
    for name in ["numpy", "pandas", "pyarrow", "sklearn", "lightgbm", "shap", "joblib", "idna", "yaml"]:
        try:
            pkgs[name] = __import__(name).__version__
        except Exception:  # pragma: no cover
            pkgs[name] = "unavailable"
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count_logical": os.cpu_count(),
        "cpu_count_physical": psutil.cpu_count(logical=False),
        "ram_gb": round(psutil.virtual_memory().total / 2**30, 2),
        "packages": pkgs,
    }
