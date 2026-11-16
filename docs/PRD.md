# PRD Riset Deteksi URL Phishing Lintas Dataset

Versi 1.0 • 15 November 2026 • Status spesifikasi implementasi dan protokol kandidat yang harus dibekukan sebelum eksperimen final

Catatan administratif 16 November 2026: instruksi pengguna terbaru memperbolehkan **dua paper utama**
untuk tugas (D-26); ketentuan sepuluh paper pada lampiran lama tidak dipakai. Pengguna menegaskan
usia 3–5 tahun tetap berlaku: **R15 (2022) dan R2 (2024)** menjadi paper utama aktif pada audit
publikasi D-33, menggantikan pasangan sementara R2/R5 (D-29). R1 (2019) hanya provenance internal
asal EBBU; bibliography aktif mengikuti pembatasan umur pada `PRD (1).md` v1.1. Satu jurnal per classifier
tidak tercantum dalam lampiran yang diterima. Rincian kepatuhan usia paper dan posisi kontribusi ada di
`docs/project_positioning.md`. Catatan ini memperjelas deliverable, tanpa mengubah eksperimen beku v1.

## 1 Keputusan dan tujuan

Bangun paket riset Python berbasis CLI untuk membandingkan Random Forest dan LightGBM pada EBBU-2017 dan HISPAR–Phishstats. Terapkan tiga kondisi fitur: seluruh fitur, seleksi konvensional, dan seleksi berbasis kestabilan sumber. Uji secara internal dan lintas dataset dua arah. Ukur kualitas deteksi, penurunan transfer, biaya komputasi, serta atribusi model. Implementasi ditujukan untuk pengembangan dengan agent AI di VS Code, dengan keputusan ilmiah, kontrak data, pengujian, serta jejak hasil yang eksplisit.

PRD menjamin aturan kerja dapat diperiksa; PRD tidak menjamin peningkatan metrik, novelty, penerimaan jurnal, atau performa lapangan. Semua hasil masih belum tersedia. Nama metode usulan adalah nama kerja, bukan klaim algoritme baru. Proyek ini merupakan studi empiris dengan protokol dan ablation yang ketat; posisikan sebagai kontribusi metodologi baru hanya jika literature gate membuktikan pembeda yang cukup.

Judul kerja konservatif: Source Only Feature Selection for Lightweight Phishing URL Detection with Bidirectional Cross Dataset Evaluation. Tambahkan Explainable jika analisis SHAP selesai dan batasi maknanya pada atribusi keputusan model.

## 2 Ruang lingkup yang disepakati

| Komponen | Keputusan v1 |
|---|---|
| Dua classifier | RandomForestClassifier dan LGBMClassifier |
| Dua sumber data | EBBU-2017 asli serta HP dari repositori Rashid dan rekan |
| Task | Binary phishing URL classification; 1 phishing, 0 benign |
| Representasi | 37 fitur lexical numerik deterministik dari string URL |
| Selektor | ALL, MEAN_PI, STABLE_PI |
| Evaluasi | A internal, A ke B, B internal, B ke A |
| Setting utama | Source-only; tidak ada adaptasi menggunakan target |
| Interface | CLI, konfigurasi YAML, artefak JSON/CSV/Parquet |
| Platform | Windows VS Code sebagai target pengguna, Linux CI sebagai tambahan |
| Perangkat awal | CPU, thread dibatasi; GPU tidak diperlukan oleh desain |
| Hasil | Manuskrip, kode, konfigurasi, audit data, prediksi, metrik, grafik |

Tidak termasuk v1: deployment web, scraping halaman, DNS/WHOIS/reputasi live, HTML, deep learning, stacking tambahan, UDA implementation, SMOTE, hyperparameter optimization besar, deteksi zero-day, eksperimen temporal tanpa timestamp yang sah, benchmark adversarial. Ekstensi membutuhkan protokol versi baru sebelum test dibuka.

## 3 Pertanyaan riset dan klaim

RQ1: seberapa jauh RF dan LightGBM turun ketika diuji pada sumber lain dengan domain terpisah?
RQ2: apakah STABLE_PI mengubah performa transfer dibanding MEAN_PI pada jumlah fitur sama dan ALL?
RQ3: apakah pengurangan fitur menghasilkan pengurangan biaya ekstraksi atau inference yang terukur?
RQ4: fitur apa yang diandalkan model, dan bagaimana ranking atribusinya berbeda pada sampel sumber dan target?

H1 kandidat: STABLE_PI meningkatkan F1 phishing transfer dibanding MEAN_PI. H0 tidak ada peningkatan konsisten. H2 kandidat: subset mengurangi biaya end-to-end. H3 eksploratif: ranking fitur sumber yang stabil berkaitan dengan transfer yang lebih baik. Tidak mengasumsikan H1 sampai H3 benar. Korelasi SHAP dengan hasil bukan hubungan kausal.

Ukuran efek yang dipra-tetapkan untuk diskusi praktis: 0.01 absolute F1 dan 10 persen relative median end-to-end latency. Ini ambang interpretasi yang dipilih peneliti, bukan standar bidang atau batas signifikansi. Hasil kecil dan negatif tetap dilaporkan.

## 4 Status bukti dan koreksi referensi

[R1] Sahingoz et al., Machine learning based phishing detection from URLs, Expert Systems with Applications, 2019, DOI 10.1016/j.eswa.2018.09.029. Landasan baseline dan asal EBBU.
[R2] Rashid et al., Phishing URL detection generalisation using Unsupervised Domain Adaptation, Computer Networks 245, 2024, 110398, DOI 10.1016/j.comnet.2024.110398. Landasan transfer dan asal HP; algoritme UDA tidak direplikasi dalam v1.
[R3] Ke et al., LightGBM A Highly Efficient Gradient Boosting Decision Tree, NeurIPS 2017. Referensi algoritme; ini proceedings, bukan artikel jurnal Q1/Q2.

