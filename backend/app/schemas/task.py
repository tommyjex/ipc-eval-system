from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class TaskResultStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class TaskScoringStatus(str, Enum):
    not_scored = "not_scored"
    scoring = "scoring"
    scored = "scored"
    score_failed = "score_failed"


class ModelProvider(str, Enum):
    volcengine = "volcengine"
    aliyun = "aliyun"
    gemini = "gemini"
    openai = "openai"
    aws = "aws"


class EvaluationTaskBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="任务名称")
    target_model: str = Field(..., max_length=100, description="目标模型")
    model_provider: Optional[ModelProvider] = Field(None, description="模型供应商")
    scoring_criteria: Optional[str] = Field(None, description="评分标准")
    prompt: Optional[str] = Field(None, description="任务级提示词")
    fps: float = Field(0.3, ge=0.01, le=30, description="视频理解帧率")


class EvaluationTaskCreate(EvaluationTaskBase):
    dataset_id: int = Field(..., description="评测集ID")


class EvaluationTaskUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="任务名称")
    target_model: Optional[str] = Field(None, max_length=100, description="目标模型")
    model_provider: Optional[ModelProvider] = Field(None, description="模型供应商")
    scoring_criteria: Optional[str] = Field(None, description="评分标准")
    prompt: Optional[str] = Field(None, description="任务级提示词")
    fps: Optional[float] = Field(None, ge=0.01, le=30, description="视频理解帧率")
    status: Optional[TaskStatus] = Field(None, description="任务状态")


class EvaluationTaskRunRequest(BaseModel):
    data_ids: Optional[list[int]] = Field(None, description="指定重跑的数据ID列表")


class EvaluationTaskScoreRequest(BaseModel):
    result_ids: Optional[list[int]] = Field(None, description="指定评分的结果ID列表")


class PromptOptimizationIssue(BaseModel):
    title: str = Field(..., description="问题标题")
    summary: str = Field(..., description="问题摘要")
    evidence: list[str] = Field(default_factory=list, description="样本证据")


class PromptOptimizationTaskMetrics(BaseModel):
    task_id: int = Field(..., description="任务ID")
    task_name: str = Field(..., description="任务名称")
    status: TaskStatus = Field(..., description="任务状态")
    micro_recall: Optional[float] = Field(None, description="Micro 召回率")
    micro_precision: Optional[float] = Field(None, description="Micro 精确率")
    macro_recall: Optional[float] = Field(None, description="Macro 召回率")
    macro_precision: Optional[float] = Field(None, description="Macro 精确率")
    coverage_rate: Optional[float] = Field(None, description="覆盖率")
    empty_sample_pass_rate: Optional[float] = Field(None, description="空样本通过率")
    unscorable_count: int = Field(0, description="不可评分数量")


class PromptOptimizationComparisonResponse(BaseModel):
    baseline_task: PromptOptimizationTaskMetrics = Field(..., description="基线任务指标")
    compare_task: PromptOptimizationTaskMetrics = Field(..., description="对比任务指标")


class PromptOptimizationResponse(BaseModel):
    optimization_id: int = Field(..., description="提示词优化记录ID")
    version_number: int = Field(..., description="优化版本号")
    task_id: int = Field(..., description="任务ID")
    sample_count: int = Field(..., description="纳入分析的样本数")
    source_prompt: Optional[str] = Field(None, description="原始提示词")
    optimization_model: str = Field(..., description="优化模型")
    analysis_summary: str = Field(..., description="问题分析摘要")
    issues: list[PromptOptimizationIssue] = Field(default_factory=list, description="问题点列表")
    optimization_strategies: list[str] = Field(default_factory=list, description="优化策略")
    optimized_prompt: str = Field(..., description="优化后提示词")
    edited_prompt: str = Field(..., description="人工微调后的提示词")
    revision_summary: list[str] = Field(default_factory=list, description="提示词修改摘要")
    compare_task_id: Optional[int] = Field(None, description="对比任务ID")
    comparison: Optional[PromptOptimizationComparisonResponse] = Field(None, description="优化前后任务级指标对比")
    analysis_input_tokens: Optional[int] = Field(None, description="第一阶段输入 tokens")
    analysis_output_tokens: Optional[int] = Field(None, description="第一阶段输出 tokens")
    prompt_input_tokens: Optional[int] = Field(None, description="第二阶段输入 tokens")
    prompt_output_tokens: Optional[int] = Field(None, description="第二阶段输出 tokens")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")


