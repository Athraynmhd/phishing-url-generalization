"""Presentation helpers for the notebook (tables and figures from saved artefacts only).
Presentation-only: never fits, thresholds or changes data; excluded from the freeze hash."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .common import GateError, Paths, read_json, sha256_file
from .features import FEATURE_NAMES, extract_features
from .reporting import COLORS, HATCH, INK2, _style
from .selection import PiResult, rank_features
from .urls import canonicalize_url

CELLS = [("A", "A", "EBBU internal"), ("A", "B", "EBBU → HP"), ("B", "B", "HP internal"), ("B", "A", "HP → EBBU")]
FAMS = ("ALL", "MEAN_PI@budget", "STABLE_PI@budget")
SRC_NAME = {"A": "EBBU", "B": "HP"}


def require_artifacts(*files: Path) -> None:
    """A presentation notebook must never rebuild missing research outputs."""
    missing = [str(p) for p in files if not Path(p).is_file()]
    if missing:
        raise GateError("Missing saved artefacts: " + ", ".join(missing)
                        + ". Preserve partial/failed runs; restore verified outputs before continuing.")


def verify_saved_evaluation(paths: Paths, freeze: dict) -> dict:
    """Check provenance and prediction bytes without loading individual TEST labels."""
    require_artifacts(paths.eval / "metrics.json", paths.eval / "predictions.parquet")
    evaluation = read_json(paths.eval / "metrics.json")
    if evaluation.get("status") != "completed" or evaluation.get("freeze_hash") != freeze["freeze_hash"]:
        raise GateError("Saved evaluation is incomplete or belongs to another freeze")
    if sha256_file(paths.eval / "predictions.parquet") != evaluation.get("predictions_sha256"):
        raise GateError("Saved prediction hash does not match metrics.json")
    return evaluation


def verify_shap_correction(paths: Paths, freeze: dict):
    """Load only a complete, hashed exploratory correction; never silently use partial runs."""
    pointer = paths.artifacts / "corrections/latest_shap.json"
    if not pointer.exists():
        return None
    latest = read_json(pointer)
    folder = paths.root / latest["artifact"]
    if sha256_file(folder / "manifest.json") != latest["manifest_sha256"]:
        raise GateError("SHAP correction manifest hash mismatch")
    doc = read_json(folder / "manifest.json")
    if doc["status"] != "passed" or doc["parent_freeze_hash"] != freeze["freeze_hash"]:
        raise GateError("Incomplete SHAP correction or different parent freeze")
    if not doc["all_additivity_passed"] or doc["max_additivity_residual"] > 1e-6:
        raise GateError("Corrected SHAP additivity did not pass")
    for name, digest in doc["output_sha256"].items():
        if sha256_file(folder / name) != digest:
            raise GateError(f"Corrected SHAP output changed: {name}")
    for name, digest in doc["code_sha256"].items():
        if sha256_file(paths.root / name) != digest:
            raise GateError(f"Correction code changed since execution: {name}")
    return folder, doc


def setup_plots():
    import matplotlib.pyplot as plt
    _style(plt)
    plt.rcParams.update({"font.size": 9, "figure.dpi": 110, "savefig.dpi": 110})
    return plt


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


# ------------------------------------------------------------------ data
def manifest_table(paths: Paths) -> pd.DataFrame:
    man = read_json(paths.raw / "manifest.json")["files"]
    return pd.DataFrame([{"file": k, "role": v["role"], "commit": v["commit"][:8], "MB": round(v["size"] / 2**20, 2),
                          "sha256": v["sha256"][:12] + "…", "expected": v["expected_records"],
                          "observed": v["observed_records"]} for k, v in man.items()]).set_index("file")


def attrition_table(audit: dict) -> pd.DataFrame:
    rows = []
    for s in "AB":
        for st, v in audit["sources"][s]["stages"].items():
            rows.append({"source": SRC_NAME[s], "stage": st.replace("after_", "after "), **v})
    return pd.DataFrame(rows).pivot_table(index="stage", columns="source", values=["n", "benign", "phishing"], sort=False)


def reason_table(records: pd.DataFrame) -> pd.DataFrame:
    return (records.groupby(["dataset_id", records.reason.fillna("in_cohort")]).size()
            .unstack(0).fillna(0).astype(int).rename(columns=SRC_NAME))


def plot_top_groups(audit: dict, n: int = 8):
    plt = setup_plots()
    fig, axes = plt.subplots(1, 2, figsize=(10, 2.8))
    for ax, s in zip(axes, "AB"):
        top = pd.Series(audit["sources"][s]["groups_cohort"]["top_groups"]).sort_values(ascending=False).head(n)[::-1]
        ax.barh(top.index, top.values, color=COLORS["ALL"])
        for y, v in enumerate(top.values):
            ax.text(v, y, f" {v:,}", va="center", fontsize=7)
        ax.set_title(f"Largest registered domains in cohort {SRC_NAME[s]}")
        ax.set_xlabel("URLs")
        ax.grid(axis="y", visible=False)
    fig.tight_layout()
    return fig


def partitions_table(prep: dict) -> pd.DataFrame:
    t = pd.DataFrame(prep["partitions"]).T
    t.index.name = "source/partition"
    return t.assign(n=t.n.astype(int), groups=t.groups.astype(int), frac=t.frac.map(pct), prevalence=t.prevalence.map(pct))


def check_group_disjoint(splits: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for s, d in splits.groupby("dataset_id"):
        g = d.groupby("partition").group_id.apply(set)
        for a, b in (("FIT", "VAL"), ("FIT", "TEST"), ("VAL", "TEST")):
            rows.append({"source": SRC_NAME[s], "pair": f"{a}∩{b}", "shared domains": len(g[a] & g[b])})
    out = pd.DataFrame(rows)
    assert out["shared domains"].eq(0).all(), "partitions share a domain"
    return out.pivot(index="pair", columns="source", values="shared domains")


# ------------------------------------------------------------------ features
def parse_demo(urls: list[str]) -> pd.DataFrame:
    rows = []
    for u in urls:
        p = canonicalize_url(u)
        rows.append({"url": u, "result": type(p).__name__, "url_key / reason": getattr(p, "url_key", getattr(p, "reason", "")),
                     "group (registered domain)": getattr(p, "group_key", "n/a")})
    return pd.DataFrame(rows).set_index("url")


def feature_demo(urls: list[str]) -> pd.DataFrame:
    X = extract_features(urls)
    X.columns = [f"{c} {FEATURE_NAMES[c]}" for c in X.columns]
    X.index = [u if len(u) < 38 else u[:35] + "…" for u in urls]
    return X.T


# ------------------------------------------------------------------ development
def chosen_k_table(dev: dict) -> pd.DataFrame:
    t = pd.DataFrame({(SRC_NAME[s], f"seed {seed}"): v["chosen_k"] for s in "AB" for seed, v in dev[s]["seeds"].items()})
    t.index.name = "model / selector"
    return t


def timing_table(dev: dict) -> pd.DataFrame:
    return pd.DataFrame({SRC_NAME[s]: {
        "PI computation (min)": dev[s]["timing"]["pi_seconds"] / 60,
        "outer-CV classifier fits (min)": dev[s]["timing"]["outer_fit_seconds"] / 60,
        "final fits (s)": sum(dev[s]["timing"]["final_fit_seconds"].values()),
        "full-FIT selector ≠ outer selectors": all(v["full_selector_hash"] not in v["outer_selector_hashes"] for v in dev[s]["seeds"].values()),
    } for s in "AB"}).round(2)


def plot_outer_cv(paths: Paths, k_candidates):
    plt = setup_plots()
    fig, axes = plt.subplots(1, 4, figsize=(13, 2.8))
    for ax, (s, m) in zip(axes, [(s, m) for s in "AB" for m in ("RF", "LGBM")]):
        cv = pd.read_csv(paths.dev / s / "outer_cv.csv")
        g = cv[cv.model == m].groupby(["selector", "k"]).ap.agg(["mean", "std"]).reset_index()
        for sel, d in g.groupby("selector"):
            ax.errorbar(d.k, d["mean"], yerr=d["std"], marker="o", ms=4, lw=1.5, capsize=2, color=COLORS[sel], label=sel)
        ax.set_title(f"{SRC_NAME[s]} · {m}")
        ax.set_xlabel("k")
        ax.set_xticks(k_candidates)
    axes[0].set_ylabel("outer hold-out AP")
    axes[0].legend(fontsize=7)
    fig.tight_layout()
    return fig


def pi_table(paths: Paths, dev: dict, source: str, q: int) -> pd.DataFrame:
    rows = []
    for seed in sorted(dev[source]["seeds"]):
        pj = read_json(paths.dev / source / "selectors" / f"pi_s{seed}_full.json")
        pi = PiResult(pj["feature_ids"], np.array(pj["pi_folds"]), np.array(pj["pi_repeats"]), pj["fit_ids_hash"], pj["n_rows"])
        _, st = rank_features(pi, "STABLE_PI", q)
        rows.append(pd.DataFrame({"mean_pi": st["mean_pi"], "votes": st["votes"]}))
    t = sum(rows) / len(rows)
    t.index = [f"{f} {FEATURE_NAMES[f]}" for f in t.index]
    return t


def plot_pi(paths: Paths, dev: dict, q: int):
    plt = setup_plots()
    fig, axes = plt.subplots(1, 2, figsize=(11, 7.5), sharey=True)
    for ax, s in zip(axes, "AB"):
        t = pi_table(paths, dev, s, q)
        ax.barh(t.index, t.mean_pi, color=[COLORS["STABLE_PI"] if v == 3 else COLORS["ALL"] for v in t.votes])
        ax.axvline(0, color=INK2, lw=.6)
        ax.set_title(f"{SRC_NAME[s]} FIT: mean PI (ΔAP), green = 3/3 folds in every seed")
        ax.grid(axis="y", visible=False)
    axes[0].invert_yaxis()
    fig.tight_layout()
    return fig


def selected_features_table(paths: Paths, seed: int = 17) -> pd.DataFrame:
    rows = []
    for s in "AB":
        for f in sorted((paths.dev / s / "bundles").glob(f"*-s{seed}.json")):
            m = read_json(f)
            if m["selector"] != "ALL":
                rows.append({"source": SRC_NAME[s], "model": m["model"], "selector": m["selector"], "k": m["k"],
                             "roles": "+".join(m["roles"]), "features": " ".join(m["feature_ids"])})
    return pd.DataFrame(rows).set_index(["source", "model", "selector", "k"])


# ------------------------------------------------------------------ results
def main_frame(analysis: Path) -> pd.DataFrame:
    summ = pd.read_csv(analysis / "summary.csv", dtype={"k_per_seed": str})
    ci = pd.read_csv(analysis / "config_ci.csv")
    return summ[summ.policy == "f1_max"].merge(ci, on=["source", "target", "model", "config"])


def results_table(main: pd.DataFrame) -> pd.DataFrame:
    v = main[main.config.isin(FAMS)].copy()
    v["cell"] = v.source.map(SRC_NAME) + " → " + v.target.map(SRC_NAME)
    v["F1 [95% CI]"] = v.f1_mean.map("{:.3f}".format) + " [" + v.ci_low.map("{:.3f}".format) + ", " + v.ci_high.map("{:.3f}".format) + "]"
    return v.pivot_table(index=["cell", "model"], columns="config", values="F1 [95% CI]", aggfunc="first", sort=False)[list(FAMS)]


def metric_table(analysis: Path, policy: str = "f1_max") -> pd.DataFrame:
    s = pd.read_csv(analysis / "summary.csv", dtype={"k_per_seed": str})
    s = s[(s.policy == policy) & s.config.isin(FAMS)]
    cols = ["k_per_seed", "f1_mean", "precision_mean", "recall_mean", "specificity_mean", "mcc_mean", "balanced_accuracy_mean",
            "roc_auc_mean", "average_precision_mean", "fpr_mean", "f1_domain_balanced_mean"]
    s = s.assign(cell=s.source.map(SRC_NAME) + " → " + s.target.map(SRC_NAME))
    return s.set_index(["cell", "model", "config"])[cols].rename(columns=lambda c: c.replace("_mean", "")).round(3)


def plot_f1(main: pd.DataFrame):
    plt = setup_plots()
    fig, axes = plt.subplots(1, 4, figsize=(13, 3.1), sharey=True)
    for ax, (s, t, ttl) in zip(axes, CELLS):
        for i, m in enumerate(("RF", "LGBM")):
            for j, conf in enumerate(FAMS):
                r = main[(main.source == s) & (main.target == t) & (main.model == m) & (main.config == conf)].iloc[0]
                fam = conf.split("@")[0]
                x = i + (j - 1) * .27
                ax.bar(x, r.f1_mean, .25, color=COLORS[fam], hatch=HATCH[fam], edgecolor="white",
                       label=fam if (i == 0 and ax is axes[0]) else None)
                ax.errorbar(x, r.f1_mean, [[r.f1_mean - r.ci_low], [r.ci_high - r.f1_mean]], fmt="none", ecolor="k", lw=.8, capsize=2)
                ax.text(x, .03, f"{r.f1_mean:.2f}", rotation=90, ha="center", va="bottom", fontsize=6.5, color="white")
        ax.set_title(ttl)
        ax.set_xticks([0, 1], ["RF", "LightGBM"])
        ax.set_ylim(0, 1)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("F1 phishing (TEST)")
    fig.legend(loc="upper center", ncol=3, bbox_to_anchor=(.5, 1.07))
    fig.tight_layout()
    return fig


def transfer_table(analysis: Path) -> pd.DataFrame:
    td = pd.read_csv(analysis / "transfer_drop.csv")
    t = td.groupby(["source", "model", "config"]).agg(f1_source=("f1_source_test", "mean"), f1_target=("f1_target_test", "mean"),
                                                      drop_pp=("drop_pp", "mean"), drop_sd=("drop_pp", "std"))
    t.index = t.index.set_levels([t.index.levels[0].map(lambda s: f"{SRC_NAME[s]} → {SRC_NAME['B' if s == 'A' else 'A']}"),
                                  t.index.levels[1], t.index.levels[2]])
    return t.round(3)


def contrast_frame(items: list, f1_abs: float) -> pd.DataFrame:
    return pd.DataFrame([{"cell": f"{SRC_NAME[c['source']]} → {SRC_NAME[c['target']]}", "model": c["model"],
                          "contrast": f"{c['a']} − {c['b']}", "k (a | b)": f"{c['k_a']} | {c['k_b']}",
                          "ΔF1": round(c["delta"], 4), "CI low": round(c["ci_low"], 4), "CI high": round(c["ci_high"], 4),
                          "per seed": [round(x, 4) for x in c["per_seed_delta"]], "same model": all(c["identical_bundle"]),
                          f"|Δ| ≥ {f1_abs}": abs(c["delta"]) >= f1_abs,
                          "verdict": "CI > 0" if c["ci_low"] > 0 else "CI < 0" if c["ci_high"] < 0 else "CI includes 0"}
                         for c in items])


def plot_contrasts(frame: pd.DataFrame, f1_abs: float):
    plt = setup_plots()
    fig, ax = plt.subplots(figsize=(7, 0.55 * len(frame) + 0.9))
    for i, r in frame.reset_index(drop=True).iterrows():
        ax.errorbar(r["ΔF1"], i, xerr=[[r["ΔF1"] - r["CI low"]], [r["CI high"] - r["ΔF1"]]], fmt="o", color=COLORS["STABLE_PI"], capsize=3)
        ax.text(r["CI high"], i, f"  {r['ΔF1']:+.3f}", va="center", fontsize=7)
    ax.axvline(0, color=INK2, lw=.8)
    ax.axvspan(-f1_abs, f1_abs, color="#eeeeea", zorder=0, label=f"|Δ| < {f1_abs} (pre-set)")
    ax.set_yticks(range(len(frame)), frame.cell + " · " + frame.model + " · " + frame.contrast.str.replace("@budget", "").str.replace("@matched", ""))
    ax.invert_yaxis()
    ax.set_xlabel("Δ F1 on target TEST, 95% paired domain-cluster bootstrap CI")
    ax.legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    return fig


def cost_table(analysis: Path) -> pd.DataFrame:
    b = pd.read_csv(analysis / "benchmark.csv")
    t = b.pivot_table(index=["source", "model", "selector", "k"], columns=["threads", "batch", "stage"], values="median_us_per_url")
    t.columns = [f"t{a}/{bb}/{c}" for a, bb, c in t.columns]
    return t.round(1)


def relative_latency_table(analysis: Path) -> pd.DataFrame:
    b = pd.read_csv(analysis / "benchmark.csv")
    t = b[b.stage == "end_to_end"].pivot_table(index=["source", "model", "selector", "k"], columns=["threads", "batch"], values="rel_to_all")
    t.columns = [f"{a} thread · {bb}" for a, bb in t.columns]
    return t.round(3)


def plot_latency(analysis: Path):
    plt = setup_plots()
    b = pd.read_csv(analysis / "benchmark.csv")
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.6))
    for ax, (th, bs, ttl) in zip(axes, ((1, "batch1", "single URL, 1 thread"), (4, "batch1024", "batch 1024, 4 threads"))):
        d = b[(b.stage.isin(["extract", "predict"])) & (b.threads == th) & (b.batch == bs)]
        p = d.pivot_table(index=["source", "model", "selector", "k"], columns="stage", values="median_us_per_url").reset_index()
        lab = p.source + "-" + p.model + " " + p.selector + " k=" + p.k.astype(str)
        y = np.arange(len(p))
        ax.barh(y, p.extract, color=COLORS["ALL"], label="parse + features")
        ax.barh(y, p.predict, left=p.extract, color=COLORS["MEAN_PI"], label="predict")
        ax.set_yticks(y, lab, fontsize=7)
        ax.invert_yaxis()
        ax.set_title(ttl)
        ax.set_xlabel("median µs per URL")
        ax.grid(axis="y", visible=False)
    axes[0].legend(fontsize=7)
    fig.tight_layout()
    return fig


def size_table(analysis: Path) -> pd.DataFrame:
    bj = read_json(analysis / "benchmark.json")
    return pd.DataFrame([{"bundle": b["bundle_id"], "features": b["n_features"], "model MB": b["model_file_bytes"] / 2**20,
                          "load ms": b["load_ms"], "fit s": b["fit_seconds"], "RSS Δ MB": b["rss_delta_mb"]}
                         for b in bj["bundles"]]).set_index("bundle").round(2)


def plot_shap_bars(analysis: Path, top: int = 8):
    plt = setup_plots()
    rk = pd.read_csv(analysis / "shap_mean_abs.csv", index_col=0)
    cols = sorted(c for c in rk.columns if "-ALL-" in c and c.endswith("s17|source"))
    fig, axes = plt.subplots(1, len(cols), figsize=(14, 3))
    for ax, c in zip(np.atleast_1d(axes), cols):
        t = c.replace("|source", "|target")
        idx = rk[c].sort_values(ascending=False).index[:top]
        y = np.arange(len(idx))
        ax.barh(y - .18, rk.loc[idx, c], .34, color=COLORS["ALL"], label="source TEST")
        ax.barh(y + .18, rk.loc[idx, t], .34, color=COLORS["MEAN_PI"], label="target TEST")
        ax.set_yticks(y, [f"{f} {FEATURE_NAMES[f]}" for f in idx], fontsize=7)
        ax.invert_yaxis()
        ax.set_title(c.split("|")[0].replace("-k37-s17", ""), fontsize=8)
        ax.set_xlabel("mean |SHAP| (probability)")
        ax.grid(axis="y", visible=False)
    np.atleast_1d(axes)[0].legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    return fig


def shap_beeswarm(analysis: Path, bundle: str, cohort: str = "source", max_display: int = 10):
    import shap
    plt = setup_plots()
    z = np.load(analysis / "shap" / f"{bundle}_{cohort}.npz", allow_pickle=True)
    names = [f"{i} {FEATURE_NAMES[i]}" for i in z["ids"]]
    plt.figure()
    shap.summary_plot(z["shap"], z["X"], feature_names=names, max_display=max_display, show=False, plot_size=(7, 3.4))
    plt.title(f"{bundle}, {cohort} TEST", fontsize=9)
    plt.tight_layout()
    return plt.gcf()
