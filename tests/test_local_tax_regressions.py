"""지방세 조회의 오답 방지 회귀 테스트."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from korean_taxlaw_mcp.domains import local_tax
from korean_taxlaw_mcp.errors import ErrorCode, NtsError
from korean_taxlaw_mcp.olta_client import detail_url


async def test_search_fetches_enough_result_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    offsets: list[int] = []

    async def fake_search_html(kind: str, **kwargs: object) -> str:
        offset = int(kwargs["offset"])
        offsets.append(offset)
        return str(offset)

    def fake_rows(html: str) -> list[dict[str, str]]:
        offset = int(html)
        return [
            {"num": str(offset + i), "documentNumber": f"지방세제과-{offset + i}", "title": "t"}
            for i in range(10)
        ]

    monkeypatch.setattr(local_tax, "search_html", fake_search_html)
    monkeypatch.setattr(local_tax, "parse_rows", fake_rows)
    monkeypatch.setattr(local_tax, "parse_total", lambda _html: 35)

    result = await local_tax.search_local_documents(
        kinds=["interpretation"], query="924", limit=30, doc_number_mode=True
    )

    assert offsets == [0, 10, 20]
    assert len(result["items"]) == 30


async def test_lookup_propagates_upstream_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail(**_kwargs: object) -> dict[str, object]:
        raise NtsError(ErrorCode.TIMEOUT, "upstream timed out")

    monkeypatch.setattr(local_tax, "search_local_documents", fail)

    with pytest.raises(NtsError) as raised:
        await local_tax.lookup_local_by_document_number("부동산세제과-1794")
    assert raised.value.code == ErrorCode.TIMEOUT


@pytest.mark.parametrize("value", ["not-a-date", "2026-02-30", "20261301"])
async def test_invalid_local_search_dates_are_rejected(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    async def should_not_call(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("잘못된 날짜로 upstream을 호출하면 안 된다")

    monkeypatch.setattr(local_tax, "search_html", should_not_call)
    with pytest.raises(NtsError) as raised:
        await local_tax.search_local_documents(
            kinds=["interpretation"], query="신탁", date_to=value
        )
    assert raised.value.code == ErrorCode.INVALID_INPUT


def test_court_source_url_contains_required_parameters() -> None:
    parsed = urlparse(detail_url("court", "20002922", "60099210"))
    query = parse_qs(parsed.query, keep_blank_values=True)
    assert query == {
        "num": ["20002922"],
        "relationshipNum": ["60099210"],
        "srchWrd": [""],
        "menuNo": ["90010100"],
        "upperMenuId": ["90010000"],
    }
