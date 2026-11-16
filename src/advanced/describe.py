"""Describe each figure and table crop with a vision model, and check the description's numbers.

For every region crop (figures and tables, one call per crop, cached), the model gets the image,
the caption and the text found inside the region (labels, values, legends), and writes a short
Vietnamese description: chart type, axes and units, legend, every value printed on the figure
attached to its bar, series or place, and the main trends. It is told not to read unlabelled
values off an axis unless it marks them "khoảng" (about).

A description is model output, not evidence. Each number in it is checked against the region
text extracted from the PDF: a number that is not there is listed under `unverified`, and the
regions with unverified numbers are checked by eye against the crop (raster images have no
region text, so all their numbers are unverified). Answers are graded against the page, never
against a description.

Writes data/advanced/descriptions.json.
Run from the repo root:  python -m src.advanced.describe
"""
import base64
import json
import re
import time
from datetime import UTC, datetime

from dotenv import load_dotenv

from ..providers import Provider
from .source import DATA_DIR

PROMPT_VERSION = 1
SYSTEM = """Bạn mô tả hình và bảng trong một báo cáo của Ngân hàng Thế giới để người khác tìm kiếm và đối chiếu.
Viết tiếng Việt, tối đa 220 từ, dạng các dòng ngắn:
- Loại: (biểu đồ cột chồng, đường, tròn, treemap, bản đồ, sơ đồ, bảng...)
- Nội dung: hình thể hiện gì, đơn vị, trục, chú giải, kịch bản hoặc nhóm.
- Giá trị: mọi giá trị được in trên hình, gắn đúng với cột, chuỗi, nhóm hoặc địa danh của nó. Với bảng, nêu cấu trúc hàng, cột và các ô quan trọng; với ma trận, nêu ô nào thuộc hàng, cột nào.
- Xu hướng: điểm cao nhất, thấp nhất, thay đổi chính.
Chỉ dựa vào hình và phần chữ trích từ hình. Không bịa giá trị: giá trị không được in mà phải ước lượng từ trục thì ghi "khoảng". Với bản đồ, nêu các địa danh được ghi và điều gì được đánh dấu ở đâu (hướng so với các địa danh khác)."""


def numbers(text: str) -> set[str]:
    """Numbers as written (1.234,5 / 12% / -0,23), normalised to digits and one decimal comma."""
    out = set()
    for m in re.findall(r"\d[\d.,]*", text):
        m = m.rstrip(".,")
        if m:
            out.add(m.replace(".", "").replace(",", "."))
    return out


def describe() -> None:
    load_dotenv()
    chunks = json.loads((DATA_DIR / "chunks.json").read_text(encoding="utf-8"))
    path = DATA_DIR / "descriptions.json"
    cache = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"regions": {}}
    provider = Provider()
    regions: dict[str, dict] = {}
    for c in chunks:  # one region per crop; table parts share their crop
        if c["crop"]:
            r = regions.setdefault(c["crop"], {"ids": [], "title": c["title"], "page": c["page"], "kind": c["kind"],
                                               "text": ""})
            r["ids"].append(c["id"])
            r["text"] += "\n" + c["text"]
    for crop, r in regions.items():
        key = crop
        cached = cache["regions"].get(key)
        if cached and cached.get("prompt_version") == PROMPT_VERSION and cached.get("model") == provider.model:
            continue
        image = base64.b64encode((DATA_DIR / crop).read_bytes()).decode()
        user = (f"Tiêu đề: {r['title']}\nTrang PDF: {r['page']}\nChữ trích từ vùng này (có thể thiếu hoặc lộn thứ tự):\n"
                f"{r['text'][:3000]}")
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": [{"type": "text", "text": user},
                                                 {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image}"}}]}]
        start = time.perf_counter()
        reply = provider.complete(messages, [])
        text = (reply["message"].get("content") or "").strip()
        found, source = numbers(text), numbers(r["text"] + " " + r["title"])
        cache["regions"][key] = {
            "ids": r["ids"], "page": r["page"], "kind": r["kind"], "title": r["title"], "description": text,
            "unverified": sorted(found - source, key=lambda x: float(x) if x.replace(".", "", 1).isdigit() else 0),
            "numbers": len(found), "model": provider.model, "prompt_version": PROMPT_VERSION,
            "cost_usd": float(reply["usage"].get("cost") or 0), "ms": round((time.perf_counter() - start) * 1000, 1)}
        print(f"{crop}: {len(found)} numbers, unverified {len(found - source)}")
    cache["system_prompt"] = SYSTEM
    cache["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    cache["cost_usd"] = round(sum(v["cost_usd"] for v in cache["regions"].values()), 6)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(cache['regions'])} regions described, total cost ${cache['cost_usd']}")


if __name__ == "__main__":
    describe()
