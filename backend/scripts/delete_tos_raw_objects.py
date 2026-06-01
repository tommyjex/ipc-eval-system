#!/usr/bin/env python3
"""
Delete TOS objects whose file name contains a target substring under a prefix.

Default behavior is dry-run. Use --execute to actually delete matched objects.

Examples:
  cd backend
  python scripts/delete_tos_raw_objects.py

  python scripts/delete_tos_raw_objects.py \
    --prefix 'tos://xujianhua-utils/AI-IPC/VideoRetrieval&IntelligentAlert/pet/' \
    --execute
"""

from __future__ import annotations

import argparse
from pathlib import PurePosixPath
import sys
from pathlib import Path

import tos

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.utils import get_tos_client


DEFAULT_PREFIX = "tos://xujianhua-utils/AI-IPC/VideoRetrieval&IntelligentAlert/pet/"
DEFAULT_SUBSTRING = "_raw"


def normalize_prefix(prefix: str) -> tuple[str, str]:
    value = prefix.strip()
    if value.startswith("tos://"):
        without_scheme = value[len("tos://") :]
        bucket, _, object_prefix = without_scheme.partition("/")
        if not bucket or not object_prefix:
            raise ValueError("Invalid TOS path, expected tos://bucket/prefix/")
        return bucket, object_prefix.rstrip("/") + "/"

    tos_client = get_tos_client()
    return tos_client.bucket, value.rstrip("/") + "/"


def matches_target(object_key: str, needle: str) -> bool:
    file_name = PurePosixPath(object_key).name
    return needle in file_name


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delete TOS objects whose file name contains a substring under a prefix"
    )
    parser.add_argument(
        "--prefix",
        default=DEFAULT_PREFIX,
        help="Object prefix, supports tos://bucket/prefix/ or plain prefix",
    )
    parser.add_argument(
        "--contains",
        default=DEFAULT_SUBSTRING,
        help="Substring to match in object file name",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Only process the first N matched objects, 0 means all",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete matched objects; default is dry-run",
    )
    args = parser.parse_args()

    bucket, object_prefix = normalize_prefix(args.prefix)
    tos_client = get_tos_client()

    if bucket != tos_client.bucket:
        raise RuntimeError(
            f"Parsed bucket={bucket}, but current TOS_BUCKET={tos_client.bucket}. "
            "Please switch environment or correct the prefix."
        )

    print(f"[INFO] scanning: tos://{bucket}/{object_prefix}")
    objects = tos_client.list_objects(object_prefix)
    matched_keys = [obj["key"] for obj in objects if matches_target(obj["key"], args.contains)]

    if args.limit > 0:
        matched_keys = matched_keys[: args.limit]

    print(f"[INFO] matched count: {len(matched_keys)}")
    if not matched_keys:
        return

    deleted_count = 0
    failed_count = 0

    for index, object_key in enumerate(matched_keys, start=1):
        print(f"[{index}/{len(matched_keys)}] {object_key}")
        if not args.execute:
            print("  -> dry-run")
            continue

        try:
            tos_client.client.delete_object(bucket=bucket, key=object_key)
            deleted_count += 1
            print("  -> deleted")
        except tos.exceptions.TosServerError as exc:
            failed_count += 1
            print(
                "  !! tos server error:"
                f" message={exc.message} code={exc.code} request_id={exc.request_id}"
            )
        except tos.exceptions.TosClientError as exc:
            failed_count += 1
            print(f"  !! tos client error: message={exc.message}")
        except Exception as exc:
            failed_count += 1
            print(f"  !! failed: {exc}")

    print(
        "[INFO] summary:",
        {
            "matched": len(matched_keys),
            "deleted": deleted_count,
            "failed": failed_count,
            "dry_run": not args.execute,
        },
    )


if __name__ == "__main__":
    main()
