"""문서번호 정규화 및 동일성 판정.

실무에서 세무사가 던지는 문서번호는 사이트 표기와 거의 항상 다르다. 복사할 때
문서구분 라벨이 붙어 오고("질의회신 서면-2026-법규재산-0119"), 하이픈이 빠지고
("서면2026법규재산0119"), 접두가 겹치고("서면서면-…"), 전각·다양한 대시가 섞인다.
이 모듈은 그 모든 표기를 **같은 비교키**로 접는다.

실제 사이트 데이터에서 관측한 배열은 세 가지다(문서구분별 60건 표본)::

    레이아웃 A  종류-연도-분류-일련    사전-2026-법규소득-0543 / 서면-2026-법규재산-0119
                                      기준-2026-법규부가-0096 / 고시-2026-소비-0002
                                      조심-2025-인-4460 / 대법원-2024-두-55396
                                      헌법재판소-2011-헌바-97
    레이아웃 B  종류-기관-연도-일련    적부-국세청-2026-0119 / 이의-광주청-2026-0024
                                      심사-부가-2026-0018
    레이아웃 C  기관 부서-일련         재정경제부 국제조세협력과-104 (구 기재부 회신)

A 와 B 는 두 번째 마디가 4자리 연도인지로 갈린다. 이 구분을 놓치면
``적부-국세청-2026-0119`` 의 "국세청"을 기관 접두로 오인해 떼어내게 된다.

설계 원칙: **없는 번호를 만들지 않는다.** 정규화는 조회용 후보 키를 넓히는 데만
쓰고, 최종적으로 반환하는 문서번호는 항상 사이트가 준 원문 문자열이다.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .codes import DOC_CLASS_ABBR

#: 검색 응답의 하이라이트 마커. 사이트가 일치 구간을 감싸 보낸다.
_HIGHLIGHT = re.compile(r"<!H[SE]>")

#: 문서구분 전체 명칭 — 복사 시 번호 앞에 붙어 오는 라벨.
_DOC_CLASS_LABELS = [
    "사전답변", "질의회신", "과세기준자문", "고시서면질의",
    "과세적부", "이의신청", "심사청구", "심판청구",
    "주요대법원판결", "주요세법해석사례", "법제처해석례",
    "납세자보호위원회심의사례", "해석정비", "해석유보",
    "판례", "헌재", "감사", "쟁점", "부실",
]

#: 생산기관 명칭 — "국세청 서면-…" 처럼 앞에 붙는 경우가 있다.
_AGENCY_LABELS = [
    "국세청", "기획재정부", "재정경제부", "법제처", "조세심판원", "감사원",
    "대법원", "헌법재판소", "국세심판원",
]

#: 레이아웃 B 를 쓰는 종류(두 번째 마디가 기관·세목).
_LAYOUT_B_TYPES = {"적부", "이의", "심사"}

#: 레이아웃 A 의 종류로 관측된 값(법원명은 접미 규칙으로 따로 판정).
_LAYOUT_A_TYPES = {"사전", "서면", "기준", "고시", "조심", "심판", "질의", "감사"}

_YEAR_RE = re.compile(r"^(19|20)\d{2}$")
_DASHES = re.compile(r"[‐-―⁃−﹘﹣－~∼]")
_MIDDOTS = re.compile(r"[·•・]")
_KEY_STRIP = re.compile(r"[\s\-·・.,_()（）]")


def _is_court_name(s: str) -> bool:
    return "법원" in s or "헌법재판소" in s


def _is_year(s: str) -> bool:
    return bool(_YEAR_RE.match(s))


def _fold(text: str) -> str:
    """전각 영숫자·다양한 대시·공백을 표준형으로 접는다."""
    s = unicodedata.normalize("NFKC", text)
    s = _DASHES.sub("-", s)
    s = _MIDDOTS.sub("-", s)
    return re.sub(r"\s+", " ", s).strip()


def comparison_key(s: str | None) -> str:
    """표기 차이를 모두 접은 비교키. 구분자·공백·괄호를 지운다."""
    if not s:
        return ""
    cleaned = _HIGHLIGHT.sub("", str(s))
    return _KEY_STRIP.sub("", unicodedata.normalize("NFKC", cleaned)).lower()


@dataclass(slots=True)
class ParsedDocNumber:
    #: 사이트 표기에 맞춘 정규 문자열. 파싱 실패 시 정리만 한 원문.
    canonical: str
    #: 표기 차이를 모두 접은 비교키.
    key: str
    #: "A" | "B" | "C" | "unknown"
    layout: str
    #: 구조 파싱이 성공했는지. False 면 키워드 검색으로만 처리한다.
    structured: bool
    type: str | None = None
    year: str | None = None
    category: str | None = None
    agency: str | None = None
    serial: str | None = None
    #: 일련번호의 수치값 — 0 패딩 차이를 흡수한다.
    serial_number: int | None = None
    #: 병합 사건 등 추가 사건번호(헌재 다건).
    extra_serials: list[str] = field(default_factory=list)
    #: 문서구분 코드를 번호 모양에서 유추한 결과. 라우팅 힌트로만 쓴다.
    inferred_doc_class: str | None = None

    def interpretation(self) -> dict[str, object]:
        """도구 응답에 실을 입력 해석 결과."""
        out: dict[str, object] = {"layout": self.layout, "structured": self.structured}
        for name in ("type", "year", "category", "agency", "serial"):
            value = getattr(self, name)
            if value:
                out[name] = value
        return out


def _looks_like_doc_number(s: str) -> bool:
    """대략적인 문서번호 판정 — 라벨 제거의 안전판으로만 쓴다."""
    t = re.sub(r"[\s\-]", "", s)
    if not re.search(r"\d", t):
        return False
    head_match = re.match(r"^[가-힣]+", t)
    if not head_match:
        return False
    head = head_match.group(0)
    if head[:2] in _LAYOUT_A_TYPES or head[:2] in _LAYOUT_B_TYPES:
        return True
    if _is_court_name(head):
        return True
    return bool(re.match(r"^[가-힣]{2,}(19|20)\d{2}", t))


def _strip_leading_labels(s: str) -> str:
    """앞에 붙은 라벨을 뗀다.

    뒤에 남은 문자열이 문서번호로 파싱되는 경우에만 뗀다 — 그렇지 않으면
    ``적부-국세청-2026-0119`` 의 "국세청"처럼 번호의 일부를 잘라먹는다.
    """
    current = s
    for _ in range(4):
        changed = False
        for label in (*_DOC_CLASS_LABELS, *_AGENCY_LABELS):
            pattern = re.compile(rf"^{re.escape(label)}\s*[-:\s]?\s*(?=\S)")
            if not pattern.match(current):
                continue
            rest = pattern.sub("", current).strip()
            if rest and _looks_like_doc_number(rest):
                current = rest
                changed = True
                break
        if not changed:
            break
    return current


def _dedupe_type_prefix(s: str) -> str:
    """접두 중복 제거: "서면서면-2026-…" → "서면-2026-…"."""
    m = re.match(r"^([가-힣]{2,4})\1(?=[\s\-0-9])", s)
    return s[len(m.group(1)):] if m else s


def _tokenize_compact(s: str) -> list[str] | None:
    """구분자가 전혀 없는 표기를 마디로 자른다.

    "서면2026법규재산0119" → ["서면", "2026", "법규재산", "0119"]
    "적부국세청20260119"   → ["적부", "국세청", "2026", "0119"]
    """
    runs = re.findall(r"[가-힣]+|\d+|\([^)]*\)", s)
    if len(runs) < 2:
        return None

    out: list[str] = []
    for run in runs:
        if run.isdigit():
            # 연도+일련이 한 덩어리로 붙은 경우 분리 (20260119 → 2026 / 0119)
            if len(run) >= 6 and _is_year(run[:4]) and not any(_is_year(x) for x in out):
                out.extend([run[:4], run[4:]])
            else:
                out.append(run)
            continue
        if run.startswith("("):
            out.append(run)
            continue
        head2 = run[:2]
        if not out and len(run) > 2 and (head2 in _LAYOUT_A_TYPES or head2 in _LAYOUT_B_TYPES):
            out.extend([head2, run[2:]])
        else:
            out.append(run)
    return out


def parse_doc_number(raw: str | None) -> ParsedDocNumber:
    """문서번호 파싱.

    실패해도 예외를 던지지 않고 ``structured=False`` 로 돌려준다 — 파싱 실패는
    "이 입력은 키워드로 취급한다"는 뜻이고, 오류가 아니다.
    """
    cleaned = _fold(_HIGHLIGHT.sub("", str(raw or "")))
    cleaned = _dedupe_type_prefix(_strip_leading_labels(cleaned))
    cleaned = _dedupe_type_prefix(cleaned)

    def fallback() -> ParsedDocNumber:
        return ParsedDocNumber(
            canonical=cleaned, key=comparison_key(cleaned), layout="unknown", structured=False
        )

    if not cleaned or not re.search(r"\d", cleaned):
        return fallback()

    # 레이아웃 C: "재정경제부 국제조세협력과-104"
    c_match = re.fullmatch(r"([가-힣]{3,})\s+([가-힣]{2,})\s*-\s*(\d+)", cleaned)
    if c_match:
        agency, dept, serial = c_match.groups()
        return ParsedDocNumber(
            canonical=f"{agency} {dept}-{serial}",
            key=comparison_key(f"{agency}{dept}{serial}"),
            layout="C", structured=True,
            agency=agency, category=dept, serial=serial, serial_number=int(serial),
        )

    parts = [p for p in re.split(r"\s*[-\s]\s*", cleaned) if p]
    if len(parts) < 3:
        tokens = _tokenize_compact(re.sub(r"[-\s]", "", cleaned))
        if tokens and len(tokens) >= len(parts):
            parts = tokens
    if len(parts) < 3:
        return fallback()

    doc_type = parts[0]
    type_known = (
        doc_type in _LAYOUT_A_TYPES or doc_type in _LAYOUT_B_TYPES or _is_court_name(doc_type)
    )
    if not type_known and not re.match(r"^[가-힣(]", doc_type):
        return fallback()

    tail = parts[-1]
    serials = [x.strip() for x in tail.split(",") if x.strip()]
    if not serials or not re.match(r"^\d+", serials[0]):
        return fallback()
    serial = serials[0]

    if _is_year(parts[1]):
        layout = "A"
        year = parts[1]
        category = "-".join(parts[2:-1]) or None
        agency = None
        canonical = "-".join(x for x in (doc_type, year, category, tail) if x)
    elif len(parts) >= 4 and _is_year(parts[2]):
        layout = "B"
        agency = parts[1]
        year = parts[2]
        category = None
        canonical = "-".join((doc_type, agency, year, tail))
    else:
        return fallback()

    inferred = DOC_CLASS_ABBR.get(doc_type)
    if inferred is None and _is_court_name(doc_type):
        inferred = "10" if "헌법재판소" in doc_type else "09"

    return ParsedDocNumber(
        canonical=canonical,
        key=comparison_key(canonical),
        layout=layout,
        structured=True,
        type=doc_type,
        year=year,
        category=category,
        agency=agency,
        serial=serial,
        serial_number=int(re.sub(r"\D.*$", "", serial) or 0),
        extra_serials=serials[1:],
        inferred_doc_class=inferred,
    )


def is_same_doc_number(a: str | None, b: str | None) -> bool:
    """두 문서번호가 **같은 문서**를 가리키는지.

    구조가 둘 다 잡히면 마디별로 비교하고 일련번호는 수치로 견준다(사이트는
    4자리 0 패딩이라 ``0119`` 와 ``119`` 는 같은 문서다). 구조가 안 잡히면 비교키
    완전 일치만 인정한다. 어느 쪽도 **부분일치는 인정하지 않는다.**
    """
    ka, kb = comparison_key(a), comparison_key(b)
    if ka and ka == kb:
        return True

    pa, pb = parse_doc_number(a), parse_doc_number(b)
    if not (pa.structured and pb.structured):
        return False
    if pa.layout != pb.layout:
        return False
    if (pa.type or "") != (pb.type or ""):
        return False
    if (pa.year or "") != (pb.year or ""):
        return False
    if comparison_key(pa.category) != comparison_key(pb.category):
        return False
    if comparison_key(pa.agency) != comparison_key(pb.agency):
        return False
    if pa.serial_number is None or pb.serial_number is None:
        return False
    if pa.serial_number != pb.serial_number:
        return False
    # 병합 사건 목록까지 같아야 동일 문서다
    return [comparison_key(x) for x in pa.extra_serials] == [
        comparison_key(x) for x in pb.extra_serials
    ]


def lookup_candidates(raw: str) -> list[str]:
    """사이트 검색에 던질 후보 문자열들. **순서가 곧 우선순위**다.

    사이트 색인은 하이픈 있는 형태와 없는 형태를 모두 담고 있어(``DOCU_NO_STR1``
    실측) 정규형 하나로도 대개 맞지만, 표기 편차를 흡수하려고 압축형을 함께 던진다.
    """
    parsed = parse_doc_number(raw)
    out: list[str] = []

    def add(value: str | None) -> None:
        if value and value not in out:
            out.append(value)

    add(parsed.canonical)
    if parsed.structured:
        add(parsed.canonical.replace("-", ""))
        # 0 패딩 편차: 4자리로 맞춘 형태도 후보에 넣는다(조회 키일 뿐, 답이 아니다)
        if parsed.serial and parsed.serial.isdigit() and len(parsed.serial) < 4:
            padded = parsed.serial.zfill(4)
            add(parsed.canonical[: -len(parsed.serial)] + padded)
    add(_fold(_HIGHLIGHT.sub("", str(raw or ""))))
    return out


def looks_like_document_number(raw: str | None) -> bool:
    """입력이 문서번호로 보이는지 — 라우팅 판단에 쓴다."""
    s = _fold(str(raw or ""))
    if not s or not re.search(r"\d", s):
        return False
    if parse_doc_number(s).structured:
        return True
    return bool(re.match(r"^(사전|서면|기준|고시|적부|이의|심사|심판|조심|감사)\s*[-\s]?\s*\d", s))
