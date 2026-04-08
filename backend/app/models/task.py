from datetime import datetime
from sqlalchemy import Column, BigInteger, String, Text, Enum, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import relationship
from app.models.base import Base


class EvaluationTask(Base):
    __tablename__ = "evaluation_tasks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    dataset_id = Column(BigInteger, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, comment="评测集ID")
    name = Column(String(255), nullable=False, comment="任务名称")
    target_model = Column(String(100), nullable=False, comment="目标模型")
    model_provider = Column(String(50), comment="模型供应商")
    scoring_criteria = Column(Text, comment="评分标准")
    status = Column(
        Enum("pending", "running", "completed", "failed", name="task_status"),
        default="pending",
        comment="任务状态"
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")
    completed_at = Column(DateTime(timezone=True), comment="完成时间")

    dataset = relationship("Dataset", back_populates="tasks")
    results = relationship("TaskResult", back_populates="task", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_evaluation_tasks_dataset_id", "dataset_id"),
        Index("idx_evaluation_tasks_status", "status"),
        Index("idx_evaluation_tasks_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<EvaluationTask(id={self.id}, name='{self.name}')>"


class TaskResult(Base):
    __tablename__ = "task_results"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, ForeignKey("evaluation_tasks.id", ondelete="CASCADE"), nullable=False, comment="任务ID")
    data_id = Column(BigInteger, ForeignKey("evaluation_data.id", ondelete="CASCADE"), nullable=False, comment="评测数据ID")
    model_output = Column(Text, comment="模型输出")
    score = Column(BigInteger, comment="评分")
    score_reason = Column(Text, comment="评分原因")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")

    task = relationship("EvaluationTask", back_populates="results")
    data = relationship("EvaluationData", back_populates="results")

    __table_args__ = (
        Index("idx_task_results_task_id", "task_id"),
        Index("idx_task_results_data_id", "data_id"),
        Index("idx_task_results_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<TaskResult(id={self.id}, task_id={self.task_id})>"
