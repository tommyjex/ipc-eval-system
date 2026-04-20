import os
import tempfile
import uuid
import json
from io import BytesIO
from urllib.parse import urlparse
import urllib.request

import imageio.v2 as imageio
import requests
from PIL import Image

from app.utils import get_tos_client

DEFAULT_VIDEO_FPS = 0.3
DEBUG_TRACE_ENV_PATH = "/Users/bytedance/AI-IPC-Evaluation/ipc-eval-system/.dbg/task-25-timeout-trace.env"


def _emit_timeout_trace(location: str, hypothesis_id: str, msg: str, data: dict):
    #region debug-point trace-emit
    debug_server_url = "http://127.0.0.1:7777/event"
    session_id = "task-25-timeout-trace"
    try:
        with open(DEBUG_TRACE_ENV_PATH, "r", encoding="utf-8") as env_file:
            for line in env_file:
                line = line.strip()
                if line.startswith("DEBUG_SERVER_URL="):
                    debug_server_url = line.split("=", 1)[1]
                elif line.startswith("DEBUG_SESSION_ID="):
                    session_id = line.split("=", 1)[1]
    except Exception:
        return

    payload = {
        "sessionId": session_id,
        "runId": "pre",
        "hypothesisId": hypothesis_id,
        "location": location,
        "msg": msg,
        "data": data,
    }
    try:
        request = urllib.request.Request(
            debug_server_url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(request, timeout=2).read()
    except Exception:
        pass
    #endregion


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
) -> list[str]:
    target_fps = max(float(fps or DEFAULT_VIDEO_FPS), 0.01)
    _emit_timeout_trace(
        "app/services/video_frames.py:extract_video_frames:start",
        "A",
        "[DEBUG] start video download",
        {"video_url": video_url, "fps": target_fps, "object_prefix": object_prefix},
    )
    response = requests.get(video_url, timeout=120)
    response.raise_for_status()
    _emit_timeout_trace(
        "app/services/video_frames.py:extract_video_frames:download-finished",
        "A",
        "[DEBUG] video download finished",
        {"video_url": video_url, "bytes": len(response.content), "object_prefix": object_prefix},
    )

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
            frame_urls.append(tos_client.get_download_url(object_key))
            next_capture_time += frame_interval_seconds

        if not frame_urls:
            raise RuntimeError("视频抽帧失败，未提取到任何帧")

        _emit_timeout_trace(
            "app/services/video_frames.py:extract_video_frames:frames-finished",
            "B",
            "[DEBUG] video frame extraction finished",
            {"video_url": video_url, "frame_count": len(frame_urls), "object_prefix": object_prefix},
        )
        return frame_urls
    finally:
        if reader is not None:
            reader.close()
        if temp_video_path and os.path.exists(temp_video_path):
            os.unlink(temp_video_path)
