# Audit notebook — 16 November 2026

Notebook `notebooks/phishing_research_pipeline.ipynb` berhasil dieksekusi dari kernel baru
`phishresearch` (Python 3.10): seluruh 48 sel kode selesai tanpa error maupun keluaran stderr.
Notebook dengan error awal dipertahankan di
`artifacts/notebook_audit/phishing_research_pipeline_before.ipynb`.

Penyebab berhenti sebelumnya adalah analisis parsial tanpa `results_registry.json` dan keluaran
SHAP. Keluaran SHAP run sebelumnya diverifikasi terhadap freeze yang sama, lima berkas statistik
yang identik byte, dan 24 array NPZ (urutan fitur, residual terhadap prediksi model, ranking,
serta perbandingan ranking). Benchmark aktif tidak diganti dengan benchmark run pertama yang
terkontaminasi. Proses analisis sebelumnya juga menyelesaikan keluaran aktif selama audit;
hash seluruh keluaran SHAP sama dengan salinan yang diverifikasi. Registry asli dipertahankan.
Provenance pemulihan disimpan di `artifacts/analysis/recovery.json`.

Notebook sekarang hanya memuat hasil tersimpan. Freeze diverifikasi sebelum hasil dibuka;
file yang hilang menimbulkan pesan jelas dan tidak memulai ulang riset. Pembacaan tabel record
dan split hanya mengambil kolom metadata yang diperlukan. Integritas berkas prediksi diperiksa
melalui SHA256 tanpa membuka label individual, lalu diagnostik I06 agregat ditampilkan dari
`checks.json`. Lingkungan kernel, pencarian root proyek dan runner Windows juga diperbaiki.

`python notebooks/run_notebook.py` mengeksekusi notebook dari direktori `notebooks`, menyimpan
output di notebook asli bila berhasil, dan menyimpan salinan terpisah bila gagal.
Hash output evaluasi, analisis dan manuskrip dibandingkan sebelum/sesudah; freeze diverifikasi
kembali. Bukti terakhir: `artifacts/notebook_audit/execution.json`.

Pemeriksaan proyek mencakup inventaris file, sintaks seluruh Python di src/tests/notebooks,
validasi YAML/JSON schema/notebook, dan hash delapan berkas mentah tanpa memuat baris dataset.
Bukti: `artifacts/notebook_audit/project_checks.json`. Suite proyek lulus 61 tes; tiga tes baru
untuk keamanan notebook juga lulus secara terpisah. Tidak dilakukan fitting/evaluasi ulang
pada data riset nyata, dan modul/config/split/bundle yang masuk freeze tidak diubah.

Ada batas validasi ilmiah yang belum diselesaikan: 4/24 keluaran SHAP lama melampaui toleransi
additivity 1e-6 (maksimum sekitar 0,00333). Notebook menampilkannya sebagai peringatan dan
membatasi interpretasi RQ4; hasil tersebut tidak dinyatakan lulus I09. Kode beku
`analysis.py::_run_shap` juga mempunyai pembacaan label TEST langsung. Kode itu tidak
dijalankan oleh notebook yang diperbaiki. Perubahan kode ilmiah yang sudah dibekukan harus
mengikuti protokol v2/new holdout atau diberi label exploratory; lihat D-22–D-25.
