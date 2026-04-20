#!/usr/bin/env python3
"""
临时脚本：为指定 TOS 路径下的视频生成中文标题并重命名对象。

默认行为：
- 使用豆包 `doubao-seed-2-0-pro-260215` 理解视频内容并生成约 10 字中文标题
- 默认 dry-run，只输出映射关系，不真正重命名
- 真实执行时使用 TOS `rename_object`
- 若 `rename_object` 不支持，则自动降级为 `copy + delete`

注意：
- TOS RenameObject 需要桶已开启 rename 功能
- 仅支持对开启 RenameObject 后新上传的对象使用 rename_object
- 同一对象不支持并发重命名

示例：
  cd backend
  python scripts/rename_night_view_videos.py \
    --prefix 'AI-IPC/VideoRetrieval&IntelligentAlert/night_view/' \
    --limit 5

  python scripts/rename_night_view_videos.py \
    --prefix 'AI-IPC/VideoRetrieval&IntelligentAlert/night_view/' \
    --execute
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import tos

from app.services.ark_client import ArkClient
from app.utils import get_tos_client


DEFAULT_MODEL = "doubao-seed-2-0-pro-260215"
DEFAULT_PREFIX = "AI-IPC/VideoRetrieval&IntelligentAlert/night_view/"
VIDEO_EXTENSIONS = {"mp4", "avi", "mov", "mkv", "flv", "wmv"}
TITLE_PROMPT = """你会看到一个视频的关键帧。请理解视频内容，并为视频起一个中文标题。

