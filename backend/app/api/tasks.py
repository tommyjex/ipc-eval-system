from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from app.core.config import get_settings
from app.core.database import get_db, SessionLocal
from app.models import EvaluationTask, TaskResult, Dataset, EvaluationData, Annotation
from app.schemas.task import (
    EvaluationTaskCreate,
    EvaluationTaskUpdate,
    EvaluationTaskRunRequest,
    EvaluationTaskScoreRequest,
    EvaluationTaskResponse,
    EvaluationTaskListResponse,
    TaskResultListResponse,
    TaskResultDetailResponse,
    TaskResultDetailListResponse,
    TaskStatus,
    TaskResultSelectionResponse,
    TaskResultStatus,
    TaskScoringStatus,
)
from app.utils import get_tos_client
from app.utils import get_tos_client
from app.services import get_ark_client, get_dashscope_client
from app.services.video_frames import DEFAULT_VIDEO_FPS

router = APIRouter(prefix="/tasks", tags=["评测任务"])
SMART_SCORING_MODEL = "doubao-seed-2-0-pro-260215"
TASK_INFERENCE_BATCH_SIZE = get_settings().task_inference_batch_size
TASK_SCORING_BATCH_SIZE = get_settings().task_scoring_batch_size
logger = logging.getLogger(__name__)


def _normalize_fps(value: float) -> float:
    return round(float(value), 2)

_running_tasks: dict[str, dict] = {}


def _get_inference_client(model_provider: Optional[str]):
    provider = (model_provider or "volcengine").lower()
    if provider == "volcengine":
        return get_ark_client()
    if provider == "aliyun":
        return get_dashscope_client()
    raise ValueError(f"暂不支持的模型供应商: {provider}")


def _mark_task_results_failed(db: Session, task_id: int, error_message: str):
    db.query(TaskResult).filter(TaskResult.task_id == task_id).update(
        {
            TaskResult.status: TaskResultStatus.failed.value,
            TaskResult.error_message: error_message,
            TaskResult.completed_at: datetime.now(),
            TaskResult.score: None,
            TaskResult.recall: None,
            TaskResult.accuracy: None,
            TaskResult.score_reason: None,
            TaskResult.scoring_status: TaskScoringStatus.not_scored.value,
            TaskResult.scoring_error_message: None,
            TaskResult.scoring_model: None,
            TaskResult.scoring_started_at: None,
            TaskResult.scoring_completed_at: None,
        },
        synchronize_session=False,
    )


def _chunked(items: list[int], chunk_size: int) -> list[list[int]]:
    return [items[index:index + chunk_size] for index in range(0, len(items), chunk_size)]


