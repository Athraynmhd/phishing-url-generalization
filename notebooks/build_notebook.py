"""Builds notebooks/phishing_research_pipeline.ipynb - atomic steps, each: explanation -> code -> output."""
import sys
from pathlib import Path

import nbformat as nbf

C = []


def md(s):
    C.append(nbf.v4.new_markdown_cell(s.strip()))


def code(s):
    C.append(nbf.v4.new_code_cell(s.strip()))


def step(num, title, why, src, look=None):
    text = f"### Step {num}: {title}\n\n{why.strip()}"
    if look:
        text += f"\n\n> **What to check:** {look.strip()}"
    md(text)
    code(src)


md(r"""
# Phishing URL Detection Across Datasets
## Source-Only Feature Selection with Bidirectional Cross-Dataset Evaluation

**Study question.** If a lexical URL classifier is trained on one public phishing dataset and deployed on a
different one *without target data for fitting, feature selection or threshold calibration*, how much does it degrade, and does choosing features by
the **stability** of their importance across held-out domains (STABLE_PI) transfer better than choosing them by
**mean** importance (MEAN_PI) or using **all** 37 features (ALL)?

| | |
|---|---|
| **Sources** | A = EBBU-2017 · B = HISPAR–Phishstats (HP) |
| **Classifiers** | Random Forest · LightGBM (fixed hyper-parameters) |
| **Feature conditions** | ALL (37) · MEAN_PI · STABLE_PI (budget *k* chosen by nested CV) |
| **Evaluation cells** | A→A · A→B · B→B · B→A (same model & threshold for both cells of a source) |
| **Seeds** | 17 · 29 · 43 |

| RQ | Question |
|---|---|
| RQ1 | How far do RF and LightGBM drop on another source with disjoint domains? |
| RQ2 | Does STABLE_PI change transfer F1 vs MEAN_PI at the same *k*, and vs ALL? |
| RQ3 | Does a smaller feature set measurably reduce extraction/inference cost? |
| RQ4 | Which features do the models rely on, and how do attributions shift source → target? |

### How to read this notebook
* All logic lives in the tested package `src/phishresearch/`. Every cell below performs **one** step by
  calling one package function, then shows its output.
* This notebook **only loads saved artefacts**. It verifies the freeze before loading research results and refuses
  missing/partial outputs. It never starts acquisition, training, evaluation, or analysis during Run All.
* Individual TEST labels are not loaded here. Data checks use label-free metadata and saved aggregate diagnostics.
* Numbers are never typed by hand; the final section composes the answers from the artefacts.
""")

md(r"""
## Project positioning · two primary papers

The assignment permits **two primary papers** and retains its **3–5-year recency rule**.
Our primary pair is Sánchez-Paniagua et al. (2022,
[login-URL representativeness and classifiers](https://doi.org/10.1109/ACCESS.2022.3168681)) and Rashid et al. (2024,
[transfer/UDA](https://doi.org/10.1016/j.comnet.2024.110398)). Both fall within the five-year
window as of 16 November 2026; the 2022 paper is outside the preferred three-year window.
The 2022 study evaluates RF/LightGBM, but its best overall pipeline uses **TF-IDF/n-grams + LR**;
the 2024 paper studies **UDA**. This project evaluates RF/LightGBM rather than reproducing them.
Historical EBBU and algorithm provenance remains in the repository; the active bibliography
uses recent studies. This is an application and empirical benchmark (General Machine Learning).

**Gap tested:** with no target data for fitting, feature selection or threshold calibration,
does source-domain stability improve transfer over mean importance **at matched k**, and is
any compression worth its detection-cost trade-off? Target identities still inform the
shared-domain purge, so acquisition is not target-blind.

**Contributions:** an auditable domain-disjoint protocol; a controlled selector comparison
in both directions; and empirical transfer–cost evidence including negative results against ALL.
Neither cross-dataset testing nor feature stability is claimed as a new idea. Existing adjacent
work remains acknowledged; two primary papers do not prove global novelty. SHAP is secondary
and retains the validation warning displayed later.

This wording was clarified **after evaluation** without changing the frozen experiment.
See `docs/project_positioning.md` for evidence and submission checks. Paper recency does not
make the frozen EBBU/HP datasets contemporary. Complete full-text review is still pending for R2.
""")

