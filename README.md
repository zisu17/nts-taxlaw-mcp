# korean-taxlaw-mcp

한국 세법 자료를 출처별로 통합 조회하기 위한 MCP 서버입니다.

현재는 국세청 **국세법령정보시스템**(<https://taxlaw.nts.go.kr>) 원본 조회를 지원하며,
향후 지방세 자료를 별도 도메인으로 추가할 수 있도록 프로젝트 이름과 구조를 확장했습니다.
Python과 FastMCP로 구현했습니다.

- 최신 세법해석례 조회
- 회신·판단·결론 등 상세 본문 구조화
- 문서번호 기반 exact lookup
- 판례·결정례 및 행정 해석기준 검색
- 출처와 근거 유형을 포함한 구조화 응답

기존 `korean-law-mcp`는 법제처 OPEN API 특성상 국세청 해석례의 목록 검색은 가능하지만 상세 본문 조회에는 제한이 있습니다. `korean-taxlaw-mcp`의 현재 국세 도메인은 법제처 미러(`ntsCgmExpc`)를 거치지 않고 국세청 원본을 직접 조회해 문서번호 검색과 상세 본문 조회를 제공합니다.

---

## 1. 지원 데이터

| 영역 | 대상 | 검색 | 문서번호 조회 | 본문 |
|---|---|:---:|:---:|---|
| 세법해석례 | 사전답변, 질의회신(서면질의), 과세기준자문, 고시서면질의 | O | O | 요지·사실관계·질의내용·회신·관련법령 |
| 판례·결정례 | 과세적부, 이의신청, 심사청구, 심판청구, 판례, 헌재 | O | O | 처분개요·청구인 주장·처분청 의견·심리 및 판단·결론 |
| 행정 해석기준 | 국세 기본통칙 | O | - | 조항 본문 |
| 행정 해석기준 | 세법집행기준 | O | - | 조항명·목차 |
| 행정 해석기준 | 국세청 고시 206건, 훈령 143건 | O | - | 메타데이터 |
| 별표·서식 | 법령서식 34,487건 | O | - | 메타데이터·파일 식별자 |

### 확장 방향

- 현재 지원 범위: 국세청 국세법령정보시스템의 국세 자료
- 향후 지원 범위: 지방세 법령해석·심판례 등 지방세 자료
- 확장 원칙: 국세와 지방세의 출처·문서 식별자·권위 수준을 섞지 않고 도메인별로 구분

지방세 도메인이 구현되기 전까지 지방세 자료를 지원한다고 간주하지 않습니다.

### 수록 규모

2026년 8월 실측 기준입니다.

| 데이터 | 건수 |
|---|---:|
| 질의회신 | 132,638 |
| 사전답변 | 5,117 |
| 과세기준자문 | 1,036 |
| 고시서면질의 | 14 |
| 세법해석정비 | 996 |
| 과세적부 | 518 |
| 이의신청 | 1,478 |
| 심사청구 | 22,233 |
| 심판청구 | 71,349 |
| 판례 | 55,860 |
| 헌재 | 355 |

### 지원하지 않는 데이터

| 데이터 | 이유 |
|---|---|
| 법률·시행령·시행규칙 본문 | 국가법령정보센터가 원본이며 `korean-law-mcp`에서 제공 |
| 조세조약 | 법제처 조약 API가 더 안정적이므로 중복 구현하지 않음 |
| 일반 판례·헌재 결정 전체 | 세목이 부여된 조세 사건만 조회 |
| 세법집행기준 조항 본문 | 원본이 연도별 PDF로 배포되어 목차·조항명·PDF 파일 ID까지만 제공 |
| 서식 파일 바이너리 | POST 폼 다운로드 방식으로 안정적인 GET URL이 없음 |
| 감사원 심사청구·납세자보호위원회 심의사례·평가심의사례 | 별도 모듈·액션으로 현재 미구현 |
| 발간책자·세목별요약정보·용어사전·세무일정 | 법적 근거가 아닌 안내자료로 현재 지원하지 않음 |

추가 조사 내용은 [`docs/INVESTIGATION.md`](docs/INVESTIGATION.md)를 참고하세요.

---

## 2. 데이터 출처

현재 제공되는 모든 데이터는 **국세청 국세법령정보시스템**에서 조회합니다.

<https://taxlaw.nts.go.kr>

- 공개 조회 엔드포인트 `POST /action.do` 사용
- 로그인·CAPTCHA·접근제어 우회 없음
- 별도 세션·쿠키·인증키 불필요
- 모든 응답에 원본 추적 정보 포함

```json
{
  "sourceAgency": "국세청",
  "sourceSystem": "국세법령정보시스템",
  "sourceId": "200000000000022584",
  "documentNumber": "서면-2026-법규재산-0119",
  "sourceUrl": "https://taxlaw.nts.go.kr/qt/USEQTA002P.do?ntstDcmId=200000000000022584",
  "retrievedAt": "2026-08-19T13:34:58Z"
}
```

---

## 3. 문서번호 검색

문서번호의 표기 차이를 정규화해 동일 문서를 조회합니다.

```text
서면-2026-법규재산-0119
서면 2026 법규재산 0119
서면2026법규재산0119
서면서면-2026-법규재산-0119
질의회신 서면-2026-법규재산-0119
질의회신서면-2026-법규재산-0119
국세청 서면-2026-법규재산-0119
```

확인된 문서번호 형식은 다음과 같습니다.

| 형식 | 구조 | 예 |
|---|---|---|
| A | `종류-연도-분류-일련` | `서면-2026-법규재산-0119`, `사전-2026-법규소득-0543`, `조심-2025-인-4460` |
| B | `종류-기관-연도-일련` | `적부-국세청-2026-0119`, `이의-광주청-2026-0024`, `심사-부가-2026-0018` |
| C | `기관 부서-일련` | `재정경제부 국제조세협력과-104` |

A와 B는 두 번째 항목이 4자리 연도인지 여부로 구분합니다.

### Exact match 원칙

```text
정확히 일치
→ found: true
→ exactMatch: true
→ document 반환

일치 없음
→ NOT_FOUND
→ similarDocuments 별도 반환
```

일부만 일치하는 문서는 정답으로 반환하지 않습니다.

```text
lookup_tax_document("법규재산-0119")

→ [NOT_FOUND]

similarDocuments:
  · 서면-2026-법규재산-0119
  · 서면-2015-징세-0119
  · 기준-2023-법규부가-0044
  · 적부-국세청-2020-0119
```

`similarDocuments`는 검색 보조 정보이며 요청한 문서로 간주하지 않습니다.

`0119`와 `119`처럼 0 패딩만 다른 경우에는 동일한 문서번호로 처리합니다. 정규화는 조회 후보를 확장하기 위한 용도로만 사용하며, 최종 응답에는 국세청 원본의 문서번호를 그대로 반환합니다.

---

## 4. 키워드 검색

국세법령정보시스템의 실제 검색 결과를 기준으로 검색 문법을 적용합니다.

| 입력 | 건수 | 의미 |
|---|---:|---|
| `["상속"]` | 22,349 | 단일 키워드 |
| `["증여"]` | 22,924 | 단일 키워드 |
| `["상속","증여"]` | 14,913 | AND |
| `["상속 증여"]` | 14,913 | AND |
| `["상속\|증여"]` | 30,360 | OR |
| `["상속"]` + 제외 `["증여"]` | 7,436 | NOT |

MCP에서는 다음과 같이 사용합니다.

```python
{"query": "상속 공동상속주택"}                  # AND
{"query": "상속 증여", "match": "any"}         # OR
{"query": "상속", "exclude": ["증여"]}         # NOT
{"query": '"공동상속주택 소수지분" 양도'}       # 구절 검색
```

검색 시 다음 사항에 주의합니다.

- OR 연산자는 ASCII 파이프 `|`를 사용합니다.
- `¦`(U+00A6)는 OR로 동작하지 않습니다.
- 잘못된 정렬 필드를 전달하면 오류가 아니라 0건이 반환됩니다.
- 서버에서는 실측 검증된 `DCM_RGT_DTM`, `FRS_RGT_DTM`, `SCORE`만 사용합니다.

---

## 5. 설치

Python을 직접 설치하거나 가상환경을 수동으로 만들 필요는 없습니다. [uv](https://docs.astral.sh/uv/)가 필요한 Python과 패키지를 관리합니다.

### 5.1 uv 설치

#### Windows

PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

사내 정책으로 스크립트 실행이 제한된 경우:

```powershell
winget install --id=astral-sh.uv -e
```

#### macOS / Linux

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

설치 후 터미널을 다시 열고 확인합니다.

```bash
uv --version
```

### 5.2 서버 설치

GitHub 주소에서 바로 설치할 수 있습니다.

```bash
uv tool install git+https://github.com/zisu17/korean-taxlaw-mcp.git
```

설치 후 `korean-taxlaw-mcp` 명령을 어느 경로에서든 실행할 수 있습니다.

설치 위치 확인:

```powershell
(Get-Command korean-taxlaw-mcp).Source
```

```bash
which korean-taxlaw-mcp
```

일반적인 설치 경로:

| OS | 경로 |
|---|---|
| Windows | `C:\Users\<사용자>\.local\bin\korean-taxlaw-mcp.exe` |
| macOS / Linux | `~/.local/bin/korean-taxlaw-mcp` |

업데이트:

```bash
uv tool upgrade korean-taxlaw-mcp
```

제거:

```bash
uv tool uninstall korean-taxlaw-mcp
```

### 5.3 소스 설치

코드를 수정하거나 테스트를 실행할 경우 저장소를 내려받아 사용합니다.

```bash
git clone https://github.com/zisu17/korean-taxlaw-mcp.git
cd korean-taxlaw-mcp
uv sync
```

`uv sync`는 다음 작업을 수행합니다.

- `requires-python = ">=3.11"`에 맞는 Python 확인 및 설치
- 프로젝트 디렉터리에 `.venv` 생성
- `uv.lock` 기준 의존성 설치

가상환경을 직접 활성화할 필요는 없습니다. 이후 명령은 `uv run`으로 실행합니다.

git을 사용할 수 없는 환경에서는 GitHub의 **Code > Download ZIP**으로 내려받은 뒤 압축을 풀고 `uv sync`를 실행해도 됩니다.

동작 확인:

```bash
uv run korean-taxlaw-mcp --help
uv run python scripts/compare_with_site.py
```

### 5.4 PATH 확인

설치 직후 `uv` 또는 `korean-taxlaw-mcp` 명령을 찾지 못하면 터미널을 다시 연 뒤 확인합니다.

```powershell
uv tool update-shell
```

Windows에서 절대경로로 확인:

```powershell
& "$env:USERPROFILE\.local\bin\uv.exe" --version
```

macOS / Linux:

```bash
~/.local/bin/uv --version
```

---

## 6. Claude Code 연결

### uv tool로 설치한 경우

```bash
claude mcp add korean-taxlaw -- korean-taxlaw-mcp
```

명령을 찾지 못하면 설치 경로를 확인한 뒤 절대경로를 지정합니다.

```powershell
claude mcp add korean-taxlaw -- "C:\Users\<사용자>\.local\bin\korean-taxlaw-mcp.exe"
```

### 저장소에서 실행하는 경우

```bash
claude mcp add korean-taxlaw -- uv run --directory /절대경로/korean-taxlaw-mcp korean-taxlaw-mcp
```

등록 확인:

```bash
claude mcp list
```

### HTTP 연결

서버 실행:

```bash
korean-taxlaw-mcp --http --port 8000
```

Claude Code 등록:

```bash
claude mcp add --transport http korean-taxlaw http://127.0.0.1:8000/mcp
```

---

## 7. Claude Desktop 연결

설정 파일:

| OS | 경로 |
|---|---|
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |

Claude Desktop에서는 실행파일의 절대경로를 지정하는 편이 안정적입니다.

### Windows

uv tool 설치:

```json
{
  "mcpServers": {
    "korean-taxlaw": {
      "command": "C:\\Users\\<사용자>\\.local\\bin\\korean-taxlaw-mcp.exe"
    }
  }
}
```

저장소에서 실행:

```json
{
  "mcpServers": {
    "korean-taxlaw": {
      "command": "C:\\Users\\<사용자>\\.local\\bin\\uv.exe",
      "args": [
        "run",
        "--directory",
        "C:\\Users\\<사용자>\\korean-taxlaw-mcp",
        "korean-taxlaw-mcp"
      ]
    }
  }
}
```

JSON에서 Windows 경로의 백슬래시는 `\\`로 작성합니다. `/`를 사용해도 됩니다.

### macOS

uv tool 설치:

```json
{
  "mcpServers": {
    "korean-taxlaw": {
      "command": "/Users/<사용자>/.local/bin/korean-taxlaw-mcp"
    }
  }
}
```

저장소에서 실행:

```json
{
  "mcpServers": {
    "korean-taxlaw": {
      "command": "/Users/<사용자>/.local/bin/uv",
      "args": [
        "run",
        "--directory",
        "/Users/<사용자>/korean-taxlaw-mcp",
        "korean-taxlaw-mcp"
      ]
    }
  }
}
```

실제 경로는 다음 명령으로 확인합니다.

```powershell
(Get-Command korean-taxlaw-mcp).Source
```

```bash
which korean-taxlaw-mcp
```

### korean-law-mcp와 함께 사용

법률·시행령·시행규칙 본문은 `korean-law-mcp`, 국세청 고유 자료는 `korean-taxlaw-mcp`에서 조회하는 구성을 권장합니다.

```json
{
  "mcpServers": {
    "korean-law": {
      "command": "npx",
      "args": ["-y", "korean-law-mcp"],
      "env": {
        "LAW_OC": "발급받은-인증키"
      }
    },
    "korean-taxlaw": {
      "command": "C:\\Users\\<사용자>\\.local\\bin\\korean-taxlaw-mcp.exe"
    }
  }
}
```

### pip + venv

uv를 사용할 수 없는 환경에서는 Python 3.11 이상을 직접 설치해 기존 방식으로 실행할 수 있습니다.

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

Claude Desktop에는 가상환경의 Python 절대경로를 지정합니다.

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

---

## 8. 환경변수

모든 항목은 선택 사항이며 기본값만으로 실행할 수 있습니다.

| 변수 | 기본값 | 설명 |
|---|---:|---|
| `NTS_TIMEOUT_MS` | `20000` | 요청 타임아웃(ms) |
| `NTS_RETRIES` | `3` | 재시도 횟수 |
| `NTS_RATE_PER_MIN` | `60` | 분당 요청 한도 |
| `NTS_RATE_BURST` | `20` | 버스트 허용량 |
| `NTS_BODY_LIMIT` | `30000` | 본문 최대 글자수 |
| `NTS_CACHE_MAX` | `600` | 캐시 최대 항목 수 |
| `NTS_USER_AGENT` | Chrome UA | User-Agent |

---

## 9. MCP 도구

총 9개의 도구를 제공합니다.

| 도구 | 용도 |
|---|---|
| `lookup_tax_document` | 문서번호 exact lookup |
| `search_tax_interpretations` | 세법해석례 검색 |
| `search_tax_decisions` | 판례·결정례 검색 |
| `get_tax_document` | 해석례·결정례 본문 조회 |
| `search_tax_guidance` | 기본통칙·집행기준·고시·훈령 검색 |
| `get_tax_guidance` | 통칙·집행기준 특정 조항 조회 |
| `search_tax_forms` | 법령서식·별표 검색 |
| `search_taxlaw` | 전체 영역 통합 검색 |
| `tax_research` | 세무 질의에 대한 층별 근거 수집 |

문서번호를 알고 있다면 `lookup_tax_document`를 먼저 사용합니다.

`get_tax_document`는 해석례와 결정례의 상세 조회를 하나의 도구로 통합합니다. 국세법령정보시스템의 상세 조회 액션이 문서 유형과 관계없이 동일하기 때문에 별도의 상세 조회 도구로 나누지 않습니다.

### 사용 예제

문서번호 조회:

```json
{
  "name": "lookup_tax_document",
  "arguments": {
    "document_number": "서면-2026-법규재산-0119"
  }
}
```

응답 예:

```text
[OK]

found: true
exactMatch: true

서면-2026-법규재산-0119
질의회신 | 양도소득세 | 2026-08-11 | nts_ruling

title:
인구감소지역 내 취득한 분양권이 ’27.1.1.이후 주택으로 전환된 경우 조특법§71의2 적용 여부

relatedLaws:
- 조세특례제한법 제71조의2
- 조세특례제한법 시행령 제68조의2

sections:
- facts
- question
- relatedLawsText
```

판례·결정례 검색:

```json
{
  "name": "search_tax_decisions",
  "arguments": {
    "query": "공동상속주택",
    "type": "court",
    "result": ["국승"],
    "limit": 3
  }
}
```

기본통칙 검색:

```json
{
  "name": "search_tax_guidance",
  "arguments": {
    "kind": "basic_ruling",
    "law_name": "상속세 및 증여세법",
    "query": "상속재산"
  }
}
```

세무 질의 근거 수집:

```json
{
  "name": "tax_research",
  "arguments": {
    "question": "부모가 자녀에게 시가보다 낮은 가격으로 아파트를 양도하면 증여세가 발생하는지"
  }
}
```

---

## 10. 법적 근거 구분

세무 자료는 근거의 성격에 따라 구분해 반환합니다.

| 값 | 의미 |
|---|---|
| `statute` | 법률 |
| `enforcement_decree` | 시행령 |
| `enforcement_rule` | 시행규칙 |
| `nts_ruling` | 국세청 해석례·예규 |
| `nts_guidance` | 기본통칙·집행기준·고시·훈령 |
| `adjudication` | 과세적부·이의신청·심사청구·심판청구 |
| `court_case` | 법원 판례·헌재 결정 |

국세청 예규는 과세관청의 법령해석이며 법원을 구속하지 않습니다. 기본통칙과 집행기준은 내부 집행기준으로 법규 자체는 아닙니다.

---

## 11. 오류 처리

자료가 실제로 존재하지 않는 경우와 원본 서버 문제로 조회하지 못한 경우를 구분합니다.

| 오류 코드 | 의미 | 부존재로 판단 가능 |
|---|---|:---:|
| `NOT_FOUND` | 원본에 일치하는 자료가 없음 | O |
| `DETAIL_NOT_AVAILABLE` | 문서는 있으나 원본에서 본문을 제공하지 않음 | X |
| `UPSTREAM_ERROR` | 국세청 오류·점검·비정상 응답 | X |
| `PARSE_ERROR` | 응답 형식이 예상과 다름 | X |
| `RATE_LIMITED` | 서버 자체 요청 한도 초과 | X |
| `TIMEOUT` | 요청 시간 초과 | X |
| `INVALID_INPUT` | 입력 오류 | X |

오류 응답에는 모델이 확인되지 않은 본문이나 결론을 생성하지 않도록 `guardrail` 정보를 함께 반환합니다.

HTTP 200 응답이라도 점검 페이지 HTML이 반환되거나 본문이 비정상적으로 비어 있으면 일시 장애로 처리하고 재시도합니다.

---

## 12. 요청 제한 및 캐시

국세법령정보시스템에 과도한 요청이 발생하지 않도록 호출량을 제한하고 반복 조회를 줄입니다.

### 요청 제한

- 기본 요청 한도: 분당 60회
- 버스트 허용량: 최대 20회
- `tax_research`처럼 한 작업에서 여러 요청이 이어지는 경우를 고려해 토큰 버킷 방식 사용

### 캐시

| 대상 | 유지 시간 |
|---|---:|
| 검색 결과 | 30분 |
| 문서 본문 | 24시간 |
| 통칙·집행기준·고시·훈령 | 12시간 |
| 법령 목록 | 7일 |

### 중복 요청 처리

동일한 요청이 동시에 들어오면 실제 국세법령정보시스템 조회는 한 번만 수행하고 결과를 공유합니다.

### HTTP 연결 재사용

`httpx`의 keep-alive 연결 풀을 사용합니다.

---

## 13. 면책사항

- 이 서버는 국세청 원문 검색과 구조화를 위한 데이터 접근 계층이며 법률적 판단이나 세무 자문을 제공하지 않습니다.
- 해석례와 결정례는 개별 사안의 사실관계를 기준으로 한 판단입니다.
- 국세청 예규는 과세관청의 법령해석으로 법원을 구속하지 않습니다.
- 기본통칙과 집행기준은 내부 집행기준이며 법규가 아닙니다.
- 개정 법령은 적용시점을 별도로 확인해야 합니다.
- 데이터의 정확성과 최신성은 국세법령정보시스템의 갱신 상태를 따릅니다.
- 법적 효력이 필요한 판단에는 국세법령정보시스템 원문을 확인해야 합니다.
- 실제 신고·불복 등 법적 효력이 있는 행위는 세무사·변호사 등 자격 있는 전문가의 검토가 필요합니다.

---


## 라이선스

MIT

데이터 출처 고지는 [`NOTICE`](NOTICE)를 참고하세요.
