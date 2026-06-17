from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Literal, Optional

from app.core.config import get_settings

IMAGE_TYPES = {"jpg", "jpeg", "png", "gif", "bmp", "webp"}
VIDEO_TYPES = {"mp4", "avi", "mov", "mkv", "flv", "wmv", "webm"}
VectorRetrievalSite = Literal["byteplus", "volcengine"]
VOLCENGINE_VIKINGDB_CONTROL_HOST = "vikingdb.cn-beijing.volcengineapi.com"
VOLCENGINE_VIKINGDB_DATA_HOST = "api-vikingdb.vikingdb.cn-beijing.volces.com"
VOLCENGINE_VIKINGDB_REGION = "cn-beijing"


class VectorRetrievalConfigError(RuntimeError):
    pass


class VectorRetrievalExternalError(RuntimeError):
    pass


@dataclass
class VikingDBRuntimeConfig:
    site: VectorRetrievalSite
    host: str
    control_host: str
    region: str
    access_key: str
    secret_key: str
    collection: Optional[str] = None
    index: Optional[str] = None


@dataclass
class RetrievalQuery:
    data_id: Optional[int]
    file_name: str
    file_type: str
    tos_key: str
    tos_bucket: str
    object_url: str
    multimodal_input: dict[str, Any]


@dataclass
class VectorCollection:
    collection_name: str
    resource_id: Optional[str] = None
    description: Optional[str] = None
    data_count: Optional[int] = None
    index_names: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "collection_name": self.collection_name,
            "resource_id": self.resource_id,
            "description": self.description,
            "data_count": self.data_count,
            "index_names": self.index_names or [],
        }


@dataclass
class VectorIndex:
    collection_name: str
    index_name: str
    resource_id: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    project_name: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "collection_name": self.collection_name,
            "index_name": self.index_name,
            "resource_id": self.resource_id,
            "description": self.description,
            "status": self.status,
            "project_name": self.project_name,
        }


@dataclass
class RetrievalCandidate:
    object_id: str
    object_name: str
    object_url: Optional[str]
    metadata: dict[str, Any]
    search_score: Optional[float]
    rerank_score: Optional[float] = None
    rank: Optional[int] = None
    rerank_rank: Optional[int] = None
    kept: bool = True
    truncate_reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "object_name": self.object_name,
            "object_url": self.object_url,
            "metadata": self.metadata,
            "search_score": self.search_score,
            "rerank_score": self.rerank_score,
            "rank": self.rank,
            "rerank_rank": self.rerank_rank,
            "kept": self.kept,
            "truncate_reason": self.truncate_reason,
        }


def _missing_fields(config: object, field_names: list[str]) -> list[str]:
    return [field for field in field_names if not getattr(config, field, None)]


def _validate_vikingdb_config(settings: object) -> None:
    missing = _missing_fields(
        settings,
        [
            "vikingdb_host",
            "vikingdb_region",
            "vikingdb_collection",
            "vikingdb_index",
            "vikingdb_access_key",
            "vikingdb_secret_key",
        ],
    )
    if missing:
        raise VectorRetrievalConfigError(f"VikingDB 配置缺失: {', '.join(missing)}")


