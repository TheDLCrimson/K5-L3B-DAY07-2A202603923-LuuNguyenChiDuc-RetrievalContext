# Advanced challenge: experiments

Document and index: [data/advanced/README.md](data/advanced/README.md).
Benchmark and grading rules: [data/advanced/benchmark/README.md](data/advanced/benchmark/README.md).
Code: [src/advanced/](src/advanced/).
Everything in the first two sections was written before any run of the advanced agent on any split.

## A1 - What is fixed, and the configurations

Fixed for every configuration:

- the document (World Bank CCDR for Vietnam, Vietnamese edition, 103 pages) and its index: 384 chunks, `intfloat/multilingual-e5-base`, 768-d, exact cosine, in the pgvector table `adv_chunks`;
- the agent model `anthropic/claude-haiku-5.5` through OpenRouter, and the agent loop: at most 8 model calls, 5 searches and 4 looks, 3 new chunks per search, 3,300 characters per chunk;
- the benchmark and its split: dev 15 answerable and 3 without evidence, test 24 and 6 (dev was later extended to 20 and 3, see A4; test never changed);
- the question text is the only input: no gold, no filter, no rewritten query given by the harness.

| ID | Retrieval | Tools | Hypothesis, written before the run |
| --- | --- | --- | --- |
| V0 | dense on `adv_chunks` | search only | **Baseline.** The agent reads extracted text, table rows and the model-written description of each figure. Text and table-cell questions work; questions whose value lives only in the picture (colours, positions, unlabelled chart values, raster maps) fail, because the description can mislabel a value or lose it. |
| V1 | hybrid (top 10 per side) and cross-encoder rerank | search only | V0 with the best retrieval of the base lab. Raises the share of questions whose evidence reaches the context, mostly multi-hop and table questions, but cannot fix a value that the text does not carry. |
| V2 | as V1 | search and look (Haiku 5.5) | The `look` tool reads the crop for the question asked. It should lift chart, image and table-cell questions most, at the price of extra calls, time and cost, and of vision misreads (direction on maps was the one miss in the earlier probe). |
| V3 | as V1 | search and look (`anthropic/claude-sonnet-5.5`) | A stronger vision model behind `look`. Helps only if the failures of V2 are vision misreads and not retrieval or query errors. It costs more per look. |

V3 runs only if V2 meets its trigger below.

## A2 - Selection rule, fixed before the first run

Each dev question is graded pass or fail as ADVANCED.md section 3 defines it (right and complete, with unit, condition and calculation; the citation names the page and region and the evidence supports the whole answer; a refusal on an answerable question fails; for a no-evidence question, a refusal with no unsupported claim passes).
A system error counts as a fail.
The grades are drafted by reading each answer against the evidence and the crop, then checked by the author.

1. **Gate.** The configuration refuses all 3 no-evidence dev questions with no unsupported claim.
2. **Pass count.** The highest number of passes out of the 18 dev questions. A difference of one question is a tie.
3. **Evidence in context.** Among tied configurations, the higher share of answerable questions whose every evidence item is in the final context.
4. **Cost, then time.** Then the lower cost per question, then the lower median time.

**V3 trigger.** V3 runs on dev only if V2 has at least two dev failures labelled "vision misread": the look answer contradicts the crop while the right region was looked at.

**Test.** After the choice is written to `results/advanced/selection.json`, test runs once for the chosen configuration and once for V0 as the baseline, with `--final`.
The chosen configuration is run on test whatever its dev result is, and the pass rate is reported as it is.
The bonus is claimed only if it passes at least 27 of the 30 test questions, with no rounding.
If a test failure leads to a change, the test set is replaced with new questions before any score is reported.

## A3 - Dev results (V0, V1, V2; first run of each)

Run on 16/11/2026 with the agent and benchmark as committed.
A first attempt overlapped two runs and a reranker load failed with a Windows memory error (paging file); the stale run was stopped, the dev folder deleted and all three configurations re-run once, in order.
Labels were drafted by reading every answer against the evidence, the crop and every cited chunk (reasons in [review_labels.csv](results/advanced/dev/review_labels.csv)), then checked by the author.

| Measure | V0 dense | V1 hybrid + rerank | V2 V1 + look |
| --- | --- | --- | --- |
| Pass, all 18 (by reading) | 18/18 | 18/18 | 18/18 |
| Pass by group (table, image or diagram, chart, multi-hop, text, no evidence) | 3, 3, 4, 2, 3, 3 of the same | same | same |
| Refuses the 3 no-evidence questions without an unsupported claim | 3/3 | 3/3 | 3/3 |
| Evidence in the final context (answerable) | 15/15 | 15/15 | 15/15 |
| Evidence in the first search | 13/15 | 13/15 | 13/15 |
| Answers citing every evidence item | 15/15 | 15/15 | 15/15 |
| Searches per question (1 / 2 / 3 / 4) | 8 / 6 / 3 / 1 | 11 / 6 / 0 / 1 | 10 / 6 / 0 / 2 |
| Looks per question (0 / 1 / 2) | all 0 | all 0 | 7 / 10 / 1 |
| Model calls per question (mean) | 2.44 | 2.28 | 3.00 |
| System errors | 0 | 0 | 0 |
| Cost for 18 questions (per question) | $0.0268 ($0.0015) | $0.0238 ($0.0013) | $0.0385 ($0.0021) |
| Time per question, median / p90 | 6.0 s / 13.2 s | 9.1 s / 16.3 s | 12.9 s / 22.8 s |

