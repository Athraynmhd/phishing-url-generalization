# Audit kesiapan publikasi — 16 November 2026

**Putusan: hasil utama konsisten secara teknis, tetapi belum submission-ready.**
Audit tidak memberikan jaminan penerimaan jurnal. Tidak ada persentase kesiapan atau skor
novelty yang dibuat tanpa kriteria. Identitas penulis/afiliasi dan venue sengaja tetap pending
sesuai jawaban pengguna; bagian tersebut tidak menghambat audit teknis.

**Pembaruan koreksi D-36–D-38:** keempat temuan audit telah ditindaklanjuti dengan bukti.
Seluruh 24 keluaran SHAP koreksi lolos strict additivity; analisis koreksi aktif label-free;
encoding HP crossvalidated terhadap Table 1; PDF R2 yang diberikan pengguna telah dibaca
lengkap. RQ4 koreksi tetap **exploratory/post-hoc**. Deviasi loader historis v1 tetap
diungkapkan dan tidak dijadikan seolah protokol v1 selalu patuh. Naskah koreksi terpisah:
`manuscript/corrected/main.pdf` (8 halaman). Identitas/venue dan rilis tetap belum lengkap.

## Siklus pemeriksaan

1. **Baseline dan diagnosis:** simpan hash keluaran beku dan salinan naskah sebelum revisi;
   periksa konflik peran paper, batas angka, dan jalur TEST. Bukti: `artifacts/publication_audit/baseline.json`.
2. **Perbaikan:** migrasikan naskah/notebook ke R15 (2022) + R2 (2024), batasi bahasa
   superiority/equivalence/causality, perbaiki guard CLI, pertahankan failed runs, serta
   pisahkan hasil diagnostik SHAP yang exploratory. Bibliography aktif 2022–2026;
   rujukan historis tetap dapat diaudit di `historical_references.bib`.
3. **Verifikasi ulang:** jalankan audit model/artefak independen, regenerasikan tabel/macro
   ke direktori bayangan, jalankan seluruh notebook/pytest, kompilasi PDF, lalu cek gate
   submission. Tiap cycle audit memiliki JSON tersendiri; kegagalan tidak dihapus.
4. **Koreksi exploratory:** jalankan namespace koreksi pada matriks cohort lama, verifikasi
   ulang seluruh array terhadap probabilitas model asli, lengkapi literatur dan evidence
   mapping, lalu buat naskah koreksi dengan macro hasil yang diregenerasi otomatis. Seluruh
   angka klasifikasi, model dan 55 artefak numerik v1 tetap identik. Pemeriksaan independen:
   `notebooks/check_corrections.py`, `artifacts/publication_corrections/checks.json`.

## Bukti yang sudah kokoh

* Delapan berkas raw cocok SHA256 dengan manifest. Attrition konsisten, identitas record
  unik, dan domain tidak melintasi partisi atau kedua sumber pada cohort hasil purge.
* Audit independen mencocokkan **36 bundle**, **877.176 probabilitas tersimpan**,
  **108 threshold VAL**, **216 baris metrik agregat**, **120 baris summary**, serta
  empat kontras matched-k. Selisih maksimum probabilitas pada cycle awal hanya
  `4.44e-16`, di bawah toleransi audit `1e-12`.
* Feature extraction pada sampel FIT direkonstruksi offline dan cocok; provenance
  nested selector berbeda dari full-FIT. Audit tidak melatih ulang model, membuka URL
  dataset, atau membaca kolom label TEST individual.
* AP/AUC dan replikasi bootstrap dari label **tidak dihitung ulang oleh audit ini**;
  keduanya bergantung pada artefak evaluator/I06 dan implementasi beku yang diuji.
  Ini batas audit, bukan klaim verifikasi baru yang tidak dilakukan.
* Regenerasi laporan ke folder bayangan menghasilkan tabel, macro, feature legend,
  dan provenance CSV identik byte dengan berkas asli. Semua angka empiris naskah
  tetap melalui `manuscript/generated/macros.tex`; tidak diketik ulang.
* Guard CLI mencegah mutasi input sesudah freeze dan penimpaan output evaluasi;
  run sintetis berikutnya memakai direktori baru. Jalur `analyze` real-data legacy
  diblok, karena belum patuh aturan loader TEST. Tes guard memeriksa penolakannya.

## Status temuan ilmiah dan kelengkapan submission

