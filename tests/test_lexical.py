"""낱말 검색(BM25) — 벡터가 놓치는 글자 그대로의 일치.

여기서 지키는 것은 점수의 절댓값이 아니라 **순서와 0** 이다. 기준값은 실측으로 정하므로
숫자를 고정해 두면 문서가 바뀔 때마다 테스트가 거짓으로 깨진다. 대신 "맞는 것이 위에 온다"
와 "무관한 것은 0" 을 지킨다 — 이 둘이 무너지면 하이브리드 전체가 의미를 잃는다.
"""

from app.ingestion.lexical import Bm25Index, rrf, tokenize

DOCS = {
    "register": "API 등록부터 운영 배포까지 전체 절차 API 등록 절차 알려줘 API 등록 절차 검색해줘",
    "deploy": "TB 배포는 어떻게 하나요 TB 배포 승인은 누가 하나요 TB 배포 절차",
    "mine": "내가 등록한 API만 모아서 보려면 어떻게 하나요 내 API 목록 조회",
}


def test_josa_and_spacing_do_not_hide_a_match():
    """`등록절차를` 과 `등록 절차` 가 겹쳐야 한다.

    형태소 분석기 없이 2·3글자 묶음으로 조사를 흡수한다. 이게 안 되면 사용자가 띄어쓰기를
    틀릴 때마다 답이 사라진다 — 가장 흔한 입력이다.
    """
    tokens = set(tokenize("api등록절차를"))

    assert "등록" in tokens and "절차" in tokens
    assert "api" in tokens, "영문은 소문자 한 덩이로 둔다"


def test_a_word_is_not_counted_twice_as_its_own_ngram():
    """`서비스`(3글자)가 어절로 한 번, 3글자 묶음으로 또 한 번 세어지면 안 된다.

    두 배로 세면 짧은 낱말이 든 문서가 과대평가되고, 그 상태로 기준값을 재면 그 왜곡이
    설정값에 그대로 굳는다. 원 구현이 '알려진 한계'로 적어 둔 항목이다.
    """
    assert tokenize("서비스").count("서비스") == 1
    assert tokenize("배포").count("배포") == 1


def test_question_words_are_dropped_only_when_they_are_the_whole_word():
    """`어떻게` 는 버리고 `방법론` 안의 `방법` 은 남긴다.

    질문투를 남기면 질문의 **내용이 아니라 말투로** 문단을 고르게 된다. 반대로 부분까지
    버리면 뜻이 사라진다.
    """
    assert "어떻게" not in tokenize("어떻게 하나요")
    assert "방법론" in tokenize("방법론")


def test_a_rough_query_still_finds_the_right_entry():
    """`api등록절차 검색해줘` 처럼 거칠게 쳐도 맞는 쪽이 1위여야 한다.

    이 질문이 벡터로는 0.880 이라 임계값(0.90)을 못 넘는다(2026-10-06 측정). 낱말 쪽이
    그 자리를 메운다. `검색해줘` 가 상투어로 빠지지 않으면 '검색' 이 엉뚱한 항목과 겹쳐
    1위를 뺏는다 — 실제로 겪은 일이라 여기서 지킨다.
    """
    hits = Bm25Index(DOCS).search("api등록절차 검색해줘")

    assert hits and hits[0][0] == "register", hits


def test_unrelated_questions_score_exactly_zero():
    """무관한 질문은 **0점**이다. 벡터는 0.5 언저리를 주어 '조금 관련 있음'과 구분이 안 된다."""
    assert Bm25Index(DOCS).search("라면 먹고 싶어") == []


def test_an_empty_index_answers_without_blowing_up():
    """자료를 올리기 전의 설치. 빈 결과를 줘야 하고 예외를 내면 안 된다."""
    assert Bm25Index({}).search("아무 질문") == []


def test_rrf_prefers_what_both_rankings_agree_on():
    """두 순위가 모두 위에 둔 것이 이긴다.

    점수를 직접 더하지 않는 이유는 코사인과 BM25의 자릿수가 다르기 때문이다. 순위만 쓰면
    문서가 늘어 BM25 분포가 바뀌어도 규칙이 그대로다.
    """
    merged = rrf([["b", "a", "c"], ["a", "b"]])

    assert merged["a"] > merged["c"] and merged["b"] > merged["c"]
    # 한쪽에만 있는 것은 그 순위에서만 점수를 받는다 — 꼴찌로 끼워 넣지 않는다.
    assert "c" in merged and merged["c"] == 1 / (60 + 3)