Keputusan RF + LightGBM adalah perubahan dari pasangan RF + UDA sebelumnya. Jangan menyatakan LightGBM sebagai metode utama R2. Jika aturan kampus mensyaratkan dua artikel jurnal utama yang masing-masing mendasari satu classifier, tambahkan artikel phishing LightGBM yang relevan dan diverifikasi melalui literature gate. Requirement ini BELUM selesai, meskipun landasan algoritme LightGBM tersedia. Jangan mengganti R2 atau mengarang referensi untuk menutupnya.

Ditemukan studi sangat dekat [R4] Cross-Dataset Feature Stability Selection for Generalizable Phishing URL Detection, DOI 10.37745/ejcsit.2013/vol14n570106 dan [R5] XGBoost-Based URL Phishing Detection Method With Cross-Dataset Validation, DOI 10.1109/ACCESS.2026.3672690. Studi tersebut membuat klaim umum stabilitas fitur + cross-dataset tidak cukup sebagai novelty. Baca metode lengkap, identifikasi penggunaan target, unit split, dan efisiensi. Tidak menyimpulkan kelemahan mereka hanya dari abstrak. Status quartile studi pembanding tidak diasumsikan.

## 5 Protokol riset literatur sebelum development final

Lakukan penelusuran terstruktur, bukan mengklaim systematic review lengkap tanpa dokumentasi. Gunakan sumber penerbit/DOI, Scopus bila ada akses, IEEE, ACM, ScienceDirect, Springer dan sumber algoritme resmi. Mesin pencarian hanya untuk discovery.

Rentang awal 2019 sampai tanggal pencarian, plus referensi foundational. Bahasa Inggris. Query families: phishing URL AND cross-dataset; source-only AND phishing; feature stability AND URL; domain-disjoint phishing; lexical LightGBM phishing; explanation stability URL; URL feature selection computational cost. Ulangi dengan sinonim domain generalization, source bias, distribution shift, registered-domain split. Catat query, tanggal, mesin, jumlah hasil yang diperiksa dan alasan berhenti. Lakukan backward dan forward citation search dari R1, R2, R4, R5.

Kriteria inklusi: URL classification, metode/data/evaluasi dapat diperiksa, relevan dengan transfer/seleksi/efisiensi/penjelasan. Keluarkan artikel hanya email/image tanpa komponen URL yang relevan. Dedup DOI, lalu judul + penulis. Pisahkan preprint, proceedings, data paper dan jurnal. Periksa koreksi/retraction pada halaman penerbit sebelum menjadikannya referensi utama.

Ekstraksi per paper: identitas; versi; status full text; dataset dan tahun; raw URL tersedia; fitur online/offline; label; split URL/domain/time; overlap; penggunaan target saat pemilihan; baseline; tuning budget; metrics; confidence interval; cost hardware; SHAP model asli/surrogate; code/data license; klaim dan bukti. Setiap penilaian terkait halaman/tabel tertentu; gunakan UNKNOWN untuk yang tidak dinyatakan.

Gate LIT: gap_matrix.csv minimal mencakup R1 sampai R5 serta studi terbaru yang paling dekat; semua pembeda yang diusulkan harus dipetakan ke bukti. Tidak menetapkan novelty berdasarkan jumlah paper. Jika pendekatan identik telah ada, ubah framing menjadi audit/replikasi/benchmark yang transparan atau rumuskan pembeda yang substantif sebelum test. Jika tidak dapat memperoleh full text, tandai batas penilaian dan jangan mengklaim sudah mengauditnya.

## 6 Pengadaan data dan bukti akses

A: https://github.com/ebubekirbbr/pdd . Tree repositori diperiksa pada sesi ini melalui API GitHub; ditemukan input/data_legitimate_36400.json dan input/data_phishing_37175.json. Jumlah 36,400 dan 37,175 adalah expected berdasarkan publikasi/nama file, belum hasil audit seluruh isi.
B: https://github.com/fariza25/PhishingURLDetection . Tree diperiksa; ditemukan Datasets/hp_train.csv, hp_valid.csv, hp_test.csv, juga salinan ebbu dan iscx. Hanya keluarga hp dipakai sebagai B; jangan menganggap semua file CSV sebagai dataset HP. Datasets/data.csv berukuran satu byte pada tree yang diperiksa dan bukan pengganti HP. Expected HP 92,500 berdasarkan paper; konfirmasi jumlah aktual dan skema.

Rekonstruksi B dengan menggabungkan hp_train, hp_valid, hp_test; simpan original_split sebagai provenance. Pembagian asli dipertahankan dalam provenance tetapi diulang untuk protokol domain-disjoint ini. Jelaskan perubahan di manuskrip; jangan menyebutnya reproduksi persis split R2. A gunakan JSON asli; salinan ebbu dalam repo B hanya untuk verifikasi opsional, bukan sumber ketiga.

Preview hp_train CSV pada sesi ini menunjukkan header kosong, index, url, label, Unnamed: 0. Adapter harus mengabaikan kolom indeks dan hanya mengambil url/label setelah mapping diverifikasi. Preview JSON legitimate A menunjukkan array string URL. Preview bukan audit seluruh berkas.

Data gate wajib: download nyata, file bukan HTML/error page, schema adapter benar, mapping label didukung paper/source, baris terhitung, SHA256 tersimpan, commit repositori dan URL permanen dicatat. Preview label tidak cukup untuk menentukan mapping. Jika metadata ambigu, blok training dan minta keputusan mapping berbukti. Jangan mengganti HP dengan PhiUSIIL diam-diam.

Lisensi source code tidak otomatis lisensi redistribusi data. Catat lisensi masing-masing dataset dan sumber. Jika tidak eksplisit, tandai belum jelas; paket publik berisi downloader/provenance dan bukan salinan data sampai hak distribusi jelas. Jangan menjalankan URL atau membuka domain yang tercantum dalam dataset. Semua ekstraksi offline.

