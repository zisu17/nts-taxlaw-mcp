"""FastMCP 도구 등록.

도구를 자료 종류마다 하나씩 만들면 20~30개가 되고, 그러면 모델이 어느 것을 불러야
할지 헷갈려 정확도가 떨어진다. 그래서 **도메인 파라미터 기반 통합 도구** 9개로 묶었다.

상세 조회는 사이트 액션이 문서 종류와 무관하게 하나(``ASIQTB002PR01``)이므로
``get_tax_document`` 하나로 합쳤다 — 사용자가 '적부'가 결정례인지 해석례인지 알아야
할 이유가 없다(권장안의 get_tax_interpretation / get_tax_decision 을 대체한다).
"""

from __future__ import annotations

import asyncio
import functools
import json
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from . import SERVER_NAME, __version__
from .codes import DECISION_RESULT, TAX_TYPE, TAX_TYPE_ALIAS
from .doc_number import looks_like_document_number
from .domains.documents import (
    DECISION_CLASSES,
    INTERPRETATION_CLASSES,
    get_document,
    search_documents,
)
from .domains.forms import search_forms
from .domains.guidance import (
    get_basic_rulings,
    get_execution_standards,
    search_guidance,
)
from .domains.lookup import lookup_by_document_number
from .errors import ErrorCode, NtsError, not_found
from .research import tax_research as run_tax_research
from .routing import route_query

mcp = FastMCP(
    name=SERVER_NAME,
    version=__version__,
    instructions=(
        "국세청 국세법령정보시스템(taxlaw.nts.go.kr) 원본을 직접 조회하는 서버입니다. "
        "국세청 고유 자료(예규·불복결정례·기본통칙·집행기준·고시·훈령·서식)만 담당하고, "
        "법률·시행령·시행규칙 본문은 다루지 않습니다(법제처 기반 korean-law-mcp 사용). "
        "문서번호를 알고 있으면 항상 lookup_tax_document 를 먼저 쓰세요. "
        "조회 결과에 없는 내용은 절대 추측·생성하지 마세요."
    ),
)

# ─────────────────────────────────────────────────────────────────────────────
# 응답 포장
# ─────────────────────────────────────────────────────────────────────────────

_INTERPRETATION_TYPE_CODE = {
    "advance": "01",        # 사전답변
    "written": "02",        # 질의회신(서면질의)
    "advisory": "03",       # 과세기준자문
    "notice_written": "04", # 고시서면질의
}

_DECISION_TYPE_CODE = {
    "pre_assessment": "05",  # 과세적부
    "objection": "06",       # 이의신청
    "review": "07",          # 심사청구
    "tribunal": "08",        # 심판청구
    "court": "09",           # 판례
    "constitutional": "10",  # 헌재
}

SEARCH_SEMANTICS = (
    "공백으로 구분한 낱말은 AND, match='any' 는 OR(내부적으로 ASCII 파이프), "
    "exclude 는 NOT 으로 사이트에 전달됩니다."
)


def _ok(payload: dict[str, Any]) -> str:
    """성공 응답.

    첫 줄에 ``[OK]`` 같은 대괄호 라벨을 두는 것은 기계 독자를 향한 계약이다 —
    모델은 산문 속 완곡한 유보는 흘려보내지만 첫 토큰의 라벨은 놓치지 않는다.
    """
    return "[OK]\n" + json.dumps(payload, ensure_ascii=False, indent=2)


