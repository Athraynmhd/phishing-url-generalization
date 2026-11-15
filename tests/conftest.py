import copy
import shutil
from pathlib import Path

import pytest

from phishresearch.common import Paths, load_yaml
from phishresearch.develop import develop_source
from phishresearch.prepare import load_dev, run_audit, run_prepare
from phishresearch.synthetic import make_sources

ROOT = Path(__file__).resolve().parents[1]
FAST_TREES = 10


def fast_cfg() -> dict:
    cfg = copy.deepcopy(load_yaml(ROOT / "configs" / "protocol.yaml"))
    cfg["models"]["seeds"] = [17]
    cfg["models"]["threads"] = 2
    cfg["statistics"]["bootstrap_replicates"] = 100
    return cfg


def build_workspace(root: Path, develop: bool = True, fit_hook=None) -> tuple[dict, Paths]:
    cfg = fast_cfg()
    (root / "configs").mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "configs" / "protocol.yaml", root / "configs" / "protocol.yaml")
    paths = Paths.from_config(cfg, root)
    run_audit(cfg, None, paths, verify_labels=False, frames=make_sources())
    run_prepare(cfg, paths)
    if develop:
        for s in ("A", "B"):
            develop_source(s, load_dev(paths, s, "FIT"), load_dev(paths, s, "VAL"), cfg, 2, paths.dev / s,
                           n_estimators=FAST_TREES, fit_hook=fit_hook if s == "A" else None, log=lambda *_: None)
    return cfg, paths


@pytest.fixture(scope="session")
def workspace(tmp_path_factory):
    return build_workspace(tmp_path_factory.mktemp("ws"))
