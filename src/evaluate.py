"""
Approach A vs B 파싱 품질 비교 평가

수동 검증 기준 (PDF 원본 page 12에서 육안 확인한 매핑):
A043 → MDC 15, ADRG P671
A043 → MDC 18-1, ADRG S630
A048 → MDC 15, ADRG P671
A048 → MDC 18-1, ADRG S630
A064 → MDC 07, ADRG H680
A065 → MDC 04, ADRG E520
A065 → MDC 04, ADRG E630
A090 → MDC 15, ADRG P652
A090 → MDC 15, ADRG P661
A090 → MDC 15, ADRG P662
A090 → MDC 15, ADRG P671
A090 → MDC 15, ADRG P672
A090 → MDC 18-1, ADRG S630
"""

import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "eval"

# Ground truth (PDF page 12 육안 확인)
GROUND_TRUTH = [
    ("A043", "15", "P671"),
    ("A043", "18-1", "S630"),
    ("A048", "15", "P671"),
    ("A048", "18-1", "S630"),
    ("A064", "07", "H680"),
    ("A065", "04", "E520"),
    ("A065", "04", "E630"),
    ("A090", "15", "P652"),
    ("A090", "15", "P661"),
    ("A090", "15", "P662"),
    ("A090", "15", "P671"),
    ("A090", "15", "P672"),
    ("A090", "18-1", "S630"),
]


def load_approach(name: str) -> set[tuple]:
    path = DATA_DIR / name / f"code_index_{name[-1].lower()}.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {(m["code"], m["mdc"], m["adrg"]) for m in data}


def evaluate(name: str, mappings: set[tuple]):
    gt_set = set(GROUND_TRUTH)

    found = gt_set & mappings
    missed = gt_set - mappings

    # 해당 코드에 대한 잘못된 매핑 (false positives for these codes)
    gt_codes = {t[0] for t in GROUND_TRUTH}
    code_mappings = {m for m in mappings if m[0] in gt_codes}
    false_pos = code_mappings - gt_set

    precision = len(found) / len(code_mappings) if code_mappings else 0
    recall = len(found) / len(gt_set) if gt_set else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    print(f"\n{'='*50}")
    print(f"  {name}")
    print(f"{'='*50}")
    print(f"  총 매핑 수:     {len(mappings):,}")
    print(f"  GT 매핑:        {len(gt_set)}")
    print(f"  정답 (Hit):     {len(found)}/{len(gt_set)}")
    print(f"  누락 (Miss):    {len(missed)}")
    print(f"  오탐 (FP):      {len(false_pos)}")
    print(f"  Precision:      {precision:.3f}")
    print(f"  Recall:         {recall:.3f}")
    print(f"  F1:             {f1:.3f}")

    if missed:
        print(f"\n  누락 매핑:")
        for m in sorted(missed):
            print(f"    {m[0]} → MDC {m[1]}, ADRG {m[2]}")

    if false_pos:
        print(f"\n  오탐 매핑 (샘플):")
        for m in sorted(false_pos)[:10]:
            print(f"    {m[0]} → MDC {m[1]}, ADRG {m[2]}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("파싱 품질 비교 평가")
    print("Ground Truth: PDF page 12 육안 확인 13건")

    a = load_approach("approach_a")
    b = load_approach("approach_b")

    evaluate("Approach A (opendataloader JSON 후처리)", a)
    evaluate("Approach B (PyMuPDF span 좌표 파싱)", b)

    # 요약
    print("\n" + "=" * 50)
    print("  요약")
    print("=" * 50)

    gt_set = set(GROUND_TRUTH)
    a_hit = len(gt_set & a)
    b_hit = len(gt_set & b)

    print(f"  {'':20} {'Approach A':>12} {'Approach B':>12}")
    print(f"  {'총 매핑':20} {len(a):>12,} {len(b):>12,}")
    print(f"  {'GT Hit':20} {a_hit:>12}/{len(gt_set)} {b_hit:>12}/{len(gt_set)}")
    print(f"  {'방식':20} {'JSON bbox':>12} {'PyMuPDF':>12}")


if __name__ == "__main__":
    main()
