"""Source adapters: raw files -> canonical record rows with explicit label mapping (PRD s6-7).

Only url_raw + label are taken from sources. Index columns are dropped after the header is
checked exactly, so a silent schema change in the source fails loudly.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from .common import GateError, canonical_json, sha256_text

HP_HEADER = ["", "index", "url", "label", "Unnamed: 0"]


def record_id(dataset_id: str, source_file: str, original_row: int, url_raw: str) -> str:
    return sha256_text(canonical_json([dataset_id, source_file, int(original_row), url_raw]))


def _frame(dataset_id: str, source_file: str, urls: list[str], labels: list[int], split: str | None) -> pd.DataFrame:
    rows = range(len(urls))
    return pd.DataFrame({
        "record_id": [record_id(dataset_id, source_file, i, u) for i, u in zip(rows, urls)],
        "dataset_id": dataset_id,
        "source_file": source_file,
        "original_row": list(rows),
        "original_split": split,
        "url_raw": urls,
        "label": pd.array(labels, dtype="int64"),
    })


def load_ebbu_json(path: Path, source_file: str, label: int, dataset_id: str = "A") -> pd.DataFrame:
    """A: JSON array of URL strings; class given by the file (legitimate=0 / phishing=1)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(u, str) for u in data):
        raise GateError(f"{source_file}: expected a JSON array of strings")
    if label not in (0, 1):
        raise GateError("label must be 0 or 1")
    return _frame(dataset_id, source_file, data, [label] * len(data), None)


def load_hp_csv(path: Path, source_file: str, split: str, dataset_id: str = "B") -> pd.DataFrame:
    """B: CSV with header ',index,url,label,Unnamed: 0'; only url/label kept."""
    with open(path, newline="", encoding="utf-8") as f:
        header = next(csv.reader(f))
    if header != HP_HEADER:
        raise GateError(f"{source_file}: header changed: {header} (expected {HP_HEADER})")
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8", header=0)
    if df.shape[1] != len(HP_HEADER):
        raise GateError(f"{source_file}: expected {len(HP_HEADER)} columns, got {df.shape[1]}")
    urls, labels = df.iloc[:, 2], df.iloc[:, 3]
    bad = set(labels) - {"0", "1"}
    if bad:
        raise GateError(f"{source_file}: unexpected label values {sorted(bad)[:5]}")
    return _frame(dataset_id, source_file, urls.tolist(), labels.astype(int).tolist(), split)


def load_dataset(source_id: str, registry: dict, raw_dir: Path) -> pd.DataFrame:
    """Load one registered source into canonical (pre-parse) records."""
    src = registry["sources"][source_id]
    frames = []
    for f in src["files"]:
        local = raw_dir / source_id / src["commit"] / Path(f["path"]).name
        if not local.exists():
            raise GateError(f"missing raw file {local}; run `acquire` first")
        if src["adapter"] == "ebbu_json":
            frames.append(load_ebbu_json(local, f["path"], int(f["label"]), source_id))
        elif src["adapter"] == "hp_csv":
            frames.append(load_hp_csv(local, f["path"], f["split"], source_id))
        else:
            raise GateError(f"unknown adapter {src['adapter']}")
    return pd.concat(frames, ignore_index=True)


def load_verification_copy(registry: dict, raw_dir: Path) -> pd.DataFrame:
    """Repo B's ebbu_*.csv - used only to cross-check repo B's label convention."""
    v = registry["verification_files"]["B_ebbu_copy"]
    frames = []
    for f in v["files"]:
        local = raw_dir / "B_ebbu_copy" / v["commit"] / Path(f["path"]).name
        df = pd.read_csv(local, dtype=str, keep_default_na=False, encoding="utf-8")
        if list(df.columns)[1:] != ["url", "label", "index"]:
            raise GateError(f"{f['path']}: unexpected header {list(df.columns)}")
        frames.append(df[["url", "label"]].rename(columns={"url": "url_raw"}).astype({"label": int}))
    return pd.concat(frames, ignore_index=True)
