from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional

from app.core.database import get_db
from app.core.config import get_settings
from app.models import Dataset, EvaluationData, Annotation
from app.schemas import (
    EvaluationDataCreate,
    EvaluationDataResponse,
    EvaluationDataListResponse,
    PresignedUrlRequest,
    PresignedUrlResponse,
    TOSImportRequest,
    TOSListResponse,
    TOSObjectInfo,
    TOSFolderListResponse,
    TOSFolderInfo,
    TOSFileListResponse,
    TOSFileInfo,
    TOSImportRequestV2,
    DataStatus,
    AnnotationResponse,
    AnnotationType,
)
from app.utils import get_tos_client

router = APIRouter()

VIDEO_EXTENSIONS = {"mp4", "avi", "mov", "mkv", "flv", "wmv"}
IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "bmp", "webp"}
ALL_EXTENSIONS = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS
MAX_VIDEO_SIZE = 500 * 1024 * 1024
MAX_IMAGE_SIZE = 20 * 1024 * 1024


def is_video_file(ext: str) -> bool:
    return ext in VIDEO_EXTENSIONS


def is_image_file(ext: str) -> bool:
    return ext in IMAGE_EXTENSIONS


@router.post(
    "/{dataset_id}/upload-url",
    response_model=PresignedUrlResponse,
    summary="获取上传预签名URL"
)
def get_upload_url(dataset_id: int, data: PresignedUrlRequest, db: Session = Depends(get_db)):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="评测集不存在")

    ext = data.file_name.rsplit(".", 1)[-1].lower() if "." in data.file_name else ""

    if dataset.type == "video":
        if ext not in VIDEO_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"不支持的视频格式，支持: {', '.join(VIDEO_EXTENSIONS)}")
        if data.file_size > MAX_VIDEO_SIZE:
            raise HTTPException(status_code=400, detail="视频文件大小不能超过500MB")
        file_category = "video"
    elif dataset.type == "image":
        if ext not in IMAGE_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"不支持的图片格式，支持: {', '.join(IMAGE_EXTENSIONS)}")
        if data.file_size > MAX_IMAGE_SIZE:
            raise HTTPException(status_code=400, detail="图片文件大小不能超过20MB")
        file_category = "image"
    else:
        if ext not in ALL_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"不支持的文件格式，支持: {', '.join(ALL_EXTENSIONS)}")
        if is_video_file(ext):
            if data.file_size > MAX_VIDEO_SIZE:
                raise HTTPException(status_code=400, detail="视频文件大小不能超过500MB")
            file_category = "video"
        else:
            if data.file_size > MAX_IMAGE_SIZE:
                raise HTTPException(status_code=400, detail="图片文件大小不能超过20MB")
            file_category = "image"

    tos_client = get_tos_client()
    object_key = tos_client.generate_object_key(dataset_id, file_category, ext)
    upload_url = tos_client.get_presigned_url(object_key, method="PUT")

    return PresignedUrlResponse(
        upload_url=upload_url,
        object_key=object_key,
        expires_in=3600
    )


@router.post(
    "/{dataset_id}/data",
    response_model=EvaluationDataResponse,
    summary="确认上传完成"
)
def confirm_upload(dataset_id: int, data: EvaluationDataCreate, db: Session = Depends(get_db)):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="评测集不存在")

    tos_client = get_tos_client()
    if not tos_client.check_object_exists(data.tos_key):
        raise HTTPException(status_code=400, detail="文件未上传到TOS")

    eval_data = EvaluationData(
        dataset_id=dataset_id,
        file_name=data.file_name,
        file_type=data.file_type,
        file_size=data.file_size,
        tos_key=data.tos_key,
        tos_bucket=data.tos_bucket,
        status=DataStatus.pending.value,
    )
    db.add(eval_data)
    db.commit()
    db.refresh(eval_data)

    return _to_data_response(eval_data)


@router.post("/{dataset_id}/tos-list", response_model=TOSListResponse, summary="列出TOS对象")
def list_tos_objects(dataset_id: int, data: TOSImportRequest, db: Session = Depends(get_db)):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="评测集不存在")

    tos_client = get_tos_client()
    objects = tos_client.list_objects(data.prefix)

    return TOSListResponse(
        objects=[
            TOSObjectInfo(
                key=obj["key"],
                size=obj["size"],
                last_modified=obj["last_modified"]
            )
            for obj in objects
        ]
    )


@router.get("/{dataset_id}/tos-folders", response_model=TOSFolderListResponse, summary="列出TOS文件夹")
def list_tos_folders(
    dataset_id: int,
    prefix: str = Query("", description="当前路径前缀"),
    db: Session = Depends(get_db)
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="评测集不存在")

    tos_client = get_tos_client()
    folders = tos_client.list_folders(prefix)

    return TOSFolderListResponse(
        folders=[
            TOSFolderInfo(
                name=f["name"],
                prefix=f["prefix"],
                full_path=f["full_path"]
            )
            for f in folders
        ],
        current_prefix=prefix
    )


