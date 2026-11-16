# Evidence check: two primary papers

## Current active pair after publication audit: R15 (2022) and R2 (2024)

D-33 migrates the manuscript/notebook to the PRD v1.1 pair. R15's institutional PDF is
obtained and its classifier/representation/results sections checked; see `r15_assessment.md`.
The user supplied R2's original 14-page publisher PDF on 2026-11-16. The complete article,
Table 1, Algorithm 1, results and limitations were reviewed; see `r2_fulltext_review.md`
and the hashed PDF provenance in `artifacts/publication_corrections/`. HP encoding is
crossvalidated against all six published class counts; no author-written numeric codebook
is claimed. Earlier access failures below remain historical records. Both papers meet the
five-year cutoff 2021-11-16. R15 is outside the preferred three-year window.

R5 remains a close methodological comparator; the history below records the previous pair,
not the current bibliography policy. R16 Kapoor/Narayanan 2023 supports general evaluation
validity, from publisher full text at https://pmc.ncbi.nlm.nih.gov/articles/PMC10499856/.

## Previous assignment pair: R2 (2024) and R5 (2026)

The author confirmed on 2026-11-16 that the 3–5-year recency requirement still applies.
R1 (2019) is retained only for historical dataset attribution. The two current primary
papers both fall within 2023-11-16 through 2026-11-16, the stricter three-year window.

* R2: [publisher DOI](https://doi.org/10.1016/j.comnet.2024.110398), *Computer Networks*,
  May 2024. Crossref confirms title, authors and date. Publisher-indexed sections support
  its transfer/UDA role; complete PDF still not obtained.
* R5: [publisher DOI](https://doi.org/10.1109/ACCESS.2026.3672690), *IEEE Access*, 2026,
  pp. 43200–43212. The local PDF front page states publication on 10 March 2026. Its
  full text was inspected again: §II-A/B, PDF pp. 3–5, discusses cross-dataset importance
  criteria and overlap measurement; §III, including PDF pp. 8–9, covers classifier/cost
  comparisons. Its primary method is XGBoost; RF/LightGBM appear as comparators. It is
  relevant to stability/cost, not an exact implementation reproduced by this project.

Evidence: `artifacts/literature_recency_20261116/crossref_primary_metadata.json` and the
local R5 PDF. Crossref records returned no linked update/retraction in `update-to` or
`relation`; this is a metadata check, not an exhaustive guarantee of publication status.
Direct IEEE Xplore access presents a robot check, so the local PDF and indexed publisher
content support the review. `pwc paper info` returned no matching title; catalog absence
was not treated as evidence against the paper. No dataset URL was visited.

Selection rationale: R5 was already a close comparator in the pre-existing gap matrix;
its promotion to primary status avoids inventing a new topic or changing frozen models.
The gap is therefore framed relative to existing stability/cross-dataset work, not as a
claim that those topics are new. The full-paper reading requirement is still incomplete
for R2 even though the two references meet the count/date conditions.

## Earlier check: R1/R2 roles before the recency confirmation

Checked 2026-11-16 through publisher-indexed search results. Direct ScienceDirect opens
returned HTTP 403. Search excerpts do not establish that a complete paper/PDF was read.
No dataset URL was opened, fetched, or resolved.

| ID | Primary source | Material inspected | Supported use | Still unknown |
|---|---|---|---|---|
| R1 | https://doi.org/10.1016/j.eswa.2018.09.029 | Publisher abstract and highlights; exact-title search | URL-only/NLP classification, RF, EBBU origin | Complete protocol, grouping, and selection details not established from the abstract |
| R2 | https://doi.org/10.1016/j.comnet.2024.110398 | Publisher-indexed abstract and selected text in §4, §7, §9.2; searches on title, split, path alignment | Cross-source transfer already investigated; feature alignment uses unlabelled target distribution; original random splits; feature-intercorrelation limitation stated in §9.2 | Complete PDF not obtained; exact numeric CSV label encoding still requires direct confirmation |

Queries: exact titles; R1 + “Random Forest”; R2 + “4.2”, “92,500”, and “labels”.
Stopped after verifying the intended distinction (source-only learning versus adaptation)
and documenting access limits. No expanded ten-paper review was pursued after the user
revised the assignment to permit two papers. This is a targeted check, not a systematic review.

The gap is an inference from the different experimental question, not a statement that
the authors failed to study generalisation. Accuracy/F1 values from different protocols
must not be placed in a common performance league table.
