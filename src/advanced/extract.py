"""Extract every useful part of the report into text, table and figure chunks, with crops.

Layout rules (from reading the pages, not from any benchmark question):
- A figure or table starts at its caption line ("Hình N:", "Bảng N." ...). It runs over the
  graphics below it (vector drawings, embedded images, detected tables), taken while each
  next graphic starts within GAP points of the region so far, then over the source and note
  lines right under them ("Nguồn", "Ghi chú", "Lưu ý"), including their wrapped lines.
  A caption in the right column (x0 > 300) gives a right-column region; otherwise the region
  spans the text width.
- A detected table outside every captioned region is either the continuation of the last
  captioned table (on the next page) or an uncaptioned table (abbreviations, appendix data);
  it is titled by the nearest text line above it.
- Every other line is text. The running header and page number are dropped. Text is packed
  per page into chunks of at most TEXT_CHARS characters, split at block boundaries.
- Excluded pages: the cover, the title page and the table of contents (EXCLUDED); the TOC
  lists every caption and would pull searches to the wrong page.
Figures keep the text inside their region (labels, values, legends) next to the caption; what
that text cannot say (which value belongs to which bar, what a map shows) is added later by
src/advanced/describe.py and checked against the region text.

Writes data/advanced/chunks.json, data/advanced/crops/<id>.png (150 dpi) and
data/advanced/extract_report.json.
Run from the repo root:  python -m src.advanced.extract
"""
import json
import re
from typing import Any

from .source import DATA_DIR, open_pdf

CAPTION = re.compile(r"^(Hình|Bảng)\s+(\d+)\s*[.:]\s*(.*)")
NOTE = ("Nguồn", "Ghi chú", "Lưu ý")
HEADER = re.compile(r"^(?:[ivx]+|\d+)?\s*\|?\s*Việt Nam: Báo cáo về Khí hậu và Phát triển\s*\|?\s*(?:\d+)?$")
PAGE_LABEL = re.compile(r"^(?:\d+|[ivx]+)$")
EXCLUDED = {1: "bìa", 3: "trang tên báo cáo", 4: "mục lục", 5: "mục lục", 6: "mục lục (danh sách hộp, bảng)",
            7: "mục lục (danh sách hình)"}
GAP = 40
LABEL_SIZE = 9.5  # body text is larger; chart labels and legends are smaller
BODY_SIZE = 10.4  # body paragraphs are set in 10.5 pt
LABEL_GAP = 30  # axis labels can sit this far below the plotted area
TEXT_CHARS = 1000
TABLE_CHARS = 1500
CROP_DPI = 150
DOC = "CCDR"


def page_lines(page) -> list[dict[str, Any]]:
    out = []
    for bi, b in enumerate(page.get_text("dict")["blocks"]):
        for line in b.get("lines", []):
            text = "".join(s["text"] for s in line["spans"]).strip()
            if text:
                out.append({"rect": tuple(line["bbox"]), "text": text, "block": bi,
                            "size": round(line["spans"][0]["size"], 1)})
    return out


def is_furniture(line: dict, height: float) -> bool:
    y0, y1 = line["rect"][1], line["rect"][3]
    edge = y1 < 60 or y0 > height - 60
    return edge and (HEADER.match(line["text"]) is not None or PAGE_LABEL.match(line["text"]) is not None)


def page_label(lines: list[dict], height: float) -> str | None:
    for line in lines:
        y0, y1 = line["rect"][1], line["rect"][3]
        if (y1 < 60 or y0 > height - 60):
            m = re.match(r"^(\d+|[ivx]+)\b", line["text"]) or re.search(r"(\d+)$", line["text"])
            if m and (PAGE_LABEL.match(line["text"]) or HEADER.match(line["text"])):
                return m.group(1)
    return None


def inside(rect, region, pad: float = 1.0) -> bool:
    cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
    return region[0] - pad <= cx <= region[2] + pad and region[1] - pad <= cy <= region[3] + pad


