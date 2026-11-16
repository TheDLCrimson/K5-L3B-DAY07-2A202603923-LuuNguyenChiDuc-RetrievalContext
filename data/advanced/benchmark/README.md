# Advanced challenge: benchmark

Document: the World Bank CCDR report for Vietnam, Vietnamese edition, 103 pages ([../README.md](../README.md)).
The benchmark is in [questions.json](questions.json); [review_sheet.md](review_sheet.md) shows every question next to its evidence and crop; [verification.csv](verification.csv) is written by `python -m src.advanced.verify_benchmark`.

## Size and split

| | Answerable | Without evidence | Total |
| --- | ---: | ---: | ---: |
| dev | 15 | 3 | 18 |
| test | 24 | 6 | 30 |

Answerable test questions, one main group each (a question may carry extra tags):

| Group | Test | Dev |
| --- | ---: | ---: |
| Bảng | 6 | 3 |
| Ảnh, sơ đồ | 5 | 3 |
| Biểu đồ | 5 | 4 |
| Multi-hop | 4 | 2 |
| Text | 4 | 3 |

The split was fixed before any retrieval or agent run of the advanced challenge, and test is run once after the pipeline is chosen on dev.

## Fields

- `id`, `split`, `group` (`bang`, `anh_so_do`, `bieu_do`, `multi_hop`, `text`, `thieu_bang_chung`), `tags`, `question`.
- Answerable: `expected_answer`, `grading` (what counts as right: values, units, tolerance, required parts), `reason` (why it belongs to its group), and `evidence`.
  - Each evidence item has `need`, `page` (PDF page), `locator` (figure, table, row, column or paragraph), `chunk_ids` (alternatives that hold it), `value`, `check_text` (strings that must occur in those chunks) and `visual_only` (true when the value exists only in the image, so it is checked by eye on the crop).
  - A multi-hop question lists one evidence item per required piece; the evidence is complete when every item has at least one of its chunks in the final context.
- Without evidence: `expected_behavior`, and `absence_check` with `terms` (none occurs in any chunk of the document, searched over the text, the tables and the text inside figures), `why`, and `near_topic_in` (the nearest content, to show the question is on topic).

## How it was written and checked

- **Written by** the assistant from the page images and the extracted text, then reviewed by the author against the PDF (the same-author limit applies: questions favour what is easy to see in the report).
- **Gold is never given to the pipeline**: the agent and the retrievers see only the question text.
- **Checked by script** (`verify_benchmark`): quotas; every evidence chunk exists and is on the stated page; every `check_text` occurs in the chunks; every calculation in an expected answer is recomputed (10 of them); no term of an absent question occurs in the document; no question text repeats.
  The script caught two absence terms that were too broad (the report does mention carbon capture and national EV sales, but gives no cost per tonne and no company figures), which were narrowed to the missing fact.
- **Checked by eye** on the crops and PDF pages: the 7 visual-only evidence items (values read off an axis, colours, map positions, text inside raster images).
- **Dev and test do not share an answer.**
  Some figures appear in both splits with different questions (Hình 12, 13, 21 and 22, Bảng 5), and no dev answer is a component of a test calculation: the dev Bảng 5 question asks for the net total, and the test sum uses the component rows.

## Grading rules for test (ADVANCED.md section 3)

Each test question is pass or fail.
Answerable: right and complete, with the unit, condition and calculation if any; the citation identifies the page and the region, and the evidence supports the whole answer.
Partly right, a wrong citation or a refusal is a fail.
Without evidence: a refusal or a statement that the evidence is not enough, with no unsupported claim; a guess is a fail.
A system error, a timeout or no result is a fail and is reported separately, not removed from the 30.
Pass rate = passes / 30; the threshold is 27/30, with no rounding.

## Known limits

- Six questions have values read off an axis or colours read off an image; their tolerance is in `grading`.
- Questions are in Vietnamese on a Vietnamese edition, so the cross-language gap of the base lab does not apply here.
- The report states that its CGE numbers are model estimates; the benchmark asks for what the report says, not whether it is true.