md("## Part 0 · Environment")
step("0.0", "Check that the notebook runs in the project environment",
     "The frozen run used the exact package versions in `requirements.lock` (Python 3.10). A different kernel "
     "(e.g. Anaconda) may lack packages such as `shap` or produce different numbers, so we stop early with a clear message. "
     "In VS Code choose the kernel **Python 3.10 (phishresearch)** (top-right *Select Kernel*).",
     r"""
import sys, importlib, re, warnings
from pathlib import Path
_root = next((p for p in (Path.cwd().resolve(), *Path.cwd().resolve().parents)
              if (p / "requirements.lock").is_file() and (p / "configs/protocol.yaml").is_file()), None)
if _root is None:
    raise RuntimeError("Project root not found. Start Jupyter from this repository or its notebooks directory.")
_lock = dict(re.findall(r"^([A-Za-z0-9_.-]+)==([^\s;]+)", (_root / "requirements.lock").read_text(encoding="utf-8"), re.M))
_need = {"numpy": "numpy", "pandas": "pandas", "scikit-learn": "sklearn", "lightgbm": "lightgbm", "shap": "shap",
         "pyarrow": "pyarrow", "matplotlib": "matplotlib", "joblib": "joblib", "idna": "idna",
         "PyYAML": "yaml", "psutil": "psutil", "scipy": "scipy"}
_rows, _bad = [], []
for dist, mod in _need.items():
    try:
        with warnings.catch_warnings():          # silences tqdm's IProgress notice raised by `import shap`
            warnings.simplefilter("ignore")
            have = importlib.import_module(mod).__version__
    except ImportError:
        have = "MISSING"
    ok = have == _lock.get(dist)
    _rows.append((dist, _lock.get(dist), have, "ok" if ok else "MISMATCH")); _bad += [] if ok else [dist]
print(f"kernel python : {sys.version.split()[0]}  ({sys.executable})")
for r in _rows: print(f"  {r[0]:13s} lock {r[1]:9s} kernel {r[2]:9s} {r[3]}")
if _bad or sys.version_info[:2] != (3, 10):
    raise RuntimeError(f"Wrong kernel/environment ({', '.join(_bad) or 'python version'}). Select the kernel "
                       "'Python 3.10 (phishresearch)' or run: python -m pip install -r requirements.lock")
print("environment matches requirements.lock")
""")
step("0.1", "Locate the project and import the package",
     "The notebook may be started from the repository root or from `notebooks/`; we normalise the working directory "
     "so all relative paths in the configs resolve.",
     r"""
import os, sys, json, copy, tempfile, warnings
from pathlib import Path

ROOT = _root
os.chdir(ROOT); sys.path.insert(0, str(ROOT / "src"))

import numpy as np, pandas as pd
from IPython.display import display, Markdown
import phishresearch
from phishresearch import nbviz as viz
from phishresearch.common import Paths, GateError, load_yaml, read_json, effective_threads, environment_info

plt = viz.setup_plots()
pd.set_option("display.precision", 4, "display.max_colwidth", 90, "display.width", 200)
print(f"phishresearch {phishresearch.__version__} | root: {ROOT}")
""")
step("0.2", "Load the frozen protocol and dataset registry",
     "`protocol.yaml` holds every researcher decision (splits, k-candidates, hyper-parameters, bootstrap size); "
     "`datasets.yaml` pins each source to a Git commit and records the label-mapping evidence.",
     r"""
CFG = load_yaml("configs/protocol.yaml")
REGISTRY = load_yaml("configs/datasets.yaml")
P = Paths.from_config(CFG, ROOT)
from phishresearch.freeze import verify_freeze
FREEZE = verify_freeze(P.freeze, ROOT)
print("Frozen inputs verified:", FREEZE["freeze_hash"])

pd.Series({
    "protocol version": CFG["protocol_version"],
    "split seed / ratios": f"{CFG['splits']['seed']} / {CFG['splits']['ratios']}",
    "k candidates / q": f"{CFG['selection']['k_candidates']} / {CFG['selection']['q']}",
    "model seeds": CFG["models"]["seeds"],
    "RF": CFG["models"]["rf"], "LightGBM (main)": {k: CFG["models"]["lgbm"][k] for k in ("n_estimators", "learning_rate", "num_leaves")},
    "bootstrap replicates": CFG["statistics"]["bootstrap_replicates"],
    "source A commit": REGISTRY["sources"]["A"]["commit"][:12], "source B commit": REGISTRY["sources"]["B"]["commit"][:12],
}).to_frame("value")
""")
step("0.3", "Record the computing environment",
     "Latency and training-time numbers are only meaningful together with the hardware and library versions.",
     r"""
env = environment_info()
pd.Series({"python": env["python"], "platform": env["platform"], "CPU (logical/physical)": f"{env['cpu_count_logical']}/{env['cpu_count_physical']}",
           "RAM (GB)": env["ram_gb"], "threads used": effective_threads(CFG), **env["packages"]}).to_frame("value")
""")
step("0.4", "Define the saved-artefact guard",
     "Missing or partial outputs stop the notebook; existing and failed runs are preserved.",
     r"""
def stage(name: str, *artefacts: Path):
    viz.require_artifacts(*artefacts)
    print(f"[{name}] saved artefacts verified: " + ", ".join(str(p.relative_to(ROOT)) for p in artefacts))
""")

