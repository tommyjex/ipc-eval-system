from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
import asyncio
from collections import deque
import logging
import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import time

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
TASK_SINGLE_TIMEOUT_SECONDS = get_settings().task_single_timeout_seconds
INFERENCE_PROCESS_CONTEXT = mp.get_context("spawn")
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


def _set_task_result_failed(result: TaskResult, error_message: str):
    result.status = TaskResultStatus.failed.value
    result.model_output = None
    result.input_tokens = None
    result.output_tokens = None
    result.score = None
    result.recall = None
    result.accuracy = None
    result.score_reason = None
    result.scoring_status = TaskScoringStatus.not_scored.value
    result.scoring_error_message = None
    result.scoring_model = None
    result.scoring_started_at = None
    result.scoring_completed_at = None
    result.error_message = error_message
    result.completed_at = datetime.now()


def _mark_pending_task_results_failed(db: Session, task_id: int, error_message: str):
    db.query(TaskResult).filter(
        TaskResult.task_id == task_id,
        TaskResult.status == TaskResultStatus.pending.value,
    ).update(
        {
            TaskResult.status: TaskResultStatus.failed.value,
            TaskResult.model_output: None,
            TaskResult.input_tokens: None,
            TaskResult.output_tokens: None,
            TaskResult.score: None,
            TaskResult.recall: None,
            TaskResult.accuracy: None,
            TaskResult.score_reason: None,
            TaskResult.scoring_status: TaskScoringStatus.not_scored.value,
            TaskResult.scoring_error_message: None,
            TaskResult.scoring_model: None,
            TaskResult.scoring_started_at: None,
            TaskResult.scoring_completed_at: None,
            TaskResult.error_message: error_message,
            TaskResult.completed_at: datetime.now(),
        },
        synchronize_session=False,
    )


def _mark_selected_task_results_failed(
    db: Session,
    task_id: int,
    data_ids: list[int],
    error_message: str,
    statuses: Optional[list[str]] = None,
):
    query = db.query(TaskResult).filter(TaskResult.task_id == task_id)
    if data_ids:
        query = query.filter(TaskResult.data_id.in_(data_ids))
    if statuses:
        query = query.filter(TaskResult.status.in_(statuses))

    query.update(
        {
            TaskResult.status: TaskResultStatus.failed.value,
            TaskResult.model_output: None,
            TaskResult.input_tokens: None,
            TaskResult.output_tokens: None,
            TaskResult.score: None,
            TaskResult.recall: None,
            TaskResult.accuracy: None,
            TaskResult.score_reason: None,
            TaskResult.scoring_status: TaskScoringStatus.not_scored.value,
            TaskResult.scoring_error_message: None,
            TaskResult.scoring_model: None,
            TaskResult.scoring_started_at: None,
            TaskResult.scoring_completed_at: None,
            TaskResult.error_message: error_message,
            TaskResult.completed_at: datetime.now(),
        },
        synchronize_session=False,
    )


def _mark_running_task_results_failed(db: Session, task_id: int, error_message: str):
    _mark_selected_task_results_failed(
        db,
        task_id,
        [],
        error_message,
        statuses=[TaskResultStatus.running.value],
    )


def _run_single_task_result_process(
    child_conn,
    task_id: int,
    data_id: int,
    annotation_prompt: Optional[str],
    custom_tags: Optional[list[str]],
    target_model: Optional[str],
    model_provider: Optional[str],
    fps: float,
):
    try:
        success = _run_single_task_result(
            task_id,
            data_id,
            annotation_prompt,
            custom_tags,
            target_model,
            model_provider,
            fps,
        )
        child_conn.send({"success": success})
    except BaseException as exc:
        try:
            child_conn.send({"success": False, "error": repr(exc)})
        except Exception:
            pass
    finally:
        child_conn.close()


def _terminate_process(process: mp.Process):
    if not process.is_alive():
        return
    process.terminate()
    process.join(timeout=1)
    if process.is_alive():
        process.kill()
        process.join(timeout=1)


def _close_process_connection(connection):
    try:
        connection.close()
    except Exception:
        pass

