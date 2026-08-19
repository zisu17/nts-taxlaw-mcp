"""검색 질의 조립.

사이트 검색 문법을 실제 요청으로 확정했다(세법해석 01~04 전체, 반환 건수 기준)::

    ["상속"]                  → 22,349      ["증여"] → 22,924   ["공동상속주택"] → 2,828
    ["상속","증여"]            → 14,913   ← 배열 원소끼리 AND(교집합)
    ["상속 증여"]              → 14,913   ← 원소 내부 공백도 AND
    ["상속|증여"]              → 30,360   ← ASCII 파이프가 OR (22,349+22,924-14,913 = 30,360 정확히 일치)
    ["상속"] + excl ["증여"]   →  7,436   ← exclVcbCtl 이 NOT (22,349-14,913 = 7,436 정확히 일치)

주의할 함정이 둘 있다.

* OR 는 **ASCII 파이프 ``|``** 다. 흔히 문서에 적히는 broken bar ``¦``(U+00A6)는
  OR 로 동작하지 않고 AND 와 같은 결과를 준다(``["상속¦증여"]`` → 14,913).
* ``OR`` 라는 낱말을 쓰면 0건이 온다(``["상속 OR 증여"]`` → 0).

MCP 는 사용자에게 ``match: "all"|"any"`` 와 ``exclude: []`` 형태를 주고 여기서 변환한다.
"""

from __future__ import annotations

import re

#: OR 연산자. ASCII 파이프다 — broken bar(¦, U+00A6)는 AND 로 동작하므로 쓰면 안 된다.
OR_SEPARATOR = "|"

#: 정렬 기준. 사이트가 받는 값은 ``<필드>/<방향>`` 형태다.
#:
#: **주의**: 허용되지 않는 필드명을 주면 사이트는 오류가 아니라 **0건**을 돌려준다
#: (실측: ``RANK/DESC`` → total 0, status SUCCESS). 조용한 0건은 "자료 없음"으로
#: 오해되기 딱 좋으므로 실측 검증된 토큰만 내보낸다.
#: 검증된 필드: ``DCM_RGT_DTM``(등록일), ``FRS_RGT_DTM``(최초등록일), ``SCORE``(적합도).
SORT: dict[str, str] = {
    "latest": "DCM_RGT_DTM/DESC",
    "oldest": "DCM_RGT_DTM/ASC",
    "relevance": "SCORE/DESC",
}

_TOKEN_RE = re.compile(r'"([^"]+)"|\'([^\']+)\'|(\S+)')


def tokenize_query(query: str) -> list[str]:
    """질의 문자열을 낱말로 쪼갠다. 따옴표로 묶은 구절은 하나로 유지한다."""
    out: list[str] = []
    for m in _TOKEN_RE.finditer(query):
        term = (m.group(1) or m.group(2) or m.group(3) or "").strip()
        if term:
            out.append(term)
    return out


def build_vocab(
    query: str | None, match: str | None = None, exclude: list[str] | None = None
) -> tuple[list[str], list[str]]:
    """사용자 질의 → (icldVcbCtl, exclVcbCtl).

    ``match="any"`` 는 한 원소 안에서 ``|`` 로 이어 붙인다 — 배열 원소를 늘리면
    AND 가 되어 의미가 정반대로 뒤집힌다.
    """
    terms = tokenize_query(query) if query else []
    excluded = [x.strip() for x in (exclude or []) if x and x.strip()]

    if not terms:
        return [], excluded
    if match == "any" and len(terms) > 1:
        return [OR_SEPARATOR.join(terms)], excluded
    return terms, excluded


def to_site_date(value: str | None) -> str:
    """YYYY-MM-DD / YYYYMMDD → 사이트가 받는 YYYYMMDD. 빈 값은 빈 문자열."""
    if not value:
        return ""
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 8:
        return digits
    if len(digits) == 6:
        return digits + "01"
    if len(digits) == 4:
        return digits + "0101"
    return ""


def format_date(value: object) -> str | None:
    """YYYYMMDD(000000) → YYYY-MM-DD."""
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) < 8:
        return None
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
