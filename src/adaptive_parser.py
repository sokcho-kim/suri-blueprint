"""
적응형 다단 컬럼 PDF 파서

매 페이지의 헤더 행(진단코드/시술코드 MDC ADRG)을 자동 감지하여
컬럼 경계를 동적으로 계산. 모든 분류집 PDF에 범용 적용.
"""

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import fitz

DATA_DIR = Path(__file__).parent.parent / "data"


@dataclass
class ColumnDef:
    """하나의 컬럼 정의 (코드/MDC/ADRG X 경계)"""
    code_x: float   # 코드 시작 X
    mdc_x: float    # MDC 시작 X
    adrg_x: float   # ADRG 시작 X
    next_x: float   # 다음 컬럼 시작 or 페이지 끝


@dataclass
class PageLayout:
    """한 페이지의 레이아웃 정보"""
    columns: list[ColumnDef]
    header_y: float  # 헤더 행의 Y좌표
    data_y_start: float  # 데이터 시작 Y좌표


@dataclass
class CodeMapping:
    """하나의 코드 매핑"""
    code: str
    mdc: str
    adrg: str
    page: int = 0


def extract_spans(page: fitz.Page) -> list[dict]:
    """페이지의 모든 텍스트 span 추출"""
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
    return spans


def detect_layout(spans: list[dict], page_width: float) -> PageLayout | None:
    """헤더 행에서 컬럼 레이아웃 자동 감지

    '진단코드/시술코드', 'MDC', 'ADRG' 가 같은 Y좌표에 반복되는 패턴을 찾음.
    """
    # 같은 Y에 있는 헤더 키워드 그룹핑
    header_candidates: dict[float, list[dict]] = {}
    for s in spans:
        if s["text"] in ("진단코드", "시술코드", "MDC", "ADRG"):
            y_key = round(s["y"] / 3) * 3  # 3pt 단위 그룹핑
            header_candidates.setdefault(y_key, []).append(s)

    # 최소 3개 이상의 헤더 키워드가 있는 행 찾기 (1컬럼이면 3개, 4컬럼이면 12개)
    best_y = None
    best_headers = []
    for y_key, headers in header_candidates.items():
        # MDC와 ADRG가 각각 있어야 유효
        has_mdc = any(h["text"] == "MDC" for h in headers)
        has_adrg = any(h["text"] == "ADRG" for h in headers)
        has_code = any(h["text"] in ("진단코드", "시술코드") for h in headers)
        if has_mdc and has_adrg and has_code and len(headers) >= 3:
            if best_headers is None or len(headers) > len(best_headers):
                best_y = y_key
                best_headers = headers

    if not best_headers:
        return None

    # MDC 위치로 컬럼 그룹 구분
    mdc_positions = sorted([h["x"] for h in best_headers if h["text"] == "MDC"])
    adrg_positions = sorted([h["x"] for h in best_headers if h["text"] == "ADRG"])
    code_positions = sorted([h["x"] for h in best_headers if h["text"] in ("진단코드", "시술코드")])

    if len(mdc_positions) != len(adrg_positions):
        return None

    n_cols = len(mdc_positions)
    columns = []

    for i in range(n_cols):
        code_x = code_positions[i] if i < len(code_positions) else mdc_positions[i] - 40
        mdc_x = mdc_positions[i]
        adrg_x = adrg_positions[i]
        next_x = code_positions[i + 1] if i + 1 < len(code_positions) else page_width

        columns.append(ColumnDef(
            code_x=code_x,
            mdc_x=mdc_x,
            adrg_x=adrg_x,
            next_x=next_x,
        ))

    header_y = best_headers[0]["y"]

    return PageLayout(
        columns=columns,
        header_y=header_y,
        data_y_start=header_y + 10,
    )