class PromptOptimizationVersionItem(BaseModel):
    optimization_id: int = Field(..., description="提示词优化记录ID")
    version_number: int = Field(..., description="优化版本号")
    sample_count: int = Field(..., description="纳入分析的样本数")
    compare_task_id: Optional[int] = Field(None, description="对比任务ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")


class PromptOptimizationVersionListResponse(BaseModel):
    items: list[PromptOptimizationVersionItem]
    total: int


class PromptOptimizationUpdateRequest(BaseModel):
    edited_prompt: str = Field(..., min_length=1, description="人工微调后的提示词")


class EvaluationTaskResponse(EvaluationTaskBase):
    id: int
    dataset_id: int
    username: Optional[str] = None
    status: TaskStatus
    micro_recall: Optional[float] = None
    micro_precision: Optional[float] = None
    macro_recall: Optional[float] = None
    macro_precision: Optional[float] = None
    coverage_rate: Optional[float] = None
    empty_sample_pass_rate: Optional[float] = None
    unscorable_count: int = 0
    avg_input_tokens: Optional[float] = None
    avg_output_tokens: Optional[float] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EvaluationTaskListResponse(BaseModel):
    items: list[EvaluationTaskResponse]
    total: int


class PromptOptimizationCompareResponse(BaseModel):
    optimization: PromptOptimizationResponse = Field(..., description="最新优化记录")
    compare_task: EvaluationTaskResponse = Field(..., description="新建的对比任务")


class TaskResultBase(BaseModel):
    status: TaskResultStatus = Field(..., description="执行状态")
    model_output: Optional[str] = Field(None, description="模型输出")
    input_tokens: Optional[int] = Field(None, description="输入 tokens")
    output_tokens: Optional[int] = Field(None, description="输出 tokens")
    score: Optional[int] = Field(None, description="评分")
    recall: Optional[float] = Field(None, description="召回率")
    precision: Optional[float] = Field(None, description="精确率")
    score_reason: Optional[str] = Field(None, description="评分原因")
    tp_count: Optional[int] = Field(None, description="命中数量")
    fp_count: Optional[int] = Field(None, description="误报数量")
    fn_count: Optional[int] = Field(None, description="漏检数量")
    ground_truth_unit_count: Optional[int] = Field(None, description="标注单元数")
    predicted_unit_count: Optional[int] = Field(None, description="预测单元数")
    is_scorable: Optional[bool] = Field(None, description="是否可参与主指标聚合")
    is_empty_sample: Optional[bool] = Field(None, description="是否为空样本")
    empty_sample_passed: Optional[bool] = Field(None, description="空样本是否判断正确")
    metric_version: Optional[str] = Field(None, description="评分口径版本")
    scoring_status: TaskScoringStatus = Field(..., description="评分状态")
    scoring_error_message: Optional[str] = Field(None, description="评分失败原因")
    scoring_model: Optional[str] = Field(None, description="评分模型")
    error_message: Optional[str] = Field(None, description="失败原因")


class TaskResultResponse(TaskResultBase):
    id: int
    task_id: int
    data_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    scoring_started_at: Optional[datetime] = None
    scoring_completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TaskResultListResponse(BaseModel):
    items: list[TaskResultResponse]
    total: int


class TaskResultDetailResponse(TaskResultResponse):
    file_name: str = Field(..., description="文件名")
    file_type: str = Field(..., description="文件类型")
    download_url: Optional[str] = Field(None, description="下载链接")
    ground_truth: Optional[str] = Field(None, description="标注结果")


class TaskResultDetailListResponse(BaseModel):
    items: list[TaskResultDetailResponse]
    total: int
    micro_recall: Optional[float] = None
    micro_precision: Optional[float] = None
    macro_recall: Optional[float] = None
    macro_precision: Optional[float] = None
    coverage_rate: Optional[float] = None
    empty_sample_pass_rate: Optional[float] = None
    unscorable_count: int = 0
    avg_input_tokens: Optional[float] = None
    avg_output_tokens: Optional[float] = None


class TaskResultSelectionResponse(BaseModel):
    total: int
    result_ids: list[int]
    data_ids: list[int]
