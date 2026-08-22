# 원격 HTTP 배포용 이미지 (Cloud Run 등).
#
# 로컬 STDIO에서는 쓰지 않는다. `uv tool install` 경로와도 무관하다.
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# 코드만 고쳤을 때 재설치하지 않도록 의존성 레이어를 소스와 분리한다.
# README.md 는 pyproject 의 readme 항목이 가리키므로 프로젝트 빌드에 필요하다.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev

# 다중 인스턴스에서 세션 고정 없이 동작하도록 stateless 로 띄운다.
ENV FASTMCP_STATELESS_HTTP=true

# Cloud Run 은 PORT 를 주입한다. 셸 확장이 필요하므로 exec 형식을 쓰지 않는다.
CMD ["sh", "-c", "korean-taxlaw-mcp --http --host 0.0.0.0 --port ${PORT:-8080}"]
