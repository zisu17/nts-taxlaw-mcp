"""국세법령정보시스템 ``action.do`` 클라이언트.

사이트 전체가 하나의 디스패처를 쓴다::

    POST https://taxlaw.nts.go.kr/action.do
    Content-Type: application/x-www-form-urlencoded
    actionId=<액션ID>&paramData=<JSON>

    → {"status": "SUCCESS", "message": null, "data": {"<액션ID>": <결과>}}

화면(``/qt/USEQTA001M.do`` 등)은 이 액션을 감싼 얇은 껍데기라서, HTML 을 긁는
대신 액션을 직접 부르면 사이트 개편에 훨씬 덜 취약하다. 그래서 이 서버는
HTML 파싱을 문서 본문(HWP→HTML 변환 결과) 한 곳에만 쓴다.

세션·쿠키·로그인·토큰이 필요하지 않다(실측). 공개 조회 액션만 사용한다.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from .cache import cache
from .config import (
    ACTION_URL,
    DEFAULT_USER_AGENT,
    NTS_ORIGIN,
    RETRIES,
    RETRY_BASE_SECONDS,
    TIMEOUT_SECONDS,
)
from .errors import ErrorCode, NtsError, upstream
from .rate_limit import upstream_limiter

_RETRY_STATUS = {429, 500, 502, 503, 504}

_client: httpx.AsyncClient | None = None
_client_lock = asyncio.Lock()


async def get_client() -> httpx.AsyncClient:
    """공용 AsyncClient. keep-alive 연결 풀을 재사용해 왕복 비용을 줄인다."""
    global _client
    if _client is not None and not _client.is_closed:
        return _client
    async with _client_lock:
        if _client is None or _client.is_closed:
            _client = httpx.AsyncClient(
                timeout=httpx.Timeout(TIMEOUT_SECONDS),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                follow_redirects=False,
                headers={
                    "user-agent": DEFAULT_USER_AGENT,
                    "accept": "application/json, text/javascript, */*; q=0.01",
                    "accept-language": "ko-KR,ko;q=0.9",
                    "x-requested-with": "XMLHttpRequest",
                    "origin": NTS_ORIGIN,
                },
            )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


async def _post_action(action_id: str, param_data: Any, referer: str) -> dict[str, Any]:
    """``action.do`` 한 번 호출. 재시도·타임아웃·한도만 담당하고 해석은 하지 않는다."""
    verdict = upstream_limiter.take(1)
    if not verdict.ok:
        raise NtsError(
            ErrorCode.RATE_LIMITED,
            f"요청 한도 초과: {verdict.retry_after_sec}초 후 재시도하세요.",
            detail={"retryAfterSec": verdict.retry_after_sec},
        )

    client = await get_client()
    body = {"actionId": action_id, "paramData": json.dumps(param_data, ensure_ascii=False)}
    last_error: BaseException | None = None

    for attempt in range(RETRIES + 1):
        if attempt:
            await asyncio.sleep(RETRY_BASE_SECONDS * (2 ** (attempt - 1)))
        try:
            response = await client.post(
                ACTION_URL,
                data=body,
                headers={
                    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "referer": referer,
                },
            )
        except httpx.TimeoutException:
            last_error = NtsError(
                ErrorCode.TIMEOUT, f"action.do 시간 초과 ({TIMEOUT_SECONDS}s, {action_id})."
            )
            if attempt >= RETRIES:
                break
            continue
        except httpx.HTTPError as exc:
            last_error = upstream(f"action.do 요청 실패 ({action_id}): {exc}", actionId=action_id)
            if attempt >= RETRIES:
                break
            continue

        if response.status_code in _RETRY_STATUS and attempt < RETRIES:
            last_error = upstream(
                f"action.do HTTP {response.status_code}", actionId=action_id, status=response.status_code
            )
            continue
        if response.status_code >= 400:
            raise upstream(
                f"action.do HTTP {response.status_code}", actionId=action_id, status=response.status_code
            )

        text = response.text
        # 점검·차단 페이지는 200 + HTML 로 온다. 빈 본문도 일시 장애로 본다.
        if not text.strip():
            last_error = upstream("action.do 응답 본문이 비어 있습니다.", actionId=action_id)
            if attempt >= RETRIES:
                break
            continue
        if text.lstrip().startswith("<"):
            last_error = upstream(
                "action.do 가 JSON 대신 HTML 을 반환했습니다(점검·차단 가능).", actionId=action_id
            )
            if attempt >= RETRIES:
                break
            continue

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise NtsError(
                ErrorCode.PARSE_ERROR,
                f"action.do 응답을 JSON 으로 해석할 수 없습니다 ({action_id}).",
                detail={"actionId": action_id, "sample": text[:200]},
            ) from exc

    if isinstance(last_error, NtsError):
        raise last_error
    raise upstream(f"국세법령정보시스템 조회 실패 ({action_id}): {last_error}", actionId=action_id)


async def call_action(
    action_id: str,
    param_data: Any,
    *,
    referer: str | None = None,
    ttl: float | None = None,
    cache_key: str | None = None,
) -> Any:
    """액션 호출 + 봉투 해체.

    ``status != "SUCCESS"`` 는 업스트림 실패로 올린다. 이걸 "자료 없음"으로
    흘리면 장애가 부존재로 번역되므로 반드시 구분한다.
    """
    ref = referer or f"{NTS_ORIGIN}/index.do"

    async def run() -> Any:
        envelope = await _post_action(action_id, param_data, ref)
        status = envelope.get("status")
        if status and status != "SUCCESS":
            raise upstream(
                f"국세법령정보시스템이 오류를 반환했습니다 ({action_id}): "
                f"{envelope.get('message') or status}",
                actionId=action_id,
                status=status,
            )
        data = envelope.get("data") or {}
        if action_id not in data:
            raise NtsError(
                ErrorCode.PARSE_ERROR,
                f"응답에 {action_id} 결과가 없습니다.",
                detail={"actionId": action_id, "keys": list(data.keys())},
            )
        return data[action_id]

    if ttl and ttl > 0:
        key = cache_key or f"{action_id}:{json.dumps(param_data, sort_keys=True, ensure_ascii=False)}"
        return await cache.wrap(key, ttl, run)
    return await run()


def detail_url(ntst_dcm_id: str, kind: str) -> str:
    """문서 상세 화면 URL — 출처 추적용. 사용자가 브라우저로 열 수 있는 주소다."""
    path = "/qt/USEQTA002P.do" if kind == "question" else "/pd/USEPDA002P.do"
    return f"{NTS_ORIGIN}{path}?ntstDcmId={ntst_dcm_id}"
