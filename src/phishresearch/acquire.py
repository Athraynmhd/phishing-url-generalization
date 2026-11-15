"""Download raw dataset files at pinned commits into an immutable layout (PRD s6-7).

data/raw/<source>/<commit>/<filename>; temp file -> validate -> atomic rename.
An existing file with a different hash is never overwritten.
"""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import requests

from .common import GateError, load_yaml, read_json, sha256_file, write_json

RAW_URL = "https://raw.githubusercontent.com/{repo}/{commit}/{path}"


def raw_path(raw_dir: Path, source: str, commit: str, file_path: str) -> Path:
    return raw_dir / source / commit / Path(file_path).name


def _validate_bytes(head: bytes, size: int, expected_size: int | None, url: str) -> None:
    if size == 0:
        raise GateError(f"empty download: {url}")
    if head.lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
        raise GateError(f"HTML/error page instead of data: {url}")
    if expected_size is not None and size != expected_size:
        raise GateError(f"size mismatch for {url}: got {size}, expected {expected_size} (GitHub tree)")


def download_file(source: str, repo: str, commit: str, file_path: str, raw_dir: Path,
                  expected_size: int | None = None, session: requests.Session | None = None) -> dict:
    url = RAW_URL.format(repo=repo, commit=commit, path=file_path)
    dest = raw_path(raw_dir, source, commit, file_path)
    if dest.exists():
        return {"url": url, "path": str(dest), "sha256": sha256_file(dest), "size": dest.stat().st_size,
                "status": "cached"}
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    s = session or requests.Session()
    with s.get(url, timeout=120, stream=True) as r:
        if r.status_code != 200:
            raise GateError(f"HTTP {r.status_code} for {url}")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    with open(tmp, "rb") as f:
        head = f.read(64)
    _validate_bytes(head, tmp.stat().st_size, expected_size, url)
    os.replace(tmp, dest)
    return {"url": url, "path": str(dest), "sha256": sha256_file(dest), "size": dest.stat().st_size,
            "status": "downloaded"}


def acquire(registry_path: Path, raw_dir: Path) -> dict:
    reg = load_yaml(registry_path)
    manifest_path = raw_dir / "manifest.json"
    old = read_json(manifest_path) if manifest_path.exists() else {"files": {}}
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    files = dict(old.get("files", {}))
    groups = {**reg["sources"], **reg.get("verification_files", {})}
    with requests.Session() as session:
        for sid, src in groups.items():
            for f in src["files"]:
                info = download_file(sid, src["repo"], src["commit"], f["path"], raw_dir, f.get("size"), session)
                key = f"{sid}:{f['path']}"
                prev = files.get(key)
                if prev and prev["sha256"] != info["sha256"]:
                    raise GateError(f"hash changed for {key}; raw files are immutable")
                files[key] = {
                    "source_id": sid, "repo": src["repo"], "commit": src["commit"], "url": info["url"],
                    "file": f["path"], "local_path": os.path.relpath(info["path"], raw_dir),
                    "retrieved_at": prev["retrieved_at"] if prev else now,
                    "size": info["size"], "sha256": info["sha256"],
                    "expected_records": f.get("expected_records"),
                    "observed_records": prev.get("observed_records") if prev else None,
                    "label_mapping_evidence": src.get("label_mapping_evidence"),
                    "license_status": src.get("license_status"),
                    "role": "source" if sid in reg["sources"] else "verification_only",
                }
                print(f"[acquire] {key}: {info['status']} {info['size']} bytes sha256={info['sha256'][:12]}")
    manifest = {"schema_version": 1, "registry": str(registry_path), "files": files}
    write_json(manifest_path, manifest)
    return manifest
