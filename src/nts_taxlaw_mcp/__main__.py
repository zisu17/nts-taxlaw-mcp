"""실행 진입점.

기본은 STDIO — Claude Desktop / Claude Code 가 MCP 서버를 띄우는 방식이다.
``--http`` 는 원격·컨테이너 배치용이며, FastMCP 가 내장한 HTTP 전송을 쓴다.
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="nts-taxlaw-mcp",
        description="국세청 국세법령정보시스템 직접 조회 MCP 서버",
    )
    parser.add_argument("--http", action="store_true", help="STDIO 대신 HTTP 전송으로 실행")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP 바인드 주소 (기본 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="HTTP 포트 (기본 8000)")
    args = parser.parse_args()

    from .server import mcp

    if args.http:
        # 엔드포인트는 http://<host>:<port>/mcp
        mcp.run(transport="http", host=args.host, port=args.port)
        return

    # STDIO 모드: stdout 은 JSON-RPC 전용이다. FastMCP 가 로그·배너를 stderr 로 보내므로
    # 여기서는 아무것도 print 하지 않는다.
    mcp.run(transport="stdio")


if __name__ == "__main__":
    sys.exit(main())
