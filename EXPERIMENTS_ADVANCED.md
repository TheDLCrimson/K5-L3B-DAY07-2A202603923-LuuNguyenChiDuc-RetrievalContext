# Advanced challenge: experiments

Document and index: [data/advanced/README.md](data/advanced/README.md).
Benchmark and grading rules: [data/advanced/benchmark/README.md](data/advanced/benchmark/README.md).
Code: [src/advanced/](src/advanced/).
Everything in the first two sections was written before any run of the advanced agent on any split.

## A1 - What is fixed, and the configurations

Fixed for every configuration:

- the document (World Bank CCDR for Vietnam, Vietnamese edition, 103 pages) and its index: 384 chunks, `intfloat/multilingual-e5-base`, 768-d, exact cosine, in the pgvector table `adv_chunks`;
- the agent model `anthropic/claude-haiku-5.5` through OpenRouter, and the agent loop: at most 8 model calls, 5 searches and 4 looks, 3 new chunks per search, 3,300 characters per chunk;
- the benchmark and its split: dev 15 answerable and 3 without evidence, test 24 and 6;
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

## A3 - Dev results

To be written after the dev runs.