md("""## Part 1 · Data acquisition and data gate
Both sources are downloaded from GitHub at **pinned commits** into an immutable layout
`data/raw/<source>/<commit>/<file>` (temp file → validation → atomic rename; never overwritten).""")
step("1.1", "Load the acquisition manifest",
     "The acquisition has already run; no download is started by this notebook.",
     r"""
stage("acquire", P.raw / "manifest.json")
""")
step("1.2", "Inspect the manifest",
     "Each file has its commit, size and SHA256. Observed record counts are filled in by the audit.",
     "viz.manifest_table(P)",
     "`observed` equals `expected` for every source file (73,575 for A, 92,500 for B).")

md("""## Part 2 · Audit and domain-disjoint cohort
Order (PRD §9): **parse → within-source dedup → label-conflict quarantine → cross-source overlap audit →
symmetric purge** of every registered domain (ICANN Public Suffix List, offline snapshot) present in *both* sources.""")
step("2.1", "Load the saved audit",
     "Parsing is offline; malformed URLs are quarantined with a reason, never silently fixed.",
     r"""
stage("audit", P.processed / "records.parquet", P.artifacts / "audit.json")
AUDIT = read_json(P.artifacts / "audit.json")
""")
step("2.2", "Label-mapping evidence for source B",
     "Repository B has no codebook. Its own copy of EBBU is joined with source A on the raw URL; "
     "full agreement supports repository B's **1 = phishing** convention (HP-specific full-text confirmation remains pending, D-03/D-19).",
     r"""pd.Series(AUDIT["label_mapping_check"]).to_frame("value")""",
     "`agreement` must be 1.0, otherwise training is blocked by the pipeline.")
step("2.3", "Attrition by stage",
     "Counts after each stage; each removed URL is attributed to exactly one (first) reason.",
     "viz.attrition_table(AUDIT)")