def graphics(page) -> list[tuple]:
    """Drawings, images and tables, without full-width thin rules (section separators)."""
    out = []
    for d in page.get_drawings():
        r = d["rect"]
        if r.width > 400 and r.height < 2:
            continue
        out.append(tuple(r))
    out += [tuple(i["bbox"]) for i in page.get_image_info()]
    return out


def caption_title(lines: list[dict], i: int) -> tuple[str, float]:
    """The caption line plus the lines that wrap it (same size and left edge, directly below)."""
    cap = lines[i]
    title, bottom = cap["text"], cap["rect"][3]
    for nxt in lines[i + 1:]:
        if (abs(nxt["rect"][0] - cap["rect"][0]) < 3 and abs(nxt["size"] - cap["size"]) < 0.2
                and 0 <= nxt["rect"][1] - bottom < 4):
            title, bottom = f"{title} {nxt['text']}", nxt["rect"][3]
        else:
            break
    return title, bottom


def region_for(page, lines, i, next_top, shapes, tables) -> dict[str, Any]:
    cap = lines[i]
    title, title_bottom = caption_title(lines, i)
    right = cap["rect"][0] > 300
    x0, x1 = (cap["rect"][0] - 5, page.rect.width - 60) if right else (60, page.rect.width - 60)
    top = cap["rect"][1] - 2
    band = [r for r in shapes + tables
            if r[1] >= title_bottom - 2 and r[3] <= next_top + 1 and x0 - 10 <= (r[0] + r[2]) / 2 <= x1 + 10]
    body = [ln["rect"][1] for ln in lines
            if ln["size"] >= BODY_SIZE and len(ln["text"]) > 40 and x0 - 5 <= ln["rect"][0] <= x1]
    end, left, right = title_bottom, x0, x1
    # graphics stop at the first source or note line: anything below it (a footnote rule, the bullet
    # of the next paragraph) belongs to the page, not the figure
    stop = min([ln["rect"][1] for ln in lines if ln["text"].startswith(NOTE) and title_bottom < ln["rect"][1] < next_top
                and x0 - 5 <= ln["rect"][0] <= x1] + [next_top])
    for r in sorted(band, key=lambda r: r[1]):
        if r[1] >= stop:
            break
        # a graphic joins the region if it is close, or if no paragraph of body text separates them
        # (an italic subtitle or unit line can sit between the caption and the chart)
        if r[1] <= end + GAP or not any(end < y < r[1] for y in body):
            end = max(end, r[3])
            left, right = min(left, r[0]), max(right, r[2])
    if stop < next_top:  # a drawing (e.g. a map's clip path) can reach past the source line
        end = min(end, stop - 1)
    # below the graphics: small-font labels (axes, legends), then source and note lines with their wraps
    below = sorted((ln for ln in lines if x0 - 5 <= ln["rect"][0] <= x1 and end - 3 <= ln["rect"][1] < next_top),
                   key=lambda ln: ln["rect"][1])
    in_notes = False
    for line in below:
        r = line["rect"]
        gap = r[1] - end
        if line["text"].startswith(NOTE) and gap < 25:
            in_notes, end = True, max(end, r[3])
        elif (in_notes and gap < 5) or (not in_notes and line["size"] < LABEL_SIZE and gap < LABEL_GAP):
            end = max(end, r[3])  # a wrapped note line, or an axis label or legend below the graphics
        elif r[1] > end:
            break
    # a graphic wider than the text column (a full-bleed image) widens the region, within the page
    rect = (max(left - 2, 20), top, min(right + 2, page.rect.width - 20), min(end + 2, next_top - 1))
    m = CAPTION.match(cap["text"])
    return {"kind": "figure" if m.group(1) == "Hình" else "table", "label": f"{m.group(1)} {m.group(2)}",
            "title": title, "rect": rect}


