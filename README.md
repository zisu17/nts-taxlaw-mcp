# korean-taxlaw-mcp

국세·지방세 법령정보시스템의 원문을 직접 조회하는 한국 세법 MCP 서버입니다.

- 국세청 세법해석례·판례·결정례·기본통칙 검색
- 행정안전부 지방세 유권해석과 지방세 심판·판례 검색
- 문서번호로 정확한 문서를 찾아 본문까지 조회
- 출처 URL과 근거 유형을 포함한 구조화 응답

> 법률·시행령·시행규칙 본문은 제공하지 않습니다. 해당 자료는 국가법령정보센터 기반의
> [chrisryugj/korean-law-mcp](https://github.com/chrisryugj/korean-law-mcp)를 함께 사용하는
> 구성을 권장합니다.

## 조회 가능한 자료

| 구분 | 출처 | 주요 자료 |
|---|---|---|
| 국세 | [국세법령정보시스템](https://taxlaw.nts.go.kr) | 질의회신, 사전답변, 과세기준자문, 심사·심판·판례, 기본통칙·집행기준·고시·훈령, 서식 |
| 지방세 | [지방세 법령정보시스템](https://www.olta.re.kr) | 행정안전부·법제처 유권해석, 조세심판원·감사원·법원·헌재 결정례 |

취득세·재산세·자동차세 등은 **지방세** 도구를, 양도소득세·법인세·부가가치세 등은
**국세** 도구를 사용합니다.

## 빠른 시작

### Claude Code나 Codex에 설치 요청하기

다음 문장을 그대로 요청하면 설치와 연결 확인을 맡길 수 있습니다.

```text
korean-taxlaw-mcp를 설치하고 모든 프로젝트에서 사용할 수 있도록
사용자 범위에 korean-taxlaw라는 MCP로 등록해줘.
저장소: https://github.com/zisu17/korean-taxlaw-mcp
설치 후 연결 테스트까지 해줘.
```

### 직접 설치하기

[uv](https://docs.astral.sh/uv/)를 설치한 뒤 실행합니다.

```bash
uv tool install git+https://github.com/zisu17/korean-taxlaw-mcp.git
```

Claude Code에 등록:

```bash
claude mcp add --scope user korean-taxlaw -- korean-taxlaw-mcp
```

Codex에 등록:

```bash
codex mcp add korean-taxlaw -- korean-taxlaw-mcp
```

Claude Code의 `--scope user`와 Codex의 기본 사용자 설정은 현재 프로젝트에 한정되지 않고
모든 프로젝트에 적용됩니다. Codex 설정은 같은 컴퓨터의 ChatGPT 데스크톱 앱, Codex CLI,
IDE 확장에서 공유됩니다.

설치가 끝나면 사용 중인 데스크톱 앱을 완전히 종료한 뒤 다시 실행하세요. 운영체제별 설치,
수동 등록, HTTP 연결, 문제 해결은 [설치 가이드](docs/INSTALLATION.md)를 참고하세요.

## 사용 예

MCP가 연결된 대화 창에서 일반 문장으로 요청하면 됩니다.

```text
국세청에서 "공동상속주택" 관련 세법해석례를 찾아줘.

서면-2026-법규재산-0119 전문과 원문 링크를 보여줘.

취득세 신탁 관련 행정안전부 유권해석과 심판례를 찾아줘.

부동산세제과-1794(2026.6.9.)호 회신 내용을 보여줘.
```

문서번호를 알고 있다면 키워드 검색보다 문서번호 조회를 요청하는 것이 빠르고 정확합니다.

## 문서

- [사용 가이드](docs/USAGE.md) — 도구 선택, 문서번호 조회, 응답과 오류 해석
- [설정 가이드](docs/CONFIGURATION.md) — 요청 보호, 캐시, 환경변수
- [설치 가이드](docs/INSTALLATION.md) — 운영체제·클라이언트별 설치와 문제 해결
- [개발 가이드](docs/DEVELOPMENT.md) — 개발 환경과 테스트
- [지원 범위 조사](docs/INVESTIGATION.md) — 원본 시스템 분석과 지원·미지원 데이터

## 알아두기

- 원본 시스템에서 조세 자료로 분류한 문서만 조회합니다.
- 일부 자료는 원본 제공 방식에 따라 본문 대신 메타데이터나 파일 식별자만 반환될 수 있습니다.
- 이 서버는 원문 검색과 구조화를 위한 도구이며 세무 자문을 제공하지 않습니다. 신고·불복 등
  법적 효과가 있는 판단에는 현행 법령과 원문을 확인하고 전문가의 검토를 받으세요.

## 라이선스

MIT License. 데이터 출처 고지는 [`NOTICE`](NOTICE)를 참고하세요.
