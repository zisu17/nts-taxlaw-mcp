"""공공 웹사이트 차단 신호에 대한 보호 장치."""

from __future__ import annotations

import httpx
import pytest
import respx

from korean_taxlaw_mcp.action_client import ACTION_URL, _post_action, close_client
from korean_taxlaw_mcp.errors import ErrorCode, NtsError
from korean_taxlaw_mcp.olta_client import OLTA_ORIGIN, _request, close_client as close_olta_client
from korean_taxlaw_mcp.rate_limit import TokenBucket, retry_after_seconds


def test_cooldown_blocks_requests_without_spending_tokens() -> None:
    bucket = TokenBucket(60, 5)
    bucket.block_for(120, now=100.0)
    verdict = bucket.take(now=101.0)
    assert verdict.ok is False
    assert verdict.retry_after_sec >= 119
    bucket.reset()
    assert bucket.take(now=101.0).ok is True


def test_retry_after_never_shortens_the_safe_default() -> None:
    assert retry_after_seconds("10", default=900) == 900
    assert retry_after_seconds("1800", default=900) == 1800
    assert retry_after_seconds("invalid", default=900) == 900


async def test_nts_429_stops_immediately_and_enters_cooldown() -> None:
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(ACTION_URL).mock(
            return_value=httpx.Response(429, headers={"Retry-After": "1800"})
        )
        with pytest.raises(NtsError) as first:
            await _post_action("TEST", {}, "https://taxlaw.nts.go.kr/")
        assert first.value.code == ErrorCode.RATE_LIMITED
        assert first.value.detail == {"status": 429, "retryAfterSec": 1800}

        with pytest.raises(NtsError) as second:
            await _post_action("TEST", {}, "https://taxlaw.nts.go.kr/")
        assert second.value.code == ErrorCode.RATE_LIMITED
        assert route.call_count == 1
    await close_client()


async def test_olta_block_page_stops_future_requests() -> None:
    url = f"{OLTA_ORIGIN}/explainInfo/authoInterpretationList.do"
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(url).mock(
            return_value=httpx.Response(200, text="<html><title>Access Denied</title></html>")
        )
        with pytest.raises(NtsError) as first:
            await _request("POST", "/explainInfo/authoInterpretationList.do", data={})
        assert first.value.code == ErrorCode.UPSTREAM_ERROR

        with pytest.raises(NtsError) as second:
            await _request("POST", "/explainInfo/authoInterpretationList.do", data={})
        assert second.value.code == ErrorCode.RATE_LIMITED
        assert route.call_count == 1
    await close_olta_client()
