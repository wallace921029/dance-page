"""朗读音频的解码、拼接和编码（docs/06-ai-tech-design.md 第 6.4 节）。

每行台词单独合成后解码成同一规格的 PCM，行间插入停顿，再用 PyAV 编码为 AAC `.m4a`
（iPad Safari 和 Chrome 都能播放）。
"""

import io
import os
from pathlib import Path

import av
import numpy as np

SAMPLE_RATE = 24000
# 行与行之间的停顿（秒）
LINE_GAP_SECONDS = 0.4
BIT_RATE = 64000


class AudioDecodeError(Exception):
    pass


def decode_to_pcm(data: bytes) -> np.ndarray:
    """把任意格式的音频解码为 24kHz 单声道 16 位 PCM，形状 (1, 采样数)。"""
    resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
    chunks: list[np.ndarray] = []
    try:
        with av.open(io.BytesIO(data)) as container:
            for frame in container.decode(audio=0):
                chunks.extend(f.to_ndarray() for f in resampler.resample(frame))
        chunks.extend(f.to_ndarray() for f in resampler.resample(None))
    except (av.FFmpegError, ValueError, IndexError) as e:
        raise AudioDecodeError("音频无法解码") from e
    if not chunks:
        raise AudioDecodeError("音频为空")
    return np.concatenate(chunks, axis=1)


def join_lines(segments: list[np.ndarray]) -> np.ndarray:
    gap = np.zeros((1, int(LINE_GAP_SECONDS * SAMPLE_RATE)), dtype=np.int16)
    pieces: list[np.ndarray] = []
    for i, segment in enumerate(segments):
        if i:
            pieces.append(gap)
        pieces.append(segment)
    return np.concatenate(pieces, axis=1)


def duration_ms(pcm: np.ndarray) -> int:
    return round(pcm.shape[1] * 1000 / SAMPLE_RATE)


def write_m4a(pcm: np.ndarray, path: Path) -> None:
    """编码为 AAC `.m4a`。先写临时文件再替换，播放中的旧文件不会读到一半的内容。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    # faststart：索引放在文件开头，边下载边播放
    with av.open(str(tmp), mode="w", format="ipod", options={"movflags": "faststart"}) as out:
        stream = out.add_stream("aac", rate=SAMPLE_RATE, layout="mono")
        stream.bit_rate = BIT_RATE
        frame = av.AudioFrame.from_ndarray(pcm, format="s16", layout="mono")
        frame.rate = SAMPLE_RATE
        frame.pts = 0
        for packet in stream.encode(frame):
            out.mux(packet)
        for packet in stream.encode(None):
            out.mux(packet)
    os.replace(tmp, path)