## 7 Kontrak data

Raw immutable: data/raw/<source>/<commit>/<filename>. Download ke temporary file, validate lalu atomic rename. Jangan menimpa file raw berbeda hash. Manifest memiliki source_id, commit, url, retrieved_at, size, sha256, expected_records, observed_records, label_mapping_evidence dan license_status.

Canonical records Parquet: record_id:string, dataset_id:{A,B}, source_file:string, original_row:int, original_split:string|null, url_raw:string, url_key:string, label:int{0,1}, host_key:string, group_id:string, parse_status:string, parser_version:string. Record_id SHA256(dataset_id + source_file + original_row + raw URL) dengan serialization JSON canonical yang tetap, bukan string concatenation ambigu.

URL mentah dan label tidak dimasukkan ke model. URL/domain string, FILENAME, dataset_id, row index, original_split dan group_id tidak menjadi fitur. Prediksi menyimpan record_id dan group_id; raw URL hanya pada error analysis privat. Tidak ada target encoding, TLD legitimate probability dari label atau learned vocabulary dalam v1.

Data quality report: jumlah per tahap dan per kelas; missing, parse fail, duplicate, conflict, cross-source exact/domain overlap; ukuran grup maksimum dan distribusi; kelas per group. Alasan penghapusan dihitung tanpa double counting: priority reason tetap dan secondary flags terpisah.

## 8 Parsing dan normalisasi

Pertahankan url_raw apa adanya setelah decode file dengan encoding tercatat. Hanya hapus outer ASCII whitespace pada representasi kerja; jangan menghapus https/www/path/query, trailing slash, fragment, atau mengurutkan query. Jangan percent-decode URL untuk fitur atau dedup v1. Jangan memperpendek URL secara diam-diam.

Parser menerima http/https atau URL tanpa scheme yang memiliki host valid. Untuk parsing hostless, gunakan virtual // prefix; ini tidak mengubah string fitur asli. Protocol-relative // diterima dan diberi schememissing. Scheme lain, embedded CR/LF/NUL, port tidak sah atau host gagal diparse masuk quarantine dengan alasan. Tetapkan batas input 16,384 karakter; URL lebih panjang dikarantina dan dilaporkan sebagai batas cakupan, bukan dipotong. Angka ini keputusan implementasi v1 dan harus direview dengan distribusi panjang training sebelum freeze.

url_key untuk dedup: lower scheme dan host, IDNA host dengan kebijakan versi tetap, pertahankan case path/query/fragment, pertahankan explicit port termasuk default; hapus outer whitespace. Scheme yang tidak tercantum menggunakan penanda eksplisit, tidak dipaksa sama dengan http. Canonicalization konservatif ini tidak menangkap seluruh near-duplicate; akui batasnya.

group_id: registered domain dari PSL ICANN yang dibekukan; private suffix tidak dipakai untuk primary grouping supaya satu platform bersama tidak mudah bocor melalui subdomain. Semua blogspot.com berada pada grup konservatif blogspot.com. Laporkan kelompok besar dan sensitivitas private-suffix opsional sebagai eksperimen eksploratif setelah protokol utama. IP group menurut alamat IP kanonis. Host tanpa suffix memakai seluruh host. Hash untuk ID stabil. PSL snapshot dan library version wajib tercatat; disable fetch jaringan saat ekstraksi. IDNA rule dan parser fixture dibekukan.

## 9 Kebijakan dedup dan independensi

Urutan: parse; within-source dedup; label conflict quarantine; cross-source overlap audit; domain purge; split. Untuk url_key sama dan label sama simpan satu berdasarkan urutan source_file/original_row deterministik. Untuk url_key sama label berbeda, quarantine semua duplikat konflik pada kedua sumber sebelum analisis outcome. Domain dengan label campuran tidak otomatis konflik: URL berbeda pada domain yang sama dapat memiliki label berbeda.

Primary cohort: buang semua group_id yang muncul pada KEDUA sumber dari A dan B. Tujuan membentuk dua sumber dengan domain benar-benar terpisah; lakukan simetris agar arah transfer tidak memengaruhi cohort. Ini mengakses identitas target untuk audit overlap, bukan untuk mempelajari prediktor. Nyatakan sebagai curated domain-disjoint benchmark; bukan klaim target-blind acquisition absolut.

Laporkan cohort asli dan cohort bersih, distribusi sebelum/sesudah purge serta kehilangan platform populer. Jangan memilih kebijakan purge berdasarkan metrik. Bila purge membuang >50 persen salah satu kelas atau menyisakan <100 grup dalam salah satu kelas per sumber, tandai feasibility warning dan review sebelum freeze; tidak otomatis mengganti aturan. Jika test hanya satu kelas atau grup terlalu sedikit untuk split, gate gagal. Tidak menggabungkan dua sumber menjadi random split untuk hasil utama.

## 10 Split dan penguncian dua arah

Setiap sumber dibagi group-disjoint sekitar 60 persen FIT, 20 persen VAL, 20 persen TEST. Rasio target pada jumlah URL, tetapi penempatan utuh menurut group; rasio aktual boleh berbeda dan harus dilaporkan. Gunakan stratified group assignment deterministik; jangan paksa memecah grup besar. Simpan manifest membership record_id/group_id. split_seed=20261115 dan split algorithm version wajib tetap.

FIT: seleksi fitur, pengujian k internal, model fitting. VAL: hanya pilih threshold setelah selector/k/model dipilih. TEST: hasil akhir internal dan eksternal. Primary experiment mempunyai empat cells per konfigurasi: A FIT ke A TEST; A FIT ke B TEST; B FIT ke B TEST; B FIT ke A TEST. Model yang sama dipakai untuk dua test cells; tidak melatih ulang pada target. Source VAL tidak dimasukkan lagi ke final fitting agar threshold tetap berasal dari model yang sama.

