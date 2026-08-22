"""지방세 문서번호 정규화.

국세와 배열이 달라(부서명 + 일련번호) 별도 모듈로 처리한다. 사이트의 문서번호 검색은
일련번호 부분일치이므로 동일성 판정이 느슨하면 다른 문서를 정답으로 내놓게 된다.
이 테스트는 그 경계를 고정한다.
"""

from __future__ import annotations

import pytest

from korean_taxlaw_mcp.local_doc_number import (
    comparison_key,
    is_same_local_doc_number,
    looks_like_local_document_number,
    parse_local_doc_number,
)

TARGET = "부동산세제과-1794(2026.6.9.)호"

#: 모두 같은 문서를 가리켜야 하는 표기
EQUIVALENT = [
    "부동산세제과-1794(2026.6.9.)호",
    "부동산세제과-1794",
    "부동산세제과 1794",
    "  부동산세제과-1794  ",
    "부동산세제과–1794",          # en dash
    "부동산세제과－1794",          # 전각 hyphen
    "부동산세제과-1794호",
    "행정안전부 유권해석 부동산세제과-1794(2026.6.9.)호",
    "유권해석 부동산세제과-1794",
]


@pytest.mark.parametrize("raw", EQUIVALENT)
def test_equivalent_forms_match(raw: str) -> None:
    assert is_same_local_doc_number(raw, TARGET)


@pytest.mark.parametrize(
    "other",
    [
        "부동산세제과-1795",       # 일련번호 1 차이
        "부동산세제과-179",        # 자릿수 차이
        "지방세정팀-1794",         # 부서 다름
        "지방세운영과-1794",       # 부서 다름
        "1794",                   # 부서 없음
    ],
)
def test_different_documents_never_match(other: str) -> None:
    assert not is_same_local_doc_number(other, TARGET)


def test_same_serial_different_department_is_not_the_same_document() -> None:
    """사이트 검색은 `924` 로 `4924`·`2924` 까지 준다. 부서까지 봐야 구분된다."""
    assert not is_same_local_doc_number("부동산세제과-924", "지방세정팀-2924")
    assert not is_same_local_doc_number("부동산세제과-924", "지방세운영-4924")


def test_department_suffix_variation_is_tolerated() -> None:
    """같은 부서를 '지방세운영' / '지방세운영과' 로 섞어 쓰는 표기가 있다."""
    assert is_same_local_doc_number("지방세운영-1050", "지방세운영과-1050")


def test_date_presence_does_not_change_identity() -> None:
    assert is_same_local_doc_number("부동산세제과-1794", "부동산세제과-1794(2026.6.9.)호")


@pytest.mark.parametrize(
    "raw,department,serial",
    [
        ("부동산세제과-1794(2026.6.9.)호", "부동산세제과", "1794"),
        ("지방소득소비세제과-1683(2026.6.15.)호", "지방소득소비세제과", "1683"),
        ("지방세특례제도과-1453(2026.6.9.)호", "지방세특례제도과", "1453"),
        ("지방세정팀-2924", "지방세정팀", "2924"),
        ("지방세운영-4924", "지방세운영", "4924"),
        ("행정안전부100", "행정안전부", "100"),
    ],
)
def test_department_and_serial_extracted(raw: str, department: str, serial: str) -> None:
    """부서명이 잘리면 없는 문서번호가 만들어진다."""
    parsed = parse_local_doc_number(raw)
    assert parsed.structured is True
    assert parsed.department == department
    assert parsed.serial == serial


def test_organisation_names_are_not_stripped_as_labels() -> None:
    """'지방세'·'행정안전부' 는 부서명·문서번호의 일부다. 라벨로 떼면 번호가 깨진다."""
    assert parse_local_doc_number("지방세정팀-2924").department == "지방세정팀"
    assert parse_local_doc_number("행정안전부100").department == "행정안전부"


def test_serial_is_exposed_for_site_lookup() -> None:
    """사이트 문서번호 검색은 일련번호만 받으므로 따로 꺼낼 수 있어야 한다."""
    assert parse_local_doc_number(TARGET).serial == "1794"


def test_keyword_input_is_not_a_document_number() -> None:
    parsed = parse_local_doc_number("취득세 신탁")
    assert parsed.structured is False
    assert looks_like_local_document_number("취득세 신탁") is False


def test_bare_serial_is_not_structured() -> None:
    """숫자만으로는 문서를 특정할 수 없다."""
    assert parse_local_doc_number("924").structured is False


def test_comparison_key_ignores_separators_and_date() -> None:
    assert comparison_key("부동산세제과-1794(2026.6.9.)호") == comparison_key("부동산세제과 1794")


def test_normalizer_never_invents_a_number() -> None:
    parsed = parse_local_doc_number("부동산세제과")
    assert parsed.structured is False
    assert not any(ch.isdigit() for ch in parsed.canonical)