step("2.4", "Re-count removal reasons directly from the record table",
     "Independent check using only dataset ID and removal reason; labels and raw URLs are not loaded.",
     r"""
RECORDS = pd.read_parquet(P.processed / "records.parquet", columns=["dataset_id", "reason"])
display(viz.reason_table(RECORDS))
print("reconciles:", {s: AUDIT["sources"][s]["reconciles"] for s in "AB"}, "| feasibility warnings:", AUDIT["warnings"] or "none")
""")
step("2.5", "Cross-source overlap and purge result",
     "Shared domains are removed from **both** sources so neither transfer direction is favoured.",
     r"""
cs = AUDIT["cross_source"]
display(pd.Series({"shared registered domains (purged)": cs["shared_groups"], "exact URL overlap": cs["exact_url_key_overlap_records"],
                   "domain intersection after purge": cs["cohort_group_intersection"],
                   "benign lost A / B": f"{viz.pct(AUDIT['sources']['A']['purge_loss_benign'])} / {viz.pct(AUDIT['sources']['B']['purge_loss_benign'])}",
                   "phishing lost A / B": f"{viz.pct(AUDIT['sources']['A']['purge_loss_phishing'])} / {viz.pct(AUDIT['sources']['B']['purge_loss_phishing'])}"}).to_frame("value"))
pd.Series(cs["top_shared_groups"]).head(10).to_frame("URLs removed (top shared domains)")
""",
     "intersection after purge is 0; the purge mostly removes benign URLs of popular platforms (YouTube, Wikipedia-like sites).")
step("2.6", "Largest domains that remain",
     "Very large groups dominate URL-weighted metrics; this is why CIs resample **domains**, not URLs.",
     "fig = viz.plot_top_groups(AUDIT); plt.show()")

md("""## Part 3 · Group-disjoint splits
Whole domains are assigned deterministically to FIT/VAL/TEST (≈60/20/20 %). FIT → selection and fitting,
VAL → thresholds only, TEST → read once, after the freeze.""")
step("3.1", "Load the saved split and feature metadata", "",
     r"""
from phishresearch.prepare import load_dev
stage("prepare", P.processed / "dev_features.parquet", P.artifacts / "prepare.json", P.processed / "splits.parquet")
PREP = read_json(P.artifacts / "prepare.json")
viz.partitions_table(PREP)
""", "class prevalence is nearly identical across FIT/VAL/TEST within a source.")
step("3.2", "Verify that partitions share no domain", "",
     r"""viz.check_group_disjoint(pd.read_parquet(P.processed / "splits.parquet", columns=["dataset_id", "group_id", "partition"]))""",
     "every cell is 0 (the helper raises if not).")
step("3.3", "Demonstrate the TEST loader policy",
     "The development loader refuses TEST; TEST labels live in a separate vault file (a procedural control).",
     r"""
try:
    load_dev(P, "A", "TEST")
except GateError as e:
    print("refused:", e)
""")

md("""## Part 4 · Lexical features
37 deterministic features computed from the URL string only (no network). Examples use reserved documentation domains.""")
DEMO = '["http://login.secure.example.com:8080/a_b/c-d?x=1&y=%41#top", "example.org/blog/post", "https://bücher.example/verify-account", "http://192.0.2.10/wallet/update.php?id=7", "HTTP://WWW.Example.CO.UK:80/Path", "javascript:alert(1)", "http://bad.example.test:99999/"]'
step("4.1", "Canonicalisation and grouping",
     "Scheme/host are lower-cased and IDNA-encoded; path, query and fragment keep their case; default ports are kept; "
     "invalid inputs are quarantined with a reason.",
     f"DEMO = {DEMO}\nviz.parse_demo(DEMO)")
step("4.2", "Feature values for valid examples", "",
     "viz.feature_demo(DEMO[:5])")
step("4.3", "Subset extraction equals projection of ALL",
     "A selected subset runs only the feature functions it needs (dependency pruning) yet yields identical values.",
     r"""
from phishresearch.features import extract_features
sub = ["F02", "F20", "F36"]
assert np.array_equal(extract_features(DEMO[:5], sub).to_numpy(), extract_features(DEMO[:5])[sub].to_numpy())
print("subset == projection of ALL for", sub)
""")

