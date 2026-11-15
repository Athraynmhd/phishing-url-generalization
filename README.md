# phishresearch

Source-only feature selection for lightweight phishing URL detection with **bidirectional cross-dataset evaluation**
(EBBU-2017 ⇄ HISPAR–Phishstats), Random Forest vs LightGBM, three feature conditions (ALL, MEAN_PI, STABLE_PI).
Spesifikasi lengkap: [docs/PRD.md](docs/PRD.md). Keputusan yang menafsirkan PRD: [docs/decisions.md](docs/decisions.md).

## Setup (Windows / VS Code)

```powershell
python -m pip install -r requirements.lock      # exact environment of the frozen run (Python 3.10)
python -m pip install -e . --no-deps
python -m pytest -q                               # 60 tests: U01-U04, I01-I09
```

## Pipeline

```powershell
python -m phishresearch.cli acquire  --registry configs/datasets.yaml   # pinned commits, SHA256 manifest
python -m phishresearch.cli audit    --config configs/protocol.yaml     # parse, dedup, conflicts, symmetric domain purge
python -m phishresearch.cli prepare  --config configs/protocol.yaml     # group-disjoint 60/20/20 splits + 37 features
python -m phishresearch.cli smoke    --synthetic                        # synthetic end-to-end check (never a result)
python -m phishresearch.cli develop  --source A                          # nested k selection, final fits, VAL thresholds
python -m phishresearch.cli develop  --source B
python -m phishresearch.cli freeze   --approved-by "Name"               # hashes code, data, splits, bundles (both directions)
python -m phishresearch.cli evaluate --freeze artifacts/freeze.json     # reads TEST once, batch
python -m phishresearch.cli analyze  --freeze artifacts/freeze.json     # CIs, contrasts, benchmark, SHAP
python -m phishresearch.cli report   --freeze artifacts/freeze.json     # manuscript/generated/*
cd manuscript; latexmk -pdf main.tex
```

Setiap command keluar dengan kode ≠0 bila gate gagal dan menyebut artefak diagnostiknya.

## Layout

| Path | Isi |
|---|---|
| `src/phishresearch/` | `urls` (parser+PSL), `adapters`, `acquire`, `cohort` (audit), `splits`, `features`, `selection`, `models`, `thresholds`, `develop`, `freeze`, `evaluation`, `statistics`, `explain`, `benchmark`, `analysis`, `reporting`, `cli` |
| `configs/` | `protocol.yaml` (semua parameter protokol), `datasets.yaml` (registry + bukti mapping label) |
| `data/raw/` | file mentah immutable per commit (gitignored) + `manifest.json` |
| `artifacts/` | `audit.json`, `prepare.json`, `dev/`, `freeze.json`, `eval/`, `analysis/` |
| `manuscript/` | IEEE conference paper; angka hanya dari `generated/macros.tex` (`\res{key}`) |
| `docs/` | PRD, decisions, sources, risk register, literature gap matrix |

## Batas klaim

Hasil adalah benchmark terkurasi domain-disjoint dari dua dataset publik lama; bukan klaim deployment, zero-day,
atau robustness temporal. Loader TEST + freeze adalah kontrol prosedural, bukan evaluasi buta kriptografis.
Data mentah tidak diredistribusi (lisensi belum jelas); gunakan `acquire`.
