# 상세 설치 및 연결 가이드

README의 간단 설치로 해결되지 않거나 직접 설정하려는 사용자를 위한 문서입니다.

## 1. 권장 설치: uv tool

Python을 직접 설치하거나 가상환경을 수동으로 만들 필요는 없습니다.
[uv](https://docs.astral.sh/uv/)가 필요한 Python과 패키지를 관리합니다.

### uv 설치

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

사내 정책으로 스크립트 실행이 제한된 Windows 환경:

```powershell
winget install --id=astral-sh.uv -e
```

macOS 또는 Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

설치 후 터미널을 다시 열고 확인합니다.

```bash
uv --version
```

### korean-taxlaw-mcp 설치

```bash
uv tool install git+https://github.com/zisu17/korean-taxlaw-mcp.git
```

동작 확인:

```bash
korean-taxlaw-mcp --help
```

업데이트와 제거:

```bash
uv tool upgrade korean-taxlaw-mcp
uv tool uninstall korean-taxlaw-mcp
```

## 2. 실행파일 경로 확인

Windows PowerShell:

```powershell
(Get-Command korean-taxlaw-mcp).Source
```

macOS 또는 Linux:

```bash
which korean-taxlaw-mcp
```

일반적인 경로는 다음과 같습니다.

| OS | 경로 |
|---|---|
| Windows | `C:\Users\<사용자>\.local\bin\korean-taxlaw-mcp.exe` |
| macOS / Linux | `~/.local/bin/korean-taxlaw-mcp` |

명령을 찾지 못하면 터미널을 다시 열고 다음 명령을 실행합니다.

```bash
uv tool update-shell
```

## 3. Claude Code 연결

uv tool로 설치한 경우:

```bash
claude mcp add korean-taxlaw -- korean-taxlaw-mcp
claude mcp list
```

명령을 찾지 못하는 Windows 환경에서는 절대경로를 지정합니다.

```powershell
claude mcp add korean-taxlaw -- "C:\Users\<사용자>\.local\bin\korean-taxlaw-mcp.exe"
```

소스 저장소에서 직접 실행하는 경우:

```bash
claude mcp add korean-taxlaw -- uv run --directory /절대경로/korean-taxlaw-mcp korean-taxlaw-mcp
```

## 4. Claude Desktop 수동 연결

설정 파일 경로:

| OS | 경로 |
|---|---|
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |

설정 변경 전 Claude Desktop을 종료하고 기존 파일을 백업하는 것을 권장합니다.

### Windows

```json
{
  "mcpServers": {
    "korean-taxlaw": {
      "command": "C:\\Users\\<사용자>\\.local\\bin\\korean-taxlaw-mcp.exe"
    }
  }
}
```

JSON의 Windows 경로에서는 백슬래시를 `\\`로 작성합니다.

### macOS

```json
{
  "mcpServers": {
    "korean-taxlaw": {
      "command": "/Users/<사용자>/.local/bin/korean-taxlaw-mcp"
    }
  }
}
```

설정을 저장한 뒤 Claude Desktop을 완전히 종료하고 다시 실행합니다.

## 5. 소스에서 실행

코드를 수정하거나 개발에 참여할 때 사용합니다.

```bash
git clone https://github.com/zisu17/korean-taxlaw-mcp.git
cd korean-taxlaw-mcp
uv sync
uv run korean-taxlaw-mcp --help
```

`uv sync`는 호환되는 Python을 확인하고 프로젝트의 `.venv`와 `uv.lock` 기준 의존성을
준비합니다. 가상환경을 직접 활성화할 필요는 없습니다.

Claude Code에 소스 실행 방식으로 등록:

```bash
claude mcp add korean-taxlaw -- uv run --directory /절대경로/korean-taxlaw-mcp korean-taxlaw-mcp
```

## 6. pip + venv 대체 설치

uv를 사용할 수 없는 경우 Python 3.11 이상을 직접 설치한 뒤 사용합니다.

```bash
git clone https://github.com/zisu17/korean-taxlaw-mcp.git
cd korean-taxlaw-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m korean_taxlaw_mcp --help
```

Windows 가상환경 활성화:

```powershell
.venv\Scripts\activate
```

Claude Desktop에는 가상환경 Python의 절대경로를 지정할 수도 있습니다.

```json
{
  "mcpServers": {
    "korean-taxlaw": {
      "command": "/절대경로/korean-taxlaw-mcp/.venv/bin/python",
      "args": ["-m", "korean_taxlaw_mcp"]
    }
  }
}
```

## 7. HTTP 연결

서버 실행:

```bash
korean-taxlaw-mcp --http --port 8000
```

Claude Code 등록:

```bash
claude mcp add --transport http korean-taxlaw http://127.0.0.1:8000/mcp
```

## 8. 함께 사용하면 좋은 MCP

법률·시행령·시행규칙 본문은
[chrisryugj/korean-law-mcp](https://github.com/chrisryugj/korean-law-mcp), 국세청 고유 자료는
`korean-taxlaw-mcp`로 조회하는 구성을 권장합니다. 두 서버를 함께 등록하면 법령 본문과
국세청 해석례·결정례를 서로 다른 출처와 권위 수준으로 확인할 수 있습니다.

## 9. 문제 해결

- `uv` 또는 `korean-taxlaw-mcp`를 찾지 못하면 터미널과 Claude Desktop을 완전히 재시작합니다.
- Claude Desktop 설정의 `command`에는 실제 실행파일의 절대경로를 사용하는 편이 안정적입니다.
- JSON 문법 오류가 없는지, 기존 `mcpServers` 항목을 덮어쓰지 않았는지 확인합니다.
- 연결 후 Claude에게 “사용 가능한 MCP 도구를 확인해줘”라고 요청해 `korean-taxlaw` 등록을 확인합니다.
