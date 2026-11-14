# Experiments

This file is written before each experiment runs: its setup, hypothesis and how the result will be judged.
Results are added below each plan afterwards, and the plan above them is not edited.

## Fixed for every experiment

- Corpus and index: the 1,264 Day 6 strategy B chunks ([data/day6/README.md](data/day6/README.md)); every method searches exactly these chunks.
- Benchmark: [benchmark/questions.json](benchmark/questions.json); experiments run on dev only, and test is run once per configuration after the choice is fixed.
- Hit rule: [src/evidence.py](src/evidence.py), range-aware, any `gold` alternative counts.
- Retrieval metrics are over answerable questions only (30 on dev); unanswerable questions are traced but never enter a denominator.
- Filter: a question's `year` filter is applied when it has one; it is set only when the question names the law version ([benchmark/README.md](benchmark/README.md#question-mix)).
- Queries are the original question text, unchanged, in every retrieval experiment.
- A top 3 is always exported; Hit@1 and Evidence Hit@3 are the comparison measures, with MRR@10 and Hit@20 as extras.
- Context budget: 3,300 characters per context, source labels and separators included, set before any run.
  Day 6 B chunks are at most 1,000 characters (median 758) and a label is under 100, so three chunks always fit; the starter's 800 would drop most chunks.
- Time is wall-clock per query on this machine (GTX 1650 4 GB, models loaded once beforehand); retrieval uses only local models, so its API cost is 0.

## E1 - retrieval methods on dev (Part 2)