md("""## Part 5 · Source-only development
Per source and seed: 3 outer **domain** folds of FIT → permutation importance (PI) from outer-train only →
classifier on top-*k* → outer AP → smallest *k* within 0.01 AP of the best → PI on full FIT → final models →
thresholds locked on source VAL. TEST is never touched.""")
step("5.1", "Load development outputs for both sources", "No fitting is performed.",
     r"""
for s in "AB":
    stage(f"develop {s}", P.dev / s / "develop.json", P.dev / s / "outer_cv.csv")
DEV = {s: read_json(P.dev / s / "develop.json") for s in "AB"}
""")
step("5.2", "Chosen feature budget k", "Selected per source × classifier × selector × seed.",
     "viz.chosen_k_table(DEV)",
     "k is identical for both selectors here, so the matched-k contrast compares the rankings directly.")
step("5.3", "Nested-CV evidence behind the choice of k", "Mean ± sd of outer hold-out AP across the 3 outer folds (seed 17 … 43 pooled).",
     r"""fig = viz.plot_outer_cv(P, CFG["selection"]["k_candidates"]); plt.show()""")
step("5.4", "Permutation importance on full FIT",
     "Bars = mean PI over folds and seeds; green = feature in the top-12 with positive PI in all three domain folds in every seed.",
     r"""fig = viz.plot_pi(P, DEV, CFG["selection"]["q"]); plt.show()""")
step("5.5", "Selected feature subsets (seed 17)", "",
     "viz.selected_features_table(P)")
step("5.6", "Compute cost of development and nested-selection integrity", "",
     "viz.timing_table(DEV)",
     "the last row is True: the selector used for the final model is never the one evaluated in outer CV.")

md("""## Part 6 · Freeze
Before any TEST label is read, a manifest hashes configs, code (except presentation modules), PSL, records, splits,
feature files, the TEST vault and **all 36 model bundles of both directions**.""")
step("6.1", "Verify the existing freeze", "A notebook cannot approve or replace the research freeze.",
     r"""
stage("freeze", P.freeze)
FREEZE = verify_freeze(P.freeze, ROOT)
pd.Series({"freeze hash": FREEZE["freeze_hash"], "approved by": FREEZE["approved_by"], "created": FREEZE["created_at"],
           "git commit": FREEZE["git_commit"], "files hashed": len(FREEZE["body"]["file_hashes"]), "bundles": len(FREEZE["body"]["plan"]),
           "verification": "PASSED"}).to_frame("value")
""")
step("6.2", "Tamper demonstration",
     "A modified copy of the manifest is rejected (the real manifest is not touched).",
     r"""
bad = copy.deepcopy(FREEZE); bad["body"]["seeds"] = [1]
with tempfile.TemporaryDirectory() as td:
    fp = Path(td) / "freeze.json"; fp.write_text(json.dumps(bad), encoding="utf-8")
    try: verify_freeze(fp, ROOT)
    except GateError as e: print("rejected:", e)
""")

md("""## Part 7 · Final evaluation (one batch)
Every frozen bundle is scored on its own source TEST and on the other source's TEST with the **same** VAL-locked threshold.""")
step("7.1", "Verify and load the saved evaluation", "Prediction bytes are hashed without reading individual TEST labels.",
     r"""
import pyarrow.parquet as pq
EVAL = viz.verify_saved_evaluation(P, FREEZE)
MET = pd.DataFrame(EVAL["metrics"])
n_predictions = pq.ParquetFile(P.eval / "predictions.parquet").metadata.num_rows
print(f"{EVAL['run_id']}: {n_predictions:,} predictions, {len(MET)} metric rows, status = {EVAL['status']}")
""")
step("7.2", "Inspect the saved metric-recomputation check",
     "The analysis already recomputed every metric. Show its aggregate check after verifying prediction integrity; no labels are loaded here.",
     r"""
CHECK = read_json(P.analysis / "checks.json")["I06_recompute"]
if CHECK["status"] != "pass" or CHECK["rows_checked"] != len(MET) or CHECK["max_abs_diff"] != 0:
    raise GateError("Saved metric-recomputation check failed or is incomplete")
CHECK
""", "`max_abs_diff` is 0.0.")

