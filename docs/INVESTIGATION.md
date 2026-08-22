# 국세법령정보시스템 조사 결과

조사 시점: 2026-08-19. 사이트 메뉴가 아니라 **실제 HTTP 요청**을 재현해 확인한 내용이다.

## 1. 국세청 사이트 구조

`taxlaw.nts.go.kr` 의 화면(`/qt/USEQTA001M.do` 등)은 얇은 껍데기다. 데이터 요청은
모두 단일 엔드포인트로 간다.

```
POST https://taxlaw.nts.go.kr/action.do
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
X-Requested-With: XMLHttpRequest

actionId=<액션ID>&paramData=<JSON 문자열>
```

응답:

```json
{ "status": "SUCCESS", "message": null, "data": { "<액션ID>": <결과> } }
```

근거: `/js/common/common.js` 의 `Req.doAction()`(2418행 부근)이 모든 화면의 공통 통로다.

```javascript
_req.doAction = function(paramActionId, paramData, ...) {
  let parameter = { actionId: paramActionId, paramData: JSON.stringify(paramData) }
  $.ajax({ url: '/action.do', data: parameter, type: 'POST', dataType: "JSON", ... })
}
```

HTML 을 긁지 않고 액션을 직접 호출하면 화면 개편의 영향을 덜 받는다. 이 서버는
HWP→HTML 변환 결과인 문서 본문만 HTML 로 파싱한다.

### 접근 조건

| 항목 | 결과 |
|---|---|
| 세션/쿠키 | **불필요** (jsessionid 없이 200) |
| 로그인·인증키 | **불필요** |
| CSRF 토큰 | 없음 |
| CAPTCHA | 공개 조회 경로에 없음 |
| Referer | 없어도 동작하나 예의상 화면 URL 을 보냄 |
| User-Agent | 브라우저 UA 사용 |

로그인·CAPTCHA·접근제어 우회는 하지 않았고, 공개 조회 액션만 사용한다.

---

## 2. 자료 목록

`list_endpoint` 는 사람이 볼 화면, `action` 은 실제 데이터 통로다.

