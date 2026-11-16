"""The advanced-challenge document: where it comes from and how to fetch and verify it.

World Bank, "Việt Nam: Báo cáo về Khí hậu và Phát triển" (Vietnam Country Climate and
Development Report, CCDR), July 2022, Vietnamese full edition, 103 pages.
Record: https://openknowledge.worldbank.org/handle/10986/37618 (rights: CC BY 3.0 IGO).
Page 2 of the PDF allows copying in whole or in part for non-commercial purposes with full
attribution. The PDF is not committed; this module downloads it and checks its SHA-256.

Run from the repo root:  python -m src.advanced.source
"""
import hashlib
import urllib.request

from ..day6 import REPO_ROOT

TITLE = "Việt Nam: Báo cáo về Khí hậu và Phát triển (World Bank CCDR, 07/2022, bản tiếng Việt)"
RECORD = "https://openknowledge.worldbank.org/handle/10986/37618"
URL = ("https://openknowledge.worldbank.org/server/api/core/bitstreams/"
       "0e81a56a-8db6-592b-a6f0-2834d974660e/content")
FILE_NAME = "CCDR Full report VIE_11.07.pdf"
SHA256 = "a40a23396ee0d35f5ba14bf7fe7cd80f47d237b8793645496df82a4f40a7d28a"
PAGES = 103
LICENSE = ("CC BY 3.0 IGO (repository record); PDF p.2: sao chép toàn bộ hoặc một phần cho mục đích "
           "phi thương mại, ghi nhận đầy đủ tác phẩm")
DATA_DIR = REPO_ROOT / "data" / "advanced"
PDF_PATH = DATA_DIR / "source" / "ccdr_vi.pdf"


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch() -> None:
    """Download the PDF once and refuse a file whose hash differs from the one indexed."""
    if not PDF_PATH.exists():
        PDF_PATH.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(URL, headers={"User-Agent": "lab-client"})
        with urllib.request.urlopen(req, timeout=180) as r:
            PDF_PATH.write_bytes(r.read())
    digest = sha256(PDF_PATH)
    if digest != SHA256:
        raise SystemExit(f"{PDF_PATH} has SHA-256 {digest}, expected {SHA256}")
    print(f"{PDF_PATH} OK ({SHA256[:12]}...)")


def open_pdf():
    import pymupdf

    fetch()
    doc = pymupdf.open(PDF_PATH)
    if len(doc) != PAGES:
        raise SystemExit(f"expected {PAGES} pages, got {len(doc)}")
    return doc


if __name__ == "__main__":
    fetch()
