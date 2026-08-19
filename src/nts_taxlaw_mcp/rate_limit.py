"""토큰버킷 요청 한도.

국세법령정보시스템은 공개 조회 서비스이고 우리는 손님이다. 한 대화 턴에
tax_research 같은 체인 도구가 10여 회를 연달아 부르는 게 정상이므로 고정창
방식은 창 초반에 몰린 요청을 통째로 막아버린다. 토큰버킷은 연속 리필이라
평균 처리율은 같게 유지하면서 버스트만 흡수한다.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .config import RATE_BURST, RATE_PER_MIN


@dataclass(frozen=True, slots=True)
class Verdict:
    ok: bool
    retry_after_sec: int


_OK = Verdict(True, 0)


class TokenBucket:
    def __init__(self, rate_per_min: int, burst: int | None = None) -> None:
        self._rate = rate_per_min
        self._burst = burst if burst is not None else rate_per_min
        self._tokens = float(self._burst)
        self._last = 0.0

    def take(self, n: int = 1, now: float | None = None) -> Verdict:
        if self._rate <= 0:
            return Verdict(False, 60)
        current = time.monotonic() if now is None else now
        if self._last == 0.0:
            self._last = current
        self._tokens = min(self._burst, self._tokens + (current - self._last) / 60.0 * self._rate)
        self._last = current

        if self._tokens >= n:
            self._tokens -= n
            return _OK
        deficit = min(n, self._burst) - self._tokens
        return Verdict(False, max(1, int(deficit / self._rate * 60) + 1))

    def reset(self) -> None:
        """버킷을 가득 찬 상태로 되돌린다. 테스트 격리용."""
        self._tokens = float(self._burst)
        self._last = 0.0


upstream_limiter = TokenBucket(RATE_PER_MIN, RATE_BURST)
