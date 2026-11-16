# Risk register

| ID | Risiko | Mitigasi | Trigger | Status |
|---|---|---|---|---|
| R-01 | Skema/label HP berbeda dugaan | Header dan raw hash; kedua encoding dibandingkan dengan enam jumlah kelas Table 1 PDF R2 (D-37) | validasi data | **Encoding crossvalidated**: hanya 0 benign / 1 phishing cocok pada semua original split. Bukan codebook verbatim atau verifikasi label per URL. |
| R-02 | Lisensi data tidak jelas | Hanya downloader + manifest; data/raw di-gitignore | release data | Terbuka |
| R-03 | Purge menghapus banyak benign | Laporan attrition; ambang feasibility | >50% loss | Benign A −25,9%, B −35,6% → di bawah ambang, dilaporkan |
| R-04 | Domain besar mendominasi | Cluster bootstrap, domain-balanced sekunder | dominance report | `za.com` 11% cohort B; `wikipedia.org` 2,9% A |
| R-05 | Novelty dekat (R4, R5) | Gap matrix full text R4/R5 | framing review | Pembeda: source-only + domain-disjoint + bidirectional; bukan algoritme baru |
| R-06 | Fitur berkorelasi menekan PI | Korelasi Spearman FIT dilaporkan (`selection.json`) | diskusi | Dilaporkan |
| R-07 | Proxy RF bias ke RF | Proxy sama untuk semua selector, diungkapkan | - | Diungkapkan |
| R-08 | Overhead parsing dominan | Benchmark nyata + dependency pruning (I09) | klaim lightweight gagal | Ditentukan hasil |
| R-09 | Dataset tua (2017–2024) | Klaim dibatasi pada benchmark | - | Diungkapkan |
| R-10 | Agen melihat TEST saat development | Loader menolak TEST; label TEST file terpisah; freeze sebelum evaluate | - | Prosedural |
| R-11 | Dependency/PSL berubah | `requirements.lock`, hash PSL, offline | rerun | Terkunci |
| R-12 | Tiga seed terlalu sedikit | CI kondisional; per-seed dilaporkan; tanpa uji t | - | Diungkapkan |
| R-13 | Full text utama belum diperiksa | PDF R2 asli pengguna dan review seluruh 14 halaman; D-37 | submission | **Selesai untuk pasangan utama R15/R2**. R1 historis masih terbatas dan tidak diklaim dibaca lengkap. |
| R-14 | Additivity SHAP real-data gagal | Koreksi input/threshold representation dan strict actual-model checks; D-38 | residual >1e-6 | **Dikoreksi secara exploratory**: seluruh 24/24 keluaran koreksi lulus. Empat kegagalan v1 tetap tersimpan. Additivity tidak menjamin faithfulness. |
| R-15 | Jalur SHAP lama membaca label vault di luar evaluator | CLI legacy diblok; namespace koreksi aktif memakai saved feature matrices; sampling baru dibatasi evaluator | perbaikan kode beku | **Jalur aktif dimitigasi dan diuji**; koreksi diberi label exploratory. Pelanggaran historis v1 tetap didokumentasikan; tidak diklaim hilang atau retrospectively blinded. |