| ID | Method | Configuration | Hypothesis |
| --- | --- | --- | --- |
| M1 | Dense (baseline) | e5 query vector, exact cosine on pgvector, `year` filter in SQL (Day 6 configuration C) | Strong on paraphrase questions; its misses are near-duplicate neighbouring clauses or the other law version. |
| M2 | BM25 | `rank_bm25` Okapi (k1 1.5, b 0.75) over lower-cased NFC syllables plus adjacent syllable pairs (Day 6 tokenizer), same filter | Close to dense on direct-wording questions, clearly worse on paraphrase questions, which share few words with the law. |
| M3 | Hybrid | Top 20 from each of M1 and M2, scores min-max normalised per query and side, fused as 0.7 dense + 0.3 BM25 (Day 6's dev choice); RRF (k 60) is logged as a second configuration | At least M1's Hit@3 and a higher Hit@1, since the keyword side breaks dense ties between near-duplicates. |
| M4 | Hybrid + rerank | The union of M1's and M2's top 20 (up to 40), re-scored by the cross-encoder `BAAI/bge-reranker-v2-m3` (fp16) on question and chunk text | Fixes the Day 6 holdout misses where both sides chose a neighbouring clause (h05: Điều 172 for 171; h06: the right article, the wrong clause; h10: certificate articles over the definition in Điều 4), raising Hit@1 most; costs added time per query. |

Raw scores from different retrievers are never added: M3 fuses only normalised scores or ranks, and M4 ranks by one model's score.

**Selection rule, fixed before the run.**
The retrieval that the agent's search tool will use is chosen on dev by these steps, in order:

1. Highest Evidence Hit@3.
2. If two methods are within one question (1/30), higher Hit@1, with the same band.
3. Then lower median time per query.

## E1 results

Run on 14/11/2026 with `python -m src.eval_retrieval --split dev`; traces and summaries are in [results/retrieval/dev/](results/retrieval/dev/summary.md).
Dev has 30 answerable questions; the 3 unanswerable ones are traced and not counted.

| ID | Method | Hit@1 | Evidence Hit@3 | MRR@10 | Hit@20 | Context Evidence Rate | Median / p90 ms per query | Errors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M1 | dense (baseline) | 21/30 (70%) | 26/30 (87%) | 0.803 | 30/30 | 26/30 (87%) | 42 / 52 | 0 |
| M2 | bm25 | 20/30 (67%) | 23/30 (77%) | 0.734 | 28/30 | 23/30 (77%) | 15 / 21 | 0 |
| M3 | hybrid, weighted 0.7 | 24/30 (80%) | 27/30 (90%) | 0.861 | 30/30 | 27/30 (90%) | 61 / 77 | 0 |
| M3b | hybrid, RRF | 23/30 (77%) | 25/30 (83%) | 0.825 | 29/30 | 25/30 (83%) | 68 / 79 | 0 |
| M4 | hybrid + rerank | 26/30 (87%) | 28/30 (93%) | 0.911 | 30/30 | 28/30 (93%) | 4,011 / 4,523 | 0 |

Context Evidence Rate equals Evidence Hit@3 here because each pipeline sends its top 3 and the budget always fits three chunks (largest context 3,162 of 3,300 characters).
It will differ once the agent builds context from several searches.

Evidence Hit@3 by question type:

| Type | dense | bm25 | hybrid | hybrid_rrf | hybrid_rerank |
| --- | --- | --- | --- | --- | --- |
| `truc_tiep` (11) | 11 | 11 | 11 | 11 | 11 |
| `dien_dat_lai` (9) | 6 | 4 | 7 | 6 | 7 |
| `dieu_kien_ngoai_le` (10) | 9 | 8 | 9 | 8 | 10 |

Misses at 3: dense q12, h05, h06, h10; bm25 q02, q04, h03, h05, h06, h09, h10; hybrid h05, h06, h10; hybrid_rrf q02, h05, h06, h09, h10; hybrid_rerank h03, h06.

**Check against Day 6.** Dense and hybrid reproduce the Day 6 lab's configurations C and D exactly on the same 30 questions (C: Hit@1 13 + 4 + 4 = 21, Hit@3 15 + 4 + 7 = 26 over Day 6 dev, test and holdout; D: 14 + 4 + 6 = 24 and 15 + 5 + 7 = 27), so Lab 7 searches the same index in the same way.

**Hypotheses.**

- M1, confirmed: every dense miss is a near-topic chunk from the right law version, and three of the four are a neighbouring chunk or article.
  q12 takes another chunk of the right article (2024 Điều 135), h05 the next article (Điều 172 for 171), h06 the right article but clause 2 instead of 1 (Điều 236), and h10 the certificate articles 139-140 over the definition in Điều 4.
- M2, confirmed: BM25 ties dense on direct-wording questions (11/11) and is worst on paraphrase (4/9 against 6/9), where the question shares few words with the law.
- M3, confirmed: hybrid lifts Hit@1 by 3 and Hit@3 by 1 over dense (q12 moves from rank 4 to 2).
  RRF is worse than the weighted fusion: by using ranks only, it gives BM25's weaker list an equal say, and it loses q02 and h09.
- M4, mostly confirmed: rerank fixes two of the three Day 6 holdout misses (h05 from rank 16 to 3, h10 from 4 to 1) and lifts q12 to rank 1, for the best Hit@1 (+2 over hybrid) and MRR.
  It does not fix h06 (it ranks Điều 235 on mediation first, and the right clause of Điều 236 stays at rank 4), and it loses h03 (rank 2 to 4), preferring the transitional provisions of Điều 254 and 257 on recovery and compensation to Điều 91.
  No question-chunk pair exceeded the 512-token limit.

**Time and cost.** Rerank scores up to 40 pairs per query and takes about 4.0 s, against 61 ms for hybrid, on a GTX 1650 in fp32.
fp16 was tried first and took 16.9 s per query, because this GPU runs fp16 matrix products about 5 times slower than fp32, so the run above uses fp32.
All five methods use local models only: the API cost is 0, and loading the reranker takes about 2.3 GB of GPU memory.

**Selection, by the rule above.**
Step 1: hybrid_rerank has the highest Evidence Hit@3 (28), but hybrid (27) is within one question.
Step 2: Hit@1 is 26 against 24, a gap of two questions, outside the band, so **hybrid_rerank is chosen** for the agent's search tool and step 3 (time) is not reached.
The trade-off is 4 s per search; the agent's own model calls take seconds too, so this is accepted, and the number of searches per question is counted in the agent experiments.

**Carried into the agent experiments.** Both remaining misses are retrieval-ranking errors, and the evidence is in the pool (Hit@20 30/30):

- h06: the right article, Điều 236, is found, but the clause for parties that do have a certificate sits in a neighbouring chunk.
- h03: the right chunk sits at rank 4, just outside the top 3.