def _prepare_task_results(
    db: Session,
    task_id: int,
    dataset_id: int,
    target_data_ids: Optional[list[int]] = None,
) -> list[EvaluationData]:
    data_query = db.query(EvaluationData).filter(EvaluationData.dataset_id == dataset_id)
    if target_data_ids:
        data_query = data_query.filter(EvaluationData.id.in_(target_data_ids))
    data_list = data_query.all()
    if not data_list:
        return []

    if target_data_ids:
        found_ids = {data.id for data in data_list}
        invalid_ids = [data_id for data_id in target_data_ids if data_id not in found_ids]
        if invalid_ids:
            raise ValueError(f"存在无效的数据ID: {invalid_ids[:10]}")

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

    db.commit()
    return data_list


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
        # #endregion
        if not result:
            error_message = "未找到 TaskResult 记录，任务初始化结果可能未完成或结果已被删除"
            # #endregion
            logger.error(
                "评测任务单条初始化异常: task_id=%s data_id=%s detail=%s",
                task_id,
                data_id,
                error_message,
            )
            if data:
                db.add(TaskResult(
                    task_id=task_id,
                    data_id=data_id,
                    status=TaskResultStatus.failed.value,
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
                    error_message=error_message,
                    completed_at=datetime.now(),
                ))
                db.commit()
            return False
        if not data:
            error_message = "未找到 EvaluationData 记录，评测数据可能已被删除"
            # #endregion
            logger.error(
                "评测任务单条初始化异常: task_id=%s data_id=%s detail=%s",
                task_id,
                data_id,
                error_message,
            )
            _set_task_result_failed(result, error_message)
            db.commit()
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
            _set_task_result_failed(result, str(exc))
            db.commit()
            return False

        result.status = TaskResultStatus.running.value
        result.error_message = None
        result.completed_at = None
        db.commit()
        # #endregion

        try:
            tos_client = get_tos_client()
            download_url = tos_client.get_download_url(data.tos_key)
            model_download_url = tos_client.get_download_url(data.tos_key, public_endpoint=True)
            lower_file_type = data.file_type.lower()
            is_gif = lower_file_type == "gif"

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
                    model_file_url=model_download_url,
                )
                inference_result = inference_client.annotate_with_usage(content, target_model)

            db.refresh(result)
            if result.status != TaskResultStatus.running.value:
                logger.warning(
                    "评测任务单条结果已被外部收尾，跳过成功回写: task_id=%s data_id=%s current_status=%s",
                    task_id,
                    data_id,
                    result.status,
                )
                return False

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
            # #endregion
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
            db.refresh(result)
            if result.status != TaskResultStatus.running.value:
                logger.warning(
                    "评测任务单条结果已被外部收尾，跳过失败回写: task_id=%s data_id=%s current_status=%s",
                    task_id,
                    data_id,
                    result.status,
                )
                return False
            _set_task_result_failed(result, str(exc))
            db.commit()
            # #endregion
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


def _get_target_task_result_ids(
    db: Session,
    task_id: int,
    target_result_ids: Optional[list[int]] = None,
) -> list[int]:
    query = db.query(TaskResult.id).filter(TaskResult.task_id == task_id)
    if target_result_ids:
        query = query.filter(TaskResult.id.in_(set(target_result_ids)))
    return [row[0] for row in query.order_by(TaskResult.id.asc()).all()]


def _get_scoreable_task_result_ids(
    db: Session,
    task_id: int,
    target_result_ids: Optional[list[int]] = None,
    scoring_statuses: Optional[list[str]] = None,
) -> list[int]:
    query = db.query(TaskResult.id)\
        .join(EvaluationData, TaskResult.data_id == EvaluationData.id)\
        .outerjoin(Annotation, EvaluationData.id == Annotation.data_id)\
        .filter(TaskResult.task_id == task_id)\
        .filter(TaskResult.model_output.isnot(None))\
        .filter(TaskResult.model_output != "")\
        .filter(Annotation.id.isnot(None))\
        .filter(Annotation.ground_truth.isnot(None))\
        .filter(Annotation.ground_truth != "")

    if target_result_ids:
        query = query.filter(TaskResult.id.in_(set(target_result_ids)))
    if scoring_statuses:
        query = query.filter(TaskResult.scoring_status.in_(scoring_statuses))

    return [row[0] for row in query.distinct().order_by(TaskResult.id.asc()).all()]


