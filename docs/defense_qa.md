# Persiapan diskusi dengan pembimbing

Judul: **DA-GAFS: Direction- and Generalization-Aware Feature Selection for Cross-Source Phishing URL Detection**
Kategori: General Machine Learning (application project)

Angka di dokumen ini disalin dari `manuscript/corrected/generated/macros.tex`, `ext_macros.tex` dan `dagafs_macros.tex`
(run `artifacts/extensions/latest.json`, `artifacts/extensions/dagafs/latest.json`, `artifacts/extensions/dagafs_posthoc/latest.json`). Jika data atau analisis berubah, angka diperbarui dari
file tersebut, bukan diketik ulang di naskah.

---

## 1. Inti proyek dalam satu kalimat

> Jika detektor URL phishing dilatih pada satu dataset lalu dipakai pada dataset lain **tanpa data target sama sekali**,
> apakah memilih fitur yang *stabil* lebih tahan dibanding memilih fitur yang *rata-rata paling penting* pada jumlah fitur
> yang sama, dan berapa harga kompresi itu?

**Jawaban singkat yang dibawa ke ruang diskusi:**
1. Transfer **tidak simetris**: EBBU→HP F1 0,922 (LightGBM), tetapi HP→EBBU hanya 0,739–0,790.
2. STABLE-PI mengalahkan MEAN-PI pada k yang sama **hanya di arah sulit** (+0,059 RF, +0,077 LightGBM; CI tidak memuat 0).
   Di arah lain efeknya netral.
3. **Tidak ada subset** yang menyamai 37 fitur lintas dataset. Penghematan latensi juga kecil.
4. **Mengapa** (RQ5, hanya VAL): satu aturan "bukan HTTPS ⇒ phishing" saja sudah mencapai F1 0,874 di HP. Selain itu,
   3 dari 14 fitur **berbalik arah** antar dataset (jumlah label host, jumlah subdomain, keberadaan query).
   Stabilitas yang diukur di dalam *satu* sumber tidak bisa mendeteksi pembalikan semacam ini.
5. **DA-GAFS** (RQ6, arahan pembimbing: 5 komponen C1–C5; hanya FIT/VAL, memakai label FIT kedua koleksi untuk seleksi):
   - C2 menemukan 2 pembalikan yang robust (`host_label_count` r −0,31/+0,65; `subdomain_label_count` r −0,44/+0,66;
     tanda bertahan di 100% replikasi bootstrap).
   - Tetapi gate arah **merugikan**: `subdomain_label_count` adalah fitur terpenting lintas sumber. Tanpa fitur itu AP lintas
     sumber di FIT maksimal 0,914 vs 0,942, sehingga aturan biaya (C4) memilih k*=35 dan DA-GAFS ≈ ALL
     (LightGBM HP→EBBU +0,006 [+0,002, +0,010]).
   - Yang **berhasil** adalah bukti lintas sumber (C1/importance gabungan): subset 12 fitur (waktu ekstraksi 0,53× ALL)
     mengalahkan subset source-only STABLE-PI di HP→EBBU sebesar +0,048 (RF) dan +0,066 (LightGBM), dan RF-nya bahkan
     melampaui RF ALL (+0,013). Ini evaluasi **post-hoc** (D-42).
   - C5 memilih LightGBM tunggal; ensemble 3 model akan turun −0,031 di HP→EBBU.

## 2. Pitch 60 detik

