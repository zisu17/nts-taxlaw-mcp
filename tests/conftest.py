from __future__ import annotations

import gzip
import json
import os
import pathlib

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


#: fixture 는 실제 응답을 저장소에 고정해 네트워크 없이 회귀 테스트를 재현한다.
#: 원본 응답이 바뀌었는지 확인할 때만 `python scripts/refresh_fixtures.py` 로 갱신한다.
FIXTURES_MISSING_REASON = (
    "테스트 fixture 가 없습니다. 저장소를 다시 확인하거나 "
    "`python scripts/refresh_fixtures.py` 로 국세법령정보시스템에서 받아오세요."
)


def fixtures_available() -> bool:
    return FIXTURES.is_dir() and (
        any(FIXTURES.glob("*.json.gz")) or any(FIXTURES.glob("*.json"))
    )


#: fixture 가 필요한 테스트 모듈에 `pytestmark = requires_fixtures` 로 붙인다.
requires_fixtures = pytest.mark.skipif(not fixtures_available(), reason=FIXTURES_MISSING_REASON)


def load(name: str) -> dict:
    """저장된 실제 국세청 응답을 읽는다."""
    compressed = FIXTURES / f"{name}.json.gz"
    if compressed.exists():
        with gzip.open(compressed, "rt", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)

    plain = FIXTURES / f"{name}.json"
    if plain.exists():
        return json.loads(plain.read_text(encoding="utf-8"))

    pytest.skip(f"{compressed.name} 없음 — {FIXTURES_MISSING_REASON}")


@pytest.fixture
def fixture():
    return load


@pytest.fixture(autouse=True)
def _isolate_shared_state():
    """캐시와 요청 한도는 모듈 수준 싱글턴이다. 테스트 간에 새게 두면
    앞 테스트가 버킷을 비워 뒤 테스트가 RATE_LIMITED 로 실패한다."""
    from korean_taxlaw_mcp.cache import cache
    from korean_taxlaw_mcp.rate_limit import upstream_limiter

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
