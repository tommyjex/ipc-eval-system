from typing import Any, Optional
from volcenginesdkarkruntime import Ark
from app.core.config import get_settings
import tempfile
import os
import json
import re
import requests
from PIL import Image
from io import BytesIO

from app.services.video_frames import DEFAULT_VIDEO_FPS, extract_video_frames


class ArkClient:
    def __init__(self):
        settings = get_settings()
        self.client = Ark(api_key=settings.ark_api_key)
        self.base_url = settings.ark_base_url
        self.default_model = settings.ark_model

    def extract_gif_frames(self, gif_url: str, max_frames: int = 5) -> list[str]:
        try:
            response = requests.get(gif_url, timeout=30)
            response.raise_for_status()
            
            gif = Image.open(BytesIO(response.content))
            
            frames = []
            frame_count = 0
            
            try:
                while frame_count < max_frames:
                    gif.seek(frame_count)
                    frame = gif.copy()
                    if frame.mode != 'RGB':
                        frame = frame.convert('RGB')
                    frames.append(frame)
                    frame_count += 1
            except EOFError:
                pass
            
            if len(frames) == 0:
                return []
            
            from app.utils import get_tos_client
            tos_client = get_tos_client()
            
            frame_urls = []
            for i, frame in enumerate(frames):
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                    frame.save(tmp.name, 'JPEG', quality=85)
                    
                    object_key = f"temp/gif_frames/{os.path.basename(gif_url).split('.')[0]}_frame_{i}.jpg"
                    with open(tmp.name, 'rb') as f:
                        file_content = f.read()
                        tos_client.client.put_object(
                            bucket=tos_client.bucket,
                            key=object_key,
                            content=file_content
                        )
                    os.unlink(tmp.name)
                    
                    frame_url = tos_client.get_download_url(object_key)
                    frame_urls.append(frame_url)
            
            return frame_urls
        except Exception as e:
            print(f"Error extracting GIF frames: {e}")
            return []

    def build_annotation_content(
        self,
        file_url: str,
        file_type: str,
        annotation_prompt: Optional[str] = None,
        custom_tags: Optional[list[str]] = None,
        gif_frame_urls: Optional[list[str]] = None,
        fps: float = DEFAULT_VIDEO_FPS,
    ) -> list[dict]:
        video_types = {"mp4", "avi", "mov", "mkv", "flv", "wmv"}
        is_video = file_type.lower() in video_types
        is_gif = file_type.lower() == "gif"

        default_prompt = "请分析这张图片的内容，描述图片中的场景、物体、人物活动等信息。" if not is_video else "请分析这个视频的内容，描述视频中的场景、物体、人物活动等信息。"
        
        if is_gif and gif_frame_urls:
            default_prompt = "这是一个GIF动画的多帧图片，请分析这些帧图片的内容，描述动画中的场景、物体、人物活动等信息。"
        elif is_video:
            default_prompt = "这是从视频中按固定时间间隔抽取的一组关键帧图片，请综合分析这些帧图片的内容，描述视频中的场景、物体、人物活动等信息。"
        
        user_prompt = annotation_prompt or default_prompt
        
        if custom_tags and len(custom_tags) > 0:
            tags_str = "，".join(custom_tags)
            user_prompt = f"{user_prompt}\n\n请从以下标签中选择最合适的标签：{tags_str}"

        content = [{"type": "input_text", "text": user_prompt}]

        if is_gif and gif_frame_urls and len(gif_frame_urls) > 0:
            for frame_url in gif_frame_urls:
                content.append({"type": "input_image", "image_url": frame_url, "detail": "low"})
        elif is_video:
            frame_urls = extract_video_frames(file_url, fps=fps, object_prefix="temp/ark_video_frames")
            for frame_url in frame_urls:
                content.append({"type": "input_image", "image_url": frame_url, "detail": "low"})
        else:
            content.append({"type": "input_image", "image_url": file_url, "detail": "low"})

        return content

    def annotate(
        self,
        content: list[dict],
        model: Optional[str] = None
    ) -> str:
        return self.annotate_with_usage(content, model)["text"]

    def _extract_usage(self, response: Any) -> dict[str, Optional[int]]:
        usage = getattr(response, "usage", None)
        if usage is None and isinstance(response, dict):
            usage = response.get("usage")
        if usage is None and hasattr(response, "model_dump"):
            try:
                usage = response.model_dump().get("usage")
            except Exception:
                usage = None

        if isinstance(usage, dict):
            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")
        else:
            input_tokens = getattr(usage, "input_tokens", None) if usage is not None else None
            output_tokens = getattr(usage, "output_tokens", None) if usage is not None else None

        return {
            "input_tokens": int(input_tokens) if input_tokens is not None else None,
            "output_tokens": int(output_tokens) if output_tokens is not None else None,
        }

    def annotate_with_usage(
        self,
        content: list[dict],
        model: Optional[str] = None
    ) -> dict[str, Any]:
        response = self.client.responses.create(
            model=model or self.default_model,
            input=[
                {
                    "role": "user",
                    "content": content
                }
            ],
            thinking={"type":"disabled"}
        )
        text = ""
        for item in response.output:
            if item.type == "message" and item.role == "assistant":
                if item.content and len(item.content) > 0:
                    text = item.content[0].text
                    break
        usage = self._extract_usage(response)
        return {
            "text": text,
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
        }

    def _extract_json_block(self, text: str) -> dict:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if not match:
                raise
            return json.loads(match.group(0))

    def _extract_scoring_fields(self, text: str) -> dict:
        recall_match = re.search(r'"recall"\s*:\s*([0-9]+(?:\.[0-9]+)?)|召回率\s*[:：]\s*([0-9]+(?:\.[0-9]+)?)', text)
        accuracy_match = re.search(r'"accuracy"\s*:\s*([0-9]+(?:\.[0-9]+)?)|准确率\s*[:：]\s*([0-9]+(?:\.[0-9]+)?)', text)
        reason_match = re.search(r'"reason"\s*:\s*"([\s\S]*?)"|评分理由\s*[:：]\s*([\s\S]+)', text)

        recall_value = "0"
        if recall_match:
            recall_value = recall_match.group(1) or recall_match.group(2) or "0"

        accuracy_value = "0"
        if accuracy_match:
            accuracy_value = accuracy_match.group(1) or accuracy_match.group(2) or "0"
        reason_value = ""
        if reason_match:
            reason_value = (reason_match.group(1) or reason_match.group(2) or "").strip().strip('",')

        return {
            "recall": float(recall_value),
            "accuracy": float(accuracy_value),
            "reason": reason_value,
        }

    def _normalize_scoring_input(self, text: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            return cleaned

        try:
            parsed = self._extract_json_block(cleaned)
        except Exception:
            return cleaned

        if isinstance(parsed, dict) and "event" in parsed:
            normalized = {
                "description": parsed.get("description", ""),
                "title": parsed.get("title", ""),
                "event": parsed.get("event", []),
            }
            return json.dumps(normalized, ensure_ascii=False)

        return json.dumps(parsed, ensure_ascii=False)

    def annotate_image(
        self,
        image_url: str,
        annotation_prompt: Optional[str] = None,
        custom_tags: Optional[list[str]] = None,
        model: Optional[str] = None
    ) -> str:
        content = self.build_annotation_content(image_url, "jpg", annotation_prompt, custom_tags)
        return self.annotate(content, model)

    def annotate_video(
        self,
        video_url: str,
        annotation_prompt: Optional[str] = None,
        custom_tags: Optional[list[str]] = None,
        model: Optional[str] = None,
        fps: float = DEFAULT_VIDEO_FPS,
    ) -> str:
        content = self.build_annotation_content(video_url, "mp4", annotation_prompt, custom_tags, fps=fps)
        return self.annotate(content, model)

    def annotate_gif(
        self,
        gif_url: str,
        annotation_prompt: Optional[str] = None,
        custom_tags: Optional[list[str]] = None,
        model: Optional[str] = None,
        max_frames: int = 5,
        fps: float = DEFAULT_VIDEO_FPS,
    ) -> str:
        return self.annotate_gif_with_usage(
            gif_url,
            annotation_prompt,
            custom_tags,
            model,
            max_frames=max_frames,
            fps=fps,
        )["text"]

    def annotate_gif_with_usage(
        self,
        gif_url: str,
        annotation_prompt: Optional[str] = None,
        custom_tags: Optional[list[str]] = None,
        model: Optional[str] = None,
        max_frames: int = 5,
        fps: float = DEFAULT_VIDEO_FPS,
    ) -> dict[str, Any]:
        frame_urls = self.extract_gif_frames(gif_url, max_frames)
        
        if frame_urls:
            content = self.build_annotation_content(
                gif_url, "gif", annotation_prompt, custom_tags, gif_frame_urls=frame_urls, fps=fps
            )
        else:
            content = self.build_annotation_content(gif_url, "gif", annotation_prompt, custom_tags, fps=fps)
        
        return self.annotate_with_usage(content, model)

    def score_result(
        self,
        ground_truth: str,
        model_output: str,
        scoring_criteria: Optional[str] = None,
        model: str = "doubao-seed-2.0-pro-260215"
    ) -> dict:
        normalized_ground_truth = self._normalize_scoring_input(ground_truth)
        normalized_model_output = self._normalize_scoring_input(model_output)
        prompt = f"""你是一个严格的评测助手，需要根据标注结果与模型输出，对模型结果进行结构化评分。

请仅基于以下三项内容完成评分：
1. 标注结果（ground_truth）
2. 模型输出（model_output）
3. 评分标准

评分要求：
- recall 表示召回率，范围 0 到 100
- accuracy 表示准确率，范围 0 到 100
- reason 用中文简洁说明评分理由
- 只返回 JSON，不要输出任何额外说明
- 如果输入内容是 JSON，且包含 description、title、event 等字段，请优先按 JSON 解析
- 如果 ground_truth 和 model_output 都包含 event 列表，请严格按评分标准比对 event 列表，不要把 description 或 title 当作评分依据

评分标准：
{scoring_criteria or "无"}

标注结果：
{normalized_ground_truth}

模型输出：
{normalized_model_output}

请严格按以下 JSON 结构返回：
{{
  "recall": 0,
  "accuracy": 0,
  "reason": "评分理由"
}}
"""
        response_text = self.annotate(
            [{"type": "input_text", "text": prompt}],
            model=model
        )
        try:
            parsed = self._extract_json_block(response_text)
        except Exception:
            parsed = self._extract_scoring_fields(response_text)
        recall = max(0.0, min(100.0, float(parsed.get("recall", 0))))
        accuracy = max(0.0, min(100.0, float(parsed.get("accuracy", 0))))
        reason = str(parsed.get("reason", "")).strip()
        return {
            "recall": recall,
            "accuracy": accuracy,
            "reason": reason,
        }


_ark_client: Optional[ArkClient] = None


def get_ark_client() -> ArkClient:
    global _ark_client
    if _ark_client is None:
        _ark_client = ArkClient()
    return _ark_client
