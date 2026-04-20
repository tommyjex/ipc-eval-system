#!/usr/bin/env python3
"""
使用火山方舟 Seedream 5.0 生成登录页/首页大图。

示例：
  cd backend
  source .venv/bin/activate

  # 生成登录页大图
  PYTHONPATH=. python scripts/generate_seedream_images.py --preset login

  # 生成首页大图
  PYTHONPATH=. python scripts/generate_seedream_images.py --preset home

  # 自定义 prompt
  PYTHONPATH=. python scripts/generate_seedream_images.py \
    --prompt "未来感家庭智能中控大屏，温暖客厅场景，蓝白科技风"
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import requests
from volcenginesdkarkruntime import Ark

from app.core.config import get_settings


MODEL_ID = "doubao-seedream-5-0-260128"
DEFAULT_SIZE = "2K"
DEFAULT_OUTPUT_FORMAT = "png"

PRESET_PROMPTS = {
    "login": (
        "家庭智能主题登录页大图，现代高端智能家居客厅场景，"
        "画面中有柔和灯光、智能中控屏、安防摄像头、门磁、扫地机器人、智能音箱，"
        "整体风格简洁高级、蓝白科技感、轻拟物与真实场景融合，"
        "留出右侧或中央大面积留白用于登录表单，横向构图，网页首屏 Banner 视觉，"
        "画质精致，商业产品官网风格。"
    ),
    "home": (
        "家庭智能主题首页大图，展示完整的智慧家庭生态，"
        "包括智能摄像头、智能门锁、智能照明、智能电视、语音助手、家庭大屏中控、老人儿童看护、安防提醒等元素，"
        "场景温暖明亮，具有未来感与可信赖感，蓝白橙点缀的科技配色，"
        "横向宽屏网页头图构图，左中右层次丰富，适合作为产品官网首页 Hero Banner，"
        "高质量、高细节、现代互联网企业官网视觉。"
    ),
}


def build_client() -> Ark:
    settings = get_settings()
    return Ark(
        base_url=settings.ark_base_url,
        api_key=settings.ark_api_key,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="调用 doubao-seedream-5-0-260128 生成图片")
    parser.add_argument(
        "--preset",
        choices=sorted(PRESET_PROMPTS.keys()),
        help="使用内置场景 prompt，支持 login / home",
    )
    parser.add_argument("--prompt", default="", help="自定义 prompt；若传入则优先级高于 --preset")
    parser.add_argument("--size", default=DEFAULT_SIZE, help="图片尺寸，例如 2K / 3K")
    parser.add_argument("--output-format", default=DEFAULT_OUTPUT_FORMAT, choices=["png", "jpeg"], help="输出格式")
    parser.add_argument("--output-dir", default="generated_images", help="生成图片下载目录")
    parser.add_argument("--filename", default="", help="输出文件名，不带路径")
    parser.add_argument("--watermark", action="store_true", help="是否保留水印，默认关闭")
    parser.add_argument("--no-download", action="store_true", help="只打印 URL，不下载图片")
    return parser.parse_args()


def resolve_prompt(args: argparse.Namespace) -> str:
    if args.prompt.strip():
        return args.prompt.strip()
    if args.preset:
        return PRESET_PROMPTS[args.preset]
    raise ValueError("请通过 --preset 或 --prompt 提供生成提示词")


def download_image(url: str, output_path: Path):
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(response.content)


def main():
    args = parse_args()
    prompt = resolve_prompt(args)
    client = build_client()

    print("[INFO] 调用模型生成图片...")
    print(f"[INFO] model={MODEL_ID}")
    print(f"[INFO] size={args.size}")
    print(f"[INFO] output_format={args.output_format}")
    print(f"[INFO] prompt={prompt}")

    result = client.images.generate(
        model=MODEL_ID,
        prompt=prompt,
        size=args.size,
        output_format=args.output_format,
        response_format="url",
        watermark=args.watermark,
    )

    if not getattr(result, "data", None):
        raise RuntimeError("模型未返回图片结果")

    image_url = result.data[0].url
    print(f"[INFO] image_url={image_url}")

    metadata = {
        "model": MODEL_ID,
        "prompt": prompt,
        "size": args.size,
        "output_format": args.output_format,
        "image_url": image_url,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = args.filename.strip() or (
        f"{args.preset or 'custom'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{args.output_format}"
    )
    output_path = output_dir / stem
    meta_path = output_path.with_suffix(".json")

    if not args.no_download:
        print(f"[INFO] 下载图片到: {output_path}")
        download_image(image_url, output_path)
    else:
        print("[INFO] 已跳过下载，仅输出 URL")

    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[INFO] 元数据已写入: {meta_path}")


if __name__ == "__main__":
    main()
