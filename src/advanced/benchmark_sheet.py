"""Writes data/advanced/benchmark/review_sheet.md: every question next to its evidence.

For each question: the question, the expected answer, the grading rule, and for every piece
of evidence the PDF page (and the printed page label), where on the page, the value, and the
crop image of the figure or table (or the passage, for text). A reviewer checks each against
the original PDF page; the sheet does not replace opening the page.

Run from the repo root:  python -m src.advanced.benchmark_sheet
"""
import json

from .source import DATA_DIR

BENCH = DATA_DIR / "benchmark"
GROUPS = {"bang": "Bảng", "anh_so_do": "Ảnh, sơ đồ", "bieu_do": "Biểu đồ", "multi_hop": "Multi-hop",
          "text": "Text", "thieu_bang_chung": "Thiếu bằng chứng"}


def snippet(text: str, needles: list[str], width: int = 260) -> str:
    for n in needles:
        i = text.find(n)
        if i >= 0:
            return text[max(0, i - width // 2): i + width // 2].replace("\n", " ")
    return text[:width].replace("\n", " ")


def main() -> None:
    questions = json.loads((BENCH / "questions.json").read_text(encoding="utf-8"))
    chunks = {c["id"]: c for c in json.loads((DATA_DIR / "chunks.json").read_text(encoding="utf-8"))}
    lines = ["# Review sheet: advanced benchmark", "",
             "Check every question against the original PDF page, not only against this sheet.",
             "Each question has one main group; the answer, the grading rule and the evidence must agree with the page.", ""]
    for split in ("dev", "test"):
        qs = [q for q in questions if q["split"] == split]
        lines += [f"## {split}: {len(qs)} questions", ""]
        for q in qs:
            lines += [f"### {q['id']} ({GROUPS[q['group']]}{', ' + ', '.join(q['tags']) if q['tags'] else ''})", "",
                      f"**Câu hỏi:** {q['question']}", ""]
            if not q["answerable"]:
                a = q["absence_check"]
                lines += [f"**Hành vi mong đợi:** {q['expected_behavior']}", "",
                          f"**Vì sao không trả lời được:** {a['why']}", "",
                          f"**Từ khóa đã tìm trong toàn bộ tài liệu (0 kết quả):** {', '.join(a['terms'])}", "",
                          f"**Gần chủ đề ở:** {a['near_topic_in']}", ""]
                continue
            lines += [f"**Đáp án:** {q['expected_answer']}", "", f"**Cách chấm:** {q['grading']}", "",
                      f"**Lý do thuộc nhóm:** {q['reason']}", ""]
            for e in q["evidence"]:
                first = chunks[e["chunk_ids"][0]]
                label = first["page_label"]
                lines += [f"- **Evidence:** {e['need']}",
                          f"  - PDF trang {e['page']} (số trang in: {label}); vị trí: {e['locator']}; giá trị: {e['value']}",
                          f"  - chunk: {', '.join(e['chunk_ids'])}"
                          + ("; **chỉ kiểm tra được bằng mắt trên hình**" if e["visual_only"] else "")]
                if first["crop"]:
                    lines += [f"  - ![{first['id']}](../{first['crop']})"]
                else:
                    lines += [f"  - đoạn: \"{snippet(first['text'], e['check_text'])}\""]
            lines += [""]
    (BENCH / "review_sheet.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {BENCH / 'review_sheet.md'}")


if __name__ == "__main__":
    main()
