from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models import Dataset, EvaluationData
from app.schemas.vector_retrieval import (
    VectorCollectionResponse,
    VectorIndexResponse,
    VectorRetrievalEvaluateRequest,
    VectorRetrievalEvaluateResponse,
    VectorRetrievalQueryResponse,
    VectorRetrievalSite,
)
from app.services.vector_retrieval import (
    RerankClient,
    VectorRetrievalConfigError,
    VectorRetrievalExternalError,
    VikingDBCollectionClient,
    VikingDBRetrievalClient,
    apply_truncation,
    build_retrieval_query,
    build_text_retrieval_query,
    parse_scalar_filter,
    rerank_candidates,
)
from app.utils import get_tos_client

router = APIRouter(prefix="/vector-retrieval", tags=["向量检索评估"])


def _build_post_process_ops_from_tags(tags: list[str]) -> list[dict] | None:
    clean_tags = [tag.strip() for tag in tags if tag and tag.strip()]
    if not clean_tags:
        return None
    return [
        {
            "op": "string_contain",
            "field": "des",
            "pattern": tag,
        }
        for tag in clean_tags
    ]


@router.get(
    "/collections",
    response_model=list[VectorCollectionResponse],
    summary="查询 VikingDB Collection 列表",
)
def list_vector_collections(site: VectorRetrievalSite = "byteplus", keyword: str | None = None):
    try:
        collections = VikingDBCollectionClient(site=site).list_collections(keyword=keyword)
    except VectorRetrievalConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"查询 VikingDB Collection 失败: {exc}"
        ) from exc
    return [VectorCollectionResponse(**collection.to_dict()) for collection in collections]


@router.get(
    "/indexes",
    response_model=list[VectorIndexResponse],
    summary="查询指定 Collection 的 VikingDB Index 列表",
)
def list_vector_indexes(collection_name: str, site: VectorRetrievalSite = "byteplus"):
    try:
        indexes = VikingDBCollectionClient(site=site).list_indexes(collection_name=collection_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VectorRetrievalConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"查询 VikingDB Index 失败: {exc}"
        ) from exc
    return [VectorIndexResponse(**index.to_dict()) for index in indexes]


@router.post(
    "/evaluate", response_model=VectorRetrievalEvaluateResponse, summary="执行向量检索评估"
)
def evaluate_vector_retrieval(
    request: VectorRetrievalEvaluateRequest,
    db: Session = Depends(get_db),
):
    try:
        scalar_filter = parse_scalar_filter(request.scalar_filter)
        post_process_ops = _build_post_process_ops_from_tags(request.filter_tags)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        if request.collection_name and request.query:
            retrieval_query = build_text_retrieval_query(request.query)
            collection_name = request.collection_name
            index_name = request.index_name
        else:
            if request.dataset_id is None:
                raise ValueError("必须提供 collection_name + query，或提供兼容旧链路的 dataset_id")
            dataset = db.query(Dataset).filter(Dataset.id == request.dataset_id).first()
            if not dataset:
                raise HTTPException(status_code=404, detail="评测集不存在")

            sample_query = db.query(EvaluationData).filter(
                EvaluationData.dataset_id == request.dataset_id
            )
            if request.data_id is not None:
                sample_query = sample_query.filter(EvaluationData.id == request.data_id)

            sample = sample_query.order_by(EvaluationData.created_at.asc()).first()
            if not sample:
                detail = (
                    "指定评测数据不存在"
                    if request.data_id is not None
                    else "评测集没有可用于检索的评测数据"
                )
                raise HTTPException(
                    status_code=404 if request.data_id is not None else 400, detail=detail
                )

            tos_client = get_tos_client()
            object_url = tos_client.get_download_url(sample.tos_key, public_endpoint=True)
            retrieval_query = build_retrieval_query(sample, object_url)
            collection_name = None
            index_name = None

        search_client = VikingDBRetrievalClient(site=request.site)
        search_results = search_client.search(
            query=retrieval_query,
            top_k=request.top_k,
            scalar_filter=scalar_filter,
            collection_name=collection_name,
            index_name=index_name,
            post_process_ops=post_process_ops,
        )
        search_results_payload = [candidate.to_dict() for candidate in search_results]

        rerank_scores = RerankClient().rerank(
            retrieval_query,
            search_results,
            rerank_model=request.rerank_model,
        )
        rerank_results = rerank_candidates(search_results, rerank_scores)

        settings = get_settings()
        min_score = (
            request.min_score
            if request.min_score is not None
            else settings.vector_retrieval_rerank_min_score
        )
        step_delta_threshold = (
            request.step_delta_threshold
            if request.step_delta_threshold is not None
            else settings.vector_retrieval_step_delta_threshold
        )
        truncated_results = apply_truncation(
            rerank_results,
            min_score=min_score,
            step_delta_threshold=step_delta_threshold,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VectorRetrievalConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VectorRetrievalExternalError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"向量检索评估失败: {exc}") from exc

    rerank_results_payload = [candidate.to_dict() for candidate in rerank_results]
    final_results_payload = [
        candidate.to_dict() for candidate in truncated_results if candidate.kept
    ]
    truncate_reason = next(
        (candidate.truncate_reason for candidate in truncated_results if candidate.truncate_reason),
        None,
    )

    return VectorRetrievalEvaluateResponse(
        site=request.site,
        dataset_id=request.dataset_id,
        collection_name=request.collection_name,
        index_name=index_name,
        query=VectorRetrievalQueryResponse(
            data_id=retrieval_query.data_id,
            file_name=retrieval_query.file_name,
            file_type=retrieval_query.file_type,
            tos_key=retrieval_query.tos_key,
            tos_bucket=retrieval_query.tos_bucket,
            object_url=retrieval_query.object_url,
            multimodal_input=retrieval_query.multimodal_input,
        ),
        top_k=request.top_k,
        rerank_model=request.rerank_model,
        scalar_filter=scalar_filter,
        post_process_ops=post_process_ops,
        min_score=min_score,
        step_delta_threshold=step_delta_threshold,
        search_results=search_results_payload,
        rerank_results=rerank_results_payload,
        final_results=final_results_payload,
        truncated=truncate_reason is not None,
        truncate_reason=truncate_reason,
    )
