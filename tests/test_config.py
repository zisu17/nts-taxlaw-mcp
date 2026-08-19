"""환경변수 우선순위: 사이트별 > 공통 > 기본값.

설정이 조용히 엉키면 한쪽 사이트에만 타임아웃이 걸리거나 남의 서버에 과도한 요청을
보내게 된다. 우선순위를 코드로 고정한다.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Iterator

import pytest

PREFIXES = ("TAXLAW_", "NTS_", "OLTA_")


@pytest.fixture
def load_config(monkeypatch: pytest.MonkeyPatch):
    """주어진 환경변수만 남기고 config 를 다시 읽는다."""

    def _load(env: dict[str, str]):
        for name in list(os.environ):
            if name.startswith(PREFIXES):
                monkeypatch.delenv(name, raising=False)
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        import korean_taxlaw_mcp.config as config_module

        return importlib.reload(config_module)

    yield _load
    # 다른 테스트가 오염된 설정을 보지 않게 원상 복구한다
    import korean_taxlaw_mcp.config as config_module

    importlib.reload(config_module)


def test_defaults(load_config) -> None:
    config = load_config({})
    for site in (config.NTS, config.OLTA):
        assert site.timeout_seconds == 20.0
        assert site.retries == 3
        assert site.rate_per_min == 60
        assert site.rate_burst == 20
        assert site.body_limit == 30_000
        assert "Mozilla/5.0" in site.user_agent
    assert config.CACHE_MAX_ENTRIES == 600


def test_common_variables_apply_to_both_sites(load_config) -> None:
    config = load_config(
        {
            "TAXLAW_TIMEOUT_MS": "5000",
            "TAXLAW_RETRIES": "1",
            "TAXLAW_RATE_PER_MIN": "11",
            "TAXLAW_RATE_BURST": "4",
            "TAXLAW_BODY_LIMIT": "2000",
            "TAXLAW_USER_AGENT": "Common/1",
        }
    )
    for site in (config.NTS, config.OLTA):
        assert site.timeout_seconds == 5.0
        assert site.retries == 1
        assert site.rate_per_min == 11
        assert site.rate_burst == 4
        assert site.body_limit == 2000
        assert site.user_agent == "Common/1"


def test_site_variable_overrides_common(load_config) -> None:
    config = load_config(
        {
            "TAXLAW_TIMEOUT_MS": "5000",
            "NTS_TIMEOUT_MS": "1000",
            "OLTA_TIMEOUT_MS": "2000",
            "TAXLAW_USER_AGENT": "Common/1",
            "NTS_USER_AGENT": "NtsOnly/2",
        }
    )
    assert config.NTS.timeout_seconds == 1.0
    assert config.OLTA.timeout_seconds == 2.0
    assert config.NTS.user_agent == "NtsOnly/2"
    # 재정의하지 않은 쪽은 공통값을 그대로 쓴다
    assert config.OLTA.user_agent == "Common/1"


def test_site_variable_alone_does_not_leak_to_the_other_site(load_config) -> None:
    """이름과 적용 범위가 일치해야 한다. `NTS_*` 가 지방세에 걸리면 안 된다."""
    config = load_config({"NTS_RATE_PER_MIN": "5", "NTS_USER_AGENT": "NtsOnly/2", "NTS_BODY_LIMIT": "900"})
    assert config.NTS.rate_per_min == 5
    assert config.OLTA.rate_per_min == 60          # 기본값 유지
    assert config.NTS.user_agent == "NtsOnly/2"
    assert "Mozilla/5.0" in config.OLTA.user_agent  # 기본값 유지
    assert config.NTS.body_limit == 900
    assert config.OLTA.body_limit == 30_000


def test_olta_variable_alone_does_not_leak_to_nts(load_config) -> None:
    config = load_config({"OLTA_RATE_PER_MIN": "5", "OLTA_TIMEOUT_MS": "1000"})
    assert config.OLTA.rate_per_min == 5
    assert config.OLTA.timeout_seconds == 1.0
    assert config.NTS.rate_per_min == 60
    assert config.NTS.timeout_seconds == 20.0


def test_cache_max_is_shared_and_keeps_legacy_name(load_config) -> None:
    """캐시는 두 사이트가 한 객체를 공유하므로 사이트별 재정의가 성립하지 않는다."""
    assert load_config({"TAXLAW_CACHE_MAX": "42"}).CACHE_MAX_ENTRIES == 42
    # 이전 이름도 계속 동작해야 한다
    assert load_config({"NTS_CACHE_MAX": "77"}).CACHE_MAX_ENTRIES == 77
    # 새 이름이 우선
    assert load_config({"TAXLAW_CACHE_MAX": "42", "NTS_CACHE_MAX": "77"}).CACHE_MAX_ENTRIES == 42


@pytest.mark.parametrize("bad", ["", "abc", "0", "-5"])
def test_invalid_value_falls_through_instead_of_crashing(load_config, bad: str) -> None:
    """잘못 준 값 때문에 서버가 못 뜨는 것보다 기본값으로 도는 편이 낫다."""
    config = load_config({"NTS_RATE_PER_MIN": bad})
    assert config.NTS.rate_per_min == 60


def test_invalid_site_value_falls_back_to_common_not_default(load_config) -> None:
    config = load_config({"TAXLAW_TIMEOUT_MS": "7000", "NTS_TIMEOUT_MS": "abc"})
    assert config.NTS.timeout_seconds == 7.0


def test_retries_zero_is_allowed(load_config) -> None:
    """재시도 끄기는 유효한 설정이다(minimum=0)."""
    assert load_config({"TAXLAW_RETRIES": "0"}).NTS.retries == 0


def test_body_limit_has_a_floor(load_config) -> None:
    """너무 작은 상한은 본문을 통째로 잘라 쓸모없게 만든다."""
    assert load_config({"TAXLAW_BODY_LIMIT": "10"}).NTS.body_limit == 30_000


def test_rate_buckets_are_separate_objects() -> None:
    """두 곳은 다른 기관의 서버다. 한쪽 조회가 다른 쪽 한도를 깎으면 안 된다."""
    from korean_taxlaw_mcp.olta_client import olta_limiter
    from korean_taxlaw_mcp.rate_limit import upstream_limiter

    assert upstream_limiter is not olta_limiter


def test_sites_point_at_different_origins() -> None:
    from korean_taxlaw_mcp.config import NTS, OLTA

    assert NTS.origin == "https://taxlaw.nts.go.kr"
    assert OLTA.origin == "https://www.olta.re.kr"
    assert NTS.name != OLTA.name