Detektor URL murah dan cepat, tetapi akurasi yang dilaporkan hampir selalu diukur di dalam satu dataset. Kami
mengukur apa yang terjadi saat model dipindahkan ke dataset lain dengan domain yang benar-benar terpisah, dua arah,
tanpa menyentuh data target untuk training, seleksi fitur, maupun threshold. Kami membandingkan dua cara memilih
fitur dari bukti permutation importance yang sama: berdasarkan rata-rata, atau berdasarkan stabilitas antar fold
domain. Hasilnya, stabilitas membantu di satu arah, tetapi kompresi tetap merugikan dibanding memakai semua fitur.
Analisis error menunjukkan penyebabnya: sebagian sinyal bergantung pada era dataset (HTTPS) atau bahkan berbalik
makna antar dataset (subdomain). Karena itu kami membangun DA-GAFS dengan lima komponen: stabilitas lintas sumber,
konsistensi arah, ranking terpadu, budget multi-objective akurasi–biaya, dan ensemble yang sadar generalisasi. Temuannya
jujur dua sisi: bukti lintas sumber menghasilkan subset 12 fitur yang jauh lebih baik dari subset source-only dengan
biaya ekstraksi separuh, tetapi membuang fitur yang arahnya berbalik justru merugikan, karena fitur itu tetap dipakai
model pohon. Pembalikan marginal tidak sama dengan tidak bisa ditransfer.

---

## 3. Pertanyaan yang mungkin diajukan, dan jawabannya

### A. Novelty dan posisi

**Q: Apa yang baru? Cross-dataset phishing kan sudah diteliti (Rashid 2024).**
Benar, dan naskah menyatakannya secara eksplisit. Yang kami uji berbeda:
(i) batasan **source-only penuh** (UDA Rashid memakai data target tanpa label);
(ii) perbandingan **matched-k** antara aturan ranking stabil vs rata-rata dari bukti PI yang sama;
(iii) split **domain-disjoint dua arah** (Rashid memakai split URL acak, sudah dicek di full text);
(iv) penjelasan mekanistis mengapa seleksi dari satu sumber gagal, yaitu cue yang berbalik arah.
Kami **tidak** mengklaim algoritme baru atau mengalahkan UDA.

**Q: Kalau hasilnya STABLE-PI tetap kalah dari ALL, apa gunanya?**
Itu hasil negatif yang informatif. Praktisi sering memangkas fitur untuk efisiensi dan mengira seleksi berbasis
stabilitas "aman" untuk generalisasi. Kami menunjukkan batasnya: stabilitas di dalam satu sumber hanya mengurangi
kerugian, tidak menghilangkannya. RQ5 juga menjelaskan alasannya. Itulah insight yang diminta kriteria tugas
("convey novel insight about the problem").

**Q: Ini application project atau algorithmic?**
Application/empirical project (dinyatakan di naskah dan di bawah judul). STABLE-PI adalah aturan ranking eksplisit,
bukan algoritme learning baru.

### B. Data dan desain eksperimen

**Q: Kenapa EBBU dan HP? Datanya lama.**
Keduanya publik, berlabel, dipakai di paper utama (EBBU di Sánchez-Paniagua 2022; HP di Rashid 2024), dan berbeda
proses koleksi, sehingga cocok untuk menguji transfer. Keterbatasan usia data diakui di Threats to Validity, dan
justru terlihat di temuan HTTPS.

**Q: Kenapa harus split per domain? Bukankah split acak biasa sudah cukup?**
Dengan split acak, URL dari domain yang sama bisa muncul di train dan test, sehingga model menghafal domain.
Kami juga membuang 692 domain yang muncul di kedua dataset, agar transfer yang diukur bukan sekadar
"domain yang sudah pernah dilihat".

**Q: Pembuangan domain bersama itu memakai identitas data target. Bukankah itu bocor?**
Purge hanya memakai *identitas domain* untuk kurasi benchmark, tidak pernah untuk training, seleksi, atau threshold.
Naskah menyebut ini secara eksplisit ("source-only describes learning and calibration, not target-blind acquisition").

**Q: Kenapa hanya RF dan LightGBM? Kenapa tidak deep learning?**
Fokus kami detektor ringan dengan fitur leksikal dan biaya terukur, dan keduanya dievaluasi di paper utama 2022.
Tugas meminta baseline dari materi kuliah, jadi kami menambahkan **Logistic Regression** dan aturan satu fitur
(RQ5). Deep learning di luar cakupan dan disebut sebagai batas.

