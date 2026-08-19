"""지방세 파서·조회 계층 — 저장된 실제 HTML fixture 기반.

지방세 사이트는 JSON API 가 없어 렌더된 HTML 이 원본이다. 그래서 fixture 도 HTML 이고,
마크업이 바뀌면 여기 테스트가 먼저 깨진다.
"""

from __future__ import annotations

import pytest

from korean_taxlaw_mcp.codes import LOCAL_TAX_TYPE, LOCAL_TAX_TYPE_ALIAS
from korean_taxlaw_mcp.domains.local_tax import resolve_tax_codes
from korean_taxlaw_mcp.olta_client import SOURCES
from korean_taxlaw_mcp.olta_parse import parse_detail, parse_rows, parse_total

from .conftest import requires_fixtures

pytestmark = requires_fixtures

KINDS = list(SOURCES)


# ─── 목록 파싱 ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("kind", KINDS)
def test_search_rows_parsed(html_fixture, kind: str) -> None:
    """6종 전부 같은 파서로 10건이 나와야 한다."""
    html = html_fixture(f"olta_search_{kind}")
    rows = parse_rows(html)
    assert len(rows) == 10, f"{kind}: 행 {len(rows)}개"
    for row in rows:
        assert row["num"].isdigit()
        assert row["documentNumber"], f"{kind}: 문서번호 비었음"
        assert row["title"]
        # 하이라이트 마커·태그가 새어 나가면 문서번호 비교가 깨진다
        assert "<!HS>" not in row["documentNumber"]
        assert "<" not in row["title"]


@pytest.mark.parametrize("kind", KINDS)
def test_search_total_parsed(html_fixture, kind: str) -> None:
    assert parse_total(html_fixture(f"olta_search_{kind}")) > 0


def test_popup_id_is_not_the_href_void_zero(html_fixture) -> None:
    """같은 `<a>` 의 `href="javascript:void(0);"` 를 문서 번호로 잡으면 안 된다."""
    for kind in KINDS:
        rows = parse_rows(html_fixture(f"olta_search_{kind}"))
        assert all(row["num"] != "0" for row in rows), f"{kind}: num=0 이 섞였다"


def test_court_rows_carry_relationship_num(html_fixture) -> None:
    """법원 판례만 팝업 인수가 둘이다. 둘째 값이 없으면 상세가 500 을 낸다."""
    rows = parse_rows(html_fixture("olta_search_court"))
    assert rows
    assert all(row.get("relationshipNum", "").isdigit() for row in rows)


def test_other_kinds_have_no_relationship_num(html_fixture) -> None:
    for kind in ("interpretation", "moleg", "tribunal", "audit", "constitutional"):
        rows = parse_rows(html_fixture(f"olta_search_{kind}"))
        assert all("relationshipNum" not in row for row in rows), kind


@pytest.mark.parametrize("kind", ["tribunal", "court"])
def test_decision_result_label_extracted(html_fixture, kind: str) -> None:
    """심판·판례는 `<span class="label">기각</span>` 으로 결정유형을 함께 준다."""
    rows = parse_rows(html_fixture(f"olta_search_{kind}"))
    assert any(row.get("decisionResult") for row in rows)


def test_tax_type_extracted_even_when_highlighted(html_fixture) -> None:
    """검색어가 세목명과 겹치면 사이트가 `<!HS>취득세<!HE>` 로 감싸 보낸다."""
    rows = parse_rows(html_fixture("olta_search_interpretation"))
    tax_types = {row.get("taxType") for row in rows}
    assert tax_types - {None}
    assert all("<!HS>" not in (t or "") for t in tax_types)


def test_alarm_script_template_is_not_parsed_as_a_row(html_fixture) -> None:
    """페이지 상단 알림 스크립트에도 `<li><p>` 문자열이 있다. 행으로 잡히면 안 된다."""
    rows = parse_rows(html_fixture("olta_search_interpretation"))
    assert all("menuName" not in row["title"] for row in rows)
    assert all(len(row["documentNumber"]) < 60 for row in rows)


# ─── 문서번호 검색 ────────────────────────────────────────────────────────────

def test_document_number_search_is_exact_for_unique_serial(html_fixture) -> None:
    rows = parse_rows(html_fixture("olta_docnumber_exact"))
    assert len(rows) == 1
    assert rows[0]["documentNumber"].startswith("부동산세제과-1794")


