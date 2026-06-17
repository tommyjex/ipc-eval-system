from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Protocol

from vikingdb.auth import IAM  # type: ignore
from vikingdb.vector import VikingVector  # type: ignore

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_PATH = BACKEND_ROOT / "outputs" / "vector_ingestion_dataset_7_en.json"
DEFAULT_BATCH_SIZE = 100
DEFAULT_PRIMARY_KEY_FIELD = "id"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


class UpsertPreparationError(RuntimeError):
    """向量库写入数据准备失败。"""


class CollectionClient(Protocol):
    def upsert(self, request: Any) -> Any:
        """写入一批数据到 VikingDB Collection。"""


@dataclass(frozen=True)
class UpsertSummary:
    total_count: int
    batch_count: int
    dry_run: bool


def load_source_payload(input_path: Path) -> list[dict[str, Any]]:
    try:
        with input_path.open("r", encoding="utf-8") as file_obj:
            payload = json.load(file_obj)
    except Exception as exc:
        raise UpsertPreparationError(
            f"读取输入 JSON 失败: path={input_path}, reason={exc}"
        ) from exc

    if not isinstance(payload, list):
        raise UpsertPreparationError(f"输入 JSON 顶层结构必须为数组: path={input_path}")
    if not all(isinstance(item, dict) for item in payload):
        raise UpsertPreparationError("输入 JSON 每条记录必须为对象")
    return payload


def _read_english_annotation(record: dict[str, Any]) -> dict[str, Any]:
    annotation = record.get("english_annotation")
    if not isinstance(annotation, dict):
        data_id = record.get("data_id")
        raise UpsertPreparationError(f"english_annotation 缺失或不是对象: data_id={data_id}")
    return annotation


def _stringify_event(event: Any) -> str:
    if isinstance(event, list):
        return ";".join(str(item) for item in event)
    if event is None:
        return ""
    return str(event)


def build_vikingdb_data_item(
    record: dict[str, Any],
    *,
    primary_key_field: str = DEFAULT_PRIMARY_KEY_FIELD,
) -> dict[str, Any]:
    annotation = _read_english_annotation(record)
    data_id = record.get("data_id")
    file_name = record.get("file_name")

    if data_id is None:
        raise UpsertPreparationError("data_id 缺失，无法生成主键")
    if not file_name:
        raise UpsertPreparationError(f"file_name 缺失: data_id={data_id}")

    description = annotation.get("description") or ""
    title = annotation.get("title") or ""
    event = annotation.get("event") or []
    event_text = _stringify_event(event)

    return {
        primary_key_field: str(data_id),
        "description": str(description),
        "title": str(title),
        "event": event_text,
        "des": ";".join([str(description), str(title), event_text]),
        "name": str(file_name),
    }


def build_vikingdb_data(
    payload: list[dict[str, Any]],
    *,
    primary_key_field: str = DEFAULT_PRIMARY_KEY_FIELD,
) -> list[dict[str, Any]]:
    return [
        build_vikingdb_data_item(record, primary_key_field=primary_key_field)
        for record in payload
    ]


def chunked(items: list[dict[str, Any]], batch_size: int) -> Iterable[list[dict[str, Any]]]:
    if batch_size < 1 or batch_size > DEFAULT_BATCH_SIZE:
        raise UpsertPreparationError(f"batch_size 必须在 1 到 {DEFAULT_BATCH_SIZE} 之间")
    for index in range(0, len(items), batch_size):
        yield items[index : index + batch_size]


def create_vikingdb_collection_client() -> Any:
    from app.core.config import get_settings

    settings = get_settings()
    missing = [
        name
        for name in (
            "vikingdb_host",
            "vikingdb_region",
            "vikingdb_collection",
            "vikingdb_access_key",
            "vikingdb_secret_key",
        )
        if not getattr(settings, name, None)
    ]
    if missing:
        raise UpsertPreparationError(f"VikingDB 配置缺失: {', '.join(missing)}")

    client = VikingVector(
        host=settings.vikingdb_host,
        region=settings.vikingdb_region,
        auth=IAM(ak=settings.vikingdb_access_key, sk=settings.vikingdb_secret_key),
        scheme="https",
    )
    return client.collection(collection_name=settings.vikingdb_collection)


def upsert_data_batches(
    data: list[dict[str, Any]],
    collection_client: CollectionClient,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    async_write: bool = False,
) -> int:
    try:
        from vikingdb.vector.models.collection import UpsertDataRequest  # type: ignore
    except ImportError as exc:
        raise UpsertPreparationError(
            "未安装 vikingdb-python-sdk，请执行 python3 -m pip install -U vikingdb-python-sdk"
        ) from exc

    batch_count = 0
    for batch in chunked(data, batch_size):
        request = UpsertDataRequest(data=batch, async_write=async_write)
        response = collection_client.upsert(request)
        code = getattr(response, "code", None)
        if code and code != "Success":
            message = getattr(response, "message", "")
            raise UpsertPreparationError(f"VikingDB upsert 失败: code={code}, message={message}")
        batch_count += 1
        print(f"写入进度: batch={batch_count}, batch_size={len(batch)}")
    return batch_count


def prepare_and_upsert(
    *,
    input_path: Path,
    dry_run: bool,
    batch_size: int,
    async_write: bool,
    primary_key_field: str,
) -> UpsertSummary:
    payload = load_source_payload(input_path)
    data = build_vikingdb_data(payload, primary_key_field=primary_key_field)
    batch_count = len(list(chunked(data, batch_size)))

    if dry_run:
        preview = data[0] if data else {}
        print(json.dumps({"count": len(data), "first_item": preview}, ensure_ascii=False, indent=2))
        return UpsertSummary(total_count=len(data), batch_count=batch_count, dry_run=True)

    collection_client = create_vikingdb_collection_client()
    actual_batch_count = upsert_data_batches(
        data,
        collection_client,
        batch_size=batch_size,
        async_write=async_write,
    )
    return UpsertSummary(total_count=len(data), batch_count=actual_batch_count, dry_run=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="将翻译后的标注数据写入 VikingDB Collection。")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="输入 JSON 文件路径。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只构造并预览数据，不写入 VikingDB。",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"每批写入条数，最大 {DEFAULT_BATCH_SIZE}。",
    )
    parser.add_argument("--async-write", action="store_true", help="启用 VikingDB async_write。")
    parser.add_argument(
        "--primary-key-field",
        default=DEFAULT_PRIMARY_KEY_FIELD,
        help=f"Collection 主键字段名，默认 {DEFAULT_PRIMARY_KEY_FIELD}。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = prepare_and_upsert(
            input_path=args.input,
            dry_run=args.dry_run,
            batch_size=args.batch_size,
            async_write=args.async_write,
            primary_key_field=args.primary_key_field,
        )
    except UpsertPreparationError as exc:
        print(f"失败: {exc}")
        return 1

    print(f"总记录数: {summary.total_count}")
    print(f"批次数: {summary.batch_count}")
    print(f"执行模式: {'dry-run' if summary.dry_run else 'upsert'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