def _resolve_vikingdb_runtime_config(
    settings: object,
    site: VectorRetrievalSite = "byteplus",
) -> VikingDBRuntimeConfig:
    if site == "volcengine":
        missing = _missing_fields(settings, ["tos_access_key", "tos_secret_key"])
        if missing:
            raise VectorRetrievalConfigError(
                f"火山引擎 VikingDB 配置缺失: {', '.join(missing)}"
            )
        return VikingDBRuntimeConfig(
            site=site,
            host=VOLCENGINE_VIKINGDB_DATA_HOST,
            control_host=VOLCENGINE_VIKINGDB_CONTROL_HOST,
            region=VOLCENGINE_VIKINGDB_REGION,
            access_key=str(getattr(settings, "tos_access_key")),
            secret_key=str(getattr(settings, "tos_secret_key")),
            collection=getattr(settings, "vikingdb_collection", None),
            index=getattr(settings, "vikingdb_index", None),
        )

    if site != "byteplus":
        raise VectorRetrievalConfigError(f"不支持的向量检索站点: {site}")

    missing = _missing_fields(
        settings,
        [
            "vikingdb_host",
            "vikingdb_region",
            "vikingdb_access_key",
            "vikingdb_secret_key",
        ],
    )
    if missing:
        raise VectorRetrievalConfigError(f"BytePlus VikingDB 配置缺失: {', '.join(missing)}")

    return VikingDBRuntimeConfig(
        site=site,
        host=str(getattr(settings, "vikingdb_host")),
        control_host=_resolve_vikingdb_control_host(settings),
        region=str(getattr(settings, "vikingdb_region")),
        access_key=str(getattr(settings, "vikingdb_access_key")),
        secret_key=str(getattr(settings, "vikingdb_secret_key")),
        collection=getattr(settings, "vikingdb_collection", None),
        index=getattr(settings, "vikingdb_index", None),
    )


def _resolve_vikingdb_control_host(settings: object) -> str:
    configured_host = getattr(settings, "vikingdb_control_host", None)
    if configured_host:
        return str(configured_host)

    region = getattr(settings, "vikingdb_region", None)
    if region == "ap-southeast-1":
        return "api-vikingdb.mlp.ap-mya.byteplus.com"
    return str(getattr(settings, "vikingdb_host", "") or "")


def _validate_rerank_config(settings: object) -> None:
    missing = _missing_fields(
        settings,
        [
            "vikingdb_knowledge_host",
            "vikingdb_region",
            "vikingdb_access_key",
            "vikingdb_secret_key",
        ],
    )
    if missing:
        raise VectorRetrievalConfigError(f"Rerank 配置缺失: {', '.join(missing)}")


def build_retrieval_query(sample: Any, object_url: str) -> RetrievalQuery:
    file_type = (sample.file_type or "").lower()
    if file_type in IMAGE_TYPES:
        multimodal_input = {"image_url": object_url}
    elif file_type in VIDEO_TYPES:
        multimodal_input = {"video_url": object_url}
    else:
        raise ValueError(f"当前文件类型不支持向量检索: {sample.file_type}")

    return RetrievalQuery(
        data_id=sample.id,
        file_name=sample.file_name,
        file_type=sample.file_type,
        tos_key=sample.tos_key,
        tos_bucket=sample.tos_bucket,
        object_url=object_url,
        multimodal_input=multimodal_input,
    )


def build_text_retrieval_query(query_text: str) -> RetrievalQuery:
    stripped_query = query_text.strip()
    if not stripped_query:
        raise ValueError("搜索 query 不能为空")
    return RetrievalQuery(
        data_id=None,
        file_name=stripped_query,
        file_type="text",
        tos_key="",
        tos_bucket="",
        object_url="",
        multimodal_input={"text": stripped_query},
    )


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_candidate_field(candidate: Any, names: tuple[str, ...], default: Any = None) -> Any:
    if isinstance(candidate, dict):
        for name in names:
            if name in candidate:
                return candidate[name]
        return default

    for name in names:
        if hasattr(candidate, name):
            return getattr(candidate, name)
    return default


def _first_present(mapping: dict[str, Any], names: tuple[str, ...], default: Any = None) -> Any:
    for name in names:
        if name in mapping:
            return mapping[name]
    return default


def _candidate_to_dict(candidate: Any) -> dict[str, Any]:
    if isinstance(candidate, dict):
        return candidate
    if hasattr(candidate, "model_dump"):
        return candidate.model_dump()
    if hasattr(candidate, "dict"):
        return candidate.dict()
    if hasattr(candidate, "__dict__"):
        return dict(candidate.__dict__)
    return {"raw": str(candidate)}


