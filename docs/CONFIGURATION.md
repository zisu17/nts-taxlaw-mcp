# 설정 가이드

모든 설정은 선택 사항이며 기본값만으로 실행할 수 있습니다.

## 요청 보호

국세와 지방세는 서로 다른 원본 서버를 사용하므로 호출량을 출처별로 계산합니다.

- 기본 한도: 출처별 분당 60회, 순간 버스트 20회
- 429와 일시적인 원본 서버 오류는 지수 백오프로 기본 3회 재시도
- 같은 요청이 동시에 들어오면 실제 원본 조회는 한 번만 수행

외부 기관의 WAF와 정책은 예고 없이 바뀔 수 있으므로 차단 가능성을 0으로 보장할 수는 없습니다.
보호 한도는 프로세스별이므로 같은 IP에서 여러 인스턴스를 실행하면 실제 호출량이 합산됩니다.

## 환경변수

사이트별 설정이 공통 설정보다 우선합니다.

```text
NTS_* / OLTA_*  >  TAXLAW_*  >  기본값
```

| 항목 | 공통 | 국세 전용 | 지방세 전용 | 기본값 |
|---|---|---|---|---:|
| 타임아웃(ms) | `TAXLAW_TIMEOUT_MS` | `NTS_TIMEOUT_MS` | `OLTA_TIMEOUT_MS` | `20000` |
| 재시도 횟수 | `TAXLAW_RETRIES` | `NTS_RETRIES` | `OLTA_RETRIES` | `3` |
| 재시도 대기(ms) | `TAXLAW_RETRY_BASE_MS` | `NTS_RETRY_BASE_MS` | `OLTA_RETRY_BASE_MS` | `300` |
| 분당 요청 한도 | `TAXLAW_RATE_PER_MIN` | `NTS_RATE_PER_MIN` | `OLTA_RATE_PER_MIN` | `60` |
| 버스트 | `TAXLAW_RATE_BURST` | `NTS_RATE_BURST` | `OLTA_RATE_BURST` | `20` |
| 본문 길이 상한 | `TAXLAW_BODY_LIMIT` | `NTS_BODY_LIMIT` | `OLTA_BODY_LIMIT` | `30000` |
| User-Agent | `TAXLAW_USER_AGENT` | `NTS_USER_AGENT` | `OLTA_USER_AGENT` | Chrome UA |
| 캐시 항목 수 | `TAXLAW_CACHE_MAX` | — | — | `600` |

예를 들어 지방세 요청만 분당 20회로 낮추려면 다음과 같이 설정합니다.

```bash
OLTA_RATE_PER_MIN=20
```

공통 타임아웃은 10초로 두고 국세만 30초로 늘릴 수도 있습니다.

```bash
TAXLAW_TIMEOUT_MS=10000
NTS_TIMEOUT_MS=30000
```

숫자가 아니거나 허용 범위보다 작은 값은 무시하고 다음 후보 또는 기본값을 사용합니다.
`NTS_CACHE_MAX`는 이전 버전과의 호환을 위해 계속 인식하지만 새 설정에는
`TAXLAW_CACHE_MAX`를 사용하세요.

## 캐시

인메모리 캐시는 두 출처가 공유하지만 키에 출처를 포함해 결과를 구분합니다.

| 대상 | 유지 시간 |
|---|---:|
| 검색 결과 | 30분 |
| 문서 본문 | 24시간 |
| 기본통칙·집행기준·고시·훈령 | 12시간 |
| 법령 목록 등 정적 자료 | 7일 |

캐시는 프로세스를 다시 시작하면 초기화됩니다. 최대 항목 수를 넘으면 만료된 항목을 먼저 제거하고,
그다음 가장 오래 사용하지 않은 항목을 제거합니다.