要求：
1. 标题要准确概括视频内容，适合监控/安防场景
2. 标题长度控制在 6 到 12 个中文字符，约 10 字
3. 只输出标题本身，不要解释，不要标点，不要引号
4. 优先包含核心主体、行为、场景
"""


def normalize_prefix(prefix: str) -> tuple[str, str]:
    value = prefix.strip()
    if value.startswith("tos://"):
        without_scheme = value[len("tos://") :]
        bucket, _, object_prefix = without_scheme.partition("/")
        if not bucket or not object_prefix:
            raise ValueError("TOS 路径格式不正确，应为 tos://bucket/prefix/")
        return bucket, object_prefix.rstrip("/") + "/"
    tos_client = get_tos_client()
    return tos_client.bucket, value.rstrip("/") + "/"


def is_video_key(object_key: str) -> bool:
    suffix = object_key.rsplit(".", 1)[-1].lower() if "." in object_key else ""
    return suffix in VIDEO_EXTENSIONS


def sanitize_title(title: str, fallback: str) -> str:
    value = title.strip()
    value = re.sub(r"^[\"'“”‘’《》【】\[\]\(\)\s]+|[\"'“”‘’《》【】\[\]\(\)\s]+$", "", value)
    value = re.sub(r"[\\/:*?\"<>|#]+", "", value)
    value = re.sub(r"[，。；：、！!？?·`~]+", "", value)
    value = re.sub(r"\s+", "", value)
    if not value:
        value = fallback
    return value[:12]


def deduplicate_filename(
    tos_client,
    target_prefix: str,
    title: str,
    extension: str,
    occupied_keys: set[str],
) -> str:
    base_name = title
    candidate = f"{target_prefix}{base_name}.{extension}"
    index = 2
    while candidate in occupied_keys or tos_client.check_object_exists(candidate):
        candidate = f"{target_prefix}{base_name}_{index}.{extension}"
        index += 1
    occupied_keys.add(candidate)
    return candidate


def build_video_title(
    ark_client: ArkClient,
    download_url: str,
    extension: str,
    fps: float,
    model: str,
) -> str:
    content = ark_client.build_annotation_content(
        download_url,
        extension,
        annotation_prompt=TITLE_PROMPT,
        fps=fps,
    )
    result = ark_client.annotate_with_usage(content, model=model)
    return result["text"].strip()


def rename_with_fallback(tos_client, bucket: str, source_key: str, target_key: str) -> str:
    try:
        tos_client.client.rename_object(bucket=bucket, key=source_key, new_key=target_key)
        return "renamed"
    except tos.exceptions.TosServerError as exc:
        if getattr(exc, "code", "") != "CannotBeRenamed":
            raise
        tos_client.client.copy_object(
            bucket=bucket,
            key=target_key,
            src_bucket=bucket,
            src_key=source_key,
            forbid_overwrite=True,
        )
        tos_client.client.delete_object(bucket=bucket, key=source_key)
        return "copied_deleted"


def main():
    parser = argparse.ArgumentParser(description="为 TOS 路径下的视频批量生成中文标题并重命名")
    parser.add_argument("--prefix", default=DEFAULT_PREFIX, help="对象前缀，支持 tos://bucket/prefix/ 或直接传 prefix")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="用于理解视频内容的豆包模型")
    parser.add_argument("--fps", type=float, default=0.3, help="视频抽帧频率")
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 个视频，0 表示全部")
    parser.add_argument("--source-key", action="append", default=[], help="只处理指定对象 key，可重复传入")
    parser.add_argument("--execute", action="store_true", help="真实执行重命名；默认仅 dry-run")
    parser.add_argument("--enable-bucket-rename", action="store_true", help="执行前尝试开启桶 rename 功能")
    parser.add_argument("--report", default="", help="输出报告 JSON 文件路径")
    args = parser.parse_args()

    bucket, object_prefix = normalize_prefix(args.prefix)
    tos_client = get_tos_client()
    ark_client = ArkClient()
    occupied_keys: set[str] = set()

    if bucket != tos_client.bucket:
        raise RuntimeError(
            f"脚本解析出的 bucket={bucket}，但当前环境配置 TOS_BUCKET={tos_client.bucket}，请切换环境或修正参数"
        )

    if args.enable_bucket_rename:
        print("[INFO] 开启桶 rename 功能...")
        tos_client.client.put_bucket_rename(bucket=bucket, rename_enable=True)

    print(f"[INFO] 扫描前缀: tos://{bucket}/{object_prefix}")
    objects = tos_client.list_objects(object_prefix)
    video_objects = [obj for obj in objects if is_video_key(obj["key"])]
    if args.source_key:
        selected_keys = set(args.source_key)
        video_objects = [obj for obj in video_objects if obj["key"] in selected_keys]
    if args.limit > 0:
        video_objects = video_objects[: args.limit]

    print(f"[INFO] 命中视频数量: {len(video_objects)}")
    if not video_objects:
        return

    results: list[dict[str, Any]] = []
    original_prefix = object_prefix

    for index, obj in enumerate(video_objects, start=1):
        object_key = obj["key"]
        file_name = object_key.rsplit("/", 1)[-1]
        extension = file_name.rsplit(".", 1)[-1].lower()
        fallback_title = Path(file_name).stem[:12] or f"夜视视频{index}"
        download_url = tos_client.get_download_url(object_key)

        print(f"[{index}/{len(video_objects)}] 解析视频标题: {object_key}")
        try:
            raw_title = build_video_title(ark_client, download_url, extension, args.fps, args.model)
            title = sanitize_title(raw_title, fallback_title)
            new_key = deduplicate_filename(
                tos_client,
                original_prefix,
                title,
                extension,
                occupied_keys,
            )
            item = {
                "source_key": object_key,
                "raw_title": raw_title,
                "title": title,
                "target_key": new_key,
                "status": "planned",
            }

            if args.execute and new_key != object_key:
                print(f"  -> rename: {object_key} => {new_key}")
                item["status"] = rename_with_fallback(tos_client, bucket, object_key, new_key)
            elif args.execute:
                print("  -> skip: 标题与原对象名等价，无需重命名")
                item["status"] = "skipped"
            else:
                print(f"  -> dry-run: {object_key} => {new_key}")

            results.append(item)
        except tos.exceptions.TosServerError as exc:
            results.append(
                {
                    "source_key": object_key,
                    "status": "tos_server_error",
                    "error": f"{exc.message} (request_id={exc.request_id}, code={exc.code})",
                }
            )
            print(f"  !! TOS 服务端错误: {exc.message} request_id={exc.request_id}")
        except tos.exceptions.TosClientError as exc:
            results.append(
                {
                    "source_key": object_key,
                    "status": "tos_client_error",
                    "error": f"{exc.message}, cause={exc.cause}",
                }
            )
            print(f"  !! TOS 客户端错误: {exc.message}")
        except Exception as exc:
            results.append(
                {
                    "source_key": object_key,
                    "status": "failed",
                    "error": str(exc),
                }
            )
            print(f"  !! 处理失败: {exc}")

    report_path = args.report or f"rename_report_{Path(object_prefix.rstrip('/')).name}.json"
    report_file = Path(report_path)
    report_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[INFO] 报告已写入: {report_file}")
    print(
        "[INFO] 统计:",
        json.dumps(
            {
                "planned": sum(1 for item in results if item["status"] == "planned"),
                "renamed": sum(1 for item in results if item["status"] == "renamed"),
                "copied_deleted": sum(1 for item in results if item["status"] == "copied_deleted"),
                "skipped": sum(1 for item in results if item["status"] == "skipped"),
                "failed": sum(
                    1
                    for item in results
                    if item["status"] in {"failed", "tos_client_error", "tos_server_error"}
                ),
            },
            ensure_ascii=False,
        ),
    )


if __name__ == "__main__":
    main()