def normalize_search_candidate(candidate: Any, rank: int) -> RetrievalCandidate:
    raw_metadata = (
        _read_candidate_field(candidate, ("metadata", "fields", "scalar_fields"), {}) or {}
    )
    metadata = raw_metadata if isinstance(raw_metadata, dict) else {"metadata": raw_metadata}
    raw = _candidate_to_dict(candidate)

    object_id = str(
        _read_candidate_field(
            candidate,
            ("id", "object_id", "primary_key", "pk", "tos_key", "key"),
            metadata.get("id") or metadata.get("tos_key") or f"candidate-{rank}",
        )
    )
    object_name = str(
        _read_candidate_field(
            candidate,
            ("object_name", "file_name", "name"),
            metadata.get("file_name")
            or metadata.get("object_name")
            or metadata.get("name")
            or object_id,
        )
    )
    object_url = _read_candidate_field(
        candidate,
        ("object_url", "url", "image_url", "video_url"),
        metadata.get("object_url") or metadata.get("url"),
    )
    search_score = _as_float(_read_candidate_field(candidate, ("score", "distance", "similarity")))

    metadata.setdefault("raw", raw)
    return RetrievalCandidate(
        object_id=object_id,
        object_name=object_name,
        object_url=object_url,
        metadata=metadata,
        search_score=search_score,
        rank=rank,
    )


class VikingDBRetrievalClient:
    def __init__(
        self,
        site: VectorRetrievalSite = "byteplus",
        client_factory: Optional[Callable[..., Any]] = None,
    ):
        self.settings = get_settings()
        self.config = _resolve_vikingdb_runtime_config(self.settings, site)
        self._client_factory = client_factory

    def _create_sdk_client(self) -> Any:
        if self._client_factory:
            return self._client_factory(
                host=self.config.host,
                region=self.config.region,
                ak=self.config.access_key,
                sk=self.config.secret_key,
            )

        try:
            from vikingdb.auth import IAM  # type: ignore
            from vikingdb.vector import VikingVector  # type: ignore
        except ImportError as exc:
            raise VectorRetrievalConfigError(
                "未安装 vikingdb-python-sdk，请执行 python3 -m pip install -U vikingdb-python-sdk"
            ) from exc

        return VikingVector(
            host=self.config.host,
            region=self.config.region,
            auth=IAM(ak=self.config.access_key, sk=self.config.secret_key),
            scheme="https",
        )

    def _resolve_search_target(
        self,
        client: Any,
        collection_name: Optional[str] = None,
        index_name: Optional[str] = None,
    ) -> Any:
        target_collection = collection_name or self.config.collection
        target_index = index_name or self.config.index
        if not target_collection:
            raise VectorRetrievalConfigError("VikingDB Collection 名称不能为空")
        if not target_index:
            raise VectorRetrievalConfigError("VikingDB Index 名称不能为空")
        if hasattr(client, "index"):
            return client.index(
                collection_name=target_collection,
                index_name=target_index,
            )
        if hasattr(client, "get_collection"):
            collection = client.get_collection(target_collection)
            if hasattr(collection, "get_index"):
                return collection.get_index(target_index)
            if hasattr(client, "get_index"):
                return client.get_index(target_collection, target_index)
            return collection
        raise VectorRetrievalConfigError("VikingDB SDK 当前对象不支持获取 Index")

    def search(
        self,
        query: RetrievalQuery,
        top_k: int,
        scalar_filter: Optional[dict[str, Any]] = None,
        collection_name: Optional[str] = None,
        index_name: Optional[str] = None,
        post_process_ops: Optional[list[dict[str, Any]]] = None,
    ) -> list[RetrievalCandidate]:
        client = self._create_sdk_client()
        target = self._resolve_search_target(
            client,
            collection_name=collection_name,
            index_name=index_name,
        )
        if not hasattr(target, "search_by_multi_modal"):
            raise VectorRetrievalConfigError("VikingDB SDK 当前对象不支持 search_by_multi_modal")

        kwargs: dict[str, Any] = {"limit": top_k}
        if scalar_filter:
            kwargs["filter"] = scalar_filter
        if post_process_ops:
            kwargs["post_process_ops"] = post_process_ops

        raw_results: Any = None
        signature_errors: list[TypeError] = []
        call_attempts: tuple[Callable[[], Any], ...]
        try:
            from vikingdb.vector.models.index import SearchByMultiModalRequest  # type: ignore

            call_attempts = (
                lambda: target.search_by_multi_modal(
                    SearchByMultiModalRequest(**query.multimodal_input, **kwargs)
                ),
                lambda: target.search_by_multi_modal(query.multimodal_input | kwargs),
            )
        except ImportError:
            call_attempts = (
                lambda: target.search_by_multi_modal(query.multimodal_input, **kwargs),
                lambda: target.search_by_multi_modal(data=query.multimodal_input, **kwargs),
                lambda: target.search_by_multi_modal(query=query.multimodal_input, **kwargs),
            )
        for call in call_attempts:
            try:
                raw_results = call()
                break
            except TypeError as exc:
                signature_errors.append(exc)
                continue
            except Exception as exc:
                raise VectorRetrievalExternalError(f"VikingDB 检索失败: {exc}") from exc
        else:
            raise VectorRetrievalExternalError(f"VikingDB 检索失败: {signature_errors[-1]}")

        items = _extract_result_items(raw_results)
        return [normalize_search_candidate(item, index + 1) for index, item in enumerate(items)]


