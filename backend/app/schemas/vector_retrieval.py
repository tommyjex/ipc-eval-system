from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

VectorRetrievalSite = Literal["byteplus", "volcengine"]


class VectorRetrievalEvaluateRequest(BaseModel):
    site: VectorRetrievalSite = Field("byteplus", description="向量检索站点")
    dataset_id: Optional[int] = Field(None, ge=1, description="兼容旧链路的评测集ID")
    data_id: Optional[int] = Field(
        None, ge=1, description="指定评测数据ID；不传时使用评测集首条数据"
    )
    collection_name: Optional[str] = Field(
        None, min_length=1, description="VikingDB Collection 名称"
    )
    index_name: Optional[str] = Field(None, min_length=1, description="VikingDB Index 名称")
    query: Optional[str] = Field(None, min_length=1, description="文字检索 query")
    top_k: int = Field(10, ge=1, le=100, description="检索返回数量")
    rerank_model: Literal["m3-v2-rerank", "base-multilingual-rerank"] = Field(
        "m3-v2-rerank",
        description="Viking Knowledge Rerank 模型",
    )
    scalar_filter: Optional[dict[str, Any] | str] = Field(None, description="VikingDB 标量过滤条件")
    filter_tags: list[str] = Field(default_factory=list, description="标量过滤标签")
    min_score: Optional[float] = Field(None, description="低分截断阈值；不传时使用后端配置")
    step_delta_threshold: Optional[float] = Field(
        None,
        ge=0,
        description="相邻分数下降比例阈值，按 (当前分数-下一条分数)/当前分数 计算",
    )


class VectorCollectionResponse(BaseModel):
    collection_name: str
    resource_id: Optional[str] = None
    description: Optional[str] = None
    data_count: Optional[int] = None
    index_names: list[str] = Field(default_factory=list)


class VectorIndexResponse(BaseModel):
    collection_name: str
    index_name: str
    resource_id: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    project_name: Optional[str] = None


class VectorRetrievalQueryResponse(BaseModel):
    data_id: Optional[int] = None
    file_name: str
    file_type: str
    tos_key: str
    tos_bucket: str
    object_url: str
    multimodal_input: dict[str, Any]


class VectorRetrievalResultItem(BaseModel):
    object_id: str
    object_name: str
    object_url: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    search_score: Optional[float] = None
    rerank_score: Optional[float] = None
    rank: Optional[int] = None
    rerank_rank: Optional[int] = None
    kept: bool
    truncate_reason: Optional[str] = None


class VectorRetrievalEvaluateResponse(BaseModel):
    site: VectorRetrievalSite = "byteplus"
    dataset_id: Optional[int] = None
    collection_name: Optional[str] = None
    index_name: Optional[str] = None
    query: VectorRetrievalQueryResponse
    top_k: int
    rerank_model: str
    scalar_filter: Optional[dict[str, Any]] = None
    post_process_ops: Optional[list[dict[str, Any]]] = None
    min_score: Optional[float] = None
    step_delta_threshold: Optional[float] = None
    search_results: list[VectorRetrievalResultItem]
    rerank_results: list[VectorRetrievalResultItem]
    final_results: list[VectorRetrievalResultItem]
    truncated: bool
    truncate_reason: Optional[str] = None
