from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


class LineItem(BaseModel):
    character_id: int | None = None
    text: str

    @field_validator("text")
    @classmethod
    def _text(cls, v: str) -> str:
        return v.strip()


class CharacterOut(BaseModel):
    id: int
    book_id: str
    name: str
    is_narrator: bool
    voice_prompt: str | None
    sort_order: int


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


class SpreadOut(BaseModel):
    index: int
    left_page_index: int | None
    right_page_index: int | None
    mode: Literal["single", "separate", "merged"]
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


class BookAiOut(BaseModel):
    story: str | None
    read_order: Literal["left_first", "right_first"]
    voice_ready_at: datetime | None
    dance_ready_at: datetime | None
    characters: list[CharacterOut]
    spreads: list[SpreadOut]
    running_jobs: list[AiJobOut]


class BookAiUpdate(BaseModel):
    story: str | None = None
    read_order: Literal["left_first", "right_first"] | None = None


class SpreadModeUpdate(BaseModel):
    mode: Literal["separate", "merged"]


class UnitUpdate(BaseModel):
    lines: list[LineItem] | None = None
    motion_prompt: str | None = None


class JobEnqueuedOut(BaseModel):
    job_id: int
    status: str