class VikingDBCollectionClient:
    def __init__(
        self,
        site: VectorRetrievalSite = "byteplus",
        api_factory: Optional[Callable[[], Any]] = None,
    ):
        self.settings = get_settings()
        self.config = _resolve_vikingdb_runtime_config(self.settings, site)
        self._api_factory = api_factory

    def _create_api_client(self) -> Any:
        if self._api_factory:
            return self._api_factory()

        try:
            import volcenginesdkcore  # type: ignore
            import volcenginesdkvikingdb as vdb  # type: ignore
            from volcenginesdkvikingdb.api.vikingdb_api import VIKINGDBApi  # type: ignore
        except ImportError as exc:
            raise VectorRetrievalConfigError(
                "未安装 volcengine VikingDB SDK，无法查询 Collection 列表"
            ) from exc

        configuration = volcenginesdkcore.Configuration()
        configuration.ak = self.config.access_key
        configuration.sk = self.config.secret_key
        configuration.region = self.config.region
        configuration.host = self.config.control_host
        configuration.scheme = "https"
        volcenginesdkcore.Configuration.set_default(configuration)

        return VIKINGDBApi(), vdb

    def list_collections(
        self, keyword: Optional[str] = None, page_size: int = 100
    ) -> list[VectorCollection]:
        api_client = self._create_api_client()
        if isinstance(api_client, tuple):
            client, vdb = api_client
            filter_obj = (
                vdb.FilterForListVikingdbCollectionInput(collection_name_keyword=keyword)
                if keyword
                else None
            )
            request = vdb.ListVikingdbCollectionRequest(
                project_name="default",
                page_number=1,
                page_size=page_size,
                filter=filter_obj,
            )
            response = client.list_vikingdb_collection(request)
            raw_collections = response.collections or []
        else:
            raw_collections = api_client.list_collections(keyword=keyword, page_size=page_size)

        return [self._normalize_collection(item) for item in raw_collections]

    def list_indexes(self, collection_name: str, page_size: int = 100) -> list[VectorIndex]:
        if not collection_name or not collection_name.strip():
            raise ValueError("Collection 名称不能为空")

        api_client = self._create_api_client()
        if isinstance(api_client, tuple):
            client, vdb = api_client
            filter_obj = self._build_index_filter(vdb, collection_name.strip())
            request = vdb.ListVikingdbIndexRequest(
                project_name="default",
                page_number=1,
                page_size=page_size,
                filter=filter_obj,
            )
            response = client.list_vikingdb_index(request)
            raw_indexes = _read_candidate_field(response, ("indexes", "Indexes"), []) or []
        else:
            raw_indexes = api_client.list_indexes(
                collection_name=collection_name.strip(),
                page_size=page_size,
            )

        indexes = [
            self._normalize_index(item, fallback_collection_name=collection_name.strip())
            for item in raw_indexes
        ]
        return [index for index in indexes if index.collection_name == collection_name.strip()]

    def _build_index_filter(self, vdb: Any, collection_name: str) -> Any:
        filter_cls = getattr(vdb, "FilterForListVikingdbIndexInput", None)
        if filter_cls is None:
            return None

        for kwargs in (
            {"collection_name": [collection_name]},
            {"collection_name": collection_name},
            {"CollectionName": [collection_name]},
        ):
            try:
                return filter_cls(**kwargs)
            except TypeError:
                continue
        raise VectorRetrievalConfigError("VikingDB SDK 当前对象不支持构造 Index 列表过滤条件")

    def _normalize_collection(self, item: Any) -> VectorCollection:
        stats = getattr(item, "collection_stats", None)
        return VectorCollection(
            collection_name=str(
                _read_candidate_field(item, ("collection_name", "collectionName", "name"), "")
            ),
            resource_id=_read_candidate_field(item, ("resource_id", "resourceId"), None),
            description=_read_candidate_field(item, ("description",), None),
            data_count=getattr(stats, "data_count", None) if stats is not None else None,
            index_names=_read_candidate_field(item, ("index_names", "indexNames"), []) or [],
        )

    def _normalize_index(self, item: Any, fallback_collection_name: str) -> VectorIndex:
        return VectorIndex(
            collection_name=str(
                _read_candidate_field(
                    item,
                    ("collection_name", "collectionName", "CollectionName"),
                    fallback_collection_name,
                )
            ),
            index_name=str(
                _read_candidate_field(item, ("index_name", "indexName", "IndexName"), "")
            ),
            resource_id=_read_candidate_field(
                item, ("resource_id", "resourceId", "ResourceId"), None
            ),
            description=_read_candidate_field(item, ("description", "Description"), None),
            status=_read_candidate_field(item, ("status", "Status"), None),
            project_name=_read_candidate_field(
                item, ("project_name", "projectName", "ProjectName"), None
            ),
        )


