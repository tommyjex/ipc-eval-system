from sqlalchemy import Column, BigInteger, String, Text, DateTime, Index
from sqlalchemy.sql import func

from app.models.base import Base


class TaskPromptTemplate(Base):
    __tablename__ = "task_prompt_templates"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment="模板名称")
    scene = Column(String(50), nullable=False, comment="业务场景")
    description = Column(String(500), comment="模板描述")
    content = Column(Text, nullable=False, comment="任务 Prompt 模板内容")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        Index("idx_prompt_templates_scene", "scene"),
        Index("idx_prompt_templates_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<TaskPromptTemplate(id={self.id}, name='{self.name}', scene='{self.scene}')>"