| category | sub_category | search | doc_no | full_text | list_endpoint | action (search / detail) | identifier | important_fields | priority | notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 세법해석례 | 사전답변 (01) | O | O | O | `/qt/USEQTA001M.do?ntstDcmClCd=01` | `ASIPDI002PR01` / `ASIQTB002PR01` | `ntstDcmId` | 요지·질의·회신·관련법령 | **P0** | 5,117건 |
| 세법해석례 | 질의회신 (02) | O | O | O | `…ntstDcmClCd=02` | 동일 | `ntstDcmId` | 동일 | **P0** | 132,638건 (최대) |
| 세법해석례 | 과세기준자문 (03) | O | O | O | `…ntstDcmClCd=03` | 동일 | `ntstDcmId` | 동일 | **P0** | 1,036건 |
| 세법해석례 | 고시서면질의 (04) | O | O | O | `…ntstDcmClCd=04` | 동일 | `ntstDcmId` | 동일 | P1 | 14건 |
| 세법해석례 | 전체 해석례 | O | O | O | `/qt/USEQTJ001M.do` | 동일 (01~04 합) | — | — | **P0** | 통합 화면 |
| 세법해석례 | 세법해석정비 | O | △ | O | `/qt/USEQTE001M.do` | `ASIPDI002PR01` (`dcmClCdCtl=["002_01"]`) | `ntstDcmId` | 정비사유 | P2 | 996건 |
| 세법해석례 | 법제처 해석례 (41) | △ | △ | △ | `/qt/USEQTM001M.do` | `ASIBGE004MR03` | — | — | P3 | 법제처가 원본 → 중복 |
| 세법해석례 | 자주찾는 쟁점별 사례 (13) | △ | X | △ | `/qt/USEQTH001M.do` | 별도 모듈 | — | — | P3 | 편집 큐레이션 |
| 세법해석례 | 주요 해석사례 (21) | △ | X | △ | `/qt/USEQTI001M.do` | 별도 모듈 | — | — | P3 | 큐레이션 |
| 판례·결정례 | 과세적부 (05) | O | O | O | `/pd/USEPDA001M.do?ntstDcmClCd=05` | `ASIPDI002PR01` / `ASIQTB002PR01` | `ntstDcmId` | 결정결과·귀속연도·판단 | **P0** | 518건 |
| 판례·결정례 | 이의신청 (06) | O | O | O | `…=06` | 동일 | `ntstDcmId` | 동일 | **P0** | 1,478건 |
| 판례·결정례 | 심사청구 (07) | O | O | O | `…=07` | 동일 | `ntstDcmId` | 동일 | **P0** | 22,233건 |
| 판례·결정례 | 심판청구 (08) | O | O | O | `…=08` | 동일 | `ntstDcmId` | 동일 | **P0** | 71,349건 |
| 판례·결정례 | 판례 (09) | O | O | O | `…=09` | 동일 | `ntstDcmId` | 하급심 사건번호 | **P0** | 55,860건 |
| 판례·결정례 | 헌재 (10) | O | O | O | `…=10` | 동일 | `ntstDcmId` | 병합사건 | P1 | 355건 |
| 판례·결정례 | 감사원 심사청구 (11) | △ | X | ? | `/pd/USEPDM001M.do` | 별도 모듈 | — | — | P2 | 조사 완료·미구현 |
| 판례·결정례 | 주요 대법원 판결 (20) | △ | X | ? | `/pd/USEPDG001M.do` | 별도 모듈 | — | — | P3 | 09 의 큐레이션 |
| 행정해석기준 | 국세 기본통칙 | O | — | O | `/st/USESTD001M.do` | `ASISTD001MR01` → `MR03` → `MR02` | `ntstBscId`+`rgtYr`+`ntstExrBaseSn` | 조항명·본문 | **P0** | 15개 법령 |
| 행정해석기준 | 세법집행기준 | O | — | △ | `/st/USESTE002M.do` | `ASISTE001MR03` → `MR02` | `ntstBscId`+`ntstPlcnBkId`+`rgtYr` | 조항명·PDF fleId | **P0** | 15책, 본문은 PDF |
| 행정해석기준 | 국세청 고시 | O | — | △ | `/st/USESTF001M.do` | `ASISTF001MR01` (`ntarClCd=01`) | `ntarBscId` | 공포일·소관부서 | P1 | 206건 |
| 행정해석기준 | 국세청 훈령 | O | — | △ | `/st/USESTG001M.do` | `ASISTF001MR01` (`ntarClCd=03`) | `ntarBscId` | 동일 | P1 | 143건 |
| 행정해석기준 | 최신 훈령·고시 | O | — | △ | `/st/USESTI002M.do` | 위와 동일(정렬만) | — | — | P2 | 별 기능 아님 |
| 행정해석기준 | 조문별 개정세법해설 | △ | X | ? | `/st/USESTH001M.do` | 별도 모듈 | — | — | P2 | 미구현 |
| 별표·서식 | 법령서식 | O | — | X | `/af/USEAFB001M.do` | `ASIAFB001MR02` → `MR01` | `ntstBscId`+`ntstAtFrmlSn` | 서식명·개정일·fleId | P1 | 34,487건 |
| 별표·서식 | 별표 / 훈령서식 / 자주찾는서식 | O | — | X | `/af/USEAFA001M.do` 등 | 같은 액션 계열 | 동일 | 동일 | P2 | 파라미터만 다름 |
| 법령 | 조세법령·일반법령 | O | — | O | `/st/USESTA001M.do` | `ASISTZ001MR01` 등 | `ntstBscId` | — | **제외** | 법제처가 원본 |
| 법령 | 조세조약 | O | — | O | `/st/USESTC001M.do` | 별도 모듈 | — | — | **제외** | 법제처가 더 안정적 |
| 기타 | 납세자보호위원회 심의사례 (14) | △ | X | ? | `/bg/USEBGF001M.do` | 별도 모듈 | — | — | P2 | 조사 완료·미구현 |
| 기타 | 평가심의사례 | △ | X | ? | `/bg/USEBGI001M.do` | 별도 모듈 | — | — | P3 | 미구현 |
| 기타 | 발간책자 / 세목별요약정보 | △ | X | ? | `/el/USEELA001M.do`, `/bg/USEBGG001M.do` | 별도 모듈 | — | — | P3 | 안내자료 — 오인 위험 |
| 기타 | 용어사전 / 세무일정 | △ | X | ? | `/st/USESTJ001M.do`, `/cm/USECMC001M.do` | 별도 모듈 | — | — | P3 | 상담 근거 아님 |
| 기타 | 세법해석 질의안내 / 공지사항 | X | X | — | `/br/USEBRD001M.do` | — | — | — | P3 | 정적 안내 |

