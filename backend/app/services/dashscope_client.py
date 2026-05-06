import json
import os
import tempfile
import uuid
from io import BytesIO
from typing import Any, Optional

import requests
from PIL import Image

from app.core.config import get_settings
import logging
from app.services.video_frames import DEFAULT_VIDEO_FPS, extract_video_frames


class DashScopeClient:
    VIDEO_FRAME_LIST_MODELS = {
        "qwen3.6-plus",
        "qwen3.6-flash",
        "qwen3-vl-plus",
        "qwen3-vl-flash",
    }

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.dashscope_api_key
        self.base_url = settings.dashscope_base_url.rstrip("/")
        self.default_model = "qwen-plus"
        self.debug_response = settings.dashscope_debug_response
        self._logger = logging.getLogger(__name__)

    def extract_gif_frames(self, gif_url: str, max_frames: int = 5) -> list[str]:
        try:
            response = requests.get(gif_url, timeout=30)
            response.raise_for_status()

            gif = Image.open(BytesIO(response.content))
            frames = []
            frame_index = 0

            try:
                while frame_index < max_frames:
                    gif.seek(frame_index)
                    frame = gif.copy()
                    if frame.mode != "RGB":
                        frame = frame.convert("RGB")
                    frames.append(frame)
                    frame_index += 1
            except EOFError:
                pass

            if not frames:
                return []

            from app.utils import get_tos_client

            tos_client = get_tos_client()
            frame_urls: list[str] = []

            for index, frame in enumerate(frames):
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    frame.save(tmp.name, "JPEG", quality=85)

                    object_key = f"temp/dashscope_gif_frames/{uuid.uuid4().hex}_frame_{index}.jpg"
                    with open(tmp.name, "rb") as file_obj:
                        tos_client.client.put_object(
                            bucket=tos_client.bucket,
                            key=object_key,
                            content=file_obj.read(),
                        )
                    os.unlink(tmp.name)

                    frame_urls.append(tos_client.get_download_url(object_key, public_endpoint=True))

            return frame_urls
        except Exception as exc:
            print(f"DashScope GIF frame extraction failed: {exc}")
            return []

    def _build_prompt(
        self,
        file_type: str,
        annotation_prompt: Optional[str] = None,
        custom_tags: Optional[list[str]] = None,
        use_frame_list: bool = False,
    ) -> str:
        lower_file_type = file_type.lower()
        video_types = {"mp4", "avi", "mov", "mkv", "flv", "wmv", "webm"}

        if use_frame_list:
            prompt = "这是一个GIF动画拆分后的多帧图片，请综合分析这些帧的内容并描述整体场景、物体和动作。"
        elif lower_file_type in video_types:
            prompt = "请分析这个视频的内容，描述视频中的场景、物体、人物活动等信息。"
        else:
            prompt = "请分析这张图片的内容，描述图片中的场景、物体、人物活动等信息。"

        user_prompt = annotation_prompt or prompt
        if custom_tags:
            user_prompt = f"{user_prompt}\n\n请从以下标签中选择最合适的标签：{'，'.join(custom_tags)}"
        return user_prompt

    def _fetch_text_content(self, file_url: str) -> str:
        response = requests.get(file_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.encoding or "utf-8"
        return response.text

    def _should_use_video_frame_list_content(self, model: Optional[str]) -> bool:
        if not model:
            return False
        return model in self.VIDEO_FRAME_LIST_MODELS

    def _build_messages_content_log_view(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        content_view: list[dict[str, Any]] = []
        for message in messages:
            raw_content = message.get("content")
            if isinstance(raw_content, str):
                content_view.append(
                    {
                        "role": message.get("role"),
                        "content_type": "text",
                        "text_preview": raw_content[:120],
                    }
                )
                continue

            if isinstance(raw_content, list):
                item_views: list[dict[str, Any]] = []
                for item in raw_content:
                    if not isinstance(item, dict):
                        item_views.append({"type": type(item).__name__})
                        continue

                    if "video" in item and isinstance(item["video"], list):
                        item_views.append(
                            {
                                "type": "video",
                                "fps": item.get("fps"),
                                "frame_count": len(item["video"]),
                                "frame_preview": item["video"][:3],
                            }
                        )
                    elif "image" in item:
                        item_views.append(
                            {
                                "type": "image",
                                "image": item.get("image"),
                            }
                        )
                    elif "text" in item:
                        text_value = item.get("text")
                        item_views.append(
                            {
                                "type": "text",
                                "text_preview": text_value[:120] if isinstance(text_value, str) else None,
                            }
                        )
                    else:
                        item_views.append({"type": "unknown", "keys": sorted(item.keys())})

                content_view.append(
                    {
                        "role": message.get("role"),
                        "content_type": "list",
                        "items": item_views,
                    }
                )
                continue

            content_view.append(
                {
                    "role": message.get("role"),
                    "content_type": type(raw_content).__name__,
                }
            )

        return content_view

    def build_annotation_content(
        self,
        file_url: str,
        file_type: str,
        annotation_prompt: Optional[str] = None,
        custom_tags: Optional[list[str]] = None,
        gif_frame_urls: Optional[list[str]] = None,
        fps: float = DEFAULT_VIDEO_FPS,
        model_file_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        lower_file_type = file_type.lower()
        video_types = {"mp4", "avi", "mov", "mkv", "flv", "wmv", "webm"}
        text_types = {"txt", "text", "md", "markdown", "json", "csv", "log"}

        if lower_file_type in text_types:
            file_text = self._fetch_text_content(file_url)
            prompt = annotation_prompt or "请分析以下文本内容，并给出结构化、准确的结果。"
            if custom_tags:
                prompt = f"{prompt}\n\n请从以下标签中选择最合适的标签：{'，'.join(custom_tags)}"
            text_content = f"{prompt}\n\n文本内容如下：\n{file_text}"
            return {
                "mode": "text",
                "messages": [{"role": "user", "content": text_content}],
            }

        if lower_file_type == "gif" and gif_frame_urls:
            prompt = self._build_prompt(
                file_type=file_type,
                annotation_prompt=annotation_prompt,
                custom_tags=custom_tags,
                use_frame_list=True,
            )
            return {
                "mode": "multimodal",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"video": gif_frame_urls, "fps": fps},
                            {"text": prompt},
                        ],
                    }
                ],
            }

        prompt = self._build_prompt(
            file_type=file_type,
            annotation_prompt=annotation_prompt,
            custom_tags=custom_tags,
        )

        if lower_file_type in video_types:
            frame_urls = extract_video_frames(
                file_url,
                fps=fps,
                object_prefix="temp/dashscope_video_frames",
                public_download_url=True,
            )
            if self._should_use_video_frame_list_content(model) and frame_urls:
                media_content = [
                    {"video": frame_urls, "fps": fps},
                    {"text": f"这是从视频中按固定时间间隔抽取的一组关键帧图片。{prompt}"},
                ]
            else:
                media_content = [
                    *({"image": frame_url} for frame_url in frame_urls),
                    {"text": f"这是从视频中按固定时间间隔抽取的一组关键帧图片。{prompt}"},
                ]
        else:
            media_content = [
                {"image": model_file_url or file_url},
                {"text": prompt},
            ]

        return {
            "mode": "multimodal",
            "messages": [{"role": "user", "content": media_content}],
        }

    def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            f"{self.base_url}{endpoint}",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-DashScope-SSE": "disable",
            },
            json=payload,
            timeout=120,
        )

        if response.status_code >= 400:
            detail = response.text
            try:
                error_payload = response.json()
                detail = error_payload.get("message") or error_payload.get("code") or detail
            except ValueError:
                pass
            raise RuntimeError(f"DashScope 请求失败({response.status_code}): {detail}")

        return response.json()

    def _extract_response_text(self, payload: dict[str, Any]) -> str:
        output = payload.get("output") or {}
        choices = output.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            content = message.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                text_parts: list[str] = []
                for item in content:
                    if isinstance(item, dict):
                        if isinstance(item.get("text"), str):
                            text_parts.append(item["text"])
                        elif item.get("type") == "text" and isinstance(item.get("text"), str):
                            text_parts.append(item["text"])
                    elif isinstance(item, str):
                        text_parts.append(item)
                if text_parts:
                    return "\n".join(text_parts).strip()

        if isinstance(output.get("text"), str):
            return output["text"]

        message = output.get("message") or {}
        if isinstance(message.get("content"), str):
            return message["content"]

        raise RuntimeError(f"DashScope 返回结果缺少可解析文本: {json.dumps(payload, ensure_ascii=False)}")

    def _extract_usage(self, payload: dict[str, Any]) -> dict[str, Optional[int]]:
        usage = payload.get("usage") or {}
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        return {
            "input_tokens": int(input_tokens) if input_tokens is not None else None,
            "output_tokens": int(output_tokens) if output_tokens is not None else None,
        }

    def _messages_contain_json_keyword(self, messages: list[dict[str, Any]]) -> bool:
        for message in messages:
            content = message.get("content")
            if isinstance(content, str) and "json" in content.lower():
                return True
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        text = item.get("text")
                        if isinstance(text, str) and "json" in text.lower():
                            return True
        return False

    def _ensure_json_keyword(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if self._messages_contain_json_keyword(messages):
            return messages
        return [
            {
                "role": "system",
                "content": "请以JSON格式输出，仅返回合法JSON对象，不要输出任何额外说明。",
            },
            *messages,
        ]

    def annotate(
        self,
        content: dict[str, Any],
        model: Optional[str] = None,
        structured_output_json: bool = False,
    ) -> str:
        return self.annotate_with_usage(
            content,
            model,
            structured_output_json=structured_output_json,
        )["text"]

    def annotate_with_usage(
        self,
        content: dict[str, Any],
        model: Optional[str] = None,
        structured_output_json: bool = False,
    ) -> dict[str, Any]:
        if content["mode"] == "text":
            endpoint = "/services/aigc/text-generation/generation"
        else:
            endpoint = "/services/aigc/multimodal-generation/generation"

        messages = content["messages"]
        if structured_output_json:
            messages = self._ensure_json_keyword(messages)

        payload = {
            "model": model or self.default_model,
            "input": {"messages": messages},
            "parameters": {
                "result_format": "message",
                "enable_thinking": False,
                "max_tokens": 1000,
            },
        }
        if structured_output_json:
            payload["response_format"] = {"type": "json_object"}
        self._logger.info(
            "ALIYUN_DEBUG request content: endpoint=%s model=%s messages_content=%s",
            endpoint,
            payload.get("model"),
            json.dumps(self._build_messages_content_log_view(messages), ensure_ascii=False),
        )
        response_payload = self._post(endpoint, payload)
        if self.debug_response:
            # Avoid log flooding: print full JSON once per request but keep it on one line.
            self._logger.info(
                "DashScope raw response: endpoint=%s model=%s payload=%s",
                endpoint,
                payload.get("model"),
                json.dumps(response_payload, ensure_ascii=False),
            )
        usage = self._extract_usage(response_payload)
        return {
            "text": self._extract_response_text(response_payload),
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
        }

    def annotate_gif(
        self,
        gif_url: str,
        annotation_prompt: Optional[str] = None,
        custom_tags: Optional[list[str]] = None,
        model: Optional[str] = None,
        max_frames: int = 5,
        fps: float = DEFAULT_VIDEO_FPS,
        structured_output_json: bool = False,
    ) -> str:
        return self.annotate_gif_with_usage(
            gif_url,
            annotation_prompt,
            custom_tags,
            model,
            max_frames=max_frames,
            fps=fps,
            structured_output_json=structured_output_json,
        )["text"]

    def annotate_gif_with_usage(
        self,
        gif_url: str,
        annotation_prompt: Optional[str] = None,
        custom_tags: Optional[list[str]] = None,
        model: Optional[str] = None,
        max_frames: int = 5,
        fps: float = DEFAULT_VIDEO_FPS,
        structured_output_json: bool = False,
    ) -> dict[str, Any]:
        frame_urls = self.extract_gif_frames(gif_url, max_frames=max_frames)
        content = self.build_annotation_content(
            gif_url,
            "gif",
            annotation_prompt,
            custom_tags,
            gif_frame_urls=frame_urls or None,
            fps=fps,
        )
        return self.annotate_with_usage(
            content,
            model,
            structured_output_json=structured_output_json,
        )


_dashscope_client: Optional[DashScopeClient] = None


def get_dashscope_client() -> DashScopeClient:
    global _dashscope_client
    if _dashscope_client is None:
        _dashscope_client = DashScopeClient()
    return _dashscope_client