**Q: Mana baseline-nya?**
Ada tiga:
(1) **ALL 37 fitur** sebagai pembanding seleksi;
(2) **Logistic Regression** (log1p + standardisasi, C=1, tanpa tuning);
(3) aturan **"bukan HTTPS ⇒ phishing"** tanpa training.
Hasilnya, LogReg kuat di dalam sumber (F1 0,871 / 0,929), tetapi EBBU→HP runtuh ke 0,275 walaupun AUC-nya 0,847.
Artinya peringkat skornya masih bisa dipakai, tetapi threshold dari sumber tidak.

**Q: Hyper-parameter tidak di-tuning?**
Sengaja ditetapkan di awal agar perbedaan yang terlihat berasal dari seleksi fitur, bukan dari tuning. Ini juga
mencegah pemakaian data target untuk tuning. Keterbatasannya diakui.

### C. Statistik dan validitas

**Q: Hanya 3 seed, kok berani klaim?**
Kami tidak memakai uji t dengan 3 seed. Ketidakpastian diukur dengan **paired domain-cluster bootstrap**
(2.000 replikasi, domain sebagai unit, sampel identik untuk kedua lengan). Kami juga menyatakan bahwa CI ini
kondisional pada model yang sudah dilatih dan tidak mencakup variasi training. Tidak ada klaim signifikansi familywise.

**Q: Kenapa F1, bukan akurasi?**
F1 kelas phishing ditetapkan sebagai outcome primer sebelum evaluasi. AP, AUC, MCC, dan balanced accuracy juga
dilaporkan. Akurasi menyesatkan bila prevalensi berbeda antar dataset.

**Q: EBBU→HP justru lebih tinggi dari EBBU→EBBU. Bukankah itu aneh?**
Aneh, dan itu temuan. RQ5 menjelaskannya:
- HP lebih "mudah" dipisahkan oleh cue sederhana. Aturan HTTPS saja sudah mencapai F1 0,874.
- Model EBBU masih meleset di HP pada phishing berbasis HTTPS: 57,4% phishing HTTPS terlewat, padahal phishing
  non-HTTPS hanya 1,6%.

**Q: Bagaimana Anda tahu tidak mengintip TEST?**
- Loader development menolak partisi TEST.
- Label TEST disimpan terpisah dan hanya dibaca oleh evaluator.
- Freeze meng-hash kode, data, split, dan model sebelum TEST dibuka.
- Analisis RQ5 hanya memakai FIT/VAL, dan ada tes otomatis yang gagal bila ekstensi menyentuh vault TEST.

**Q: Analisis tambahan dibuat setelah melihat hasil. Bukankah itu p-hacking?**
Kami menyatakannya terbuka sebagai **exploratory, post-freeze**:
- Spesifikasinya dicatat di decision log D-40 sebelum dijalankan.
- Analisis ini tidak memakai TEST.
- Analisis ini tidak mengubah angka utama.

Sebagai pemeriksaan kewajaran, F1 di target VAL mereproduksi F1 di target TEST (0,928 vs 0,922; 0,783 vs 0,790).

### C2. DA-GAFS (arahan pembimbing, RQ6)

**Q: Apa kepanjangan DA-GAFS? Apakah ini genetic algorithm?**
A: Direction-Aware, Generalization-Aware Feature Selection. Bukan genetic algorithm: ini ranking terpadu (C3) ditambah
aturan multi-objective (C4) berupa Pareto front akurasi lintas sumber vs biaya ekstraksi, dengan aturan pemilihan tetap
(termurah dalam toleransi 0,01 AP dari yang terbaik, sama dengan aturan budget v1). Tafsiran ini dicatat di D-41.

**Q: DA-GAFS memakai label dataset target. Bukankah itu kebocoran?**
A: Label FIT koleksi target dipakai **hanya untuk memilih fitur dan kombinasi model**, tidak untuk melatih model atau
memilih threshold. Evaluasi memakai target **VAL**, yang domain-nya terpisah dari FIT dan tidak pernah dilihat. Jadi ini
setting multi-source, bukan zero-shot, dan kami menyatakannya eksplisit di paper. Uji yang benar-benar zero-shot butuh
sumber ketiga (Future Work i).

