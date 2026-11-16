# TASKS / evidence log

| Milestone | Status | Evidence |
|---|---|---|
| M0 Literature & data feasibility | **Current primary full texts reviewed; HP encoding crossvalidated** | `docs/literature/gap_matrix.csv` (R1–R5, R15); pinned raw counts/hashes preserved. R15 (2022) / R2 (2024) full texts reviewed. All six HP Table 1 class counts match the original CSV splits under 0 benign / 1 phishing only; no author-written codebook or row-level label verification claimed. D-37 and `docs/literature/r2_fulltext_review.md`. Dataset redistribution licence remains unclear. |
| M1 Foundation | Done | package, configs, schemas, offline parser + PSL; U01–U03 pass |
| M2 Data protocol | Done | `audit.json` (reconciles = true, 0 cross-source group intersection), `prepare.json`; AC01–AC03 |
| M3 Models & selection | Done | `artifacts/dev/{A,B}`; I01, I03 pass; outer CV in `outer_cv.csv` |
| M4 Freeze | see `artifacts/freeze.json` | signed by agent on user instruction (D-14) |
| M5 Final evaluation | see `artifacts/eval/metrics.json` | single batch; I06 recompute check in `artifacts/analysis/checks.json` |
| M6 Analysis & manuscript | see `manuscript/` | macros/provenance in `manuscript/generated/` |
| Notebook audit (2026-11-16) | **Done; SHAP scientific limitation remains** | 48/48 code cells executed, zero error outputs; `artifacts/notebook_audit/execution.json`. Freeze, evaluation, analysis and generated manuscript outputs unchanged during execution. Saved SHAP recovery verified against 24 NPZ arrays; D-22–D-25 and `artifacts/analysis/recovery.json`. |
| Two-primary-paper positioning (2026-11-16) | **Done; primary full-text/recency and SHAP limitations remain explicit** | D-26–D-28; `docs/project_positioning.md`; Introduction/Related Work/Discussion clarify gap and bounded empirical contributions. IEEE journal PDF: 8 pages, no unresolved citations/macros or overfull boxes. Notebook 48/48 cells passed; `python -m pytest -q`: 64 passed in 346.91 s. Evidence: `artifacts/editorial_revision_20261116/checks.json`. |
| Primary-paper recency correction (2026-11-16) | Historical editorial cycle, superseded by D-33 | R2 (2024) + R5 (2026) was the temporary D-29–D-30 pair. The subsequent PRD v1.1 and R15 assessment led to the current R15/R2 pair; R5 remains adjacent work. No scientific protocol changes. |
| R15 candidate assessment (2026-11-16) | **Done; migration completed in the next cycle** | Institutional PDF and Crossref checked; publication 2022-04-18 meets five-year window. RF/LightGBM participation and LR/TF-IDF best-result caveat verified. R15 + R2 support an application study, not an exact replication. `docs/literature/r15_assessment.md`, D-31–D-33. Earlier pytest: 64 passed in 400.90 s; preserved evidence in `artifacts/literature_candidate_2022/`. |
| Publication audit cycles (2026-11-16) | **Engineering checks passed; submission NOT ready** | D-33–D-35; R15/R2 migration, bounded claims and CLI preservation guards. Independent audit: 36 bundles, 877,176 saved probabilities, 108 source-VAL thresholds, 216 aggregate metric rows, 120 summary rows and four matched-k contrasts. All 55 protected output hashes and the freeze remain unchanged. Shadow reporting byte-matches numeric manuscript files. Notebook 48/48 code cells, zero errors; full pytest 71 passed in 356.55 s; subsequent unit checks 50 passed. PDF eight pages, citations/macros resolved, visually checked. `artifacts/publication_audit/submission_status.json` explicitly remains false; scientific and author/release items below remain open. |
| Isolated-environment verification (2026-11-16) | **Passed for install, unit tests, saved inference and notebook** | New Windows/Python 3.10 venv from scoped research/audit snapshots; editable install and pip check pass. 50 unit tests pass in 0.91 s; complete 36-bundle score/108-threshold audit passes; all 48 notebook code cells pass using the venv's isolated kernel. Logs/reports in `artifacts/publication_audit/clean_*`, runtime in the latest audit cycle, dependency evidence in `dependency_snapshot.json`. Frozen lockfile and protected results unchanged. No fresh full-training or cross-OS reproducibility claim. |
| Scientific corrections (2026-11-16; D-36–D-38) | **Four findings addressed; corrected SHAP explicitly exploratory** | RF float32 input/threshold representation corrected with strict actual-classifier checks. Independently verified 24 arrays / 12,000 explanation rows; max residual 2.95e-8 at unchanged 1e-6 tolerance. Active correction analysis is label-free; legacy v1 remains blocked/archived. HP mapping verified against original PDF Table 1; R2 full 14-page review complete. Notebook 48/48 code cells executed using isolated kernel. Full `python -m pytest -q`: **77 passed in 383.43 s**, `artifacts/publication_corrections/pytest.log`. Corrected manuscript is eight pages, `manuscript/corrected/main.pdf`; non-SHAP empirical numbers and all 55 protected v1 files remain unchanged. `checks.json`, `access_check.json`, `submission_check.log` document scope and remaining author/release items. |

