# 테스트 fixture

이 디렉터리에는 국세법령정보시스템의 **실제 응답**을 압축한 `*.json.gz`가 들어간다.
원본 약 8MB를 약 1.5MB로 줄여 CI와 개발 환경에서 같은 테스트를 재현한다.

이 서버를 설치해서 쓰기만 한다면 이 파일들은 필요 없다. 테스트에서만 사용된다.

```bash
python scripts/refresh_fixtures.py           # 없는 것만 받기
python scripts/refresh_fixtures.py --force   # 원본 응답으로 전부 갱신
pytest                                       # 기본: 네트워크 없는 테스트
```

fixture가 유실되면 `tests/test_parsers.py`와 `tests/test_tools.py`는 이유를 밝히고
건너뛴다. CI에서는 fixture가 모두 존재하는지 별도로 확인한다.

## 왜 저장이 필요한가

두 층으로 회귀를 잡기 위해서다.

| 층 | 무엇을 잡는가 |
|---|---|
| fixture 기반 (`pytest`) | **우리 파서의 회귀.** 네트워크 없이 돌고, 사이트 장애가 빌드를 깨뜨리지 않는다 |
| 실서버 (`NTS_LIVE=1 pytest`) | **원본 개편.** 응답 구조·코드표·검색 문법이 바뀌었는지 |

fixture 만 있으면 사이트가 바뀐 걸 모르고, 실서버 테스트만 있으면 남의 공개 서비스를
매 실행마다 두드리게 된다. 그래서 둘 다 둔다.

## 재생성했을 때 내용이 달라지는가

- **상세 응답**(`detail_*.json.gz`): 고정된 `ntstDcmId`로 받으므로 같은 문서가 온다.
  스크립트가 문서번호까지 대조해서 다르면 실패로 알린다.
- **검색 응답**(`search_*.json.gz`): 최신 N건이라 문서가 바뀐다. 테스트가 건수 대신
  **구조**(필드 존재·타입·매핑)만 검증하므로 무방하다.
- **코드표**(`codes.json.gz`): 바뀌면 `scripts/refresh_codes.py`가 차이를 알려준다.