md("""## Part 8 · Analysis
Cluster-bootstrap CIs (domains resampled), the four pre-specified contrasts, transfer drop, latency benchmark and SHAP.""")
step("8.1", "Load the completed analysis", "Incomplete runs are preserved. Recovery provenance is shown when saved SHAP outputs were reused.",
     r"""
stage("analyze", *(P.analysis / n for n in ("results_registry.json", "summary.csv", "config_ci.csv", "contrasts.json",
                                          "transfer_drop.csv", "benchmark.csv", "benchmark.json", "shap_summary.csv",
                                          "shap_compare.csv", "shap_mean_abs.csv")))
A = P.analysis
ANALYSIS = read_json(A / "results_registry.json")
if ANALYSIS["freeze_hash"] != FREEZE["freeze_hash"] or ANALYSIS["run_id"] != EVAL["run_id"]:
    raise GateError("Analysis belongs to another frozen evaluation")
recovery_path = A / ANALYSIS.get("recovery_provenance", "recovery.json")
if recovery_path.is_file():
    recovery = read_json(recovery_path)
    display(pd.Series({k: recovery[k] for k in ("source", "method", "shap_arrays_checked", "additivity_failures",
                                               "max_additivity_error", "individual_test_labels_read")}))
MAIN = viz.main_frame(A)
ANALYSIS["status"]
""")

md("### RQ1: internal vs cross-dataset performance")
step("8.2", "F1 with 95 % domain-cluster CI", "Primary threshold policy = F1-max on source VAL; mean over 3 seeds.",
     "viz.results_table(MAIN)")
step("8.3", "Visual comparison of the four evaluation cells", "",
     "fig = viz.plot_f1(MAIN); plt.show()")
step("8.4", "Transfer drop", "F1(source TEST) − F1(target TEST), same model and threshold; percentage points.",
     "viz.transfer_table(A)",
     "a negative drop means the model scored *higher* on the other source.")
step("8.5", "All metrics (primary threshold)", "Includes MCC, ROC-AUC, AP and the domain-balanced F1 (each domain weighted equally).",
     "viz.metric_table(A)")
step("8.6", "Operating point with ≤1 % FPR on source VAL",
     "The VAL-locked low-FPR threshold applied to TEST: recall and the *achieved* FPR (which may exceed 1 % on the target).",
     r"""viz.metric_table(A, "fpr_le")[["recall", "precision", "fpr", "f1"]]""")

md("### RQ2: does stability-based selection transfer better?")
step("8.7", "Primary contrasts: STABLE_PI − MEAN_PI at matched k (target TEST)",
     "Paired domain-cluster bootstrap (2,000 replicates); the same resampled domains are used for both arms and all seeds.",
     r"""
CON = read_json(A / "contrasts.json"); F1ABS = CFG["effects"]["f1_abs"]
PRIMARY = viz.contrast_frame(CON["primary"], F1ABS); PRIMARY
""")
step("8.8", "Forest plot of the primary contrasts", "", "fig = viz.plot_contrasts(PRIMARY, F1ABS); plt.show()")
step("8.9", "Secondary contrasts (cross-dataset)", "STABLE vs ALL, MEAN vs ALL, STABLE vs MEAN at the selected budget.",
     r"""SECONDARY = viz.contrast_frame([c for c in CON["secondary"] if c["source"] != c["target"]], F1ABS)
SECONDARY""")
step("8.10", "Forest plot of the secondary contrasts", "", "fig = viz.plot_contrasts(SECONDARY, F1ABS); plt.show()")

