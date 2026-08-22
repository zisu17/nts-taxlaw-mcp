"""문서 모델과 출처·권위 표기.

법적 근거와 안내자료를 같은 무게로 읽으면 세무 상담에서 잘못된 결론이 나올 수 있다.
모든 반환 문서에 ``authorityLevel`` 을 붙여 법률 조문, 국세청 집행기준, 발간책자의
층위를 구분한다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class AuthorityLevel(StrEnum):
    STATUTE = "statute"
    ENFORCEMENT_DECREE = "enforcement_decree"
    ENFORCEMENT_RULE = "enforcement_rule"
    NTS_RULING = "nts_ruling"
    LOCAL_RULING = "local_ruling"
    NTS_GUIDANCE = "nts_guidance"
    ADJUDICATION = "adjudication"
    COURT_CASE = "court_case"


#: 모델이 층위를 구분할 수 있도록 응답에 싣는 한국어 설명.
AUTHORITY_LABEL: dict[AuthorityLevel, str] = {
    AuthorityLevel.STATUTE: "법률 (국회 제정 — 법적 구속력)",
    AuthorityLevel.ENFORCEMENT_DECREE: "시행령 (대통령령 — 법적 구속력)",
    AuthorityLevel.ENFORCEMENT_RULE: "시행규칙 (부령 — 법적 구속력)",
    AuthorityLevel.NTS_RULING: "국세청 해석례 (예규 — 과세관청의 법령해석, 법원을 구속하지 않음)",
    AuthorityLevel.LOCAL_RULING: (
        "지방세 유권해석 (행정안전부·법제처 — 지방세 과세관청의 법령해석, 법원을 구속하지 않음)"
    ),
    AuthorityLevel.NTS_GUIDANCE: "국세청 행정해석기준 (기본통칙·집행기준·고시·훈령 — 내부 집행기준, 법규 아님)",
    AuthorityLevel.ADJUDICATION: "불복 결정례 (과세적부·이의신청·심사청구·심판청구 — 해당 사건에 대한 결정)",
    AuthorityLevel.COURT_CASE: "법원 판례·헌재 결정 (사법적 판단)",
}

_RULING_CLASSES = {"01", "02", "03", "04", "21", "31", "32", "41"}
_ADJUDICATION_CLASSES = {"05", "06", "07", "08", "11", "14"}
_COURT_CLASSES = {"09", "10", "20"}


def authority_for_doc_class(doc_class: str) -> AuthorityLevel:
    """문서구분 코드 → 권위 층위."""
    if doc_class in _ADJUDICATION_CLASSES:
        return AuthorityLevel.ADJUDICATION
    if doc_class in _COURT_CLASSES:
        return AuthorityLevel.COURT_CASE
    return AuthorityLevel.NTS_RULING


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def make_citation(
    *, source_id: str, document_number: str, source_url: str, source_agency: str | None = None
) -> dict[str, Any]:
    """모든 반환 문서가 갖는 출처 블록.

    본문 일부만 실어도 원문을 되짚을 수 있어야 한다. 응답에 그대로 실리므로
    키는 camelCase 로 둔다.
    """
    return {
        "sourceAgency": source_agency or "국세청",
        "sourceSystem": "국세법령정보시스템",
        "sourceId": source_id,
        "documentNumber": document_number,
        "sourceUrl": source_url,
        "retrievedAt": now_iso(),
    }
