"""Execute every notebook cell and retain failures as separate audit artefacts.

Usage: python notebooks/run_notebook.py
"""
import argparse
import asyncio
import datetime as dt
import os
from pathlib import Path
import sys
import time

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from phishresearch.common import Paths, load_yaml, sha256_file, write_json
from phishresearch.freeze import verify_freeze


def main(kernel_name="phishresearch"):
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    paths = Paths.from_config(load_yaml(ROOT / "configs/protocol.yaml"), ROOT)
    freeze = verify_freeze(paths.freeze, ROOT)
    notebook = ROOT / "notebooks/phishing_research_pipeline.ipynb"
    audit = paths.artifacts / "notebook_audit"
    audit.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    protected = [f for folder in (paths.analysis, paths.eval, ROOT / "manuscript/generated")
                 for f in folder.rglob("*") if f.is_file()]
    before = {str(f.relative_to(ROOT)): sha256_file(f) for f in protected}
    nb = nbformat.read(notebook, as_version=4)
    nbformat.validate(nb)
    started = time.perf_counter()

    def progress(cell, cell_index, **kwargs):
        print(f"Executed cell {cell_index + 1}/{len(nb.cells)}", flush=True)

    client = NotebookClient(nb, timeout=180, kernel_name=kernel_name, allow_errors=False,
                            resources={"metadata": {"path": str(notebook.parent)}}, on_cell_executed=progress)
    try:
        client.execute(env={**os.environ, "IPYTHONDIR": str(audit / "ipython"),
                            "JUPYTER_RUNTIME_DIR": str(audit / "jupyter_runtime")})
        verify_freeze(paths.freeze, ROOT)
        after_files = [f for folder in (paths.analysis, paths.eval, ROOT / "manuscript/generated")
                       for f in folder.rglob("*") if f.is_file()]
        after = {str(f.relative_to(ROOT)): sha256_file(f) for f in after_files}
        if before != after:
            raise RuntimeError("Notebook changed saved research/manuscript artefacts")
    except Exception:
        nbformat.write(nb, audit / f"execution_failed_{stamp}.ipynb")
        raise
    nbformat.write(nb, notebook)
    evidence = {"status": "passed", "executed_at_utc": stamp, "kernel": kernel_name,
                "runner_python": sys.executable,
                "code_cells_executed": sum(c.cell_type == "code" for c in nb.cells),
                "error_outputs": sum(o.output_type == "error" for c in nb.cells for o in c.get("outputs", [])),
                "seconds": time.perf_counter() - started, "freeze_hash": freeze["freeze_hash"],
                "notebook_sha256": sha256_file(notebook), "protected_outputs_unchanged": True,
                "protected_output_sha256": before}
    write_json(audit / f"execution_{stamp}.json", evidence)
    write_json(audit / "execution.json", evidence)
    print(f"All {evidence['code_cells_executed']} code cells passed; freeze and saved research outputs unchanged.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", default="phishresearch", help="Registered Jupyter kernel to execute")
    args = parser.parse_args()
    main(kernel_name=args.kernel)