def _run_single_task_result(
    task_id: int,
    data_id: int,
    annotation_prompt: Optional[str],
    custom_tags: Optional[list[str]],
    target_model: Optional[str],
    model_provider: Optional[str],
    fps: float,
) -> bool:
    db = SessionLocal()
    try:
        result = db.query(TaskResult).filter(
            TaskResult.task_id == task_id,
            TaskResult.data_id == data_id,
        ).first()
        data = db.query(EvaluationData).filter(EvaluationData.id == data_id).first()
        if not result or not data:
            return False

        try:
            inference_client = _get_inference_client(model_provider)
        except Exception as exc:
            logger.exception(
                "初始化推理客户端失败: task_id=%s data_id=%s provider=%s model=%s",
                task_id,
                data_id,
                model_provider,
                target_model,
            )
            result.status = TaskResultStatus.failed.value
            result.input_tokens = None
            result.output_tokens = None
            result.recall = None
            result.accuracy = None
            result.score = None
            result.score_reason = None
            result.scoring_status = TaskScoringStatus.not_scored.value
            result.scoring_error_message = None
            result.scoring_model = None
            result.scoring_started_at = None
            result.scoring_completed_at = None
            result.error_message = str(exc)
            result.completed_at = datetime.now()
            db.commit()
            return False

        result.status = TaskResultStatus.running.value
        result.error_message = None
        result.completed_at = None
        db.commit()

        try:
            tos_client = get_tos_client()
            download_url = tos_client.get_download_url(data.tos_key)
            is_gif = data.file_type.lower() == "gif"

            if is_gif:
                inference_result = inference_client.annotate_gif_with_usage(
                    download_url,
                    annotation_prompt,
                    custom_tags,
                    target_model,
                    fps=fps,
                )
            else:
                content = inference_client.build_annotation_content(
                    download_url,
                    data.file_type,
                    annotation_prompt,
                    custom_tags,
                    fps=fps,
                )
                inference_result = inference_client.annotate_with_usage(content, target_model)

            result.model_output = inference_result["text"]
            result.input_tokens = inference_result.get("input_tokens")
            result.output_tokens = inference_result.get("output_tokens")
            result.score = None
            result.recall = None
            result.accuracy = None
            result.score_reason = None
            result.scoring_status = TaskScoringStatus.not_scored.value
            result.scoring_error_message = None
            result.scoring_model = None
            result.scoring_started_at = None
            result.scoring_completed_at = None
            result.status = TaskResultStatus.completed.value
            result.error_message = None
            result.completed_at = datetime.now()
            db.commit()
            return True
        except Exception as exc:
            logger.exception(
                "评测任务单条推理失败: task_id=%s data_id=%s file_type=%s provider=%s model=%s",
                task_id,
                data_id,
                data.file_type,
                model_provider,
                target_model,
            )
            result.status = TaskResultStatus.failed.value
            result.input_tokens = None
            result.output_tokens = None
            result.recall = None
            result.accuracy = None
            result.score = None
            result.score_reason = None
            result.scoring_status = TaskScoringStatus.not_scored.value
            result.scoring_error_message = None
            result.scoring_model = None
            result.scoring_started_at = None
            result.scoring_completed_at = None
            result.error_message = str(exc)
            result.completed_at = datetime.now()
            db.commit()
            return False
    finally:
        db.close()


def _score_single_task_result(
    result_id: int,
    scoring_criteria: Optional[str],
) -> tuple[str, Optional[str]]:
    db = SessionLocal()
    try:
        ark_client = get_ark_client()
        row = db.query(TaskResult, Annotation)\
            .join(EvaluationData, TaskResult.data_id == EvaluationData.id)\
            .outerjoin(Annotation, EvaluationData.id == Annotation.data_id)\
            .filter(TaskResult.id == result_id)\
            .first()
        if not row:
            return ("failed", "评分结果不存在")

        result, annotation = row
        if not result.model_output or not annotation or not annotation.ground_truth:
            result.scoring_status = TaskScoringStatus.not_scored.value
            result.scoring_error_message = None
            result.scoring_model = None
            result.scoring_started_at = None
            result.scoring_completed_at = None
            db.commit()
            return ("skipped", None)

        if result.status == TaskResultStatus.pending.value:
            result.status = TaskResultStatus.completed.value

        result.scoring_status = TaskScoringStatus.scoring.value
        result.scoring_error_message = None
        result.scoring_model = SMART_SCORING_MODEL
        result.scoring_started_at = datetime.now()
        result.scoring_completed_at = None
        db.commit()

        try:
            scoring = ark_client.score_result(
                ground_truth=annotation.ground_truth,
                model_output=result.model_output,
                scoring_criteria=scoring_criteria,
                model=SMART_SCORING_MODEL,
            )

            result.recall = scoring["recall"]
            result.accuracy = scoring["accuracy"]
            result.score_reason = scoring["reason"] or None
            result.score = round((scoring["recall"] + scoring["accuracy"]) / 2)
            result.scoring_status = TaskScoringStatus.scored.value
            result.scoring_error_message = None
            result.scoring_completed_at = datetime.now()
            db.commit()
            return ("scored", None)
        except Exception as exc:
            logger.exception(
                "智能评分单条失败: result_id=%s task_id=%s data_id=%s model=%s",
                result.id,
                result.task_id,
                result.data_id,
                SMART_SCORING_MODEL,
            )
            result.scoring_status = TaskScoringStatus.score_failed.value
            result.scoring_error_message = str(exc)
            result.scoring_completed_at = datetime.now()
            db.commit()
            return ("failed", str(exc))
    finally:
        db.close()


