from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import TaskPromptTemplate
from app.schemas.dataset import DatasetScene
from app.schemas.prompt_template import (
    TaskPromptTemplateCreate,
    TaskPromptTemplateListResponse,
    TaskPromptTemplateResponse,
    TaskPromptTemplateUpdate,
)

router = APIRouter(prefix="/prompt-templates", tags=["任务 Prompt 模板"])


@router.get("", response_model=TaskPromptTemplateListResponse, summary="获取任务 Prompt 模板列表")
def list_prompt_templates(
    scene: Optional[DatasetScene] = Query(None, description="业务场景"),
    db: Session = Depends(get_db),
):
    query = db.query(TaskPromptTemplate)
    if scene:
        query = query.filter(TaskPromptTemplate.scene == scene.value)
    items = query.order_by(TaskPromptTemplate.created_at.desc()).all()
    return TaskPromptTemplateListResponse(
        items=[TaskPromptTemplateResponse.model_validate(item) for item in items],
        total=len(items),
    )


@router.post("", response_model=TaskPromptTemplateResponse, summary="创建任务 Prompt 模板")
def create_prompt_template(
    payload: TaskPromptTemplateCreate,
    db: Session = Depends(get_db),
):
    item = TaskPromptTemplate(
        name=payload.name.strip(),
        scene=payload.scene.value,
        description=payload.description.strip() if payload.description else None,
        content=payload.content.strip(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return TaskPromptTemplateResponse.model_validate(item)


@router.put("/{template_id}", response_model=TaskPromptTemplateResponse, summary="更新任务 Prompt 模板")
def update_prompt_template(
    template_id: int,
    payload: TaskPromptTemplateUpdate,
    db: Session = Depends(get_db),
):
    item = db.query(TaskPromptTemplate).filter(TaskPromptTemplate.id == template_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="任务 Prompt 模板不存在")

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
    return TaskPromptTemplateResponse.model_validate(item)


@router.delete("/{template_id}", summary="删除任务 Prompt 模板")
def delete_prompt_template(
    template_id: int,
    db: Session = Depends(get_db),
):
    item = db.query(TaskPromptTemplate).filter(TaskPromptTemplate.id == template_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="任务 Prompt 模板不存在")
    db.delete(item)
    db.commit()
    return {"message": "任务 Prompt 模板已删除"}
