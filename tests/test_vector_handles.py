"""벡터 핸들 — **밖에서** 색인을 다시 만들었을 때.

서버는 Chroma 클라이언트를 폴더마다 하나씩 오래 들고 있고(`vector_store.get_client`),
인덱스 객체도 캐시한다(`pipeline.retrieve.get_retriever`). 그 사이 `scripts/pack_index.py`
같은 **별도 프로세스**가 컬렉션을 지우고 새로 만들면 쥐고 있던 컬렉션 id 가 사라진다.

2026-10-07 에 개발 서버에서 겪었다. 자료를 올리고 `docker exec ... pack_index.py` 로
색인했더니 사용자 화면(`/api/drive`)이 **재시작할 때까지 계속 500** 이었다. 색인은 멀쩡히
끝났고 로그에도 오류가 없어서 화면만 보고는 원인을 알 수 없었다.
"""

import base64

import pytest
from chromadb.errors import InvalidCollectionException
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.ingestion import vector_store
from app.main import app
from app.pipeline import retrieve

AUTH = {"Authorization": "Basic " + base64.b64encode(b"tester:secret").decode()}

# 죽은 핸들을 흉내 내는 길. 실제로 다른 프로세스를 띄우는 대신, 그 프로세스가 만들어 내는
# **예외 하나**를 그대로 던진다 — 우리가 지키려는 것은 그 예외를 받았을 때의 행동이다.
_boom = APIRouter()


@_boom.get("/__stale__")
def _raise_stale():
    raise InvalidCollectionException("Collection 00000000 does not exist.")


app.include_router(_boom)


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def test_a_stale_handle_answers_503_with_what_to_do(client, isolated_data):
    """빈 500 이 아니라 **무엇을 하면 되는지** 적어서 돌려준다.

    빈 500 은 화면만 보고 원인을 알 수 없다. 이 프로젝트에서 가장 비싼 종류의 고장이
    '오류는 안 나는데 결과가 틀린 것' 이고, 그다음이 '오류는 나는데 말이 없는 것' 이다.
    """
    response = client.get("/__stale__")

    assert response.status_code == 503
    assert "다시 시도" in response.json()["detail"]


def test_a_stale_handle_drops_the_cached_handles(client, isolated_data):
    """핸들을 **버려야** 한다. 안 버리면 재시작할 때까지 계속 같은 오류가 난다."""
    retrieve.get_retriever()                      # 캐시에 올려 둔다
    vector_store.get_client()
    assert retrieve._retrievers and vector_store._CLIENTS

    client.get("/__stale__")

    assert not retrieve._retrievers, "인덱스 핸들을 버려야 합니다"
    assert not vector_store._CLIENTS, "Chroma 클라이언트를 버려야 합니다"


def test_the_next_request_works_again(client, isolated_data):
    """한 번 삼키고 **다음 요청부터는 살아나야** 한다 — 사람이 재시작하지 않아도."""
    client.get("/__stale__")

    assert client.get("/health/ready").status_code == 200
    assert client.get("/api/drive").status_code == 200