범례: O 지원 · △ 가능하나 미구현 · X 불가 · — 해당없음

---

## 3. 검색 액션 상세 — `ASIPDI002PR01`

세법해석례와 판례·결정례가 **같은 액션**을 쓴다. 문서구분과 컬렉션만 다르다.

```json
{
  "startCount": 1,                       // 페이지 번호(1부터). 오프셋 아님
  "viewCount": 50,                       // 페이지 크기
  "schDtBase": "DCM_RGT_DTM",            // 또는 FRS_RGT_DTM(최초등록일)
  "bltnStrtDt": "20260101",              // YYYYMMDD, 빈 문자열 허용
  "bltnEndDt": "",
  "collectionName": "question,question_gr",   // 01~04 / precedent,precedent_gr = 05~10
  "dcmClCdCtl": ["001_02"],              // 001_<문서구분>. 세법해석정비는 002_01
  "icldVcbCtl": ["상속", "공동상속주택"],   // 포함 낱말 = AND
  "exclVcbCtl": ["증여"],                 // 제외 낱말 = NOT
  "ntstTlawClCdList": ["307"],           // 세목 필터
  "sortField": "DCM_RGT_DTM/DESC"
}
```

선택 필터: `dcsThanPrdcOrgnClCtl`(생산기관), `prtsDcsTypeClCtl_2`(결정유형),
`prtsAttrYrCtl`(귀속연도).

### 응답 구조

```
top[0].categoryMap.SUB_ID_CATEGORY  → [{name:"001_02", count:"132638"}, …]  문서구분별 건수
body[].dcm                          → 검색 행 (대문자 스네이크 필드 71개)
wnSessionUuid[]                     → 화면 추적용. 조회에 불필요
```

### 검색 행의 주요 필드

| 필드 | 의미 |
|---|---|
| `DOC_ID` | 문서 ID = 상세 조회의 `ntstDcmId` |
| `NTST_DCM_DSCM_CNTN` | 문서번호 |
| `TTL` | 제목 |
| `GIST_CNTN` | 요지 |
| `NTST_DCM_CL_CD` / `LBL1_TTL` | 문서구분 코드 / 이름 |
| `NTST_TLAW_CL_CD` / `NTST_TLAW_CL_NM` | 세목 |
| `NTST_DCM_DCS_CL_CD` / `NTST_DCM_DCS_CL_NM` | 결정유형 |
| `NTST_DCM_SRCS_ORGN_CL_CD` | 생산기관 |
| `NTST_DCM_RGT_DT` | 등록일 |
| `ATTR_YR` | 귀속연도 |
| `DOCU_NO_STR1` | **문서번호 색인** — 하이픈형과 압축형을 함께 담는다 |
| `RFRN_QUT_NTST_DCM_ID` | 인용 문서 ID |
| `SCORE` / `RANK` | 적합도 |

`DOCU_NO_STR1` 실측값:

```
서면-2026-법규재산-0119 서면-2026-법규재산-0119 서면2026법규재산0119 20260811 202608 2026 08 11
```

사이트가 두 표기를 모두 색인해 두므로, 정규형 하나로도 압축형 입력이 잡힌다.
검색 결과에서는 일치 구간이 `<!HS>…<!HE>` 로 감싸여 오므로 **비교 전에 반드시 제거**해야 한다.

### 검색 연산

세법해석 01~04 전체 대상, 반환 건수:

| 입력 | 건수 | 결론 |
|---|---|---|
| `["상속"]` | 22,349 | — |
| `["증여"]` | 22,924 | — |
| `["상속","증여"]` | 14,913 | 배열 원소끼리 **AND** |
| `["상속 증여"]` | 14,913 | 원소 내부 공백도 **AND** |
| `["상속\|증여"]` | 30,360 | ASCII 파이프가 **OR** (22,349+22,924−14,913 = 30,360 정확히 일치) |
| `["상속¦증여"]` | 14,913 | broken bar(U+00A6)는 **OR 아님** — AND 와 동일 |
| `["상속 OR 증여"]` | 0 | `OR` 낱말은 무효 |
| `["상속"]` + excl `["증여"]` | 7,436 | **NOT** (22,349−14,913 = 7,436 정확히 일치) |

### 정렬

| 값 | 결과 |
|---|---|
| `DCM_RGT_DTM/DESC`, `DCM_RGT_DTM/ASC` | 정상 |
| `FRS_RGT_DTM/DESC` | 정상 |
| `SCORE/DESC` | 정상 (적합도) |
| `RANK/DESC`, `RANK` | **total 0, status SUCCESS** ← 조용한 0건 함정 |

