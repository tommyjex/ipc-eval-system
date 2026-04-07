import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.models import Dataset, EvaluationData
from app.schemas import (
    DatasetCreate,
    DatasetUpdate,
    DatasetResponse,
    DatasetListResponse,
    DatasetType,
    DatasetScene,
    DatasetStatus,
    DataStatus,
)

router = APIRouter()


@router.post("", response_model=DatasetResponse, summary="创建评测集")
def create_dataset(data: DatasetCreate, db: Session = Depends(get_db)):
    dataset = Dataset(
        name=data.name,
        description=data.description,
        type=data.type.value,
        scene=data.scene.value if data.scene else None,
        annotation_prompt=data.annotation_prompt,
        custom_tags=json.dumps(data.custom_tags, ensure_ascii=False) if data.custom_tags else None,
        status=DatasetStatus.draft.value,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return _to_dataset_response(dataset)


@router.get("", response_model=DatasetListResponse, summary="获取评测集列表")
def list_datasets(
    type: Optional[DatasetType] = Query(None, description="评测集类型"),
    status: Optional[DatasetStatus] = Query(None, description="评测集状态"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db)
):
    query = db.query(Dataset)

    if type:
        query = query.filter(Dataset.type == type.value)
    if status:
        query = query.filter(Dataset.status == status.value)
    if keyword:
        query = query.filter(Dataset.name.contains(keyword))

    total = query.count()
    datasets = query.order_by(Dataset.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return DatasetListResponse(
        items=[_to_dataset_response(d) for d in datasets],
        total=total
    )


@router.get("/{dataset_id}", response_model=DatasetResponse, summary="获取评测集详情")
def get_dataset(dataset_id: int, db: Session = Depends(get_db)):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="评测集不存在")
    return _to_dataset_response(dataset)


@router.put("/{dataset_id}", response_model=DatasetResponse, summary="更新评测集")
def update_dataset(dataset_id: int, data: DatasetUpdate, db: Session = Depends(get_db)):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="评测集不存在")

    if data.name is not None:
        dataset.name = data.name
    if data.description is not None:
        dataset.description = data.description
    if data.status is not None:
        dataset.status = data.status.value
    if data.scene is not None:
        dataset.scene = data.scene.value
    if data.annotation_prompt is not None:
        dataset.annotation_prompt = data.annotation_prompt
    if data.custom_tags is not None:
        dataset.custom_tags = json.dumps(data.custom_tags, ensure_ascii=False)

    db.commit()
    db.refresh(dataset)
    return _to_dataset_response(dataset)


@router.delete("/{dataset_id}", summary="删除评测集")
def delete_dataset(dataset_id: int, db: Session = Depends(get_db)):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="评测集不存在")

    db.delete(dataset)
    db.commit()
    return {"message": "删除成功"}


def _to_dataset_response(dataset: Dataset) -> DatasetResponse:
    data_count = len(dataset.evaluation_data) if dataset.evaluation_data else 0
    annotated_count = sum(
        1 for d in dataset.evaluation_data if d.status == DataStatus.annotated.value
    ) if dataset.evaluation_data else 0

    custom_tags = None
    if dataset.custom_tags:
        try:
            custom_tags = json.loads(dataset.custom_tags)
        except:
            custom_tags = None

    return DatasetResponse(
        id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        type=DatasetType(dataset.type),
        scene=DatasetScene(dataset.scene) if dataset.scene else None,
        annotation_prompt=dataset.annotation_prompt,
        custom_tags=custom_tags,
        status=DatasetStatus(dataset.status),
        data_count=data_count,
        annotated_count=annotated_count,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
    )