Sebelum salah satu TEST dibuka, hasilkan dan hash protokol kedua arah, manifests, fitur, fixed hyperparameters, k candidates, seeds dan script evaluasi. Agen development tidak memiliki loader TEST labels. Evaluator membaca TEST sekali sebagai batch seluruh konfigurasi. Ini kontrol perangkat lunak/prosedural, bukan bukti kriptografis peneliti tidak pernah melihat label publik. Jangan mengklaim blinded evaluation absolut.

Jika test pernah dipakai sebelumnya untuk mengubah metode, beri status exploratory; freeze tidak menghapus pengetahuan sebelumnya. Perubahan metode setelah hasil final membutuhkan protocol_v2 dan holdout baru/third dataset, atau label eksploratif. Melatih arah B pada B FIT tetap sah karena B TEST disjoint; jangan memakai hasil A ke B untuk mengubah aturan arah B.

## 11 Kamus fitur v1

Seluruh fitur numerik float64/int64 finite; urutan dan feature_schema_hash tetap. Seluruh panjang menghitung Unicode code points pada string kerja, host memakai host ASCII IDNA tanpa trailing dot untuk grouping; host-feature representation gunakan aturan yang sama di semua sumber. Path/query/fragment diambil parser tanpa decoding. Delimiter ? dan # tidak masuk panjang komponennya. Zero division menghasilkan 0. Semua fitur berikut adalah rancangan penelitian, bukan daftar reproduksi lengkap R1.

| ID | Nama | Definisi |
|---|---|---|
| F01 | url_length | panjang string kerja |
| F02 | host_length | panjang host ASCII |
| F03 | path_length | panjang path |
| F04 | query_length | panjang query |
| F05 | fragment_length | panjang fragment |
| F06 | dot_count | jumlah literal . di seluruh URL |
| F07 | hyphen_count | jumlah literal - |
| F08 | underscore_count | jumlah literal _ |
| F09 | slash_count | jumlah literal / |
| F10 | at_count | jumlah literal @ |
| F11 | question_count | jumlah literal ? |
| F12 | equals_count | jumlah literal = |
| F13 | ampersand_count | jumlah literal & |
| F14 | percent_count | jumlah literal % |
| F15 | colon_count | jumlah literal : |
| F16 | digit_count | jumlah ASCII 0 sampai 9 |
| F17 | letter_count | jumlah ASCII a-z atau A-Z |
| F18 | digit_ratio | F16 dibagi F01 |
| F19 | nonascii_count | code point >127 pada string kerja |
| F20 | char_entropy | -sum p(c) log2 p(c), karakter string kerja |
| F21 | max_alnum_run | panjang run regex ASCII [A-Za-z0-9]+ terpanjang |
| F22 | host_label_count | jumlah label hostname nonkosong; IP bernilai 0 |
| F23 | subdomain_label_count | label host sebelum registered domain; IP 0 |
| F24 | host_digit_ratio | ASCII digits host dibagi panjang host |
| F25 | host_is_ip | ipaddress mendeteksi IPv4 atau IPv6 |
| F26 | explicit_port | 1 jika URL mencantumkan port |
| F27 | port_number | nomor explicit port; jika tidak ada 0 |
| F28 | has_userinfo | 1 bila netloc memiliki userinfo |
| F29 | has_query | panjang query >0 |
| F30 | is_https | scheme eksplisit case insensitive https |
| F31 | scheme_missing | tidak ada scheme eksplisit termasuk // |
| F32 | host_has_punycode | salah satu label host mulai xn-- |
| F33 | encoded_triplet_count | match tidak overlap %[0-9A-Fa-f]{2} |
| F34 | query_pair_count | jumlah segmen query nonkosong dipisah &; tidak decode |
| F35 | path_segment_count | jumlah segmen path nonkosong dipisah / |
| F36 | url_keyword_count | hit token keyword case insensitive pada seluruh string |
| F37 | host_keyword_count | hit token keyword case insensitive pada host |

Keyword dictionary tetap: login, signin, verify, account, secure, update, password, banking, confirm, wallet. Tokenize regex [A-Za-z]+ dan hit exact token; repeated token dihitung berulang. Daftar dipilih peneliti sebelum test, bukan dipelajari dari sumber/target. Tidak menggunakan allbrands.txt atau keywords.txt dataset A dalam v1 karena dapat memperkenalkan dependensi sumber. Jika dictionary diubah, feature version berubah.

Pengurangan fitur belum tentu pengurangan latency karena beberapa fitur berbagi parsing. Extractor harus mendukung dependency graph dan selected_features; hanya hitung entropy/keyword atau operasi lain jika diperlukan subset. Tetap ukur overhead parsing bersama. Schema ALL p=37; candidate k=[8,16,24]. Tidak memilih k=37 sebagai subset secara diam-diam.

## 12 Algoritme seleksi yang dapat diimplementasikan

Semua selector menggunakan RF proxy yang sama, n_estimators=200, max_depth=16, min_samples_leaf=2, max_features=sqrt, n_jobs terbatas, class_weight=null. Ini mengurangi bias perbedaan learner saat membandingkan selector, tetapi berpotensi menguntungkan RF terhadap LightGBM; akui dan pertimbangkan proxy kedua hanya sebagai sensitivity preregistered.

Fungsi fit_selector(FIT, groups, k): buat tiga fold stratified group di FIT; per fold fit proxy pada dua fold, hitung permutation importance pada fold ketiga memakai average_precision dengan label phishing=1 dan lima permutations. Tidak menggunakan VAL/TEST. Feature constant pada fold memiliki PI 0. PI negatif disimpan dan tidak diubah dalam laporan.

