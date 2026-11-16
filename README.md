# phishresearch

Source-only feature selection for lightweight phishing URL detection with **bidirectional cross-dataset evaluation**
(EBBU-2017 ⇄ HISPAR–Phishstats), Random Forest vs LightGBM, three feature conditions (ALL, MEAN_PI, STABLE_PI).
Spesifikasi lengkap: [docs/PRD.md](docs/PRD.md). Keputusan yang menafsirkan PRD: [docs/decisions.md](docs/decisions.md).

## GitHub dan cakupan distribusi

Repository: [Athraynmhd/phishing-url-generalization](https://github.com/Athraynmhd/phishing-url-generalization)
(privat pada unggahan awal). Kode, konfigurasi, notebook beserta output tersimpan, sumber/PDF
naskah, tabel/grafik hasil agregat dan bukti audit terpilih disertakan. Lisensi kode belum
ditetapkan pemilik; tidak ada pemberian lisensi open source secara otomatis. Keterangan
lisensi komponen pihak ketiga tetap mengikuti berkas dan sumber masing-masing.

`.gitignore` mengecualikan dataset mentah/olahan, model, prediksi per-record, array input SHAP,
environment lokal, kredensial, salinan full text pihak ketiga, dan berkas sementara. Failed
runs tetap dipertahankan di workspace lokal. Manifest hash dan pointer yang disertakan adalah
rekam provenance; sebagian targetnya sengaja tidak didistribusikan.
`.gitattributes` mempertahankan byte/line ending berkas agar checkout tidak mengubah
hash kode yang dicatat dalam freeze.

Clone baru dapat membaca output notebook dan naskah serta menjalankan tes synthetic.
**Run All notebook dan audit eksperimen lengkap memerlukan artefak lokal asli yang cocok
dengan freeze**, termasuk data olahan, bundle model, prediksi, dan array SHAP. Instalasi
dependency saja tidak menyediakan berkas tersebut. Jangan menjalankan pipeline dari awal
untuk menimpa freeze yang disertakan. Untuk eksperimen baru, gunakan workspace terpisah
dan protokol/holdout baru; downloader dan commit sumber tercatat dalam konfigurasi serta
`data/raw/manifest.json`. Salinan paper diperoleh dari DOI/sumber pada `docs/sources.md`.

Instruksi tugas terbaru memperbolehkan dua paper utama dan tetap mensyaratkan usia 3–5 tahun:
**Sánchez-Paniagua 2022 dan Rashid 2024**. Sumber EBBU/algoritme historis disimpan sebagai
provenance internal; bibliography aktif mengikuti batas usia pada PRD v1.1.
Gap, kontribusi empiris, batas novelty, serta kepatuhan deliverable dijelaskan di
[docs/project_positioning.md](docs/project_positioning.md). R2 membahas UDA; eksperimen ini
memakai RF/LightGBM dalam setting source-only dan tidak mengklaim mereplikasi/mengungguli
UDA R2 atau metode terbaik TF-IDF/LR pada paper 2022. R4/R5 tetap pembanding terdekat.
Status kesiapan publikasi: [docs/publication_readiness.md](docs/publication_readiness.md).

Koreksi ilmiah D-36–D-38: seluruh 24 keluaran SHAP koreksi lulus additivity; jalur
analisis koreksi tidak membaca label TEST; encoding HP cocok dengan Table 1 pada seluruh
split asli; PDF lengkap R2 telah diperiksa. Naskah terkini untuk ditinjau:
[manuscript/corrected/main.pdf](manuscript/corrected/main.pdf) (8 halaman).
Koreksi SHAP dinyatakan **exploratory/post-hoc**; hasil/naskah v1 tetap dipertahankan.

```powershell
python -m phishresearch.cli analyze --exploratory-correction --jobs 4
python notebooks/verify_hp_encoding.py
python notebooks/check_corrections.py
```

Perintah koreksi membuat direktori run baru. Notebook memverifikasi hash sidecar sebelum
memakai SHAP koreksi; mode analyze legacy tetap ditolak. Review paper dan bukti encoding:
[docs/literature/r2_fulltext_review.md](docs/literature/r2_fulltext_review.md).

## Setup (Windows / VS Code)

```powershell
python -m pip install -r requirements-research.txt # scoped snapshot of installed research/notebook/test dependencies
python -m pip install -e . --no-deps
python -m pytest -q                               # unit, invariant, integration and notebook-safety checks
```

Snapshot ini telah diuji pada instalasi bersih Windows/Python 3.10: `pip check`, 50 tes unit,
seluruh 48 sel kode notebook, dan reproduksi probabilitas dari 36 model tersimpan lulus.
Ini bukan pelatihan ulang seluruh eksperimen dari nol. Untuk audit PDF/submission, pasang
dependency tambahan dengan `python -m pip install -r requirements-audit.txt`.

## Pipeline

Perintah berikut mendokumentasikan tahap riset. Pada workspace yang sudah memiliki freeze,
CLI menolak mutasi acquisition/audit/prepare/develop/freeze dan penimpaan evaluasi.
Jalur `analyze` real-data legacy diblok karena pelanggaran loader TEST; perbaikan ilmiah
memerlukan protokol baru atau artefak exploratory yang terpisah. Jangan memakai urutan
ini untuk menimpa eksperimen yang sudah selesai. `smoke` menyimpan run baru tanpa menghapus run lama.

```powershell
python -m phishresearch.cli acquire  --registry configs/datasets.yaml   # pinned commits, SHA256 manifest
python -m phishresearch.cli audit    --config configs/protocol.yaml     # parse, dedup, conflicts, symmetric domain purge
python -m phishresearch.cli prepare  --config configs/protocol.yaml     # group-disjoint 60/20/20 splits + 37 features
python -m phishresearch.cli smoke    --synthetic                        # synthetic end-to-end check (never a result)
python -m phishresearch.cli develop  --source A                          # nested k selection, final fits, VAL thresholds
python -m phishresearch.cli develop  --source B
python -m phishresearch.cli freeze   --approved-by "Name"               # hashes code, data, splits, bundles (both directions)
python -m phishresearch.cli evaluate --freeze artifacts/freeze.json     # reads TEST once, batch
python notebooks/audit_publication.py                                # audit saved science, no individual TEST labels
python -m phishresearch.cli report   --freeze artifacts/freeze.json     # manuscript/generated/*
cd manuscript; latexmk -pdf main.tex
```

Setiap command keluar dengan kode ≠0 bila gate gagal dan menyebut artefak diagnostiknya.

## Notebook

Pilih kernel **Python 3.10 (phishresearch)** lalu jalankan semua sel di
`notebooks/phishing_research_pipeline.ipynb`, atau gunakan:

```powershell
python notebooks/run_notebook.py
```

Notebook hanya memuat artefak tersimpan dan memverifikasi freeze; tidak melatih ulang atau
membuka label TEST individual. Runner menyimpan bukti eksekusi di
`artifacts/notebook_audit/execution.json` dan mempertahankan notebook gagal sebagai berkas terpisah.
Jika retry analisis D-21 kehilangan keluaran SHAP, `python notebooks/recover_analysis.py`
memulihkan hanya berkas yang hilang dari run terdahulu dengan freeze sama, setelah validasi;
benchmark aktif tetap dipertahankan. Peringatan additivity SHAP lama tetap ditampilkan (D-24).

## Layout

| Path | Isi |
|---|---|
| `src/phishresearch/` | `urls` (parser+PSL), `adapters`, `acquire`, `cohort` (audit), `splits`, `features`, `selection`, `models`, `thresholds`, `develop`, `freeze`, `evaluation`, `statistics`, `explain`, `benchmark`, `analysis`, `reporting`, `cli` |
| `configs/` | `protocol.yaml` (semua parameter protokol), `datasets.yaml` (registry + bukti mapping label) |
| `data/raw/` | file mentah immutable per commit (gitignored) + `manifest.json` |
| `artifacts/` | `audit.json`, `prepare.json`, `dev/`, `freeze.json`, `eval/`, `analysis/` |
| `manuscript/` | IEEE journal-format manuscript; angka hanya dari `generated/macros.tex` (`\res{key}`) |
| `docs/` | PRD, decisions, sources, risk register, literature gap matrix |

## Batas klaim

Hasil adalah benchmark terkurasi domain-disjoint dari dua dataset publik lama; bukan klaim deployment, zero-day,
atau robustness temporal. Loader TEST + freeze adalah kontrol prosedural, bukan evaluasi buta kriptografis.
Data mentah tidak diredistribusi (lisensi belum jelas); gunakan `acquire`.