허용되지 않는 정렬 필드는 오류가 아니라 0건을 낳는다. 이 서버는 검증된 세 필드만 쓴다.

### 페이지네이션

`startCount` 는 **1부터 시작하는 페이지 번호**다. `viewCount=5` 로 `startCount` 1·2 를
호출하면 서로 다른 5건이 온다. 오프셋으로 오해하면 2페이지 요청에 1페이지가 돌아온다.

---

## 4. 상세 조회 액션 — `ASIQTB002PR01`

```json
{ "dcmDVO": { "ntstDcmId": "200000000000022584" } }
```

문서구분 01~10 **전부** 이 액션 하나로 처리된다(실측 확인). 그래서 MCP 도구도
`get_tax_document` 하나로 합쳤다.

### 응답 구조

| 키 | 내용 |
|---|---|
| `dcmDVO` | 메타데이터 (문서번호·제목·요지·회신·세목·결정유형·등록일 등) |
| `dcmHwpEditorDVOList` | 본문. `dcmFleTy=="html"` 항목의 `dcmFleByte` 가 **본문 HTML**, `"hwp"` 는 원본 첨부 |
| `dcmRltnStttList` | 관련법령 (`ntstTextNm` + `bsafRfkNo1`=법령ID + `bsafRfkNo2`=조문ID) |
| `dcmRfrnPrtsList`, `dcmQutPrtsList` | 인용·참조 판례 |
| `trilPsagList` | 심급 경과 |

### dcmDVO 주요 필드

| 필드 | 의미 |
|---|---|
| `ntstDcmDscmCntn` | 문서번호 |
| `ntstDcmTtl` | 제목 |
| `ntstDcmGistCntn` | **요지** |
| `ntstDcmCntn` | **회신·답변 본문** (본문 HTML 이 아니라 이 필드에 있다) |
| `ntstDcmMatrCntn` | 키워드 (`;` 구분) |
| `ntstDcmClCd` / `ntstTlawClCd` / `ntstDcmDcsClCd` | 문서구분 / 세목 / 결정유형 |
| `ntstDcmSrcsOrgnClCd` | 생산기관 |
| `ntstDcmRgtDt` / `frsRgtDtm` | 등록일 / 최초등록 |
| `attrYr` | 귀속연도 |
| `ntstPrdgHpnnNoCntn` | 하급심 사건번호 (판례) |
| `stttInfpClCd` | 공개구분 |
| `fleId`, `ntstWpFleId` | 첨부 파일 ID |

### 본문 절 구조 (문서 종류별 실측)

본문은 최상위 번호 제목으로 나뉘고, 종류마다 다르다.

| 문서 종류 | 절 구성 |
|---|---|
| 질의회신·사전답변·기준자문 | 1.사실관계 / 2.질의내용 / 3.관련법령 및 관련사례 (회신은 `ntstDcmCntn`) |
| 과세적부 | 1.사실관계 및 과세예고통지 내용 / 2.청구인들 주장 / 3.통지관서 의견 / 4.심리 및 판단 / 5.결론 |
| 이의신청 | 1.사실관계 및 처분내용 / 2.**신청법인의** 주장 / 3.조사청 의견 / 4.심리 및 판단 / 5.결론 |
| 심사청구 | 1.처분개요 / 2.청구인 주장 / 3.처분청 의견 / 4.심리 및 판단 / 5.결론 |
| 심판청구 | 1.처분개요 / 2.청구인 주장 및 처분청 의견 / 3.심리 및 판단 / 4.결 론 |
| 판례 | 번호 절 구조가 아님 (상고이유별 서술 + 결론) |

파싱할 때 유의할 점은 두 가지다.

1. 주체 뒤에 조사가 붙는다 — "신청법인**의** 주장". 정규식이 이를 놓치면 절이 빠진다.
2. 절 안에서 번호가 **다시 1부터** 매겨진다. 이의신청 실측: "2. 신청법인의 주장" 아래에
   "1)~6)" 이 붙는다. 번호 연속성만 믿으면 중첩 항목을 절로 오인한다.
   → 어휘로 먼저 걸러내고, 이미 받은 절보다 번호가 큰 것만 받는 방식으로 해결했다.

본문 크기는 최대 **1.4MB**(심사청구 일부)까지 나온다. 반드시 자르고, 자른 사실을 표시해야 한다.

---

