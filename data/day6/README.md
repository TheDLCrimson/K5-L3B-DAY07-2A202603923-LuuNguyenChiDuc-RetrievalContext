# Day 6 data

This lab searches the index built in the Day 6 lab, [TheDLCrimson/K5-L3B-DAY06-2A202603923-DataIngestion](https://github.com/TheDLCrimson/K5-L3B-DAY06-2A202603923-DataIngestion) at commit `5b5acdc`, without re-indexing anything.

| Item | Value |
| --- | --- |
| Corpus | Luật Đất đai 2013 (45/2013/QH13) and 2024 (31/2024/QH15), official Công báo text, 370 content pages in 4 PDF files |
| Rights | Legal normative documents are not protected by copyright (Luật Sở hữu trí tuệ, Điều 15 khoản 2); the Day 6 manifest lists sources and hashes |
| Chunks | Day 6 strategy B (article, else clause groups, at most 1,000 characters): 1,264 chunks, 237 of them spanning a page break |
| Embedding | `intfloat/multilingual-e5-base` at revision `d128750`, 768 dimensions, L2-normalised; passages indexed as `passage: ` + text, queries embedded as `query: ` + text |
| Vector store | PostgreSQL 16 + pgvector 0.8.7 in the Day 6 Docker container, table `chunks`, rows with `strategy = 'B'`; exact cosine search (no ANN index), `year` filter in SQL |

[chunks.json](chunks.json) is the full export of those rows in the Lab 7 chunk format (`id`, `text`, `source_id`, `source`, `page`, `metadata`).
It was read from pgvector, so it is exactly what dense search ranks, and lexical methods read the same file.
[export_info.json](export_info.json) records the check that produced it:

- the row count, model and vector size matched the Day 6 run;
- all 1,264 chunks matched Day 6's `results/chunks/B.jsonl` on ID, text, pages and content hash;
- one stored vector, re-embedded here, had cosine 1.0 to the stored one, so the query side uses the same model;
- the file's SHA-256 is recorded.

## Rebuild

```bash
# in the Day 6 repo's starter/ folder; -p keeps the Day 6 project name and its data volume
docker compose -p day6_student_starter up -d --wait
# in this repo
cp .env.example .env
python -m src.day6                     # index check
python -m src.export_day6 --day6-repo ../K5-L3B-DAY06-2A202603923-DataIngestion
```

Without `-p day6_student_starter`, Compose names the project after the folder and starts a new, empty database.
