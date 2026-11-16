# Penilaian kandidat R15 dalam PRD v1.1

Tanggal kajian: 16 November 2026. Permintaan ini menilai kelayakan kandidat dalam
`PRD (1).md`, bukan mengganti model, dataset atau hasil eksperimen beku.

**Keputusan: R15 layak sebagai paper utama pengganti R1, dengan batas peran yang jelas.**
Pasangan yang direkomendasikan untuk arah PRD tersebut adalah R15 (2022) + R2 (2024).
Pada audit publikasi berikutnya (D-33), naskah/notebook dimigrasikan ke R15/R2; artefak
penilaian kandidat sebelumnya tetap dipertahankan sebagai riwayat, bukan ditulis ulang.

## Identitas dan kelayakan umur

Manuel Sánchez-Paniagua, Eduardo Fidalgo Fernández, Enrique Alegre, Wesam Al-Nabki,
Víctor González-Castro, “Phishing URL Detection: A Real-Case Scenario Through Login URLs,”
*IEEE Access*, vol. 10, pp. 42949–42960, 2022,
[DOI](https://doi.org/10.1109/ACCESS.2022.3168681).

Tanggal publikasi pada halaman pertama PDF adalah **18 April 2022**. Paper berada dalam
jendela lima tahun 16 November 2021–16 November 2026, tetapi di luar prioritas tiga tahun.
R2 terbit Mei 2024 dan masuk keduanya. Tidak ada syarat artikel harus berumur minimal
tiga tahun. Klaim Q1/SJR 2024 dalam PRD belum diverifikasi secara independen pada audit ini.

## Bukti kesesuaian metode

| Pertanyaan | Temuan | Lokasi bukti |
|---|---|---|
| Apakah RF/LightGBM dipakai? | Ya, keduanya termasuk classifier yang dievaluasi | §IV-A, PDF hlm. 6 |
| Apa representasinya? | Jalur handcrafted memakai 38 fitur; jalur lain memakai TF-IDF/n-gram | §IV-A |
| Apakah RF/LightGBM terbaik secara keseluruhan? | Tidak; laporan keseluruhan mengunggulkan jalur TF-IDF/n-gram + LR | §VI-A dan Table 6 |
| Dataset asal paper? | PILU-90K dengan subset PLU-60K dan PIU-60K; EBBU juga dipakai sebagai pembanding | §III dan §V-A |
| Apakah paper sudah membahas pergeseran evaluasi? | Ya, termasuk representativitas login dan pengujian lintas waktu | §V–VI |

Full PDF tersedia dari repositori institusi, dan bagian metode/hasil relevan sudah diperiksa.
Jangan memakai salinan bertajuk serupa dengan DOI/penulis lain sebagai paper yang sama.

## Peran pasangan yang dapat dipertanggungjawabkan

* **R15 (2022):** mendukung alasan memilih RF/LightGBM sebagai classifier URL yang sudah
  diteliti, sekaligus memotivasi perhatian terhadap representativitas data dan false positives.
* **R2 (2024):** mendasari masalah transfer lintas sumber dan pembanding konseptual UDA;
  tidak boleh disebut mengusulkan LightGBM.

Keduanya cukup untuk sebuah **studi aplikasi/perluasan evaluasi**. Jika dosen menghendaki
reproduksi metode utama satu-per-paper, desain RF/LightGBM saat ini belum memenuhi makna
itu: metode unggulan R15 adalah LR berbasis TF-IDF dan metode R2 adalah UDA. Instruksi tugas
yang diterima tidak secara eksplisit mewajibkan reproduksi satu-per-paper.

## Gap yang tetap sejalan

Pertanyaan proyek tetap: pada seleksi dari domain sumber saja, apakah stabilitas PI
mengubah transfer dibanding rata-rata PI pada jumlah fitur sama, dengan domain terpisah,
threshold sumber terkunci, dan biaya yang diukur? Ini rumusan pertanyaan eksperimen proyek,
bukan klaim bahwa R15 atau R2 tidak pernah membahas generalisasi. Tidak mengklaim algoritme
baru, keberhasilan temporal, login-specific detection, atau keunggulan atas paper asal.

Eksperimen proyek tetap memakai 37 fitur dan EBBU/HP. Perbedaan dari fitur/dataset R15 harus
diterangkan; mengganti judul rujukan tidak mengubah data lama menjadi baru. Migrasi ke PILU
akan mengubah cohort dan protokol beku, sehingga membutuhkan versi/holdout baru atau hasil
yang diberi label exploratory. Kebutuhan itu tidak berlaku jika perubahan hanya editorial.

## Batas kesiapan dan provenance

R15 memenuhi umur dan relevansi, tetapi belum menutup full-text review R2, validasi label HP,
warning SHAP, ataupun kelengkapan submission. PRD v1.1 juga tidak memberi pengecualian
otomatis bagi semua rujukan klasik; daftar pustaka aktif perlu diselaraskan sebelum
dinyatakan mengikuti aturan tersebut. Pertahankan asal EBBU dalam manifest/provenance
internal walaupun artikel 2019 tidak dihitung sebagai paper utama.

PDF: `docs/literature/papers/R15_SanchezPaniagua2022_LoginURLs_IEEEAccess.pdf`.
Sumber: repositori Universidad de León, endpoint server API pada `acquisition.json`.
SHA256: `a17f6266a9ada4888ad7c29c1e3864860435ea215c60a7c022f212d6cf21c649`.
Crossref: `artifacts/literature_candidate_2022/crossref.json`.
Tidak membuka, mengunduh, atau me-resolve URL sampel dataset.