## 5. 행정 해석기준 액션

```
ASISTZ001MR01 {"ntstSysClCd":"01"}                  → 세법 31개 (ntstBscId 확보)
ASISTD001MR01 {}                                    → 기본통칙 보유 법령 15개
ASISTD001MR03 {"ntstBscId":…}                       → 기본통칙 개정연도 목록
ASISTD001MR02 {"ntstBscId":…, "rgtYr":"2024"}       → 조항 + 본문 (bscExrDVOList)
ASISTE001MR03 {"ntstBscId":…, "ntstPlcnBkId":…}     → 집행기준 연도 + PDF fleId
ASISTE001MR02 {"ntstBscId":…, "rgtYr":"2024"}       → 집행기준 조항 목차 (exeBaseDVOList)
ASISTF001MR01 {"ntarClCd":"01"|"03", "ntstSjtClCd":"All", "searchKeyword":"",
               "pageIndex":1, "recordCountPerPage":10}  → 고시(01)·훈령(03), notcFeldDVOList
ACMCMA001MR01 {"cmCodeDVOList":[{"cmnClsfCd":"19378"}, …]}  → 공통코드표
```

주의:

- **`ntstSjtClCd:"All"` 을 빼면 고시·훈령이 0건**으로 온다. 사이트가 초기화 시 넣는 값이다.
- **집행기준은 `ntstPlcnBkId` 가 필요**하다. 이 목록은 조회 액션이 없고
  `/js/common/common_st.js` 의 `exeBaseStttList` 에 정적으로 박혀 있어 상수로 옮겼다.
- **기본통칙은 조항 본문이 함께 오지만 집행기준은 목차만 온다**(483건 전부
  `ntstTextCntn` 공백). 집행기준 본문은 연도별 PDF 로만 배포된다.

## 6. 서식 액션

```
ASIAFB001MR02 {}                                     → 서식 보유 법령 1,748개
ASIAFB001MR01 {"searchNtstBscId":"stttAll",          → 서식 34,487건 (stttFrmlDVOList)
               "searchFrmlNm":"상속세",
               "pageIndex":1, "recordCountPerPage":20}
```

주의: 파라미터는 `ntstBscId` 가 아니라 **`searchNtstBscId`** 다. 틀리면 0건이 온다.

파일 다운로드는 `/downloadStorFile.do` 로 가는데, 이는 `actionId`+`data`+`fileType` 을
POST 로 받아 **서버가 렌더링**해 주는 인쇄 경로다. 안정적인 GET URL 이 없어
바이너리 제공은 범위에서 제외했다.

---

## 7. 코드표 (`ACMCMA001MR01`)

| 그룹 | 내용 | 값 |
|---|---|---|
| 19378 | 문서구분 | 01 사전답변, 02 질의회신, 03 과세기준자문, 04 고시서면질의, 05 과세적부, 06 이의신청, 07 심사청구, 08 심판청구, 09 판례, 10 헌재, 11 감사, 13 쟁점, 14 납보위, 20 주요대법원판결, 21 주요세법해석사례, 31 해석정비, 32 해석유보, 41 법제처해석례 |
| 19387 | 세목 | 301 국세기본, 302 국세징수, 303 법인세, 305 종합소득세, 306 부가가치세, 307 양도소득세, 308 상속증여세, 309 조세특례, 310 국제조세, 311 종합부동산세, 312 원천세, 313 소비세, 314 주세, 315 교육세 (101~117·201~216 은 법령명, 401+ 는 약칭) |
| 19425 | 생산기관 | 01 국세청, 02 기획재정부, 03 법제처, 04 조세심판원, 05 감사원, 51 지방법원, 52 행정법원, 53 고등법원, 54 대법원, 55 헌법재판소, 99 기타 |
| 19375 | 결정유형 | 01 각하, 02 채택, 03 불채택, 04 일부채택, 05 기각, 06 경정, 07 인용, 08 일부인용, 09 재조사, 10 국승, 11 국패, 12 일부국패, 13 일부국승, 14 합헌, 15 위헌, 16 헌법불합치, 19 수범, 20 지적, 22 유죄, 23 일부유죄, 24 무죄, 99 기타 |
| 15917 | 공개구분 | 01 공개, 02 비공개, 03 공개연기, 04 수록제외, 05 대내외공개, 06 대내공개 |
| 19377 | 사건분류 | 01 행정, 02 민사, 03 형사 |