@router.post("", response_model=EvaluationTaskResponse, summary="创建评测任务")
def create_task(data: EvaluationTaskCreate, db: Session = Depends(get_db)):
    dataset = db.query(Dataset).filter(Dataset.id == data.dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="评测集不存在")
    
    task = EvaluationTask(
        dataset_id=data.dataset_id,
        name=data.name,
        target_model=data.target_model,
        model_provider=data.model_provider.value if data.model_provider else None,
        scoring_criteria=data.scoring_criteria,
        prompt=data.prompt,
        fps=_normalize_fps(data.fps),
        status=TaskStatus.pending.value,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("", response_model=EvaluationTaskListResponse, summary="获取评测任务列表")
def list_tasks(
    dataset_id: Optional[int] = Query(None, description="评测集ID"),
    status: Optional[TaskStatus] = Query(None, description="任务状态"),
    sort_by: Optional[str] = Query(None, description="排序字段，可选 avg_recall / avg_accuracy"),
    sort_order: Optional[str] = Query("desc", description="排序方向，可选 asc / desc"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db)
):
    stats_subquery = db.query(
        TaskResult.task_id.label("task_id"),
        func.avg(TaskResult.recall).label("avg_recall"),
        func.avg(TaskResult.accuracy).label("avg_accuracy"),
    ).filter(
        TaskResult.scoring_status == TaskScoringStatus.scored.value,
    ).group_by(TaskResult.task_id).subquery()

    query = db.query(
        EvaluationTask,
        stats_subquery.c.avg_recall,
        stats_subquery.c.avg_accuracy,
    ).outerjoin(
        stats_subquery,
        EvaluationTask.id == stats_subquery.c.task_id,
    )
    
    if dataset_id:
        query = query.filter(EvaluationTask.dataset_id == dataset_id)
    if status:
        query = query.filter(EvaluationTask.status == status.value)

    if sort_by not in (None, "avg_recall", "avg_accuracy"):
        raise HTTPException(status_code=400, detail="不支持的排序字段")
    if sort_order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="不支持的排序方向")

    total = query.count()

    if sort_by == "avg_recall":
        sort_column = stats_subquery.c.avg_recall
        null_fallback = 999999 if sort_order == "asc" else -1
        order_clause = func.coalesce(sort_column, null_fallback).asc() if sort_order == "asc" else func.coalesce(sort_column, null_fallback).desc()
    elif sort_by == "avg_accuracy":
        sort_column = stats_subquery.c.avg_accuracy
        null_fallback = 999999 if sort_order == "asc" else -1
        order_clause = func.coalesce(sort_column, null_fallback).asc() if sort_order == "asc" else func.coalesce(sort_column, null_fallback).desc()
    else:
        order_clause = EvaluationTask.created_at.desc()

    rows = query.order_by(order_clause, EvaluationTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    tasks: list[EvaluationTask] = []
    for task, avg_recall, avg_accuracy in rows:
        task.avg_recall = avg_recall
        task.avg_accuracy = avg_accuracy
        tasks.append(task)

    return EvaluationTaskListResponse(items=tasks, total=total)


@router.get("/{task_id}", response_model=EvaluationTaskResponse, summary="获取评测任务详情")
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(EvaluationTask).filter(EvaluationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="评测任务不存在")
    return task


@router.put("/{task_id}", response_model=EvaluationTaskResponse, summary="更新评测任务")
def update_task(task_id: int, data: EvaluationTaskUpdate, db: Session = Depends(get_db)):
    task = db.query(EvaluationTask).filter(EvaluationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="评测任务不存在")
    
    if data.name is not None:
        task.name = data.name
    if data.target_model is not None:
        task.target_model = data.target_model
    if data.scoring_criteria is not None:
        task.scoring_criteria = data.scoring_criteria
    if data.prompt is not None:
        task.prompt = data.prompt
    if data.fps is not None:
        task.fps = _normalize_fps(data.fps)
    if data.status is not None:
        task.status = data.status.value
    
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", summary="删除评测任务")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(EvaluationTask).filter(EvaluationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="评测任务不存在")
    
    db.delete(task)
    db.commit()
    return {"message": "删除成功"}


@router.post("/{task_id}/run", summary="运行评测任务")
async def run_task(
    task_id: int,
    payload: Optional[EvaluationTaskRunRequest] = None,
    db: Session = Depends(get_db),
):
    task = db.query(EvaluationTask).filter(EvaluationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="评测任务不存在")
    
    if task.status == TaskStatus.running.value:
        active_running_results = db.query(TaskResult).filter(
            TaskResult.task_id == task_id,
            TaskResult.status == TaskResultStatus.running.value
        ).all()
        if active_running_results:
            raise HTTPException(status_code=400, detail="任务正在运行中")
        # Recover stale task status when the task was left in running but no worker is active.
        task.status = TaskStatus.pending.value
        task.completed_at = None
        db.commit()
        db.refresh(task)

    target_data_ids = payload.data_ids if payload and payload.data_ids else None
    data_query = db.query(EvaluationData).filter(EvaluationData.dataset_id == task.dataset_id)
    if target_data_ids:
        data_query = data_query.filter(EvaluationData.id.in_(target_data_ids))
    data_list = data_query.all()
    if not data_list:
        raise HTTPException(status_code=400, detail="评测集内暂无可评测数据")

    if target_data_ids:
        found_ids = {data.id for data in data_list}
        invalid_ids = [data_id for data_id in target_data_ids if data_id not in found_ids]
        if invalid_ids:
            raise HTTPException(status_code=400, detail=f"存在无效的数据ID: {invalid_ids[:10]}")

        existing_results = db.query(TaskResult).filter(
            TaskResult.task_id == task_id,
            TaskResult.data_id.in_(found_ids),
        ).all()
        existing_map = {result.data_id: result for result in existing_results}

        for data in data_list:
            result = existing_map.get(data.id)
            if result is None:
                db.add(TaskResult(
                    task_id=task_id,
                    data_id=data.id,
                    status=TaskResultStatus.pending.value,
                    scoring_status=TaskScoringStatus.not_scored.value,
                    model_output=None,
                    input_tokens=None,
                    output_tokens=None,
                    score=None,
                    recall=None,
                    accuracy=None,
                    score_reason=None,
                    scoring_error_message=None,
                    scoring_model=None,
                    scoring_started_at=None,
                    scoring_completed_at=None,
                    error_message=None,
                    completed_at=None,
                ))
            else:
                result.status = TaskResultStatus.pending.value
                result.scoring_status = TaskScoringStatus.not_scored.value
                result.model_output = None
                result.input_tokens = None
                result.output_tokens = None
                result.score = None
                result.recall = None
                result.accuracy = None
                result.score_reason = None
                result.scoring_error_message = None
                result.scoring_model = None
                result.scoring_started_at = None
                result.scoring_completed_at = None
                result.error_message = None
                result.completed_at = None
    else:
        db.query(TaskResult).filter(TaskResult.task_id == task_id).delete(synchronize_session=False)

        for data in data_list:
            db.add(TaskResult(
                task_id=task_id,
                data_id=data.id,
                status=TaskResultStatus.pending.value,
                scoring_status=TaskScoringStatus.not_scored.value,
                model_output=None,
                input_tokens=None,
                output_tokens=None,
                score=None,
                recall=None,
                accuracy=None,
                score_reason=None,
                scoring_error_message=None,
                scoring_model=None,
                scoring_started_at=None,
                scoring_completed_at=None,
                error_message=None,
                completed_at=None,
            ))
    
    task.status = TaskStatus.running.value
    task.completed_at = None
    db.commit()
    
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _run_evaluation_task, task_id, target_data_ids)
    
    return {"message": "任务已启动", "task_id": task_id}