MEAN_PI: urutkan fitur berdasarkan mean signed PI di tiga folds, tie feature_id ascending; pilih k teratas. STABLE_PI: setiap fold mengurutkan PI, tie ID; vote_j jumlah fold saat fitur masuk top q=12 DAN PI_j>0. Urutkan tuple descending vote, descending median PI, ascending rank MAD, ascending feature_id; pilih k. MAD dihitung atas ranking fold, bukan nilai PI. q tetap 12 untuk semua k. Simpan raw PI per fold/repeat, votes, median, MAD dan selected IDs. Jika seluruh PI <=0, tetap deterministik tetapi tandai selector_degenerate; jangan menyatakan bukti stabilitas.

Ini kandidat heuristic yang transparan; bukan jaminan robust learning. Tiga fold adalah domain groups held-out, bukan tiga sumber independen atau environment fisik. Klaim dibatasi pada resampling domain dalam sumber.

Pemilihan k: tiga outer group folds di source FIT. Untuk setiap outer train dan k, jalankan fit_selector HANYA pada outer train menggunakan tiga inner folds; latih classifier tetap pada outer train subset; skor outer holdout average_precision dan F1 threshold 0.5. Pilih k berdasarkan mean outer AP: ambil k terkecil dalam 0.01 AP absolut dari best mean AP. Toleransi ini fixed. Tie k sama tidak mungkin; tie model configs tidak dipilih lintas model. Pilih k terpisah per source/classifier/selector. Setelah memilih k, fit_selector ulang di seluruh source FIT, lalu final classifier FIT subset.

ALL tidak memilih k. Hyperparameter classifier tetap sehingga CV outer digunakan hanya memilih k; skor outer bukan hasil generalisasi final. Selector fit yang dipakai validasi outer tidak boleh di-cache dari source FIT penuh. Ini invariance terpenting untuk mencegah feature selection leakage [R6,R7].

Matched-k comparison wajib: untuk masing-masing source/classifier/seed, gunakan k STABLE_PI yang terpilih dan buat model MEAN_PI tambahan dengan k itu jika berbeda dari k MEAN_PI terpilih. Jika sama, reuse model. Dengan ini efek stability dibandingkan pada kapasitas fitur sama. Laporkan juga hasil konfigurasi budget-selected masing-masing sebagai secondary; jangan mencampur kedua kontras.

## 13 Classifier dan sumber daya

RF final fixed: 300 trees, max_depth=20, min_samples_leaf=2, max_features=sqrt, bootstrap=true, class_weight=null, random_state=model_seed. LightGBM fixed: objective=binary, boosting_type=gbdt, n_estimators=300, learning_rate=0.05, num_leaves=31, max_depth=-1, min_child_samples=20, subsample=1.0, colsample_bytree=1.0, reg_lambda=1.0, class_weight=null. deterministic=true, force_col_wise=true pada CPU; random_state dan seeds pendukung dicatat. Tidak memakai early stopping di target. Jangan menyatakan fixed parameters sebagai hasil optimasi atau optimum [R8].

Model seeds [17,29,43]; split dan folds tetap untuk seed model, sehingga variasi yang diukur terutama estimator/PI randomness, bukan ketidakpastian seluruh sampling populasi. Jangan menjadikan tiga seed sebagai tiga dataset independen. Jika budget cukup, repeated split menjadi ekstensi pra-test, bukan ditambahkan untuk mencari signifikansi.

Threads maksimum min(4, CPU available), outer loop serial; tidak nested n_jobs=-1. Profil cepat untuk smoke memakai fixture sintetis, satu seed dan 20 trees; hasil tidak masuk manuskrip. Sebelum full run, hitung estimasi fit count dari DAG dan pilot pada FIT. Batasi jobs berdasarkan budget waktu lokal; timeout adalah failure yang dicatat, bukan metrik nol. Profil final memerlukan budget yang disepakati di config; nilai runtime tidak ditebak.

## 14 Threshold dan metrik

Primary outcome F1 phishing pada threshold source VAL yang dipilih memaksimalkan F1. Untuk setiap final model, prediksi source VAL; kandidat threshold semua unique scores dan finite sentinel nextafter(max_score,+infinity) yang memungkinkan all-negative; decision score>=threshold. Tie pilih threshold terbesar. Tidak refit setelah threshold selection. Laporkan juga F1 pada 0.5 sebagai sensitivity.

Secondary operating point: pilih threshold terendah pada source VAL dengan empirical FPR<=0.01 untuk memaksimalkan recall, tie threshold terbesar bila recall setara. Simpan actual benign denominator, FP count dan achieved FPR. Pada target laporkan achieved FPR dan recall menggunakan threshold sumber itu; jangan menamakannya target recall@1%FPR jika target FPR tidak 1%. ROC-derived target recall@1% boleh hanya sebagai exploratory diagnostic, tidak sebagai operational locked-threshold metric.

Metrik lain: precision phishing, recall phishing, specificity, MCC, balanced_accuracy, accuracy, ROC_AUC, AP dan confusion counts TN FP FN TP. AP menggunakan average_precision_score; jangan menyebut AP identik dengan trapezoidal PR-AUC [R9]. PR curve disimpan. Zero denominator precision=0 dengan explicit flag; AUC/AP dengan kelas tunggal tidak dipaksakan valid, evaluasi cohort utama gagal. Catat prevalence dan jumlah domain tiap test.

Transfer drop: F1(source TEST)-F1(target TEST), keduanya dari model dan threshold sumber sama; satuan percentage points bila dikali 100. Perbedaan class prevalence dan difficulty membuatnya deskripsi benchmark, bukan kausal murni domain shift.

## 15 Analisis statistik

Pre-specify primary contrast STABLE_PI versus MEAN_PI matched-k pada F1 phishing target untuk tiap classifier dan arah, total empat kontras. ALL comparisons secondary. Hitung delta per seed dan mean paired delta. Confidence interval menggunakan paired domain-cluster bootstrap pada TARGET TEST, 2,000 replicates, sampling domain dengan replacement dan membawa semua URL domain; pasangan prediksi dari model yang dibandingkan harus memakai sampel bootstrap identik. Pada setiap replicate hitung metric difference tiap seed lalu rata-ratakan; jangan concat tiga seed menjadi tiga kali baris independen.