def chunk_text(lines: list[dict]) -> list[tuple[str, tuple]]:
    """Pack lines into chunks of at most TEXT_CHARS, splitting at block boundaries when possible."""
    blocks: dict[int, list[dict]] = {}
    for line in lines:
        blocks.setdefault(line["block"], []).append(line)
    chunks, cur, rects = [], "", []
    for bl in blocks.values():
        text = " ".join(line["text"] for line in bl)
        text = re.sub(r"\s+", " ", text).strip()
        if cur and len(cur) + 1 + len(text) > TEXT_CHARS:
            chunks.append((cur, union(rects)))
            cur, rects = "", []
        while len(text) > TEXT_CHARS:  # a block longer than the limit is cut at a sentence end
            cut = text.rfind(". ", 0, TEXT_CHARS) + 1 or TEXT_CHARS
            chunks.append((text[:cut].strip(), union([line["rect"] for line in bl])))
            text = text[cut:].strip()
        cur = f"{cur} {text}".strip()
        rects += [line["rect"] for line in bl]
    if cur:
        chunks.append((cur, union(rects)))
    return chunks


def union(rects) -> tuple:
    return (min(r[0] for r in rects), min(r[1] for r in rects), max(r[2] for r in rects), max(r[3] for r in rects))


def rnd(rect) -> list[float]:
    return [round(v, 1) for v in rect]


NUMBER = re.compile(r"^[-+]?(?:\d[\d.,]*%?|N\.?A|-)$")


def poor_markdown(md: str) -> bool:
    """Borderless numeric tables come out of table detection as whole columns packed into a cell."""
    cells = [c for row in md.splitlines()[2:] for c in row.strip("|").split("|")]
    return bool(cells) and (sum("<br>" in c for c in cells) / len(cells) > 0.3 or max(map(len, cells)) > 300)


def grow_up(lines: list[dict], rect: tuple) -> tuple:
    """Extend a borderless table upward over the small-font header lines directly above it."""
    top = rect[1]
    for line in sorted((ln for ln in lines if ln["rect"][3] <= rect[1] + 1), key=lambda ln: -ln["rect"][3]):
        r = line["rect"]
        if top - r[3] > 25:
            break
        if line["size"] >= BODY_SIZE or not (rect[0] - 10 <= r[0] <= rect[2]):
            continue
        top = min(top, r[1])
    return (rect[0], top - 1, rect[2], rect[3])


def spaced_header(page, table) -> str:
    """Markdown with the header row read from each header cell's box: table detection drops the
    spaces between words in header cells, clipping the page text keeps them."""
    import pymupdf

    rows = table.to_markdown().strip().splitlines()
    cells = table.header.cells
    if rows and len(cells) == rows[0].strip("|").count("|") + 1:
        rows[0] = "|" + "|".join(" ".join(page.get_text("text", clip=pymupdf.Rect(c)).split()) if c else ""
                                 for c in cells) + "|"
    return "\n".join(rows)


def numeric_share(page, rect) -> float:
    import pymupdf

    words = [w[4] for w in page.get_text("words", clip=pymupdf.Rect(*rect))]
    return sum(bool(NUMBER.match(w)) for w in words) / max(len(words), 1)


def cell_blocks(page, rect) -> str:
    """A text-heavy table (a matrix of actions): one line per text block, which keeps each cell whole."""
    import pymupdf

    blocks = page.get_text("blocks", clip=pymupdf.Rect(*rect), sort=True)
    return "\n".join(" ".join(b[4].split()) for b in blocks if b[4].strip())


