from datetime import datetime
from sqlalchemy import Column, BigInteger, String, Text, Enum, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment="评测集名称")
    description = Column(Text, comment="评测集描述")
    type = Column(Enum("video", "image", "mixed", name="dataset_type"), nullable=False, comment="评测集类型")
    scene = Column(String(50), comment="业务场景")
    annotation_prompt = Column(Text, comment="标注提示词")
    custom_tags = Column(Text, comment="自定义标签，JSON数组格式")
    status = Column(
        Enum("draft", "ready", "archived", name="dataset_status"),
        default="draft",
        comment="评测集状态"
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")

    evaluation_data = relationship("EvaluationData", back_populates="dataset", cascade="all, delete-orphan")
    tasks = relationship("EvaluationTask", back_populates="dataset", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_datasets_status", "status"),
        Index("idx_datasets_type", "type"),
        Index("idx_datasets_scene", "scene"),
        Index("idx_datasets_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<Dataset(id={self.id}, name='{self.name}')>"


class EvaluationData(Base):
    __tablename__ = "evaluation_data"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    dataset_id = Column(BigInteger, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, comment="评测集ID")
    file_name = Column(String(255), nullable=False, comment="文件名")
    file_type = Column(String(50), nullable=False, comment="文件类型")
    file_size = Column(BigInteger, nullable=False, comment="文件大小(字节)")
    tos_key = Column(String(500), nullable=False, comment="TOS对象键")
    tos_bucket = Column(String(100), nullable=False, comment="TOS存储桶")
    status = Column(
        Enum("pending", "annotated", "failed", name="data_status"),
        default="pending",
        comment="标注状态"
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")

    dataset = relationship("Dataset", back_populates="evaluation_data")
    annotations = relationship("Annotation", back_populates="evaluation_data", cascade="all, delete-orphan")
    results = relationship("TaskResult", back_populates="data", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_evaluation_data_dataset_id", "dataset_id"),
        Index("idx_evaluation_data_status", "status"),
        Index("idx_evaluation_data_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<EvaluationData(id={self.id}, file_name='{self.file_name}')>"


class Annotation(Base):
    __tablename__ = "annotations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    data_id = Column(BigInteger, ForeignKey("evaluation_data.id", ondelete="CASCADE"), nullable=False, comment="评测数据ID")
    ground_truth = Column(Text, nullable=False, comment="真值标注")
    annotation_type = Column(Enum("manual", "ai", name="annotation_type"), nullable=False, comment="标注类型")
    model_name = Column(String(100), comment="模型名称(大模型标注时)")
    annotator_id = Column(BigInteger, comment="标注者ID(人工标注时)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")

    evaluation_data = relationship("EvaluationData", back_populates="annotations")

    __table_args__ = (
        Index("idx_annotations_data_id", "data_id"),
        Index("idx_annotations_type", "annotation_type"),
        Index("idx_annotations_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<Annotation(id={self.id}, data_id={self.data_id}, type='{self.annotation_type}')>"