**Q: Kenapa tidak dievaluasi di TEST?**
A: TEST sudah dibuka sekali untuk protokol v1 yang dibekukan. Memakai TEST lagi untuk metode yang dirancang setelah
melihat hasil v1 berarti reuse holdout. Aturan proyek: perubahan memerlukan protocol v2 dan holdout baru, atau dilabel
exploratory. Kami membuktikan VAL target mereproduksi TEST (LightGBM 0,928 vs 0,922 dan 0,783 vs 0,790).

**Q: Gate arah malah tidak membantu. Bukankah berarti komponen C2 gagal?**
A: C2 berhasil *mendeteksi* pembalikan secara robust, tetapi *keputusan* membuang fitur tersebut salah untuk model pohon.
`subdomain_label_count` berbalik arah secara marginal, namun tetap fitur terpenting lintas sumber. Kemungkinan besar karena
dipakai bersama fitur host lain (belum kami uji langsung). Ini hasil negatif yang informatif: unit keputusan seharusnya
asosiasi kondisional (misalnya kesepakatan tanda SHAP per irisan), bukan marginal. Kami tidak menyetel ulang gate setelah
melihat hasil, karena itu akan menjadi p-hacking.

**Q: Kalau DA-GAFS ≈ ALL, apa kontribusinya?**
A: Ada tiga. (1) Ablation yang memisahkan apa yang membantu (bukti lintas sumber) dari yang tidak (gate arah).
(2) Subset lintas sumber 12 fitur dengan biaya ekstraksi separuh yang jauh lebih baik dari subset source-only (+0,048/+0,066).
(3) C5 mencegah ensemble yang merugikan (−0,031). Klaim kami dibatasi sebagai exploratory.

**Q: Evaluasi subset 12 fitur itu post-hoc. Bagaimana mempertanggungjawabkannya?**
A: Diputuskan setelah melihat kurva **FIT** (bukan target VAL). Titiknya dipilih oleh aturan yang sama yang sudah
ditetapkan, tidak ada parameter yang diubah, dan statusnya dilabel post-hoc di D-42, paper, notebook dan slide.
Alasannya: pada k*=35 ablation matched-k identik dengan ALL, sehingga komponen biaya tidak bisa dinilai tanpa evaluasi ini.

**Q: Kenapa C1 (XS-IS − XS-I) bernilai tepat 0?**
A: Pada k=35 kedua ranking memilih himpunan fitur yang sama (ALL dikurangi dua fitur yang hampir konstan). Efek C1 tidak
bisa dipisahkan pada budget itu. Pada k* masing-masing (12 vs 13), XS-IS sedikit di bawah XS-I di keempat sel
(selisih ≤ 0,009 F1), jadi menambahkan stabilitas di atas importance gabungan tidak membantu di benchmark ini.

**Q: Kenapa ensemble tidak lebih baik?**
A: LogReg mentransfer buruk (RQ5), jadi rata-rata probabilitas ikut turun. Aturan C5 memilih kombinasi dengan AP lintas
sumber di FIT, yaitu LightGBM tunggal, dan itu terkonfirmasi di VAL. Ensemble berbobot atau stacking adalah langkah
berikutnya, bukan klaim saat ini.

### D. Kejujuran tentang masalah historis (siapkan, jangan disembunyikan)

**Q: Di repo ada catatan pelanggaran loader dan SHAP yang gagal. Apa itu?**
Audit internal menemukan dua hal: analisis SHAP lama membaca label TEST di luar evaluator, dan sebagian residual
additivity SHAP RF melebihi toleransi (penyebabnya threshold float32 di library SHAP).
Penanganannya:
- Jalur lama diblok.
- Koreksi SHAP dilakukan sebagai exploratory, tanpa label TEST, dan seluruh 24 kohort lulus toleransi 1e-6.
- Jejaknya tetap disimpan.

Angka klasifikasi utama tidak terpengaruh, karena berasal dari evaluator.

**Q: Freeze ditandatangani oleh AI agent?**
Ya, atas instruksi eksplisit penulis, dan ini tercatat apa adanya (D-14). Freeze adalah kontrol prosedural; tanggung
jawab ilmiah tetap pada penulis.

