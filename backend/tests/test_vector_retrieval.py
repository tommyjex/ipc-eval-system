from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import vector_retrieval as vector_retrieval_api
from app.core.database import get_db
from app.models import Dataset, EvaluationData
from app.models.base import Base
from app.services import vector_retrieval as vector_retrieval_service
from app.services.vector_retrieval import (
    RerankClient,
    RetrievalCandidate,
    RetrievalQuery,
    VectorCollection,
    VectorIndex,
    VectorRetrievalConfigError,
    _extract_result_items,
    _validate_vikingdb_config,
    apply_truncation,
    normalize_search_candidate,
    parse_scalar_filter,
    rerank_candidates,
)

SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _candidate(object_id: str, score: float) -> RetrievalCandidate:
    return RetrievalCandidate(
        object_id=object_id,
        object_name=f"{object_id}.jpg",
        object_url=f"https://example.com/{object_id}.jpg",
        metadata={},
        search_score=score,
    )


def test_parse_scalar_filter_accepts_json_string():
    parsed = parse_scalar_filter('{"scene":"pet","score":{"$gte":0.8}}')

    assert parsed == {"scene": "pet", "score": {"$gte": 0.8}}


def test_parse_scalar_filter_rejects_non_object_json():
    with pytest.raises(ValueError, match="JSON 对象"):
        parse_scalar_filter('["scene"]')


def test_vikingdb_config_missing_fields_has_clear_error():
    settings = SimpleNamespace(
        vikingdb_host="host",
        vikingdb_region=None,
        vikingdb_collection="collection",
        vikingdb_index="index",
        vikingdb_access_key="ak",
        vikingdb_secret_key=None,
    )

    with pytest.raises(VectorRetrievalConfigError, match="vikingdb_region, vikingdb_secret_key"):
        _validate_vikingdb_config(settings)


def test_normalize_search_candidate_reads_vikingdb_fields_name():
    candidate = SimpleNamespace(
        id="object-1",
        fields={"name": "sample.mp4", "des": "sample description"},
        score=0.42,
    )

    normalized = normalize_search_candidate(candidate, rank=1)

    assert normalized.object_id == "object-1"
    assert normalized.object_name == "sample.mp4"
    assert normalized.metadata["des"] == "sample description"
    assert normalized.search_score == 0.42


def test_extract_result_items_reads_vikingdb_search_response_shape():
    item = SimpleNamespace(id="object-1")
    response = SimpleNamespace(result=SimpleNamespace(data=[item]))

    assert _extract_result_items(response) == [item]


def test_rerank_candidates_orders_by_score_desc():
    candidates = [_candidate("a", 0.9), _candidate("b", 0.8), _candidate("c", 0.7)]

    ranked = rerank_candidates(candidates, [0.2, 0.95, 0.5])

    assert [candidate.object_id for candidate in ranked] == ["b", "c", "a"]
    assert [candidate.rerank_rank for candidate in ranked] == [1, 2, 3]


def test_vector_collection_list_api_uses_vikingdb_collections(monkeypatch):
    class FakeCollectionClient:
        def list_collections(self, keyword=None):
            assert keyword == "ipc"
            return [
                VectorCollection(
                    collection_name="ipc_eval",
                    resource_id="resource-1",
                    data_count=215,
                    index_names=["ipc_eval_index"],
                )
            ]

    monkeypatch.setattr(
        vector_retrieval_api, "VikingDBCollectionClient", lambda: FakeCollectionClient()
    )

    app = FastAPI()
    app.include_router(vector_retrieval_api.router, prefix="/api")
    client = TestClient(app)

    response = client.get("/api/vector-retrieval/collections", params={"keyword": "ipc"})

    assert response.status_code == 200
    assert response.json() == [
        {
            "collection_name": "ipc_eval",
            "resource_id": "resource-1",
            "description": None,
            "data_count": 215,
            "index_names": ["ipc_eval_index"],
        }
    ]


