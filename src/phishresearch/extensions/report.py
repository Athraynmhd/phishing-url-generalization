"""Manuscript macros/tables/figure for the exploratory extensions (D-40).

Writes generated/ext_macros.tex (\\@namedef lines only; \\res is defined by macros.tex),
tab_baseline.tex, tab_ext_contrasts.tex, tab_slices.tex, tab_examples.tex and fig_eda.pdf.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..reporting import COLORS, INK2, _style

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
