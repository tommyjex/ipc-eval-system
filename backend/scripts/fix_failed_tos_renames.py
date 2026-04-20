#!/usr/bin/env python3

from app.utils import get_tos_client


def main():
    bucket = "xujianhua-utils"
    tos_client = get_tos_client()

    pairs = [
        (
            "AI-IPC/VideoRetrieval&IntelligentAlert/night_view/0b1dc34875c8c828a9bfb896289f6c31.mp4",
            "AI-IPC/VideoRetrieval&IntelligentAlert/night_view/夜间偷狗贼潜入农家院.mp4",
        ),
        (
            "AI-IPC/VideoRetrieval&IntelligentAlert/night_view/0e4bcebbd93b8b8ff49d333854c42ce9.mp4",
            "AI-IPC/VideoRetrieval&IntelligentAlert/night_view/夜间监控拍摄到动物跑过路.mp4",
        ),
        (
            "AI-IPC/VideoRetrieval&IntelligentAlert/night_view/17b12d96d7825771736d79b9ca06908e.mp4",
            "AI-IPC/VideoRetrieval&IntelligentAlert/night_view/凌晨两人驾乘电动车盗窃车.mp4",
        ),
    ]

    for source_key, target_key in pairs:
        print(f"copy: {source_key} -> {target_key}")
        tos_client.client.copy_object(
            bucket=bucket,
            key=target_key,
            src_bucket=bucket,
            src_key=source_key,
            forbid_overwrite=True,
        )
        print(f"delete: {source_key}")
        tos_client.client.delete_object(bucket=bucket, key=source_key)

    print("copy_delete_done")


if __name__ == "__main__":
    main()