Jika bootstrap replicate hanya satu kelas, skip dan catat; jika >5 persen invalid, tandai interval tidak stabil dan laporkan tanpa klaim kuat. Fixed split dan seed set berarti CI ini conditional pada model fits; tidak mencakup seluruh ketidakpastian training. Laporkan median ukuran cluster dan dominasi domain besar. URL-weighted metrics primary, domain-balanced weighted summaries secondary karena menjawab pertanyaan berbeda.

Hindari uji t dengan tiga seed atau folds berkorelasi. Default laporkan effect sizes dan empat CI tanpa klaim familywise significance. Jika manuscript mensyaratkan inferensi familywise, tambahkan simultaneous interval/prosedur multiple comparison yang dipra-tetapkan bersama reviewer statistik; jangan mengklaim Holm hanya dari percentile CI. Tidak memilih satu arah terbaik lalu mengabaikan lainnya.

## 16 Efisiensi dan penjelasan

Benchmark tiap final configuration pada mesin sama: catat CPU, OS, RAM, Python, paket, thread, power mode bila tersedia. Batch1 dan batch1024 diukur terpisah. Warmup 10, minimal 30 repeated batches memakai URL dari source VAL yang sama untuk seluruh model; ukur perf_counter_ns. Report median/p95 waktu per request batch dan normalized per URL yang diberi label jelas. Single-URL latency dan throughput batch tidak dipertukarkan.

Pisahkan parser+feature extraction, prediction-only, end-to-end. Cache off untuk end-to-end; precomputed features hanya untuk prediction-only. Selected-feature dependency pruning benar-benar aktif. File model size setelah serialization seragam, loading time, peak RSS baseline dan delta, training wall time serta total selection cost dicatat. SHAP latency dilaporkan terpisah. Tidak memasukkan SHAP ke latency deteksi kecuali pipeline produk memang menggunakannya setiap request. Definisikan lightweight relatif kepada ALL model yang sama dan hardware yang dilaporkan, bukan label universal.

SHAP: TreeExplainer pada classifier aktual, bukan surrogate; explicit feature_perturbation=interventional, background maksimal100 sampel source FIT yang dipilih seed tetap, model_output=probability jika kombinasi versi mendukung. Gunakan 500 sampel source TEST dan500 target TEST, stratifikasi label hanya untuk explanation analysis setelah freeze, laporkan kebijakan sampling. Jika API/version tidak mendukung output probability, ubah via keputusan terdokumentasi sebelum analisis; jangan diam-diam menukar log-odds dan probability [R10].

Validate kelas positif benar dan additivity terhadap score yang dijelaskan. Output abs mean ranking, beeswarm, contoh FP/FN yang dipilih aturan tetap, Spearman rank correlation dan top10 Jaccard antar cohort. Same model, same background untuk perbandingan source-target. Cross-cohort attribution differences bukan otomatis ketidakstabilan/ketidaksetiaan penjelasan karena distribusi input berubah. Stability antar seed pada cohort sama laporkan terpisah; tidak klaim trust manusia/causality tanpa evaluasi lain.

## 17 Arsitektur dan kontrak modul

Package src/phishresearch. CLI sebagai entry point tunggal. Notebook hanya eksplorasi FIT dan visualisasi artefak; bukan sumber logika final. Agent tidak membuat UI sebelum core research lulus.

| Modul | Input | Output | Invariant |
|---|---|---|---|
| acquire | dataset registry | raw + manifest | hashes, provenance |
| adapters | raw source files | canonical records | mapping label eksplisit |
| audit | canonical records | audit.json + quarantine | reason counts |
| cohort | records + policy | cohort records | symmetric purge |
| splits | cohort + seed | splits.parquet | group disjoint |
| features | URL + schema | X parquet | 37 finite features |
| selection | FIT X,y,groups,k | selector.json | no VAL/TEST reads |
| training | FIT, selector, params | model bundle | column order fixed |
| thresholds | final model + source VAL | thresholds.json | no target reads |
| freeze | protocol + run plan | freeze manifest | immutable hashes |
| evaluation | frozen bundles + TEST | predictions + metrics | no fit APIs |
| analysis | predictions | tables, CIs, SHAP | no model changes |
| reporting | verified artifacts | tables/figures/manuscript data | traceable values |

Required functions with typed interfaces: load_dataset(adapter, manifest); canonicalize_url(raw)->ParsedURL|Quarantine; make_group_splits(records,config)->SplitManifest; extract_features(urls,selected_ids)->FeatureMatrix; fit_selector(X,y,groups,k,seed)->SelectorArtifact; fit_model(X,y,config)->ModelBundle; choose_threshold(y_val,scores,policy)->ThresholdArtifact; evaluate_frozen(bundle,test,threshold)->EvaluationArtifact. Reject unknown feature IDs and extra model input columns. Avoid implicit global state.

## 18 Repository structure dan CLI

