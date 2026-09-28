"""单元朗读：把台词解析成"说话人音色 + 文本"，以及判断朗读是否需要重新生成。"""

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass

from app.ai.settings import CapabilityConfig
from app.ai.voices import current_voice
from app.models import AiUnit, Character


@dataclass
class SpeechLine:
    character_name: str
    text: str
    # 说话人在当前朗读设置下的音色；None 表示还没生成
    voice_id: str | None


class SpeechError(ValueError):
    """无法生成朗读的原因（中文，给管理员看）。"""


def resolve_lines(
    unit: AiUnit, characters: Iterable[Character], tts: CapabilityConfig
) -> list[SpeechLine]:
    """单元里要朗读的台词。没有指定说话人的行由旁白读；空行跳过。"""
    chars = list(characters)
    by_id = {c.id: c for c in chars}
    narrator = next((c for c in chars if c.is_narrator), None)
    lines: list[SpeechLine] = []
    for line in unit.lines or []:
        text = (line.get("text") or "").strip()
        if not text:
            continue
        character = by_id.get(line.get("character_id")) or narrator
        if character is None:
            raise SpeechError("有台词没有指定说话人，请先添加旁白角色")
        voice = current_voice(character, tts)
        lines.append(SpeechLine(character.name, text, voice.voice_id if voice else None))
    return lines


def check_lines(lines: list[SpeechLine]) -> None:
    if not lines:
        raise SpeechError("该单元没有台词，不需要朗读")
    missing = list(dict.fromkeys(line.character_name for line in lines if line.voice_id is None))
    if missing:
        raise SpeechError(f"请先为角色「{'」「'.join(missing)}」生成音色")


def source_hash(lines: list[SpeechLine], tts: CapabilityConfig) -> str | None:
    """台词 + 音色的指纹；与生成时记录的不一致，就需要重新生成（docs/06 第 4 节）。"""
    if not lines or any(line.voice_id is None for line in lines):
        return None
    payload = {
        "provider": tts.provider,
        "model": tts.model,
        "lines": [[line.voice_id, line.text] for line in lines],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def audio_outdated(unit: AiUnit, current_hash: str | None) -> bool:
    return unit.audio_source_hash is not None and unit.audio_source_hash != current_hash
