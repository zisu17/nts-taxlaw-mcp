from __future__ import annotations

import json
import os
import pathlib

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


#: fixture 는 실제 응답을 그대로 담아 8MB 가까이 되므로 커밋하지 않는다.
#: 저장소를 clone 하는 사람 대부분은 서버를 쓰기만 하고 테스트를 돌리지 않는다.
#: 필요하면 `python scripts/refresh_fixtures.py` 로 만든다.
FIXTURES_MISSING_REASON = (
    "테스트 fixture 가 없습니다. `python scripts/refresh_fixtures.py` 로 "
    "국세법령정보시스템에서 받아오세요 (약 8MB, 커밋 대상 아님)."
)


def fixtures_available() -> bool:
    return FIXTURES.is_dir() and any(FIXTURES.glob("*.json"))


#: fixture 가 필요한 테스트 모듈에 `pytestmark = requires_fixtures` 로 붙인다.
requires_fixtures = pytest.mark.skipif(not fixtures_available(), reason=FIXTURES_MISSING_REASON)


def load(name: str) -> dict:
    """저장된 실제 국세청 응답을 읽는다."""
    path = FIXTURES / f"{name}.json"
    if not path.exists():
        pytest.skip(f"{path.name} 없음 — {FIXTURES_MISSING_REASON}")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def fixture():
    return load


@pytest.fixture(autouse=True)
def _isolate_shared_state():
    """캐시와 요청 한도는 모듈 수준 싱글턴이다. 테스트 간에 새게 두면
    앞 테스트가 버킷을 비워 뒤 테스트가 RATE_LIMITED 로 실패한다."""
    from nts_taxlaw_mcp.cache import cache
    from nts_taxlaw_mcp.rate_limit import upstream_limiter

    cache.clear()
    upstream_limiter.reset()
    yield
    cache.clear()
    upstream_limiter.reset()


#: 실제 국세청 서버를 때리는 테스트는 기본으로 건너뛴다.
#: CI 가 남의 공개 서비스를 매 실행마다 두드리면 안 되고, 사이트 장애가 우리 빌드를
#: 깨뜨려서도 안 된다. NTS_LIVE=1 을 줄 때만 돈다.
live = pytest.mark.skipif(
    os.environ.get("NTS_LIVE") != "1",
    reason="실제 국세청 서버 호출 테스트 — NTS_LIVE=1 로 활성화",
)