문서구분별로 허용되는 결정유형·생산기관이 다르다(`/qt/USEQTA001M.do` 인라인 JS 실측):

```
결정유형  05:[01,02,03,04,05]  06·07·08:[01,05,07,08,99]
          09:[01,10,11,12,99,22,23,24]  10:[01,14,15,16,99]
생산기관  01~04:[01,02,03]  05:[01,99]  06·07:[01,05,07,08,99]
          08:[01,04,05]  09:[51,52,53,54]
```

이 코드표는 상수로 고정하고, 원본과 어긋나면 즉시 알 수 있도록 테스트로 대조한다
(`tests/test_parsers.py::test_code_tables_match_constants`,
`tests/test_live.py::test_code_tables_still_match_upstream`).

---

## 8. 문서번호 배열 (실측 표본: 문서구분별 60건)

| 레이아웃 | 형태 | 관측된 3번째 마디 어휘 |
|---|---|---|
| A | `종류-연도-분류-일련` | 사전/서면/기준: 법규재산·법규법인·법규소득·법규부가·법규국조·법규기본·부동산·소득·법인·부가·소비·원천·자본거래·국제세원 / 고시: 소비 / 조심: 광·구·부·서·소·인·전·중 / 법원: 두·누·구합·구단·가합·가단 / 헌재: 헌바·헌가·헌마·헌아 |
| B | `종류-기관-연도-일련` | 적부: 국세청·서울청·부산청·광주청 / 이의: 서울청·중부청·인천청·대전청·광주청·대구청·부산청 / 심사: 부가·소득·법인·증여·상속·양도·종부·기타 (세목이 들어간다) |
| C | `기관 부서-일련` | 재정경제부·기획재정부 + 국제조세협력과·재산세제과·금융세제과·조세정책과 등 |

A 와 B 는 **두 번째 마디가 4자리 연도인지**로 갈린다. 이 구분이 없으면
`적부-국세청-2026-0119` 의 `국세청` 을 기관 접두로 오인해 잘라낸다.

기타 변형:

- 헌재 병합사건: `헌법재판소-2009-헌바-35,82`, `헌법재판소-2008-헌가-27,2010헌바153,365`
- 법원 지원 표기: `서울고등법원(인천)-2025-누-10162`
- 구 기재부 회신: 공백 1개 + 하이픈 1개 (`재정경제부 국제조세협력과-104`)

---

## 9. 실패 모드 정리

| 증상 | 원인 |
|---|---|
| 검색 0건인데 status SUCCESS | 정렬 필드 무효(`RANK/DESC`) 또는 컬렉션 불일치 |
| 고시·훈령 0건 | `ntstSjtClCd:"All"` 누락 |
| 서식 0건 | `ntstBscId` 를 썼음 (→ `searchNtstBscId`) |
| 집행기준 연도 목록 빈 배열 | `ntstPlcnBkId` 누락 |
| 문서번호 비교 실패 | `<!HS>`/`<!HE>` 마커 미제거 |
| 2페이지가 1페이지와 동일 | `startCount` 를 오프셋으로 계산 |
| 해석례+결정례 동시 검색 0건 | 두 컬렉션을 한 요청에 섞음 |
| 200 응답인데 JSON 파싱 실패 | 점검·차단 페이지(HTML) |

---

# 지방세 법령정보시스템 조사 결과

조사 시점: 2026-08-20. 대상: 한국지방세연구원(KILF) **지방세 법령정보시스템**
<https://www.olta.re.kr>. 국세청과 마찬가지로 메뉴가 아니라 **실제 HTTP 요청**을
재현해 확인한 내용이다.

## 1. 지방세 사이트 구조

국세청은 `action.do` 단일 JSON 디스패처지만, 이 사이트는 **검색이 목록 화면 자체로
가는 form POST** 이고 응답은 서버가 렌더링한 HTML 이다. 그래서 HTML 파싱을 피할 수
없고, 파서를 `olta_parse.py` 한 곳에 몰아두었다.

```
POST /explainInfo/<목록화면>.do
Content-Type: application/x-www-form-urlencoded; charset=UTF-8

menuNo, upperMenuId   ← 화면 식별자 (필수. 아래 §5 함정 참조)
collection            ← 자료 종류
searchType            ← 1(통합검색) | 2(문서번호검색)
query                 ← 검색어 (연산자 & | ! [] {} 지원)
taxTitleStr           ← 세목 코드를 `|` 로 이어 붙인 문자열
startCount            ← **오프셋** (0, 10, 20 …). 국세청의 페이지 번호와 다르다
startDate / endDate   ← YYYY.MM.DD
sort=RANK, searchField=ALL, range=ALL, detailSearchIsOnOff=on
```

