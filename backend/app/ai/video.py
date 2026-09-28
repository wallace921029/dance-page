"""首尾帧视频的共用部分：提示词、首帧图片、下载后的处理（docs/06 第 6.5 节）。

封面动画（D96）先用上；A4 的开页动画沿用同一套做法。
"""

import hashlib
import io
import os
from pathlib import Path

import av
from PIL import Image

from app.ai.settings import CapabilityConfig

# 首帧图片：长边缩到这么大（万相要求边长 360–2000 像素），JPEG 足够清楚
FRAME_LONG_EDGE = 1280
FRAME_QUALITY = 90

# 兜底的动作描述（正常由视觉模型看封面写出具体角色的动作，见 vision.describe_cover_motion）
DEFAULT_COVER_MOTION = "画面中的角色眨眨眼睛、轻轻点头，头发和衣角随微风飘动"

# 像魔法报纸上会动的照片：画还是那张画，只有角色做看得见的小动作，再回到原样。
# 不能把"幅度很小"强调过头：首尾帧相同，模型容易干脆不动（D96 实测几乎静止）
COVER_PROMPT_TEMPLATE = (
    "镜头完全固定不动，背景和其他物体保持静止，保持原画的绘本画风、色彩和线条，"
    "画面中的文字和书名完全不变。像一张有魔法的会动的照片：{motion}。"
    "角色的动作轻柔自然、清楚可见，角色留在原位不走动，最后回到初始姿态。"
)
NEGATIVE_PROMPT = (
    "镜头移动，镜头推拉，缩放，旋转，画面变形，画风变化，颜色变化，新增物体，"
    "文字变化，文字抖动，闪烁，剧烈动作，角色走动，角色离开画面，画面静止不动"
)


def cover_prompt(motion: str | None) -> str:
    motion = (motion or "").strip().rstrip("。；;，,") or DEFAULT_COVER_MOTION
    return COVER_PROMPT_TEMPLATE.format(motion=motion)


def frame_jpeg(image_path: Path) -> bytes:
    """把页面图转成上传给服务商的首帧：RGB JPEG，长边不超过 FRAME_LONG_EDGE，边长取偶数。"""
    with Image.open(image_path) as image:
        frame = image.convert("RGB")
    frame.thumbnail((FRAME_LONG_EDGE, FRAME_LONG_EDGE), Image.Resampling.LANCZOS)
    width, height = frame.width // 2 * 2, frame.height // 2 * 2
    if (width, height) != frame.size:
        frame = frame.crop((0, 0, width, height))
    buf = io.BytesIO()
    frame.save(buf, format="JPEG", quality=FRAME_QUALITY)
    return buf.getvalue()


class VideoProcessError(Exception):
    pass


def save_video(data: bytes, path: Path) -> None:
    """去掉音轨，并把索引移到文件开头（边下载边播放），不重新编码。先写临时文件再替换。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    try:
        with av.open(io.BytesIO(data)) as source:
            if not source.streams.video:
                raise VideoProcessError("下载的文件里没有视频")
            video_in = source.streams.video[0]
            with av.open(
                str(tmp), mode="w", format="mp4", options={"movflags": "faststart"}
            ) as out:
                video_out = out.add_stream_from_template(video_in)
                for packet in source.demux(video_in):
                    if packet.dts is None:
                        continue
                    packet.stream = video_out
                    out.mux(packet)
    except (av.FFmpegError, ValueError) as e:
        tmp.unlink(missing_ok=True)
        raise VideoProcessError("下载的视频无法处理") from e
    os.replace(tmp, path)


def cover_source_hash(motion: str | None, video: CapabilityConfig, resolution: str) -> str:
    """封面动画的"动作描述 + 模型 + 清晰度"指纹；变了就显示"需要重新生成"。"""
    raw = "\n".join([cover_prompt(motion), video.provider, video.model, resolution])
    return hashlib.sha256(raw.encode()).hexdigest()


def cover_frame_key(cover_page_index: int, assets_version: int) -> str:
    """生成时用的是哪一张封面；换了封面或重新拆页后，旧动画对不上。"""
    return f"{cover_page_index}:{assets_version}"
