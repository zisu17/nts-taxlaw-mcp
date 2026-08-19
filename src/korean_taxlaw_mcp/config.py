"""환경변수 설정. 모두 선택 항목이며 기본값만으로 동작한다."""

from __future__ import annotations

import os

# 국세 — 국세청 국세법령정보시스템
NTS_ORIGIN = "https://taxlaw.nts.go.kr"
ACTION_URL = f"{NTS_ORIGIN}/action.do"

# 지방세 — 한국지방세연구원(KILF) 지방세 법령정보시스템
OLTA_ORIGIN = "https://www.olta.re.kr"


def _int_env(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= minimum else default


DEFAULT_USER_AGENT = os.environ.get(
    "NTS_USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
)

TIMEOUT_SECONDS: float = _int_env("NTS_TIMEOUT_MS", 20_000) / 1000
RETRIES: int = _int_env("NTS_RETRIES", 3, minimum=0)
RETRY_BASE_SECONDS: float = 0.3

RATE_PER_MIN: int = _int_env("NTS_RATE_PER_MIN", 60)
RATE_BURST: int = _int_env("NTS_RATE_BURST", 20)

# 본문 응답 상한. 실측으로 심사청구 일부 문서의 본문 HTML 이 1.4MB 까지 나온다 —
# 그대로 실으면 클라이언트 컨텍스트를 통째로 삼킨다.
BODY_LIMIT: int = _int_env("NTS_BODY_LIMIT", 30_000, minimum=500)

CACHE_MAX_ENTRIES: int = _int_env("NTS_CACHE_MAX", 600)

# 지방세 사이트도 같은 타임아웃·재시도·한도 정책을 쓴다. 별도로 조절하려면
# OLTA_* 환경변수를 준다.
OLTA_TIMEOUT_SECONDS: float = _int_env("OLTA_TIMEOUT_MS", 20_000) / 1000
OLTA_RATE_PER_MIN: int = _int_env("OLTA_RATE_PER_MIN", 60)
OLTA_RATE_BURST: int = _int_env("OLTA_RATE_BURST", 20)
