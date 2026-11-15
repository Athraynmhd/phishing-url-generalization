# Risk register

| ID | Risiko | Mitigasi | Trigger | Status |
|---|---|---|---|---|
| R-01 | Skema/label HP berbeda dugaan | Header diperiksa persis; cross-verify label 100% (D-03) | M0 block | **Tertutup** (konfirmasi R2 full text disarankan) |
| R-02 | Lisensi data tidak jelas | Hanya downloader + manifest; data/raw di-gitignore | release data | Terbuka |
| R-03 | Purge menghapus banyak benign | Laporan attrition; ambang feasibility | >50% loss | Benign A −25,9%, B −35,6% → di bawah ambang, dilaporkan |
| R-04 | Domain besar mendominasi | Cluster bootstrap, domain-balanced sekunder | dominance report | `za.com` 11% cohort B; `wikipedia.org` 2,9% A |
| R-05 | Novelty dekat (R4, R5) | Gap matrix full text R4/R5 | framing review | Pembeda: source-only + domain-disjoint + bidirectional; bukan algoritme baru |
| R-06 | Fitur berkorelasi menekan PI | Korelasi Spearman FIT dilaporkan (`selection.json`) | diskusi | Dilaporkan |
| R-07 | Proxy RF bias ke RF | Proxy sama untuk semua selector, diungkapkan | — | Diungkapkan |
| R-08 | Overhead parsing dominan | Benchmark nyata + dependency pruning (I09) | klaim lightweight gagal | Ditentukan hasil |
| R-09 | Dataset tua (2017–2024) | Klaim dibatasi pada benchmark | — | Diungkapkan |
| R-10 | Agen melihat TEST saat development | Loader menolak TEST; label TEST file terpisah; freeze sebelum evaluate | — | Prosedural |
| R-11 | Dependency/PSL berubah | `requirements.lock`, hash PSL, offline | rerun | Terkunci |
| R-12 | Tiga seed terlalu sedikit | CI kondisional; per-seed dilaporkan; tanpa uji t | — | Diungkapkan |
| R-13 | Full text R1/R2 belum ada | Ditandai UNKNOWN | submission | Terbuka (D-19) |
