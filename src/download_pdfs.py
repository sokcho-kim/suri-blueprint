"""
HIRA 전자자료 PDF 다운로드 파이프라인

우선순위별로 PDF를 다운로드하고 제목 기반 파일명으로 저장.
"""

import json
import re
import sys
import time
from pathlib import Path

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
DATA_DIR = Path(__file__).parent.parent / "data"
DOWNLOADS_DIR = Path(__file__).parent.parent / "downloads"
EBOOK_LIST = DATA_DIR / "ebook_list.json"

# 우선순위별 다운로드 대상 (pdf_path로 식별)
TARGETS = {
    "P0": [
        "/ebooksc/2026/01/BZ202601272870622.pdf",  # KDRG V4.7 분류집
        "/ebooksc/2026/01/BZ202601272870628.pdf",  # KDRG V4.7 분류집(부록)
        "/ebooksc/2026/01/BZ202601272870642.pdf",  # KDRG 신포괄용 V1.6
        "/ebooksc/2026/01/BZ202601202839800.pdf",  # KOPG V2.7 분류집
        "/ebooksc/2026/03/BZ202603243124987.pdf",  # KDRG-KM V2.2 분류집
        "/ebooksc/2026/03/BZ202603243124965.pdf",  # KOPG-KM V3.1 분류집
        "/ebooksc/2026/03/BZ202603233119206.pdf",  # KRPG V2.2 분류집
    ],
    "P1": [
        "/ebooksc/2026/03/BZ202603053039374.pdf",  # 2026년 1월판 건강보험요양급여비용
        "/ebooksc/2026/03/BZ202603123071288.pdf",  # 포괄수가제 요양급여비용 및 청구방법
        "/ebooksc/2026/03/BZ202603163084309.pdf",  # 2026 의료급여 실무편람
    ],
    "P2": [
        "/ebooksc/2026/01/BZ202601052750163.pdf",  # 암환자 약제 적용기준 세부사항
        "/ebooksc/2026/01/BZ202601202839720.pdf",  # 2025년 약제업무 규정 모음집
    ],
}


def sanitize_filename(title: str) -> str:
    """파일명에 쓸 수 없는 문자 제거"""
    name = re.sub(r'[<>:"/\\|?*]', "", title)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def load_ebook_index() -> dict[str, dict]:
    """pdf_path → item 매핑"""
    items = json.loads(EBOOK_LIST.read_text(encoding="utf-8"))
    return {item["pdf_path"]: item for item in items}


def download_file(url: str, dest: Path) -> bool:
    """PDF 다운로드. 이미 있으면 스킵."""
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  SKIP (exists): {dest.name}")
        return True

    try:
        r = requests.get(url, headers=HEADERS, timeout=60, stream=True)
        r.raise_for_status()

        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        size_mb = dest.stat().st_size / (1024 * 1024)
        print(f"  OK: {dest.name} ({size_mb:.1f} MB)")
        return True

    except Exception as e:
        print(f"  FAIL: {url} -> {e}")
        return False


def main():
    index = load_ebook_index()
    priorities = sys.argv[1:] if len(sys.argv) > 1 else ["P0"]

    for priority in priorities:
        paths = TARGETS.get(priority, [])
        if not paths:
            print(f"Unknown priority: {priority}")
            continue

        out_dir = DOWNLOADS_DIR / priority
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n=== {priority} ({len(paths)}건) ===")

        ok, fail = 0, 0
        for pdf_path in paths:
            item = index.get(pdf_path)
            if not item:
                print(f"  NOT FOUND in index: {pdf_path}")
                fail += 1
                continue

            filename = sanitize_filename(item["title"]) + ".pdf"
            url = f"https://www.hira.or.kr{pdf_path}"
            dest = out_dir / filename

            if download_file(url, dest):
                ok += 1
            else:
                fail += 1

            time.sleep(1)

        print(f"\n{priority} 완료: {ok} 성공, {fail} 실패")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
