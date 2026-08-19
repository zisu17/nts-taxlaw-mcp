"""문서번호 정규화 — 이 서버의 가장 중요한 기능이라 경계를 촘촘히 고정한다."""

from __future__ import annotations

import pytest

from korean_taxlaw_mcp.doc_number import (
    comparison_key,
    is_same_doc_number,
    lookup_candidates,
    looks_like_document_number,
    parse_doc_number,
)

TARGET = "서면-2026-법규재산-0119"

#: 모두 같은 문서를 가리켜야 하는 표기들 (요구 사양 + 사이트 복사 실태)
EQUIVALENT = [
    "서면-2026-법규재산-0119",
    "서면 2026 법규재산 0119",
    "서면2026법규재산0119",
    "서면서면-2026-법규재산-0119",
    "질의회신 서면-2026-법규재산-0119",
    "질의회신서면-2026-법규재산-0119",
    "국세청 서면-2026-법규재산-0119",
    "  서면-2026-법규재산-0119  ",
    "서면–2026–법규재산–0119",       # en dash
    "서면－2026－법규재산－0119",       # 전각 hyphen
    "서면-2026-법규재산-119",         # 0 패딩 누락
]


@pytest.mark.parametrize("raw", EQUIVALENT)
def test_equivalent_forms_normalize_to_target(raw: str) -> None:
    assert parse_doc_number(raw).canonical.replace(" ", "") in (
        TARGET,
        "서면-2026-법규재산-119",
    )
    assert is_same_doc_number(raw, TARGET)


def test_highlight_markers_are_stripped() -> None:
    """검색 응답은 일치 구간을 <!HS>..<!HE> 로 감싸 보낸다."""
    site = "<!HS>서면<!HE>-<!HS>2026<!HE>-<!HS>법규재산<!HE>-<!HS>0119<!HE>"
    assert is_same_doc_number(site, TARGET)
    assert comparison_key(site) == comparison_key(TARGET)


@pytest.mark.parametrize(
    "other",
    [
        "서면-2026-법규재산-0109",   # 일련번호 1자리 차이
        "서면-2025-법규재산-0119",   # 연도 차이
        "사전-2026-법규재산-0119",   # 종류 차이
        "서면-2026-법규법인-0119",   # 분류 차이
        "법규재산-0119",             # 부분일치
        "서면-2026-법규재산-01190",  # 자릿수 차이
    ],
)
def test_different_documents_never_match(other: str) -> None:
    """부분일치·인접 번호를 같은 문서로 보면 세무 상담에서 곧바로 오답이 된다."""
    assert not is_same_doc_number(other, TARGET)


@pytest.mark.parametrize("suffix", ["호", "XYZ", "abc"])
def test_arbitrary_serial_suffix_is_not_an_exact_match(suffix: str) -> None:
    raw = f"{TARGET}{suffix}"
    assert parse_doc_number(raw).structured is False
    assert not is_same_doc_number(raw, TARGET)


def test_layout_a_type_year_category_serial() -> None:
    p = parse_doc_number("서면-2026-법규재산-0119")
    assert (p.layout, p.type, p.year, p.category, p.serial) == ("A", "서면", "2026", "법규재산", "0119")
    assert p.inferred_doc_class == "02"


def test_layout_b_keeps_agency_inside_number() -> None:
    """적부·이의·심사는 두 번째 마디가 기관이다. 접두로 오인해 떼면 번호가 깨진다."""
    p = parse_doc_number("적부-국세청-2026-0119")
    assert (p.layout, p.type, p.agency, p.year, p.serial) == ("B", "적부", "국세청", "2026", "0119")
    assert p.inferred_doc_class == "05"
    assert p.canonical == "적부-국세청-2026-0119"


def test_layout_b_survives_label_prefix() -> None:
    assert parse_doc_number("과세적부 적부-국세청-2026-0119").canonical == "적부-국세청-2026-0119"


def test_layout_b_compact_form() -> None:
    assert parse_doc_number("적부국세청20260119").canonical == "적부-국세청-2026-0119"


def test_layout_c_old_ministry_style() -> None:
    p = parse_doc_number("재정경제부 국제조세협력과-104")
    assert p.layout == "C"
    assert p.agency == "재정경제부"
    assert p.serial == "104"


@pytest.mark.parametrize(
    "raw,expected_class",
    [
        ("사전-2026-법규소득-0543", "01"),
        ("서면-2026-법규재산-0119", "02"),
        ("기준-2026-법규부가-0096", "03"),
        ("고시-2026-소비-0002", "04"),
        ("적부-국세청-2026-0119", "05"),
        ("이의-광주청-2026-0024", "06"),
        ("심사-부가-2026-0018", "07"),
        ("조심-2025-인-4460", "08"),
        ("대법원-2024-두-55396", "09"),
        ("서울고등법원-2025-누-10162", "09"),
        ("헌법재판소-2011-헌바-97", "10"),
    ],
)
def test_doc_class_inferred_from_shape(raw: str, expected_class: str) -> None:
    """번호 모양만으로 어느 영역을 먼저 볼지 정할 수 있어야 한다."""
    assert parse_doc_number(raw).inferred_doc_class == expected_class


def test_merged_constitutional_cases_keep_extra_serials() -> None:
    p = parse_doc_number("헌법재판소-2009-헌바-35,82")
    assert p.serial == "35"
    assert p.extra_serials == ["82"]
    # 병합 목록이 다르면 다른 문서다
    assert not is_same_doc_number("헌법재판소-2009-헌바-35,82", "헌법재판소-2009-헌바-35")


def test_keyword_input_is_not_treated_as_document_number() -> None:
    p = parse_doc_number("상속 공동상속주택")
    assert p.structured is False
    assert p.layout == "unknown"
    assert looks_like_document_number("상속 공동상속주택") is False


def test_partial_number_is_not_structured() -> None:
    """'법규재산-0119' 는 문서번호로 확정할 수 없다 — 키워드로 처리돼야 한다."""
    assert parse_doc_number("법규재산-0119").structured is False
    assert looks_like_document_number("법규재산-0119") is False


def test_candidates_include_hyphenated_and_compact() -> None:
    cands = lookup_candidates("서면2026법규재산0119")
    assert "서면-2026-법규재산-0119" in cands
    assert "서면2026법규재산0119" in cands


def test_normalizer_never_invents_a_number() -> None:
    """정규화가 없는 번호를 만들어내면 안 된다 — 입력 정보만으로 구성돼야 한다."""
    p = parse_doc_number("서면-2026-법규재산")   # 일련번호 없음
    assert p.structured is False
    assert "0" not in p.canonical.replace("2026", "")