md("### RQ3: computational cost")
step("8.11", "Latency per URL by stage", "Median µs per URL; parse+features, predict-only and end-to-end; 1 and 4 inference threads.",
     "viz.cost_table(A)")
step("8.12", "End-to-end latency relative to ALL", "< 0.90 would be a ≥10 % reduction (the pre-set practical threshold).",
     "viz.relative_latency_table(A)")
step("8.13", "Where the time goes", "", "fig = viz.plot_latency(A); plt.show()")
step("8.14", "Model size, load and training time", "", "viz.size_table(A)")

md("### RQ4: what the models rely on (SHAP)")
step("8.15", "SHAP integrity and rank agreement",
     "TreeExplainer on the actual models (interventional, probability output). Spearman ρ and top-10 Jaccard compare "
     "source vs target rankings and, for ALL, rankings across seeds.",
     r"""
SS = pd.read_csv(A / "shap_summary.csv"); SC = pd.read_csv(A / "shap_compare.csv")
SHAP_A = A
print(f"max additivity error = {SS.additivity_max_abs_err.max():.1e}")
SHAP_FAILURES = SS[SS.additivity_max_abs_err > 1e-6]
if len(SHAP_FAILURES):
    display(Markdown(f"**SHAP validation warning:** {len(SHAP_FAILURES)}/{len(SS)} saved explanations exceed the existing 1e-6 "
                     "additivity tolerance. RQ4 is diagnostic; I09 is not passed for these real-data outputs. See D-24."))
    display(SHAP_FAILURES[["bundle_id", "cohort", "additivity_max_abs_err"]])

correction = viz.verify_shap_correction(P, FREEZE)
if correction is not None:
    SHAP_A, correction_manifest = correction
    SS = pd.read_csv(SHAP_A / "shap_summary.csv")
    SC = pd.read_csv(SHAP_A / "shap_compare.csv")
    SHAP_FAILURES = SS[SS.additivity_max_abs_err > 1e-6]
    display(Markdown(f"**Exploratory correction (D-36): {len(SS)}/{len(SS)} cohorts passed strict additivity.** "
                     f"Maximum residual {SS.additivity_max_abs_err.max():.2e}. The fitted models, thresholds and saved "
                     "classification results remain unchanged. The preceding warning belongs to preserved v1 outputs. "
                     "Plots and RQ4 summaries below use the corrected explanations; additivity alone does not establish faithfulness."))
    display(SS[["bundle_id", "cohort", "old_additivity_max_abs_err", "additivity_max_abs_err"]])
display(SC.round(3))
""")
step("8.16", "Top attributions, source vs target TEST (ALL, seed 17)", "", "fig = viz.plot_shap_bars(SHAP_A); plt.show()")
step("8.17", "Beeswarm: LightGBM trained on HP, explained on HP TEST", "",
     r"""fig = viz.shap_beeswarm(SHAP_A, "B-LGBM-ALL-k37-s17", "source"); plt.show()""")
step("8.18", "Beeswarm: the same model on EBBU TEST (target)", "Same model, same background; only the input distribution changes.",
     r"""fig = viz.shap_beeswarm(SHAP_A, "B-LGBM-ALL-k37-s17", "target"); plt.show()""")

md(r"""
### Validation boundary before interpreting the findings

Passing notebook execution and synthetic tests does **not** mean the study is submission-ready.
The independent audit (`python notebooks/audit_publication.py`) checks saved scores and aggregate
lineage without reading TEST labels. The exploratory correction is stored separately, with a
label-free analysis route and strict SHAP checks. The legacy v1 loader violation remains in
the historical record. HP numeric encoding is crossvalidated against all six published class
counts in Table 1; this is not an author-written codebook. The user-supplied 14-page R2 PDF
has now been reviewed completely, including Algorithm 1 and the stated limitations.
A new independent contemporary holdout remains unavailable. The corrected explanations
remain explicitly exploratory; the preserved v1 protocol deviation is not erased.
Author identities and venue are pending from the author. See `docs/publication_readiness.md`.
""")

