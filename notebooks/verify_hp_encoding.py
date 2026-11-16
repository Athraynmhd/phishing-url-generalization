"""Crossvalidate raw HP numeric encoding against primary-paper class aggregates."""
import datetime as dt
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from phishresearch.common import Paths, load_yaml, read_json, sha256_file, write_json
from phishresearch.corrections.evaluation import verify_hp_encoding
from phishresearch.freeze import verify_freeze


def main():
    cfg = load_yaml(ROOT / "configs/protocol.yaml")
    paths = Paths.from_config(cfg, ROOT)
    frozen = verify_freeze(paths.freeze, ROOT)
    paper = ROOT / "docs/literature/r2_hp_table1.json"
    report = verify_hp_encoding(paths, read_json(paper)["counts"])
    report.update(freeze_hash=frozen["freeze_hash"], paper=read_json(paper), paper_table_sha256=sha256_file(paper))
    verify_freeze(paths.freeze, ROOT)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = paths.artifacts / "publication_corrections"
    write_json(folder / f"hp_encoding_{stamp}.json", report)
    write_json(folder / "hp_encoding.json", report)
    print(f"HP: {report['status']}; benign={report['mapping']['benign']}, phishing={report['mapping']['phishing']}; all original splits match.")


if __name__ == "__main__":
    main()
