"""Manuscript macros/tables/figure for the exploratory extensions (D-40).

Writes generated/ext_macros.tex (\\@namedef lines only; \\res is defined by macros.tex),
tab_baseline.tex, tab_ext_contrasts.tex, tab_slices.tex, tab_examples.tex and fig_eda.pdf.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..models import MODELS
from ..reporting import COLORS, INK, INK2, _style

NAME = {"A": "EBBU", "B": "HP"}
CONFIGS = [("HTTPS-rule", "Rule: not HTTPS"), ("LR-ALL", "LogReg (37)"), ("RF-ALL", "RF (37) v1"),
           ("LGBM-ALL", "LightGBM (37) v1"), ("RF-noHTTPS", "RF w/o F30"), ("LGBM-noHTTPS", "LightGBM w/o F30")]


def _f(x, n=3):
    return "--" if x is None or pd.isna(x) else f"{x:.{n}f}"


def _tex(s: str) -> str:
    return s.replace("\\", "/").replace("_", "\\_").replace("%", "\\%").replace("&", "\\&").replace("#", "\\#") \
            .replace("~", "\\textasciitilde{}").replace("$", "\\$").replace("^", "\\^{}").replace("{", "").replace("}", "")


def write_ext_report(run: Path, manuscript_dir: Path) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _style(plt)
    out = Path(manuscript_dir) / "generated"
    out.mkdir(parents=True, exist_ok=True)
    m = pd.read_csv(run / "metrics.csv")
    res = json.loads((run / "results.json").read_text(encoding="utf-8"))
    con = pd.DataFrame(res["contrasts"])
    sl = pd.read_csv(run / "slices.csv")
    eda = pd.read_csv(run / "eda.csv")
    ex = pd.read_csv(run / "error_examples.csv")
    g = m.groupby(["source", "eval", "config"])[["f1", "ap", "auc", "recall", "fpr"]].mean()
    mac = {}

    def add(k, v):
        mac[k] = v

    # ------------------------------------------------------------ table: baselines + ablation
    rows = []
    for conf, label in CONFIGS:
        cells = []
        for s in ("A", "B"):
            cells += [_f(g.loc[(s, "source_val", conf), "f1"]), _f(g.loc[(s, "target_val", conf), "f1"]),
                      _f(g.loc[(s, "target_val", conf), "ap"])]
        rows.append(f"{label} & " + " & ".join(cells) + " \\\\")
        if conf == "HTTPS-rule":
            rows.append("\\midrule")
    (out / "tab_baseline.tex").write_text(
        "\\begin{tabular}{lcccccc}\n\\toprule\n& \\multicolumn{3}{c}{Source EBBU} & \\multicolumn{3}{c}{Source HP} \\\\\n"
        "\\cmidrule(lr){2-4}\\cmidrule(lr){5-7}\nModel & F1$_{\\mathrm{src}}$ & F1$_{\\rightarrow\\mathrm{HP}}$ & AP$_{\\rightarrow\\mathrm{HP}}$ "
        "& F1$_{\\mathrm{src}}$ & F1$_{\\rightarrow\\mathrm{EBBU}}$ & AP$_{\\rightarrow\\mathrm{EBBU}}$ \\\\\n\\midrule\n"
        + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n", encoding="utf-8")
    for s in ("A", "B"):
        for conf, key in (("HTTPS-rule", "Rule"), ("LR-ALL", "LR"), ("RF-ALL", "RF"), ("LGBM-ALL", "LGBM"),
                          ("RF-noHTTPS", "RFnoH"), ("LGBM-noHTTPS", "LGBMnoH")):
            add(f"x{key}Src{s}", _f(g.loc[(s, "source_val", conf), "f1"]))
            add(f"x{key}Tgt{s}", _f(g.loc[(s, "target_val", conf), "f1"]))
            add(f"x{key}TgtAP{s}", _f(g.loc[(s, "target_val", conf), "ap"]))
            add(f"x{key}TgtAUC{s}", _f(g.loc[(s, "target_val", conf), "auc"]))
            add(f"x{key}TgtRec{s}", _f(g.loc[(s, "target_val", conf), "recall"]))
            add(f"x{key}TgtFPR{s}", f"{100 * g.loc[(s, 'target_val', conf), 'fpr']:.1f}")

    # ------------------------------------------------------------ table: paired contrasts on target VAL
    crow = []
    for s in ("A", "B"):
        for a, b, label in (("RF-ALL", "LR-ALL", "RF $-$ LogReg"), ("LGBM-ALL", "LR-ALL", "LGBM $-$ LogReg"),
                            ("RF-ALL", "RF-noHTTPS", "RF $-$ no-F30"), ("LGBM-ALL", "LGBM-noHTTPS", "LGBM $-$ no-F30")):
            for ev in ("source_val", "target_val"):
                r = con[(con.source == s) & (con.a == a) & (con.b == b) & (con["eval"] == ev)].iloc[0]
                tag = f"x{'D' if ev == 'target_val' else 'Ds'}{a.split('-')[0]}{'LR' if b == 'LR-ALL' else 'noH'}{s}"
                add(tag, f"{r.delta:+.3f}")
                add(tag + "CI", f"[{r.ci_low:+.3f}, {r.ci_high:+.3f}]")
            rt = con[(con.source == s) & (con.a == a) & (con.b == b) & (con["eval"] == "target_val")].iloc[0]
            rs = con[(con.source == s) & (con.a == a) & (con.b == b) & (con["eval"] == "source_val")].iloc[0]
            crow.append(f"{NAME[s][0]}$\\rightarrow${NAME['B' if s == 'A' else 'A'][0]} & {label} & {rs.delta:+.3f} "
                        f"& {rt.delta:+.3f} [{rt.ci_low:+.3f}, {rt.ci_high:+.3f}] \\\\")
        crow.append("\\midrule")
    crow.pop()
    (out / "tab_ext_contrasts.tex").write_text(
        "\\begin{tabular}{llcc}\n\\toprule\nDir. & $a-b$ & $\\Delta$F1$_{\\mathrm{src}}$ & $\\Delta$F1$_{\\mathrm{tgt}}$ [95\\% CI] \\\\\n"
        "\\midrule\n" + "\n".join(crow) + "\n\\bottomrule\n\\end{tabular}\n", encoding="utf-8")

    # ------------------------------------------------------------ table: error slices (LightGBM v1, transfer)
    srow = []
    for s in ("A", "B"):
        t = sl[(sl.source == s) & (sl.model == "LGBM") & (sl["eval"] == "target_val") & sl.slice.isin(["https", "subdomains"])]
        for r in t.itertuples():
            val = r.value.replace(">=", "$\\geq$").replace("<=", "$\\leq$")
            srow.append(f"{NAME[s]}$\\rightarrow${NAME['B' if s == 'A' else 'A']} & {'HTTPS' if r.slice == 'https' else 'Subdomains'} "
                        f"& {val} & {r.n:,} & {100 * r.prevalence:.0f} "
                        f"& {_f(None if pd.isna(r.fpr) else 100 * r.fpr, 1)} & {_f(None if pd.isna(r.fnr) else 100 * r.fnr, 1)} \\\\")
            key = f"x{s}{'Https' if r.slice == 'https' else 'Sub'}{r.value.replace(' ', '').replace('>=', 'ge').replace('<=', 'le')}"
            add(key + "FPR", _f(100 * r.fpr, 1) if not pd.isna(r.fpr) else "--")
            add(key + "FNR", _f(100 * r.fnr, 1) if not pd.isna(r.fnr) else "--")
            add(key + "Share", f"{100 * r.share:.0f}")
        srow.append("\\midrule")
    srow.pop()
    (out / "tab_slices.tex").write_text(
        "\\begin{tabular}{lllrrrr}\n\\toprule\nDirection & Slice & Value & URLs & Phish (\\%) & FPR (\\%) & FNR (\\%) \\\\\n"
        "\\midrule\n" + "\n".join(srow) + "\n\\bottomrule\n\\end{tabular}\n", encoding="utf-8")

    # ------------------------------------------------------------ table: fixed-rule FP/FN examples
    erow = []
    for s in ("A", "B"):
        t = ex[(ex.source == s) & (ex.model == "LGBM") & (ex["eval"] == "target_val")]
        for kind in ("FP", "FN"):
            for r in t[t.kind == kind].head(2).itertuples():
                erow.append(f"{NAME[s]}$\\rightarrow${NAME['B' if s == 'A' else 'A']} & {kind} & {r.score:.3f} & "
                            f"\\texttt{{\\scriptsize {_tex(r.url[:40])}}} \\\\")
    (out / "tab_examples.tex").write_text(
        "\\begin{tabular}{llcl}\n\\toprule\nDirection & Error & Score & URL (defanged, truncated) \\\\\n\\midrule\n"
        + "\n".join(erow) + "\n\\bottomrule\n\\end{tabular}\n", encoding="utf-8")

    # ------------------------------------------------------------ EDA macros + figure
    e = eda.set_index("feature")
    for f in e.index:
        add(f"xd{f}A", f"{e.loc[f, 'A_d']:+.2f}")
        add(f"xd{f}B", f"{e.loc[f, 'B_d']:+.2f}")
    flips = e[~e.sign_agrees]
    add("xFlipList", ", ".join(f"\\texttt{{{_tex(e.loc[f, 'name'])}}}" for f in flips.index))
    add("xNFlip", str(len(flips)))
    add("xNEda", str(len(e)))
    for s in ("A", "B"):
        add(f"xHttpsBenign{s}", f"{100 * e.loc['F30', f'{s}_benign_mean']:.1f}")
        add(f"xHttpsPhish{s}", f"{100 * e.loc['F30', f'{s}_phish_mean']:.1f}")
    order = e.sort_values("B_d").index
    fig, ax = plt.subplots(figsize=(3.45, 2.7))
    y = range(len(order))
    for i, f in enumerate(order):
        ax.plot([e.loc[f, "A_d"], e.loc[f, "B_d"]], [i, i], color="#c9c8c3", lw=1, zorder=1)
    ax.scatter(e.loc[order, "A_d"], y, color=COLORS["ALL"], s=14, label="EBBU", zorder=2)
    ax.scatter(e.loc[order, "B_d"], y, color=COLORS["MEAN_PI"], s=14, marker="s", label="HP", zorder=2)
    ax.axvline(0, color=INK2, lw=0.6)
    ax.set_yticks(list(y))
    ax.set_yticklabels([f"{f} {e.loc[f, 'name']}" + (" *" if not e.loc[f, "sign_agrees"] else "") for f in order], fontsize=6)
    ax.set_xlabel("Cohen's d (phishing $-$ benign), source FIT")
    ax.legend(loc="lower right", fontsize=6)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(out / "fig_eda.pdf")
    fig.savefig(out / "fig_eda.png", dpi=200)
    plt.close(fig)

    lines = ["% AUTO-GENERATED by phishresearch.extensions.report from " + run.as_posix().split("/artifacts/")[-1]
             + " - do not edit", "\\makeatletter"]
    lines += [f"\\@namedef{{r@{k}}}{{{v}}}" for k, v in mac.items()]
    lines.append("\\makeatother")
    (out / "ext_macros.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    pd.DataFrame(list(mac.items()), columns=["key", "value"]).assign(provenance=str(run.name)).to_csv(
        out / "ext_provenance.csv", index=False)
    return mac


# ====================================================================== DA-GAFS (D-41)
def _pretty(combo: str) -> str:
    return combo.replace("LGBM", "LightGBM").replace("LR", "LogReg")


def write_dagafs_report(run: Path, manuscript_dir: Path, posthoc: Path) -> dict:
    """run = verified D-41 run, posthoc = verified D-42 run."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _style(plt)
    out = Path(manuscript_dir) / "generated"
    out.mkdir(parents=True, exist_ok=True)
    m = pd.read_csv(run / "metrics.csv")
    res = json.loads((run / "results.json").read_text(encoding="utf-8"))
    con = pd.DataFrame(res["contrasts"])
    ft = pd.read_csv(run / "features.csv").set_index("feature")
    sw = pd.read_csv(run / "sweep.csv")
    eg = pd.read_csv(run / "ensemble.csv").set_index("combo")
    g = m.groupby(["source", "eval", "config"])[["f1", "ap", "auc", "recall", "fpr", "k"]].mean()
    mac = {}
    k = int(res["k"])
    mac["gK"] = str(k)
    for R, key in (("I", "gKI"), ("IS", "gKIS"), ("ISD", "gKISD")):
        mac[key] = str(res["k_star"][R])
    conf = res["conflicts"]
    mac["gNConflict"] = str(len(conf))
    mac["gConflictList"] = ", ".join(f"\\texttt{{{_tex(ft.loc[f, 'name'])}}}" for f in conf) or "none"
    mac["gFeatList"] = ", ".join(f"\\texttt{{{_tex(ft.loc[f, 'name'])}}}" for f in res["features"]["ISD"])
    mac["gNfeat"] = str(len(ft))
    mac["gSignStabMin"] = (f"{min(ft.loc[f, c] for f in conf for c in ('sign_stability_A', 'sign_stability_B')):.2f}"
                           if conf else "--")
    for f in ft.index:
        mac[f"gr{f}A"], mac[f"gr{f}B"] = f"{ft.loc[f, 'r_A']:+.2f}", f"{ft.loc[f, 'r_B']:+.2f}"
        mac[f"gS{f}"], mac[f"gI{f}"] = f"{ft.loc[f, 'S']:.2f}", f"{ft.loc[f, 'I']:.2f}"
    mac["gNSone"] = str(int((ft.S == 1).sum()))
    add_us, meas = res["extract_us_additive"], res["extract_us_measured"]
    mac["gCostD"], mac["gCostAll"] = f"{add_us['DAGAFS']:.1f}", f"{add_us['ALL']:.1f}"
    mac["gMeasD"], mac["gMeasAll"] = f"{meas['DAGAFS']:.1f}", f"{meas['ALL']:.1f}"
    mac["gMeasRel"] = f"{meas['DAGAFS'] / meas['ALL']:.2f}"
    mac["gParse"] = f"{res['parse_us']:.1f}"
    ch = sw[sw.chosen].set_index("ranking")
    best = sw.groupby("ranking").g.max()
    for R, key in (("I", "I"), ("IS", "IS"), ("ISD", "D")):
        mac[f"gAPfit{key}"], mac[f"gAPbest{key}"] = f"{ch.loc[R, 'g']:.3f}", f"{best[R]:.3f}"
    mac["gAPfitAll"] = f"{sw[sw.k == len(ft)].g.iloc[0]:.3f}"
    top = ft.sort_values("rank_I").index[0]                         # most important pooled feature
    mac["gTopI"] = f"\\texttt{{{_tex(ft.loc[top, 'name'])}}}"
    excl = sw[(sw.ranking == "ISD") & ~sw.features.str.split().apply(lambda fs: top in fs)]
    mac["gAPnoTop"] = f"{excl.g.max():.3f}"
    gae = res["gae"]
    mac["gGAE"] = _pretty(gae)
    mac["gGAEsize"] = str(len(gae.split("+")))
    mac["gEnsBest"] = _pretty(eg.g.idxmax())
    mac["gEnsBestAP"], mac["gEnsGAEAP"] = f"{eg.g.max():.3f}", f"{eg.loc[gae, 'g']:.3f}"
    mac["gEnsThreeAP"] = f"{eg.loc['RF+LGBM+LR', 'g']:.3f}"
    mac["gEnsGAECost"], mac["gEnsThreeCost"] = f"{eg.loc[gae, 'cost_us']:.1f}", f"{eg.loc['RF+LGBM+LR', 'cost_us']:.1f}"

    # ------------------------------------------------------------ main table (each ranking at its own k*)
    pm = pd.read_csv(posthoc / "metrics.csv")
    pres = json.loads((posthoc / "results.json").read_text(encoding="utf-8"))
    pcon = pd.DataFrame(pres["contrasts"])
    meas2 = pres["extract_us_measured"]
    h = pm.groupby(["source", "eval", "config"])[["f1", "ap", "recall", "fpr", "k"]].mean()
    us = {"ALL": meas2["ALL"], "I": meas2["I"], "IS": meas2["IS"], "DAGAFS": meas2["DAGAFS"]}
    mac["hMeasAll"], mac["hMeasI"], mac["hMeasIS"], mac["hMeasD"] = (f"{us[x]:.0f}" for x in ("ALL", "I", "IS", "DAGAFS"))
    mac["hRelI"], mac["hRelD"] = f"{us['I'] / us['ALL']:.2f}", f"{us['DAGAFS'] / us['ALL']:.2f}"
    mac["hKI"], mac["hKIS"] = str(pres["own_k"]["I"]), str(pres["own_k"]["IS"])
    mac["hFeatI"] = ", ".join(f"\\texttt{{{_tex(ft.loc[f, 'name'])}}}" for f in pres["features"]["I"])
    rowsdef = [("ALL", "ALL v1 (source-only)", "ALL"), ("STABLE", "STABLE-PI v1 (source-only)", None),
               ("I@own", "XS-I, own $k^*$ (post-hoc)", "I"), ("IS@own", "XS-IS, own $k^*$ (post-hoc)", "IS"),
               ("DAGAFS@own", "DA-GAFS, $k^*$", "DAGAFS")]
    rows = []
    for model, mname in (("RF", "RF"), ("LGBM", "LightGBM")):
        for c, lab, cu in rowsdef:
            conf = f"{model}-{c}"
            kk = str(int(h.loc[("A", "target_val", conf), "k"]))
            if c == "STABLE":
                kk += "/" + str(int(h.loc[("B", "target_val", conf), "k"]))
            cells = [kk, f"{us[cu]:.0f}" if cu else "--"]
            for s in ("A", "B"):
                cells += [_f(h.loc[(s, "source_val", conf), "f1"]), _f(h.loc[(s, "target_val", conf), "f1"]),
                          _f(h.loc[(s, "target_val", conf), "ap"])]
                key = f"h{model[0]}{c.replace('@own', '').replace('STABLE', 'St').replace('DAGAFS', 'D')}"
                mac[f"{key}Tgt{s}"] = _f(h.loc[(s, "target_val", conf), "f1"])
                mac[f"{key}Src{s}"] = _f(h.loc[(s, "source_val", conf), "f1"])
                mac[f"{key}TgtAP{s}"] = _f(h.loc[(s, "target_val", conf), "ap"])
                mac[f"{key}TgtRec{s}"] = _f(h.loc[(s, "target_val", conf), "recall"])
            rows.append(f"{mname} {lab} & " + " & ".join(cells) + " \\\\")
        rows.append("\\midrule")
    for c, lab in (("GAE", f"C5 choice: {mac['gGAE']} DA-GAFS"), ("ENS3", "RF+LightGBM+LogReg DA-GAFS")):
        cells = [str(k), "--"]
        for s in ("A", "B"):
            cells += [_f(g.loc[(s, "source_val", c), "f1"]), _f(g.loc[(s, "target_val", c), "f1"]),
                      _f(g.loc[(s, "target_val", c), "ap"])]
        rows.append(f"{lab} & " + " & ".join(cells) + " \\\\")
    (out / "tab_dagafs.tex").write_text(
        "\\begin{tabular}{lcccccccc}\n\\toprule\n& & & \\multicolumn{3}{c}{Source EBBU} & \\multicolumn{3}{c}{Source HP} \\\\\n"
        "\\cmidrule(lr){4-6}\\cmidrule(lr){7-9}\nConfiguration & $k$ & $\\mu$s & F1$_{\\mathrm{src}}$ & F1$_{\\rightarrow\\mathrm{HP}}$ & "
        "AP$_{\\rightarrow\\mathrm{HP}}$ & F1$_{\\mathrm{src}}$ & F1$_{\\rightarrow\\mathrm{EBBU}}$ & AP$_{\\rightarrow\\mathrm{EBBU}}$ \\\\\n"
        "\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n", encoding="utf-8")
    for s in ("A", "B"):
        for c in g.loc[(s, "target_val")].index:
            key = c.replace("-", "").replace("LGBM", "L").replace("DAGAFS", "D").replace("STABLE", "St")
            mac[f"g{key}Tgt{s}"] = _f(g.loc[(s, "target_val", c), "f1"])
            mac[f"g{key}Src{s}"] = _f(g.loc[(s, "source_val", c), "f1"])
            mac[f"g{key}TgtAP{s}"] = _f(g.loc[(s, "target_val", c), "ap"])

    # ------------------------------------------------------------ contrasts table (target VAL)
    def pick(frame, s, a, b, ev="target_val"):
        return frame[(frame.source == s) & (frame.a == a) & (frame.b == b) & (frame["eval"] == ev)].iloc[0]

    spec = [(con, "DAGAFS", "ALL", "DA-GAFS $-$ ALL v1"), (con, "DAGAFS", "STABLE", "DA-GAFS $-$ STABLE-PI v1"),
            (con, "DAGAFS", "IS", "C2 gate, matched $k$"), (pcon, "I@own", "ALL", "XS-I $-$ ALL v1$^\\dagger$"),
            (pcon, "I@own", "STABLE", "XS-I $-$ STABLE-PI v1$^\\dagger$")]
    crow = []
    for model, mname in (("RF", "RF"), ("LGBM", "LightGBM")):
        for frame, a, b, lab in spec:
            cells = []
            for s in ("A", "B"):
                r = pick(frame, s, f"{model}-{a}", f"{model}-{b}")
                cells.append(f"{r.delta:+.3f} [{r.ci_low:+.3f}, {r.ci_high:+.3f}]")
                key = f"gD{model[0]}{a.replace('@own', '')[:2]}{b[:2]}{s}"
                mac[key], mac[key + "CI"] = f"{r.delta:+.3f}", f"[{r.ci_low:+.3f}, {r.ci_high:+.3f}]"
                mac[key + "src"] = f"{pick(frame, s, f'{model}-{a}', f'{model}-{b}', 'source_val').delta:+.3f}"
            crow.append(f"{mname} & {lab} & " + " & ".join(cells) + " \\\\")
        crow.append("\\midrule")
    for a, lab in (("GAE", f"C5 choice $-$ LightGBM DA-GAFS"), ("ENS3", "RF+LGBM+LR $-$ LightGBM DA-GAFS")):
        cells = []
        for s in ("A", "B"):
            r = pick(con, s, a, "LGBM-DAGAFS")
            cells.append(f"{r.delta:+.3f} [{r.ci_low:+.3f}, {r.ci_high:+.3f}]")
            mac[f"gD{a}{s}"], mac[f"gD{a}{s}CI"] = f"{r.delta:+.3f}", f"[{r.ci_low:+.3f}, {r.ci_high:+.3f}]"
        crow.append(f"Ensemble & {lab} & " + " & ".join(cells) + " \\\\")
    for model in MODELS:
        for s in ("A", "B"):
            r = pick(con, s, f"{model}-IS", f"{model}-I")
            mac[f"gD{model[0]}ISI{s}"] = f"{r.delta:+.3f}"
    (out / "tab_dagafs_contrasts.tex").write_text(
        "\\begin{tabular}{llcc}\n\\toprule\nModel & $a-b$ & EBBU$\\rightarrow$HP & HP$\\rightarrow$EBBU \\\\\n\\midrule\n"
        + "\n".join(crow) + "\n\\bottomrule\n\\end{tabular}\n", encoding="utf-8")

    # ------------------------------------------------------------ figure: component scores (C1-C3)
    o = ft[(ft.IS >= 0.05) | ft.conflict].sort_values(["G", "IS"], ascending=True)   # informative features only
    fig, ax = plt.subplots(figsize=(3.45, 3.0))
    yy = np.arange(len(o))
    cf = o.conflict.to_numpy(dtype=bool)
    ax.barh(yy, o.IS, color="#c9c8c3", height=0.7, label="$(I+S)/2$, no direction term")
    ax.scatter(o.G, yy, color=COLORS["STABLE_PI"], s=10, zorder=3, label="DA-GAFS score $G$")
    ax.scatter(o.IS[cf], yy[cf], color=COLORS["MEAN_PI"], marker="x", s=22, zorder=4, label="direction conflict ($D{=}0$)")
    for y_, f in zip(yy[cf], o.index[cf]):
        ax.text(o.loc[f, "IS"] + 0.02, y_, f"$r$={o.loc[f, 'r_A']:+.2f}/{o.loc[f, 'r_B']:+.2f}", va="center", fontsize=5, color=INK2)
    ax.set_yticks(yy)
    ax.set_yticklabels([f"{f} {o.loc[f, 'name']}" for f in o.index], fontsize=5)
    ax.set_xlabel("C1 importance + stability, gated by C2")
    ax.set_xlim(0, 1.0)
    ax.legend(loc="center right", fontsize=5.5)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(out / "fig_dagafs_scores.pdf")
    fig.savefig(out / "fig_dagafs_scores.png", dpi=200)
    plt.close(fig)

    # ------------------------------------------------------------ figure: Pareto front (C4)
    fig, ax = plt.subplots(figsize=(3.45, 2.3))
    style = {"I": ("#9a9893", "o", "XS-I"), "IS": (COLORS["ALL"], "s", "XS-IS"), "ISD": (COLORS["STABLE_PI"], "^", "DA-GAFS")}
    for R, (col, mk, lab) in style.items():
        p = sw[sw.ranking == R].sort_values("k")
        ax.plot(p.cost_us, p.g, color=col, lw=0.8, marker=mk, ms=2.5, label=lab)
        c = p[p.chosen].iloc[0]
        ax.scatter([c.cost_us], [c.g], s=45, facecolors="none", edgecolors=col, lw=1.1, zorder=4)
    fr = sw[sw.pareto].sort_values("cost_us")
    ax.step(fr.cost_us, fr.g, where="post", color=INK, lw=0.5, ls=":", label="Pareto front")
    ax.set_xlabel("parse + extraction cost ($\\mu$s per URL, additive)")
    ax.set_ylabel("cross-source AP on FIT")
    ax.set_ylim(max(sw.g.min(), sw.g.max() - 0.25), sw.g.max() + 0.01)
    ax.legend(loc="lower right", fontsize=5.5)
    fig.tight_layout()
    fig.savefig(out / "fig_pareto.pdf")
    fig.savefig(out / "fig_pareto.png", dpi=200)
    plt.close(fig)

    lines = ["% AUTO-GENERATED by phishresearch.extensions.report (DA-GAFS) from "
             + run.as_posix().split("/artifacts/")[-1] + " - do not edit", "\\makeatletter"]
    lines += [f"\\@namedef{{r@{key}}}{{{v}}}" for key, v in mac.items()]
    lines.append("\\makeatother")
    (out / "dagafs_macros.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    pd.DataFrame(list(mac.items()), columns=["key", "value"]).assign(provenance=str(run.name)).to_csv(
        out / "dagafs_provenance.csv", index=False)
    return mac
