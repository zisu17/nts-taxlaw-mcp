"""한국지방세연구원(KILF) 지방세 법령정보시스템 클라이언트.

국세청과 달리 이 사이트는 **JSON API 가 없다.** 검색은 목록 화면 자체로 보내는
평범한 form POST 이고, 응답은 서버가 렌더링한 HTML 이다. 그래서 여기서는
HTML 파싱을 피할 수 없고, 대신 파서를 한 곳(:mod:`olta_parse`)에 몰아둔다.

검색 파라미터(실측 확정)::

    POST /explainInfo/<목록화면>.do
    Content-Type: application/x-www-form-urlencoded; charset=UTF-8

    collection    = authoritative | legal | screen | evaluation
                    | sentencing_supreme | ordinance      ← 자료 종류
    searchType    = 1(통합검색) | 2(문서번호검색)
    query         = 검색어 (연산자 &, |, !, [], {} 지원)
    taxTitleStr   = 세목 코드를 `|` 로 이어 붙인 문자열
    startCount    = **오프셋**(0, 10, 20 …). 국세청의 페이지 번호와 다르다
    startDate/endDate = YYYY.MM.DD
    sort          = RANK
    searchField   = ALL
    range         = ALL
    detailSearchIsOnOff = on

세션·쿠키·CSRF 토큰이 필요하지 않다(실측: 쿠키 없이 200 + 정상 결과).
공개 조회 화면만 사용하며 로그인·접근제어 우회를 하지 않는다.
"""

from __future__ import annotations

import asyncio
from typing import NamedTuple
from urllib.parse import urlencode

import httpx

from .cache import cache
from .config import (
    DEFAULT_USER_AGENT,
    OLTA_ORIGIN,
    OLTA_RATE_BURST,
    OLTA_RATE_PER_MIN,
    OLTA_TIMEOUT_SECONDS,
    RETRIES,
    RETRY_BASE_SECONDS,
)
from .errors import ErrorCode, NtsError, upstream
from .rate_limit import TokenBucket

#: 지방세 사이트는 국세청과 별개 호스트이므로 요청 한도도 따로 센다.
olta_limiter = TokenBucket(OLTA_RATE_PER_MIN, OLTA_RATE_BURST)

_RETRY_STATUS = {429, 500, 502, 503, 504}

_client: httpx.AsyncClient | None = None
_client_lock = asyncio.Lock()


async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is not None and not _client.is_closed:
        return _client
    async with _client_lock:
        if _client is None or _client.is_closed:
            _client = httpx.AsyncClient(
                timeout=httpx.Timeout(OLTA_TIMEOUT_SECONDS),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                follow_redirects=True,
                headers={
                    "user-agent": DEFAULT_USER_AGENT,
                    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "accept-language": "ko-KR,ko;q=0.9",
                },
            )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


def _check_limit() -> None:
    verdict = olta_limiter.take(1)
    if not verdict.ok:
        raise NtsError(
            ErrorCode.RATE_LIMITED,
            f"지방세 법령정보시스템 요청 한도 초과: {verdict.retry_after_sec}초 후 재시도하세요.",
            detail={"retryAfterSec": verdict.retry_after_sec},
        )


async def _request(
    method: str, path: str, *, data: dict[str, str] | None = None, params: dict[str, str] | None = None
) -> str:
    """폼 POST 또는 GET.

    ``data`` 는 반드시 **dict** 로 준다. httpx 0.28 의 AsyncClient 에 튜플 리스트를
    넘기면 "Attempted to send an sync request with an AsyncClient instance" 로 죽는다
    (실측). 이 사이트는 반복 키를 쓰지 않으므로 dict 로 충분하다 — 세목 다중 선택도
    ``taxTitleStr`` 한 필드에 ``|`` 로 이어 붙인다.
    """
    _check_limit()
    client = await get_client()
    url = f"{OLTA_ORIGIN}{path}"
    headers = {"referer": url}

    last_error: BaseException | None = None
    for attempt in range(RETRIES + 1):
        if attempt:
            await asyncio.sleep(RETRY_BASE_SECONDS * (2 ** (attempt - 1)))
        try:
            response = await (
                client.post(url, data=data, headers=headers)
                if method == "POST"
                else client.get(url, params=params, headers=headers)
            )
        except httpx.TimeoutException:
            last_error = NtsError(
                ErrorCode.TIMEOUT,
                f"지방세 법령정보시스템 시간 초과 ({OLTA_TIMEOUT_SECONDS}s, {path}).",
            )
            if attempt >= RETRIES:
                break
            continue
        except httpx.HTTPError as exc:
            last_error = upstream(f"지방세 법령정보시스템 요청 실패 ({path}): {exc}", path=path)
            if attempt >= RETRIES:
                break
            continue

        if response.status_code in _RETRY_STATUS and attempt < RETRIES:
            last_error = upstream(
                f"지방세 법령정보시스템 HTTP {response.status_code}", path=path, status=response.status_code
            )
            continue
        if response.status_code >= 400:
            raise upstream(
                f"지방세 법령정보시스템 HTTP {response.status_code}", path=path, status=response.status_code
            )

        text = response.text
        if not text.strip():
            last_error = upstream("지방세 법령정보시스템 응답 본문이 비어 있습니다.", path=path)
            if attempt >= RETRIES:
                break
            continue
        return text

    if isinstance(last_error, NtsError):
        raise last_error
    raise upstream(f"지방세 법령정보시스템 조회 실패 ({path}): {last_error}", path=path)


