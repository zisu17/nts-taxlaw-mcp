"""원격 호스팅(Prefect Horizon) 진입점.

Horizon 은 `main.py:mcp` 처럼 **파일 경로와 객체 이름**으로 서버를 찾고, 그 파일을
패키지가 아닌 단독 스크립트로 로드한다. 그래서 `src/korean_taxlaw_mcp/server.py` 를
직접 진입점으로 주면 그 안의 상대 임포트(`from . import ...`)가 부모 패키지를 못 찾아
`ImportError` 로 죽는다.

여기서 `src` 를 경로에 넣고 패키지로 임포트하는 이유가 그것이다. 배포 환경이
프로젝트 자체를 설치하지 않고 의존성만 설치하는 경우에도 임포트가 성립한다.

로컬 실행(STDIO)에는 이 파일이 필요하지 않다 — `korean-taxlaw-mcp` 명령이
`__main__.py` 를 그대로 쓴다.
"""

from __future__ import annotations

import pathlib
import sys

_SRC = pathlib.Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from korean_taxlaw_mcp.server import mcp  # noqa: E402

__all__ = ["mcp"]
