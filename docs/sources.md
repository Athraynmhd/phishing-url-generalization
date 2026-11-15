# Sources

Diverifikasi 2026-11-15 melalui Crossref/OpenAlex/Semantic Scholar (metadata) dan halaman penerbit.
Status quartile **tidak** diasumsikan; verifikasi ulang saat submission.

| ID | Referensi | DOI / URL | Full text | Lisensi artikel |
|---|---|---|---|---|
| R1 | O. K. Sahingoz, E. Buber, O. Demir, B. Diri, "Machine learning based phishing detection from URLs," *Expert Systems with Applications*, vol. 117, pp. 345–357, 2019. | 10.1016/j.eswa.2018.09.029 | Tidak diperoleh (paywall; handle OA `hdl.handle.net/11424/94241` HTTP 500) | Elsevier |
| R2 | S. Rashid, B. Doyle, S. C. Han, S. Seneviratne, "Phishing URL detection generalisation using Unsupervised Domain Adaptation," *Computer Networks*, vol. 245, 110398, 2024. | 10.1016/j.comnet.2024.110398 | Tidak diperoleh otomatis (unduh manual dari ScienceDirect) | CC BY 4.0 |
| R3 | G. Ke *et al.*, "LightGBM: A highly efficient gradient boosting decision tree," *NeurIPS*, 2017. | proceedings.neurips.cc (paper 6449f44a…) | `docs/literature/papers/R3_Ke2017_LightGBM_NeurIPS.pdf` | NeurIPS |
| R4 | R. Z. J. Kanon, K. Sohan, M. S. Islam, M. G. Murtuza, "Cross-Dataset Feature Stability Selection for Generalizable Phishing URL Detection: A Comparative Study of Classical Ensembles and Deep Learning," *Eur. J. Comput. Sci. Inf. Technol.*, vol. 14, no. 5, pp. 70–106, 2026. | 10.37745/ejcsit.2013/vol14n570106 | `docs/literature/papers/R4_Kanon2026_StabilitySelection_EJCSIT.pdf` | penerbit OA |
| R5 | M. Misiek, T. Hyla, "XGBoost-Based URL Phishing Detection Method With Cross-Dataset Validation," *IEEE Access*, vol. 14, pp. 43200–, 2026. | 10.1109/ACCESS.2026.3672690 | `docs/literature/papers/R5_Misiek2026_XGBoost_Access.pdf` | CC BY 4.0 |
| R6 | C. Ambroise, G. J. McLachlan, "Selection bias in gene extraction on the basis of microarray gene-expression data," *PNAS*, 99(10), 2002. | 10.1073/pnas.102102699 | rujukan metodologi (leakage seleksi fitur) | — |
| R7 | S. Varma, R. Simon, "Bias in error estimation when using cross-validation for model selection," *BMC Bioinformatics*, 7:91, 2006. | 10.1186/1471-2105-7-91 | rujukan metodologi (nested CV) | CC BY |
| R8 | J. Bergstra, Y. Bengio, "Random search for hyper-parameter optimization," *JMLR*, 13, 2012. | jmlr.org/papers/v13/bergstra12a | rujukan (parameter tetap ≠ optimum) | — |
| R9 | J. Davis, M. Goadrich, "The relationship between precision-recall and ROC curves," *ICML*, 2006. | 10.1145/1143844.1143874 | rujukan (AP ≠ PR-AUC trapesium) | — |
| R10 | S. M. Lundberg *et al.*, "From local explanations to global understanding with explainable AI for trees," *Nature Machine Intelligence*, 2, 2020. | 10.1038/s42256-019-0138-9 | rujukan TreeExplainer | — |
| R11 | L. Breiman, "Random forests," *Machine Learning*, 45, 2001. | 10.1023/A:1010933404324 | rujukan algoritme RF | — |
| R12 | A. Altmann *et al.*, "Permutation importance: a corrected feature importance measure," *Bioinformatics*, 26(10), 2010. | 10.1093/bioinformatics/btq134 | rujukan PI | — |
| R13 | N. Meinshausen, P. Bühlmann, "Stability selection," *JRSS-B*, 72(4), 2010. | 10.1111/j.1467-9868.2010.00740.x | rujukan prinsip stabilitas | — |

R6–R13 adalah referensi metodologi/fondasi yang dirujuk PRD (R6–R10) atau manuskrip; metadata DOI wajib dicek ulang sebelum submission.

## Dataset

| Sumber | Repo @ commit | File | Lisensi data |
|---|---|---|---|
| A EBBU-2017 | `ebubekirbbr/pdd@90b394d8f9fb5d5dc48400e8bf46b001ce42999f` | `input/data_legitimate_36400.json`, `input/data_phishing_37175.json` | Repo tanpa LICENSE → **belum jelas**; tidak diredistribusi |
| B HP | `fariza25/PhishingURLDetection@ff9f1f5b517a80e9c967f0137c07eddd636c043d` | `Datasets/hp_{train,valid,test}.csv` | Kode MIT; lisensi data tidak dinyatakan → **belum jelas**; tidak diredistribusi |
| Verifikasi | repo B, commit sama | `Datasets/ebbu_{train,valid,test}.csv` | hanya untuk cek mapping label (D-03) |
