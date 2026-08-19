"""자연어 라우팅 — 요구 사양의 표현이 모두 국세청 검색으로 흘러야 한다."""

from __future__ import annotations

import pytest

from nts_taxlaw_mcp.routing import route_query

#: 요구 사양에 열거된 표현
REQUIRED_PHRASES = [
    "국세청", "국세", "예규", "서면", "서면질의", "질의회신", "사전답변",
    "과세기준자문", "기준자문", "국세청 해석", "세법해석", "기본통칙",
    "세법집행기준", "적부", "과세적부", "이의신청", "심사청구",
]


@pytest.mark.parametrize("phrase", REQUIRED_PHRASES)
def test_required_phrases_route_to_nts(phrase: str) -> None:
    assert route_query(f"{phrase} 관련 자료 찾아줘").is_nts_query is True


#: 문서번호 접두만으로도 라우팅돼야 한다
@pytest.mark.parametrize(
    "prefix,expected_domain",
    [("서면-2026-법규재산-0119", "interpretation"),
     ("사전-2026-법규소득-0543", "interpretation"),
     ("적부-국세청-2026-0119", "decision"),
     ("심사-부가-2026-0018", "decision"),
     ("조심-2025-인-4460", "decision")],
)
def test_document_number_prefix_routes(prefix: str, expected_domain: str) -> None:
    hint = route_query(prefix)
    assert hint.is_nts_query is True
    assert expected_domain in hint.domains
    assert hint.document_number == prefix


@pytest.mark.parametrize(
    "query,domain",
    [("사전답변 찾아줘", "interpretation"), ("질의회신 사례", "interpretation"),
     ("과세기준자문 사례", "interpretation"), ("과세적부 결정", "decision"),
     ("이의신청 사례", "decision"), ("심사청구 결정례", "decision"),
     ("심판청구 조세심판", "decision"), ("대법원 판례", "decision"),
     ("헌재 결정", "decision"), ("기본통칙 내용", "guidance"),
     ("세법집행기준", "guidance"), ("훈령 확인", "guidance"),
     ("법령서식 별표", "form")],
)
def test_phrase_maps_to_domain(query: str, domain: str) -> None:
    assert domain in route_query(query).domains


def test_routing_words_are_stripped_from_search_query() -> None:
    """사이트는 공백 구분 낱말을 AND 로 묶는다 — '국세청'·'예규' 가 남으면 결과가 말라붙는다."""
    hint = route_query("국세청 예규 공동상속주택 양도소득세")
    assert hint.content_query == "공동상속주택 양도소득세"


def test_document_number_stripped_before_marker_words() -> None:
    """순서를 뒤집으면 '적부-국세청-2026-0119' 가 '- -2026-0119' 잔해로 남는다."""
    assert route_query("적부-국세청-2026-0119").content_query == ""
    assert route_query("조심-2025-인-4460 판단 근거").content_query == "판단 근거"


def test_tax_type_is_inferred_but_reported_as_hint_only() -> None:
    """추정 세목을 필터로 강제하면 분류가 다른 관련 문서가 누락된다."""
    hint = route_query("공동상속주택 양도소득세")
    assert "307" in hint.tax_type_codes
    assert hint.reasons  # 근거가 남아야 감사 가능하다


def test_non_tax_query_is_not_routed() -> None:
    assert route_query("오늘 날씨 어때").is_nts_query is False


def test_unspecified_tax_query_searches_both_domains() -> None:
    hint = route_query("부모가 자녀에게 저가 양도하면 증여세 문제")
    assert hint.is_nts_query is True
    assert set(hint.domains) == {"interpretation", "decision"}
