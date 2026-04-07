from typing import Optional
from volcenginesdkarkruntime import Ark
from app.core.config import get_settings
import tempfile
import os
import requests
from PIL import Image
from io import BytesIO


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
        gif_frame_urls: Optional[list[str]] = None
    ) -> list[dict]:
        video_types = {"mp4", "avi", "mov", "mkv", "flv", "wmv"}
        is_video = file_type.lower() in video_types
        is_gif = file_type.lower() == "gif"

        default_prompt = "请分析这张图片的内容，描述图片中的场景、物体、人物活动等信息。" if not is_video else "请分析这个视频的内容，描述视频中的场景、物体、人物活动等信息。"
        
        if is_gif and gif_frame_urls:
            default_prompt = "这是一个GIF动画的多帧图片，请分析这些帧图片的内容，描述动画中的场景、物体、人物活动等信息。"
        
        user_prompt = annotation_prompt or default_prompt
        
        if custom_tags and len(custom_tags) > 0:
            tags_str = "，".join(custom_tags)
            user_prompt = f"{user_prompt}\n\n请从以下标签中选择最合适的标签：{tags_str}"

        content = [{"type": "input_text", "text": user_prompt}]

        if is_gif and gif_frame_urls and len(gif_frame_urls) > 0:
            for frame_url in gif_frame_urls:
                content.append({"type": "input_image", "image_url": frame_url})
        elif is_video:
            content.append({"type": "input_video", "video_url": file_url})
        else:
            content.append({"type": "input_image", "image_url": file_url})

        return content

    def annotate(
        self,
        content: list[dict],
        model: Optional[str] = None
    ) -> str:
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
        for item in response.output:
            if item.type == "message" and item.role == "assistant":
                if item.content and len(item.content) > 0:
                    return item.content[0].text
        return ""

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
        model: Optional[str] = None
    ) -> str:
        content = self.build_annotation_content(video_url, "mp4", annotation_prompt, custom_tags)
        return self.annotate(content, model)

    def annotate_gif(
        self,
        gif_url: str,
        annotation_prompt: Optional[str] = None,
        custom_tags: Optional[list[str]] = None,
        model: Optional[str] = None,
        max_frames: int = 5
    ) -> str:
        frame_urls = self.extract_gif_frames(gif_url, max_frames)
        
        if frame_urls:
            content = self.build_annotation_content(
                gif_url, "gif", annotation_prompt, custom_tags, gif_frame_urls=frame_urls
            )
        else:
            content = self.build_annotation_content(gif_url, "gif", annotation_prompt, custom_tags)
        
        return self.annotate(content, model)


_ark_client: Optional[ArkClient] = None


def get_ark_client() -> ArkClient:
    global _ark_client
    if _ark_client is None:
        _ark_client = ArkClient()
    return _ark_client