### E. Biaya dan dampak praktis

**Q: Penghematan latensinya berapa? Layak?**
Untuk satu URL dengan satu thread, subset butuh 0,75–1,10× waktu ALL; untuk batch 1024 dengan 4 thread 0,47–1,01×.
Parsing dan ekstraksi adalah bagian besar dari biaya, dan inferensi pohon hampir tidak bergantung pada k.
Kesimpulannya, penghematan kecil dibanding kehilangan akurasi transfer.

**Q: Apa implikasi praktisnya?**
1. Jangan percaya akurasi dalam satu dataset untuk deployment.
2. Jangan memangkas fitur hanya berdasarkan satu sumber.
3. Waspadai cue yang bergantung era, seperti HTTPS. Phishing modern banyak memakai HTTPS, sehingga cue ini bisa
   melemah. Ini hipotesis untuk future work, bukan klaim.

### F. Refleksi (diminta eksplisit oleh tugas)

**Q: Apakah Anda mendapatkan yang diinginkan?**
Sebagian. Hipotesis stabilitas didukung di satu arah. Harapan bahwa model ringkas tetap tahan lintas dataset tidak
didukung. Yang didapat adalah mekanisme kegagalan yang jelas.

**Q: Apa yang akan dilakukan berbeda?**
- Baseline LogReg dan aturan HTTPS dipra-registrasi.
- EDA kelas-kondisional kedua sumber dilakukan *sebelum* merancang selektor.
- Sumber ketiga direncanakan sejak awal.
- Kontras berbasis AP dilaporkan berdampingan dengan F1.

**Q: Future work?**
1. Seleksi berbasis stabilitas **lintas sumber**, diuji di sumber ketiga.
2. Data terbaru dengan split temporal.
3. Rekalibrasi threshold tanpa label dibandingkan dengan UDA.

Semuanya memerlukan protokol v2 dan holdout baru.

---

## 4. Kelemahan yang sebaiknya diakui sendiri sebelum ditanya
- Hanya dua dataset publik lama; satu split; tiga seed.
- STABLE-PI tidak menyamai ALL; manfaatnya hanya di satu arah.
- RQ5 dan RQ6 bersifat exploratory dan dilakukan setelah freeze (walau tanpa TEST); evaluasi subset 12 fitur adalah post-hoc (D-42).
- DA-GAFS memakai label FIT koleksi target untuk seleksi; ini bukan transfer zero-shot dan tidak ada sumber ketiga.
- Gate arah (C2), komponen paling baru, tidak meningkatkan transfer.
- Data mentah tidak bisa diredistribusi (lisensi tidak jelas); repo menyediakan downloader dan hash.

## 5. Klaim yang tidak boleh diucapkan
- "Metode kami lebih baik dari UDA / dari paper X." Tidak pernah dibandingkan pada kondisi identik.
- "Robust terhadap zero-day atau phishing modern." Datanya lama.
- "SHAP membuktikan fitur X menyebabkan prediksi." Hanya deskriptif.
- "Signifikan secara statistik" untuk seluruh keluarga uji. Tidak ada koreksi familywise.
- "DA-GAFS mengalahkan ALL" atau "DA-GAFS bekerja tanpa data target." Keduanya tidak benar.
- "Fitur yang berbalik arah harus dibuang." Hasil kami justru menunjukkan sebaliknya untuk model pohon.

## 6. Checklist sebelum presentasi
- [ ] Isi nama lengkap dan email kedua anggota di `manuscript/corrected/main.tex` dan `slides/slides.tex`, lalu kompilasi ulang.
- [ ] Anggota kedua melakukan commit sendiri ke repo (penilaian berdasarkan kontribusi commit).
- [ ] Latihan 15 menit dengan `slides/slides.pdf` (22 slide termasuk 2 backup; bagian DA-GAFS slide 13–17).
- [ ] Buka notebook pada Part 8 · RQ5/RQ6 (step 8.19–8.36) sebagai demo bila diminta.