세션·쿠키·CSRF 토큰이 필요하지 않다(실측: 쿠키 없이 200 + 정상 결과).
페이지의 `<meta name="csrfToken" content="">` 는 비어 있고 검증되지 않는다.

## 2. 자료 목록

| kind | 자료 | collection | 목록 | 상세 | 규모(취득세 검색) |
|---|---|---|---|---|---|
| `interpretation` | 행정안전부 유권해석 | `authoritative` | `/explainInfo/authoInterpretationList.do` | `/explainInfo/authoInterpretationDetail.do?num=` | 2,203 |
| `moleg` | 법제처 유권해석 | `legal` | `/explainInfo/lawInterpretationList.do` | `/explainInfo/lawInterpretationDetail.do?num=` | 340 |
| `tribunal` | 조세심판원 심판결정례 | `screen` | `/explainInfo/judgeDecisionList.do` | `/explainInfo/judgeDecisionDetail.do?num=` | 18,867 |
| `audit` | 감사원 심사결정례 | `evaluation` | `/explainInfo/dlbDcnList.do` | `/explainInfo/dlbDcnDetail.do?num=` | 1,348 |
| `court` | 법원 판례 | `sentencing_supreme` | `/explainInfo/decisionList.do` | `/explainInfo/detailView/decisionDtlView.do?num=&relationshipNum=&srchWrd=` | 3,098 |
| `constitutional` | 헌법재판소 결정례 | `ordinance` | `/explainInfo/constitutionDcnList.do` | `/explainInfo/constitutionDcnDetail.do?num=` | 116 |

전체 규모(질의 없음): 행안부 유권해석 3,379 · 조세심판원 25,167 · 감사원 1,952 ·
법원 판례 5,821 · 헌재 214 · 법제처 888.

미구현(조사만 완료):

| 자료 | 경로 | 판단 |
|---|---|---|
| 지방세 관계 법령 | `/ordinance/importantList.do` | 법제처가 원본 → korean-law-mcp 중복 |
| 지방자치단체 조례 | `/ordinance/rulesListAPI.do` | 법제처 자치법규가 원본 → 중복 |
| 지방세관계법 운영예규 | `/ordinance/basicGeneralPrincipleList.do` | 국세 기본통칙 대응물. 진입 파라미터 미확정 |
| 시가표준액 | `/cop/bbs/selectBoardList.do?bbsId=…214` | 게시판 첨부 파일 형태 |
| 전자도서관·세목별 요약 | `/ebook/catalist.do`, `/itemInfo/taxItemInfoList.do` | 법적 근거 아닌 안내자료 |

## 3. 세목 코드 (22개)

상세검색 폼의 체크박스에서 실측했다. 필터는 **`taxTitleStr`** 에 `|` 로 이어 붙여 보낸다.

```
11100 취득세      11200 등록면허세    11300 레저세        11400 지방소비세
12100 지역자원시설세 12200 지방교육세  21000 담배소비세     22000 주민세
23000 지방소득세   24000 재산세       25000 자동차세       30000 기타
30030 농어촌특별세  30040 세외수입     30050 국세          30070 지방세기본
30080 지방세징수   30110 종합부동산세   30154 체납처분      30155 포상금
30156 조세범      30650 개별소비세
```

필터가 실제로 동작하는지 집합으로 확인했다(query=신탁, 행안부 유권해석):

| 필터 | 건수 |
|---|---|
| 없음 | 171 |
| 취득세(11100) | 116 |
| 재산세(24000) | 33 |
| 취득세\|재산세 | 149 |

`116 + 33 = 149` 로 정확히 맞는다.

## 4. 검색 연산 (실측 확정)

행안부 유권해석 기준.

| 입력 | 건수 | 의미 |
|---|---|---|
| `취득세` | 2,203 | — |
| `신탁` | 171 | — |
| `취득세 신탁` | 122 | 공백이 **AND** |
| `취득세&신탁` | 122 | 명시적 AND — 공백과 동일 |
| `취득세\|신탁` | 2,250 | **OR** |
| `취득세!신탁` | 2,079 | **NOT** |
| `[취득세 신탁]` | 59 | 구문검색(100% 일치) |