@router.get("/{dataset_id}/tos-files", response_model=TOSFileListResponse, summary="列出TOS文件夹中的文件")
def list_tos_files(
    dataset_id: int,
    prefix: str = Query(..., description="文件夹前缀"),
    db: Session = Depends(get_db)
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="评测集不存在")

    tos_client = get_tos_client()
    files = tos_client.list_files_in_folder(prefix)

    valid_files = []
    for f in files:
        ext = f["extension"]
        if dataset.type == "video" and ext in VIDEO_EXTENSIONS:
            valid_files.append(f)
        elif dataset.type == "image" and ext in IMAGE_EXTENSIONS:
            valid_files.append(f)
        elif dataset.type == "mixed" and ext in ALL_EXTENSIONS:
            valid_files.append(f)

    return TOSFileListResponse(
        files=[
            TOSFileInfo(
                key=f["key"],
                name=f["name"],
                size=f["size"],
                extension=f["extension"],
                last_modified=f["last_modified"]
            )
            for f in valid_files
        ],
        folder_prefix=prefix
    )


@router.post(
    "/{dataset_id}/import-v2",
    response_model=list[EvaluationDataResponse],
    summary="从TOS导入数据"
)
def import_from_tos_v2(dataset_id: int, data: TOSImportRequestV2, db: Session = Depends(get_db)):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="评测集不存在")

    tos_client = get_tos_client()
    settings = get_settings()
    imported_data = []

    for key in data.keys:
        if not tos_client.check_object_exists(key):
            continue

        file_name = key.rsplit("/", 1)[-1]
        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

        if dataset.type == "video" and ext not in VIDEO_EXTENSIONS:
            continue
        elif dataset.type == "image" and ext not in IMAGE_EXTENSIONS:
            continue
        elif dataset.type == "mixed" and ext not in ALL_EXTENSIONS:
            continue

        existing = db.query(EvaluationData).filter(
            EvaluationData.dataset_id == dataset_id,
            EvaluationData.tos_key == key
        ).first()
        if existing:
            continue

        eval_data = EvaluationData(
            dataset_id=dataset_id,
            file_name=file_name,
            file_type=ext,
            file_size=0,
            tos_key=key,
            tos_bucket=settings.tos_bucket,
            status=DataStatus.pending.value,
        )
        db.add(eval_data)
        imported_data.append(eval_data)

    db.commit()
    return [_to_data_response(d) for d in imported_data]


@router.post(
    "/{dataset_id}/import",
    response_model=list[EvaluationDataResponse],
    summary="从TOS导入数据"
)
def import_from_tos(dataset_id: int, keys: list[str], db: Session = Depends(get_db)):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="评测集不存在")

    tos_client = get_tos_client()
    settings = get_settings()
    imported_data = []

    for key in keys:
        if not tos_client.check_object_exists(key):
            continue

        file_name = key.rsplit("/", 1)[-1]
        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

        eval_data = EvaluationData(
            dataset_id=dataset_id,
            file_name=file_name,
            file_type=ext,
            file_size=0,
            tos_key=key,
            tos_bucket=settings.tos_bucket,
            status=DataStatus.pending.value,
        )
        db.add(eval_data)
        imported_data.append(eval_data)

    db.commit()
    return [_to_data_response(d) for d in imported_data]


@router.get(
    "/{dataset_id}/data",
    response_model=EvaluationDataListResponse,
    summary="获取评测数据列表"
)
def list_evaluation_data(
    dataset_id: int,
    status: Optional[DataStatus] = Query(None, description="标注状态"),
    keyword: Optional[str] = Query(None, description="关键词（文件名）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db)
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="评测集不存在")

    query = db.query(EvaluationData).filter(EvaluationData.dataset_id == dataset_id)

    if status:
        query = query.filter(EvaluationData.status == status.value)
    if keyword:
        query = query.outerjoin(Annotation, Annotation.data_id == EvaluationData.id).filter(
            or_(
                EvaluationData.file_name.contains(keyword),
                Annotation.ground_truth.contains(keyword),
            )
        ).distinct()

    total = query.count()
    data_list = query.order_by(EvaluationData.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return EvaluationDataListResponse(
        items=[_to_data_response(d) for d in data_list],
        total=total
    )


@router.delete("/{dataset_id}/data/{data_id}", summary="删除评测数据")
def delete_evaluation_data(dataset_id: int, data_id: int, db: Session = Depends(get_db)):
    eval_data = db.query(EvaluationData).filter(
        EvaluationData.id == data_id,
        EvaluationData.dataset_id == dataset_id
    ).first()
    if not eval_data:
        raise HTTPException(status_code=404, detail="评测数据不存在")

    tos_client = get_tos_client()
    tos_client.delete_object(eval_data.tos_key)

    db.delete(eval_data)
    db.commit()
    return {"message": "删除成功"}


def _to_data_response(eval_data: EvaluationData) -> EvaluationDataResponse:
    tos_client = get_tos_client()
    download_url = tos_client.get_download_url(eval_data.tos_key)

    annotation = eval_data.annotations[0] if eval_data.annotations else None
    annotation_response = None
    if annotation:
        annotation_response = AnnotationResponse(
            id=annotation.id,
            data_id=annotation.data_id,
            ground_truth=annotation.ground_truth,
            annotation_type=AnnotationType(annotation.annotation_type),
            model_name=annotation.model_name,
            annotator_id=annotation.annotator_id,
            created_at=annotation.created_at,
            updated_at=annotation.updated_at,
        )

    return EvaluationDataResponse(
        id=eval_data.id,
        dataset_id=eval_data.dataset_id,
        file_name=eval_data.file_name,
        file_type=eval_data.file_type,
        file_size=eval_data.file_size,
        tos_key=eval_data.tos_key,
        tos_bucket=eval_data.tos_bucket,
        status=DataStatus(eval_data.status),
        created_at=eval_data.created_at,
        download_url=download_url,
        annotation=annotation_response,
        updated_at=annotation.updated_at if annotation else None,
    )