def classify_span_adaptive(span: dict, layout: PageLayout) -> tuple[int, str] | None:
    """동적 레이아웃 기반으로 span을 (컬럼, 필드)로 분류"""
    x = span["x"]
    tolerance = 5.0  # X좌표 허용 오차

    for col_idx, col in enumerate(layout.columns):
        col_end = col.next_x

        # 코드 영역: code_x ~ mdc_x
        if col.code_x - tolerance <= x < col.mdc_x - tolerance:
            return (col_idx, "code")
        # MDC 영역: mdc_x ~ adrg_x
        if col.mdc_x - tolerance <= x < col.adrg_x - tolerance:
            return (col_idx, "mdc")
        # ADRG 영역: adrg_x ~ next column
        if col.adrg_x - tolerance <= x < col_end - tolerance:
            return (col_idx, "adrg")

    return None


def group_by_y(spans: list[dict], tolerance: float = 3.0) -> list[list[dict]]:
    """Y좌표 기준으로 행 그룹핑"""
    if not spans:
        return []

    sorted_spans = sorted(spans, key=lambda s: (s["y"], s["x"]))
    rows = []
    current_row = [sorted_spans[0]]
    current_y = sorted_spans[0]["y"]

    for s in sorted_spans[1:]:
        if abs(s["y"] - current_y) <= tolerance:
            current_row.append(s)
        else:
            rows.append(sorted(current_row, key=lambda s: s["x"]))
            current_row = [s]
            current_y = s["y"]

    if current_row:
        rows.append(sorted(current_row, key=lambda s: s["x"]))

    return rows


def is_data_span(span: dict, layout: PageLayout) -> bool:
    """데이터 영역의 span인지 확인 (헤더/페이지 번호 제외)"""
    if span["y"] <= layout.data_y_start:
        return False
    text = span["text"]
    # 페이지 헤더/푸터 패턴 제외
    if re.match(r'^\d+\s+(KDRG|KOPG|KRPG|Diagnosis|Procedure)', text):
        return False
    if text in ("진단코드", "시술코드", "MDC", "ADRG", "색인"):
        return False
    if re.match(r'^(Diagnosis|Procedure) Code Index\s+\d+$', text):
        return False
    return True


def parse_page_adaptive(
    page: fitz.Page,
    page_idx: int,
    last_codes: dict,
    last_mdcs: dict,
    prev_layout: PageLayout | None,
) -> tuple[list[CodeMapping], PageLayout | None]:
    """적응형 페이지 파싱"""
    spans = extract_spans(page)
    layout = detect_layout(spans, page.rect.width)

    if layout is None:
        layout = prev_layout
    if layout is None:
        return [], None

    # 데이터 span만 필터
    data_spans = [s for s in spans if is_data_span(s, layout)]
    rows = group_by_y(data_spans)
    mappings = []

    for row in rows:
        row_data = {i: {"code": None, "mdc": None, "adrg": None} for i in range(len(layout.columns))}

        for span in row:
            result = classify_span_adaptive(span, layout)
            if result is None:
                continue
            col_idx, field_name = result
            if col_idx < len(layout.columns):
                row_data[col_idx][field_name] = span["text"]

        for col_idx in range(len(layout.columns)):
            d = row_data[col_idx]

            if d["code"]:
                last_codes[col_idx] = d["code"]

            if d["mdc"]:
                last_mdcs[col_idx] = d["mdc"]

            if d["mdc"] and d["adrg"]:
                code = last_codes.get(col_idx)
                if code:
                    mappings.append(CodeMapping(
                        code=code, mdc=d["mdc"], adrg=d["adrg"], page=page_idx + 1
                    ))
            elif d["adrg"] and not d["mdc"]:
                code = last_codes.get(col_idx)
                mdc = last_mdcs.get(col_idx)
                if code and mdc:
                    mappings.append(CodeMapping(
                        code=code, mdc=mdc, adrg=d["adrg"], page=page_idx + 1
                    ))

    return mappings, layout


