# Koreksi exploratory dan pekerjaan protokol berikutnya

Pembaruan D-36–D-38: koreksi SHAP dan jalur label-free telah dijalankan secara exploratory
dalam `src/phishresearch/corrections`; seluruh 24 cohort lulus. HP encoding crossvalidated
terhadap Table 1 dan review full text R2 selesai. `docs/publication_readiness.md` memuat
status terkini. Rencana di bawah tetap relevan untuk protokol baru dengan holdout baru;
bukan klaim bahwa eksperimen tersebut sudah dilakukan.

Dokumen ini adalah rencana koreksi setelah audit, bukan protokol baru yang sudah dibekukan,
bukan klaim ada holdout baru, dan bukan izin menimpa eksperimen v1. Perubahan berikutnya
harus dicatat sebelum label holdout baru dibuka. Jika memakai kembali cohort lama untuk
diagnostik, keluaran harus dipisahkan dan diberi label exploratory.

## Koreksi wajib untuk jalur analisis

1. Pusatkan semua pembacaan label TEST di `evaluation.py`. Sampling explanation yang
   memerlukan stratifikasi label dilakukan di sana, menghasilkan record IDs/fitur tanpa
   mengekspor label ke modul pengembangan/visualisasi. Validasi lintas data dijalankan
   oleh evaluator; analisis menerima saved scores/counts yang telah dipastikan konsisten.
2. Tambahkan tes akses file yang menolak pembacaan vault label dari semua entry point
   selain evaluator, termasuk analysis, notebook, CLI dan worker SHAP. AST search saja
   bukan bukti absolut; tambahkan pengujian perilaku pembacaan file.
3. Tangani residual additivity terhadap probabilitas classifier sebenarnya. Pemakaian
   float32 perlu diperiksa karena sklearn RF memakai float32 saat inferensi, tetapi
   diagnostik audit menunjukkan itu tidak menyelesaikan semua kasus. Jangan menambahkan
   residual ke SHAP secara manual atau melonggarkan toleransi hanya agar hasil lulus.
4. Tentukan kebijakan hasil explanation gagal sebelum analisis baru: pertahankan failure,
   laporkan jumlah dan lokasi, dan larang registry menyatakan validasi penuh. Uji seluruh
   sampel yang dilaporkan, bukan hanya fixture sintetis atau sampel yang mudah.

## Bukti data dan evaluasi

* Konfirmasi kode angka HP dari author/codebook/bukti langsung yang sah. Jangan memakai
  pola URL atau label yang diharapkan untuk menjustifikasi mapping.
* Peroleh dan baca lengkap R2. Lengkapi matrix penggunaan target, unit split, tuning,
  threshold dan overlap berdasarkan bagian/tabel, termasuk UNKNOWN bila tidak dilaporkan.
* Tetapkan holdout independen yang relevan dengan klaim; periksa provenance, lisensi,
  timestamp, URL/domain overlap dan akses raw URL sebelum menjanjikan eksperimen.
* Repeated group splits mengukur variasi sampling training lebih baik daripada menambah
  estimator seeds pada split sama. Tentukan biaya dan analisis sebelum hasil baru dilihat.
* Kalau menambahkan LR/TF-IDF dari R15 atau UDA dari R2, nyatakan sebagai baseline baru
  dengan budget/source-target access yang jelas, bukan membandingkan skor publikasi
  berlainan dengan angka eksperimen sendiri.

## Batas klaim dan submission

Perjelas apakah targetnya benchmark historis, generalisasi ke sumber kontemporer, atau
metode baru. Klaim terakhir memerlukan bukti pembeda lebih kuat; dua rujukan utama untuk
tugas tidak menggantikan audit studi terdekat. Pilih venue, identitas penulis, peran
kontributor dan kebijakan code/data availability sebelum menyatakan siap submit.
