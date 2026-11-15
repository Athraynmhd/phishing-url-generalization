# TASKS / evidence log

| Milestone | Status | Evidence |
|---|---|---|
| M0 Literature & data feasibility | **Done, with open items** | `docs/literature/gap_matrix.csv` (R1–R5; R4/R5 full text with page refs); data gate: 73,575 / 92,500 observed = expected, SHA256 in `data/raw/manifest.json`; label check 100% (`artifacts/audit.json`). Open: R1/R2 full text (D-19), campus 2-journal rule (D-20). |
| M1 Foundation | Done | package, configs, schemas, offline parser + PSL; U01–U03 pass |
| M2 Data protocol | Done | `audit.json` (reconciles = true, 0 cross-source group intersection), `prepare.json`; AC01–AC03 |
| M3 Models & selection | Done | `artifacts/dev/{A,B}`; I01, I03 pass; outer CV in `outer_cv.csv` |
| M4 Freeze | see `artifacts/freeze.json` | signed by agent on user instruction (D-14) |
| M5 Final evaluation | see `artifacts/eval/metrics.json` | single batch; I06 recompute check in `artifacts/analysis/checks.json` |
| M6 Analysis & manuscript | see `manuscript/` | macros/provenance in `manuscript/generated/` |

## Test suite
`python -m pytest -q` → 61 tests (unit 46, invariants 10... see pytest output); last full run recorded in git log.

## Open items for the author
1. Download R2 (CC BY, ScienceDirect) and R1 full text manually; confirm D-03 label mapping against R2 and finish gap-matrix UNKNOWN cells.
2. Decide on the campus requirement of two main journal articles (LightGBM phishing article) — D-20.
3. Fill author/affiliation placeholders in `manuscript/main.tex`; pick target venue.
