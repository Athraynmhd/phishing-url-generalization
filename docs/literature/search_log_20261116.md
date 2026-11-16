# Log pemeriksaan literatur audit publikasi

Tanggal: 16 November 2026. Ini penelusuran terarah untuk memverifikasi peran referensi,
bukan systematic review atau bukti bahwa suatu ide belum pernah diterbitkan.

| Kelompok kueri/sumber | Yang diperiksa | Hasil/batas |
|---|---|---|
| Exact title/DOI R15; repository Universidad de León | Metadata Crossref, PDF asli 12 halaman, §IV–VI dan Table 6 | RF/LightGBM tercakup, terbaik TF-IDF/n-gram + LR; date 2022-04-18 |
| Exact title/DOI R2; PDF/author/institutional repository | Publisher indexed sections; Crossref; OpenAlex locations; Minerva landing; public Elsevier API | Data/transfer/UDA roles supported; endpoint FULL HTTP 401, institutional bot-check; full PDF incomplete |
| R5 exact title/DOI dan PDF lokal | Front page, selection across datasets, classifier and cost sections | Prior stability/cost evidence; no claim project reproduces XGBoost |
| “Leakage and the reproducibility crisis in machine-learning-based science” | Full text author/publisher version at PMC10499856 | R16 supports general evaluation-validity rationale; not a replacement for original algorithm attribution |
| sklearn RF official version 1.7 documentation | Input conversion to float32 for inference | Motivates exploratory precision check; not evidence that all SHAP residuals are fixed |
| PWC exact-title queries R15/R5 | Catalog lookup | Titles absent; used primary publisher/institutional sources instead; absence is not exclusion evidence |

Stopping rule: peran kedua paper utama, studi stability terdekat, dan keterbatasan akses
sudah terdokumentasi. Tidak menambah baseline, mengganti data, atau mengubah hipotesis
berdasarkan metrik TEST yang sudah tersedia. Numeric HP codebook tidak ditemukan dari
daftar kode/dokumentasi repo author pada commit yang dipin (hanya README tersedia).
Tidak membuka, fetch, atau resolve URL sampel dari dataset.

Sumber primer:
https://doi.org/10.1109/ACCESS.2022.3168681
https://doi.org/10.1016/j.comnet.2024.110398
https://doi.org/10.1109/ACCESS.2026.3672690
https://pmc.ncbi.nlm.nih.gov/articles/PMC10499856/
https://scikit-learn.org/1.7/modules/generated/sklearn.ensemble.RandomForestClassifier.html