Repository target:
- pyproject.toml, exact dependency lockfile, README.md, AGENTS.md
- configs/protocol.yaml, configs/datasets.yaml
- docs/PRD.md, sources.md, decisions.md, risk_register.md, literature/gap_matrix.csv
- src/phishresearch/{acquire,adapters,urls,cohort,splits,features,selection,models,thresholds,freeze,evaluation,statistics,explain,benchmark,reporting,cli}.py
- schemas/*.schema.json
- tests/unit, tests/integration, tests/invariants; fixtures menggunakan reserved example.test domains
- data/raw, data/processed, artifacts/runs/<run_id>, manuscript; raw dan hasil berat gitignored

Target CLI (belum diimplementasikan pada paket PRD):
python -m phishresearch.cli acquire --registry configs/datasets.yaml
python -m phishresearch.cli audit --config configs/protocol.yaml
python -m phishresearch.cli prepare --config configs/protocol.yaml
python -m phishresearch.cli smoke --synthetic
python -m phishresearch.cli develop --source A --config configs/protocol.yaml
python -m phishresearch.cli develop --source B --config configs/protocol.yaml
python -m phishresearch.cli freeze --config configs/protocol.yaml
python -m phishresearch.cli evaluate --freeze artifacts/freeze.json
python -m phishresearch.cli analyze --freeze artifacts/freeze.json
python -m phishresearch.cli report --freeze artifacts/freeze.json

CLI evaluate menolak missing freeze, mismatch hash, TEST overlap, bundle yang tidak memiliki source ID, dan label positif selain1. Resume hanya artefak hash cocok; model file tidak dipercaya dari pihak luar. Setiap command return nonzero pada gate failure dan menjelaskan artefak diagnostik.

## 19 Model bundle dan jejak hasil

Bundle berisi serialized model, ordered feature IDs, extractor/parser/PSL hashes, selector, source dataset/cohort/split hashes, seeds, params lengkap, thresholds, package lock hash, git commit, fit record IDs hash dan tanggal. record_id list hash dapat diverifikasi; jangan menulis raw URL ke log.

predictions.parquet: run_id, seed, source, target, model, selector, budget_type, k, record_id, group_id, y_true, score_phishing, threshold_policy, threshold, y_pred. Simpan satu score per record/model lalu threshold decisions dapat tabel terpisah untuk efisiensi; bila format panjang, unique key mencakup threshold_policy.

metrics.json: schema_version, run provenance, n_rows,n_domains,prevalence,TN,FP,FN,TP,metric names, threshold policy, values, warnings. Setiap tabel publik memiliki cell provenance ke run_id + metric + source/target/seed/selector. Reporting tidak mengetik angka manual. results registry immutable dengan status planned/running/completed/failed/incomplete; tidak mengisi missing result dengan angka nol.

## 20 Pengujian wajib untuk agent

U01 parsing: scheme absent, uppercase host, case sensitive path, IDNA, IPv4/6, userinfo, explicit default port, percent encoding, malformed input, embedded newline, query empty. Expected ditentukan manual pada fixture reserved, tidak menyalin implementation.
U02 exact feature: panjang, counts, entropy string sederhana, query segmentation, keyword token boundaries; selected extractor sama dengan ALL projection untuk setiap subset.
U03 labels: file source mapping terbukti, pos_label=1, probabilitas kolom classes_ yang benar walau urutan berbeda.
U04 metric: confusion kecil hand-calculated; threshold ties; source FPR exact; single-class behavior.
I01 no leakage: injected heldout-only feature tidak boleh mengubah selected subset sebelum final evaluation; selector provenance hanya FIT/inner training. Custom estimator spy memastikan fit IDs tidak menyentuh outer holdout/VAL/TEST.
I02 group purge dan partitions: nol group intersection antar sumber sesudah purge serta FIT/VAL/TEST; konflik seluruhnya quarantine.
I03 nested selection: cached selector outer train harus memiliki ID hash berbeda dari source-full selector, validation groups disjoint.
I04 freeze tamper: modifikasi satu config byte/model/split menghasilkan evaluasi ditolak.
I05 deterministic: input shuffled menghasilkan canonical ordering/split sama; rerun satu seed menghasilkan prediksi sesuai toleransi CPU yang ditetapkan.
I06 metric recomputation: laporan cocok dengan predictions, confusion totals sama n, tak ada duplicate key.
I07 offline extraction: socket/network monkeypatch fail jika extractor mencoba jaringan; PSL lokal tersedia.
I08 CLI integration pada synthetic dua sumber; gate tidak melabeli synthetic sebagai scientific result.
I09 SHAP additivity dan output class; benchmark selected features benar-benar tidak menghitung operasi yang tidak diperlukan.

CI: lint, type checking ringan, unit/invariants, small integration. Full real dataset run tidak wajib di setiap commit. User mengotorisasi verifikasi pada task PRD; implementasi berikutnya harus menjalankan tes relevan sebelum milestone dinyatakan selesai.

## 21 Acceptance criteria

AC01 kedua data terunduh dengan source commit, hash dan observed counts; label mapping jelas.
AC02 cohort/split group intersections nol; quarantine dan attrition bisa direkonsiliasi.
AC03 extractor37 dan subset equivalence lulus; tidak ada forbidden metadata input.
AC04 semua fit/selection/tuning dalam partisi yang diizinkan; outer validation tidak masuk seleksi inner.
AC05 dua model, tiga kondisi dan empat evaluation cells lengkap, matched-k tersedia.
AC06 kedua arah frozen sebelum final results; setiap perubahan memiliki protocol version.
AC07 metrik dapat dihitung ulang persis dari saved predictions; probability kelas phishing benar.
AC08 runtime/size/SHAP dilaporkan sesuai scope; klaim lightweight menunggu bukti.
AC09 sumber dan literature gate diverifikasi; novelty tidak diasumsikan.
AC10 manuskrip semua angka berasal artefak; hasil negatif dan keterbatasan ditulis.

Tidak ada acceptance berupa accuracy>=99 persen, peningkatan wajib atau diterima Q1. Engineering success terpisah dari research outcome. Jika STABLE_PI kalah, proyek dapat selesai sebagai evaluasi negatif yang jujur.

## 22 Milestone dan workflow agentic AI

M0 Literature and Data Feasibility: verifikasi dataset bytes + skema + license, paper LightGBM pendukung bila diperlukan, gap matrix dan keputusan kontribusi. Exit: tidak ada blocking UNKNOWN.
M1 Foundation: environment, package, schemas, fixtures, raw manifests, offline parser. Exit: U01 sampai U03.
M2 Data Protocol: cohort, splits, features, lineage. Exit: AC01 sampai AC03.
M3 Models and Selection: baseline fixed, selectors, nested k, thresholds, estimasi compute. Exit: I01 I03, output validation sumber tanpa TEST.
M4 Freeze: kedua arah dan semua ablations disusun; review author untuk keputusan ilmiah final. Review freeze merupakan kontrol peneliti, bukan permintaan izin setiap edit. Exit: manifest ditandatangani author/peneliti dan hash tercatat.
M5 Final Evaluation: seluruh run plan batch; failure dicatat; retry hanya config identik untuk kegagalan teknis. Exit: AC05 sampai AC07.
M6 Analysis and Manuscript: CIs, biaya, SHAP, diskusi, reproducibility package. Exit: AC08 sampai AC10.

Estimasi awal enam sampai delapan minggu paruh waktu setelah feasibility; bukan janji. M0 bisa mengubah jadwal. Agent mengerjakan satu milestone, memperbarui TASKS.md dan evidence log, menjalankan checks, lalu commit kecil jika git tersedia. Agent tidak menandai phase done hanya karena file dibuat. Dilarang mengubah hipotesis setelah melihat hasil atau menghapus failed runs agar tabel rapi.

## 23 Penulisan jurnal dan pelacakan klaim

Introduction: masalah source shift, konsekuensi false alarm, batas existing evidence; jangan memakai statistik serangan tanpa sumber tepat.
Related Work: R1/R2 foundation, studi stability terdekat dan biaya/interpretability; perbandingan berbasis protokol bukan hanya akurasi paper berbeda.
Methods: cohort attrition, label mapping, PSL/grouping, fitur37, selector formula, fixed parameters, nested k, freeze, threshold, seeds, bootstrap, benchmark.
Results: data audit terlebih dahulu, semua internal/cross, matched-k, deltas dan uncertainty, cost, SHAP dan error types.
Discussion: mengapa mungkin gagal/berhasil, source bias, old datasets, overlap purge selection effect, proxy RF bias, correlated features, prevalence, representativeness, penjelasan bukan kausal.
Conclusion: menjawab RQ dengan hasil aktual; tidak mengklaim deployment reliability, zero-day, temporal robustness atau privacy guarantees tanpa uji.
Data/code availability: sumber, commit, lisensi, downloader, lockfile, command, manifests. Abstract terakhir; jangan membuat angka perkiraan sebagai hasil.

Setiap klaim memiliki claim_id, wording, evidence artifact/source, status verified/inferred/unknown dan lokasi manuskrip. Klaim Q1/Q2 harus menyebut sistem/tahun/kategori dan diverifikasi ulang saat submission; peringkat bukan bukti validitas artikel. Artikel R2 bukan metode LightGBM dan studi ini bukan replikasi persis R1/R2.

## 24 Risiko dan keputusan terbuka

| Risiko | Mitigasi | Trigger |
|---|---|---|
| HP schema/label berbeda dugaan | adapter berbukti; sample manual | M0 block |
| Data license tidak jelas | link/downloader, tanpa redistribusi | release data block |
| Purge menghapus banyak benign | attrition report, review sebelum freeze | feasibility warning |
| Domain besar mendominasi | cluster bootstrap, domain-balanced secondary | dominance report |
| Novelty dekat existing | gap matrix + full text comparison | framing review |
| Correlated features menekan PI | correlation matrix FIT dan batas interpretasi | discussion |
| Selektor proxy bias ke RF | same proxy disclosed; optional fixed sensitivity | no silent change |
| Overhead fitur dominan parsing | benchmark nyata dependency pruning | lightweight claim fails |
| Dataset tua | batasi klaim pada benchmark | no contemporary claim |
| Agent melihat TEST saat development | loader policy + freeze + audit | exploratory flag |
| Dependency/PSL berubah | exact lock/hash dan offline mode | rerun version |
| Tiga seeds terlalu sedikit | CI conditional dan laporkan raw per seed | no seed t-test |

Pending keputusan: verifikasi original label schemas, full raw acquisition, exact environment pins setelah install, kebutuhan dua artikel jurnal utama classifier, full-text novelty audit, pilihan jurnal target. Pending bukan alasan mengarang detail. Modul yang tidak bergantung padanya boleh dibangun; training final diblok sampai data gate selesai.

## 25 Sumber dan batas protokol

Referensi lengkap dan URLs tersedia di docs/SOURCES.md. Desain split60/20/20, fitur37, hyperparameters fixed, toleransi0.01, budget k, q12, bootstrap2000 dan acceptance di dokumen ini adalah keputusan usulan peneliti; bukan ketentuan yang dinyatakan paper sumber. Bekukan setelah feasibility dan review. Paket ini spesifikasi/handoff; tidak berisi hasil training atau implementasi pipeline yang sudah selesai.


## 26 Kontrak implementasi tambahan

Schemas JSON dalam paket adalah kontrak awal. Implementasi harus menambahkan validasi lintas field: TN+FP+FN+TP=n_rows; score_phishing finite di [0,1]; jumlah domain cocok; metrics recomputed dari predictions; threshold finite boleh >1 untuk all-negative sentinel; dan unique key lengkap. Jangan menganggap JSON Schema saja menjamin seluruh invariant ilmiah. Contoh template config mengandung null yang sengaja membuat gate freeze gagal sampai provenance terisi.

HP reconstruction tidak menggabungkan original_split sebagai fitur. Dataset counts 92,500 dan 73,575 adalah expected; observed counts wajib menggantikannya dalam Methods. Tuliskan adapter unit test yang mendeteksi perubahan header dan indeks tambahan.

Literature review dan dataset validation dapat mengubah desain sebelum freeze. Semua perubahan harus mempunyai alasan berbukti; struktur PRD bukan perintah mempertahankan desain yang ternyata tidak layak.
