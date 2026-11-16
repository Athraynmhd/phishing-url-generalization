"""Build a separate manuscript bundle with exploratory corrected SHAP numbers.

The original manuscript/generated numeric artefacts remain byte-identical. The new
bundle's numbers are generated exclusively through its generated/macros.tex.
"""
import datetime as dt
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from phishresearch.common import Paths, load_yaml, read_json, sha256_file, write_json
from phishresearch.freeze import verify_freeze
from phishresearch.nbviz import verify_shap_correction
from phishresearch.reporting import run_report


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Expected one editorial target: {old[:90]}")
    return text.replace(old, new, 1)


def main():
    cfg = load_yaml(ROOT / "configs/protocol.yaml")
    paths = Paths.from_config(cfg, ROOT)
    frozen = verify_freeze(paths.freeze, ROOT)
    correction = verify_shap_correction(paths, frozen)
    if correction is None:
        raise RuntimeError("Complete corrected SHAP evidence is required")
    shap_dir, manifest = correction
    hp = read_json(paths.artifacts / "publication_corrections/hp_encoding.json")
    assert hp["mapping"]["benign"] == 0 and hp["mapping"]["phishing"] == 1
    original = ROOT / "manuscript"
    target = original / "corrected"
    if target.exists():
        target = original / ("corrected_" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S%f"))
    target.mkdir()
    shutil.copytree(original / "sections", target / "sections")
    for name in ("main.tex", "refs.bib"):
        shutil.copy2(original / name, target / name)
    if (original / "IEEEtran.cls").exists():
        shutil.copy2(original / "IEEEtran.cls", target / "IEEEtran.cls")
    main_tex = (target / "main.tex").read_text(encoding="utf-8")
    main_tex = replace_once(main_tex, "Project category: General Machine Learning; application and empirical evaluation.",
                           "General Machine Learning: frozen classification benchmark with exploratory post-freeze SHAP corrections.")
    main_tex = replace_once(main_tex, "\\clearpage\n\\bibliographystyle", "\\bibliographystyle")
    main_tex = replace_once(main_tex, r"\input{sections/conclusion.tex}", "\\clearpage\n\\input{sections/conclusion.tex}")
    (target / "main.tex").write_text(main_tex, encoding="utf-8")
    p = target / "sections/related.tex"
    text = replace_once(p.read_text(encoding="utf-8"),
        "Complete PDF review remains pending; publisher material supports these stated roles, while unavailable details are not treated as evidence that a control is absent.",
        "Full-text review confirms random URL splits, validation tuning, and target-distribution alignment. Their diagnostic RF feature shortlist uses impurity importance shared across dataset-trained models, whereas our ranking uses source-domain permutation evidence. Details not reported in the article are not treated as proof that a control was absent.")
    p.write_text(text, encoding="utf-8")
    p = target / "sections/methods.tex"
    text = p.read_text(encoding="utf-8")
    start = "This indirect check does not by itself prove HP-specific numeric encoding; direct confirmation remains a limitation."
    text = replace_once(text, start, r"An additional evaluator-only audit uniquely matches both numeric classes to the benign/phishing counts in every original HP split in Table~1 of~\cite{rashid2024}, supporting 0 = benign and 1 = phishing directly against published class aggregates. This is count-based crossvalidation; an author-written numeric codebook is not supplied.")
    text = replace_once(text,
        r"The largest saved additivity residual is \res{shapAddErr}; some RF outputs exceed the existing $10^{-6}$ validation tolerance. Accordingly, SHAP is reported as a diagnostic with an unresolved validation limitation, not a fully validated explanation contribution.",
        r"The explanations here are an explicitly exploratory post-freeze correction on exactly the saved feature matrices. RF inputs/background are cast to the classifier's float32 input lattice; SHAP's threshold representation is rounded downward on that lattice to preserve the original classifier's split decisions. The fitted classifiers are unchanged. Every corrected cohort passes the existing $10^{-6}$ tolerance, with maximum residual \res{shapAddErr}; explainer predictions and background expectations are independently checked against the actual classifier. Additivity is a numerical consistency property and does not by itself establish explanation fidelity.")
    p.write_text(text, encoding="utf-8")
    p = target / "sections/results.tex"
    text = replace_once(p.read_text(encoding="utf-8"),
        r"Some saved RF explanations exceed the additivity tolerance (maximum residual \res{shapAddErr}); the following rankings are diagnostic and must not be read as a complete validation of explanation fidelity.",
        r"The corrected exploratory explanations pass strict additivity (maximum residual \res{shapAddErr}). The following rankings use these corrected outputs; the original failing outputs remain archived. Numerical consistency does not establish causal attribution or complete explanation fidelity.")
    text = replace_once(text, r"\caption{SHAP rank agreement:", r"\caption{Exploratory corrected SHAP rank agreement:")
    text = replace_once(text, r"\caption{Mean $|$SHAP$|$", r"\caption{Exploratory corrected mean $|$SHAP$|$")
    p.write_text(text, encoding="utf-8")
    p = target / "sections/discussion.tex"
    text = replace_once(p.read_text(encoding="utf-8"),
        "Numeric HP label encoding was verified indirectly through the repository's copy of EBBU; complete primary-paper checks remain pending.",
        "HP encoding is crossvalidated against the primary paper's class counts in all original splits; a verbatim numeric codebook is not supplied. The complete user-supplied article PDF was reviewed, including its data, alignment algorithm and limitations.")
    text = replace_once(text,
        "Some saved SHAP outputs fail the additivity tolerance, so attributions cannot substantiate causal or fully validated explanation claims. The notebook audit also identified direct TEST-vault access in the frozen legacy SHAP analysis; the repaired notebook does not execute that path, but a corrected analysis must follow the versioning rules.",
        "The original SHAP outputs failed additivity and the legacy analysis accessed TEST labels outside the evaluator. Both findings remain in the v1 audit trail. This version uses a separately hashed, label-free exploratory correction on saved feature matrices, with strict additivity and classifier-equivalence checks. Correction after observing v1 outputs does not create a new independent holdout or establish causal explanation fidelity. Full-text review of the primary papers supports this methodological distinction without establishing global novelty.")
    p.write_text(text, encoding="utf-8")
    p = target / "sections/conclusion.tex"
    text = replace_once(p.read_text(encoding="utf-8"),
        "SHAP comparisons remain diagnostic because some saved outputs fail additivity validation (RQ4).",
        "Exploratory corrected SHAP comparisons pass strict numerical additivity while retaining descriptive, non-causal scope (RQ4).")
    text = replace_once(text, "Future work should resolve explanation validation, evaluate more recent independent sources,",
                        "Future work should assess explanation fidelity beyond additivity, evaluate more recent independent sources,")
    text = replace_once(text, r"every number in this paper is generated by \texttt{phishresearch.cli report}.",
                        r"every empirical number in this paper is read from this bundle's automatically generated \texttt{generated/macros.tex}. Correction provenance links its SHAP inputs to the preserved v1 outputs.")
    p.write_text(text, encoding="utf-8")
    run_report(cfg, paths, target, shap_dir=shap_dir)
    provenance = {"status": "exploratory corrected manuscript", "parent_freeze_hash": frozen["freeze_hash"],
                  "shap_manifest": str((shap_dir / "manifest.json").relative_to(ROOT)),
                  "shap_manifest_sha256": sha256_file(shap_dir / "manifest.json"),
                  "hp_encoding_evidence": "artifacts/publication_corrections/hp_encoding.json",
                  "numeric_source": str((target / "generated/macros.tex").relative_to(ROOT)),
                  "classification_results_changed": False, "original_manuscript_numbers_unchanged": True}
    write_json(target / "correction_provenance.json", provenance)
    write_json(paths.artifacts / "publication_corrections/manuscript_latest.json", {"artifact": str(target.relative_to(ROOT))})
    verify_freeze(paths.freeze, ROOT)
    print(f"Corrected manuscript bundle: {target}")


if __name__ == "__main__":
    main()
