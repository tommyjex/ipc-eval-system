from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
import uuid
import asyncio
import json

from app.core.database import get_db
from app.core.config import get_settings
from app.models import EvaluationData, Annotation, Dataset
from app.schemas import (
    AnnotationCreate,
    AnnotationUpdate,
    AnnotationResponse,
    BatchAnnotationRequest,
    AIAnnotationRequest,
    AIAnnotationStatus,
    AnnotationType,
    DataStatus,
)
from app.utils import get_tos_client
from app.services import get_ark_client

router = APIRouter()

_ai_annotation_tasks: dict[str, AIAnnotationStatus] = {}


@router.post(
    "/data/{data_id}/annotations",
    response_model=AnnotationResponse,
    summary="创建单条标注"
)
def create_annotation(data_id: int, data: AnnotationCreate, db: Session = Depends(get_db)):
    eval_data = db.query(EvaluationData).filter(EvaluationData.id == data_id).first()
    if not eval_data:
        raise HTTPException(status_code=404, detail="评测数据不存在")

    existing = db.query(Annotation).filter(Annotation.data_id == data_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="该数据已有标注，请使用更新接口")

    annotation = Annotation(
        data_id=data_id,
        ground_truth=data.ground_truth,
        annotation_type=data.annotation_type.value,
        model_name=data.model_name,
        annotator_id=data.annotator_id,
    )
    db.add(annotation)
    eval_data.status = DataStatus.annotated.value
    db.commit()
    db.refresh(annotation)
    return _to_annotation_response(annotation)


@router.post(
    "/batch-annotations",
    response_model=list[AnnotationResponse],
    summary="批量人工标注"
)
def batch_create_annotations(data: BatchAnnotationRequest, db: Session = Depends(get_db)):
    eval_data_list = db.query(EvaluationData).filter(EvaluationData.id.in_(data.data_ids)).all()
    if len(eval_data_list) != len(data.data_ids):
        raise HTTPException(status_code=400, detail="部分数据不存在")

    annotations = []
    for eval_data in eval_data_list:
        existing = db.query(Annotation).filter(Annotation.data_id == eval_data.id).first()
        if existing:
            existing.ground_truth = data.ground_truth
            existing.annotation_type = AnnotationType.manual.value
            annotations.append(existing)
        else:
            annotation = Annotation(
                data_id=eval_data.id,
                ground_truth=data.ground_truth,
                annotation_type=AnnotationType.manual.value,
            )
            db.add(annotation)
            annotations.append(annotation)
        eval_data.status = DataStatus.annotated.value

    db.commit()
    return [_to_annotation_response(a) for a in annotations]


@router.post(
    "/ai-annotations",
    response_model=AIAnnotationStatus,
    summary="大模型标注（异步）"
)
async def create_ai_annotations(data: AIAnnotationRequest, db: Session = Depends(get_db)):
    eval_data_list = db.query(EvaluationData).filter(EvaluationData.id.in_(data.data_ids)).all()
    if len(eval_data_list) != len(data.data_ids):
        raise HTTPException(status_code=400, detail="部分数据不存在")

    task_id = str(uuid.uuid4())
    _ai_annotation_tasks[task_id] = AIAnnotationStatus(
        task_id=task_id,
        status="pending",
        total=len(data.data_ids),
        completed=0,
        failed=0,
    )

    asyncio.create_task(_process_ai_annotations(task_id, data.data_ids, data.model, data.prompt, db))

    return _ai_annotation_tasks[task_id]


@router.get(
    "/ai-annotations/{task_id}",
    response_model=AIAnnotationStatus,
    summary="查询大模型标注状态"
)
def get_ai_annotation_status(task_id: str):
    if task_id not in _ai_annotation_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _ai_annotation_tasks[task_id]


@router.get(
    "/data/{data_id}/annotations",
    response_model=AnnotationResponse,
    summary="获取标注结果"
)
def get_annotation(data_id: int, db: Session = Depends(get_db)):
    annotation = db.query(Annotation).filter(Annotation.data_id == data_id).first()
    if not annotation:
        raise HTTPException(status_code=404, detail="标注不存在")
    return _to_annotation_response(annotation)


@router.put(
    "/annotations/{annotation_id}",
    response_model=AnnotationResponse,
    summary="更新标注"
)
def update_annotation(annotation_id: int, data: AnnotationUpdate, db: Session = Depends(get_db)):
    annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
    if not annotation:
        raise HTTPException(status_code=404, detail="标注不存在")

    if data.ground_truth is not None:
        annotation.ground_truth = data.ground_truth

    db.commit()
    db.refresh(annotation)
    return _to_annotation_response(annotation)


async def _process_ai_annotations(
    task_id: str,
    data_ids: list[int],
    model: Optional[str],
    prompt: Optional[str],
    db: Session
):
    ark_client = get_ark_client()
    settings = get_settings()

    first_data = db.query(EvaluationData).filter(EvaluationData.id == data_ids[0]).first()
    if not first_data:
        _ai_annotation_tasks[task_id].status = "completed"
        return

    dataset = db.query(Dataset).filter(Dataset.id == first_data.dataset_id).first()
    annotation_prompt = prompt or (dataset.annotation_prompt if dataset else None)
    custom_tags = None
    if dataset and dataset.custom_tags:
        try:
            custom_tags = json.loads(dataset.custom_tags)
        except:
            custom_tags = None

    for data_id in data_ids:
        try:
            eval_data = db.query(EvaluationData).filter(EvaluationData.id == data_id).first()
            if not eval_data:
                _ai_annotation_tasks[task_id].failed += 1
                continue

            tos_client = get_tos_client()
            download_url = tos_client.get_download_url(eval_data.tos_key)

            is_gif = eval_data.file_type.lower() == "gif"
            
            if is_gif:
                result = ark_client.annotate_gif(
                    download_url,
                    annotation_prompt,
                    custom_tags,
                    model or settings.ark_model
                )
            else:
                content = ark_client.build_annotation_content(
                    download_url,
                    eval_data.file_type,
                    annotation_prompt,
                    custom_tags
                )
                result = ark_client.annotate(content, model or settings.ark_model)

            annotation = db.query(Annotation).filter(Annotation.data_id == data_id).first()
            if annotation:
                annotation.ground_truth = result
                annotation.annotation_type = AnnotationType.ai.value
                annotation.model_name = model or settings.ark_model
            else:
                annotation = Annotation(
                    data_id=data_id,
                    ground_truth=result,
                    annotation_type=AnnotationType.ai.value,
                    model_name=model or settings.ark_model,
                )
                db.add(annotation)

            eval_data.status = DataStatus.annotated.value
            db.commit()

            _ai_annotation_tasks[task_id].completed += 1
        except Exception as e:
            print(f"AI annotation error for data_id {data_id}: {e}")
            _ai_annotation_tasks[task_id].failed += 1

    _ai_annotation_tasks[task_id].status = "completed"


def _to_annotation_response(annotation: Annotation) -> AnnotationResponse:
    return AnnotationResponse(
        id=annotation.id,
        data_id=annotation.data_id,
        ground_truth=annotation.ground_truth,
        annotation_type=AnnotationType(annotation.annotation_type),
        model_name=annotation.model_name,
        annotator_id=annotation.annotator_id,
        created_at=annotation.created_at,
        updated_at=annotation.updated_at,
    )
