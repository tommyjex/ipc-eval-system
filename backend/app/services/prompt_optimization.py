import json
from typing import Any, Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models import Annotation, Dataset, EvaluationData, EvaluationTask, TaskPromptOptimization, TaskResult
from app.schemas.task import (
    PromptOptimizationComparisonResponse,
    PromptOptimizationIssue,
    PromptOptimizationResponse,
    PromptOptimizationTaskMetrics,
    PromptOptimizationVersionItem,
    PromptOptimizationVersionListResponse,
)
from app.schemas.task import TaskScoringStatus
from app.services.ark_client import ArkClient


OPTIMIZATION_MODEL = "doubao-seed-2-0-pro-260215"
OPTIMIZATION_TIMEOUT_SECONDS = 120


def _truncate_text(value: str | None, limit: int = 1200) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _build_sample_payload(rows: list[tuple[TaskResult, EvaluationData, Annotation | None]]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for result, data, annotation in rows:
        payload.append(
            {
                "object_name": data.file_name,
                "ground_truth": _truncate_text(annotation.ground_truth if annotation else ""),
                "model_output": _truncate_text(result.model_output),
                "recall": result.recall,
                "precision": result.precision,
                "score_reason": _truncate_text(result.score_reason, limit=800),
                "is_empty_sample": result.is_empty_sample,
                "empty_sample_passed": result.empty_sample_passed,
                "tp_count": result.tp_count,
                "fp_count": result.fp_count,
                "fn_count": result.fn_count,
            }
        )
    return payload


def _build_stats(samples: list[dict[str, Any]]) -> dict[str, Any]:
    low_recall = sum(1 for item in samples if item["recall"] is not None and item["recall"] < 80)
    low_precision = sum(1 for item in samples if item["precision"] is not None and item["precision"] < 80)
    empty_failed = sum(1 for item in samples if item["is_empty_sample"] and item["empty_sample_passed"] is False)
    false_positive = sum(1 for item in samples if (item["fp_count"] or 0) > 0)
    false_negative = sum(1 for item in samples if (item["fn_count"] or 0) > 0)
    return {
        "sample_count": len(samples),
        "low_recall_count": low_recall,
        "low_precision_count": low_precision,
        "empty_sample_failed_count": empty_failed,
        "false_positive_sample_count": false_positive,
        "false_negative_sample_count": false_negative,
    }


def _serialize_json_list(items: list[Any]) -> str:
    return json.dumps(items, ensure_ascii=False)


def _deserialize_json_list(payload: Optional[str]) -> list[Any]:
    if not payload:
        return []
    try:
        value = json.loads(payload)
        return value if isinstance(value, list) else []
    except Exception:
        return []


def _build_task_metrics(db: Session, task: EvaluationTask) -> PromptOptimizationTaskMetrics:
    scored_condition = TaskResult.scoring_status == TaskScoringStatus.scored.value
    empty_and_passed_condition = TaskResult.is_empty_sample.is_(True) & TaskResult.empty_sample_passed.is_(True)
    aggregate_condition = scored_condition & TaskResult.is_scorable.is_(True) & ~empty_and_passed_condition

    stats_row = (
        db.query(
            func.coalesce(func.sum(case((aggregate_condition, TaskResult.tp_count), else_=0)), 0).label("sum_tp"),
            func.coalesce(func.sum(case((aggregate_condition, TaskResult.fp_count), else_=0)), 0).label("sum_fp"),
            func.coalesce(func.sum(case((aggregate_condition, TaskResult.fn_count), else_=0)), 0).label("sum_fn"),
            func.avg(case((aggregate_condition, TaskResult.recall), else_=None)).label("macro_recall"),
            func.avg(case((aggregate_condition, TaskResult.precision), else_=None)).label("macro_precision"),
            func.count(case((aggregate_condition, 1), else_=None)).label("scorable_count"),
            func.count(case((scored_condition & TaskResult.is_empty_sample.is_(True), 1), else_=None)).label("empty_sample_count"),
            func.count(case((scored_condition & TaskResult.empty_sample_passed.is_(True), 1), else_=None)).label("empty_sample_passed_count"),
            func.count(case((scored_condition & TaskResult.is_scorable.is_(False), 1), else_=None)).label("unscorable_count"),
            func.count(case((scored_condition, 1), else_=None)).label("total_count"),
        )
        .filter(TaskResult.task_id == task.id)
        .first()
    )

    micro_recall = None
    micro_precision = None
    coverage_rate = None
    empty_sample_pass_rate = None
    if stats_row:
        sum_tp = int(stats_row.sum_tp or 0)
        sum_fp = int(stats_row.sum_fp or 0)
        sum_fn = int(stats_row.sum_fn or 0)
        scorable_count = int(stats_row.scorable_count or 0)
        total_count = int(stats_row.total_count or 0)
        empty_count = int(stats_row.empty_sample_count or 0)
        empty_passed_count = int(stats_row.empty_sample_passed_count or 0)
        micro_recall = round(sum_tp / (sum_tp + sum_fn) * 100, 2) if (sum_tp + sum_fn) > 0 else None
        micro_precision = round(sum_tp / (sum_tp + sum_fp) * 100, 2) if (sum_tp + sum_fp) > 0 else None
        coverage_rate = round(scorable_count / total_count * 100, 2) if total_count > 0 else None
        empty_sample_pass_rate = round(empty_passed_count / empty_count * 100, 2) if empty_count > 0 else None

    return PromptOptimizationTaskMetrics(
        task_id=task.id,
        task_name=task.name,
        status=task.status,
        micro_recall=micro_recall,
        micro_precision=micro_precision,
        macro_recall=round(float(stats_row.macro_recall), 2) if stats_row and stats_row.macro_recall is not None else None,
        macro_precision=round(float(stats_row.macro_precision), 2) if stats_row and stats_row.macro_precision is not None else None,
        coverage_rate=coverage_rate,
        empty_sample_pass_rate=empty_sample_pass_rate,
        unscorable_count=int(stats_row.unscorable_count or 0) if stats_row else 0,
    )


def build_prompt_optimization_response(
    db: Session,
    task: EvaluationTask,
    optimization: TaskPromptOptimization,
) -> PromptOptimizationResponse:
    issues_raw = _deserialize_json_list(optimization.issues_json)
    issues = [
        PromptOptimizationIssue(
            title=str(item.get("title") or "").strip(),
            summary=str(item.get("summary") or "").strip(),
            evidence=[str(e).strip() for e in (item.get("evidence") or []) if str(e).strip()],
        )
        for item in issues_raw
        if isinstance(item, dict) and str(item.get("title") or "").strip() and str(item.get("summary") or "").strip()
    ]
    strategies = [str(item).strip() for item in _deserialize_json_list(optimization.optimization_strategies_json) if str(item).strip()]
    revisions = [str(item).strip() for item in _deserialize_json_list(optimization.revision_summary_json) if str(item).strip()]

    comparison = None
    if optimization.compare_task_id:
        compare_task = db.query(EvaluationTask).filter(EvaluationTask.id == optimization.compare_task_id).first()
        if compare_task:
            comparison = PromptOptimizationComparisonResponse(
                baseline_task=_build_task_metrics(db, task),
                compare_task=_build_task_metrics(db, compare_task),
            )

    return PromptOptimizationResponse(
        optimization_id=optimization.id,
        version_number=int(optimization.version_number or 1),
        task_id=task.id,
        sample_count=int(optimization.sample_count or 0),
        source_prompt=optimization.source_prompt,
        optimization_model=optimization.optimization_model,
        analysis_summary=optimization.analysis_summary or "",
        issues=issues,
        optimization_strategies=strategies,
        optimized_prompt=optimization.optimized_prompt,
        edited_prompt=(optimization.edited_prompt or optimization.optimized_prompt or "").strip(),
        revision_summary=revisions,
        compare_task_id=optimization.compare_task_id,
        comparison=comparison,
        analysis_input_tokens=optimization.analysis_input_tokens,
        analysis_output_tokens=optimization.analysis_output_tokens,
        prompt_input_tokens=optimization.prompt_input_tokens,
        prompt_output_tokens=optimization.prompt_output_tokens,
        created_at=optimization.created_at,
        updated_at=optimization.updated_at,
    )


def list_prompt_optimization_records(db: Session, task_id: int) -> list[TaskPromptOptimization]:
    return (
        db.query(TaskPromptOptimization)
        .filter(TaskPromptOptimization.task_id == task_id)
        .order_by(TaskPromptOptimization.version_number.desc(), TaskPromptOptimization.id.desc())
        .all()
    )


def build_prompt_optimization_version_list(
    records: list[TaskPromptOptimization],
) -> PromptOptimizationVersionListResponse:
    items = [
        PromptOptimizationVersionItem(
            optimization_id=record.id,
            version_number=int(record.version_number or 1),
            sample_count=int(record.sample_count or 0),
            compare_task_id=record.compare_task_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
        for record in records
    ]
    return PromptOptimizationVersionListResponse(items=items, total=len(items))


def get_prompt_optimization_record(
    db: Session,
    task_id: int,
    optimization_id: Optional[int] = None,
) -> Optional[TaskPromptOptimization]:
    query = db.query(TaskPromptOptimization).filter(TaskPromptOptimization.task_id == task_id)
    if optimization_id is not None:
        return query.filter(TaskPromptOptimization.id == optimization_id).first()
    return query.order_by(TaskPromptOptimization.version_number.desc(), TaskPromptOptimization.id.desc()).first()


def _get_next_version_number(db: Session, task_id: int) -> int:
    current = (
        db.query(func.max(TaskPromptOptimization.version_number))
        .filter(TaskPromptOptimization.task_id == task_id)
        .scalar()
    )
    return int(current or 0) + 1


def optimize_task_prompt(
    db: Session,
    task: EvaluationTask,
    dataset: Dataset,
    rows: list[tuple[TaskResult, EvaluationData, Annotation | None]],
) -> PromptOptimizationResponse:
    if not rows:
        raise ValueError("当前任务没有可用于提示词优化的已评分样本")

    source_prompt = (task.prompt or dataset.annotation_prompt or "").strip()
    samples = _build_sample_payload(rows)
    stats = _build_stats(samples)
    ark_client = ArkClient(timeout=OPTIMIZATION_TIMEOUT_SECONDS)

    analysis_system_prompt = (
        "你是视觉大模型提示词诊断专家。"
        "你将收到一个评测任务的原始提示词、任务场景和全量已评分样本。"
        "你必须重点分析标注结果与模型输出之间的差异，识别高频漏检、误报、空样本误报、格式偏差与约束缺失。"
        "请只输出 JSON 对象，不要输出额外说明。"
        "JSON 必须包含以下字段："
        "analysis_summary(string),"
        "issues(array，元素为对象，包含 title(string), summary(string), evidence(array[string]))，"
        "optimization_strategies(array[string])。"
        "issues 最多输出 5 项，evidence 每项最多输出 3 条。"
    )
    analysis_user_prompt = (
        "请基于以下任务信息和全量样本，输出问题分析与优化策略，不要直接生成优化后的提示词。\n"
        f"任务名称：{task.name}\n"
        f"原始提示词：{source_prompt or '未设置'}\n"
        f"评测集场景：{getattr(dataset, 'scene', None) or '未设置'}\n"
        f"自定义标签：{json.dumps(getattr(dataset, 'custom_tags', None) or [], ensure_ascii=False)}\n"
        f"统计信息：{json.dumps(stats, ensure_ascii=False)}\n"
        f"全量样本数据：{json.dumps(samples, ensure_ascii=False)}"
    )
    analysis_response = ark_client.generate_json_with_usage(
        system_prompt=analysis_system_prompt,
        user_prompt=analysis_user_prompt,
        model=OPTIMIZATION_MODEL,
        thinking_enabled=True,
    )
    analysis_data = analysis_response["data"]

    prompt_system_prompt = (
        "你是视觉大模型提示词优化专家。"
        "你将收到原始提示词、任务场景、标签信息，以及上一阶段输出的问题分析与优化策略。"
        "请生成一版可直接用于视觉理解任务的优化后提示词。"
        "请只输出 JSON 对象，不要输出额外说明。"
        "JSON 必须包含以下字段："
        "optimized_prompt(string),"
        "revision_summary(array[string])。"
    )
    prompt_user_prompt = (
        "请根据以下信息生成优化后的提示词。\n"
        f"任务名称：{task.name}\n"
        f"原始提示词：{source_prompt or '未设置'}\n"
        f"评测集场景：{getattr(dataset, 'scene', None) or '未设置'}\n"
        f"自定义标签：{json.dumps(getattr(dataset, 'custom_tags', None) or [], ensure_ascii=False)}\n"
        f"第一阶段问题分析：{json.dumps(analysis_data, ensure_ascii=False)}"
    )
    prompt_response = ark_client.generate_json_with_usage(
        system_prompt=prompt_system_prompt,
        user_prompt=prompt_user_prompt,
        model=OPTIMIZATION_MODEL,
        thinking_enabled=True,
    )
    prompt_data = prompt_response["data"]

    issues: list[PromptOptimizationIssue] = []
    for item in analysis_data.get("issues") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        summary = str(item.get("summary") or "").strip()
        evidence = [str(e).strip() for e in (item.get("evidence") or []) if str(e).strip()]
        if title and summary:
            issues.append(PromptOptimizationIssue(title=title, summary=summary, evidence=evidence))

    strategies = [str(item).strip() for item in (analysis_data.get("optimization_strategies") or []) if str(item).strip()]
    revisions = [str(item).strip() for item in (prompt_data.get("revision_summary") or []) if str(item).strip()]

    optimized_prompt = str(prompt_data.get("optimized_prompt") or "").strip()
    if not optimized_prompt:
        raise ValueError("优化模型未返回有效的优化后提示词")

    optimization = TaskPromptOptimization(
        task_id=task.id,
        version_number=_get_next_version_number(db, task.id),
        optimization_model=OPTIMIZATION_MODEL,
        optimized_prompt=optimized_prompt,
    )
    db.add(optimization)
    optimization.sample_count = len(samples)
    optimization.source_prompt = source_prompt or None
    optimization.optimization_model = OPTIMIZATION_MODEL
    optimization.analysis_summary = str(analysis_data.get("analysis_summary") or "").strip()
    optimization.issues_json = _serialize_json_list([issue.model_dump() for issue in issues])
    optimization.optimization_strategies_json = _serialize_json_list(strategies)
    optimization.optimized_prompt = optimized_prompt
    optimization.edited_prompt = optimized_prompt
    optimization.revision_summary_json = _serialize_json_list(revisions)
    optimization.analysis_input_tokens = analysis_response.get("input_tokens")
    optimization.analysis_output_tokens = analysis_response.get("output_tokens")
    optimization.prompt_input_tokens = prompt_response.get("input_tokens")
    optimization.prompt_output_tokens = prompt_response.get("output_tokens")
    optimization.compare_task_id = None
    db.commit()
    db.refresh(optimization)
    return build_prompt_optimization_response(db, task, optimization)


def update_prompt_optimization_prompt(
    db: Session,
    task: EvaluationTask,
    optimization: TaskPromptOptimization,
    edited_prompt: str,
) -> PromptOptimizationResponse:
    optimization.edited_prompt = edited_prompt.strip()
    db.commit()
    db.refresh(optimization)
    return build_prompt_optimization_response(db, task, optimization)
