"""Single CLI entry point:  python -m phishresearch.cli <command> ...

Every command returns nonzero on a gate failure and names the diagnostic artefact.
"""
from __future__ import annotations

import argparse
import copy
import shutil
import sys
from pathlib import Path

from .common import GateError, Paths, effective_threads, environment_info, load_yaml, sha256_file, write_json

ROOT = Path.cwd()


def _cfg(args) -> tuple[dict, Paths]:
    cfg = load_yaml(args.config)
    return cfg, Paths.from_config(cfg, ROOT)


def provenance(paths: Paths) -> dict:
    from .features import feature_schema_hash
    from .freeze import _git_commit
    from .urls import PARSER_VERSION, psl_hash
    lock = ROOT / "requirements.lock"
    return {"git_commit": _git_commit(ROOT), "parser_version": PARSER_VERSION, "psl_sha256": psl_hash(),
            "feature_schema_hash": feature_schema_hash(),
            "records_sha256": sha256_file(paths.processed / "records.parquet"),
            "splits_sha256": sha256_file(paths.processed / "splits.parquet"),
            "lockfile_sha256": sha256_file(lock) if lock.exists() else None,
            "environment": environment_info()}


def cmd_acquire(args):
    from .acquire import acquire
    cfg = load_yaml(args.config)
    acquire(Path(args.registry), Paths.from_config(cfg, ROOT).raw)


def cmd_audit(args):
    from .prepare import run_audit
    cfg, paths = _cfg(args)
    rep = run_audit(cfg, load_yaml(args.registry), paths)
    print(f"[audit] written {paths.artifacts / 'audit.json'}; warnings: {rep['warnings'] or 'none'}")


def cmd_prepare(args):
    from .prepare import run_prepare
    cfg, paths = _cfg(args)
    rep = run_prepare(cfg, paths)
    for k, v in rep["partitions"].items():
        print(f"[prepare] {k}: n={v['n']} groups={v['groups']} frac={v['frac']:.3f} prevalence={v['prevalence']:.3f}")


def cmd_develop(args):
    from .develop import develop_source
    from .prepare import load_dev
    cfg, paths = _cfg(args)
    out = paths.dev / args.source
    if (out / "develop.json").exists() and not args.overwrite:
        raise GateError(f"{out} already developed; pass --overwrite to redo (before freeze only)")
    if paths.freeze.exists():
        raise GateError("a freeze manifest exists; development after freeze requires protocol_v2")
    shutil.rmtree(out, ignore_errors=True)
    develop_source(args.source, load_dev(paths, args.source, "FIT"), load_dev(paths, args.source, "VAL"), cfg,
                   effective_threads(cfg), out, provenance=provenance(paths))


def cmd_freeze(args):
    from .freeze import build_freeze
    cfg, paths = _cfg(args)
    fr = build_freeze(Path(args.config), Path(args.registry), paths, args.approved_by, cfg)
    print(f"[freeze] {paths.freeze} hash={fr['freeze_hash']} files={len(fr['body']['file_hashes'])} "
          f"bundles={len(fr['body']['plan'])} approved_by={fr['approved_by']}")


def cmd_evaluate(args):
    from .evaluation import run_evaluation
    cfg, paths = _cfg(args)
    doc = run_evaluation(Path(args.freeze), paths)
    print(f"[evaluate] {len(doc['metrics'])} metric rows -> {paths.eval}")


def cmd_analyze(args):
    from .analysis import run_analysis
    cfg, paths = _cfg(args)
    run_analysis(Path(args.freeze), cfg, paths, skip_shap=args.skip_shap, skip_benchmark=args.skip_benchmark)


def cmd_report(args):
    from .reporting import run_report
    cfg, paths = _cfg(args)
    run_report(cfg, paths, ROOT / "manuscript")


def cmd_smoke(args):
    """Synthetic two-source end-to-end run. Output is NOT a scientific result."""
    from .analysis import run_analysis
    from .develop import develop_source
    from .evaluation import run_evaluation
    from .freeze import build_freeze
    from .prepare import load_dev, run_audit, run_prepare
    from .synthetic import make_sources
    cfg = copy.deepcopy(load_yaml(args.config))
    cfg["models"]["seeds"] = cfg["smoke"]["seeds"]
    cfg["statistics"]["bootstrap_replicates"] = 200
    cfg["benchmark"].update({"warmup": 2, "repeats": 5})
    cfg["explain"].update({"background": 20, "n_source": 40, "n_target": 40})
    root = ROOT / "artifacts" / "smoke"
    shutil.rmtree(root, ignore_errors=True)
    (root / "configs").mkdir(parents=True)
    cfgp = root / "configs" / "protocol.yaml"
    import yaml
    cfgp.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    paths = Paths.from_config(cfg, root)
    run_audit(cfg, None, paths, verify_labels=False, frames=make_sources())
    run_prepare(cfg, paths)
    for s in ("A", "B"):
        develop_source(s, load_dev(paths, s, "FIT"), load_dev(paths, s, "VAL"), cfg, 2, paths.dev / s,
                       n_estimators=cfg["smoke"]["n_estimators"])
    build_freeze(cfgp, None, paths, "smoke-synthetic (not a scientific result)", cfg)
    run_evaluation(paths.freeze, paths)
    run_analysis(paths.freeze, cfg, paths)
    write_json(root / "SYNTHETIC_NOT_A_RESULT.json", {"note": "synthetic smoke run; never cite"})
    print(f"[smoke] OK - synthetic pipeline completed in {root}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="phishresearch")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, *, registry=False, freeze=False):
        p = sub.add_parser(name)
        p.add_argument("--config", default="configs/protocol.yaml")
        if registry:
            p.add_argument("--registry", default="configs/datasets.yaml")
        if freeze:
            p.add_argument("--freeze", default="artifacts/freeze.json")
        p.set_defaults(fn=fn)
        return p

    add("acquire", cmd_acquire, registry=True)
    add("audit", cmd_audit, registry=True)
    add("prepare", cmd_prepare)
    d = add("develop", cmd_develop)
    d.add_argument("--source", choices=["A", "B"], required=True)
    d.add_argument("--overwrite", action="store_true")
    f = add("freeze", cmd_freeze, registry=True)
    f.add_argument("--approved-by", required=True, help="author/researcher signing the freeze review")
    add("evaluate", cmd_evaluate, freeze=True)
    a = add("analyze", cmd_analyze, freeze=True)
    a.add_argument("--skip-shap", action="store_true")
    a.add_argument("--skip-benchmark", action="store_true")
    add("report", cmd_report, freeze=True)
    s = add("smoke", cmd_smoke)
    s.add_argument("--synthetic", action="store_true", required=True)
    args = ap.parse_args(argv)
    try:
        args.fn(args)
    except GateError as e:
        print(f"GATE FAILURE [{args.cmd}]: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
