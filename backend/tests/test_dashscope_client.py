import pytest

from app.services.dashscope_client import DashScopeClient


def build_client_without_settings() -> DashScopeClient:
    return DashScopeClient.__new__(DashScopeClient)


@pytest.mark.parametrize("model", ["qwen3.7-plus", "qwen3.7-flash"])
def test_qwen37_models_use_video_frame_sequence_content(model):
    client = build_client_without_settings()
    frame_urls = [
        "https://example.com/frame-1.jpg",
        "https://example.com/frame-2.jpg",
        "https://example.com/frame-3.jpg",
        "https://example.com/frame-4.jpg",
    ]
    prompt = "请分析视频帧"
    fps = 0.3

    content = client._build_frame_sequence_content(
        frame_urls,
        prompt,
        fps,
        model=model,
    )

    assert content == [
        {"video": frame_urls, "fps": fps},
        {"text": prompt},
    ]


def test_non_video_frame_list_model_uses_image_sequence_content():
    client = build_client_without_settings()
    frame_urls = [
        "https://example.com/frame-1.jpg",
        "https://example.com/frame-2.jpg",
        "https://example.com/frame-3.jpg",
        "https://example.com/frame-4.jpg",
    ]
    prompt = "请分析视频帧"

    content = client._build_frame_sequence_content(
        frame_urls,
        prompt,
        fps=0.3,
        model="qwen3.5-flash",
    )

    assert content == [
        {"image": "https://example.com/frame-1.jpg"},
        {"image": "https://example.com/frame-2.jpg"},
        {"image": "https://example.com/frame-3.jpg"},
        {"image": "https://example.com/frame-4.jpg"},
        {"text": prompt},
    ]
