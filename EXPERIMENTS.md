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

## E2 - the agent with each retrieval (Part 3)

Written on 14/11/2026 while the first full dev runs were in progress, before any of their results was read.

Agent: [src/agent.py](src/agent.py), model `anthropic/claude-haiku-5.5` through OpenRouter, the provider layer adapted from Day 4.
Tools: `search_law(query, year?)`, which returns up to 3 chunks not shown before (3,300-character budget per result), and `finish(status, answer, citations)`.
Stop: `finish`, or 6 model calls (then an abstention, reason `turn_limit`); searches beyond 4 are refused.
Code guards: `year` is accepted only when the question names that law version; a citation counts only if its chunk was shown in this run.
The system prompt states general rules only: it has no example drawn from any benchmark question, dev or test.

| ID | Search tool | Hypothesis |
| --- | --- | --- |
| A0 | dense (M1) | Baseline. Its Context Evidence Rate can exceed M1's Hit@3 (26/30), because the model may search again with its own legal wording. |
| A1 | hybrid_rerank (M4) | A higher Context Evidence Rate than A0 and fewer searches per question, since the first search is better; each search costs about 4 s more. |

Measured without labels: Context Evidence Rate, tool use and calls per question, abstentions on unanswerable and on answerable questions, cost and time.
Answer correctness and citation support are labelled by reading in Part 4, together with the error analysis.

## E2 results

Run on 14/11/2026 on dev (33 questions: 30 answerable, 3 unanswerable); traces in [results/agent/dev/](results/agent/dev/).

| Measure | A0 dense | A1 hybrid_rerank |
| --- | --- | --- |
| Status | answered 30, abstain 3, error 0 | answered 30, abstain 3, error 0 |
| Tool use | 33/33 | 33/33 |
| Retrieval calls (total; per question 1 / 2 / 3 / 4) | 52 (21 / 7 / 3 / 2) | 49 (22 / 8 / 1 / 2) |
| Gold in the first search's results | 28/30 | 30/30 |
| Context Evidence Rate | 30/30 | 30/30 |
| Answered and cited a chunk holding the gold (ID check only) | 30/30 | 30/30 |
| Abstained on unanswerable (by status, to be confirmed by reading) | 3/3 | 3/3 |
| Abstained on answerable | 0/30 | 0/30 |
| Tokens in / out | 248,906 / 28,725 | 243,243 / 27,013 |
| Cost for the 33 questions (billed by OpenRouter) | $0.0389 | $0.0375 |
| Time per question, median / p90 | 4.9 s / 9.6 s | 8.7 s / 18.9 s |

**Hypotheses.**

- A0, confirmed: the agent's context holds the evidence for all 30 questions, against 26/30 for one dense search on the original question (M1).
  Two things add up: the model's own legal-term query already finds the gold in its first search for 28/30, and it searches again when the first results do not answer.
  For example, h10 took four dense searches before the definition in Điều 4 came up; h05 found "ổn định lâu dài" on the second.
- A1, not confirmed on context, because both runs reach the ceiling (30/30).
  Its first search has the gold for all 30 (A0: 28), and it makes 3 fewer searches in total, but each search costs about 4 s of reranking, so the median question takes 8.7 s against 4.9 s; the cost is the same.

**The year guard was needed.** In 12 search calls (A0: 5, A1: 7) the model set a `year` the question does not name, for example 2024 on h05, which asks about both laws.
The code refused each one and the model searched again without the filter, as the error message says, so no filter came from anything but the question.

**What this means for Part 4.** On dev the measures that need no reading are at their ceiling for both configurations, so they cannot pick between them.
The comparison has to come from reading: whether each answer is right and complete, and whether each citation supports it, plus time and cost.

## E3 - labels, dev errors and the second improvement (Part 4)

Written on 14/11/2026 before any answer was labelled and before A3 or A4 existed.

**Labels.** Every dev answer of each configuration is labelled in `results/agent/dev/<config>/reviews.json`, in the format `starter/agent_metrics.py` reads, with a reason per label:

- `answer_grade` (answerable): 0 wrong, unsupported or refused; 1 partly right or incomplete; 2 right and complete, including every condition the expected answer names.
  For a question that names no law version and whose answer exists in both laws, an answer from only one law is incomplete (1).
- `citation_support`: one value per citation, true only when that chunk's text states what it is cited for; an existing ID is not enough.
- `abstention_correct` (unanswerable): true when the answer refuses the asked value and asserts nothing the chunks do not state.

The labels are drafted with AI assistance by reading each answer against the text of every chunk it cites and against the expected answer, then checked by the author; the report says so.

**Second improvement.** Two changes, each tested on dev against A1:

| ID | Change from A1 | Hypothesis | Measured by |
| --- | --- | --- | --- |
| A3 | Per-version search: the code refuses a `year` only when the question names the other version; when the question names none, the prompt asks for a search in each law | Every dev question that names no version and has gold in both laws cites gold from both (13/13; A1 12/13, missing h05), with no citation from the wrong version on a filtered question | Both-law coverage (automatic) and labels |
| A4 | Rerank pool of the top 10 per side instead of 20 | Rerank time per search about halves (4 s to about 2 s), and Evidence Hit@3 on dev stays within one question of M4 (28/30) | E1 metrics on all 30, then agent time and labels |

If both hold, their combination A5 is run and labelled on dev before the choice; no configuration reaches test without dev labels.

**Selection rule for the final configuration, fixed now.**

1. Gate: 3/3 correct abstentions on the dev unanswerable questions, and no more false abstentions than A0.
2. Highest mean grounded-answer grade on the 30 dev answerable questions (/2); within 0.05 (1.5 grade points) is a tie.
3. Then the higher share of citations that support the answer.
4. Then the lower median time per question, then the lower cost.