md("## Part 9 · Answers to the research questions (composed from artefacts)")
step("9.1", "Compose the answers", "No number below is typed by hand.",
     r"""
def cell(s, t, m, c): return MAIN[(MAIN.source == s) & (MAIN.target == t) & (MAIN.model == m) & (MAIN.config == c)].iloc[0]
L = ["**RQ1: transfer (ALL features, VAL-locked threshold):**"]
for s, t in (("A", "B"), ("B", "A")):
    for m in ("RF", "LGBM"):
        a, b = cell(s, s, m, "ALL"), cell(s, t, m, "ALL")
        L.append(f"- {viz.SRC_NAME[s]}→{viz.SRC_NAME[t]} {m}: internal F1 {a.f1_mean:.3f} → cross {b.f1_mean:.3f} "
                 f"[{b.ci_low:.3f}, {b.ci_high:.3f}] (drop {100 * (a.f1_mean - b.f1_mean):+.1f} pp)")
L.append("\n**RQ2: STABLE_PI − MEAN_PI at matched k (target F1):**")
for _, r in PRIMARY.iterrows():
    L.append(f"- {r.cell} {r.model}: Δ = {r['ΔF1']:+.3f} [{r['CI low']:+.3f}, {r['CI high']:+.3f}] → {r.verdict}")
vs_all = SECONDARY[SECONDARY.contrast.str.startswith("STABLE_PI@budget − ALL")]
L.append("- versus ALL: " + "; ".join(f"{r.cell} {r.model} Δ = {r['ΔF1']:+.3f} ({r.verdict})" for _, r in vs_all.iterrows()))
rel = viz.relative_latency_table(A).reset_index(); rel = rel[rel.selector != "ALL"]
L.append(f"\n**RQ3: end-to-end latency relative to ALL:** single URL/1 thread {rel['1 thread · batch1'].min():.2f}–{rel['1 thread · batch1'].max():.2f}; "
         f"batch 1024/4 threads {rel['4 thread · batch1024'].min():.2f}–{rel['4 thread · batch1024'].max():.2f}.")
st = SC[SC.kind == "source_vs_target"]
L.append(f"\n**RQ4: SHAP ranking agreement source vs target:** Spearman ρ {st.spearman.min():.2f}–{st.spearman.max():.2f}, "
         f"top-10 Jaccard {st.top10_jaccard.min():.2f}–{st.top10_jaccard.max():.2f} (attribution shift is descriptive, not causal).")
if len(SHAP_FAILURES):
    L.append(f"**RQ4 validation limitation:** {len(SHAP_FAILURES)}/{len(SS)} saved explanations exceed the additivity tolerance; "
             "these attributions must not be described as fully validated.")
display(Markdown("\n".join(L)))
""")
md(r"""
### Limits of the claims
* A curated, domain-disjoint benchmark of two older public datasets; not a deployment, zero-day or temporal-robustness claim.
* Confidence intervals are conditional on the fixed split and the three seeds; no family-wise significance is claimed.
* Freeze + TEST loader are procedural controls, not cryptographic blinding. The freeze was signed by the agent on the
  author's explicit instruction (see `docs/decisions.md`, D-14).
* The frozen-v1 manuscript (`manuscript/main.pdf`) retains the original diagnostic SHAP figures.
  A separate corrected manuscript bundle uses its own generated/macros.tex and the exploratory SHAP outputs above.
""")

nb = nbf.v4.new_notebook()
nb["cells"] = C
nb["metadata"] = {"kernelspec": {"name": "phishresearch", "display_name": "Python 3.10 (phishresearch)", "language": "python"},
                  "language_info": {"name": "python"}}
out = Path(sys.argv[1])
out.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, out)
print("written", out, "cells:", len(C))
