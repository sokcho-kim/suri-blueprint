"""
Approach A: opendataloader-pdf JSON → bounding box 기반 다단 컬럼 후처리

코드 색인 페이지의 다단 레이아웃을 bounding box X좌표로 분리하여
구조화된 코드 매핑 테이블로 변환.
"""

import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
INPUT_JSON = DATA_DIR / "parsed" / "test" / "KDRG V4.7 분류집(부록).json"
OUTPUT_DIR = DATA_DIR / "eval" / "approach_a"


def load_json():
    with open(INPUT_JSON, encoding="utf-8") as f:
        return json.load(f)


def extract_code_index_elements(data: dict, start_page: int = 11, end_page: int = 300):
    """코드 색인 페이지에서 텍스트 + bounding box 추출"""
    elements = []
    for kid in data["kids"]:
        pn = kid.get("page number", 0)
        if start_page <= pn <= end_page:
            content = kid.get("content", "").strip()
            bb = kid.get("bounding box", [])
            t = kid.get("type", "")

            if content and t not in ("header", "footer", "image"):
                elements.append({
                    "page": pn,
                    "type": t,
                    "content": content,
                    "x": bb[0] if len(bb) >= 4 else 0,
                    "y": bb[1] if len(bb) >= 4 else 0,
                    "x2": bb[2] if len(bb) >= 4 else 0,
                    "y2": bb[3] if len(bb) >= 4 else 0,
                })

            # Also check kids of this element
            for child in kid.get("kids", []):
                child_content = child.get("content", "").strip()
                child_bb = child.get("bounding box", [])
                child_type = child.get("type", "")
                if child_content and child_type not in ("header", "footer", "image"):
                    elements.append({
                        "page": pn,
                        "type": child_type,
                        "content": child_content,
                        "x": child_bb[0] if len(child_bb) >= 4 else 0,
                        "y": child_bb[1] if len(child_bb) >= 4 else 0,
                        "x2": child_bb[2] if len(child_bb) >= 4 else 0,
                        "y2": child_bb[3] if len(child_bb) >= 4 else 0,
                    })

    return elements


def parse_code_line(text: str) -> list[dict]:
    """코드 라인에서 (진단코드, MDC, ADRG) 매핑 추출

    패턴: 'A000 06 G671' → code=A000, mdc=06, adrg=G671
    """
    import re
    # 코드 패턴: 알파벳+숫자(진단코드), 숫자 또는 숫자-숫자(MDC), 알파벳+숫자(ADRG)
    tokens = text.split()
    results = []

    i = 0
    current_code = None
    current_mdc = None

    while i < len(tokens):
        token = tokens[i]

        # 진단코드 패턴: A000, C460, S4641 등
        if re.match(r'^[A-Z]\w{2,5}$', token) and not re.match(r'^[A-Z]\d{3}$', token) is None or \
           re.match(r'^[A-Z]\d{2,4}[A-Z]?$', token):
            # Could be a diagnosis code or ADRG
            # ADRG: single letter + 3 digits (G671, J611, P641, etc.)
            if re.match(r'^[A-Z]\d{3}$', token) and current_mdc is not None:
                # This is an ADRG
                results.append({
                    "code": current_code,
                    "mdc": current_mdc,
                    "adrg": token,
                })
            else:
                # This is a new diagnosis code
                current_code = token
                current_mdc = None

        # MDC 패턴: 01-21, 18-1, 18-2, 21-1 등
        elif re.match(r'^\d{1,2}(-\d)?$', token):
            current_mdc = token

        i += 1

    return results


def process_elements(elements: list[dict]) -> list[dict]:
    """전체 엘리먼트를 파싱하여 코드 매핑 추출"""
    all_mappings = []

    for el in elements:
        content = el["content"]
        # 헤딩이나 설명문 스킵
        if any(kw in content for kw in ["색인", "Index", "안내", "예시", "KDRG", "코드체계"]):
            continue

        mappings = parse_code_line(content)
        for m in mappings:
            if m["code"] and m["mdc"] and m["adrg"]:
                m["page"] = el["page"]
                m["source_text"] = content[:100]
                all_mappings.append(m)

    return all_mappings


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    print("Approach A: opendataloader JSON bounding box 후처리")
    print("=" * 60)

    data = load_json()
    elements = extract_code_index_elements(data)
    print(f"코드 색인 영역 엘리먼트: {len(elements)}개")

    # Show sample elements
    print("\n샘플 엘리먼트 (page 11-13):")
    for el in elements[:20]:
        if el["page"] <= 13:
            print(f"  p{el['page']} [{el['type']}] x={el['x']:.0f} | {el['content'][:80]}")

    # Parse code mappings
    mappings = process_elements(elements)
    print(f"\n추출된 코드 매핑: {len(mappings)}건")

    # Show samples
    print("\n샘플 매핑:")
    for m in mappings[:20]:
        print(f"  {m['code']} → MDC {m['mdc']}, ADRG {m['adrg']}")

    # Save results
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Save as markdown table
    md_path = OUTPUT_DIR / "code_index_a.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# KDRG V4.7 진단코드 색인 (Approach A)\n\n")
        f.write("| 진단코드 | MDC | ADRG |\n")
        f.write("|----------|-----|------|\n")
        for m in mappings:
            f.write(f"| {m['code']} | {m['mdc']} | {m['adrg']} |\n")

    # Save as JSON
    json_path = OUTPUT_DIR / "code_index_a.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(mappings, f, ensure_ascii=False, indent=2)

    print(f"\n저장: {md_path}")
    print(f"저장: {json_path}")

    return len(mappings)


if __name__ == "__main__":
    main()
