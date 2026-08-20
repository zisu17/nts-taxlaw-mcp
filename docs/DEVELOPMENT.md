# 개발 가이드

## 준비 사항

- Python 3.11 이상
- [uv](https://docs.astral.sh/uv/)

## 개발 환경

```bash
git clone https://github.com/zisu17/korean-taxlaw-mcp.git
cd korean-taxlaw-mcp
uv sync --extra dev
```

## 테스트

일반 테스트는 원본 사이트를 호출하지 않습니다.

```bash
uv run pytest -q --ignore=tests/test_live.py
```

실서버 통합 테스트는 명시적으로 활성화한 경우에만 실행됩니다.

```bash
NTS_LIVE=1 uv run pytest -q tests/test_live.py
```