def _extract_result_items(raw_results: Any) -> list[Any]:
    if raw_results is None:
        return []
    if isinstance(raw_results, list):
        return raw_results
    if isinstance(raw_results, dict):
        for field in ("data", "items", "results", "result", "result_list"):
            value = raw_results.get(field)
            if isinstance(value, list):
                return value
            nested_items = _extract_result_items(value)
            if nested_items:
                return nested_items
    for field in ("data", "items", "results", "result", "result_list"):
        value = getattr(raw_results, field, None)
        if isinstance(value, list):
            return value
        nested_items = _extract_result_items(value)
        if nested_items:
            return nested_items
    return []


class RerankClient:
    def __init__(self, client_factory: Optional[Callable[..., Any]] = None):
        self.settings = get_settings()
        _validate_rerank_config(self.settings)
        self._client_factory = client_factory

    def _create_sdk_client(self) -> Any:
        if self._client_factory:
            return self._client_factory(
                host=self.settings.vikingdb_knowledge_host,
                region=self.settings.vikingdb_region,
                ak=self.settings.vikingdb_access_key,
                sk=self.settings.vikingdb_secret_key,
                scheme="https",
                timeout=self.settings.rerank_timeout,
            )

        try:
            from vikingdb.auth import IAM  # type: ignore
            from vikingdb.knowledge import VikingKnowledge  # type: ignore
        except ImportError as exc:
            raise VectorRetrievalConfigError(
                "未安装 vikingdb-python-sdk，请执行 python3 -m pip install -U vikingdb-python-sdk"
            ) from exc

        return VikingKnowledge(
            host=self.settings.vikingdb_knowledge_host,
            region=self.settings.vikingdb_region,
            auth=IAM(ak=self.settings.vikingdb_access_key, sk=self.settings.vikingdb_secret_key),
            scheme="https",
            timeout=self.settings.rerank_timeout,
        )

    def rerank(
        self,
        query: RetrievalQuery,
        candidates: list[RetrievalCandidate],
        rerank_model: Optional[str] = None,
    ) -> list[float]:
        if not candidates:
            return []

        try:
            response = self._create_sdk_client().rerank(
                datas=[self._build_data_item(query, candidate) for candidate in candidates],
                rerank_model=rerank_model or self.settings.rerank_model,
                rerank_instruction=self.settings.rerank_instruction,
                endpoint_id=self.settings.rerank_endpoint_id,
                timeout=self.settings.rerank_timeout,
            )
        except Exception as exc:
            raise VectorRetrievalExternalError(f"Viking Knowledge Rerank 请求失败: {exc}") from exc

        scores = self._extract_scores(response, len(candidates))
        if len(scores) != len(candidates):
            raise VectorRetrievalExternalError("Rerank 返回分数数量与候选结果数量不一致")
        return scores

    def _build_data_item(self, query: RetrievalQuery, candidate: RetrievalCandidate) -> Any:
        item_payload = {
            "query": self._build_query_payload(query),
            "content": self._build_candidate_content(candidate),
            "title": candidate.object_name,
        }
        if (
            candidate.object_url
            and get_preview_modality(candidate.object_url, candidate.object_name) == "image"
        ):
            item_payload["image"] = candidate.object_url

        try:
            from vikingdb.knowledge.models.rerank import RerankDataItem  # type: ignore
        except ImportError as exc:
            raise VectorRetrievalConfigError(
                "未安装 vikingdb-python-sdk，请执行 python3 -m pip install -U vikingdb-python-sdk"
            ) from exc
        return RerankDataItem(**item_payload)

    def _build_query_payload(self, query: RetrievalQuery) -> dict[str, Any]:
        if "text" in query.multimodal_input:
            return {"text": query.multimodal_input["text"]}
        payload = {
            "text": f"查找与查询样本 {query.file_name} 最相关的检索结果",
            "file_name": query.file_name,
            "file_type": query.file_type,
            "object_url": query.object_url,
        }
        if query.file_type.lower() in IMAGE_TYPES:
            payload["image"] = query.object_url
        elif query.file_type.lower() in VIDEO_TYPES:
            payload["video"] = query.object_url
        return payload

    def _build_candidate_content(self, candidate: RetrievalCandidate) -> str:
        metadata = {key: value for key, value in candidate.metadata.items() if key != "raw"}
        parts = [
            f"对象名称: {candidate.object_name}",
            f"对象ID: {candidate.object_id}",
        ]
        if candidate.object_url:
            parts.append(f"对象URL: {candidate.object_url}")
        if candidate.search_score is not None:
            parts.append(f"Search分数: {candidate.search_score}")
        if metadata:
            parts.append(f"元数据: {json.dumps(metadata, ensure_ascii=False)}")
        return "\n".join(parts)

    def _extract_scores(self, payload: Any, expected_count: int) -> list[float]:
        if not isinstance(payload, dict):
            result = getattr(payload, "result", None)
            if result is not None and isinstance(getattr(result, "scores", None), list):
                return [float(score) for score in result.scores]
            if hasattr(payload, "model_dump"):
                payload = payload.model_dump()
            elif hasattr(payload, "dict"):
                payload = payload.dict()
            elif hasattr(payload, "__dict__"):
                payload = dict(payload.__dict__)
            else:
                return []

        if isinstance(payload.get("scores"), list):
            return [float(score) for score in payload["scores"]]

        results = payload.get("results") or payload.get("data") or []
        if isinstance(results, dict):
            if isinstance(results.get("scores"), list):
                return [float(score) for score in results["scores"]]
            results = results.get("results") or results.get("items") or []
        if not isinstance(results, list):
            return []

        scores: list[Optional[float]] = [None] * expected_count
        sequential_scores: list[float] = []
        for index, item in enumerate(results):
            if not isinstance(item, dict):
                sequential_scores.append(float(item))
                continue
            score = _as_float(_first_present(item, ("score", "relevance_score", "rerank_score")))
            if score is None:
                continue
            result_index = item.get("index")
            if isinstance(result_index, int) and 0 <= result_index < expected_count:
                scores[result_index] = score
            else:
                sequential_scores.append(score)

        if any(score is not None for score in scores):
            return [float(score if score is not None else 0.0) for score in scores]
        return sequential_scores


