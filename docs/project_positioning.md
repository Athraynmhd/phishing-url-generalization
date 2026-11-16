# Posisi proyek dan kesesuaian tugas

Pasangan utama aktif sudah diselaraskan ke `PRD (1).md`: **R15 (2022) + R2 (2024)**.
R5 menjadi pembanding terdekat, bukan paper utama. Lihat `docs/literature/r15_assessment.md`
dan `docs/publication_readiness.md` untuk batas bukti serta kesiapan submission.

Pembaruan: 16 November 2026. Instruksi pengguna memperbolehkan dua paper dan menegaskan
usia 3–5 tahun tetap berlaku. Dua paper utama memenuhi batas lima tahun, dengan 2024
masuk prioritas tiga tahun dan 2022 di luar prioritas itu. Dokumen ini memperjelas laporan sesudah eksperimen;
bukan perubahan metode atau hipotesis sebelum TEST.

## Dua paper utama

| Paper | Peran dalam proyek | Batas penggunaan |
|---|---|---|
| Rashid dkk. (2024), DOI 10.1016/j.comnet.2024.110398 | Dasar persoalan generalisasi lintas dataset; sumber HP; pembanding konseptual UDA | UDA bukan LightGBM. Proyek tidak mengimplementasikan UDA dan tidak mengklaim mengunggulinya. |
| Sánchez-Paniagua dkk. (2022), DOI 10.1109/ACCESS.2022.3168681 | Mengevaluasi RF/LightGBM dan representativitas URL login | Hasil terbaik keseluruhan TF-IDF/n-gram + LR; proyek tidak memakai PILU atau mengklaim reproduksi metode terbaik. |

Dua paper utama ini memenuhi **ketentuan jumlah dan usia** berdasarkan tanggal acuan
16 November 2026. Batas tiga tahun adalah 16 November 2023 dan batas lima tahun adalah
16 November 2021; publikasi Mei 2024 masuk keduanya dan 18 April 2022 masuk lima tahun.
Full text R15 dan R2 tersedia dan diperiksa. PDF R2 asli pengguna telah dibaca lengkap
sesuai D-37; rincian metode dan batas bukti ada di `docs/literature/r2_fulltext_review.md`.
Sahingoz dkk. (2019) dan referensi algoritme klasik dipertahankan dalam provenance internal,
termasuk `docs/literature/historical_references.bib`, bukan bibliography aktif yang dibatasi
usia. Tidak ada kewajiban satu jurnal per classifier dalam teks tugas.
Mengganti peran referensi tidak menjadikan dataset EBBU/HP sebagai dataset baru.

## Gap yang dapat dipertanggungjawabkan

Deteksi phishing URL dan penurunan performa lintas dataset **sudah** diteliti. R2 juga
sudah menawarkan solusi yang memanfaatkan distribusi target tanpa label. Karena itu,
gap proyek bukan ketiadaan studi cross-dataset atau ketiadaan studi stability selection.
R2 juga mengevaluasi transfer model sebelum adaptasi; melakukan pengujian tanpa UDA saja
bukan pembeda yang cukup. Pertanyaan matched-k dan gabungan kontrol evaluasinya yang diuji di sini.
R5 sudah membahas stabilitas importance dan biaya komputasi. Pembeda yang diajukan adalah
cara memperoleh evidence seleksi dari domain sumber saja dan kontrol perbandingannya,
bukan menemukan hubungan stabilitas–transfer atau pengukuran biaya untuk pertama kali.

Pertanyaan yang diuji adalah: **tanpa data target untuk fitting, seleksi fitur, atau
kalibrasi threshold, apakah ranking permutation importance yang mempertimbangkan
kestabilan antar-fold domain sumber memberi F1 transfer lebih baik daripada ranking
rata-rata pada jumlah fitur sama; dan apakah pengurangan fitur memberi penghematan
latensi yang sepadan?** Dua arah transfer diuji pada cohort yang domainnya terpisah.
Identitas target dipakai untuk audit/purge domain, sehingga akuisisi benchmark tidak
diklaim target-blind. Benchmark biaya juga memakai pool VAL kedua sumber, bukan fitting.