def rows_from_words(page, rect) -> str:
    """Rebuild a borderless table row by row from word positions: 'label | value | value ...'.

    A line with no number is joined to the numeric line right below it, so a row keeps its
    section heading and a label that wraps onto two lines.
    """
    import pymupdf

    words = sorted(page.get_text("words", clip=pymupdf.Rect(*rect)), key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    lines: list[list] = []
    for w in words:
        cy = (w[1] + w[3]) / 2
        if lines and abs(cy - lines[-1][0]) < 3:
            lines[-1][1].append(w)
        else:
            lines.append([cy, [w]])
    rows, pending = [], ""
    for cy, ws in lines:
        ws.sort(key=lambda w: w[0])
        label = " ".join(w[4] for w in ws if not NUMBER.match(w[4]))
        values = [w[4] for w in ws if NUMBER.match(w[4])]
        if not values:
            pending = f"{pending} {label}".strip()
            continue
        rows.append(" | ".join([f"{pending} {label}".strip()] + values))
        pending = ""
    if pending:
        rows.append(pending)
    return "\n".join(rows)


def split_table(md: str, limit: int = TABLE_CHARS) -> list[str]:
    """Split a markdown table into parts of about `limit` characters, each with the header rows."""
    rows = md.strip().splitlines()
    if len(md) <= limit or len(rows) < 4:
        return [md.strip()]
    if rows[1].startswith("|-") or rows[1].startswith("|:"):
        k = 2
    else:  # rebuilt rows: the header is every line before the first one with a label and two values
        k = next((i for i, r in enumerate(rows)
                  if r.count("|") >= 4 and re.search(r"[^\W\d_]", r.split("|")[0])), 0)
    head, body = rows[:k], rows[k:]
    parts, cur = [], []
    for row in body:
        if cur and len("\n".join(head + cur + [row])) > limit:
            parts.append("\n".join(head + cur))
            cur = []
        cur.append(row)
    parts.append("\n".join(head + cur))
    return parts


def squeeze_markdown(md: str) -> str:
    """Drop the empty columns that table detection leaves in wide layouts."""
    rows = [r.strip().strip("|").split("|") for r in md.strip().splitlines()]
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    keep = [j for j in range(width) if any(re.sub(r"[-:\s]", "", rows[i][j]) for i in range(len(rows)) if i != 1)]
    return "\n".join("|" + "|".join(rows[i][j].strip() for j in keep) + "|" for i in range(len(rows)))


def table_title(lines: list[dict], top: float) -> str:
    above = [ln for ln in lines if top - 60 < ln["rect"][3] <= top + 1 and ln["size"] >= BODY_SIZE]
    return above[-1]["text"] if above else "Bảng không có tiêu đề"


def extract() -> None:
    import pymupdf

    doc = open_pdf()
    crops = DATA_DIR / "crops"
    crops.mkdir(parents=True, exist_ok=True)
    for old in crops.glob("*.png"):
        old.unlink()
    chunks: list[dict[str, Any]] = []
    report: dict[str, Any] = {"pages": {}, "excluded": {}, "uncaptioned_tables": [], "continued_tables": []}
    last_table: dict[str, Any] | None = None  # the last table seen: page, bottom, label, title
    for page in doc:
        n = page.number + 1
        lines = page_lines(page)
        label = page_label(lines, page.rect.height)
        if n in EXCLUDED:
            report["excluded"][n] = EXCLUDED[n]
            continue
        lines = [ln for ln in lines if not is_furniture(ln, page.rect.height)]
        shapes = graphics(page)
        found = page.find_tables().tables
        table_md = {}
        for t in found:
            bbox, md = tuple(t.bbox), squeeze_markdown(spaced_header(page, t))
            if poor_markdown(md):
                bbox = grow_up(lines, bbox)
                md = rows_from_words(page, bbox) if numeric_share(page, bbox) > 0.3 else cell_blocks(page, bbox)
            table_md[bbox] = md
        tables = list(table_md)
        caps = [i for i, ln in enumerate(lines) if CAPTION.match(ln["text"]) and "...." not in ln["text"]]
        regions = []
        for j, i in enumerate(caps):
            same_side = [lines[k]["rect"][1] for k in caps[j + 1:]
                         if (lines[k]["rect"][0] > 300) == (lines[i]["rect"][0] > 300)]
            next_top = min(same_side + [page.rect.height - 60])
            regions.append(region_for(page, lines, i, next_top, shapes, tables))
        for t in tables:  # tables outside every captioned region
            if any(inside(t, r["rect"]) for r in regions):
                continue
            continued = (last_table is not None and last_table["page"] == n - 1 and last_table["bottom"] > 580
                         and t[1] < 120 and table_title(lines, t[1]) == "Bảng không có tiêu đề")
            if continued:
                title = last_table["title"].removesuffix(" (tiếp)") + " (tiếp)"
                region = {"kind": "table", "label": last_table["label"], "title": title, "rect": t, "continued": True}
                report["continued_tables"].append({"page": n, "of_page": last_table["first_page"], "title": title})
            else:
                region = {"kind": "table", "label": None, "title": table_title(lines, t[1]), "rect": t}
                report["uncaptioned_tables"].append({"page": n, "title": region["title"]})
            regions.append(region)
        counts = {"text": 0, "figure": 0, "table": 0}
        region_lines = set()
        for k, r in enumerate(regions):
            inner = [ln for ln in lines if inside(ln["rect"], r["rect"])]
            region_lines.update(id(ln) for ln in inner)
            suffix = (r["label"] or "bang").replace(" ", "").replace("Hình", "H").replace("Bảng", "B")
            cid = f"{DOC}-p{n:03d}-{suffix}{'c' if r.get('continued') else ''}"
            if any(c["id"].startswith(cid) for c in chunks):
                cid = f"{cid}{k}"
            crop = crops / f"{cid}.png"
            page.get_pixmap(dpi=CROP_DPI, clip=pymupdf.Rect(*r["rect"])).save(crop)
            base = {"kind": r["kind"], "page": n, "page_label": label, "bbox": rnd(r["rect"]), "label": r["label"],
                    "title": r["title"], "crop": crop.relative_to(DATA_DIR).as_posix()}
            if r["kind"] == "table":
                mds = [md for tb, md in table_md.items() if inside(tb, r["rect"])]
                notes = "\n".join(ln["text"] for ln in inner if ln["text"].startswith(NOTE))
                parts = [p for md in mds for p in split_table(md)] or ["\n".join(ln["text"] for ln in inner)]
                for pi, part in enumerate(parts, 1):
                    pid = cid if len(parts) == 1 else f"{cid}-r{pi}"
                    chunks.append({"id": pid, **base, "text": (part + ("\n" + notes if notes else "")).strip(),
                                   "part": f"{pi}/{len(parts)}" if len(parts) > 1 else None})
                last_table = {"page": n, "bottom": r["rect"][3], "label": r["label"], "title": r["title"],
                              "first_page": last_table["first_page"] if r.get("continued") else n}
            else:
                body = "\n".join(ln["text"] for ln in inner if ln["text"] not in r["title"])
                chunks.append({"id": cid, **base, "text": body.strip(), "part": None})
            counts[r["kind"]] += 1
        rest = [ln for ln in lines if id(ln) not in region_lines]
        for k, (text, rect) in enumerate(chunk_text(rest), 1):
            chunks.append({"id": f"{DOC}-p{n:03d}-t{k:02d}", "kind": "text", "page": n, "page_label": label,
                           "bbox": rnd(rect), "label": None, "title": None, "crop": None, "text": text, "part": None})
            counts["text"] += 1
        report["pages"][n] = {"label": label, **counts, "chars": sum(len(ln["text"]) for ln in lines)}
    (DATA_DIR / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    report["totals"] = {"chunks": len(chunks), **{k: sum(c["kind"] == k for c in chunks)
                                                   for k in ("text", "figure", "table")},
                        "regions": len(list(crops.glob("*.png")))}
    report["sparse_pages"] = [n for n, p in report["pages"].items() if p["chars"] < 200]
    (DATA_DIR / "extract_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n",
                                                  encoding="utf-8", newline="\n")
    print(f"{report['totals']}; excluded pages {sorted(report['excluded'])}; "
          f"uncaptioned tables {len(report['uncaptioned_tables'])}, continued {len(report['continued_tables'])}; "
          f"sparse pages {report['sparse_pages']}")


if __name__ == "__main__":
    extract()