def test_vector_index_list_api_uses_selected_collection(monkeypatch):
    class FakeCollectionClient:
        def list_indexes(self, collection_name):
            assert collection_name == "ipc_eval"
            return [
                VectorIndex(
                    collection_name="ipc_eval",
                    index_name="ipc_eval_index",
                    resource_id="index-resource-1",
                    status="Ready",
                    project_name="default",
                )
            ]

    monkeypatch.setattr(
        vector_retrieval_api, "VikingDBCollectionClient", lambda: FakeCollectionClient()
    )

    app = FastAPI()
    app.include_router(vector_retrieval_api.router, prefix="/api")
    client = TestClient(app)

    response = client.get(
        "/api/vector-retrieval/indexes",
        params={"collection_name": "ipc_eval"},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "collection_name": "ipc_eval",
            "index_name": "ipc_eval_index",
            "resource_id": "index-resource-1",
            "description": None,
            "status": "Ready",
            "project_name": "default",
        }
    ]


def test_rerank_client_uses_viking_knowledge_sdk(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        vector_retrieval_service,
        "get_settings",
        lambda: SimpleNamespace(
            vikingdb_knowledge_host="api-knowledgebase.mlp.ap-southeast-1.bytepluses.com",
            vikingdb_region="ap-southeast-1",
            vikingdb_access_key="ak",
            vikingdb_secret_key="sk",
            rerank_model="m3-v2-rerank",
            rerank_instruction=None,
            rerank_endpoint_id=None,
            rerank_timeout=30,
        ),
    )

    class FakeKnowledgeClient:
        def rerank(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(result=SimpleNamespace(scores=[0.7, 0.9]))

    def fake_factory(**kwargs):
        captured["client_kwargs"] = kwargs
        return FakeKnowledgeClient()

    query = RetrievalQuery(
        data_id=11,
        file_name="query.jpg",
        file_type="jpg",
        tos_key="datasets/1/query.jpg",
        tos_bucket="bucket",
        object_url="https://example.com/query.jpg",
        multimodal_input={"image_url": "https://example.com/query.jpg"},
    )

    scores = RerankClient(client_factory=fake_factory).rerank(
        query,
        [_candidate("a", 0.9), _candidate("b", 0.8)],
        rerank_model="base-multilingual-rerank",
    )

    assert scores == [0.7, 0.9]
    assert (
        captured["client_kwargs"]["host"] == "api-knowledgebase.mlp.ap-southeast-1.bytepluses.com"
    )
    assert len(captured["datas"]) == 2
    assert captured["rerank_model"] == "base-multilingual-rerank"
    assert captured["timeout"] == 30


def test_apply_truncation_by_low_score_marks_tail():
    candidates = rerank_candidates(
        [_candidate("a", 0.9), _candidate("b", 0.8), _candidate("c", 0.7)], [0.91, 0.4, 0.3]
    )

    truncated = apply_truncation(candidates, min_score=0.5, step_delta_threshold=None)

    assert [candidate.kept for candidate in truncated] == [True, False, False]
    assert truncated[1].truncate_reason == "low_score<0.5"
    assert truncated[2].truncate_reason == "low_score<0.5"


def test_apply_truncation_by_step_delta_marks_after_gap():
    candidates = rerank_candidates(
        [_candidate("a", 0.9), _candidate("b", 0.8), _candidate("c", 0.7)], [0.95, 0.6, 0.59]
    )

    truncated = apply_truncation(candidates, min_score=None, step_delta_threshold=0.3)

    assert [candidate.kept for candidate in truncated] == [True, False, False]
    assert truncated[1].truncate_reason == "step_delta>=0.3"


def test_vector_retrieval_api_uses_mocked_search_rerank_and_truncation(monkeypatch):
    db = TestingSessionLocal()
    try:
        dataset = Dataset(
            id=1,
            name="向量评测集",
            type="image",
            status="ready",
        )
        sample = EvaluationData(
            id=11,
            dataset_id=1,
            file_name="query.jpg",
            file_type="jpg",
            file_size=123,
            tos_key="datasets/1/image/query.jpg",
            tos_bucket="bucket",
            status="pending",
        )
        db.add(dataset)
        db.add(sample)
        db.commit()
    finally:
        db.close()

    class FakeTOSClient:
        def get_download_url(self, object_key, public_endpoint=False):
            assert public_endpoint is True
            return f"https://tos.example.com/{object_key}"

    class FakeSearchClient:
        def search(
            self,
            query,
            top_k,
            scalar_filter=None,
            collection_name=None,
            index_name=None,
            post_process_ops=None,
        ):
            assert query.multimodal_input == {
                "image_url": "https://tos.example.com/datasets/1/image/query.jpg"
            }
            assert top_k == 3
            assert scalar_filter == {"scene": "pet"}
            assert collection_name is None
            assert index_name is None
            assert post_process_ops is None
            return [_candidate("a", 0.9), _candidate("b", 0.8), _candidate("c", 0.7)]

    class FakeRerankClient:
        def rerank(self, query, candidates, rerank_model=None):
            assert query.data_id == 11
            assert len(candidates) == 3
            assert rerank_model == "base-multilingual-rerank"
            return [0.95, 0.61, 0.6]

    monkeypatch.setattr(vector_retrieval_api, "get_tos_client", lambda: FakeTOSClient())
    monkeypatch.setattr(vector_retrieval_api, "VikingDBRetrievalClient", lambda: FakeSearchClient())
    monkeypatch.setattr(vector_retrieval_api, "RerankClient", lambda: FakeRerankClient())
    monkeypatch.setattr(
        vector_retrieval_api,
        "get_settings",
        lambda: SimpleNamespace(
            vector_retrieval_rerank_min_score=None,
            vector_retrieval_step_delta_threshold=None,
        ),
    )

    app = FastAPI()
    app.include_router(vector_retrieval_api.router, prefix="/api")
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    response = client.post(
        "/api/vector-retrieval/evaluate",
        json={
            "dataset_id": 1,
            "top_k": 3,
            "rerank_model": "base-multilingual-rerank",
            "scalar_filter": {"scene": "pet"},
            "step_delta_threshold": 0.3,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["query"]["data_id"] == 11
    assert data["rerank_model"] == "base-multilingual-rerank"
    assert [item["object_id"] for item in data["rerank_results"]] == ["a", "b", "c"]
    assert [item["object_id"] for item in data["final_results"]] == ["a"]
    assert data["truncated"] is True
    assert data["truncate_reason"] == "step_delta>=0.3"


def test_vector_retrieval_api_supports_text_query_collection_and_filter_tags(monkeypatch):
    class FakeSearchClient:
        def search(
            self,
            query,
            top_k,
            scalar_filter=None,
            collection_name=None,
            index_name=None,
            post_process_ops=None,
        ):
            assert query.multimodal_input == {"text": "person falling"}
            assert top_k == 5
            assert collection_name == "ipc_eval"
            assert index_name == "ipc_eval_index"
            assert scalar_filter is None
            assert post_process_ops == [
                {"op": "string_contain", "field": "des", "pattern": "person"},
                {"op": "string_contain", "field": "des", "pattern": "fall"},
            ]
            return [_candidate("a", 0.9), _candidate("b", 0.8)]

    class FakeRerankClient:
        def rerank(self, query, candidates, rerank_model=None):
            assert query.data_id is None
            assert query.file_name == "person falling"
            assert rerank_model == "m3-v2-rerank"
            return [0.88, 0.66]

    monkeypatch.setattr(vector_retrieval_api, "VikingDBRetrievalClient", lambda: FakeSearchClient())
    monkeypatch.setattr(vector_retrieval_api, "RerankClient", lambda: FakeRerankClient())
    monkeypatch.setattr(
        vector_retrieval_api,
        "get_settings",
        lambda: SimpleNamespace(
            vector_retrieval_rerank_min_score=None,
            vector_retrieval_step_delta_threshold=None,
        ),
    )

    app = FastAPI()
    app.include_router(vector_retrieval_api.router, prefix="/api")
    client = TestClient(app)

    response = client.post(
        "/api/vector-retrieval/evaluate",
        json={
            "collection_name": "ipc_eval",
            "index_name": "ipc_eval_index",
            "query": "person falling",
            "top_k": 5,
            "rerank_model": "m3-v2-rerank",
            "filter_tags": ["person", "fall"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["dataset_id"] is None
    assert data["collection_name"] == "ipc_eval"
    assert data["index_name"] == "ipc_eval_index"
    assert data["post_process_ops"] == [
        {"op": "string_contain", "field": "des", "pattern": "person"},
        {"op": "string_contain", "field": "des", "pattern": "fall"},
    ]
    assert data["query"]["multimodal_input"] == {"text": "person falling"}
    assert [item["object_id"] for item in data["final_results"]] == ["a", "b"]