## E3 results

Run and labelled on 14/11/2026, dev only (30 answerable, 3 unanswerable).
Traces, labels (`reviews.json`, one reason per label) and the `starter/agent_metrics.py` output are in each configuration's folder under [results/agent/dev/](results/agent/dev/).
The labels were drafted with AI assistance by reading every answer against the text of each chunk it cites, then checked by the author.

| ID | Configuration | Grounded answer 2 / 1 / 0 (mean /2) | Citations that support the answer | Cited gold from both laws | Wrong-version citations | Abstention / false abstention | Retrieval calls | Cost (33 questions) | Time per question, median / p90 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A0 | dense | 30 / 0 / 0 (2.00) | 69/71 (97.2%) | 13/13 | 0/22 | 3/3, 0/30 | 52 | $0.0389 | 4.9 s / 9.6 s |
| A1 | hybrid_rerank | 29 / 1 / 0 (1.97) | 74/75 (98.7%) | 12/13 | 0/29 | 3/3, 0/30 | 49 | $0.0375 | 8.7 s / 18.9 s |
| A3 | A1 + per-version search | 29 / 1 / 0 (1.97) | 83/84 (98.8%) | 13/13 | 0/24 | 3/3, 0/30 | 57 | $0.0376 | 11.6 s / 19.5 s |
| A4 | A1 with a rerank pool of 10 per side | 30 / 0 / 0 (2.00) | 70/70 (100%) | 13/13 | 0/22 | 3/3, 0/30 | 46 | $0.0333 | 6.4 s / 12.1 s |
| A5 | A3 + A4 | 29 / 1 / 0 (1.97) | 84/85 (98.8%) | 13/13 | 0/25 | 3/3, 0/30 | 60 | $0.0412 | 7.8 s / 14.4 s |

Every configuration has Context Evidence Rate 30/30, tool use 33/33 and no errors.
Wrong-version citations count citations from the other law on questions that name a version.

**A4 at the retrieval level** ([results/retrieval/dev/summary.md](results/retrieval/dev/summary.md)): `hybrid_rerank_pool10` keeps Hit@1 26/30 and has Evidence Hit@3 27/30 (M4: 28/30), losing h05, whose 2013 gold no longer reaches the pool (Hit@20 29/30).
Its median search time is 2.2 s against 3.6 s for M4 in the same session.
M4 was re-run alongside so the two times are comparable; its scores are unchanged and its time differs from the 4.0 s in E1 only by run-to-run variation.

**Hypotheses.**

- A3, confirmed: both-law coverage rises from 12/13 to 13/13 (h05 now cites Điều 125 and Điều 171), with no wrong-version citation.
  It costs searches (57 against 49) and time (11.6 s median).
- A4, confirmed on quality, partly on time: Evidence Hit@3 stays within one question (27 against 28), and the agent stays at Context Evidence Rate 30/30, because it searches again when needed.
  Time per search falls by about 40% rather than half, and time per question by 27% (6.4 s against 8.7 s).
- Both held, so A5 was run and labelled as planned. It is slower than A4 and no better on any measure.

**Dev errors analysed** (cause, change, before and after):

1. h05, an answer from one law version (A1, grade 1).
   The question names no version; A1 found Điều 125 of the 2013 law, which is no longer in force. Its attempt to search with `year=2024` was refused by the year guard, and it said it found nothing in the 2024 law.
   Change: A3 allows a per-version search when the question names no version. After it, h05 cites both laws (grade 2), and both-law coverage is 13/13.
2. Neighbouring-clause retrieval misses (h03, h06 in E1), where the gold sat at rank 4 for M4.
   In the agent, the model's second search with legal wording brought the right clause into context: Context Evidence Rate is 30/30 for every configuration, against Evidence Hit@3 of 26-28/30 for a single search on the original question.
3. A0 q08, a mis-citation: the model was shown chunk 0225 (Điều 81 clause 9, force majeure) but cited 0224 for it. The claim is true, but its citation does not support it, so it is labelled unsupported; this is why citations are read, not ID-checked.
4. A4 h10, a mistyped citation: the model wrote `B-ldd2024_cb363-0149` for the chunk it was shown, `B-ldd2024_cb365-0149` (Điều 138).
   The citation check dropped the unknown ID as designed, which left a true sentence uncited. The answer itself is right.
5. A3 and A5 q05, a contradictory opening: the answer begins "Có." ("Yes") and then states the prohibition correctly (grade 1).
   It appeared only in the two per-version runs and is not a retrieval error; it is a known risk of a one-word lead, recorded as a limit.
6. Also seen: citing a fragment of Điều 126 (0259) as proof that the article omits residential land (A1, A3), and tool-call markup leaking into one answer (A0 h03).

**Selection, by the rule fixed before labelling.**

1. Gate: all five pass (3/3 abstentions, 0 false abstentions, as A0).
2. Grounded answer: the best is 2.00 (A0, A4); A1, A3 and A5 are 1.97, within 0.05, so all five tie.
3. Citations that support the answer: A4 70/70 (100%) is highest (A3 98.8%, A5 98.8%, A1 98.7%, A0 97.2%).

**A4 (`A4_rerank_pool10`) is chosen** and frozen in [results/agent/selection.json](results/agent/selection.json) before any test run.
It is also the cheapest configuration ($0.0333 for 33 questions) and the fastest after A0 (6.4 s median).
The margins on dev are small: one grade point and a few citations separate the five, so the test run is the real check.
