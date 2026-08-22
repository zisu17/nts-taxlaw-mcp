# 상세 설치 및 연결 가이드

README의 빠른 시작으로 해결되지 않거나 직접 설정하려는 사용자를 위한 문서입니다.
이 서버는 데스크톱 앱에서 로컬 STDIO MCP로 실행합니다.

## 1. 데스크톱 앱에 설치 요청하기

설치와 설정을 직접 하지 않아도 됩니다. 사용하는 앱에서 새 대화를 열고 아래 요청문을
붙여 넣으세요.

### Claude Desktop

Claude Desktop 대화창에 다음 요청문을 입력합니다.

```text
korean-taxlaw-mcp를 이 컴퓨터에 로컬 MCP로 설치해줘.

현재 사용 중인 Claude Desktop 앱의 로컬 STDIO MCP 서버로 등록하고,
이름은 korean-taxlaw로 지정해줘.

저장소: https://github.com/zisu17/korean-taxlaw-mcp

uv가 없으면 먼저 설치해. 그런 다음 uv tool로 패키지를 설치하고 실행 파일의 절대경로를
찾아 Claude Desktop 설정에 넣어줘. 기존 MCP 설정은 그대로 두고, 끝나면 앱 재시작 방법을
알려준 뒤 연결도 확인해줘.
```

### ChatGPT 데스크톱 앱의 Codex

ChatGPT 데스크톱 앱의 Codex 대화창에 다음 요청문을 입력합니다.

```text
korean-taxlaw-mcp를 이 컴퓨터에 로컬 MCP로 설치해줘.

현재 사용 중인 ChatGPT 데스크톱 앱의 Codex에서 쓸 로컬 STDIO MCP 서버로
등록하고, 이름은 korean-taxlaw로 지정해줘.

저장소: https://github.com/zisu17/korean-taxlaw-mcp

uv가 없으면 먼저 설치해. 그런 다음 uv tool로 패키지를 설치하고 실행 파일의 절대경로를
찾아 ChatGPT 데스크톱 앱의 Codex MCP 설정에 넣어줘. 기존 MCP 설정은 그대로 두고,
끝나면 앱 재시작 방법을 알려준 뒤 연결도 확인해줘.
```

## 2. uv tool로 직접 설치하기

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

## 3. 실행 파일 경로 확인하기

Windows PowerShell:

```powershell
(Get-Command korean-taxlaw-mcp).Source
```

macOS 또는 Linux:

```bash
which korean-taxlaw-mcp
```

실행 파일은 보통 아래 경로에 있습니다.

| OS | 경로 |
|---|---|
| Windows | `C:\Users\<사용자>\.local\bin\korean-taxlaw-mcp.exe` |
| macOS / Linux | `~/.local/bin/korean-taxlaw-mcp` |

명령을 찾지 못하면 터미널을 다시 열고 다음 명령을 실행합니다.

```bash
uv tool update-shell
```

## 4. 데스크톱 앱에 직접 연결하기

### Claude Desktop

설정 파일 경로:

| OS | 경로 |
|---|---|
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |

설정 변경 전 Claude Desktop을 종료하고 기존 파일을 백업하세요. 이미 `mcpServers` 항목이
있다면 지우지 말고 `korean-taxlaw` 항목만 추가합니다.

Windows:

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

macOS:

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

### ChatGPT 데스크톱 앱의 Codex

1. ChatGPT 데스크톱 앱에서 **Settings → MCP servers**를 엽니다.
2. **Add server**를 선택합니다.
3. 이름에 `korean-taxlaw`, 연결 방식에 **STDIO**를 입력합니다.
4. command에는 3절에서 확인한 실행 파일의 절대경로를 넣습니다.
5. 저장한 뒤 **Restart**를 선택합니다.

연결 후 대화창에서 `/mcp`를 입력하면 등록된 서버를 확인할 수 있습니다.

## 5. 소스에서 실행하기

코드를 수정하거나 개발에 참여할 때 사용합니다.

```bash
git clone https://github.com/zisu17/korean-taxlaw-mcp.git
cd korean-taxlaw-mcp
uv sync
uv run korean-taxlaw-mcp --help
```

`uv sync`는 호환되는 Python을 확인하고 프로젝트의 `.venv`와 `uv.lock` 기준 의존성을
준비합니다. 가상환경을 직접 활성화할 필요는 없습니다.

소스에서 실행한 서버를 등록하려면 다음 값을 사용합니다.

- command: `uv`의 절대경로
- args: `run`, `--directory`, `/절대경로/korean-taxlaw-mcp`, `korean-taxlaw-mcp`

Claude Desktop에서는 `command`와 `args`를 설정 파일에 넣고, ChatGPT 데스크톱 앱에서는
MCP 서버 추가 화면에서 같은 값을 입력합니다.

## 6. pip + venv로 설치하기

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

이 방식으로 연결할 때는 가상환경 Python의 절대경로를 command로 지정하고, args에는
`-m`, `korean_taxlaw_mcp`를 넣습니다.

Claude Desktop 설정 예시:

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

## 7. korean-law-mcp와 함께 사용하기

법률·시행령·시행규칙 본문은
[chrisryugj/korean-law-mcp](https://github.com/chrisryugj/korean-law-mcp), 국세청 고유 자료는
`korean-taxlaw-mcp`로 조회합니다. 두 서버를 함께 등록하면 법령 본문과 국세청
해석례·결정례를 출처와 권위 수준에 맞춰 나눠 볼 수 있습니다.

## 8. 문제 해결

- `uv` 또는 `korean-taxlaw-mcp`를 찾지 못하면 터미널과 데스크톱 앱을 완전히 재시작합니다.
- 설정의 command에는 실제 실행 파일의 절대경로를 넣습니다.
- Claude Desktop 설정을 직접 수정했다면 JSON 문법과 기존 `mcpServers` 항목을 확인합니다.
- ChatGPT 데스크톱 앱에서는 **Settings → MCP servers**에서 서버가 활성화됐는지 확인합니다.
- 연결 후 앱에 “사용 가능한 MCP 도구를 확인해줘”라고 요청해 `korean-taxlaw` 등록을 확인합니다.
