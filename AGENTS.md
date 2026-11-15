# Agent rules for this repository

1. Read `docs/PRD.md` and `docs/decisions.md` before changing anything. New interpretations go into `docs/decisions.md` **before** TEST is opened.
2. Never read TEST labels outside `evaluation.py`. Development uses `prepare.load_dev` only (FIT/VAL).
3. `artifacts/freeze.json` exists ⇒ protocol v1 is frozen. Any change to a hashed module, config, split or bundle requires `protocol_version: 2` and a new holdout, or results are labelled exploratory.
4. Do not delete failed runs or edit numbers by hand; the manuscript takes numbers only from `manuscript/generated/macros.tex`.
5. Never open, fetch or resolve URLs from the datasets. Feature extraction is offline (test I07).
6. Run `python -m pytest -q` before declaring a milestone done; update `TASKS.md`.
7. Fixtures use reserved `*.example.test` / documentation domains only.