@router.get("/{task_id}/results", response_model=TaskResultListResponse, summary="获取评测结果列表")
def get_task_results(
    task_id: int,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db)
):
    task = db.query(EvaluationTask).filter(EvaluationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="评测任务不存在")
    
    query = db.query(TaskResult).filter(TaskResult.task_id == task_id)
    total = query.count()
    results = query.order_by(TaskResult.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    return TaskResultListResponse(items=results, total=total)


@router.post("/{task_id}/score", summary="智能评分评测结果")
def score_task_results(
    task_id: int,
    payload: Optional[EvaluationTaskScoreRequest] = None,
    db: Session = Depends(get_db),
):
    task = db.query(EvaluationTask).filter(EvaluationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="评测任务不存在")

    results = db.query(TaskResult, Annotation)\
        .join(EvaluationData, TaskResult.data_id == EvaluationData.id)\
        .outerjoin(Annotation, EvaluationData.id == Annotation.data_id)\
        .filter(TaskResult.task_id == task_id)\
        .order_by(TaskResult.id.asc())\
        .all()
    target_result_ids = payload.result_ids if payload and payload.result_ids else None
    if target_result_ids:
        results = [(result, annotation) for result, annotation in results if result.id in set(target_result_ids)]
    if not results:
        raise HTTPException(status_code=400, detail="暂无可评分结果")

    scored_count = 0
    skipped_count = 0
    failed_count = 0
    scoreable_result_ids: list[int] = []

    for result, annotation in results:
        if not result.model_output or not annotation or not annotation.ground_truth:
            skipped_count += 1
            continue
        scoreable_result_ids.append(result.id)

    with ThreadPoolExecutor(max_workers=TASK_SCORING_BATCH_SIZE) as executor:
        for batch_ids in _chunked(scoreable_result_ids, TASK_SCORING_BATCH_SIZE):
            futures = [
                executor.submit(_score_single_task_result, result_id, task.scoring_criteria)
                for result_id in batch_ids
            ]
            for future in as_completed(futures):
                try:
                    outcome, _ = future.result()
                except Exception:
                    logger.exception(
                        "智能评分并发 worker 异常: task_id=%s model=%s",
                        task_id,
                        SMART_SCORING_MODEL,
                    )
                    outcome = "failed"

                if outcome == "scored":
                    scored_count += 1
                elif outcome == "skipped":
                    skipped_count += 1
                else:
                    failed_count += 1

    return {
        "message": "智能评分完成",
        "task_id": task_id,
        "scored_count": scored_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "model": SMART_SCORING_MODEL,
    }


@router.get("/{task_id}/results/detail", response_model=TaskResultDetailListResponse, summary="获取评测结果详情列表")
def get_task_results_detail(
    task_id: int,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=100, description="每页数量"),
    status: Optional[TaskResultStatus] = Query(None, description="任务运行状态"),
    scoring_status: Optional[TaskScoringStatus] = Query(None, description="评分状态"),
    db: Session = Depends(get_db)
):
    task = db.query(EvaluationTask).filter(EvaluationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="评测任务不存在")

    result_query = db.query(TaskResult).filter(TaskResult.task_id == task_id)
    if status is not None:
        result_query = result_query.filter(TaskResult.status == status.value)
    if scoring_status is not None:
        result_query = result_query.filter(TaskResult.scoring_status == scoring_status.value)

    total = result_query.count()

    results = db.query(TaskResult, EvaluationData, Annotation)\
        .join(EvaluationData, TaskResult.data_id == EvaluationData.id)\
        .outerjoin(Annotation, EvaluationData.id == Annotation.data_id)\
        .filter(TaskResult.task_id == task_id)\
        .filter(TaskResult.status == status.value if status is not None else True)\
        .filter(TaskResult.scoring_status == scoring_status.value if scoring_status is not None else True)\
        .order_by(EvaluationData.id.asc())\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()
    
    tos_client = get_tos_client()
    
    score_avg_row = db.query(
        func.avg(TaskResult.recall),
        func.avg(TaskResult.accuracy),
    ).filter(
        TaskResult.task_id == task_id,
        TaskResult.scoring_status == TaskScoringStatus.scored.value,
    ).first()

    token_avg_row = db.query(
        func.avg(TaskResult.input_tokens),
        func.avg(TaskResult.output_tokens),
    ).filter(
        TaskResult.task_id == task_id,
    ).first()

    response_list = []
    for result, data, annotation in results:
        download_url = tos_client.get_download_url(data.tos_key)
        response_list.append(TaskResultDetailResponse(
            id=result.id,
            task_id=result.task_id,
            data_id=result.data_id,
            status=result.status,
            model_output=result.model_output,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            score=result.score,
            recall=result.recall,
            accuracy=result.accuracy,
            score_reason=result.score_reason,
            scoring_status=result.scoring_status,
            scoring_error_message=result.scoring_error_message,
            scoring_model=result.scoring_model,
            error_message=result.error_message,
            created_at=result.created_at,
            updated_at=result.updated_at,
            completed_at=result.completed_at,
            scoring_started_at=result.scoring_started_at,
            scoring_completed_at=result.scoring_completed_at,
            file_name=data.file_name,
            file_type=data.file_type,
            download_url=download_url,
            ground_truth=annotation.ground_truth if annotation else None
        ))

    return TaskResultDetailListResponse(
        items=response_list,
        total=total,
        avg_recall=float(score_avg_row[0]) if score_avg_row and score_avg_row[0] is not None else None,
        avg_accuracy=float(score_avg_row[1]) if score_avg_row and score_avg_row[1] is not None else None,
        avg_input_tokens=float(token_avg_row[0]) if token_avg_row and token_avg_row[0] is not None else None,
        avg_output_tokens=float(token_avg_row[1]) if token_avg_row and token_avg_row[1] is not None else None,
    )


