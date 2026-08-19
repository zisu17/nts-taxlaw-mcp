#!/usr/bin/env python3
"""코드표를 원본과 대조한다.

``codes.py`` 는 공통코드를 상수로 고정하고 있다(런타임에 매번 조회하면 모든 검색이
왕복을 하나 더 태운다). 대신 원본이 바뀌었을 때 알아챌 수단이 필요하다.

    python scripts/refresh_codes.py            # 차이만 보고
    python scripts/refresh_codes.py --json     # 원본 전체를 JSON 으로 출력
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from nts_taxlaw_mcp.action_client import call_action, close_client
from nts_taxlaw_mcp.codes import (
    CASE_KIND,
    DECISION_RESULT,
    DISCLOSURE,
    DOC_CLASS,
    ISSUING_AGENCY,
    TAX_TYPE,
)

GROUPS: dict[str, tuple[str, dict[str, str]]] = {
    "19378": ("문서구분 (DOC_CLASS)", DOC_CLASS),
    "19387": ("세목 (TAX_TYPE)", TAX_TYPE),
    "19425": ("생산기관 (ISSUING_AGENCY)", ISSUING_AGENCY),
    "19375": ("결정유형 (DECISION_RESULT)", DECISION_RESULT),
    "15917": ("공개구분 (DISCLOSURE)", DISCLOSURE),
    "19377": ("사건분류 (CASE_KIND)", CASE_KIND),
}


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="원본 코드표 전체를 JSON 으로 출력")
    args = parser.parse_args()

    raw = await call_action(
        "ACMCMA001MR01", {"cmCodeDVOList": [{"cmnClsfCd": g} for g in GROUPS]}
    )
    upstream = {
        g["cmnClsfCd"]: {c["cdVval"]: c["cdVvalKrnNm"] for c in g["cmCodeDVOList"]}
        for g in raw
        if g and g.get("cmCodeDVOList")
    }
    await close_client()

    if args.json:
        print(json.dumps(upstream, ensure_ascii=False, indent=1))
        return 0

    total_drift = 0
    for group_id, (label, constant) in GROUPS.items():
        live = upstream.get(group_id, {})
        drift = 0
        print(f"\n=== {group_id}  {label} ===")
        for code, name in constant.items():
            actual = live.get(code)
            if actual is None:
                print(f"  [사라짐]   {code}: 상수={name}")
                drift += 1
            elif actual != name:
                print(f"  [바뀜]     {code}: 상수={name}  원본={actual}")
                drift += 1
        for code, name in live.items():
            if code in constant:
                continue
            # ZZ 는 "해당없음" 자리표시자다(is_blank_code 가 빈 값으로 취급).
            # 세목은 3xx 대역만 문서 검색에 쓰므로 다른 대역은 보고하지 않는다.
            if code == "ZZ":
                continue
            if group_id == "19387" and not code.startswith("3"):
                continue
            print(f"  [새로생김] {code}: {name}")
            drift += 1
        if not drift:
            print("  차이 없음")
        total_drift += drift

    print(f"\n총 차이 {total_drift}건")
    if total_drift:
        print("codes.py 를 갱신하고 tests/test_parsers.py::test_code_tables_match_constants 를 다시 돌리세요.")
    return 1 if total_drift else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
