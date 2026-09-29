"""动画视频的共用部分：提示词、首帧图片、下载后做成循环（docs/06 第 6.5、6.6 节）。

封面动画（D96）和开页动画（A4）用同一套做法：以原画为首帧生成视频（图生视频，D99），
下载后正放一遍再倒放回来，首尾都是原画，循环无接缝，叠在静态页上淡入也不跳。
"""

import hashlib
import io
import os
import tempfile
from pathlib import Path

import av
import numpy as np
from PIL import Image

from app.ai.settings import CapabilityConfig

# 首帧图片：长边缩到这么大（万相要求边长 360–2000 像素），JPEG 足够清楚
FRAME_LONG_EDGE = 1280
FRAME_QUALITY = 90
# 循环视频重新编码的画质（H.264 CRF，越小越清楚、文件越大）
LOOP_CRF = "23"

# 兜底的动作描述（正常由视觉模型看封面写出具体角色的动作，见 vision.describe_cover_motion）
DEFAULT_COVER_MOTION = "画面中的角色眨眨眼、轻轻点头、挥挥手，头发和衣角随风飘动"

# 像《哈利·波特》里《预言家日报》上会动的照片：主体明显地动，背景轻轻地动（D99）。
# 视频会倒放回来，所以只要来回往复的动作；D97 的教训：不能强调"幅度很小"，否则几乎不动
PROMPT_TEMPLATE = (
    "像《哈利·波特》里《预言家日报》上会动的魔法照片。镜头固定不动，"
    "保持原画的绘本画风、色彩和线条，画面中的文字完全不变。{motion}。"
    "主体的动作清楚、明显、生动自然，是来回往复的动作（摇摆、挥手、点头、眨眼这类），"
    "不要走路、跳走或掉落这类一去不回的动作；背景里的树叶、草、云和光影也轻轻地动。"
    "角色不离开画面，不要添加画面里没有的东西。"
)
NEGATIVE_PROMPT = (
    "镜头移动，镜头推拉，缩放，旋转，画面变形，画风变化，颜色变化，新增物体，新增角色，"
    "文字变化，文字抖动，闪烁，画面静止不动，角色离开画面"
)


def _clean_motion(motion: str | None) -> str:
    return (motion or "").strip().rstrip("。；;，,")


def cover_prompt(motion: str | None) -> str:
    return PROMPT_TEMPLATE.format(motion=_clean_motion(motion) or DEFAULT_COVER_MOTION)


def unit_prompt(motion: str) -> str:
    return PROMPT_TEMPLATE.format(motion=_clean_motion(motion))


def frame_jpeg(image_paths: list[Path]) -> bytes:
    """把页面图转成上传给服务商的首帧：RGB JPEG，长边不超过 FRAME_LONG_EDGE，边长取偶数。

    合并生成的开页传入左右两页，按同样高度左右拼成一张整图（docs/06 第 6.5 节）。
    """
    images = []
    for path in image_paths:
        with Image.open(path) as image:
            images.append(image.convert("RGB"))
    frame = images[0]
    if len(images) > 1:
        height = min(i.height for i in images)
        scaled = [
            i if i.height == height else i.resize((round(i.width * height / i.height), height))
            for i in images
        ]
        frame = Image.new("RGB", (sum(i.width for i in scaled), height))
        x = 0
        for i in scaled:
            frame.paste(i, (x, 0))
            x += i.width
    frame.thumbnail((FRAME_LONG_EDGE, FRAME_LONG_EDGE), Image.Resampling.LANCZOS)
    width, height = frame.width // 2 * 2, frame.height // 2 * 2
    if (width, height) != frame.size:
        frame = frame.crop((0, 0, width, height))
    buf = io.BytesIO()
    frame.save(buf, format="JPEG", quality=FRAME_QUALITY)
    return buf.getvalue()


class VideoProcessError(Exception):
    pass


def save_loop_video(data: bytes, path: Path) -> None:
    """做成来回播放的循环：正放一遍再倒放回来（两端的帧不重复），首尾都是原画、接缝处不跳。
    重新编码为 H.264（去掉音轨，索引放在文件开头便于边下边播），先写临时文件再替换。
    解码出的画面先存到磁盘上的临时文件，倒着读，1080P 的视频也不会占用大量内存。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    try:
        with tempfile.TemporaryFile() as raw, av.open(io.BytesIO(data)) as source:
            if not source.streams.video:
                raise VideoProcessError("下载的文件里没有视频")
            stream = source.streams.video[0]
            rate = stream.average_rate or 30
            width = height = count = 0
            for frame in source.decode(stream):
                if not count:
                    width, height = frame.width // 2 * 2, frame.height // 2 * 2
                yuv = frame.reformat(width=width, height=height, format="yuv420p")
                raw.write(yuv.to_ndarray().tobytes())
                count += 1
            if count < 2:
                raise VideoProcessError("下载的视频里没有画面")
            size = width * height * 3 // 2
            order = [*range(count), *range(count - 2, 0, -1)]
            with av.open(
                str(tmp), mode="w", format="mp4", options={"movflags": "faststart"}
            ) as out:
                encoder = out.add_stream("libx264", rate=rate)
                encoder.width, encoder.height, encoder.pix_fmt = width, height, "yuv420p"
                encoder.options = {"crf": LOOP_CRF, "preset": "medium"}
                for i in order:
                    raw.seek(i * size)
                    planes = np.frombuffer(raw.read(size), np.uint8).reshape(height * 3 // 2, width)
                    for packet in encoder.encode(av.VideoFrame.from_ndarray(planes, "yuv420p")):
                        out.mux(packet)
                for packet in encoder.encode():
                    out.mux(packet)
    except (av.FFmpegError, ValueError) as e:
        tmp.unlink(missing_ok=True)
        raise VideoProcessError("下载的视频无法处理") from e
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    os.replace(tmp, path)


def cover_source_hash(
    motion: str | None, video: CapabilityConfig, duration: int, resolution: str
) -> str:
    """封面动画的"动作描述 + 模型 + 时长 + 清晰度"指纹；变了就显示"需要重新生成"。
    判断是否过期时用封面生成时的时长和清晰度，所以临时换清晰度（D79）不算过期。"""
    raw = "\n".join([cover_prompt(motion), video.provider, video.model, str(duration), resolution])
    return hashlib.sha256(raw.encode()).hexdigest()


def unit_source_hash(
    motion: str | None, video: CapabilityConfig, duration: int, resolution: str
) -> str:
    """开页动画的"动作描述 + 模型 + 时长 + 清晰度"指纹。判断是否过期时用单元生成时的时长和清晰度，
    所以临时换了清晰度（D79）不算过期，改动作描述或换模型才算。"""
    raw = "\n".join(
        [unit_prompt(motion or ""), video.provider, video.model, str(duration), resolution]
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def cover_frame_key(cover_page_index: int, assets_version: int) -> str:
    """生成时用的是哪一张封面；换了封面或重新拆页后，旧动画对不上。"""
    return f"{cover_page_index}:{assets_version}"
