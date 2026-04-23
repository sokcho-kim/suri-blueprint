"""
Approach B: PyMuPDF span-level 좌표 기반 정밀 파싱

PDF에서 텍스트 span을 좌표와 함께 추출하고,
X좌표로 4단 컬럼을 분리하여 구조화된 코드 매핑 테이블 생성.
"""

import json
import re
import sys
from pathlib import Path

import fitz

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR = DATA_DIR / "eval" / "approach_b"

# 4단 컬럼 X좌표 경계 (page 12 기준 측정)
# 컬럼1: 진단코드~67, MDC~108, ADRG~140
# 컬럼2: 진단코드~171, MDC~211, ADRG~244
# 컬럼3: 진단코드~275, MDC~315, ADRG~348
# 컬럼4: 진단코드~379, MDC~419, ADRG~452
COLUMN_BOUNDARIES = [
    {"code_x": (60, 105), "mdc_x": (105, 138), "adrg_x": (138, 168)},
    {"code_x": (168, 209), "mdc_x": (209, 242), "adrg_x": (242, 272)},
    {"code_x": (272, 313), "mdc_x": (313, 346), "adrg_x": (346, 376)},
    {"code_x": (376, 417), "mdc_x": (417, 450), "adrg_x": (450, 480)},
]

# 코드 색인 시작/끝 페이지 (0-indexed)
DIAG_START = 10   # page 11
DIAG_END = None    # 자동 감지


def extract_spans(doc: fitz.Document, page_idx: int) -> list[dict]:
    """한 페이지의 모든 텍스트 span 추출"""
    page = doc[page_idx]
    blocks = page.get_text("dict")["blocks"]
    spans = []

    for b in blocks:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            for s in line["spans"]:
                text = s["text"].strip()
                if text:
                    spans.append({
                        "x": s["bbox"][0],
                        "y": s["bbox"][1],
                        "x2": s["bbox"][2],
                        "y2": s["bbox"][3],
                        "text": text,
                    })

    return sorted(spans, key=lambda s: (s["y"], s["x"]))


def is_header_row(spans_in_row: list[dict]) -> bool:
    """헤더 행인지 확인"""
    texts = " ".join(s["text"] for s in spans_in_row)
    return "진단코드" in texts and "MDC" in texts


def is_page_header(span: dict) -> bool:
    """페이지 헤더/푸터인지 확인"""
    text = span["text"]
    if re.match(r'^\d+\s+(KDRG|Diagnosis|진단코드)', text):
        return True
    if text in ("진단코드", "색인") and span["x"] < 50:
        return True
    if re.match(r'^Diagnosis Code Index\s+\d+$', text):
        return True
    return False


def group_by_y(spans: list[dict], tolerance: float = 3.0) -> list[list[dict]]:
    """Y좌표 기준으로 같은 행으로 그룹핑"""
    if not spans:
        return []

    rows = []
    current_row = [spans[0]]
    current_y = spans[0]["y"]

    for s in spans[1:]:
        if abs(s["y"] - current_y) <= tolerance:
            current_row.append(s)
        else:
            rows.append(sorted(current_row, key=lambda s: s["x"]))
            current_row = [s]
            current_y = s["y"]

    if current_row:
        rows.append(sorted(current_row, key=lambda s: s["x"]))

    return rows


def classify_span(span: dict) -> tuple[int, str] | None:
    """span의 X좌표로 (컬럼번호, 필드타입) 결정"""
    x = span["x"]
    for col_idx, bounds in enumerate(COLUMN_BOUNDARIES):
        if bounds["code_x"][0] <= x < bounds["code_x"][1]:
            return (col_idx, "code")
        if bounds["mdc_x"][0] <= x < bounds["mdc_x"][1]:
            return (col_idx, "mdc")
        if bounds["adrg_x"][0] <= x < bounds["adrg_x"][1]:
            return (col_idx, "adrg")
    return None