def get_preview_modality(url: str, file_name: str = "") -> str:
    target = f"{file_name} {url}".lower()
    if any(target.endswith(f".{ext}") or f".{ext}?" in target for ext in IMAGE_TYPES):
        return "image"
    if any(target.endswith(f".{ext}") or f".{ext}?" in target for ext in VIDEO_TYPES):
        return "video"
    return "unknown"


def rerank_candidates(
    candidates: list[RetrievalCandidate], scores: list[float]
) -> list[RetrievalCandidate]:
    for candidate, score in zip(candidates, scores):
        candidate.rerank_score = score

    ranked = sorted(
        candidates,
        key=lambda candidate: (
            candidate.rerank_score if candidate.rerank_score is not None else float("-inf")
        ),
        reverse=True,
    )
    for index, candidate in enumerate(ranked, start=1):
        candidate.rerank_rank = index
    return ranked


def apply_truncation(
    candidates: list[RetrievalCandidate],
    min_score: Optional[float],
    step_delta_threshold: Optional[float],
) -> list[RetrievalCandidate]:
    cutoff_index: Optional[int] = None
    cutoff_reason: Optional[str] = None

    if min_score is not None:
        for index, candidate in enumerate(candidates):
            score = candidate.rerank_score
            if score is not None and score < min_score:
                cutoff_index = index
                cutoff_reason = f"low_score<{min_score}"
                break

    if step_delta_threshold is not None:
        for index in range(len(candidates) - 1):
            current_score = candidates[index].rerank_score
            next_score = candidates[index + 1].rerank_score
            if current_score is None or next_score is None:
                continue
            if current_score == 0:
                continue
            step_delta = (current_score - next_score) / current_score
            if step_delta >= step_delta_threshold:
                step_cutoff = index + 1
                if cutoff_index is None or step_cutoff < cutoff_index:
                    cutoff_index = step_cutoff
                    cutoff_reason = f"step_delta>={step_delta_threshold}"
                break

    if cutoff_index is None:
        for candidate in candidates:
            candidate.kept = True
            candidate.truncate_reason = None
        return candidates

    for index, candidate in enumerate(candidates):
        candidate.kept = index < cutoff_index
        candidate.truncate_reason = None if candidate.kept else cutoff_reason
    return candidates


def parse_scalar_filter(raw_filter: Optional[Any]) -> Optional[dict[str, Any]]:
    if raw_filter is None or raw_filter == "":
        return None
    if isinstance(raw_filter, dict):
        return raw_filter
    if isinstance(raw_filter, str):
        try:
            parsed = json.loads(raw_filter)
        except json.JSONDecodeError as exc:
            raise ValueError(f"标量过滤条件不是合法 JSON: {exc.msg}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("标量过滤条件必须是 JSON 对象")
        return parsed
    raise ValueError("标量过滤条件必须是 JSON 对象或 JSON 字符串")
