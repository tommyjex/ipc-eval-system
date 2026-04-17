from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import ScoringCriteriaTemplate
from app.schemas.dataset import DatasetScene
from app.schemas.scoring_template import (
    ScoringCriteriaTemplateCreate,
    ScoringCriteriaTemplateListResponse,
    ScoringCriteriaTemplateResponse,
    ScoringCriteriaTemplateUpdate,
)

router = APIRouter(prefix="/scoring-templates", tags=["评分标准模板"])


@router.get("", response_model=ScoringCriteriaTemplateListResponse, summary="获取评分标准模板列表")
def list_scoring_templates(
    scene: Optional[DatasetScene] = Query(None, description="业务场景"),
    db: Session = Depends(get_db),
):
    query = db.query(ScoringCriteriaTemplate)
    if scene:
        query = query.filter(ScoringCriteriaTemplate.scene == scene.value)
    items = query.order_by(ScoringCriteriaTemplate.created_at.desc()).all()
    return ScoringCriteriaTemplateListResponse(
        items=[ScoringCriteriaTemplateResponse.model_validate(item) for item in items],
        total=len(items),
    )


@router.post("", response_model=ScoringCriteriaTemplateResponse, summary="创建评分标准模板")
def create_scoring_template(
    payload: ScoringCriteriaTemplateCreate,
    db: Session = Depends(get_db),
):
    item = ScoringCriteriaTemplate(
        name=payload.name.strip(),
        scene=payload.scene.value,
        description=payload.description.strip() if payload.description else None,
        content=payload.content.strip(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return ScoringCriteriaTemplateResponse.model_validate(item)


@router.put("/{template_id}", response_model=ScoringCriteriaTemplateResponse, summary="更新评分标准模板")
def update_scoring_template(
    template_id: int,
    payload: ScoringCriteriaTemplateUpdate,
    db: Session = Depends(get_db),
):
    item = db.query(ScoringCriteriaTemplate).filter(ScoringCriteriaTemplate.id == template_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="评分标准模板不存在")

    if payload.name is not None:
        item.name = payload.name.strip()
    if payload.scene is not None:
        item.scene = payload.scene.value
    if payload.description is not None:
        item.description = payload.description.strip() or None
    if payload.content is not None:
        item.content = payload.content.strip()

    db.commit()
    db.refresh(item)
    return ScoringCriteriaTemplateResponse.model_validate(item)


@router.delete("/{template_id}", summary="删除评分标准模板")
def delete_scoring_template(
    template_id: int,
    db: Session = Depends(get_db),
):
    item = db.query(ScoringCriteriaTemplate).filter(ScoringCriteriaTemplate.id == template_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="评分标准模板不存在")
    db.delete(item)
    db.commit()
    return {"message": "评分标准模板已删除"}