## Test suite

GitHub release preparation (2026-11-16, D-39): **77 passed in 583.33 s** using
`python -m pytest -q`; output preserved in `artifacts/github_release/pytest.log`.
Private repository: `Athraynmhd/phishing-url-generalization`. Credentials scan covers
candidate files and the branch history; no actionable hits (reserved parser fixture
userinfo is documented separately). Dataset/model/SHAP-array/full-text exclusions and
selected result inclusions were checked. Frozen v1 hashes remain valid; staged file
bytes match local files through `.gitattributes`. Evidence: `preflight.json` and
`validation.json` in `artifacts/github_release/`. Complete local artifacts are required
for notebook re-execution; the README states the clone's distribution scope.

`python -m pytest -q` → 61 passed (pre-freeze run, `artifacts/pytest_prefreeze.log`).

Audit 2026-11-16: `python -m pytest -q` → **61 passed in 393.19 s**;
new presentation guards separately: `python -m pytest -q tests/unit/test_notebook_safety.py`
→ **3 passed**. These cover rejection of mismatched/tampered saved predictions without label reads,
preservation of partial runs, and notebook restrictions on research execution/label-bearing reads.
`artifacts/notebook_audit/project_checks.json`: project files inventoried, 33 Python files syntax-checked,
39 Python/config/schema/notebook files validated, 8/8 raw-file hashes match the acquisition manifest.

Two-primary-paper editorial revision: `python -m pytest -q` → **64 passed in 346.91 s**
(includes the three notebook-safety guards). IEEE journal PDF and notebook were rebuilt;
freeze and all saved research/generated numeric outputs remain byte-identical. The literature
matrix retains R1–R5; an existing unquoted-comma issue in R5 was corrected and all rows verified
against the 22-field header. Neither a larger literature survey nor a new experiment was claimed.

## Remaining author/release items and scientific boundaries
1. Author/affiliation/email are explicitly deferred by the user. Venue, release URL/DOI and owner-selected code licence remain pending; do not invent them. Dataset redistribution rights remain unclear.
2. Current primary papers: **R15 Sánchez-Paniagua 2022 + R2 Rashid 2024** (D-33/D-37). Both satisfy the five-year maximum as of 2026-11-16; R15 is outside the preferred three-year window. Both full texts are reviewed. Two primary papers and complete review do not establish global novelty by themselves.
3. Corrected SHAP is **post-hoc/exploratory**, validated on the same saved cohorts; no independent new holdout is claimed. The original four failing outputs and frozen legacy loader deviation remain in the historical audit trail. Corrected analysis does not read individual TEST labels. Future confirmatory extensions require a new protocol and holdout.
4. HP numeric encoding is uniquely crossvalidated against all six primary-paper counts, but a verbatim author codebook and per-URL label correctness are not claimed. Historical R1 and algorithm sources remain internal provenance.

Latest audit evidence and the distinction between engineering success and submission readiness:
`docs/publication_readiness.md`, `docs/claim_evidence.csv`, `docs/protocol_v2_corrections.md`,
and `artifacts/publication_corrections/`. Latest full-suite output: **77 passed in 383.43 s**.
Earlier audit logs remain preserved under `artifacts/publication_audit/`; they describe prior
states and are not the current list of open findings.
