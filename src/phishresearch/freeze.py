"""Freeze manifest (PRD s10, M4): hash everything that determines the TEST results of
BOTH directions before any TEST label is read. Evaluation refuses on any mismatch.

Hashed code = every module except presentation-only ones (reporting, cli), so figure/table
layout can be fixed after evaluation without unfreezing the science.
"""
from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path

from .common import GateError, Paths, canonical_json, environment_info, read_json, sha256_file, sha256_text, write_json

PRESENTATION_ONLY = {"reporting.py", "cli.py", "__main__.py", "nbviz.py"}


def _git_commit(root: Path) -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
                              check=True).stdout.strip() or None
    except Exception:
        return None


PKG = Path(__file__).resolve().parent


def _key(p: Path, root: Path) -> str:
    p = Path(p).resolve()
    if p.is_relative_to(PKG):
        return "pkg/" + p.relative_to(PKG).as_posix()
    return p.relative_to(root).as_posix()


def _resolve(key: str, root: Path) -> Path:
    return PKG / key[4:] if key.startswith("pkg/") else Path(root) / key


def _tracked_files(paths: Paths, config_path: Path, registry_path: Path | None) -> list[Path]:
    files = [config_path]
    if registry_path:
        files.append(registry_path)
    files += sorted(p for p in PKG.glob("*.py") if p.name not in PRESENTATION_ONLY)
    files += sorted((PKG / "resources").glob("*"))
    for name in ("records.parquet", "splits.parquet", "dev_features.parquet"):
        files.append(paths.processed / name)
    files += [paths.processed / "test_vault" / "test_features.parquet", paths.processed / "test_vault" / "test_labels.parquet"]
    for name in ("audit.json", "prepare.json"):
        files.append(paths.artifacts / name)
    if (paths.raw / "manifest.json").exists():
        files.append(paths.raw / "manifest.json")
    for src in ("A", "B"):
        d = paths.dev / src
        if not (d / "develop.json").exists():
            raise GateError(f"source {src} not developed; both directions must exist before freeze")
        files += sorted(p for p in d.rglob("*") if p.is_file())
    return files


def build_freeze(config_path: Path, registry_path: Path | None, paths: Paths, approved_by: str,
                 cfg: dict) -> dict:
    files = _tracked_files(paths, Path(config_path), Path(registry_path) if registry_path else None)
    hashes = {_key(f, paths.root): sha256_file(f) for f in files if Path(f).exists()}
    missing = [str(f) for f in files if not Path(f).exists()]
    if missing:
        raise GateError(f"cannot freeze, missing artefacts: {missing[:5]}")
    plan = []
    for src in ("A", "B"):
        dev = read_json(paths.dev / src / "develop.json")
        tgt = "B" if src == "A" else "A"
        for seed, info in dev["seeds"].items():
            for bid in info["bundles"]:
                plan.append({"bundle_id": bid, "source": src, "targets": [src, tgt],
                             "bundle": f"{(paths.dev / src / 'bundles').relative_to(paths.root).as_posix()}/{bid}"})
    body = {"protocol_version": cfg["protocol_version"], "file_hashes": hashes, "plan": plan,
            "seeds": cfg["models"]["seeds"], "k_candidates": cfg["selection"]["k_candidates"]}
    freeze = {"schema_version": 1, "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
              "approved_by": approved_by, "git_commit": _git_commit(paths.root), "environment": environment_info(),
              "body": body, "freeze_hash": sha256_text(canonical_json(body))}
    write_json(paths.freeze, freeze)
    return freeze


def verify_freeze(freeze_path: Path, root: Path) -> dict:
    if not Path(freeze_path).exists():
        raise GateError(f"missing freeze manifest {freeze_path}")
    fr = read_json(freeze_path)
    body = fr["body"]
    if sha256_text(canonical_json(body)) != fr.get("freeze_hash"):
        raise GateError("freeze manifest body was modified")
    if not fr.get("approved_by"):
        raise GateError("freeze manifest has no approver")
    bad = []
    for rel, h in body["file_hashes"].items():
        p = _resolve(rel, root)
        if not p.exists() or sha256_file(p) != h:
            bad.append(rel)
    if bad:
        raise GateError(f"freeze hash mismatch for {len(bad)} file(s): {bad[:5]}")
    return fr
