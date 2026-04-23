"""
HIRA 전자자료 게시판 ebook 목록 메타데이터 수집

출력: data/ebook_list.json
"""

import json
import time
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.hira.or.kr/ra/ebook/list.do?pgmid=HIRAA030402000000"
PDF_BASE = "https://www.hira.or.kr"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
OUTPUT = Path(__file__).parent.parent / "data" / "ebook_list.json"


def fetch_page(page: int) -> list[dict]:
    """한 페이지의 ebook 목록을 파싱"""
    r = requests.post(
        BASE_URL,
        data={"pageIndex": str(page), "searchKeyWrd": "", "searchWrd": ""},
        headers=HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    items = soup.select("div.txtBox")
    results = []

    for item in items:
        tit_el = item.select_one("p.tit")
        spans = item.select("span")
        link = item.select_one("a.btn_file")

        title = tit_el.get_text(strip=True) if tit_el else ""
        dept = spans[0].get_text(strip=True) if len(spans) > 0 else ""
        date = spans[1].get_text(strip=True) if len(spans) > 1 else ""
        pdf_path = link["href"] if link and link.has_attr("href") else ""
        pdf_url = f"{PDF_BASE}{pdf_path}" if pdf_path else ""

        if title:
            results.append({
                "title": title,
                "department": dept,
                "date": date[:10],  # YYYY-MM-DD
                "pdf_url": pdf_url,
                "pdf_path": pdf_path,
            })

    return results


def scrape_all() -> list[dict]:
    """전체 페이지 순회하며 목록 수집"""
    all_items = []
    page = 1

    while True:
        print(f"  page {page}...", end=" ", flush=True)
        items = fetch_page(page)
        print(f"{len(items)} items")

        if not items:
            break

        all_items.extend(items)
        page += 1
        time.sleep(0.5)  # 서버 부하 방지

    # 중복 제거 (pdf_url 기준)
    seen = set()
    unique = []
    for item in all_items:
        key = item["pdf_url"] or item["title"]
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


def main():
    print("HIRA 전자자료 목록 수집 시작")
    items = scrape_all()
    print(f"\n총 {len(items)}건 수집 완료")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장: {OUTPUT}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
