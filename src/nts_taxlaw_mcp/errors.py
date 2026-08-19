"""구조화된 오류.

이 서버의 최우선 요구사항은 "없는 것을 없다고 말하기"다. 그래서 오류 코드는
**자료가 없다**(NOT_FOUND)와 **업스트림이 답을 주지 못했다**(UPSTREAM_ERROR,
DETAIL_NOT_AVAILABLE)를 절대 섞지 않는다. 이 둘을 한 라벨로 뭉개면 장애가
부존재로 읽혀서, 실재하는 예규를 "없습니다"라고 답하는 거짓 부정이 된다.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    #: 조회 조건에 정확히 일치하는 자료가 원본에 없다. 부존재 주장.
    NOT_FOUND = "NOT_FOUND"
    #: 문서는 찾았으나 본문을 원본이 제공하지 않는다. 부존재 주장 아님.
    DETAIL_NOT_AVAILABLE = "DETAIL_NOT_AVAILABLE"
    #: 국세법령정보시스템이 오류·점검·비정상 응답을 반환. 부존재 주장 아님.
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    #: 응답 형식이 예상과 달라 파싱하지 못했다 (사이트 구조 변경 신호).
    PARSE_ERROR = "PARSE_ERROR"
    #: 이 서버의 자체 요청 한도에 걸렸다.
    RATE_LIMITED = "RATE_LIMITED"
    #: 입력이 잘못됐다.
    INVALID_INPUT = "INVALID_INPUT"
    #: 시간 초과.
    TIMEOUT = "TIMEOUT"


#: 모델이 본문·결론을 만들어내지 못하게 못 박는 지시문.
GUARDRAIL: dict[ErrorCode, str] = {
    ErrorCode.NOT_FOUND: (
        "원본에 일치하는 자료가 없습니다. 문서 내용을 추측하거나 생성하지 마세요. "
        "비슷한 문서를 정답으로 제시하지 말고, 사용자에게 '조회 실패'를 그대로 보고하세요."
    ),
    ErrorCode.DETAIL_NOT_AVAILABLE: (
        "문서는 존재하지만 본문을 가져오지 못했습니다. 본문을 추측·생성하지 마세요. "
        "메타데이터와 원문 링크만 제시하고, 본문은 확인하지 못했음을 명시하세요."
    ),
    ErrorCode.UPSTREAM_ERROR: (
        "국세법령정보시스템 응답 실패입니다. 이는 '자료가 없다'는 뜻이 아닙니다. "
        "자료 부존재로 단정하지 말고 일시적 조회 실패로 보고하세요."
    ),
    ErrorCode.PARSE_ERROR: "원본 응답을 해석하지 못했습니다. 내용을 추측하지 말고 조회 실패로 보고하세요.",
    ErrorCode.RATE_LIMITED: "요청 한도에 걸렸습니다. 잠시 후 재시도하세요. 자료 부존재가 아닙니다.",
    ErrorCode.INVALID_INPUT: "입력이 잘못되었습니다. 결과를 추측하지 마세요.",
    ErrorCode.TIMEOUT: "시간 초과입니다. 자료 부존재가 아닙니다.",
}


class NtsError(Exception):
    """국세법령정보시스템 조회 오류."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        hints: list[str] | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hints = hints or []
        self.detail = detail

    def envelope(self) -> dict[str, Any]:
        """LLM 이 읽을 오류 봉투."""
        error: dict[str, Any] = {"code": str(self.code), "message": self.message}
        if self.hints:
            error["hints"] = self.hints
        if self.detail:
            error["detail"] = self.detail
        return {"ok": False, "error": error, "guardrail": GUARDRAIL[self.code]}


def not_found(message: str, hints: list[str] | None = None, **detail: Any) -> NtsError:
    return NtsError(ErrorCode.NOT_FOUND, message, hints=hints, detail=detail or None)


def upstream(message: str, **detail: Any) -> NtsError:
    return NtsError(ErrorCode.UPSTREAM_ERROR, message, detail=detail or None)
