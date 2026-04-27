from sqlalchemy import Boolean, Column, BigInteger, String, Text, Enum, DateTime, ForeignKey, Index, func, Float
from sqlalchemy.orm import relationship
from app.models.base import Base


class EvaluationTask(Base):
    __tablename__ = "evaluation_tasks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    dataset_id = Column(BigInteger, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, comment="评测集ID")
    username = Column(String(64), nullable=True, comment="创建用户名")
    name = Column(String(255), nullable=False, comment="任务名称")
    target_model = Column(String(100), nullable=False, comment="目标模型")
    model_provider = Column(String(50), comment="模型供应商")
    scoring_criteria = Column(Text, comment="评分标准")
    prompt = Column(Text, comment="任务级提示词")
    fps = Column(Float, nullable=False, default=0.3, server_default="0.3", comment="视频理解帧率")
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
    prompt_optimizations = relationship(
        "TaskPromptOptimization",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskPromptOptimization.version_number.desc()",
        foreign_keys="TaskPromptOptimization.task_id",
    )

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
    status = Column(String(20), nullable=False, default="pending", comment="执行状态")
    model_output = Column(Text, comment="模型输出")
    input_tokens = Column(BigInteger, comment="输入 tokens")
    output_tokens = Column(BigInteger, comment="输出 tokens")
    score = Column(BigInteger, comment="评分")
    recall = Column(Float, comment="召回率")
    precision = Column("precision", Float, quote=True, comment="精确率")
    score_reason = Column(Text, comment="评分原因")
    tp_count = Column(BigInteger, comment="命中数量")
    fp_count = Column(BigInteger, comment="误报数量")
    fn_count = Column(BigInteger, comment="漏检数量")
    ground_truth_unit_count = Column(BigInteger, comment="标注单元数")
    predicted_unit_count = Column(BigInteger, comment="预测单元数")
    is_scorable = Column(Boolean, nullable=False, default=True, server_default="1", comment="是否可参与评分")
    is_empty_sample = Column(Boolean, nullable=False, default=False, server_default="0", comment="是否为空样本")
    empty_sample_passed = Column(Boolean, nullable=False, default=False, server_default="0", comment="空样本是否判断正确")
    metric_version = Column(String(32), comment="评分口径版本")
    scoring_status = Column(String(20), nullable=False, default="not_scored", comment="评分状态")
    scoring_error_message = Column(Text, comment="评分失败原因")
    scoring_model = Column(String(100), comment="评分模型")
    scoring_started_at = Column(DateTime(timezone=True), comment="评分开始时间")
    scoring_completed_at = Column(DateTime(timezone=True), comment="评分完成时间")
    error_message = Column(Text, comment="失败原因")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")
    completed_at = Column(DateTime(timezone=True), comment="完成时间")

    task = relationship("EvaluationTask", back_populates="results")
    data = relationship("EvaluationData", back_populates="results")

    __table_args__ = (
        Index("idx_task_results_task_id", "task_id"),
        Index("idx_task_results_data_id", "data_id"),
        Index("idx_task_results_status", "status"),
        Index("idx_task_results_scoring_status", "scoring_status"),
        Index("idx_task_results_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<TaskResult(id={self.id}, task_id={self.task_id})>"


class TaskPromptOptimization(Base):
    __tablename__ = "task_prompt_optimizations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, ForeignKey("evaluation_tasks.id", ondelete="CASCADE"), nullable=False, comment="原始任务ID")
    version_number = Column(BigInteger, nullable=False, default=1, server_default="1", comment="版本号")
    compare_task_id = Column(BigInteger, ForeignKey("evaluation_tasks.id", ondelete="SET NULL"), nullable=True, comment="对比任务ID")
    optimization_model = Column(String(100), nullable=False, comment="优化模型")
    sample_count = Column(BigInteger, nullable=False, default=0, server_default="0", comment="纳入分析的样本数")
    source_prompt = Column(Text, comment="原始提示词")
    analysis_summary = Column(Text, comment="问题分析摘要")
    issues_json = Column(Text, comment="问题点 JSON")
    optimization_strategies_json = Column(Text, comment="优化策略 JSON")
    optimized_prompt = Column(Text, nullable=False, comment="模型生成的优化后提示词")
    edited_prompt = Column(Text, comment="人工微调后的提示词")
    revision_summary_json = Column(Text, comment="提示词修改说明 JSON")
    analysis_input_tokens = Column(BigInteger, comment="第一阶段输入 tokens")
    analysis_output_tokens = Column(BigInteger, comment="第一阶段输出 tokens")
    prompt_input_tokens = Column(BigInteger, comment="第二阶段输入 tokens")
    prompt_output_tokens = Column(BigInteger, comment="第二阶段输出 tokens")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")

    task = relationship(
        "EvaluationTask",
        back_populates="prompt_optimizations",
        foreign_keys=[task_id],
    )
    compare_task = relationship(
        "EvaluationTask",
        foreign_keys=[compare_task_id],
    )

    __table_args__ = (
        Index("idx_task_prompt_optimizations_task_id", "task_id"),
        Index("idx_task_prompt_optimizations_task_version", "task_id", "version_number", unique=True),
        Index("idx_task_prompt_optimizations_compare_task_id", "compare_task_id"),
    )

    def __repr__(self):
        return f"<TaskPromptOptimization(id={self.id}, task_id={self.task_id}, version={self.version_number}, compare_task_id={self.compare_task_id})>"
