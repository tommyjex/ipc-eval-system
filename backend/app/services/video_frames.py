import os
import tempfile
import uuid
from io import BytesIO
from urllib.parse import urlparse

import imageio.v2 as imageio
import requests
from PIL import Image

from app.utils import get_tos_client

DEFAULT_VIDEO_FPS = 0.3


def _resize_to_480p(frame_image: Image.Image) -> Image.Image:
    image = frame_image.convert("RGB")
    width, height = image.size
    if height < width:
        target_width, target_height = 720, 480
    else:
        target_width, target_height = 480, 720

    if height <= target_height and width <= target_width:
        return image

    if height / target_height < width / target_width:
        new_width = target_width
        new_height = int(height * (new_width / width))
    else:
        new_height = target_height
        new_width = int(width * (new_height / height))

    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    return image


def extract_video_frames(
    video_url: str,
    fps: float = DEFAULT_VIDEO_FPS,
    object_prefix: str = "temp/video_frames",
    public_download_url: bool = False,
) -> list[str]:
    target_fps = max(float(fps or DEFAULT_VIDEO_FPS), 0.01)
    response = requests.get(video_url, timeout=120)
    response.raise_for_status()

    tos_client = get_tos_client()
    temp_video_path = ""
    reader = None
    frame_urls: list[str] = []

    try:
        parsed_path = urlparse(video_url).path
        suffix = os.path.splitext(parsed_path)[1] or ".mp4"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_video:
            tmp_video.write(response.content)
            temp_video_path = tmp_video.name

        reader = imageio.get_reader(temp_video_path, format="ffmpeg")
        metadata = reader.get_meta_data()
        source_fps = float(metadata.get("fps") or 0) or 1.0
        frame_interval_seconds = 1.0 / target_fps
        next_capture_time = 0.0

        for frame_index, frame_array in enumerate(reader):
            current_time = frame_index / source_fps
            if current_time + 1e-6 < next_capture_time:
                continue

            image = _resize_to_480p(Image.fromarray(frame_array))
            frame_buffer = BytesIO()
            image.save(frame_buffer, format="JPEG", quality=85, optimize=True)
            object_key = f"{object_prefix}/{uuid.uuid4().hex}_frame_{len(frame_urls)}.jpg"
            tos_client.client.put_object(
                bucket=tos_client.bucket,
                key=object_key,
                content=frame_buffer.getvalue(),
            )
            frame_urls.append(tos_client.get_download_url(object_key, public_endpoint=public_download_url))
            next_capture_time += frame_interval_seconds

        if not frame_urls:
            raise RuntimeError("视频抽帧失败，未提取到任何帧")

        return frame_urls
    finally:
        if reader is not None:
            reader.close()
        if temp_video_path and os.path.exists(temp_video_path):
            os.unlink(temp_video_path)
