"""검색 파이프라인 — 세 갈래 분기가 이 서비스 동작의 전부다."""

import pytest

from app.core.question_log import read_question_logs
from app.core.runtime_config import RuntimeConfig, save_runtime_config
from app.ingestion.doc_index import DocIndex
from app.models.schemas import AskRequest
from app.pipeline.retrieve import Retriever
from app.qa import store as qa_store
from app.qa.index import QaIndex


def make_qa(question, answer="등록 화면에서 진행합니다.", status="approved", variants=None, **kw):
    item = qa_store.QaItem(
        qa_id=qa_store.new_qa_id(), question=question, answer=answer,
        variants=variants or [], status=status, **kw,
    )
    qa_store.upsert_item(item)
    QaIndex().upsert_item(item)
    return item


def write_doc(settings, name, body):
    path = settings.raw_docs_dir + f"/{name}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    DocIndex().ingest_file(__import__("pathlib").Path(path), force=True)


@pytest.fixture
def thresholds():
    def _set(match=0.90, floor=0.55):
        save_runtime_config(RuntimeConfig(
            qa_match_threshold=match, related_docs_floor=floor,
            related_docs_count=3, qa_top_k=10, doc_top_k=10,
        ))
    return _set


def test_exact_question_returns_answer(thresholds):
    thresholds()
    item = make_qa("API 등록은 어떻게 하나요?")

    response = Retriever().ask(AskRequest(question="API 등록은 어떻게 하나요?"))

    assert response.result_type == "answer"
    assert response.answer == item.answer
    assert response.matched_qa_id == item.qa_id


def test_variant_question_matches_same_answer(thresholds):
    thresholds()
    item = make_qa("API 등록은 어떻게 하나요?", variants=["API 등록 절차 알려주세요"])

    response = Retriever().ask(AskRequest(question="API 등록 절차 알려주세요"))

    assert response.result_type == "answer"
    assert response.matched_qa_id == item.qa_id


def test_unapproved_qa_never_reaches_user(thresholds):
    """검수를 통과하지 않은 초안이 사용자에게 새어 나가면 안 된다."""
    thresholds()
    make_qa("API 등록은 어떻게 하나요?", status="pending")

    response = Retriever().ask(AskRequest(question="API 등록은 어떻게 하나요?"))

    assert response.result_type != "answer"


def test_approving_puts_item_into_index(thresholds):
    thresholds()
    item = make_qa("API 등록은 어떻게 하나요?", status="pending")
    assert QaIndex().count() == 0

    qa_store.set_status({item.qa_id}, "approved")
    QaIndex().upsert_item(qa_store.get_item(item.qa_id))

    assert Retriever().ask(AskRequest(question="API 등록은 어떻게 하나요?")).result_type == "answer"


def test_falls_back_to_related_docs(isolated_data, thresholds):
    # QA는 못 맞추지만 문서는 걸리는 구간
    thresholds(match=0.99, floor=0.10)
    make_qa("템플릿을 어떻게 수정하나요?")
    write_doc(isolated_data, "api-등록", "---\ntitle: API 등록\n---\n\n## 등록 준비\n\nAPI 그룹을 먼저 만듭니다.\n")

    response = Retriever().ask(AskRequest(question="API 등록은 어떻게 하나요?"))

    assert response.result_type == "related_docs"
    assert response.related_docs
    assert response.related_docs[0].chunk_id


def test_unresolved_when_nothing_matches(thresholds):
    thresholds(match=0.99, floor=0.98)
    make_qa("템플릿을 어떻게 수정하나요?")

    response = Retriever().ask(AskRequest(question="점심 메뉴 추천해 주세요"))

    assert response.result_type == "unresolved"
    assert response.ticket_id.startswith("TCK-")


def test_related_docs_respects_count(isolated_data, thresholds):
    thresholds(match=0.99, floor=0.0)
    body = "---\ntitle: 안내\n---\n\n" + "\n".join(
        f"## 절 {n}\n\n내용 {n} 입니다.\n" for n in range(6)
    )
    write_doc(isolated_data, "안내", body)

    response = Retriever().ask(AskRequest(question="내용"))

    assert len(response.related_docs) == 3


def test_question_is_logged_with_result_type(thresholds):
    thresholds()
    make_qa("API 등록은 어떻게 하나요?")
    Retriever().ask(AskRequest(question="API 등록은 어떻게 하나요?"))

    items, total = read_question_logs()

    assert total == 1
    assert items[0].result_type == "answer"
    assert items[0].similarity is not None


def test_test_channel_is_excluded_from_stats(thresholds):
    thresholds()
    make_qa("API 등록은 어떻게 하나요?")
    Retriever().ask(AskRequest(question="API 등록은 어떻게 하나요?", channel="auto"))

    _, visible = read_question_logs()
    _, everything = read_question_logs(include_test=True)

    assert visible == 0
    assert everything == 1


def test_hit_count_increases_on_match(thresholds):
    thresholds()
    item = make_qa("API 등록은 어떻게 하나요?")
    Retriever().ask(AskRequest(question="API 등록은 어떻게 하나요?"))

    assert qa_store.get_item(item.qa_id).hit_count == 1


def test_deleted_variant_stops_matching(thresholds):
    """변형 질문을 지웠는데 벡터가 남아 계속 걸리면, 검수자가 고쳐도 동작이 안 바뀐다."""
    thresholds()
    item = make_qa("템플릿 수정 방법", variants=["API 등록은 어떻게 하나요?"])
    assert Retriever().ask(AskRequest(question="API 등록은 어떻게 하나요?")).result_type == "answer"

    item.variants = []
    qa_store.upsert_item(item)
    QaIndex().upsert_item(item)

    assert Retriever().ask(AskRequest(question="API 등록은 어떻게 하나요?")).result_type != "answer"


def test_support_records_unresolved():
    response = Retriever().record_support(AskRequest(question="권한그룹 값이 궁금합니다"))

    items, total = read_question_logs()
    assert response.result_type == "unresolved"
    assert total == 1
    assert items[0].ticket_id == response.ticket_id
