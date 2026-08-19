# korean-law-mcp 와의 중복 분석

대상 버전: `korean-law-mcp` v4.12.1 (MIT, <https://github.com/chrisryugj/korean-law-mcp>)

## 1. 기존 구현이 국세청 자료를 어디까지 다루는가

저장소를 직접 읽고 확인한 사실:

| 항목 | 확인 내용 | 위치 |
|---|---|---|
| 데이터 원천 | 전부 법제처 국가법령정보센터 OPEN API. 국세청 해석례도 법제처 미러(`ntsCgmExpc`)로 받는다 | `NOTICE`, `src/lib/api-client.ts` |
| 국세청 해석례 검색 | `search_decisions(domain="nts")` → `searchNtsInterpretations` | `src/tools/unified-decisions.ts:82` |
| 국세청 해석례 **본문** | **미지원.** `[NOT_SUPPORTED]` 를 반환한다 | `src/tools/customs-interpretations.ts:138-155` |
| `ntstDcmId` 매핑 | 불가하다고 명시 | 같은 곳 |
| `taxlaw.nts.go.kr` 직접 호출 | **판례 본문 폴백 경로에만** 존재. `action.do` + `ASIQTB002PR01` 사용 | `src/tools/precedents.ts:274-300` |
| 노출 도구 수 | 내부 ~64개 → 9개만 노출(`V3_EXPOSED`) | `src/lib/tool-profiles.ts` |

원문 인용:

> `[NOT_SUPPORTED]` 국세청 법령해석은 법제처 OPEN API에서 본문 조회를 제공하지 않습니다.
> … 법제처 OPEN API target `ntsCgmExpc` 는 `lawSearch.do` 목록 조회만 지원합니다.
> … (상세링크의 ntstDcmId는 법제처 일련번호와 다른 별도 식별자라 자동 변환 불가.)

**즉 기존 구현의 공백은 정확히 이것이다**: 국세청 해석례의 목록은 되지만 본문은 안 되고,
문서번호로 특정 문서를 집을 수도 없다. 이 서버가 그 공백을 메운다.

### 이미 발견해 둔 자산

`precedents.ts:274` 의 `fetchTaxlawAction()` 은 이 프로젝트가 전면적으로 쓰는 것과
같은 프로토콜을 이미 쓰고 있다.

```typescript
const body = new URLSearchParams({
  actionId: "ASIQTB002PR01",
  paramData: JSON.stringify({ dcmDVO: { ntstDcmId } }),
})
```

다만 거기서는 **법제처 판례 본문이 비었을 때의 마지막 폴백**으로만 쓰이고,
`ntstDcmId` 를 법제처 HTML 뷰어의 iframe 리다이렉트를 3단 추적해 겨우 얻어낸다.
그 값을 직접 검색으로 얻을 수 있다는 점은 활용되지 않았다 — 이 프로젝트는 그
`ntstDcmId` 를 **검색 결과의 `DOC_ID` 로 바로 얻어** 폴백이 아닌 정면 경로로 쓴다.

## 2. 기능별 분류

| 기능 | 분류 | 근거 |
|---|---|---|
| 법률 본문 | `REUSE_KOREAN_LAW_MCP` | 법제처가 원본. 조문·연혁·시점 조회가 이미 성숙 |
| 시행령·시행규칙 본문 | `REUSE_KOREAN_LAW_MCP` | 동일 |
| 법령 연혁·시점 비교 | `REUSE_KOREAN_LAW_MCP` | `time_travel`, `applicable_law` 등 전용 도구 존재 |
| 조례·자치법규 | `REUSE_KOREAN_LAW_MCP` | 국세청 범위 밖 |
| 조세조약 | `REUSE_KOREAN_LAW_MCP` | 법제처 조약 API 가 더 안정적. NTS 쪽 이점 없음 |
| 일반 판례·헌재 결정 | `REUSE_KOREAN_LAW_MCP` | 법제처가 원본. 조세 사건만 필요할 때 이 서버가 세목으로 좁혀 준다 |
| 법제처 법령해석 | `REUSE_KOREAN_LAW_MCP` | 법제처가 원본 |
| 조세심판원 결정 **목록** | `HYBRID` | 법제처에도 있으나 NTS 는 세목·귀속연도·결정유형 필터가 붙는다 |
| 국세청 해석례 **검색** | `HYBRID` | 법제처 미러도 되지만 NTS 가 최신·필터·건수 우위 |
| **국세청 해석례 본문** | `NTS_DIRECT_REQUIRED` | 법제처가 제공하지 않음 (`[NOT_SUPPORTED]`) |
| **문서번호 exact lookup** | `NTS_DIRECT_REQUIRED` | 법제처 일련번호와 문서번호 체계가 다르다 |
| **과세적부·이의신청·심사청구** | `NTS_DIRECT_REQUIRED` | 국세청 고유. 법제처에 없다 |
| **국세 기본통칙** | `NTS_DIRECT_REQUIRED` | 국세청 고유 |
| **세법집행기준** | `NTS_DIRECT_REQUIRED` | 국세청 고유 |
| **국세청 고시·훈령** | `NTS_DIRECT_REQUIRED` | 법제처 행정규칙과 수록 범위·형태가 다르다 |
| 국세 법령서식 | `NTS_DIRECT_REQUIRED` | 국세청이 서식·별표를 별도 관리 |
| 세법 → 통칙 → 집행기준 → 예규 연결 | `HYBRID` | 법령 층은 법제처, 그 아래 층은 NTS. `tax_research` 가 이 경계를 명시한다 |

## 3. 경계 처리 방식

`tax_research` 는 법령 층을 **조회하지 않고**, 조회하지 않는다는 사실과 어디서 봐야
하는지를 응답에 남긴다.

```json
{
  "layer": "법률",
  "authorityLevel": "statute",
  "provider": "external",
  "status": "not_covered",
  "message": "법률 본문은 이 서버(국세청 원본)의 범위가 아닙니다. 법제처 데이터를 쓰는 korean-law-mcp (get_law_text / search_law) 로 확인하세요. 확인 대상: 조세특례제한법제71조의2"
}
```

이렇게 두면 모델이 "법령을 확인했다"고 착각하지 않는다. 층을 조용히 빼면 모델은
그 층이 없다고 여기거나 스스로 채워 넣는다.

## 4. 재사용한 설계 (코드 복사가 아니라 판단의 재사용)

`korean-law-mcp` 는 MIT 라이선스이므로 코드 재사용에 제약이 없다. 다만 이 프로젝트는
언어가 다르고(TypeScript → Python) 업스트림도 다르므로 코드를 옮기지 않고 **설계 판단**만
가져왔다. 그 판단들은 그 저장소가 실측으로 얻은 것이라 출처를 밝힌다.

| 가져온 판단 | 원 위치 | 이 프로젝트의 적용 |
|---|---|---|
| 부존재와 조회 실패를 다른 오류 코드로 분리 | `src/lib/errors.ts` `UPSTREAM_NO_DATA` vs `NOT_FOUND` | `NOT_FOUND` vs `UPSTREAM_ERROR`/`DETAIL_NOT_AVAILABLE` (`errors.py`) |
| 대괄호 라벨을 기계 독자와의 계약으로 씀 | `noResultHint()` 의 `[NOT_FOUND]` 접두 | 모든 도구 응답 첫 토큰이 `[OK]`/`[NOT_FOUND]`/… |
| 응답에 "추측하지 말라"는 지시문을 싣는다 | 같은 곳 | `GUARDRAIL` 사전 (`errors.py`) |
| 고정창 대신 토큰버킷 | `src/lib/rate-limit.ts` | `rate_limit.py` |
| 만료 우선 + LRU 축출 캐시 | `src/lib/cache.ts` | `cache.py` (+ 동일 키 요청 병합 추가) |
| 지수 백오프를 왕복 시간에 맞춰 짧게(1s→0.3s) | `fetch-with-retry.ts` `DEFAULT_RETRY_DELAY` 주석 | `RETRY_BASE_SECONDS = 0.3` |
| 200 + HTML 은 점검 페이지로 보고 재시도 | `classifyOkBody()` | `action_client.py` |
| 도구 폭발 억제 (64개 → 9개 노출) | `src/lib/tool-profiles.ts` | 처음부터 통합 도구 9개 |
| `action.do` + `ASIQTB002PR01` 프로토콜 | `src/tools/precedents.ts:274` | 전면 채택 후 확장(검색·통칙·집행기준·고시·훈령·서식) |

라이선스·고지: `NOTICE` 참조.

## 5. 함께 쓸 때의 역할 분담

```
질문: "상속세및증여세법 제35조 관련 국세청 예규와 심판례를 찾아줘"

korean-law-mcp   → 상속세및증여세법 제35조 본문, 시행령 위임 조문, 개정 연혁
korean-taxlaw-mcp   → 제35조 관련 기본통칙·집행기준, 국세청 예규, 심판·판례
```

두 서버를 같은 클라이언트에 등록하는 방법은 README 7절에 있다.
