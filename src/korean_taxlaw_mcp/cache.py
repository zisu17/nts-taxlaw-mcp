"""TTL + LRU 인메모리 캐시.

TTL 은 자료의 갱신 특성에 맞춘다(사이트 실측: 해석례는 등록일 기준 하루 단위로
쌓이고, 확정된 문서의 본문은 사실상 불변, 기본통칙·집행기준은 연 단위 개정).
그래서 검색 결과는 짧게, 문서 본문은 길게, 기준자료는 아주 길게 잡는다.
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, TypeVar

from .config import CACHE_MAX_ENTRIES

T = TypeVar("T")


class TTL:
    #: 검색 결과 — 신규 등록이 하루 단위로 반영되므로 30분.
    SEARCH = 30 * 60
    #: 문서 본문 — 확정 문서는 변하지 않는다. 24시간.
    DETAIL = 24 * 60 * 60
    #: 기본통칙·집행기준·고시·훈령 — 연 단위 개정. 12시간.
    GUIDANCE = 12 * 60 * 60
    #: 법령 목록 등 거의 안 바뀌는 것. 7일.
    STATIC = 7 * 24 * 60 * 60


@dataclass(slots=True)
class _Entry:
    value: Any
    stored_at: float
    ttl: float


class TtlCache:
    def __init__(self, max_size: int = CACHE_MAX_ENTRIES) -> None:
        self._map: OrderedDict[str, _Entry] = OrderedDict()
        self._max_size = max_size
        self._inflight: dict[str, asyncio.Future[Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._map.get(key)
        if entry is None:
            return None
        if time.monotonic() - entry.stored_at > entry.ttl:
            del self._map[key]
            return None
        self._map.move_to_end(key)
        return entry.value

    def set(self, key: str, value: Any, ttl: float) -> None:
        if key in self._map:
            del self._map[key]
        elif len(self._map) >= self._max_size:
            self._evict()
        self._map[key] = _Entry(value, time.monotonic(), ttl)

    def _evict(self) -> None:
        """만료분을 먼저 버리고, 없으면 가장 오래 안 쓴 것을 버린다."""
        now = time.monotonic()
        for key, entry in list(self._map.items()):
            if now - entry.stored_at > entry.ttl:
                del self._map[key]
                return
        self._map.popitem(last=False)

    async def wrap(self, key: str, ttl: float, produce: Callable[[], Awaitable[T]]) -> T:
        """캐시에 있으면 그걸 주고, 없으면 만들어 넣는다.

        같은 키에 대한 동시 요청은 하나로 합친다 — 세무 상담 한 턴에 여러 도구가
        같은 검색을 반복하는 일이 흔해서, 합치지 않으면 업스트림에 같은 요청을
        여러 번 날린다.
        """
        hit = self.get(key)
        if hit is not None:
            return hit

        running = self._inflight.get(key)
        if running is not None:
            return await asyncio.shield(running)

        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self._inflight[key] = future
        try:
            value = await produce()
        except BaseException as exc:  # noqa: BLE001 — 대기자에게 그대로 전달
            if not future.done():
                future.set_exception(exc)
            raise
        else:
            self.set(key, value, ttl)
            if not future.done():
                future.set_result(value)
            return value
        finally:
            self._inflight.pop(key, None)
            # 아무도 기다리지 않는 예외 future 의 "never retrieved" 경고를 막는다
            if future.done() and not future.cancelled() and future.exception() is not None:
                future.exception()

    def clear(self) -> None:
        self._map.clear()
        self._inflight.clear()

    def __len__(self) -> int:
        return len(self._map)


cache = TtlCache()
