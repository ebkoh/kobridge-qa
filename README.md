# KoBridge-QA: bridge inspection manual QA benchmark and retrieval-unit scoring

This repository contains KoBridge-QA, a 210-item multiple-choice question-answering
benchmark on two Korean bridge and facility inspection manuals. It also contains the
scoring and statistics code used to compare four retrieval-unit designs (C1 to C4) on
it, and the per-item results of that comparison. The results cover retrieval-measure
hits, chosen options, prompt tokens and a free-form pilot. `code/reproduce.py`
recomputes every aggregate from the per-item results alone.

## Contents

```
README.md
LICENSE                          MIT, for code/
data/
  kobridge_qa.jsonl              210 items
  kobridge_qa_permuted.jsonl     the same items with options permuted to balance the keyed position
code/
  scoring/                       judgement rules: label, matcher, four measures, multi-hop
                                 full-evidence coverage, answer parsing, provision citation,
                                 question-evidence overlap
  stats/                         paired bootstrap, exact McNemar, Holm, Wilson
  reproduce.py                   reads results/ only and writes every aggregate as CSV
results/
  retrieval_per_item.jsonl       item x index x condition: measure hits, decomposition steps,
                                 attribution rules, multi-hop coverage, retrieved unit IDs
  answers_per_item.jsonl         item x configuration: chosen option, parsed, correct; for the
                                 12 unparsed responses, the failure type and response text
  tokens_per_item.jsonl          item x index: prompt tokens
  freeform_pilot.jsonl           38 items x 4 configurations: free-form grade, provision cited
  index_units.jsonl              every unit of the four indexes: ID, role, document, page,
                                 table identifier (no text)
```

## Data schema

### `data/kobridge_qa.jsonl`

One item per line.

| Field | Meaning |
|---|---|
| `id` | `Q001` to `Q210` |
| `type`, `subtype` | capability type (T1 hierarchical navigation, T2 parent-child aggregation, T3 tabular extraction, T4 multi-hop, T5 unanswerable) and subtype |
| `difficulty` | `easy`, `medium`, `hard` |
| `document` | source manual: `code` is `bridge_guideline`, `facility_type3_manual` or `both`, plus `name_ko` |
| `section_path` | `chapter`, `section`, `subsection`, `section_title`, `full_path` |
| `page_range` | page labels in the source manual |
| `table_refs` | numbered tables that govern the answer |
| `question` | question stem |
| `choices` | four options: `idx` (0-based), `label` (1-4), `text` |
| `answer_idx` | keyed option, 0-based |
| `evidence` | `source_quote` (short quotation with its location), `location`, `supporting_tables` (`id`, `page`) |
| `requires_capabilities` | boolean flags per capability |
| `distractor_strategy` | how the distractors were written |
| `version`, `created_at`, `revised_at` | item version and dates |
| `revision_note` | present on four items (Q073, Q089, Q159, Q194): what was revised, why, and when |

The options of four items (Q073, Q089, Q159, Q194) were revised after review against the source pages, and all reported runs used the revised options.

Item counts by type are T1 50, T2 50, T3 50, T4 50 and T5 10. The keyed answer is at
option 1 for 88 items, option 2 for 34, option 3 for 40 and option 4 for 48.

## Reproducing the aggregates

```bash
python code/reproduce.py                 # writes reproduced/
python code/reproduce.py --out DIR       # writes DIR/
```

The script needs Python 3.8 or later and the standard library only, and it runs in
about ten seconds. Rates and differences are written unrounded to six decimals, and
p-values to six significant digits. The output is identical from run to run.

| Output | Contents |
|---|---|
| `index_outcomes_depth5.csv` | hits and recall of each index and measure at depth five, for all labeled items and for T3 items |
| `index_accuracy_tokens.csv` | accuracy, Wilson interval and mean prompt tokens of C1–C4; whether the index stores table identifiers |
| `paired_contrasts.csv` | paired contrasts in four families: <ul><li>`depth5`: sixteen contrasts, the four measures for each of C1 to C2, C1 to C3, C3 to C4 and C2 to C4</li><li>`by_type`: C3 to C4 content-based, per type</li><li>`similar_volume`: C2 to C4, four measures</li><li>`accuracy`: three contrasts</li></ul> Each row gives the difference, bootstrap interval, gained/lost and exact p. Holm-adjusted p is given within `depth5+accuracy` (19 tests) and within `by_type` (4 tests). |
| `decomposition.csv` | steps A–D: source-label recall, change from the previous step with interval, gained/lost and p, and content-based recall |
| `attribution_rules.csv` | C1 and C2 source-label hits and their difference under each heading rule |
| `similar_volume.csv` | the character budget, realized mean characters and units, items whose C2 and C4 totals are within 10% |
| `pipeline_accuracy.csv` | accuracy and Wilson interval of the GPT-4o configurations; against C4: items favoring each side, exact p and Holm-adjusted p over the twelve comparisons; unparsed responses |
| `local_generators.csv` | accuracy of the Qwen3 runs |
| `multihop_coverage.csv` | full-evidence coverage of the 49 multi-hop items per index, and correct answers with a labeled unit unmatched |
| `freeform_pilot.csv` | per configuration on the 38 pilot items: free-form accuracy, multiple-choice accuracy on the same items, responses citing the labeled provision |
| `freeform_pilot_contrast.csv` | closed book against C4 on free-form correctness: discordant items and exact p |
| `benchmark_index_facts.csv` | item and label counts, keyed positions, median question-evidence overlap, units per index |
| `derived_figures.csv` | prompt-token ratios, accuracy range, decomposition gain, re-embedding changes, per-type net losses, Holm results, unparsed-response counts by failure type, cosine equivalent of the similarity floor |

## Licence

- `code/`: MIT (`LICENSE`).
- `data/` and `results/`: Creative Commons Attribution 4.0 International (CC BY 4.0),
  https://creativecommons.org/licenses/by/4.0/.

## Source manuals

The benchmark is written on two manuals. They are not redistributed here.

- 시설물의 안전 및 유지관리 실시 세부지침(안전점검·진단 편) — 교량편, December 2024 edition
- 제3종시설물 정기안전점검 매뉴얼, 2026 edition

Publisher: Korea Authority of Land and Infrastructure Safety (국토안전관리원),
https://www.kalis.or.kr