def test_document_number_search_is_partial_match(html_fixture) -> None:
    """`924` 는 `4924`·`2924` 까지 잡는다 — exact 판정이 반드시 필요한 이유."""
    from korean_taxlaw_mcp.local_doc_number import is_same_local_doc_number

    rows = parse_rows(html_fixture("olta_docnumber_partial"))
    numbers = [row["documentNumber"] for row in rows]
    assert len(numbers) > 1
    # 부서명 없는 입력에는 exact 가 없어야 한다
    assert not any(is_same_local_doc_number(n, "924") for n in numbers)
    # 실제로 서로 다른 부서가 섞여 온다
    assert len({n.split("-")[0] for n in numbers}) > 1


# ─── 상세 파싱 ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("kind", KINDS)
def test_detail_parsed(html_fixture, kind: str) -> None:
    parsed = parse_detail(html_fixture(f"olta_detail_{kind}"))
    assert parsed, f"{kind}: 상세 파싱 실패"
    assert parsed.get("fullText"), f"{kind}: 본문 없음"
    text = str(parsed["fullText"])
    assert "<p" not in text and "&nbsp;" not in text
    # 화면 장식 문구가 본문에 섞이면 안 된다
    assert "자료보안을 위해" not in text
    assert "한국지방세연구원 - 지방세 법령정보시스템" not in text


def test_interpretation_detail_has_question_and_answer(html_fixture) -> None:
    parsed = parse_detail(html_fixture("olta_detail_interpretation"))
    assert parsed.get("documentNumber", "").startswith("부동산세제과")
    assert parsed.get("taxType")
    assert parsed.get("title")
    assert parsed.get("gist")
    assert parsed.get("question")
    assert parsed.get("answer")


def test_article_notation_spaces_are_tightened(html_fixture) -> None:
    """사이트가 글자 단위로 태그를 감싸 놓아 태그를 지우면 '제 106 조' 가 된다.

    그대로 반환하면 모델이 원문과 다른 조문 문자열을 인용한다.
    """
    parsed = parse_detail(html_fixture("olta_detail_interpretation"))
    text = str(parsed.get("answer") or parsed.get("fullText") or "")
    assert "제 1" not in text.replace("제 1항", "")  # '제 106 조' 류가 남지 않아야
    assert "「 " not in text and " 」" not in text


def test_decision_detail_has_reasoning(html_fixture) -> None:
    for kind in ("tribunal", "audit", "constitutional"):
        parsed = parse_detail(html_fixture(f"olta_detail_{kind}"))
        assert parsed.get("gist") or parsed.get("reasoning"), kind


# ─── 세목 코드 ────────────────────────────────────────────────────────────────

def test_local_tax_codes_cover_the_site_checkboxes() -> None:
    """사이트 상세검색의 세목 체크박스 22개를 그대로 담고 있어야 한다."""
    assert len(LOCAL_TAX_TYPE) == 22
    for code in ("11100", "11200", "24000", "25000", "23000", "30650"):
        assert code in LOCAL_TAX_TYPE


@pytest.mark.parametrize(
    "value,expected",
    [
        ("취득세", "11100"), ("취득", "11100"),
        ("재산세", "24000"), ("자동차세", "25000"),
        ("지방소득세", "23000"), ("등록면허세", "11200"),
        ("11100", "11100"),
    ],
)
def test_tax_type_alias_resolution(value: str, expected: str) -> None:
    codes, unresolved = resolve_tax_codes(value)
    assert codes == [expected]
    assert unresolved == []


def test_unresolved_tax_type_is_reported_not_dropped() -> None:
    """조용히 버리면 사용자가 필터가 걸린 줄 안다."""
    codes, unresolved = resolve_tax_codes(["취득세", "존재하지않는세목"])
    assert codes == ["11100"]
    assert unresolved == ["존재하지않는세목"]


def test_alias_table_points_only_to_known_codes() -> None:
    for alias, code in LOCAL_TAX_TYPE_ALIAS.items():
        assert code in LOCAL_TAX_TYPE, f"{alias} → {code} 는 없는 코드"


# ─── 자료 종류 정의 ───────────────────────────────────────────────────────────

def test_all_sources_declare_menu_ids() -> None:
    """menuNo 를 빼면 법원 판례 검색이 HTTP 500 을 낸다."""
    for kind, src in SOURCES.items():
        assert src.menu_no, kind
        assert src.upper_menu_id, kind
        assert src.collection, kind
        assert src.label, kind


def test_collections_are_distinct() -> None:
    collections = [src.collection for src in SOURCES.values()]
    assert len(collections) == len(set(collections))