def _score_task_result_ids_concurrently(
    task_id: int,
    result_ids: list[int],
    scoring_criteria: Optional[str],
    max_workers: int,
):
    if not result_ids:
        return

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_score_single_task_result, result_id, scoring_criteria)
            for result_id in result_ids
        ]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception:
                logger.exception(
                    "智能评分并发 worker 异常: task_id=%s model=%s",
                    task_id,
                    SMART_SCORING_MODEL,
                )


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
    dataset_id: Optional[list[int]] = Query(None, description="评测集ID"),
    model_provider: Optional[list[str]] = Query(None, description="模型供应商"),
    target_model: Optional[list[str]] = Query(None, description="目标模型"),
    status: Optional[list[TaskStatus]] = Query(None, description="任务状态"),
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
        query = query.filter(EvaluationTask.dataset_id.in_(dataset_id))
    if model_provider:
        query = query.filter(EvaluationTask.model_provider.in_(model_provider))
    if target_model:
        query = query.filter(EvaluationTask.target_model.in_(target_model))
    if status:
        query = query.filter(EvaluationTask.status.in_([item.value for item in status]))

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

    target_result_ids = payload.result_ids if payload and payload.result_ids else None
    requested_result_ids = _get_target_task_result_ids(db, task_id, target_result_ids)
    if not requested_result_ids:
        raise HTTPException(status_code=400, detail="暂无可评分结果")

    scoreable_result_ids = _get_scoreable_task_result_ids(db, task_id, target_result_ids)
    _score_task_result_ids_concurrently(
        task_id,
        scoreable_result_ids,
        task.scoring_criteria,
        TASK_SCORING_BATCH_SIZE,
    )

    remaining_retry_ids = _get_scoreable_task_result_ids(
        db,
        task_id,
        target_result_ids,
        scoring_statuses=[
            TaskScoringStatus.not_scored.value,
            TaskScoringStatus.score_failed.value,
        ],
    )
    if remaining_retry_ids:
        retry_workers = max(1, min(16, len(remaining_retry_ids), TASK_SCORING_BATCH_SIZE))
        logger.warning(
            "智能评分补偿重试: task_id=%s retry_count=%s workers=%s",
            task_id,
            len(remaining_retry_ids),
            retry_workers,
        )
        _score_task_result_ids_concurrently(
            task_id,
            remaining_retry_ids,
            task.scoring_criteria,
            retry_workers,
        )

    final_statuses = [
        row[0]
        for row in db.query(TaskResult.scoring_status)
        .filter(TaskResult.id.in_(requested_result_ids))
        .all()
    ]
    scored_count = final_statuses.count(TaskScoringStatus.scored.value)
    skipped_count = final_statuses.count(TaskScoringStatus.not_scored.value)
    failed_count = final_statuses.count(TaskScoringStatus.score_failed.value)

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
    status: Optional[list[TaskResultStatus]] = Query(None, description="任务运行状态"),
    scoring_status: Optional[list[TaskScoringStatus]] = Query(None, description="评分状态"),
    db: Session = Depends(get_db)
):
    task = db.query(EvaluationTask).filter(EvaluationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="评测任务不存在")

    status_values = [item.value for item in status] if status else []
    scoring_status_values = [item.value for item in scoring_status] if scoring_status else []

    result_query = db.query(TaskResult).filter(TaskResult.task_id == task_id)
    if status_values:
        result_query = result_query.filter(TaskResult.status.in_(status_values))
    if scoring_status_values:
        result_query = result_query.filter(TaskResult.scoring_status.in_(scoring_status_values))

    total = result_query.count()

    results = db.query(TaskResult, EvaluationData, Annotation)\
        .join(EvaluationData, TaskResult.data_id == EvaluationData.id)\
        .outerjoin(Annotation, EvaluationData.id == Annotation.data_id)\
        .filter(TaskResult.task_id == task_id)\
        .filter(TaskResult.status.in_(status_values) if status_values else True)\
        .filter(TaskResult.scoring_status.in_(scoring_status_values) if scoring_status_values else True)\
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
    status: Optional[list[TaskResultStatus]] = Query(None, description="任务运行状态"),
    scoring_status: Optional[list[TaskScoringStatus]] = Query(None, description="评分状态"),
    db: Session = Depends(get_db),
):
    task = db.query(EvaluationTask).filter(EvaluationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="评测任务不存在")

    status_values = [item.value for item in status] if status else []
    scoring_status_values = [item.value for item in scoring_status] if scoring_status else []

    query = db.query(TaskResult.id, TaskResult.data_id).filter(TaskResult.task_id == task_id)
    if status_values:
        query = query.filter(TaskResult.status.in_(status_values))
    if scoring_status_values:
        query = query.filter(TaskResult.scoring_status.in_(scoring_status_values))

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
        try:
            data_list = _prepare_task_results(db, task_id, task.dataset_id, target_data_ids)
        except ValueError as exc:
            task.status = TaskStatus.failed.value
            task.completed_at = datetime.now()
            db.commit()
            logger.warning("评测任务初始化失败: task_id=%s detail=%s", task_id, str(exc))
            return
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
        pending_data_ids = deque(data_ids)
        active_workers: dict[int, dict] = {}

        def start_worker(next_data_id: int):
            parent_conn, child_conn = INFERENCE_PROCESS_CONTEXT.Pipe(duplex=False)
            process = INFERENCE_PROCESS_CONTEXT.Process(
                target=_run_single_task_result_process,
                args=(
                    child_conn,
                    task_id,
                    next_data_id,
                    annotation_prompt,
                    custom_tags,
                    task.target_model,
                    task.model_provider,
                    _normalize_fps(task.fps or DEFAULT_VIDEO_FPS),
                ),
            )
            process.start()
            child_conn.close()
            active_workers[next_data_id] = {
                "process": process,
                "conn": parent_conn,
                "started_at": time.monotonic(),
            }

        try:
            while pending_data_ids or active_workers:
                while pending_data_ids and len(active_workers) < TASK_INFERENCE_BATCH_SIZE:
                    start_worker(pending_data_ids.popleft())

                if not active_workers:
                    continue

                now = time.monotonic()
                timed_out_data_ids: list[int] = []

                for data_id, meta in list(active_workers.items()):
                    process = meta["process"]
                    conn = meta["conn"]

                    if process.is_alive():
                        if now - meta["started_at"] > TASK_SINGLE_TIMEOUT_SECONDS:
                            timed_out_data_ids.append(data_id)
                            _terminate_process(process)
                            _close_process_connection(conn)
                            active_workers.pop(data_id, None)
                        continue

                    payload = None
                    if conn.poll():
                        try:
                            payload = conn.recv()
                        except EOFError:
                            payload = None
                    process.join(timeout=0.2)
                    _close_process_connection(conn)
                    active_workers.pop(data_id, None)

                    succeeded = bool(payload and payload.get("success"))
                    if not succeeded:
                        has_failure = True

                if timed_out_data_ids:
                    has_failure = True
                    timeout_message = f"单条任务执行超时（执行时间 >{TASK_SINGLE_TIMEOUT_SECONDS}s）"
                    logger.error(
                        "评测任务存在超时结果: task_id=%s timeout_count=%s provider=%s model=%s data_ids=%s",
                        task_id,
                        len(timed_out_data_ids),
                        task.model_provider,
                        task.target_model,
                        timed_out_data_ids[:10],
                    )
                    _mark_selected_task_results_failed(
                        db,
                        task_id,
                        timed_out_data_ids,
                        timeout_message,
                        statuses=[
                            TaskResultStatus.pending.value,
                            TaskResultStatus.running.value,
                        ],
                    )
                    db.commit()
                time.sleep(0.2)
        finally:
            for meta in active_workers.values():
                _terminate_process(meta["process"])
                _close_process_connection(meta["conn"])

        pending_count = db.query(TaskResult).filter(
            TaskResult.task_id == task_id,
            TaskResult.status == TaskResultStatus.pending.value,
        ).count()
        if pending_count > 0:
            has_failure = True
            error_message = "任务执行中断，结果未开始执行"
            logger.error(
                "评测任务存在残留 pending 结果: task_id=%s pending_count=%s",
                task_id,
                pending_count,
            )
            _mark_pending_task_results_failed(db, task_id, error_message)
            db.commit()

        running_count = db.query(TaskResult).filter(
            TaskResult.task_id == task_id,
            TaskResult.status == TaskResultStatus.running.value,
        ).count()
        if running_count > 0:
            has_failure = True
            error_message = "任务执行超时，结果未完成"
            logger.error(
                "评测任务存在残留 running 结果: task_id=%s running_count=%s",
                task_id,
                running_count,
            )
            _mark_running_task_results_failed(db, task_id, error_message)
            db.commit()

        task.status = TaskStatus.failed.value if has_failure else TaskStatus.completed.value
        task.completed_at = datetime.now()
        db.commit()
    except Exception as exc:
        logger.exception("评测任务主调度异常退出: task_id=%s", task_id)
        db.rollback()
        error_message = f"评测任务主调度异常退出: {type(exc).__name__}: {exc}"
        _mark_pending_task_results_failed(db, task_id, error_message)
        _mark_running_task_results_failed(db, task_id, error_message)
        task = db.query(EvaluationTask).filter(EvaluationTask.id == task_id).first()
        if task:
            task.status = TaskStatus.failed.value
            task.completed_at = datetime.now()
        db.commit()
    finally:
        db.close()
