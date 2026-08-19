"""검색 문법 변환 — 사이트 실측 의미와 어긋나면 검색이 조용히 틀린다."""

from __future__ import annotations

import pytest

from nts_taxlaw_mcp.query import SORT, build_vocab, format_date, to_site_date, tokenize_query


def test_space_separated_terms_become_and() -> None:
    """배열 원소끼리 AND 다. 원소를 늘리는 것이 AND 의 표현이다."""
    include, exclude = build_vocab("상속 공동상속주택", "all")
    assert include == ["상속", "공동상속주택"]
    assert exclude == []


def test_any_match_joins_with_ascii_pipe() -> None:
    """OR 는 ASCII 파이프다. 배열 원소를 늘리면 AND 가 되어 의미가 뒤집힌다."""
    include, _ = build_vocab("상속 증여", "any")
    assert include == ["상속|증여"]
    assert len(include) == 1


def test_or_operator_is_not_broken_bar() -> None:
    """broken bar(¦, U+00A6)는 사이트에서 OR 로 동작하지 않는다(AND 와 같은 결과)."""
    include, _ = build_vocab("상속 증여", "any")
    assert "¦" not in include[0]
    assert "|" in include[0]


def test_exclude_becomes_not_list() -> None:
    include, exclude = build_vocab("상속", "all", ["증여", "상속포기"])
    assert include == ["상속"]
    assert exclude == ["증여", "상속포기"]


def test_quoted_phrase_stays_one_term() -> None:
    assert tokenize_query('"공동상속주택 소수지분" 양도') == ["공동상속주택 소수지분", "양도"]


def test_single_term_ignores_any_match() -> None:
    """낱말이 하나면 OR 로 이을 것이 없다."""
    include, _ = build_vocab("상속", "any")
    assert include == ["상속"]


def test_empty_query_yields_empty_include() -> None:
    assert build_vocab(None, "all") == ([], [])
    assert build_vocab("   ", "all") == ([], [])


def test_sort_tokens_are_only_verified_fields() -> None:
    """허용되지 않는 정렬 필드는 오류가 아니라 0건을 낳는다(RANK/DESC → total 0)."""
    assert set(SORT) == {"latest", "oldest", "relevance"}
    for value in SORT.values():
        field = value.split("/")[0]
        assert field in {"DCM_RGT_DTM", "FRS_RGT_DTM", "SCORE"}
    assert "RANK" not in " ".join(SORT.values())


@pytest.mark.parametrize(
    "raw,expected",
    [("2026-08-11", "20260811"), ("20260811", "20260811"), ("2026-08", "20260801"),
     ("2026", "20260101"), (None, ""), ("", ""), ("bad", "")],
)
def test_site_date_conversion(raw, expected) -> None:
    assert to_site_date(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [("20260811000000", "2026-08-11"), ("20260811", "2026-08-11"), ("2026", None), (None, None)],
)
def test_display_date_conversion(raw, expected) -> None:
    assert format_date(raw) == expected
