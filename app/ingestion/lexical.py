"""낱말 검색(BM25) — 벡터가 놓치는 **글자 그대로의 일치**를 잡는다.

### 왜 벡터만으로는 모자란가

사용자는 `api등록절차 검색해줘` 처럼 친다. 임베딩으로 재면 0.880 이라 임계값(0.90)을 못
넘어 **검수해 둔 답변이 있는데도 안 나간다**(2026-10-06 측정). 어투·띄어쓰기가 거칠수록
벡터는 멀어지는데, 낱말로 보면 `등록`·`절차` 가 그대로 겹친다.

반대도 있다. 무관한 질문(`라면 먹고 싶어`)에 벡터는 0.538 쯤을 주지만 — 낮아 보여도 그
숫자만으로는 "조금 관련 있음"과 구분되지 않는다 — 낱말 점수는 **정확히 0** 이다.

둘은 서로의 약점을 덮는다. 그래서 둘 다 쓰고, 순위를 합친다(`rrf()`).

### 한국어를 형태소 분석기 없이 다루는 법

조사가 붙어 `등록절차를` 과 `등록절차` 가 다른 낱말이 된다. 분석기를 들이면 사전과 런타임이
하나 더 늘어난다. 대신 **2·3글자 묶음을 전부 만든다** — `등록절차` 가 `등록`·`록절`·`절차`·
`등록절`·`록절차` 로 쪼개져, 조사가 붙든 띄어쓰기가 없든 겹치는 조각이 남는다.

4글자 이상은 만들지 않는다. 색인만 커지고 겹침은 거의 늘지 않는다.

### 질문투는 버린다

`어떻게`·`알려줘` 같은 말은 어느 FAQ 문단에나 들어 있어서, 남겨 두면 **질문의 내용이 아니라
질문의 말투로** 문단을 고르게 된다. 어절 전체가 상투어와 같을 때만 버린다 — `방법론` 안의
`방법` 까지 버리면 뜻이 사라진다.
"""

import math
import re
from collections import Counter

# 한글 덩어리와 영문·숫자 덩어리만 남긴다. 공백·기호는 구분자다.
_CHUNK = re.compile(r"[가-힣]+|[A-Za-z0-9_]+")
_LATIN = re.compile(r"^[A-Za-z0-9_]+$")

# 어절 **전체**가 이것과 같을 때만 버린다.
#
# 뒤쪽 두 줄은 우리 사용자가 실제로 치는 말이다. 이것을 넣기 전에는 `api등록절차 검색해줘`
# 의 '검색' 이 엉뚱한 QA('내가 등록한 API만 모아서 보려면')와 겹쳐 1위를 뺏었다.
STOPWORDS = frozenset("""
뭐야 머야 뭔가요 뭐예요 뭐죠 무엇 무엇인가요 무엇이고 뭐 머
어디 어디서 어디에 언제 왜 누가 누구 누구한테 누구인가요
어떻게 어떤 어떡해 어케 어케해
하나요 있나요 되나요 보나요 인가요 가요 나요 까요 합니다 입니다 됩니다 해요 돼요
알려줘 알려주세요 해주세요 주세요 알려 알려줄래 말해줘
검색 검색해 검색해줘 검색해주세요 찾아 찾아줘 찾아주세요 찾기
보여줘 보여주세요 설명 설명해 설명해줘 정리 정리해 정리해줘
관련 관련된 대해 대한 문서 자료 파일 내용 정보
""".split())

K1 = 1.2
B = 0.75
# 묶음을 만드는 길이. 4글자 이상은 색인만 키운다.
_NGRAMS = (2, 3)


def tokenize(text: str) -> list[str]:
    """질문과 문서에 **같은 규칙**을 쓴다. 한쪽만 바꾸면 예외 없이 점수만 어긋난다."""
    out: list[str] = []
    for chunk in _CHUNK.findall(text or ""):
        if _LATIN.match(chunk):
            out.append(chunk.lower())
            continue
        if len(chunk) <= 1 or chunk in STOPWORDS:
            continue
        out.append(chunk)
        for n in _NGRAMS:
            # 어절 자신과 같은 길이의 묶음은 만들지 않는다. 만들면 `서비스` 가 어절로
            # 한 번, 3글자 묶음으로 또 한 번 세어져 **tf 가 두 배**가 된다. 그 상태로
            # 기준값을 재면 짧은 낱말이 든 문서가 과대평가된다.
            if len(chunk) <= n:
                continue
            for i in range(len(chunk) - n + 1):
                out.append(chunk[i:i + n])
    return out


class Bm25Index:
    """`doc_id → 본문` 을 받아 점수를 매긴다. 외부 검색엔진 없이 메모리에서 돈다.

    규모: 조각 2만 건까지는 전수 비교로 충분하다(원 구현의 운영 실측). 그 위로 가면
    역색인을 만들거나 검색엔진을 들여야 한다.
    """

    def __init__(self, documents: dict[str, str]):
        self.ids: list[str] = list(documents)
        self._tf: dict[str, Counter] = {i: Counter(tokenize(documents[i])) for i in self.ids}
        self._len: dict[str, int] = {i: sum(self._tf[i].values()) for i in self.ids}
        self._avg = (sum(self._len.values()) / len(self.ids)) if self.ids else 0.0
        self._df: Counter = Counter()
        for counts in self._tf.values():
            self._df.update(counts.keys())
        self._n = len(self.ids)
        # 낱말 하나가 어느 문서에 있는지 미리 뒤집어 둔다. 질문 낱말이 든 문서만 보면
        # 되므로, 문서가 늘어도 질문 하나의 비용은 거의 그대로다.
        self._postings: dict[str, list[str]] = {}
        for doc_id, counts in self._tf.items():
            for term in counts:
                self._postings.setdefault(term, []).append(doc_id)

    def __len__(self) -> int:
        return self._n

    def search(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        """`[(doc_id, 점수)]`, 점수 내림차순. **0점은 돌려주지 않는다** — 0은 '못 찾음'이지
        '꼴찌'가 아니고, 순위 합산에서 그 둘을 섞으면 무관한 문서가 점수를 받는다."""
        if not self._n:
            return []

        scores: dict[str, float] = {}
        for term in tokenize(query):
            docs = self._postings.get(term)
            if not docs:
                continue
            idf = math.log(1 + (self._n - self._df[term] + 0.5) / (self._df[term] + 0.5))
            for doc_id in docs:
                freq = self._tf[doc_id][term]
                norm = 1 - B + B * (self._len[doc_id] / self._avg if self._avg else 1.0)
                scores[doc_id] = scores.get(doc_id, 0.0) + idf * freq * (K1 + 1) / (freq + K1 * norm)

        ranked = sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
        return ranked[:top_k]


def rrf(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    """여러 순위를 하나로 합친다 (Reciprocal Rank Fusion).

    점수를 직접 더하지 않는 이유: 코사인(0~1)과 BM25(상한 없음)는 자릿수가 다르다. 가중치를
    맞춰 놔도 **문서가 늘면 BM25 분포가 바뀌어** 다시 어긋난다. 순위만 쓰면 그 일이 없다.

    목록에 없는 문서는 그 순위에서 **점수를 받지 않는다**. 꼴찌로 넣으면 한쪽에서만 걸린
    문서가 가만히 있다가 점수를 얻는다.
    """
    out: dict[str, float] = {}
    for ranking in rankings:
        for position, doc_id in enumerate(ranking, start=1):
            out[doc_id] = out.get(doc_id, 0.0) + 1.0 / (k + position)
    return out
