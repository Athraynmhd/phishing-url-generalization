# R2: review full text dan encoding HP

**Selesai 16 November 2026.** Pengguna memberikan PDF asli penerbit,
`1-s2.0-S1389128624002305-main.pdf` (14 halaman), judul dan DOI
`10.1016/j.comnet.2024.110398` cocok. SHA256:
`4d4ead94d9224a644ea753dbaa2bb7c989ea222091aeec00c591258b99ce2edd`.
Seluruh halaman dibaca; Table 1 dan Algorithm 1 juga diperiksa secara visual.
Jejak ekstraksi/provenance: `artifacts/publication_corrections/R2_fulltext_provenance.json`.

## Bukti metode yang relevan

| Lokasi PDF | Temuan | Implikasi bagi studi ini |
|---|---|---|
| Hlm. 3–4, §3 | Kerangka UDA menggunakan distribusi target tanpa label | Source-only adalah batas akses berbeda; jangan membandingkan angka seolah budget akses target sama |
| Hlm. 4, §4/Table 1 | ISCX, EBBU dan HP; split asal acak 60/20/20; tidak mendeskripsikan domain-disjoint assignment | Cohort dan split domain-disjoint studi ini adalah desain sendiri; jangan menyebut reproduksi split asli |
| Hlm. 4, §4.3 | HP benign dari HISPAR; phishing Phishstats Juni–Agustus 2022 dengan filter skor >5 | Data historis dan mekanisme koleksi tetap menjadi batas generalisasi |
| Hlm. 5, §5/Table 2 | URLNet, URLTran, CatchPhish dan PhishRF; tuning pada validation dataset; grid/budget numerik tidak dirinci | RF/LightGBM dengan parameter tetap tidak mereplikasi empat sistem tersebut |
| Hlm. 6–8, §6.2/Table 4–5 | RF importance memakai mean decrease in impurity; top-15 diinterseksikan antar model dataset; uji Mann–Whitney pada fitur | Bukan PI source-domain atau matched-k stability selector studi ini |
| Hlm. 8–9, §7.1/Algorithm 1 | Distribusi path target TEST dipakai tanpa label untuk memperpanjang/memotong path sumber; sampling/interpolasi menyamakan ukuran | Metode memang transductive UDA; target-feature access berbeda dari fitting source-only |
| Hlm. 9, §7.2 | Prefix dan dot hostname juga dimodifikasi | Jangan mendeskripsikan metodenya sekadar classifier RF |
| Hlm. 9–11, §8/Table 6 | Kombinasi modifikasi dengan hasil terbaik dilaporkan; ada perbaikan, kasus nol dan kasus menurun | Tidak ada klaim superiority proyek atas UDA berdasarkan angka lintas paper |
| Hlm. 12, §9.2 | Batas interkorelasi fitur dan pencocokan marginal yang mengabaikan target class-conditional distribution diakui | Pembatasan novelty harus tetap mengakui analisis feature shift terdahulu |
| Hlm. 13–14 | Data availability on request; referensi dan biodata | Lisensi artikel CC BY tidak otomatis menetapkan lisensi redistribusi dataset |

Artikel tidak melaporkan domain-cluster bootstrap CI atau benchmark latency/hardware yang
setara studi ini. Domain overlap, semua detail hyperparameter dan label-per-URL correctness
tetap tidak disimpulkan bila tidak dinyatakan. Terdapat ketidakkonsistenan kecil baseline
CatchPhish ISCX→HP antara Table 2 dan Table 6; angka tersebut tidak dipakai sebagai angka
hasil proyek atau basis klaim peningkatan lintas paper.

## Bukti encoding HP yang dapat direproduksi

Table 1 (hlm. 4) menjadi sumber angka eksternal. Evaluator membandingkan **kedua**
kemungkinan orientasi label dengan ketiga file raw yang hash/commit-nya dipin:

| Original split | Numeric 0 / published benign | Numeric 1 / published phishing |
|---|---:|---:|
| train | 27.740 | 27.760 |
| valid | 9.180 | 9.320 |
| test | 9.330 | 9.170 |

Semua enam jumlah cocok tepat; hanya orientasi **0 benign / 1 phishing** cocok.
`corrections/evaluation.py::verify_hp_encoding` hanya membaca kolom label, tidak raw URL;
fungsi mengembalikan agregat dan provenance, bukan label individual.
Jalankan `python notebooks/verify_hp_encoding.py`; bukti tersimpan dalam
`artifacts/publication_corrections/hp_encoding.json` dan salinan bertimestamp.

Ini crossvalidation langsung ke class counts dalam paper dan lebih kuat daripada bukti
salinan EBBU sebelumnya. **Bukan codebook verbatim buatan author**, dan tidak menguji
kebenaran label tiap URL. Kekosongan codebook tidak disamarkan dengan mengarang kutipan.
Manifest raw v1 tetap utuh; bukti baru disimpan sebagai sidecar.

## Riwayat akses dan kesimpulan gap

Percobaan endpoint penerbit/Minerva/OpenAlex/Semantic Scholar sebelumnya disimpan sebagai
riwayat, bukan dihapus. Presentasi resmi 36 halaman dari situs laboratorium penulis
mendukung pemeriksaan awal, tetapi status full review baru ditutup setelah PDF pengguna
dibaca. Tidak ada URL di dalam dataset atau contoh paper dibuka.

R2 sudah meneliti cross-dataset transfer dan pergeseran fitur. Kontribusi proyek tetap
berupa evaluasi terkendali source-domain PI, matched feature count, threshold sumber,
domain-disjoint dua arah dan biaya; review full text tidak membuktikan klaim pertama
di dunia, algoritme baru, ataupun penerimaan publikasi.
