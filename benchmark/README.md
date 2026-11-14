# Benchmark

[questions.json](questions.json) holds 46 questions on the Land Law [Luật Đất đai] 2013 and 2024: 40 answerable and 6 without enough evidence.
It is built by `python -m src.build_benchmark` from the Day 6 question files and [new_questions.json](new_questions.json), and checked by `python -m src.verify_benchmark`, whose output is [verification.csv](verification.csv).
The test split and every unanswerable question were written and verified on 14/11/2026, before any Lab 7 retrieval or agent run.

## Split

| Split | Answerable | Unanswerable | Where the answerable questions come from |
| --- | ---: | ---: | --- |
| dev | 30 | 3 (u01-u03) | All Day 6 questions: its dev (15), its test (5) and its holdout (10) |
| test | 10 (t01-t10) | 3 (tu01-tu03) | New, from articles no dev question uses |

Every Day 6 question goes into dev because all of them were read during Day 6.
The Day 6 test was run and its failure (q12) was read, and the holdout errors (h05, h06, h10) are what motivate a reranker here.
They are fine for tuning but cannot judge Lab 7 independently, so the test split is new.
Thirty dev questions also make the comparison finer: one question is 3.3 points instead of 6.7.

## Fields

The schema is the one in [data/README.md](../data/README.md).

- Answerable questions have `id`, `split`, `type`, `question`, `expected_answer`, `gold`, `filter`, `answerable: true` and `origin`.
- `gold` is a list of alternatives, each `{source_id, page, evidence}`; a chunk that holds any one of them is a hit.
- `page` is the physical PDF page within the file named by `source_id` (one 2013 file, three 2024 gazette files), as in the Day 6 manifest.
- Unanswerable questions have `answerable: false`, `expected_behavior: "search_and_abstain"`, an `absence_reason` and an `absence_check`.
- `origin` records the Day 6 file and split of a reused question, or the date of a new one.

The starter's `convert_day6.py` keeps only the primary gold and drops Day 6's `alternative_gold`, which 13 dev questions have.
`src/build_benchmark.py` merges the primary gold and every alternative into `gold` instead.

## Hit rule

A chunk holds an evidence when it comes from the gold source, its page range covers the gold page (`page <= gold page <= page_end`), and it contains the whole quote, ignoring whitespace ([src/evidence.py](../src/evidence.py), taken from Day 6).
The starter's `baseline.hit` requires the chunk to start on the gold page, but 237 of the 1,264 chunks span a page break.
Under that rule q05's evidence would never count, because its chunk starts one page earlier.

## Question mix

| Type | Dev | Test | What it tests |
| --- | ---: | ---: | --- |
| `truc_tiep` (direct) | 11 | 3 | The question uses the law's own wording. |
| `dien_dat_lai` (paraphrase) | 9 | 4 | Everyday wording, such as "mua bán đất" for chuyển nhượng or "nhà tôi nằm trong diện thu hồi". |
| `dieu_kien_ngoai_le` (condition or exception) | 10 | 3 | The answer depends on a condition, such as the provincial approval needed above 0.5 ha in t03. |
| `thieu_bang_chung` (not enough evidence) | 3 | 3 | Near-topic questions whose answer is outside the corpus. |

Of the answerable questions, 15 dev and 7 test carry a `year` filter.
A filter is given only when the question itself names the version ("Theo Luật Đất đai 2013 ..."), and the verifier enforces that, so the filter is supplied by the user and never read from the gold.
Unfiltered questions list the matching clause of both laws as gold when both have one.
The test set has version distractors on purpose:

- t01 and t02 ask the same thing of each law (3 years in 2013, 2 consecutive years in 2024).
- In t09 and t10 the 2013 clause gives a different answer (swaps within one commune instead of one province, a 5-year instead of a 10-year lease).

## Unanswerable questions

Each one is close to the corpus topic, and its `absence_reason` says why the corpus cannot answer it.
In most cases the law hands the figure to a province, a Government decree or another law.
Its `absence_check` records the terms searched across all 1,264 chunk texts (case- and whitespace-insensitive) and how many chunks matched, and the verifier fails if a count changes.
A zero for a name or unit (Hà Nội, Nghệ An, Nguyễn Huệ, mét vuông, phạt tiền, thuế suất) shows the value is not stated anywhere.
A non-zero count for the topic term (for example "trước bạ": 2) was read chunk by chunk, and the reason says what those chunks contain instead.
"Not in the corpus" is concluded from this search over every chunk, never from a retriever's top-k.

## Verification

`python -m src.verify_benchmark` currently prints `OK` and checks that:

- IDs are unique and the minimums from [BENCHMARK.md](../BENCHMARK.md) are met;
- every one of the 56 gold evidences is in a chunk under the hit rule;
- no quote is copied into its question;
- every filter year is named in its question and has gold from that year;
- no test gold shares an article (law year, Điều) with a dev gold, judged on the chunks that hold the evidence;
- every absence count still matches the corpus.

## Limits

The same author wrote the questions, answers and gold, and searched the corpus while writing them.
The set therefore leans toward clauses that are easy to find by keyword; paraphrase questions reduce this but do not remove it.
Ten answerable test questions are still coarse: one question is 10 points.
Unanswerable questions are checked by term search, which can miss a paraphrased statement of the value; reading the matching chunks lowers this risk but does not remove it.