Ini gap **evaluasi pada setting yang didefinisikan**, bukan bukti bahwa tidak ada paper
lain yang pernah menjawabnya. Dua paper cukup untuk tugas yang direvisi, tetapi tidak
cukup untuk membuktikan novelty universal. R4/R5 pada gap_matrix tetap menjadi pemeriksaan
terhadap klaim kebaruan berlebihan. Rincian paper yang belum diperoleh tidak ditafsirkan
sebagai kelemahan paper.

## Kontribusi, bukti, dan batas klaim

| Kontribusi | Implementasi/bukti | Klaim yang dibolehkan |
|---|---|---|
| Protokol benchmark terkurasi | Purge simetris, split domain-disjoint, audit/prepare/freeze | Pengujian lintas sumber yang dapat diaudit pada EBBU–HP; bukan dataset baru atau klaim pertama. |
| Perbandingan selektor yang terkontrol | ALL, MEAN_PI, STABLE_PI; PI/proxy yang sama; nested CV dan matched-k | Menguji pengaruh aturan ranking pada jumlah fitur sama; jumlah fitur sama tidak menjamin kapasitas/struktur model sama. Bukan algoritme baru yang terbukti unggul umum. |
| Temuan empiris dan trade-off | Empat sel evaluasi, threshold sumber tetap, CI domain, benchmark waktu | Efek bergantung arah; hasil terhadap ALL dan latensi tetap dilaporkan walau tidak menguntungkan usulan. |

SHAP merupakan diagnostik pendukung. Kegagalan v1 dipertahankan dalam audit; koreksi
exploratory D-36–D-38 lulus additivity pada seluruh cohort dengan model asli tetap.
Additivity tidak digunakan sebagai bukti faithfulness lengkap atau hubungan kausal.

**Rumusan kontribusi untuk presentasi:**
“Kami mengevaluasi seleksi fitur berbasis kestabilan domain sumber pada deteksi phishing
URL, dengan pembanding rata-rata importance pada jumlah fitur sama, split domain-disjoint,
threshold terkunci, dan transfer dua arah. Kontribusi kami adalah protokol yang dapat
diaudit dan bukti empiris tentang batas trade-off transfer–biaya pada dua dataset ini.”

**Jawaban jika ditanya novelty:**
“Kami tidak mengusulkan algoritme pohon baru dan tidak mengklaim yang pertama memakai
stabilitas fitur. Kebaruan yang kami ajukan terbatas pada rancangan evaluasi dan insight
empiris dalam setting source-only ini; novelty terhadap seluruh literatur belum terbukti.”

## Kesesuaian deliverable

| Ketentuan | Status |
|---|---|
| Dua paper menurut revisi pengguna | R15 (2022) dan R2 (2024); kedua full text telah diperiksa, termasuk 14 halaman PDF R2 yang diberikan pengguna |
| Usia paper 3–5 tahun, dikonfirmasi tetap berlaku | Terpenuhi pada jendela lima tahun; bibliography aktif hanya 2022–2026, sumber historis diarsipkan internal |
| Jenis/kategori proyek | Application project / empirical benchmark; General Machine Learning |
| Baseline dan eksperimen | RF/LightGBM dengan ALL dan dua selektor, dua arah; bukan perbandingan implementasi R15 vs R2 |
| Laporan IEEE LaTeX dan PDF | Naskah koreksi: `manuscript/corrected/main.tex` dan `main.pdf`; naskah v1 tetap disimpan |
| Maksimal 10 halaman isi; referensi boleh ekstra | PDF koreksi 8 halaman termasuk referensi; angka melalui generated/macros.tex dalam bundle koreksi |
| Nama anggota, kontribusi GitHub, tautan repositori | Identitas/tautan belum tersedia; tidak dibuat fiktif |
| Slides dan presentasi 15 menit + tanya jawab 5 menit | Urutan presentasi disarankan di bawah; berkas slides dan pelaksanaan presentasi belum diverifikasi |

Urutan presentasi yang disarankan: motivasi → dua paper utama → gap → metode/protokol →
hasil positif dan negatif → batas validasi → kontribusi dan future work. Hindari menjadikan
penggabungan RF dan LightGBM, penggunaan SHAP, atau skor tinggi sebagai novelty tersendiri.
