"""문서번호 exact lookup.

이 서버의 존재 이유에 가장 가까운 기능이다. 규칙은 하나다:
**사이트가 돌려준 문서번호가 입력과 정확히 같을 때만 ``found``.**

사이트 검색은 부분일치를 넉넉하게 돌려준다 — ``법규재산-0119`` 를 넣으면
``서면-2026-법규재산-0119`` 와 ``기준-2023-법규부가-0044`` 와 ``서면-2015-징세-0119``
가 함께 온다(실측). 이 중 첫 건을 정답처럼 반환하면 세무 상담에서 곧바로 오답이 된다.
그래서 비슷한 건은 ``similarDocuments`` 로 따로 담고 ``exactMatch: false`` 를 명시한다.
"""

from __future__ import annotations

from typing import Any

from ..codes import collection_for
from ..doc_number import is_same_doc_number, lookup_candidates, parse_doc_number
from .documents import DECISION_CLASSES, INTERPRETATION_CLASSES, get_document, search_documents

_CLASSES: dict[str, list[str]] = {
    "interpretation": list(INTERPRETATION_CLASSES),
    "decision": list(DECISION_CLASSES),
}


def _domain_order(raw: str) -> list[str]:
    """문서번호 모양에서 어느 영역을 먼저 볼지 정한다. 틀려도 나머지를 순차로 본다."""
    parsed = parse_doc_number(raw)
    if parsed.inferred_doc_class:
        if collection_for(parsed.inferred_doc_class).startswith("question"):
            return ["interpretation", "decision"]
        return ["decision", "interpretation"]
    return ["interpretation", "decision"]


async def lookup_by_document_number(
    raw: str,
    *,
    include_full_text: bool = True,
    body_limit: int | None = None,
    similar_limit: int = 10,
) -> dict[str, Any]:
    """문서번호로 문서를 찾는다.

    후보 검색어를 순서대로 던지고, 각 응답에서 **문서번호가 정확히 일치하는 건만**
    exact 로 인정한다. 어느 후보에서도 exact 가 없으면 그동안 모은 부분일치 건을
    유사문서로 돌려준다.
    """
    parsed = parse_doc_number(raw)
    candidates = lookup_candidates(raw)
    similar: dict[str, dict[str, Any]] = {}
    tried: list[str] = []
    searched: list[str] = []

    for domain in _domain_order(raw):
        searched.append(domain)
        for candidate in candidates:
            tried.append(f"{domain}:{candidate}")
            # 후보 하나라도 조회에 실패하면 부존재를 확정할 수 없다. 장애를 삼키고
            # NOT_FOUND 로 내리면 실재하는 문서를 없다고 답하게 되므로 그대로 전파한다.
            result = await search_documents(
                doc_classes=_CLASSES[domain],
                query=candidate,
                match="all",
                limit=30,
                sort="relevance",
            )

            for item in result["items"]:
                number = item.get("documentNumber", "")
                if is_same_doc_number(number, parsed.canonical) or is_same_doc_number(number, raw):
                    document = await get_document(
                        item["ntstDcmId"],
                        include_full_text=include_full_text,
                        body_limit=body_limit,
                    )
                    return {
                        "found": True,
                        "exactMatch": True,
                        "normalizedDocumentNumber": parsed.canonical,
                        "inputInterpretation": parsed.interpretation(),
                        "domain": domain,
                        "document": document,
                        "sourceUrl": document["sourceUrl"],
                        "triedQueries": tried,
                        "searchedDomains": searched,
                    }
                if number:
                    similar.setdefault(item["ntstDcmId"], item)

    similar_documents = list(similar.values())[:similar_limit]
    note = (
        "입력한 문서번호와 정확히 일치하는 문서가 없습니다. similarDocuments 는 문서번호 "
        "일부가 겹치는 별개의 문서이며, 요청한 문서가 아닙니다. 이 중 하나를 정답으로 "
        "제시하지 마세요."
        if similar_documents
        else "입력한 문서번호와 정확히 일치하는 문서도, 부분적으로 겹치는 문서도 찾지 못했습니다."
    )

    out: dict[str, Any] = {
        "found": False,
        "exactMatch": False,
        "normalizedDocumentNumber": parsed.canonical,
        "inputInterpretation": parsed.interpretation(),
        "triedQueries": tried,
        "searchedDomains": searched,
        "note": note,
    }
    if similar_documents:
        out["similarDocuments"] = similar_documents
    return out