| Temuan | Dampak | Yang diperlukan |
|---|---|---|
| Empat keluaran SHAP v1 gagal additivity | **Dikoreksi secara exploratory**: 24/24 array, 12.000 baris, diverifikasi independen; residual maksimum sekitar 2,95e-8 | Batas 1e-6 tetap. Model, nilai SHAP lama dan baseline tidak ditambal; additivity bukan bukti faithfulness lengkap |
| `analysis.py` v1 membaca label di luar evaluator | **Jalur koreksi aktif label-free**; CLI legacy tetap diblok, cohort baru hanya dapat dipersiapkan evaluator | Catatan penyimpangan historis v1 dipertahankan. Koreksi post-hoc tidak membuat holdout baru atau blinding retroaktif |
| Encoding HP hanya didukung bukti EBBU tidak langsung | **Crossvalidated langsung** dengan keenam class counts Table 1 R2 pada tiga original splits; hanya 0 benign / 1 phishing cocok | Ini derived evidence terhadap paper, bukan author-written numeric codebook atau verifikasi label per URL |
| Review full text R2 belum lengkap | **Selesai**: PDF penerbit 14 halaman dari pengguna; Table 1, Algorithm 1, hasil dan keterbatasan diperiksa | Lihat `docs/literature/r2_fulltext_review.md`; detail yang tidak dilaporkan tetap ditandai tidak dilaporkan |
| Author/afiliasi/email/venue belum tersedia | Paket submission belum lengkap | Pengguna akan memberikan kemudian; tidak dibuat fiktif |

## Hal yang memperkuat jurnal, tanpa menjanjikan acceptance

Studi dua dataset historis dengan satu split dan tiga seed dapat dilaporkan sebagai benchmark
terbatas. Itu belum mendukung keandalan deployment, generalisasi kontemporer, temporal robustness,
atau klaim metode universal. Independent recent holdout, repeated splits, dan baseline tambahan
yang direncanakan sebelum TEST baru akan memperluas bukti. Kebutuhannya bergantung pada klaim
dan venue; bukan alasan mengubah eksperimen setelah melihat hasil untuk mencari peningkatan.

Dua paper utama adalah landasan tugas yang direvisi. Artikel 2022 mendukung RF/LightGBM dan
representativitas, tetapi metode terbaiknya TF-IDF/LR; artikel 2024 membahas transfer/UDA.
Tidak ada perbandingan implementasi langsung dengan metode utama kedua artikel. R4/R5 tetap
diakui sebagai studi dekat, sehingga novelty dibatasi pada pertanyaan evaluasi/protokol dan
temuan empiris. Full-text comparison dan penilaian reviewer masih menentukan kekuatan gap.

Dataset tidak diredistribusi karena lisensinya belum jelas. Downloader/provenance disediakan,
tetapi belum ada DOI rilis, URL repositori publik final atau lisensi kode yang dipilih pemilik.

## Reproduksibilitas lingkungan

Snapshot `requirements-research.txt` berhasil dipasang ke venv baru Windows/Python 3.10;
`requirements-audit.txt` menambahkan alat pemeriksaan PDF. Editable package install dan
`pip check` lulus. Pada lingkungan terpisah ini, **50 tes unit**, reproduksi seluruh
**877.176 probabilitas dari 36 bundle** dan **108 threshold VAL**, serta **48/48 sel kode
notebook** lulus. Kernel audit dipasang hanya di prefix venv; kernel pengguna tidak ditimpa.
Freeze dan semua 55 artefak numerik terlindungi tetap identik.

Bukti ada pada `artifacts/publication_audit/clean_*`, `dependency_snapshot.json`, cycle
audit dengan runtime interpreter tersimpan, dan `artifacts/notebook_audit/execution.json`.
Percobaan install yang gagal tetap disimpan; instalasi berhasil memakai pip modern dan
verifikasi TLS aktif. Lockfile provenance asli tidak diubah. Lingkup validasi ini adalah
dependency, unit test, inference dan notebook, **bukan** pelatihan ulang penuh dari nol,
pengujian OS lain, atau pengganti holdout baru.

## Diagnostik SHAP lanjutan

`notebooks/diagnose_shap_precision.py` menguji precision pada sampel matriks fitur tersimpan,
tanpa label TEST, dengan model asli. Float32 membantu sebagian keluaran HP, tetapi satu
kasus EBBU tetap gagal. Pemilihan sampel berdasarkan residual menjadikannya diagnostik post-hoc;
hasil itu bukan pengganti SHAP seluruh cohort atau bukti bahwa akar masalah sudah ditemukan.
Artefak asli tetap dipertahankan. Diagnostik awal tersebut kemudian dituntaskan oleh
`corrections/explain.py`: SHAP 0.49.1 menyimpan threshold interventional sebagai float32;
pembulatan nearest dapat memindahkan split ke atas. RF sklearn memakai input float32.
Threshold explainer dibulatkan ke float32 terbesar yang tidak melebihi threshold asli;
ini mempertahankan split classifier pada lattice input tersebut. Float32 background juga
menghindari perbedaan baseline. Tes boundary dan enumerasi exact Shapley pada kasus kecil
memeriksa metode koreksi; semua cohort nyata tetap diperiksa terhadap classifier asli.
Tidak ada perbaikan ilmiah yang disisipkan ke modul beku.

## Cara memeriksa ulang

```powershell
python notebooks/audit_publication.py
python notebooks/run_notebook.py
python -m pytest -q
python notebooks/check_submission.py
python notebooks/check_corrections.py
```

`check_submission.py --require-ready` mengembalikan kode gagal selama blocker submission
masih ada. Kelulusan engineering dibedakan secara eksplisit dari kesiapan ilmiah/publikasi.
