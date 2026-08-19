#!/usr/bin/env python3
"""테스트 fixture 를 국세법령정보시스템에서 다시 받아온다.

fixture 는 실제 응답을 그대로 저장한 것이라 8MB 가까이 된다. CI와 개발 환경에서
같은 회귀 테스트를 재현할 수 있도록 저장소에 함께 관리하며, 원본 응답의 변경을
반영할 때 이 스크립트로 갱신한다.

    python scripts/refresh_fixtures.py           # 없는 것만 받기
    python scripts/refresh_fixtures.py --force   # 전부 다시 받기

상세 fixture 는 **고정된 ntstDcmId** 로 받는다. 공개된 확정 문서라 내용이 변하지
않으므로 언제 다시 받아도 같은 문서가 온다. 검색 fixture 는 최신 N 건이라 내용이
달라지는데, 테스트가 건수 대신 **구조**만 검증하므로 문제되지 않는다.
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import pathlib
import sys

from korean_taxlaw_mcp.action_client import call_action, close_client
from korean_taxlaw_mcp.codes import collection_for
from korean_taxlaw_mcp.olta_client import SOURCES as OLTA_SOURCES
from korean_taxlaw_mcp.olta_client import close_client as close_olta_client
from korean_taxlaw_mcp.olta_client import detail_html, search_html
from korean_taxlaw_mcp.olta_parse import parse_rows

FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "tests" / "fixtures"

#: 문서구분별 검색 응답 — 구조 검증용. 최신 2건이면 충분하다.
SEARCH_CASES: list[tuple[str, str]] = [
    ("search_advance", "01"),
    ("search_written", "02"),
    ("search_advisory", "03"),
    ("search_notice_written", "04"),
    ("search_pre_assessment", "05"),
    ("search_objection", "06"),
    ("search_review", "07"),
    ("search_tribunal", "08"),
    ("search_court", "09"),
    ("search_constitutional", "10"),
]

#: 문서번호 검색 — exact 와 부분일치의 차이를 고정한다.
QUERY_CASES: list[tuple[str, str, str, int]] = [
    ("search_docnumber_exact", "02", "서면-2026-법규재산-0119", 5),
    ("search_docnumber_partial", "02", "법규재산-0119", 10),
]

#: 상세 응답 — 문서구분별로 본문 절 구조가 다르므로 종류마다 하나씩.
#: ntstDcmId 를 고정해 언제 받아도 같은 문서가 오게 한다.
DETAIL_CASES: list[tuple[str, str, str]] = [
    ("detail_written", "200000000000022584", "서면-2026-법규재산-0119"),
    ("detail_pre_assessment", "200000000000021979", "적부-국세청-2026-0119"),
    ("detail_tribunal", "200000000000022509", "조심-2025-인-4460"),
    ("detail_court", "200000000000022653", "대법원-2024-두-55396"),
    ("detail_review", "200000000000022276", "심사-부가-2026-0018"),
    ("detail_objection", "200000000000021832", "이의-광주청-2026-0024"),
]

#: 행정 해석기준·서식·코드표
ACTION_CASES: list[tuple[str, str, dict]] = [
    ("guidance_basic_ruling_laws", "ASISTD001MR01", {}),
    ("guidance_basic_ruling_years", "ASISTD001MR03", {"ntstBscId": "100000000000001561"}),
    ("guidance_basic_ruling_items", "ASISTD001MR02", {"ntstBscId": "100000000000001561", "rgtYr": "2024"}),
    ("guidance_exec_years", "ASISTE001MR03",
     {"ntstBscId": "100000000000001561", "ntstPlcnBkId": "511100000000000008"}),
    ("guidance_exec_items", "ASISTE001MR02", {"ntstBscId": "100000000000001561", "rgtYr": "2024"}),
    ("guidance_notice", "ASISTF001MR01",
     {"ntarClCd": "01", "ntstSjtClCd": "All", "searchKeyword": "", "pageIndex": 1, "recordCountPerPage": 5}),
    ("guidance_directive", "ASISTF001MR01",
     {"ntarClCd": "03", "ntstSjtClCd": "All", "searchKeyword": "", "pageIndex": 1, "recordCountPerPage": 5}),
    ("forms_search", "ASIAFB001MR01",
     {"searchNtstBscId": "stttAll", "searchFrmlNm": "상속세", "pageIndex": 1, "recordCountPerPage": 5}),
    ("codes", "ACMCMA001MR01",
     {"cmCodeDVOList": [{"cmnClsfCd": c} for c in ("19378", "19387", "19425", "19375", "15917", "19377")]}),
]


def _search_param(doc_class: str, query: str | None, limit: int) -> dict:
    return {
        "startCount": 1, "viewCount": limit, "schDtBase": "DCM_RGT_DTM",
        "bltnStrtDt": "", "bltnEndDt": "", "collectionName": collection_for(doc_class),
        "dcmClCdCtl": [f"001_{doc_class}"],
        "icldVcbCtl": [query] if query else [], "exclVcbCtl": [], "ntstTlawClCdList": [],
        "sortField": "DCM_RGT_DTM/DESC",
    }


def _write_html(name: str, html: str) -> int:
    """지방세 사이트 fixture. HTML 이 원본이라 그대로 gzip 으로 저장한다."""
    path = FIXTURES / f"{name}.html.gz"
    path.write_bytes(gzip.compress(html.encode("utf-8"), compresslevel=9, mtime=0))
    return path.stat().st_size


def _write(name: str, payload: object) -> int:
    path = FIXTURES / f"{name}.json.gz"
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    path.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))
    return path.stat().st_size


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="이미 있는 fixture 도 다시 받는다")
    args = parser.parse_args()

    FIXTURES.mkdir(parents=True, exist_ok=True)
    total = skipped = failed = 0

    def wanted(name: str) -> bool:
        nonlocal skipped
        if not args.force and (FIXTURES / f"{name}.json.gz").exists():
            skipped += 1
            return False
        return True

    async def fetch(name: str, action_id: str, param: dict, note: str = "") -> None:
        nonlocal total, failed
        if not wanted(name):
            return
        try:
            payload = await call_action(action_id, param)
        except Exception as exc:  # noqa: BLE001 — 어느 fixture 가 실패했는지 알려주고 계속
            print(f"  ✗ {name:30s} {type(exc).__name__}: {exc}")
            failed += 1
            return
        size = _write(name, payload)
        total += 1
        print(f"  ✓ {name:30s} {size:>9,}B  {note}")

    print(f"fixture 경로: {FIXTURES}")
    print("\n── 검색 응답 (문서구분별) ──")
    for name, doc_class in SEARCH_CASES:
        await fetch(name, "ASIPDI002PR01", _search_param(doc_class, None, 2), f"001_{doc_class}")

    print("\n── 문서번호 검색 ──")
    for name, doc_class, query, limit in QUERY_CASES:
        await fetch(name, "ASIPDI002PR01", _search_param(doc_class, query, limit), query)

    print("\n── 상세 응답 (본문 포함) ──")
    for name, doc_id, expected in DETAIL_CASES:
        if not wanted(name):
            continue
        try:
            payload = await call_action("ASIQTB002PR01", {"dcmDVO": {"ntstDcmId": doc_id}})
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ {name:30s} {type(exc).__name__}: {exc}")
            failed += 1
            continue
        actual = ((payload or {}).get("dcmDVO") or {}).get("ntstDcmDscmCntn")
        if actual != expected:
            # 원본에서 문서가 사라지거나 ID 가 바뀌면 테스트 기대값이 무의미해진다
            print(f"  ✗ {name:30s} 문서번호 불일치: 기대={expected} 실제={actual}")
            failed += 1
            continue
        size = _write(name, payload)
        total += 1
        print(f"  ✓ {name:30s} {size:>9,}B  {expected}")

    print("\n── 행정 해석기준 · 서식 · 코드표 ──")
    for name, action_id, param in ACTION_CASES:
        await fetch(name, action_id, param)

    await close_client()

    # ── 지방세 (한국지방세연구원 지방세 법령정보시스템) ────────────────────────
    print("\n── 지방세: 자료 종류별 검색 ──")
    picked: dict[str, dict[str, str]] = {}
    for kind in OLTA_SOURCES:
        name = f"olta_search_{kind}"
        if wanted(name):
            try:
                html = await search_html(kind, query="취득세")
            except Exception as exc:  # noqa: BLE001
                print(f"  ✗ {name:30s} {type(exc).__name__}: {exc}")
                failed += 1
                continue
            size = _write_html(name, html)
            total += 1
            print(f"  ✓ {name:30s} {size:>9,}B  {OLTA_SOURCES[kind].label}")
        else:
            html = None
        # 상세 fixture 용 대표 문서를 고른다
        try:
            rows = parse_rows(html if html is not None else await search_html(kind, query="취득세"))
            if rows:
                picked[kind] = rows[0]
        except Exception:  # noqa: BLE001
            pass

    print("\n── 지방세: 상세 (본문 포함) ──")
    for kind, row in picked.items():
        name = f"olta_detail_{kind}"
        if not wanted(name):
            continue
        try:
            html = await detail_html(
                kind, row["num"], relationship_num=row.get("relationshipNum")
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ {name:30s} {type(exc).__name__}: {exc}")
            failed += 1
            continue
        size = _write_html(name, html)
        total += 1
        print(f"  ✓ {name:30s} {size:>9,}B  {row.get('documentNumber', '?')}")

    print("\n── 지방세: 문서번호 검색 (exact / 부분일치) ──")
    for name, query, doc_mode in [
        ("olta_docnumber_exact", "1794", True),
        ("olta_docnumber_partial", "924", True),
    ]:
        if not wanted(name):
            continue
        try:
            html = await search_html("interpretation", query=query, doc_number_mode=doc_mode)
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ {name:30s} {type(exc).__name__}: {exc}")
            failed += 1
            continue
        size = _write_html(name, html)
        total += 1
        print(f"  ✓ {name:30s} {size:>9,}B  query={query}")

    await close_olta_client()
    print(f"\n받음 {total} / 건너뜀 {skipped} / 실패 {failed}")
    if failed:
        print("실패한 fixture 가 있습니다. 국세법령정보시스템 상태를 확인하고 다시 시도하세요.")
        return 1
    if total:
        print("이제 `pytest` 를 돌릴 수 있습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
