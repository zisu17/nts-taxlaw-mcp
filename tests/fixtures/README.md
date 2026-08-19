# 테스트 fixture

이 디렉터리에는 국세법령정보시스템의 **실제 응답**을 그대로 저장한 JSON 이 들어간다.
합쳐서 약 8MB 라서 **저장소에 커밋하지 않는다**(`.gitignore` 처리).

이 서버를 설치해서 쓰기만 한다면 이 파일들은 필요 없다. 테스트를 돌릴 때만 받는다.

```bash
python scripts/refresh_fixtures.py           # 없는 것만 받기 (약 8MB)
python scripts/refresh_fixtures.py --force   # 전부 다시 받기
pytest                                       # 165건
```

fixture 가 없으면 `tests/test_parsers.py` 와 `tests/test_tools.py` 는 이유를 밝히고
건너뛴다. 나머지 테스트(문서번호 정규화·검색문법·라우팅)는 fixture 없이 돈다.

## 왜 저장이 필요한가

두 층으로 회귀를 잡기 위해서다.

| 층 | 무엇을 잡는가 |
|---|---|
| fixture 기반 (`pytest`) | **우리 파서의 회귀.** 네트워크 없이 돌고, 사이트 장애가 빌드를 깨뜨리지 않는다 |
| 실서버 (`NTS_LIVE=1 pytest`) | **원본 개편.** 응답 구조·코드표·검색 문법이 바뀌었는지 |

fixture 만 있으면 사이트가 바뀐 걸 모르고, 실서버 테스트만 있으면 남의 공개 서비스를
매 실행마다 두드리게 된다. 그래서 둘 다 둔다.

## 재생성했을 때 내용이 달라지는가

- **상세 응답**(`detail_*.json`): 고정된 `ntstDcmId` 로 받으므로 같은 문서가 온다.
  스크립트가 문서번호까지 대조해서 다르면 실패로 알린다.
- **검색 응답**(`search_*.json`): 최신 N 건이라 문서가 바뀐다. 테스트가 건수 대신
  **구조**(필드 존재·타입·매핑)만 검증하므로 무방하다.
- **코드표**(`codes.json`): 바뀌면 `scripts/refresh_codes.py` 가 차이를 알려준다.
