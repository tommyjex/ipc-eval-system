from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class DatasetType(str, Enum):
    video = "video"
    image = "image"
    mixed = "mixed"


class DatasetScene(str, Enum):
    video_retrieval = "video_retrieval"
    smart_alert = "smart_alert"


class DatasetStatus(str, Enum):
    draft = "draft"
    ready = "ready"
    archived = "archived"


class DatasetAnnotationStatus(str, Enum):
    pending = "pending"
    partial = "partial"
    annotated = "annotated"


class DataStatus(str, Enum):
    pending = "pending"
    annotated = "annotated"
    failed = "failed"


class AnnotationType(str, Enum):
    manual = "manual"
    ai = "ai"


class DatasetBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="评测集名称")
    description: Optional[str] = Field(None, description="评测集描述")
    type: DatasetType = Field(..., description="评测集类型")
    scene: Optional[DatasetScene] = Field(None, description="业务场景")
    annotation_prompt: Optional[str] = Field(None, description="标注提示词")
    custom_tags: Optional[list[str]] = Field(None, description="自定义标签列表")


class DatasetCreate(DatasetBase):
    pass


class DatasetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="评测集名称")
    description: Optional[str] = Field(None, description="评测集描述")
    type: Optional[DatasetType] = Field(None, description="评测集类型")
    status: Optional[DatasetStatus] = Field(None, description="评测集状态")
    scene: Optional[DatasetScene] = Field(None, description="业务场景")
    annotation_prompt: Optional[str] = Field(None, description="标注提示词")
    custom_tags: Optional[list[str]] = Field(None, description="自定义标签列表")


class DatasetResponse(DatasetBase):
    id: int
    status: DatasetStatus
    annotation_status: DatasetAnnotationStatus
    data_count: int = Field(default=0, description="数据数量")
    annotated_count: int = Field(default=0, description="已标注数量")
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DatasetListResponse(BaseModel):
    items: list[DatasetResponse]
    total: int


class AnnotationBase(BaseModel):
    ground_truth: str = Field(..., min_length=1, description="真值标注")


class AnnotationCreate(AnnotationBase):
    annotation_type: AnnotationType = Field(..., description="标注类型")
    model_name: Optional[str] = Field(None, max_length=100, description="模型名称")
    annotator_id: Optional[int] = Field(None, description="标注者ID")


class AnnotationUpdate(BaseModel):
    ground_truth: Optional[str] = Field(None, min_length=1, description="真值标注")


class AnnotationResponse(AnnotationBase):
    id: int
    data_id: int
    annotation_type: AnnotationType
    model_name: Optional[str] = None
    annotator_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EvaluationDataBase(BaseModel):
    file_name: str = Field(..., max_length=255, description="文件名")
    file_type: str = Field(..., max_length=50, description="文件类型")
    file_size: int = Field(..., ge=0, description="文件大小(字节)")


class EvaluationDataCreate(EvaluationDataBase):
    tos_key: str = Field(..., max_length=500, description="TOS对象键")
    tos_bucket: str = Field(..., max_length=100, description="TOS存储桶")


class EvaluationDataResponse(EvaluationDataBase):
    id: int
    dataset_id: int
    tos_key: str
    tos_bucket: str
    status: DataStatus
    created_at: datetime
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    download_url: Optional[str] = Field(None, description="下载链接")
    annotation: Optional[AnnotationResponse] = Field(None, description="标注信息")

    class Config:
        from_attributes = True


class EvaluationDataListResponse(BaseModel):
    items: list[EvaluationDataResponse]
    total: int


class PresignedUrlRequest(BaseModel):
    file_name: str = Field(..., description="文件名")
    file_type: str = Field(..., description="文件类型")
    file_size: int = Field(..., ge=0, description="文件大小(字节)")


class PresignedUrlResponse(BaseModel):
    upload_url: str = Field(..., description="上传预签名URL")
    object_key: str = Field(..., description="TOS对象键")
    expires_in: int = Field(default=3600, description="URL有效期(秒)")


class TOSImportRequest(BaseModel):
    prefix: str = Field(..., description="TOS对象前缀")


class TOSObjectInfo(BaseModel):
    key: str
    size: int
    last_modified: datetime


class TOSListResponse(BaseModel):
    objects: list[TOSObjectInfo]


class TOSFolderInfo(BaseModel):
    name: str
    prefix: str
    full_path: str


class TOSFolderListResponse(BaseModel):
    folders: list[TOSFolderInfo]
    current_prefix: str


class TOSFileInfo(BaseModel):
    key: str
    name: str
    size: int
    extension: str
    last_modified: datetime
    selected: bool = False


class TOSFileListResponse(BaseModel):
    files: list[TOSFileInfo]
    folder_prefix: str


class TOSImportRequestV2(BaseModel):
    keys: list[str] = Field(..., min_length=1, description="要导入的TOS对象键列表")


class BatchAnnotationRequest(BaseModel):
    data_ids: list[int] = Field(..., min_length=1, description="数据ID列表")
    ground_truth: str = Field(..., min_length=1, description="真值标注")


class AIAnnotationRequest(BaseModel):
    data_ids: list[int] = Field(..., min_length=1, description="数据ID列表")
    model: Optional[str] = Field(None, description="模型名称")
    prompt: Optional[str] = Field(None, description="自定义提示词")


class AIAnnotationStatus(BaseModel):
    task_id: str
    status: str
    total: int
    completed: int
    failed: int
