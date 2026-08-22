"""지방세 문서번호 정규화.

지방세 문서번호는 국세와 배열이 다르다. 국세는 `종류-연도-분류-일련`
(서면-2026-법규재산-0119), 지방세 유권해석은 `생산 부서명 + 일련번호` 형식이다.
실측 표본::

    부동산세제과-1794(2026.6.9.)호     ← 부서-일련(시행일)호
    지방소득소비세제과-1683(2026.6.15.)호
    지방세특례제도과-1453(2026.6.9.)호
    부동산세제과-1050호                ← 날짜 없음
    부동산세제과-924                   ← '호' 없음
    지방세운영과-1050
    지방세운영-4924
    지방세정팀-2924
    행정안전부100                      ← 하이픈 없음

사이트의 문서번호 검색은 일련번호 부분일치다(`924` → `4924`·`2924`도 매칭).
이 모듈은 조회용 일련번호도 추출하며, 동일성 판정은
:func:`is_same_local_doc_number` 가 엄격하게 한다.

국세 문서번호 처리와 마찬가지로 없는 번호를 만들지 않는다.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_HIGHLIGHT = re.compile(r"<!H[SE]>")
_DASHES = re.compile(r"[‐-―⁃−﹘﹣－~∼]")

#: 부서-일련(날짜)호 / 부서-일련호 / 부서-일련 / 부서일련
_PATTERN = re.compile(
    r"^(?P<dept>[가-힣A-Za-z()\s]*?)\s*-?\s*"
    r"(?P<serial>\d+)\s*"
    r"(?:\(\s*(?P<date>[\d.\s]+?)\s*\)\s*)?"
    r"(?P<ho>호)?\s*$"
)

#: 문서번호를 복사할 때 앞에 붙는 자료 종류 라벨.
#:
#: 기관 단독명은 넣지 않는다. `지방세`·`행정안전부` 는 실제 부서명·문서번호의
#: 일부다(지방세정팀-2924, 지방세운영과-1050, 행정안전부100). 라벨로 떼어내면
#: 부서명이 잘려 `정팀-2924` 같은 없는 번호가 만들어진다.
_LABELS = [
    "행정안전부 유권해석", "법제처 유권해석", "조세심판원 심판결정례",
    "감사원 심사결정례", "헌법재판소 결정례", "법원 판례",
    "유권해석", "심판결정례", "심사결정례", "결정례", "판례",
]

_KEY_STRIP = re.compile(r"[\s\-·.,_()（）호]")


def _fold(text: str) -> str:
    s = unicodedata.normalize("NFKC", _HIGHLIGHT.sub("", str(text or "")))
    s = _DASHES.sub("-", s)
    return re.sub(r"\s+", " ", s).strip()


def comparison_key(value: str | None) -> str:
    """표기 차이를 접은 비교키. 구분자·괄호·'호'·날짜를 뺀다.

    날짜는 같은 문서에 대해 표기가 흔들리므로(있는 표기/없는 표기) 키에서 제외하고,
    부서명 + 일련번호로만 견준다.
    """
    if not value:
        return ""
    s = _fold(value)
    s = re.sub(r"\([^)]*\)", "", s)          # (2026.6.9.) 제거
    return _KEY_STRIP.sub("", s).lower()


@dataclass(slots=True)
class ParsedLocalDocNumber:
    canonical: str
    key: str
    structured: bool
    department: str | None = None
    serial: str | None = None
    serial_number: int | None = None
    date: str | None = None

    def interpretation(self) -> dict[str, object]:
        out: dict[str, object] = {"structured": self.structured, "layout": "부서-일련"}
        for name in ("department", "serial", "date"):
            value = getattr(self, name)
            if value:
                out[name] = value
        return out


def _strip_labels(text: str) -> str:
    current = text
    for _ in range(3):
        changed = False
        for label in _LABELS:
            # 라벨 뒤에 반드시 구분자나 공백이 와야 한다 — 한글이 바로 붙어 있으면
            # 부서명의 일부일 수 있으므로 떼지 않는다.
            pattern = re.compile(rf"^{re.escape(label)}\s*[-:]?\s+(?=\S)")
            if pattern.match(current):
                rest = pattern.sub("", current).strip()
                if rest and re.search(r"\d", rest):
                    current = rest
                    changed = True
                    break
        if not changed:
            break
    return current


def parse_local_doc_number(raw: str | None) -> ParsedLocalDocNumber:
    """지방세 문서번호 파싱. 실패해도 예외 없이 ``structured=False`` 로 돌려준다."""
    cleaned = _strip_labels(_fold(raw))
    if not cleaned or not re.search(r"\d", cleaned):
        return ParsedLocalDocNumber(cleaned, comparison_key(cleaned), False)

    m = _PATTERN.match(cleaned)
    if not m:
        return ParsedLocalDocNumber(cleaned, comparison_key(cleaned), False)

    dept = (m.group("dept") or "").strip() or None
    serial = m.group("serial")
    date = re.sub(r"\s+", "", m.group("date")) if m.group("date") else None

    # 부서명이 없으면 문서번호로 보기 어렵다(그냥 숫자일 수 있다).
    if not dept:
        return ParsedLocalDocNumber(cleaned, comparison_key(cleaned), False, serial=serial)

    canonical = f"{dept}-{serial}"
    if date:
        canonical += f"({date})"
    if m.group("ho"):
        canonical += "호"

    return ParsedLocalDocNumber(
        canonical=canonical,
        key=comparison_key(canonical),
        structured=True,
        department=dept,
        serial=serial,
        serial_number=int(serial),
        date=date,
    )


def is_same_local_doc_number(a: str | None, b: str | None) -> bool:
    """두 지방세 문서번호가 같은 문서를 가리키는지.

    부서명과 일련번호가 **모두** 같아야 인정한다. 일련번호만 같은 경우
    (`부동산세제과-924` vs `지방세정팀-2924`)는 다른 문서다.
    """
    ka, kb = comparison_key(a), comparison_key(b)
    if ka and ka == kb:
        return True

    pa, pb = parse_local_doc_number(a), parse_local_doc_number(b)
    if not (pa.structured and pb.structured):
        return False
    if pa.serial_number is None or pa.serial_number != pb.serial_number:
        return False
    # 부서명은 '과/팀' 접미가 흔들리므로(지방세운영 vs 지방세운영과) 접미를 떼고 비교
    def dept_key(value: str | None) -> str:
        return re.sub(r"(과|팀|국|부)$", "", re.sub(r"\s+", "", value or ""))

    return dept_key(pa.department) == dept_key(pb.department)


def looks_like_local_document_number(raw: str | None) -> bool:
    """입력이 지방세 문서번호로 보이는지 — 라우팅 판단에 쓴다."""
    parsed = parse_local_doc_number(raw)
    if not parsed.structured:
        return False
    # 부서명에 '세제과/운영과/특례제도과/세정팀' 같은 지방세 부서 어휘가 있으면 확실하다
    dept = parsed.department or ""
    return bool(re.search(r"(세제과|운영과|제도과|세정팀|운영|정책관|본부|행정안전부)", dept))