class Source(NamedTuple):
    """자료 종류별 화면·컬렉션·메뉴 식별자."""

    list_path: str
    detail_path: str
    collection: str
    #: **필수**. 빼면 법원 판례(`sentencing_supreme`)가 HTTP 500 을 낸다(실측).
    #: 다른 종류는 없어도 동작하지만 일관성을 위해 전부 함께 보낸다.
    menu_no: str
    upper_menu_id: str
    label: str


#: 자료 종류 → 화면 정보.
SOURCES: dict[str, Source] = {
    "interpretation": Source(
        "/explainInfo/authoInterpretationList.do",
        "/explainInfo/authoInterpretationDetail.do",
        "authoritative", "9020000", "9000000", "행정안전부 유권해석",
    ),
    "moleg": Source(
        "/explainInfo/lawInterpretationList.do",
        "/explainInfo/lawInterpretationDetail.do",
        "legal", "9030000", "9000000", "법제처 유권해석",
    ),
    "tribunal": Source(
        "/explainInfo/judgeDecisionList.do",
        "/explainInfo/judgeDecisionDetail.do",
        "screen", "9040000", "9000000", "조세심판원 심판결정례",
    ),
    "audit": Source(
        "/explainInfo/dlbDcnList.do",
        "/explainInfo/dlbDcnDetail.do",
        "evaluation", "9050000", "9000000", "감사원 심사결정례",
    ),
    "court": Source(
        "/explainInfo/decisionList.do",
        "/explainInfo/detailView/decisionDtlView.do",
        "sentencing_supreme", "90010100", "90010000", "법원 판례",
    ),
    "constitutional": Source(
        "/explainInfo/constitutionDcnList.do",
        "/explainInfo/constitutionDcnDetail.do",
        "ordinance", "9060000", "9000000", "헌법재판소 결정례",
    ),
}

#: 이전 이름 호환.
COLLECTIONS = SOURCES


async def search_html(
    kind: str,
    *,
    query: str = "",
    tax_codes: list[str] | None = None,
    offset: int = 0,
    date_from: str = "1970.01.01",
    date_to: str = "",
    doc_number_mode: bool = False,
    ttl: float | None = None,
) -> str:
    """목록 화면에 검색을 POST 하고 렌더된 HTML 을 돌려준다."""
    if kind not in SOURCES:
        raise NtsError(
            ErrorCode.INVALID_INPUT,
            f"지원하지 않는 지방세 자료 종류: {kind}",
            hints=[f"가능한 값: {', '.join(SOURCES)}"],
        )
    src = SOURCES[kind]

    form: dict[str, str] = {
        # menuNo·upperMenuId 를 빼면 법원 판례가 500 을 낸다(실측).
        "menuNo": src.menu_no,
        "upperMenuId": src.upper_menu_id,
        # searchType 2 는 문서번호(일련번호) 검색 모드다.
        "searchType": "2" if doc_number_mode else "1",
        "collection": src.collection,
        "query": query,
        "startCount": str(max(0, offset)),
        "sort": "RANK",
        "startDate": date_from,
        "endDate": date_to or "",
        "searchField": "ALL",
        "range": "ALL",
        "reQuery": "",
        # 세목 필터는 이 필드로만 걸린다. 체크박스 이름을 그대로 보내면 무동작이다.
        "taxTitleStr": "|".join(tax_codes or []),
        "detailSearchIsOnOff": "on",
        "pageIndex": "1",
    }

    async def run() -> str:
        return await _request("POST", src.list_path, data=form)

    if ttl and ttl > 0:
        key = f"olta:search:{kind}:{query}:{'|'.join(tax_codes or [])}:{offset}:{date_from}:{date_to}:{doc_number_mode}"
        return await cache.wrap(key, ttl, run)
    return await run()


async def detail_html(
    kind: str, num: str, *, relationship_num: str | None = None, ttl: float | None = None
) -> str:
    """상세 화면 HTML.

    법원 판례만 인수가 둘이다 — 목록의 `decisionDtlpopUp(num, relationshipNum, …)` 에서
    둘 다 받아 함께 보내야 본문이 열린다.
    """
    if kind not in SOURCES:
        raise NtsError(ErrorCode.INVALID_INPUT, f"지원하지 않는 지방세 자료 종류: {kind}")
    src = SOURCES[kind]
    params = {"num": num}
    if relationship_num:
        params["relationshipNum"] = relationship_num
    if kind == "court":
        # 법원 판례 상세는 srchWrd 가 **없으면** HTTP 500 을 낸다(실측). 빈 값이어도
        # 존재하기만 하면 열린다 — 검색어 하이라이트용 파라미터인데 필수로 취급된다.
        params.setdefault("srchWrd", "")
        params.setdefault("menuNo", src.menu_no)
        params.setdefault("upperMenuId", src.upper_menu_id)

    async def run() -> str:
        return await _request("GET", src.detail_path, params=params)

    if ttl and ttl > 0:
        return await cache.wrap(f"olta:detail:{kind}:{num}:{relationship_num or ''}", ttl, run)
    return await run()


def detail_url(kind: str, num: str, relationship_num: str | None = None) -> str:
    """사용자가 브라우저로 열 수 있는 상세 화면 주소 — 출처 추적용."""
    src = SOURCES[kind]
    params = {"num": num}
    if relationship_num:
        params["relationshipNum"] = relationship_num
    if kind == "court":
        params.update({"srchWrd": "", "menuNo": src.menu_no, "upperMenuId": src.upper_menu_id})
    return f"{OLTA_ORIGIN}{src.detail_path}?{urlencode(params)}"


def list_url(kind: str) -> str:
    return f"{OLTA_ORIGIN}{SOURCES[kind].list_path}"


def source_label(kind: str) -> str:
    return SOURCES[kind].label
