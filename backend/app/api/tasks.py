from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
import asyncio
from datetime import datetime

from app.core.database import get_db
from app.core.config import get_settings
from app.models import EvaluationTask, TaskResult, Dataset, EvaluationData, Annotation
from app.schemas.task import (
    EvaluationTaskCreate,
    EvaluationTaskUpdate,
    EvaluationTaskResponse,
    EvaluationTaskListResponse,
    TaskResultResponse,
    TaskResultListResponse,
    TaskResultDetailResponse,
    TaskStatus,
)
from app.utils import get_tos_client
from app.services import get_ark_client

router = APIRouter(prefix="/tasks", tags=["评测任务"])

_running_tasks: dict[str, dict] = {}


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
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db)
):
    query = db.query(EvaluationTask)
    
    if dataset_id:
        query = query.filter(EvaluationTask.dataset_id == dataset_id)
    if status:
        query = query.filter(EvaluationTask.status == status.value)
    
    total = query.count()
    tasks = query.order_by(EvaluationTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
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
def run_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(EvaluationTask).filter(EvaluationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="评测任务不存在")
    
    if task.status == TaskStatus.running.value:
        raise HTTPException(status_code=400, detail="任务正在运行中")
    
    task.status = TaskStatus.running.value
    db.commit()
    
    asyncio.create_task(_run_evaluation_task(task_id, db))
    
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


@router.get("/{task_id}/results/detail", response_model=list[TaskResultDetailResponse], summary="获取评测结果详情列表")
def get_task_results_detail(
    task_id: int,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db)
):
    task = db.query(EvaluationTask).filter(EvaluationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="评测任务不存在")
    
    results = db.query(TaskResult, EvaluationData, Annotation)\
        .join(EvaluationData, TaskResult.data_id == EvaluationData.id)\
        .outerjoin(Annotation, EvaluationData.id == Annotation.data_id)\
        .filter(TaskResult.task_id == task_id)\
        .order_by(TaskResult.created_at.desc())\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()
    
    tos_client = get_tos_client()
    
    response_list = []
    for result, data, annotation in results:
        download_url = tos_client.get_download_url(data.tos_key)
        response_list.append(TaskResultDetailResponse(
            id=result.id,
            task_id=result.task_id,
            data_id=result.data_id,
            model_output=result.model_output,
            score=result.score,
            score_reason=result.score_reason,
            created_at=result.created_at,
            file_name=data.file_name,
            file_type=data.file_type,
            download_url=download_url,
            ground_truth=annotation.ground_truth if annotation else None
        ))
    
    return response_list


async def _run_evaluation_task(task_id: int, db: Session):
    settings = get_settings()
    ark_client = get_ark_client()
    
    task = db.query(EvaluationTask).filter(EvaluationTask.id == task_id).first()
    if not task:
        return
    
    dataset = db.query(Dataset).filter(Dataset.id == task.dataset_id).first()
    if not dataset:
        task.status = TaskStatus.failed.value
        db.commit()
        return
    
    data_list = db.query(EvaluationData).filter(EvaluationData.dataset_id == task.dataset_id).all()
    
    annotation_prompt = dataset.annotation_prompt
    custom_tags = None
    if dataset.custom_tags:
        try:
            import json
            custom_tags = json.loads(dataset.custom_tags)
        except:
            pass
    
    tos_client = get_tos_client()
    
    for data in data_list:
        try:
            download_url = tos_client.get_download_url(data.tos_key)
            
            is_gif = data.file_type.lower() == "gif"
            
            if is_gif:
                model_output = ark_client.annotate_gif(
                    download_url,
                    annotation_prompt,
                    custom_tags,
                    task.target_model
                )
            else:
                content = ark_client.build_annotation_content(
                    download_url,
                    data.file_type,
                    annotation_prompt,
                    custom_tags
                )
                model_output = ark_client.annotate(content, task.target_model)
            
            result = TaskResult(
                task_id=task_id,
                data_id=data.id,
                model_output=model_output,
                score=None,
                score_reason=None
            )
            db.add(result)
            db.commit()
        except Exception as e:
            print(f"Evaluation error for data_id {data.id}: {e}")
    
    task.status = TaskStatus.completed.value
    task.completed_at = datetime.now()
    db.commit()
