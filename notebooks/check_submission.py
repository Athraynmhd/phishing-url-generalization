"""Fail-closed submission assessment; engineering success is not scientific readiness."""
import argparse
import datetime as dt
from pathlib import Path
import re
import sys

import nbformat
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from phishresearch.common import read_json, sha256_file, write_json
from phishresearch.freeze import verify_freeze


def check(root=ROOT):
    frozen = verify_freeze(root / "artifacts/freeze.json", root)
    folder = root / "artifacts/publication_audit"
    baseline = read_json(folder / "baseline.json")
    assert all(sha256_file(root / p) == h for p, h in baseline["protected_sha256"].items()), "Protected output changed"
    correction_pointer = root / "artifacts/publication_corrections/manuscript_latest.json"
    corrected = correction_pointer.exists()
    correction_checks = None
    manuscript = root / "manuscript"
    if corrected:
        from check_corrections import check as check_corrections
        correction_checks = check_corrections(root)
        manuscript = root / correction_checks["corrected_manuscript"]
    bib = (manuscript / "refs.bib").read_text(encoding="utf-8")
    entries = re.findall(r"(?ms)^@.*?(?=^@|\Z)", bib)
    keys = {re.search(r"@\w+\{([^,]+)", entry)[1] for entry in entries}
    assert all(int(re.search(r"year\s*=\s*\{(\d+)\}", entry)[1]) >= 2022 for entry in entries), "Out-of-window bibliography"
    sources = "\n".join(p.read_text(encoding="utf-8") for p in (manuscript / "sections").glob("*.tex"))
    cited = {key for group in re.findall(r"\\cite\{([^}]+)\}", sources) for key in group.split(",")}
    assert cited <= keys, "Unresolved citation key"
    macros = (manuscript / "generated/macros.tex").read_text(encoding="utf-8")
    for key in re.findall(r"\\res\{([^}]+)\}", sources):
        assert "{r@" + key + "}" in macros, "Unresolved macro: " + key
    aux = (manuscript / "main.aux").read_text(encoding="utf-8")
    bbl = (manuscript / "main.bbl").read_text(encoding="utf-8")
    numbers = dict(re.findall(r"\\bibcite\{([^}]+)\}\{(\d+)\}", aux))
    for i, key in enumerate(re.findall(r"\\bibitem\{([^}]+)\}", bbl), 1):
        assert numbers[key] == str(i), "Stale bibliography numbering"
    pair = read_json(root / "docs/literature/primary_papers.json")
    assert {p["ref_id"] for p in pair["primary_papers"]} == {"R15", "R2"}
    cutoff, asof = (dt.date.fromisoformat(pair[k]) for k in ("five_year_cutoff", "as_of"))
    for paper in pair["primary_papers"]:
        pub = dt.date(paper["publication_year"], paper["publication_month"], paper.get("publication_day", 1))
        assert cutoff <= pub <= asof
    pdf = pymupdf.open(manuscript / "main.pdf")
    assert len(pdf) <= 10
    assert not any("??" in page.get_text() for page in pdf), "PDF has unresolved tokens"
    assert "Overfull" not in (manuscript / "main.log").read_text(encoding="utf-8"), "PDF layout overflow"
    nb = nbformat.read(root / "notebooks/phishing_research_pipeline.ipynb", as_version=4)
    nbformat.validate(nb)
    code = [cell for cell in nb.cells if cell.cell_type == "code"]
    assert all(cell.execution_count is not None for cell in code), "Notebook not fully executed"
    assert not any(o.output_type == "error" for c in code for o in c.outputs), "Notebook cell error"
    execution = read_json(root / "artifacts/notebook_audit/execution.json")
    assert execution["notebook_sha256"] == sha256_file(root / "notebooks/phishing_research_pipeline.ipynb")
    cycle_meta = read_json(folder / "latest_cycle.json")
    cycle = read_json(folder / cycle_meta["artifact"])
    assert cycle["protected_outputs_unchanged"] and cycle["freeze_hash"] == frozen["freeze_hash"]
    assert cycle["scores_verified"] and cycle["checks"]["val_thresholds_reproduced"] == 108, "Full score audit missing"
    regen = read_json(folder / "report_regeneration.json")
    assert all(regen["same_tables_macros_provenance"].values())
    clean = read_json(folder / "clean_validation.json")
    assert clean["status"] == "passed" and clean["notebook_kernel_executable_verified"]
    assert clean["unit_tests_passed"] > 0 and clean["notebook_cells"] == len(code)
    assert all(sha256_file(root / p) == h for p, h in clean["requirements_sha256"].items()), "Dependency snapshot changed after clean validation"
    pytest_path = root / "artifacts/publication_corrections/pytest.log" if corrected else folder / "pytest.log"
    raw_log = pytest_path.read_bytes()
    pytest_log = raw_log.decode("utf-16") if raw_log.startswith((b"\xff\xfe", b"\xfe\xff")) else raw_log.decode("utf-8-sig")
    match = re.search(r"(\d+) passed(?:, [^\n]*?)? in ([\d.]+)s", pytest_log)
    assert match, "Completed passing pytest evidence absent"
    historical_findings = list(cycle["blockers"])
    if corrected:
        blockers = []
        assert correction_checks["r2_full_text_review_complete"]
        assert correction_checks["shap_arrays_independently_verified"] == 24
        assert "exploratory" in (manuscript / "main.tex").read_text(encoding="utf-8").lower()
    else:
        blockers = historical_findings + ["Direct HP numeric label mapping confirmation pending", "Complete primary R2 PDF review pending"]
    if any("Author Name" in p.get_text() or "email@example.org" in p.get_text() for p in pdf):
        blockers.append("Author identities/affiliations deferred by user")
    blockers.append("Target venue, release URL/DOI and owner-approved code licence not supplied")
    result = {"engineering_status": "passed", "submission_ready": not blockers,
              "as_of": pair["as_of"], "freeze_hash": frozen["freeze_hash"],
              "primary_refs": [p["ref_id"] for p in pair["primary_papers"]],
              "bibliography_entries_within_five_years": len(entries), "pdf_pages": len(pdf),
              "pdf_sha256": sha256_file(manuscript / "main.pdf"), "notebook_code_cells": len(code),
              "pytest_passed": int(match[1]), "pytest_seconds": float(match[2]),
              "isolated_environment_verified": True,
              "isolated_environment_unit_tests": clean["unit_tests_passed"],
              "independent_audit_cycle": cycle_meta["artifact"], "blockers": blockers,
              "manuscript": str(manuscript.relative_to(root)),
              "correction_checks": correction_checks,
              "historical_v1_findings_retained": historical_findings,
              "research_status": "frozen classification results; exploratory post-freeze SHAP correction" if corrected else "frozen v1 with unresolved findings",
              "claim_scope": "historical two-source empirical benchmark; no global novelty/causality/deployment claim"}
    status_path = folder / "submission_status.json"
    if status_path.exists():
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        (folder / f"submission_status_before_{stamp}.json").write_bytes(status_path.read_bytes())
    write_json(status_path, result)
    print(f"Engineering: passed; submission_ready={result['submission_ready']}; {len(blockers)} unresolved items.")
    for item in blockers:
        print(" - " + item)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    result = check()
    if args.require_ready and not result["submission_ready"]:
        raise SystemExit(2)
