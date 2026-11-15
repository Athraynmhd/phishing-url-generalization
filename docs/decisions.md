# Decision log (protocol v1)

Setiap keputusan yang tidak ditetapkan PRD, atau yang menafsirkan PRD, dicatat di sini **sebelum** TEST dibuka.
Format: ID — keputusan — alasan/bukti — dampak.

| ID | Keputusan | Alasan / bukti | Dampak |
|---|---|---|---|
| D-01 | Ruang lingkup = PRD v1 §2 tanpa ekstensi. | PRD §2. | — |
| D-02 | Commit sumber dipin: A `ebubekirbbr/pdd@90b394d8`, B `fariza25/PhishingURLDetection@ff9f1f5b` (diambil 2026-11-15 via GitHub API). Ukuran file dicek terhadap tree GitHub. | `data/raw/manifest.json` (SHA256 tiap file). | Raw immutable. |
| D-03 | Mapping label B = 1 phishing / 0 benign. | Repo B tidak punya codebook. Bukti: salinan `ebbu_*.csv` di repo B (pipeline penulis yang sama) di-join dengan file A per URL; **73.575/73.575 baris cocok (100%)** dengan label dari nama file A (`data_phishing`→1). `artifacts/audit.json › label_mapping_check`. HISPAR = daftar benign, Phishstats = feed phishing (R2, abstrak). | Gate data lulus. **Penulis sebaiknya mengonfirmasi dengan full text R2** (belum diperoleh, lihat D-19). |
| D-04 | Parser mengarantina *semua* karakter kontrol C0 (bukan hanya CR/LF/NUL) dan prefiks `kata:` yang bukan `host:port` (`mailto:`, `javascript:`, `http:/x`). | `urlsplit` diam-diam menghapus tab/kontrol awal sehingga `url_key` tidak lagi sesuai string asli. Konsekuensi: URL hostless `user:pass@host` ikut terkarantina (jarang). Teramati: A 3 karantina, B 17. | Batas cakupan dilaporkan. |
| D-05 | Batas panjang 16.384 dipertahankan. | Review distribusi: maks A 3.992, B 1.301 karakter; tidak ada URL terkena batas. | — |
| D-06 | PSL: snapshot ICANN dari paket tldextract 5.4.0 (`VERSION 2025-04-07_15-51-09_UTC`, `COMMIT 5fc8d12`), SHA256 di `audit.json`. Matcher sendiri, offline, hanya bagian ICANN. Host tanpa aturan ICANN eksplisit → seluruh host (PRD §8). | Tidak ada fetch jaringan; private suffix tidak dipakai (blogspot.com satu grup). | `za.com` (private CentralNic) menjadi satu grup besar di B (11%); dilaporkan, lihat R-04. |
| D-07 | Host Unicode → IDNA 2008/UTS46 non-transitional (`idna` 3.20). Host ASCII tidak divalidasi IDNA (underscore diizinkan) tetapi harus `[a-z0-9_.-]`. | Subdomain phishing sering memakai `_`. | — |
| D-08 | Dedup dalam sumber: simpan baris pertama urut (`source_file`, `original_row`). | PRD §9 "deterministik". A kehilangan 18.811 duplikat `url_key`. | Dilaporkan di attrition. |
| D-09 | SHAP dijalankan pada bundle seed 17 untuk ALL dan STABLE_PI(budget) tiap sumber×model; stabilitas antar-seed pada ALL (cohort sumber). | Pilot: RF interventional ≈0,43 s/sampel → semua konfigurasi×seed ≈ >2 jam. Diputuskan sebelum freeze; sampel stratifikasi 250/250. | Klaim SHAP dibatasi pada konfigurasi ini. |
| D-10 | Benchmark: bundle seed 17 setiap konfigurasi final; thread inferensi {1, 4}; batch-1 diulang 10× repeats (300), batch-1024 30×; pool URL = selang-seling URL VAL A dan B (sama untuk semua model). | Pada `n_jobs=4`, latensi RF batch-1 didominasi overhead thread pool (smoke ≈15 ms), sehingga 1 thread juga dilaporkan. Field `benchmark.threads` ditambahkan ke config setelah `develop` mulai; tidak memengaruhi development. | RQ3 dijawab per thread setting. |
| D-11 | PI dihitung sekali per (sumber, seed, baris training) dan dipakai ulang untuk MEAN_PI, STABLE_PI, semua k. | PI tidak bergantung pada k atau aturan ranking → identik dengan memanggil `fit_selector` per k/metode, lebih murah. Hash selector outer ≠ full (I03). | — |
| D-12 | Seed fold: outer = `split_seed`; inner fold outer-*o* = `split_seed+1+o`; PI full-FIT = `split_seed`. Seed model mengatur RF proxy, permutasi, dan classifier. | PRD §13: split/fold tetap lintas seed model. | Variasi antar seed = estimator/PI saja. |
| D-13 | Freeze meng-hash semua modul kecuali `reporting.py`, `cli.py`, `nbviz.py` (presentasi). | Tata letak tabel/figur boleh diperbaiki setelah evaluasi tanpa membuka freeze. | — |
| D-14 | Freeze ditandatangani agen **atas instruksi eksplisit pengguna** (2026-11-15): `approved_by = "Claude agent on behalf of the author (user instruction 2026-11-15)"`. | PRD M4: review freeze = kontrol peneliti; pengguna memilih mendelegasikan. | Dicatat apa adanya; penulis tetap bertanggung jawab atas keputusan ilmiah di log ini. |
| D-15 | pytest dipin 8.3.5. | pytest 9.2.0 crash internal (`NodeId._str_cache`) di lingkungan ini. | — |
| D-16 | Thread: RF/LightGBM/proxy `n_jobs=4`; `permutation_importance(n_jobs=1)`; loop outer serial. | PRD §13. | — |
| D-17 | Ringkasan domain-balanced: bobot URL = 1/ukuran grup di TEST. | PRD §15 (sekunder). | — |
| D-18 | CI konfigurasi tunggal = cluster bootstrap F1 rata-rata seed (pembanding nol). Kontras = paired cluster bootstrap, sampel domain identik untuk kedua lengan dan semua seed. | PRD §15. | CI kondisional pada split & seed. |
| D-19 | Full text R1 dan R2 belum diperoleh (R1 paywall, handle OA HTTP 500; R2 CC BY tetapi ScienceDirect menolak unduhan otomatis). | Gap matrix menandai UNKNOWN. Pembeda studi ini terhadap R2 (UDA memakai data target) dapat dibaca dari abstrak; tidak ada klaim kelemahan R1/R2 dari abstrak. | **Non-blocking untuk eksperimen, blocking untuk submission**: penulis mengunduh manual. |
| D-20 | Syarat kampus "dua artikel jurnal utama per classifier" (LightGBM) belum terpenuhi; tidak diisi dengan referensi karangan. | PRD §4. | Pending keputusan penulis. |