@router.get("/{task_id}/results/selection", response_model=TaskResultSelectionResponse, summary="获取筛选结果ID集合")
def get_task_result_selection(
    task_id: int,
    status: Optional[TaskResultStatus] = Query(None, description="任务运行状态"),
    scoring_status: Optional[TaskScoringStatus] = Query(None, description="评分状态"),
    db: Session = Depends(get_db),
):
    task = db.query(EvaluationTask).filter(EvaluationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="评测任务不存在")

    query = db.query(TaskResult.id, TaskResult.data_id).filter(TaskResult.task_id == task_id)
    if status is not None:
        query = query.filter(TaskResult.status == status.value)
    if scoring_status is not None:
        query = query.filter(TaskResult.scoring_status == scoring_status.value)

    rows = query.order_by(TaskResult.id.asc()).all()
    return TaskResultSelectionResponse(
        total=len(rows),
        result_ids=[row[0] for row in rows],
        data_ids=[row[1] for row in rows],
    )


def _run_evaluation_task(task_id: int, target_data_ids: Optional[list[int]] = None):
    db = SessionLocal()
    try:
        task = db.query(EvaluationTask).filter(EvaluationTask.id == task_id).first()
        if not task:
            return

        dataset = db.query(Dataset).filter(Dataset.id == task.dataset_id).first()
        if not dataset:
            task.status = TaskStatus.failed.value
            task.completed_at = datetime.now()
            db.commit()
            return

        data_query = db.query(EvaluationData).filter(EvaluationData.dataset_id == task.dataset_id)
        if target_data_ids:
            data_query = data_query.filter(EvaluationData.id.in_(target_data_ids))
        data_list = data_query.all()
        if not data_list:
            task.status = TaskStatus.completed.value
            task.completed_at = datetime.now()
            db.commit()
            return

        try:
            _get_inference_client(task.model_provider)
        except Exception as exc:
            _mark_task_results_failed(db, task_id, str(exc))
            task.status = TaskStatus.failed.value
            task.completed_at = datetime.now()
            db.commit()
            return

        annotation_prompt = task.prompt or dataset.annotation_prompt
        custom_tags = None
        if dataset.custom_tags:
            try:
                import json
                custom_tags = json.loads(dataset.custom_tags)
            except Exception:
                custom_tags = None

        data_ids = [data.id for data in data_list]
        has_failure = False

        with ThreadPoolExecutor(max_workers=TASK_INFERENCE_BATCH_SIZE) as executor:
            for batch_ids in _chunked(data_ids, TASK_INFERENCE_BATCH_SIZE):
                futures = [
                    executor.submit(
                        _run_single_task_result,
                        task_id,
                        data_id,
                        annotation_prompt,
                        custom_tags,
                        task.target_model,
                        task.model_provider,
                        _normalize_fps(task.fps or DEFAULT_VIDEO_FPS),
                    )
                    for data_id in batch_ids
                ]
                for future in as_completed(futures):
                    try:
                        succeeded = future.result()
                    except Exception:
                        logger.exception(
                            "评测任务并发 worker 异常: task_id=%s provider=%s model=%s",
                            task_id,
                            task.model_provider,
                            task.target_model,
                        )
                        succeeded = False
                    if not succeeded:
                        has_failure = True

        task.status = TaskStatus.failed.value if has_failure else TaskStatus.completed.value
        task.completed_at = datetime.now()
        db.commit()
    finally:
        db.close()
