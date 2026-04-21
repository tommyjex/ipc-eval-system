import uuid
from typing import Optional
from datetime import timedelta
import tos
from app.core.config import get_settings


class TOSClient:
    def __init__(self):
        settings = get_settings()
        self.client = tos.TosClientV2(
            ak=settings.tos_access_key,
            sk=settings.tos_secret_key,
            endpoint=settings.tos_endpoint,
            region=settings.tos_region,
        )
        self.public_client = tos.TosClientV2(
            ak=settings.tos_access_key,
            sk=settings.tos_secret_key,
            endpoint=settings.tos_public_endpoint,
            region=settings.tos_region,
        )
        self.bucket = settings.tos_bucket
        self.import_prefix = "AI-IPC"

    def generate_object_key(self, dataset_id: int, data_type: str, extension: str) -> str:
        return f"datasets/{dataset_id}/{data_type}/{uuid.uuid4().hex}.{extension}"

    def get_presigned_url(
        self,
        object_key: str,
        expires: int = 3600,
        method: str = "PUT",
        public_endpoint: bool = False,
    ) -> str:
        from tos import HttpMethodType
        client = self.public_client if public_endpoint else self.client

        if method.upper() == "PUT":
            result = client.pre_signed_url(
                http_method=HttpMethodType.Http_Method_Put,
                bucket=self.bucket,
                key=object_key,
                expires=expires
            )
        else:
            result = client.pre_signed_url(
                http_method=HttpMethodType.Http_Method_Get,
                bucket=self.bucket,
                key=object_key,
                expires=expires
            )
        return result.signed_url

    def get_download_url(self, object_key: str, expires: int = 86400, public_endpoint: bool = False) -> str:
        return self.get_presigned_url(object_key, expires, method="GET", public_endpoint=public_endpoint)

    def check_object_exists(self, object_key: str) -> bool:
        try:
            self.client.head_object(self.bucket, object_key)
            return True
        except tos.exceptions.TosClientError:
            return False
        except tos.exceptions.TosServerError as e:
            if e.status_code == 404:
                return False
            raise

    def delete_object(self, object_key: str) -> bool:
        try:
            self.client.delete_object(self.bucket, object_key)
            return True
        except Exception:
            return False

    def list_objects(self, prefix: str) -> list[dict]:
        result = self.client.list_objects_type2(
            bucket=self.bucket,
            prefix=prefix,
            max_keys=1000
        )
        objects = []
        if result.contents:
            for obj in result.contents:
                objects.append({
                    "key": obj.key,
                    "size": obj.size,
                    "last_modified": obj.last_modified,
                })
        return objects

    def list_folders(self, prefix: str = "") -> list[dict]:
        if prefix and not prefix.endswith("/"):
            prefix = prefix + "/"
        
        if prefix.startswith("AI-IPC/"):
            full_prefix = prefix
        else:
            full_prefix = f"{self.import_prefix}/{prefix}" if prefix else f"{self.import_prefix}/"
        
        result = self.client.list_objects_type2(
            bucket=self.bucket,
            prefix=full_prefix,
            delimiter="/",
            max_keys=1000
        )
        
        folders = []
        if result.common_prefixes:
            for cp in result.common_prefixes:
                folder_name = cp.prefix.rstrip("/").rsplit("/", 1)[-1]
                folders.append({
                    "name": folder_name,
                    "prefix": cp.prefix,
                    "full_path": cp.prefix,
                })
        
        return folders

    def list_files_in_folder(self, prefix: str) -> list[dict]:
        if not prefix.endswith("/"):
            prefix = prefix + "/"
        
        result = self.client.list_objects_type2(
            bucket=self.bucket,
            prefix=prefix,
            max_keys=1000
        )
        
        files = []
        if result.contents:
            for obj in result.contents:
                if obj.key != prefix and not obj.key.endswith("/"):
                    file_name = obj.key.rsplit("/", 1)[-1]
                    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
                    files.append({
                        "key": obj.key,
                        "name": file_name,
                        "size": obj.size,
                        "extension": ext,
                        "last_modified": obj.last_modified,
                    })
        
        return files


_tos_client: Optional[TOSClient] = None


def get_tos_client() -> TOSClient:
    global _tos_client
    if _tos_client is None:
        _tos_client = TOSClient()
    return _tos_client