**What the dev set shows.**
All three pass every dev question, so dev cannot separate them.
The look tool was used on 11 of the 15 answerable questions and every look agreed with the crop, but the other two configurations answered the same questions correctly from the extracted text.
That is because the report repeats most chart values in its own text (for example Hình 8's 9,8% and 12,3% are in a paragraph), and because vector charts carry their labels as text.
So the dev questions do not contain the case the look tool is for: a value that exists only in the picture.
Two of the 15 answerable dev questions read a value off an axis (ad-d09, ad-d10) and both were answered from description or text.

**One defect found.**
V1 on ad-d13 returned a correct answer with tool-call markup leaked into the answer string (`</answer> <parameter name="citations">...`).
It is graded a pass because the content and citations are right, and recorded as a model formatting fault.

**By the rule written in A2.**
The gate holds for all three, the pass counts tie (18), evidence in context ties (15/15), so step 4 decides: V1 has the lowest cost per question.
The rule, applied as written, chooses V1.
The tie says dev cannot tell whether look matters, and the test set has evidence items that exist only in the picture (five flagged `visual_only` in the benchmark: t06, t09, t10, t11, t16; two more, t07 and t08, depend on reading labels and positions on a map).

## A4 - Amendment after the dev tie (made before any test run)

The first dev runs tied, so step 4 of the rule (cost) alone would have decided, and dev had no question that only a picture can answer.
Decision of the author, taken after seeing that result and before running anything on test:

- add five dev questions whose answer exists only in the picture, on figures the test does not use (ad-d19 to ad-d23: Hình 2, 15, 17 and 4; each was checked against the extracted text and its answer is not there);
- run V0, V1 and V2 once on those five, label them the same way, and apply the rule from A2 unchanged to the 23 dev questions (the 18 first runs plus the 5 new ones);
- the test set is not touched.

Another change made at the same time, found in the first run: the harness strips tool-call markup that a model writes into the answer text (event `answer_markup_stripped`), with a unit test.
It changes how an answer string is cleaned, not what the model is asked or shown, so the 18 first-run answers are kept as they are.

## A5 - Dev results with the extension (23 questions) and the rule applied

The five new questions ran once for each of V0, V1 and V2 with the harness that strips leaked markup; labels are in [review_labels_ext.csv](results/advanced/dev/review_labels_ext.csv), drafted by reading and checked by the author.

| Question (picture-only answer) | V0 dense | V1 hybrid + rerank | V2 V1 + look |
| --- | --- | --- | --- |
| ad-d19 Hình 2, end of Thailand's line (axis read) | refused (fail) | 5,700, pass (from the description, matches the picture) | 5,700 after looking, pass |
| ad-d20 Hình 17, highest bar | pass | pass | pass |
| ad-d21 Hình 17, negative bars | pass | pass | pass |
| ad-d22 Hình 4, sector below zero (colour to legend) | pass (legend and a table row) | pass | pass (looked) |
| ad-d23 Hình 15, top layer (colour to legend) | refused (fail) | refused (fail) | pass (looked) |

| All 23 dev questions | V0 | V1 | V2 |
| --- | --- | --- | --- |
| Pass | 21/23 | 22/23 | 23/23 |
| Failures | ad-d19, ad-d23 (both refusals) | ad-d23 (refusal) | none |
| Evidence in the final context | 20/20 | 20/20 | 20/20 |
| Cited chunks that support the answer | 37/37 | 35/35 | 37/37 |
| Cost per question | $0.00155 | $0.00134 | $0.00216 |

Every failure is a refusal: V0 and V1 declined to name a colour or an axis value that the extracted text does not carry, where V2 looked at the picture and answered.

**By the rule written in A2, applied as written.**
1. The gate holds for all three (3/3 no-evidence questions refused, nothing unsupported).
2. Pass counts are 21, 22 and 23; configurations within one question of the best count as tied, so V2 and V1 are tied and V0 (two below) is out.
3. Evidence in context ties at 20/20.
4. Cost per question decides between the two: V1 is cheaper than V2, so **the rule chooses V1**.

**What this means, stated plainly.**
The rule picks V1, but the difference between V1 and V2 on dev is one question out of 23, and it is on the kind of question the look tool exists for.
The test has five evidence items flagged `visual_only` (t06, t09, t10, t11, t16) and two map questions (t07, t08) whose answer sits in the picture's labels and positions.
Choosing V1 follows the rule; choosing V2 would follow the evidence about the capability but override a rule written beforehand.

## A6 - Test, run once (16/11/2026)

The choice was committed first (commit 9374d3f, [selection.json](results/advanced/selection.json)): V1 is the chosen configuration and V0 the baseline.
Test ran once for each, with `--final`, on the 30 questions of [questions.json](data/advanced/benchmark/questions.json), which the author reviewed before the run.
Labels were drafted by reading each answer against the original page, the crop and every cited chunk, then checked by the author ([review_labels.csv](results/advanced/test/review_labels.csv)).

| Measure | V1 (chosen) | V0 (baseline) |
| --- | --- | --- |
| **Pass, all 30** | **26/30 (86.7%)** | **26/30 (86.7%)** |
| Tables (6) | 6/6 | 6/6 |
| Text (4) | 4/4 | 4/4 |
| Multi-hop (4) | 3/4 | 3/4 |
| Charts (5) | 4/5 | 4/5 |
| Images and diagrams (5) | 3/5 | 3/5 |
| No evidence (6) | 6/6 | 6/6 |
| Failed | t09, t11, t16, t20 | t09, t11, t16, t20 |
| Failure types | refusal 3, vision 1 | refusal 3, vision 1 |
| System errors | 0 | 0 |
| Evidence in the final context (24 answerable) | 24/24 | 24/24 |
| Cited chunks that support the answer | 53/54 | 50/51 |
| Cost for 30 questions (per question) | $0.0453 ($0.0015) | $0.0444 ($0.0015) |
| Time per question, median / p90 | 9.8 s / 21.4 s | 6.3 s / 11.0 s |

**The bonus bar is 27/30 (90%, no rounding). The result is 26/30, one short.**

**The four failures, the same in both configurations.**

- **t09 and t11 (Hình 11 and Hình 9, which area is darkest; which map is green).** Both refused: the extracted text carries no colour, and the agents declined to use the model-written description, which had the right answer. Refusing an answerable question fails.
- **t16 (Hình 19, which group falls most).** Both said Dịch vụ (about −2.5%) instead of Y tế (about −1.5%). The error comes from the model-written description of the chart, which the agent used without checking the picture. This is the one case where a description was wrong, and neither V0 nor V1 can look at the image.
- **t20 (Bảng 4 and Hình 18, borderline).** Both gave −73,6% correctly and read −1,1 for Gini from Hình 18, then said they could not confirm the direction, because the report's own text says Gini "tăng nhẹ so với BAU" while Hình 18 shows −1,1. I graded this a fail because the answer does not commit to the value asked for, the same standard as the base lab's t10 (quoted the clause, then refused). If the reviewer decides that stating −1,1 from the figure is enough, both configurations would pass 27/30, exactly 90%. The report contradicts itself here, so this was a weak test item.

**What the failures say.**
Tables, text and the multi-hop calculations all pass.
Every failure is a question whose answer is in the picture or whose source contradicts itself.
`look` was not available to either configuration (V2 had it and was not chosen by the rule), so this test cannot say whether it would have fixed t09, t11 and t16.
Running V2 on test now would be using test to choose, so it is not part of the claim.

**Harness note.**
`answer_markup_stripped` fired once per configuration (one answer each had tool-call markup leaked into the text, stripped as designed; the content was graded as written).

## A7 - Conclusions, trade-offs and what to do next

**Result.**
26 of 30 test questions pass (86,7%), one short of the 27 the bonus needs, for the chosen V1 and for the baseline V0 alike.
The bonus is not claimed.

**What works.**
Every table question (6/6), every text question (4/4), the multi-hop calculations that join two pages or two tables (3/4, the miss being the weak t20), and refusals on questions the report cannot answer (6/6) all pass, with no system error and with the evidence in the final context for all 24 answerable questions.
Crops with a page and a region let every citation be checked against the original.

**What does not.**
Answers that live in the picture fail when the agent cannot look: two colour questions were refused (t09, t11) and one chart question was answered wrongly from a bad description (t16).
The description written at index time is a search aid, not evidence, and one of them was wrong; an agent without `look` has no way to find out.

**Trade-offs measured.**
On dev (23 questions) `look` raised passes from 22 to 23 at 1,6 times the cost per question ($0.0022 against $0.0013) and 1,4 times the time (12,9 s against 9,1 s on the first 18 questions); on test, V1 against V0 cost the same ($0.045 for 30 questions) and took 9,8 s against 6,3 s, with the same pass count.
Rerank bought no passes on test and about 3 s per question.

**What the evidence does not settle.**
The rule picked V1 on a one-question difference.
Whether V2 would have passed t09, t11 and t16 was not tested, because running it on test after the choice would be selecting on test.
One label (t20) decides the bar, and the item is weak because the report contradicts itself on that value.

**Next steps (each needs new dev questions, a new choice and a new test).**
1. Use `look` by default for any question about a figure or a map, since the dev data point toward it and the test failures are all picture-bound.
2. Check a model-written description against the crop before an agent uses a number from it.
3. Replace test items whose source contradicts itself, and enlarge the test so one question is less than 3,3 points.
4. Run each configuration several times to measure run-to-run variance.