def parse_page(doc: fitz.Document, page_idx: int, last_codes: dict, last_mdcs: dict) -> list[dict]:
    """한 페이지에서 코드 매핑 추출

    last_codes: 각 컬럼의 마지막 진단코드 (연속 행 처리용)
    last_mdcs: 각 컬럼의 마지막 MDC (ADRG만 있는 연속 행 처리용)
    """
    spans = extract_spans(doc, page_idx)
    rows = group_by_y(spans)
    mappings = []

    for row in rows:
        # 헤더/페이지 정보 스킵
        if is_header_row(row):
            continue
        if any(is_page_header(s) for s in row):
            continue

        # 각 span을 컬럼/필드로 분류
        row_data = {i: {"code": None, "mdc": None, "adrg": None} for i in range(4)}

        for span in row:
            result = classify_span(span)
            if result is None:
                continue
            col_idx, field = result
            row_data[col_idx][field] = span["text"]

        # 매핑 생성
        for col_idx in range(4):
            d = row_data[col_idx]

            # 새 진단코드가 있으면 업데이트
            if d["code"]:
                last_codes[col_idx] = d["code"]

            # 새 MDC가 있으면 업데이트
            if d["mdc"]:
                last_mdcs[col_idx] = d["mdc"]

            # MDC + ADRG가 있으면 매핑 생성
            if d["mdc"] and d["adrg"]:
                code = last_codes.get(col_idx)
                if code:
                    mappings.append({
                        "code": code,
                        "mdc": d["mdc"],
                        "adrg": d["adrg"],
                    })
            # ADRG만 있으면 이전 MDC를 이어받음
            elif d["adrg"] and not d["mdc"]:
                code = last_codes.get(col_idx)
                mdc = last_mdcs.get(col_idx)
                if code and mdc:
                    mappings.append({
                        "code": code,
                        "mdc": mdc,
                        "adrg": d["adrg"],
                    })

    return mappings


def detect_section_end(doc: fitz.Document, start: int) -> int:
    """시술코드 색인 시작 전까지의 페이지 찾기"""
    for i in range(start, min(start + 400, doc.page_count)):
        page = doc[i]
        text = page.get_text()
        if "시술코드 색인" in text and "Procedure Code Index" in text:
            return i
    return start + 300


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    print("Approach B: PyMuPDF span-level 좌표 기반 정밀 파싱")
    print("=" * 60)

    pdf_path = "downloads/P0/KDRG V4.7 분류집(부록).pdf"
    doc = fitz.open(pdf_path)
    print(f"PDF: {pdf_path} ({doc.page_count} pages)")

    # 진단코드 색인 영역 감지
    diag_end = detect_section_end(doc, DIAG_START)
    print(f"진단코드 색인: page {DIAG_START+1} ~ {diag_end}")

    # 전체 파싱
    all_mappings = []
    last_codes = {}  # 컬럼별 마지막 진단코드
    last_mdcs = {}   # 컬럼별 마지막 MDC

    for page_idx in range(DIAG_START, diag_end):
        mappings = parse_page(doc, page_idx, last_codes, last_mdcs)
        all_mappings.extend(mappings)

        if (page_idx - DIAG_START) % 50 == 0:
            print(f"  page {page_idx+1}... ({len(all_mappings)} mappings so far)")

    print(f"\n총 추출: {len(all_mappings)}건")

    # 중복 제거
    seen = set()
    unique = []
    for m in all_mappings:
        key = (m["code"], m["mdc"], m["adrg"])
        if key not in seen:
            seen.add(key)
            unique.append(m)

    print(f"중복 제거 후: {len(unique)}건")

    # 샘플 출력
    print("\n샘플 매핑 (처음 20건):")
    for m in unique[:20]:
        print(f"  {m['code']} → MDC {m['mdc']}, ADRG {m['adrg']}")

    # 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    md_path = OUTPUT_DIR / "code_index_b.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# KDRG V4.7 진단코드 색인 (Approach B)\n\n")
        f.write("| 진단코드 | MDC | ADRG |\n")
        f.write("|----------|-----|------|\n")
        for m in unique:
            f.write(f"| {m['code']} | {m['mdc']} | {m['adrg']} |\n")

    json_path = OUTPUT_DIR / "code_index_b.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

    print(f"\n저장: {md_path}")
    print(f"저장: {json_path}")

    doc.close()
    return len(unique)


if __name__ == "__main__":
    main()
