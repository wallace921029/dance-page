from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


class LineItem(BaseModel):
    character_id: int | None = None
    text: str
    # 大模型在原文之外补充的内容（D93）；原文行为 False
    added: bool = False

    @field_validator("text")
    @classmethod
    def _text(cls, v: str) -> str:
        return v.strip()


class CharacterVoiceOut(BaseModel):
    id: int
    provider: str
    tts_model: str
    voice_prompt_used: str | None
    created_at: datetime
    # 试听音频（WAV），仅后台使用
    preview_url: str


class CharacterOut(BaseModel):
    id: int
    book_id: str
    name: str
    is_narrator: bool
    voice_prompt: str | None
    sort_order: int
    # 当前朗读设置（服务商 + 合成模型）下的音色；没有时为 None（D78）
    voice: CharacterVoiceOut | None
    voice_status: Literal["none", "queued", "running", "ready", "failed"]
    voice_error: str | None
    # 音色描述在生成音色之后又改过，需要重新生成
    voice_outdated: bool


class CharacterCreate(BaseModel):
    name: str
    is_narrator: bool = False
    voice_prompt: str | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("角色名字不能为空")
        return v


class CharacterUpdate(BaseModel):
    name: str | None = None
    is_narrator: bool | None = None
    voice_prompt: str | None = None
    sort_order: int | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("角色名字不能为空")
        return v


class AiUnitOut(BaseModel):
    id: str
    book_id: str
    first_page_index: int
    page_count: int
    lines: list[LineItem]
    motion_prompt: str | None
    audio_enabled: bool
    video_enabled: bool
    audio_status: str
    video_status: str
    audio_error: str | None
    video_error: str | None
    audio_source_hash: str | None
    video_source_hash: str | None
    audio_duration_ms: int | None
    video_duration_s: int | None
    video_resolution: str | None
    audio_version: int
    video_version: int
    created_at: datetime
    updated_at: datetime
    # 已生成的朗读（后台试听）；重新生成期间仍可听旧的
    audio_url: str | None
    # 台词或音色在生成朗读之后改过，需要重新生成
    audio_outdated: bool


class SpreadOut(BaseModel):
    index: int
    left_page_index: int | None
    right_page_index: int | None
    mode: Literal["single", "separate", "merged"]
    # 开页的"朗读""动画"开关（D95）；没有单元时为 True
    audio_enabled: bool
    video_enabled: bool
    units: list[AiUnitOut]


class AiJobOut(BaseModel):
    id: int
    type: str
    book_id: str
    unit_id: str | None
    character_id: int | None
    status: str
    progress_done: int
    progress_total: int
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class CoverVideoOut(BaseModel):
    """封面动画（D96）"""

    motion_prompt: str | None
    status: Literal["none", "queued", "running", "ready", "failed"]
    error: str | None
    # 已生成的视频（后台预览）；重新生成期间仍可看旧的
    video_url: str | None
    resolution: str | None
    # 动作描述、模型或清晰度在生成之后改过
    outdated: bool
    # 生成之后换了封面（或重新拆页），旧动画对不上，读者看不到
    frame_changed: bool
    enabled_at: datetime | None


class BookAiOut(BaseModel):
    story: str | None
    read_order: Literal["left_first", "right_first"]
    voice_ready_at: datetime | None
    dance_ready_at: datetime | None
    characters: list[CharacterOut]
    spreads: list[SpreadOut]
    running_jobs: list[AiJobOut]
    cover: CoverVideoOut


class BookAiUpdate(BaseModel):
    story: str | None = None
    read_order: Literal["left_first", "right_first"] | None = None
    cover_motion_prompt: str | None = None


class SpreadModeUpdate(BaseModel):
    mode: Literal["separate", "merged"]


class SpreadSwitchesUpdate(BaseModel):
    audio_enabled: bool | None = None
    video_enabled: bool | None = None


class UnitUpdate(BaseModel):
    lines: list[LineItem] | None = None
    motion_prompt: str | None = None


class GenerateAllOut(BaseModel):
    # 放进队列的单元数；0 表示都已是最新
    queued: int


class JobEnqueuedOut(BaseModel):
    job_id: int
    status: str