def detect_index_sections(doc: fitz.Document) -> list[tuple[str, int, int]]:
    """문서에서 색인 섹션(진단코드/시술코드) 자동 감지"""
    sections = []
    current_section = None
    current_start = None

    for i in range(doc.page_count):
        page = doc[i]
        text = page.get_text()

        if "진단코드 색인" in text and "Diagnosis Code Index" in text:
            if current_section:
                sections.append((current_section, current_start, i))
            current_section = "diagnosis"
            current_start = i
        elif "시술코드 색인" in text and "Procedure Code Index" in text:
            if current_section:
                sections.append((current_section, current_start, i))
            current_section = "procedure"
            current_start = i
        elif "외과적 우선순위" in text or "중증도 분류" in text:
            if current_section:
                sections.append((current_section, current_start, i))
                current_section = None

    if current_section:
        sections.append((current_section, current_start, doc.page_count))

    return sections


def parse_pdf(pdf_path: str | Path) -> list[CodeMapping]:
    """PDF 파일 전체 파싱"""
    doc = fitz.open(str(pdf_path))
    print(f"  PDF: {Path(pdf_path).name} ({doc.page_count} pages)")

    sections = detect_index_sections(doc)
    if not sections:
        # 섹션 감지 실패 시 전체 문서 파싱 시도
        print("  섹션 자동 감지 실패 — 전체 문서 스캔")
        sections = [("all", 0, doc.page_count)]

    all_mappings = []

    for section_name, start, end in sections:
        print(f"  섹션: {section_name} (page {start+1}~{end})")

        last_codes = {}
        last_mdcs = {}
        layout = None

        for page_idx in range(start, end):
            page = doc[page_idx]
            mappings, layout = parse_page_adaptive(page, page_idx, last_codes, last_mdcs, layout)

            for m in mappings:
                all_mappings.append(m)

            if (page_idx - start) % 100 == 0 and page_idx > start:
                print(f"    page {page_idx+1}... ({len(all_mappings)} total)")

        # 새 섹션 시작 시 컬럼 상태 리셋
        last_codes.clear()
        last_mdcs.clear()

    doc.close()
    return all_mappings


def deduplicate(mappings: list[CodeMapping]) -> list[CodeMapping]:
    """중복 제거"""
    seen = set()
    unique = []
    for m in mappings:
        key = (m.code, m.mdc, m.adrg)
        if key not in seen:
            seen.add(key)
            unique.append(m)
    return unique


def save_results(mappings: list[CodeMapping], output_dir: Path, name: str):
    """결과 저장 (Markdown + JSON)"""
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = output_dir / f"{name}.json"
    data = [{"code": m.code, "mdc": m.mdc, "adrg": m.adrg, "page": m.page} for m in mappings]
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Markdown
    md_path = output_dir / f"{name}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# {name} 코드 색인\n\n")
        f.write(f"총 {len(mappings)}건\n\n")
        f.write("| 코드 | MDC | ADRG |\n")
        f.write("|------|-----|------|\n")
        for m in mappings:
            f.write(f"| {m.code} | {m.mdc} | {m.adrg} |\n")

    print(f"  저장: {json_path}")
    print(f"  저장: {md_path}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    print("적응형 다단 컬럼 PDF 파서")
    print("=" * 60)

    downloads = Path(__file__).parent.parent / "downloads" / "P0"
    output_dir = DATA_DIR / "parsed" / "adaptive"

    pdf_files = sorted(downloads.glob("*.pdf"))
    print(f"대상 PDF: {len(pdf_files)}개\n")

    total = 0
    for pdf_path in pdf_files:
        print(f"\n{'─' * 50}")
        mappings = parse_pdf(pdf_path)
        unique = deduplicate(mappings)
        print(f"  추출: {len(mappings)} → 중복 제거: {len(unique)}")

        name = pdf_path.stem
        save_results(unique, output_dir, name)
        total += len(unique)

    print(f"\n{'=' * 60}")
    print(f"전체 완료: {total}건")


if __name__ == "__main__":
    main()
