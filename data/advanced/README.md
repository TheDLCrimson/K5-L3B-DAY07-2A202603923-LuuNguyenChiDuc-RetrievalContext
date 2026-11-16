# Advanced challenge: document and index

## Document

World Bank, *Việt Nam: Báo cáo về Khí hậu và Phát triển* (Vietnam Country Climate and Development Report, CCDR), July 2022, Vietnamese full edition.

| Field | Value |
| --- | --- |
| Record | <https://openknowledge.worldbank.org/handle/10986/37618> |
| File | `CCDR Full report VIE_11.07.pdf`, 3,764,665 bytes, 103 pages |
| SHA-256 | `a40a23396ee0d35f5ba14bf7fe7cd80f47d237b8793645496df82a4f40a7d28a` |
| Rights | CC BY 3.0 IGO on the record; page 2 of the PDF allows copying in whole or in part for non-commercial purposes with full attribution |
| In this repo | Not the PDF: `python -m src.advanced.source` downloads it to `data/advanced/source/` (gitignored) and checks the hash. The crops and extracted text are committed under the attribution terms above |

The English edition of the same report has 98 pages, below the 100-page minimum, so the Vietnamese edition is used.
Page numbers below are PDF page indexes (1-103); each chunk also keeps the printed page label.

## What was indexed

| | Count |
| --- | --- |
| Pages indexed | 97 of 103 |
| Pages excluded | 6: cover (1), title page (3), table of contents (4-7) |
| Chunks | 384: 334 text, 22 figures, 28 table parts |
| Figure and table regions (crops) | 40: Hình 1-22, Bảng 1-6 (Bảng 5 runs onto the next page), and 12 uncaptioned tables (abbreviations, appendix data and the priority matrix) |
| Region descriptions | 40, by `anthropic/claude-haiku-5.5`, $0.041 in total |
| Index | pgvector table `adv_chunks` in the Day 6 container, `intfloat/multilingual-e5-base` (revision as Day 6), 768-d, exact cosine |

The table of contents is excluded because it repeats every caption and would pull searches to the wrong page.
Twelve pages are nearly empty (dividers, blank pages, the back cover); their text is indexed as it is.

## Pipeline

1. `python -m src.advanced.source` downloads and verifies the PDF.
2. `python -m src.advanced.extract` cuts each figure and table from the page layout ([src/advanced/extract.py](../../src/advanced/extract.py) explains the rules), saves a 150 dpi crop per region in `crops/`, and writes `chunks.json` and `extract_report.json`.
   - Text: every line outside a region, without the running header and page number, packed per page into chunks of at most 1,000 characters at block boundaries.
   - Tables with ruled cells: markdown from PyMuPDF table detection, with the header row re-read from each header cell, since detection drops the spaces in header cells.
   - Borderless numeric tables (appendix p94-97): rebuilt row by row from word positions, with the header lines above them.
   - Text-heavy tables (the priority matrix, p100-102): one line per text block, which keeps each cell whole; which row and column a cell belongs to is visible in the crop and stated in the description.
   - Long tables are split into parts of about 1,500 characters, each repeating the header rows.
   - Figures: the caption, plus all text inside the region (labels, values, legends, notes).
3. `python -m src.advanced.describe` sends each crop with its caption and region text to the vision model and writes `descriptions.json` (prompt, model, cost, and per region the numbers not found in the region text).
4. `python -m src.advanced.index build` embeds every chunk into `adv_chunks`; figure and table chunks carry the description after a marker saying it is model-generated.

## Checks against the original

- **Region boundaries:** all 40 crops were viewed against their pages.
  Each holds the whole figure or table from its caption to its source line.
  Six boundary errors found this way, while checking crops and again while writing benchmark questions, were fixed in the rules: an italic subtitle between caption and chart, axis labels below the plot area, a map's clip path reaching past the source line (this one has a test), rotated axis labels that start inside the plot and run below it (Hình 8 and 16), series labels hanging past the right edge (Hình 7), and the last row of four tables clipped by a point or two.
  A script then checks every crop for text cut at its edges: 0 found.
- **Tables:** Bảng 1 and the first rows of the p95 appendix table were compared with the page images and match, including the report's own "1.08,9" for Malaysia in Bảng 1.
- **Descriptions:** of 848 numbers in the descriptions, 672 also appear in the text extracted from the same region.
  Most of the other 176 are marked as estimates read off an axis ("khoảng"), or are counts and years; raster figures (Hình 4, 9, 10, 11) have no region text, so none of their numbers can be checked this way.
  Read in full against the crop: Hình 20 (all 18 values correct) and the p100 priority matrix (every action in the right cell, 7 / 4 / 4 / 7 per cell).
- **Vision model, before indexing:** 11 questions on four figures, answers read by hand: 10 correct.
  The miss was a direction on the Hình 14 map (it named a coal area south-east of Hà Nội as south-west).

Descriptions are search aids, not evidence: benchmark answers are graded against the page, and the agent reads values from the crop before it uses them.

## Not handled, and the effect

| Part | Why | Effect |
| --- | --- | --- |
| Photos on the six chapter divider pages | Decorative | Not described; their photo credits are indexed as text |
| Raster maps and chart (Hình 4, 9, 10, 11) | No text inside the image | Only the caption, notes and the model's description are searchable; values come from looking at the crop |
| Unlabelled values in charts | Not printed | Descriptions give estimates marked "khoảng"; questions on them need a reading off the axis |
| Header of the p97 table | The "0" in "bằng 0" splits the rebuilt header | The column groups are clear in the crop and the description |
| Chunks longer than 512 tokens (some tables and figures with descriptions) | Model limit | Dense search and the reranker read the first 512 tokens; BM25 reads everything |
