"""생성 결과가 한국어인지 판정한다.

프롬프트로 "한국어로만 쓰라"고 해도 4B~8B 다국어 모델은 영어 문장이나 중국어 조각을 섞어
내보낸다(1차 프로젝트 3-4). 그런 항목이 QA 인덱스에 들어가면 검수자가 하나씩 지워야 하고,
못 보고 지나가면 사용자에게 그대로 나간다.

한글 '비율'로 재면 `OAS 3.0 Swagger YAML 등록` 같은 명사 나열형 질문이 억울하게 걸린다.
그래서 세 가지만 본다.

1. 다른 CJK(중국어·일본어 가나)가 섞였는가 — 소형 모델이 가장 흔하게 흘리는 문자다
2. 한글이 하나도 없는가
3. 영어 기능어가 여럿 나오는가(= 영어 '문장'이다). 고유명사(OAS, Swagger, Path)는
   기능어를 동반하지 않으므로 살아남는다

1차 프로젝트(`app/eval/question_gen.py`)에서 그대로 가져왔다. 거기서 실제로 걸러낸 실적이 있다.
"""

import re

_HANGUL = re.compile(r"[가-힣]")
_OTHER_CJK = re.compile(r"[぀-ヿ一-鿿]")
_ENGLISH_FUNCTION_WORDS = re.compile(
    r"\b(?:the|is|are|was|were|how|what|which|do|does|did|can|could|should|"
    r"you|your|i|we|they|of|and|for|with|from|to|in|on|at|it|this|that)\b",
    re.IGNORECASE,
)
_ENGLISH_SENTENCE_HITS = 3


def is_korean(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if _OTHER_CJK.search(stripped):
        return False
    if not _HANGUL.search(stripped):
        return False
    return len(_ENGLISH_FUNCTION_WORDS.findall(stripped)) < _ENGLISH_SENTENCE_HITS


def is_expected_language(text: str, language: str) -> bool:
    """납품처 언어(`data/profile.json`)에 맞는 결과인가.

    판정기가 있는 언어는 실제로 거르고, **없는 언어는 통과시킨다.** 한국어 판정을 그대로
    들이대면 한국어가 아닌 조직에서는 초안이 전부 버려지고 "완료, 0건"으로 끝난다 —
    예외가 나지 않아 원인을 찾는 데 가장 오래 걸리는 종류의 실패다. 거르지 못하는 것보다
    아무것도 만들지 못하는 쪽이 나쁘다. 새 언어의 판정기가 생기면 여기에 분기를 더한다.
    """
    if language == "ko":
        return is_korean(text)
    return bool(text.strip())
