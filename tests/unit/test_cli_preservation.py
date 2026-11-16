"""CLI mutations must preserve frozen science and failed-run evidence."""
from pathlib import Path

import pytest

from phishresearch import cli
from phishresearch.common import GateError, Paths, write_json


@pytest.mark.parametrize("command", ["acquire", "audit", "prepare", "develop", "freeze"])
def test_frozen_mutations_refused(tmp_path, monkeypatch, command):
    paths = Paths(tmp_path, tmp_path / "raw", tmp_path / "processed", tmp_path / "artifacts")
    write_json(paths.freeze, {"keep": "original"})
    monkeypatch.setattr(cli, "_cfg", lambda args: ({}, paths))
    monkeypatch.setattr(cli, "load_yaml", lambda path: {"paths": {"raw": "raw", "processed": "processed", "artifacts": "artifacts"}})
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    from types import SimpleNamespace
    args = SimpleNamespace(config="unused", registry="unused", source="A", approved_by="test")
    with pytest.raises(GateError, match="freeze exists"):
        getattr(cli, "cmd_" + command)(args)
    assert paths.freeze.read_text().find("original") >= 0


def test_partial_output_and_smoke_evidence_preserved(tmp_path, monkeypatch):
    folder = tmp_path / "artifacts/smoke"
    folder.mkdir(parents=True)
    failed = folder / "failure.json"
    failed.write_bytes(b"failed run remains")
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    new_root = cli._new_smoke_root()
    assert new_root != folder and new_root.is_relative_to(tmp_path / "artifacts/smoke_runs")
    assert failed.read_bytes() == b"failed run remains"
    with pytest.raises(GateError, match="preserve"):
        cli._empty_output(folder, "test")


def test_legacy_scientific_analysis_disabled():
    with pytest.raises(GateError, match="loader policy"):
        cli.cmd_analyze(None)