def _envelope_errors(fn):
    """``NtsError`` 를 **구조화된 본문**으로 되돌린다.

    예외를 그대로 올리면 FastMCP 가 ``ToolError`` 로 감싸면서 메시지 문자열만 남기고
    ``detail`` 을 버린다. 그런데 이 서버에서 가장 중요한 정보가 바로 그 detail 안에 있다 —
    ``similarDocuments``(정답이 아닌 유사 문서)와 ``guardrail``(본문을 지어내지 말라는 지시).
    그것들이 클라이언트에 닿지 않으면 환각 방지 설계가 무력해진다.

    그래서 오류도 첫 토큰이 ``[NOT_FOUND]`` 같은 라벨인 정상 본문으로 돌려준다.
    라벨이 곧 기계 독자와의 계약이므로 상태 표시로 충분하다.
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> str:
        try:
            return await fn(*args, **kwargs)
        except NtsError as exc:
            return f"[{exc.code}]\n" + json.dumps(exc.envelope(), ensure_ascii=False, indent=2)

    return wrapper


def _resolve_tax_types(value: str | list[str] | None) -> tuple[list[str], list[str]]:
    """세목 입력(이름·별칭·코드) → 코드 목록. 못 알아본 값은 조용히 버리지 않고 알린다."""
    if not value:
        return [], []
    raw_list = [value] if isinstance(value, str) else list(value)
    codes: list[str] = []
    unresolved: list[str] = []
    for raw in raw_list:
        s = str(raw).strip()
        if not s:
            continue
        if s in TAX_TYPE:
            codes.append(s)
            continue
        alias = TAX_TYPE_ALIAS.get(s) or TAX_TYPE_ALIAS.get(s.replace(" ", ""))
        if alias:
            codes.append(alias)
            continue
        by_name = next((c for c, n in TAX_TYPE.items() if n == s or s in n), None)
        if by_name:
            codes.append(by_name)
            continue
        unresolved.append(s)
    return list(dict.fromkeys(codes)), unresolved


def _resolve_decision_results(names: list[str] | None) -> tuple[list[str], list[str]]:
    if not names:
        return [], []
    by_label = {label: code for code, label in DECISION_RESULT.items()}
    codes = [by_label[name] for name in names if name in by_label]
    unresolved = [name for name in names if name not in by_label]
    return list(dict.fromkeys(codes)), list(dict.fromkeys(unresolved))


def _merge_law(query: str | None, law: str | None, article: str | None) -> str | None:
    """law/article 을 키워드에 합친다. 사이트는 관련법령을 본문 색인으로도 잡는다."""
    parts = [p.strip() for p in (query, law, article) if p and p.strip()]
    return " ".join(parts) if parts else None


# ─────────────────────────────────────────────────────────────────────────────
# 1. lookup_tax_document
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="lookup_tax_document",
    description=(
        "문서번호로 국세청 문서를 **정확히 일치하는 것만** 찾아 본문까지 반환한다. "
        "세법해석례(사전답변·질의회신·과세기준자문·고시서면질의)와 판례·결정례"
        "(과세적부·이의신청·심사청구·심판청구·판례·헌재)를 자동 판별한다. "
        "'서면-2026-법규재산-0119', '서면 2026 법규재산 0119', '서면2026법규재산0119', "
        "'질의회신 서면-2026-법규재산-0119' 처럼 표기가 달라도 같은 문서로 정규화한다. "
        "정확히 일치하는 문서가 없으면 NOT_FOUND 를 반환하고, 번호가 일부 겹치는 문서는 "
        "similarDocuments 로 분리해 준다(정답이 아님). 문서번호를 아는 경우 항상 이 도구를 먼저 쓸 것."
    ),
)
@_envelope_errors
async def lookup_tax_document(
    document_number: Annotated[
        str,
        Field(
            min_length=2,
            description=(
                "문서번호. 표기 편차를 자동 정규화한다. 적부-국세청-2026-0119 처럼 "
                "기관이 번호에 포함된 형식도 지원."
            ),
        ),
    ],
    include_full_text: Annotated[bool, Field(description="본문 전문 포함 여부")] = True,
    body_limit: Annotated[
        int | None, Field(ge=500, le=200_000, description="본문 최대 글자수(기본 30000)")
    ] = None,
) -> str:
    outcome = await lookup_by_document_number(
        document_number, include_full_text=include_full_text, body_limit=body_limit
    )
    if outcome["found"]:
        return _ok({"input": document_number, **outcome})

    raise NtsError(
        ErrorCode.NOT_FOUND,
        f"문서번호 '{document_number}' 와 정확히 일치하는 문서를 "
        "국세법령정보시스템에서 찾지 못했습니다.",
        hints=[
            "문서번호 표기를 원문 그대로 다시 확인하세요.",
            "연도·일련번호를 바꿔가며 확인하려면 search_tax_interpretations 또는 "
            "search_tax_decisions 를 쓰세요.",
            *(
                ["아래 similarDocuments 는 번호 일부가 겹치는 별개 문서이며 요청한 문서가 아닙니다."]
                if outcome.get("similarDocuments")
                else []
            ),
        ],
        detail={
            "normalizedDocumentNumber": outcome["normalizedDocumentNumber"],
            "inputInterpretation": outcome["inputInterpretation"],
            "exactMatch": False,
            "similarDocuments": outcome.get("similarDocuments", []),
            "triedQueries": outcome["triedQueries"],
            "searchedDomains": outcome["searchedDomains"],
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. search_tax_interpretations
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="search_tax_interpretations",
    description=(
        "국세청 세법해석례(예규)를 검색한다. 대상: 사전답변(01)·질의회신(02, 서면질의)·"
        "과세기준자문(03)·고시서면질의(04). 키워드·세목·관련법령·조문·기간으로 좁힐 수 있다. "
        "공백으로 구분한 낱말은 AND, match='any' 는 OR, exclude 는 NOT 이다. "
        "문서번호를 알고 있으면 document_number 를 넘기면 exact lookup 으로 처리된다. "
        "법제처 미러가 아니라 국세청 원본을 직접 조회하므로 최신 예규가 바로 잡힌다."
    ),
)
@_envelope_errors
async def search_tax_interpretations(
    query: Annotated[str | None, Field(description="검색 키워드. 공백 구분은 AND. 따옴표로 묶으면 한 구절.")] = None,
    document_number: Annotated[str | None, Field(description="문서번호를 주면 exact lookup 을 수행한다.")] = None,
    type: Annotated[
        Literal["all", "advance", "written", "advisory", "notice_written"],
        Field(description="all(기본) | advance(사전답변) | written(질의회신) | advisory(과세기준자문) | notice_written(고시서면질의)"),
    ] = "all",
    tax_type: Annotated[str | list[str] | None, Field(description="세목. 이름·별칭·코드(301~315) 허용.")] = None,
    law: Annotated[str | None, Field(description="관련 법령명(예: '상속세 및 증여세법')")] = None,
    article: Annotated[str | None, Field(description="관련 조문(예: '제35조')")] = None,
    match: Annotated[Literal["all", "any"], Field(description="all=AND(기본), any=OR")] = "all",
    exclude: Annotated[list[str] | None, Field(description="제외할 낱말(NOT)")] = None,
    date_from: Annotated[str | None, Field(description="등록일 시작 (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, Field(description="등록일 종료 (YYYY-MM-DD)")] = None,
    sort: Annotated[Literal["latest", "oldest", "relevance"] | None, Field(description="정렬")] = None,
    page: Annotated[int, Field(ge=1, description="페이지 번호(1부터). 오프셋이 아니다.")] = 1,
    limit: Annotated[int, Field(ge=1, le=100, description="페이지 크기")] = 20,
) -> str:
    # 문서번호가 주어지면 키워드 검색이 아니라 exact lookup 이 먼저다.
    if document_number and document_number.strip():
        return await lookup_tax_document(document_number=document_number)

    codes, unresolved = _resolve_tax_types(tax_type)
    merged = _merge_law(query, law, article)
    if not merged and not codes and not date_from and not date_to:
        raise NtsError(
            ErrorCode.INVALID_INPUT,
            "query, tax_type, date_from/date_to 중 최소 하나는 필요합니다.",
            hints=["문서번호로 찾으려면 document_number 또는 lookup_tax_document 를 쓰세요."],
        )

    classes = list(INTERPRETATION_CLASSES) if type == "all" else [_INTERPRETATION_TYPE_CODE[type]]
    result = await search_documents(
        doc_classes=classes, query=merged, match=match, exclude=exclude,
        tax_type_codes=codes, date_from=date_from, date_to=date_to,
        sort=sort, page=page, limit=limit,
    )
    if not result["items"]:
        raise not_found(
            f"세법해석례 검색 결과가 없습니다 (query={merged!r}).",
            [
                "키워드를 줄이세요 — 공백으로 구분된 낱말은 AND 조건입니다.",
                "match='any' 로 바꾸면 낱말 중 하나만 포함된 문서도 찾습니다.",
                *([f"인식하지 못한 세목: {', '.join(unresolved)}"] if unresolved else []),
            ],
        )
    payload: dict[str, Any] = {"domain": "interpretation", **result, "searchSemantics": SEARCH_SEMANTICS}
    if unresolved:
        payload["unresolvedTaxTypes"] = unresolved
    return _ok(payload)


# ─────────────────────────────────────────────────────────────────────────────
# 3. search_tax_decisions
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="search_tax_decisions",
    description=(
        "국세청·조세심판원·법원의 판례·결정례를 검색한다. 대상: 과세적부(05)·이의신청(06)·"
        "심사청구(07)·심판청구(08)·판례(09)·헌재(10). "
        "결정결과(인용·기각·각하·경정·재조사·국승·국패 등)와 귀속연도로 필터할 수 있다. "
        "사건번호를 알면 case_number 로 넘기면 exact lookup 이 수행된다."
    ),
)
@_envelope_errors
async def search_tax_decisions(
    query: Annotated[str | None, Field(description="검색 키워드")] = None,
    case_number: Annotated[str | None, Field(description="사건번호/문서번호. exact lookup 수행.")] = None,
    type: Annotated[
        Literal["all", "pre_assessment", "objection", "review", "tribunal", "court", "constitutional"],
        Field(description="all(기본) | pre_assessment(과세적부) | objection(이의신청) | review(심사청구) | tribunal(심판청구) | court(판례) | constitutional(헌재)"),
    ] = "all",
    tax_type: Annotated[str | list[str] | None, Field(description="세목")] = None,
    result: Annotated[list[str] | None, Field(description="결정 결과 필터(인용/기각/각하/경정/국승/국패 등)")] = None,
    attribution_year: Annotated[str | None, Field(pattern=r"^\d{4}$", description="귀속연도(4자리)")] = None,
    law: Annotated[str | None, Field(description="관련 법령명")] = None,
    article: Annotated[str | None, Field(description="관련 조문")] = None,
    match: Annotated[Literal["all", "any"], Field(description="all=AND(기본), any=OR")] = "all",
    exclude: Annotated[list[str] | None, Field(description="제외할 낱말(NOT)")] = None,
    date_from: Annotated[str | None, Field(description="등록일 시작")] = None,
    date_to: Annotated[str | None, Field(description="등록일 종료")] = None,
    sort: Annotated[Literal["latest", "oldest", "relevance"] | None, Field(description="정렬")] = None,
    page: Annotated[int, Field(ge=1)] = 1,
    limit: Annotated[int, Field(ge=1, le=100)] = 20,
) -> str:
    if case_number and case_number.strip():
        return await lookup_tax_document(document_number=case_number)

    codes, unresolved = _resolve_tax_types(tax_type)
    result_codes, unresolved_results = _resolve_decision_results(result)
    if unresolved_results:
        raise NtsError(
            ErrorCode.INVALID_INPUT,
            f"인식하지 못한 결정 결과: {', '.join(unresolved_results)}",
            hints=[f"사용 가능한 값: {', '.join(dict.fromkeys(DECISION_RESULT.values()))}"],
        )
    merged = _merge_law(query, law, article)
    if not merged and not codes and not result_codes and not date_from and not date_to and not attribution_year:
        raise NtsError(
            ErrorCode.INVALID_INPUT,
            "query, tax_type, result, attribution_year, date_from/date_to 중 최소 하나는 필요합니다.",
        )

    classes = list(DECISION_CLASSES) if type == "all" else [_DECISION_TYPE_CODE[type]]
    found = await search_documents(
        doc_classes=classes, query=merged, match=match, exclude=exclude,
        tax_type_codes=codes, decision_result_codes=result_codes,
        attribution_year=attribution_year, date_from=date_from, date_to=date_to,
        sort=sort, page=page, limit=limit,
    )
    if not found["items"]:
        raise not_found(
            f"판례·결정례 검색 결과가 없습니다 (query={merged!r}).",
            [
                "키워드를 줄이거나 match='any' 를 시도하세요.",
                *([f"인식하지 못한 세목: {', '.join(unresolved)}"] if unresolved else []),
            ],
        )
    payload: dict[str, Any] = {"domain": "decision", **found, "searchSemantics": SEARCH_SEMANTICS}
    if unresolved:
        payload["unresolvedTaxTypes"] = unresolved
    return _ok(payload)


# ─────────────────────────────────────────────────────────────────────────────
# 4. get_tax_document
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="get_tax_document",
    description=(
        "국세청 문서 1건의 본문·구조화 필드를 가져온다. ntst_dcm_id(검색 결과의 문서 ID) 또는 "
        "document_number 로 지정한다. 해석례는 요지·질의내용·사실관계·회신·관련법령으로, "
        "결정례는 처분개요·청구인주장·처분청의견·심리및판단·결론으로 분해해 반환한다. "
        "문서 종류에 따라 존재하는 절이 다르므로 없는 절은 생략된다. "
        "본문을 원본이 주지 않으면 DETAIL_NOT_AVAILABLE 로 알리고 본문을 생성하지 않는다."
    ),
)
@_envelope_errors
async def get_tax_document(
    ntst_dcm_id: Annotated[str | None, Field(description="국세법령정보시스템 문서 ID(숫자 18자리)")] = None,
    document_number: Annotated[str | None, Field(description="문서번호. ID 를 모를 때 사용.")] = None,
    include_full_text: Annotated[bool, Field(description="본문 전문 포함 여부")] = True,
    body_limit: Annotated[int | None, Field(ge=500, le=200_000)] = None,
) -> str:
    if not (ntst_dcm_id or document_number):
        raise NtsError(
            ErrorCode.INVALID_INPUT, "ntst_dcm_id 또는 document_number 중 하나는 필요합니다."
        )
    if ntst_dcm_id and ntst_dcm_id.strip():
        document = await get_document(
            ntst_dcm_id.strip(), include_full_text=include_full_text, body_limit=body_limit
        )
        if document.get("bodyUnavailable"):
            raise NtsError(
                ErrorCode.DETAIL_NOT_AVAILABLE,
                f"문서 {document.get('documentNumber') or ntst_dcm_id} 는 존재하지만 "
                "본문을 제공받지 못했습니다.",
                detail={"document": document},
            )
        return _ok({"document": document})
    return await lookup_tax_document(
        document_number=document_number or "",
        include_full_text=include_full_text,
        body_limit=body_limit,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5~6. 행정 해석기준
# ─────────────────────────────────────────────────────────────────────────────

_AUTHORITY_WARNING = (
    "기본통칙·집행기준·고시·훈령은 국세청 내부 집행기준으로, 법률·시행령·시행규칙과 같은 "
    "법규가 아닙니다. 법적 근거로 인용할 때는 반드시 근거 법조문을 함께 확인하세요."
)


@mcp.tool(
    name="search_tax_guidance",
    description=(
        "국세청 행정 해석기준을 검색한다. kind: basic_ruling(국세 기본통칙) | "
        "execution_standard(세법집행기준) | notice(국세청 고시) | directive(국세청 훈령). "
        "기본통칙은 조항 본문까지 제공되고, 집행기준은 조항명(목차)까지만 제공된다"
        "(원본이 본문을 API 로 주지 않음). 기본통칙·집행기준은 law_name 이 필요하다"
        "(예: '상속세 및 증여세법', '상속증여세 집행기준'). "
        "이 자료는 법규가 아닌 국세청 내부 집행기준임을 결과에 함께 표기한다."
    ),
)
@_envelope_errors
async def search_tax_guidance(
    kind: Annotated[
        Literal["basic_ruling", "execution_standard", "notice", "directive"],
        Field(description="조회할 기준 종류"),
    ],
    law_name: Annotated[str | None, Field(description="기본통칙·집행기준에는 필수")] = None,
    revision_year: Annotated[str | None, Field(pattern=r"^\d{4}$", description="개정연도. 생략하면 최신본")] = None,
    query: Annotated[str | None, Field(description="조항명·본문 키워드")] = None,
    page: Annotated[int, Field(ge=1)] = 1,
    limit: Annotated[int, Field(ge=1, le=300)] = 40,
) -> str:
    result = await search_guidance(
        kind=kind, law_name=law_name, revision_year=revision_year,
        query=query, page=page, limit=limit,
    )
    if not result.get("items"):
        raise not_found(
            f"{kind} 조회 결과가 없습니다.",
            [
                "query 를 줄이거나 생략하고 전체 목록을 받아 보세요.",
                *(["revision_year 를 생략하면 최신본을 조회합니다."] if revision_year else []),
            ],
        )
    return _ok({"domain": "guidance", "authorityWarning": _AUTHORITY_WARNING, **result})


@mcp.tool(
    name="get_tax_guidance",
    description=(
        "기본통칙 또는 세법집행기준의 특정 조항 1건을 가져온다. "
        "search_tax_guidance 로 찾은 item_id, 또는 조항명 일부(title)로 지정한다."
    ),
)
@_envelope_errors
async def get_tax_guidance(
    kind: Annotated[Literal["basic_ruling", "execution_standard"], Field(description="기준 종류")],
    law_name: Annotated[str, Field(description="대상 법령명")],
    revision_year: Annotated[str | None, Field(pattern=r"^\d{4}$")] = None,
    item_id: Annotated[str | None, Field(description="조항 식별자(search 결과의 itemId)")] = None,
    title: Annotated[str | None, Field(description="조항명 일부. item_id 를 모를 때 사용")] = None,
) -> str:
    if not (item_id or title):
        raise NtsError(ErrorCode.INVALID_INPUT, "item_id 또는 title 중 하나는 필요합니다.")

    result = (
        await get_basic_rulings(law_name=law_name, revision_year=revision_year, limit=300)
        if kind == "basic_ruling"
        else await get_execution_standards(law_name=law_name, revision_year=revision_year, limit=300)
    )
    items = result["items"]
    hit = (
        next((i for i in items if i.get("itemId") == item_id), None)
        if item_id
        else next((i for i in items if title and title in i["title"]), None)
    )
    if not hit:
        label = "기본통칙" if kind == "basic_ruling" else "집행기준"
        target = f"itemId '{item_id}'" if item_id else f"제목에 '{title}' 를 포함한 조항"
        raise not_found(
            f"{law_name} {result['revisionYear']}년 {label} 에서 {target} 을 찾지 못했습니다.",
            [f"해당 연도 조항 수: {len(items)}. search_tax_guidance 로 조항명을 먼저 확인하세요."],
        )
    return _ok({"lawName": result["lawName"], "revisionYear": result["revisionYear"], "item": hit})


# ─────────────────────────────────────────────────────────────────────────────
# 7. search_tax_forms
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="search_tax_forms",
    description=(
        "국세 법령서식·별표를 검색한다. 서식명·관련법령·개정일·서식 파일 식별자를 반환한다. "
        "파일 실물은 국세법령정보시스템이 POST 폼으로만 내려주므로 이 서버는 바이너리를 "
        "제공하지 않고 조회 화면 URL 을 준다."
    ),
)
@_envelope_errors
async def search_tax_forms(
    query: Annotated[str | None, Field(description="서식명 키워드")] = None,
    law_name: Annotated[str | None, Field(description="관련 법령명으로 한정")] = None,
    page: Annotated[int, Field(ge=1)] = 1,
    limit: Annotated[int, Field(ge=1, le=100)] = 20,
) -> str:
    result = await search_forms(query=query, law_name=law_name, page=page, limit=limit)
    if not result["items"]:
        raise not_found("서식 검색 결과가 없습니다.", ["서식명 일부만 넣어 보세요(예: '상속세', '증여')."])
    return _ok({"domain": "form", **result})


# ─────────────────────────────────────────────────────────────────────────────
# 8. search_taxlaw (영역 통합)
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="search_taxlaw",
    description=(
        "국세청 자료 전 영역을 한 번에 검색한다(해석례·결정례·고시훈령·서식). "
        "질의에 문서번호가 섞여 있으면 exact lookup 을 최우선으로 시도한다. "
        "domains 를 생략하면 질의 표현('예규', '심판', '통칙', '적부' 등)을 보고 조회 영역을 "
        "자동 결정한다. 어느 영역을 봐야 할지 모를 때의 진입점으로 쓸 것."
    ),
)
@_envelope_errors
async def search_taxlaw(
    query: Annotated[str, Field(min_length=1, description="자연어 또는 키워드")],
    domains: Annotated[
        list[Literal["interpretation", "decision", "guidance", "form"]] | None,
        Field(description="조회할 영역. 생략하면 자동 결정."),
    ] = None,
    tax_type: Annotated[str | list[str] | None, Field(description="세목(명시하면 필터로 적용)")] = None,
    limit_per_domain: Annotated[int, Field(ge=1, le=50, description="영역별 결과 수")] = 5,
) -> str:
    hint = route_query(query)
    targets = list(domains) if domains else (hint.domains or ["interpretation", "decision"])
    codes, _unresolved = _resolve_tax_types(tax_type)
    # 세목은 **사용자가 명시했을 때만** 필터로 쓴다. 추정 세목을 강제하면 거짓 부정이
    # 난다 — '상속 공동상속주택' 은 308 로 추정되지만 정작 맞는 예규는 307 로 분류돼 있다.
    search_query = hint.content_query or query

    # 문서번호가 섞여 있으면 exact lookup 이 최우선이다.
    if hint.document_number or looks_like_document_number(query):
        outcome = await lookup_by_document_number(
            hint.document_number or query.strip(), include_full_text=False
        )
        if outcome["found"]:
            return _ok({
                "resolvedBy": "documentNumber",
                "routing": hint.to_dict(),
                "exactMatch": True,
                "document": outcome["document"],
            })

    results: dict[str, Any] = {}
    errors: dict[str, str] = {}

    async def one(domain: str) -> None:
        try:
            if domain == "interpretation":
                classes = [c for c in hint.doc_classes if c in INTERPRETATION_CLASSES] or list(INTERPRETATION_CLASSES)
                results["interpretation"] = await search_documents(
                    doc_classes=classes, query=search_query, tax_type_codes=codes,
                    limit=limit_per_domain, sort="relevance",
                )
            elif domain == "decision":
                classes = [c for c in hint.doc_classes if c in DECISION_CLASSES] or list(DECISION_CLASSES)
                results["decision"] = await search_documents(
                    doc_classes=classes, query=search_query, tax_type_codes=codes,
                    limit=limit_per_domain, sort="relevance",
                )
            elif domain == "guidance":
                # 통칙·집행기준은 법령명이 필요하므로 통합검색에서는 고시·훈령만 훑는다.
                notice, directive = await asyncio.gather(
                    search_guidance(kind="notice", query=search_query, limit=limit_per_domain),
                    search_guidance(kind="directive", query=search_query, limit=limit_per_domain),
                )
                results["guidance"] = {"notice": notice, "directive": directive}
            elif domain == "form":
                results["form"] = await search_forms(query=search_query, limit=limit_per_domain)
        except Exception as exc:  # noqa: BLE001 — 한 영역 실패가 전체를 무너뜨리지 않게
            errors[domain] = str(exc)

    await asyncio.gather(*(one(d) for d in targets))

    def has_hit(value: Any) -> bool:
        if isinstance(value, dict) and isinstance(value.get("items"), list):
            return bool(value["items"])
        if isinstance(value, dict):
            return any(has_hit(v) for v in value.values() if isinstance(v, dict))
        return False

    if not any(has_hit(v) for v in results.values()) and errors:
        raise NtsError(
            ErrorCode.UPSTREAM_ERROR,
            f"'{query}' 통합검색 중 하나 이상의 조회 영역이 실패했습니다.",
            detail={"partialErrors": errors, "domainsSearched": targets},
        )

    if not any(has_hit(v) for v in results.values()):
        raise not_found(
            f"'{query}' 에 대한 결과가 없습니다 (검색어 '{search_query}', 조회 영역: {', '.join(targets)}).",
            [
                "키워드를 줄이세요 — 공백 구분 낱말은 AND 조건입니다.",
                "영역을 domains 로 직접 지정해 보세요.",
            ],
        )

    payload: dict[str, Any] = {
        "query": query,
        "searchQuery": search_query,
        "routing": hint.to_dict(),
        "domainsSearched": targets,
        "taxTypeFilterApplied": codes or None,
        "taxTypeNote": (
            "사용자가 지정한 세목으로 필터링했습니다."
            if codes
            else "세목 필터를 적용하지 않았습니다(추정 세목을 강제하면 분류가 다른 관련 문서가 "
                 "누락될 수 있음). routing.taxTypeCodes 는 참고용 추정치입니다."
        ),
        "results": results,
    }
    if errors:
        payload["partialErrors"] = errors
    return _ok(payload)


# ─────────────────────────────────────────────────────────────────────────────
# 9. tax_research
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="tax_research",
    description=(
        "세무 쟁점 하나를 층별 근거로 모아 온다: 법률→시행령→시행규칙(범위 밖, 확인 경로 안내)"
        "→기본통칙→세법집행기준→국세청 해석례→불복 결정례→판례·헌재. "
        "각 층에 authorityLevel 을 붙여 법규와 행정해석과 개별 결정의 효력 차이를 구분한다. "
        "**법률적 판단이나 결론을 만들지 않는다** — 원문 근거 수집과 출처 제시만 한다. "
        "법령 본문이 필요하면 korean-law-mcp 를 함께 쓸 것."
    ),
)
@_envelope_errors
async def tax_research(
    question: Annotated[str, Field(min_length=2, description="세무 쟁점 질문(자연어)")],
    tax_type: Annotated[str | None, Field(description="세목을 알면 지정(정확도 향상)")] = None,
    law: Annotated[str | None, Field(description="관련 법령명을 알면 지정")] = None,
    article: Annotated[str | None, Field(description="관련 조문을 알면 지정")] = None,
    limit_per_layer: Annotated[int, Field(ge=1, le=20, description="층별 결과 수")] = 5,
    include_guidance: Annotated[bool, Field(description="기본통칙·집행기준 포함 여부")] = True,
) -> str:
    outcome = await run_tax_research(
        question=question, tax_type=tax_type, law=law, article=article,
        limit_per_layer=limit_per_layer, include_guidance=include_guidance,
    )
    return _ok(outcome)


TOOL_NAMES = [
    "lookup_tax_document",
    "search_tax_interpretations",
    "search_tax_decisions",
    "get_tax_document",
    "search_tax_guidance",
    "get_tax_guidance",
    "search_tax_forms",
    "search_taxlaw",
    "tax_research",
]
