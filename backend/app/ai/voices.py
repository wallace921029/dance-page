"""角色音色（docs/06-ai-tech-design.md 第 6.3 节）。

音色与"服务商 + 合成模型"绑定（D78）：后台显示的是当前朗读设置下的那一个，
切换服务商或合成模型后需要重新设计，切回来时旧音色还在。
"""

from collections.abc import Iterable, Sequence
from typing import Literal

from app.ai.settings import CapabilityConfig
from app.models import AiUnit, Character, CharacterVoice, Job

VoiceStatus = Literal["none", "queued", "running", "ready", "failed"]

# 试听句的长度上限（字符）：够听出音色即可，也省合成费用
PREVIEW_TEXT_MAX = 60


def current_voice(character: Character, tts: CapabilityConfig) -> CharacterVoice | None:
    return next(
        (v for v in character.voices if v.provider == tts.provider and v.tts_model == tts.model),
        None,
    )


def voice_state(
    voice: CharacterVoice | None, voice_jobs: Sequence[Job]
) -> tuple[VoiceStatus, str | None]:
    """音色状态：看该角色最近一次音色任务。失败后若还没重新生成成功，显示失败原因。"""
    job = max(voice_jobs, key=lambda j: j.id, default=None)
    if job is not None and job.status in ("queued", "running"):
        return job.status, None  # type: ignore[return-value]
    if (
        job is not None
        and job.status == "failed"
        and (voice is None or job.created_at >= voice.created_at)
    ):
        return "failed", job.error
    return ("ready" if voice else "none"), None


def preview_text(character: Character, units: Iterable[AiUnit], language: str | None) -> str:
    """试听句：优先用角色在书里的第一句台词，听起来最贴近实际朗读。"""
    ordered = sorted(units, key=lambda u: u.first_page_index)
    for unit in ordered:
        for line in unit.lines or []:
            text = (line.get("text") or "").strip()
            if line.get("character_id") == character.id and text:
                return text[:PREVIEW_TEXT_MAX]
    if language == "en":
        return f"Hello, I'm {character.name}. Let's read a story together!"[:PREVIEW_TEXT_MAX]
    return f"你好，我是{character.name}。我们一起来读故事吧！"[:PREVIEW_TEXT_MAX]


def preferred_name(character: Character) -> str:
    """服务商要求音色名只含字母、数字、下划线，且较短。"""
    return f"c{character.id}"