국세청과 달리 **공백이 그대로 AND** 이고, OR 는 ASCII 파이프다(국세청도 파이프지만
국세청 쪽은 `¦`(U+00A6)가 AND 로 동작하는 함정이 따로 있다).

## 5. 주의사항

| 증상 | 원인 |
|---|---|
| 법원 판례 검색이 **HTTP 500** | `menuNo`·`upperMenuId` 누락. 다른 종류는 없어도 되지만 법원 판례만 필수 |
| 법원 판례 상세가 **HTTP 500** | `srchWrd` 누락. **빈 값이어도 존재해야** 열린다 |
| 세목 필터가 무동작 | 체크박스 이름 `ch_deatail_search_taxlist` 를 보냈다. 실제 파라미터는 `taxTitleStr` |
| 2페이지가 1페이지와 동일 | `startCount` 를 페이지 번호로 계산했다. 이 사이트는 **오프셋**(0,10,20) |
| 문서 번호가 전부 `0` | 같은 `<a>` 의 `href="javascript:void(0);"` 를 팝업 인수로 잡았다. 함수명이 `…PopUp` 인 것만 봐야 한다 |
| 세목이 파싱 안 됨 | 검색어가 세목명과 겹치면 `<!HS>취득세<!HE>` 하이라이트 마커가 끼어든다 |
| 알림 스크립트가 행으로 잡힘 | 페이지 상단 JS 템플릿에도 `<li><p>` 문자열이 있다. `<span class="part">` 앵커가 필요하다 |
| 조문 인용이 `제 106 조제 1 항` | 사이트가 글자 단위로 태그를 감싼다. 태그 제거 후 공백을 다시 붙여야 한다 |
| `httpx` AsyncClient 가 죽음 | `data=` 에 튜플 리스트를 넘겼다(`Attempted to send an sync request…`). dict 로 줘야 한다 |

## 6. 목록 행 마크업

```html
<li>
  <p><span class="part">재산세</span>부동산세제과-1794(2026.6.9.)호 (2026.06.09)</p>
  <p class="tt"><a … onclick="AddViewDocument('제목','javascript:authoritativePopUp(60099135)');">제목</a></p>
  <p class="txt"><a …>요지</a></p>
</li>
```

심판·판례는 머리 `<p>` 끝에 `<span class="label">기각</span>`(결정유형)이 붙고,
법원 판례는 팝업 인수가 둘이다 — `decisionDtlpopUp(20002922, 60099210, null)`
(첫째=`num`, 둘째=`relationshipNum`).

## 7. 상세 화면 구조

```
부동산세제과-1794(2026.6.9.)호(20260609) 재산세    ← 문서번호(등록일) 세목
공장용지 중 부대시설용 건축물의 부속토지에 대한 …      ← 제목
관계법령    「지방세법 시행규칙」제52조
답변요지    제조시설은 건축물 외 토지에 정착하여 …
본문
  < 질의요지 >  …
  < 회신내용 >  …
```

절 이름은 자료 종류마다 다르다: 유권해석은 답변요지/질의요지/회신내용,
심판·판례·감사원은 요지/이유. 화면 장식 문구("자료보안을 위해 비실명자료로만 인쇄되며…",
"다운로드", "프린트")는 본문에서 제거해야 한다.

## 8. 문서번호 배열

국세와 달리 **생산 부서명 + 일련번호**로 구성된다.

| 예 | 구성 |
|---|---|
| `부동산세제과-1794(2026.6.9.)호` | 부서-일련(시행일)호 |
| `지방소득소비세제과-1683(2026.6.15.)호` | 동일 |
| `부동산세제과-1050호` | 날짜 없음 |
| `부동산세제과-924` | '호' 없음 |
| `지방세정팀-2924`, `지방세운영-4924` | 구 부서명 |
| `행정안전부100` | 하이픈 없음 |
| `조심2025지0592` | 심판결정례 |
| `대법원2025두35102` | 법원 판례 |
| `감심2024-630` | 감사원 |
| `2019헌바107` | 헌재 |

**문서번호 검색(`searchType=2`)은 일련번호 부분일치다.** `1794` → 1건이지만
`924` → 4건(`부동산세제과-924`, `지방세운영-4924`, `지방세정팀-2924` …).
부서명을 함께 넣으면 0건이 온다. 그래서 조회는 일련번호로 하고, **반환된 문서번호가
입력과 정확히 같을 때만** exact 로 인정한다. 부서명 접미(`과`/`팀`)는 표기가 흔들려
비교에서 떼어낸다.
