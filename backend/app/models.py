import uuid
from datetime import datetime
from typing import Literal

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.clock import utcnow
from app.db import Base, UTCDateTime

Role = Literal["admin", "reader"]


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # NOCASE：用户名唯一性不区分大小写（Tom 与 tom 视为同一个）
    username: Mapped[str] = mapped_column(String(collation="NOCASE"), unique=True)
    password_hash: Mapped[str]
    role: Mapped[str] = mapped_column(String(16))
    is_disabled: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    # 最近使用时间：登录时和会话续期时（至多每天一次）更新
    last_active_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class UserSession(Base):
    """登录会话。只保存令牌的哈希，数据库泄露也无法直接冒充登录。"""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    # 上次续期时间
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    user: Mapped[User] = relationship(back_populates="sessions")


class InviteCode(Base):
    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    used_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    used_by: Mapped[User | None] = relationship()

    @property
    def status(self) -> Literal["unused", "used", "expired", "revoked"]:
        if self.used_at is not None:
            return "used"
        if self.revoked_at is not None:
            return "revoked"
        if self.expires_at <= utcnow():
            return "expired"
        return "unused"


class Book(Base):
    __tablename__ = "books"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    title: Mapped[str]
    original_filename: Mapped[str]
    file_size: Mapped[int]
    language: Mapped[str | None] = mapped_column(String(8))  # 'zh' | 'en'
    orientation: Mapped[str | None] = mapped_column(String(16))  # 'portrait' | 'landscape'
    cover_page_index: Mapped[int] = mapped_column(default=0)
    page_count: Mapped[int] = mapped_column(default=0)
    # 跨页大图从第几页开始两两配对（2 或 3，见 D43）：拆页时自动检测，管理员可覆盖
    spread_start_detected: Mapped[int | None]
    spread_start_override: Mapped[int | None]
    visibility: Mapped[str] = mapped_column(String(16), default="listed")  # 'listed' | 'unlisted'
    # 'processing' | 'ready' | 'failed'
    processing_status: Mapped[str] = mapped_column(String(16), default="processing")
    processing_error: Mapped[str | None]
    # 页面图或封面变化时加 1，拼进图片地址让浏览器缓存失效
    assets_version: Mapped[int] = mapped_column(default=0)
    # AI 阶段字段（D67, D69, 06-ai-tech-design 第 4 节）
    story: Mapped[str | None]
    read_order: Mapped[str] = mapped_column(
        String(16), default="left_first", server_default="left_first"
    )  # 'left_first' | 'right_first'
    voice_ready_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    dance_ready_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    pages: Mapped[list["Page"]] = relationship(
        back_populates="book",
        order_by="Page.page_index",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    jobs: Mapped[list["Job"]] = relationship(
        back_populates="book", cascade="all, delete-orphan", passive_deletes=True
    )
    characters: Mapped[list["Character"]] = relationship(
        back_populates="book",
        order_by="Character.sort_order",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    ai_units: Mapped[list["AiUnit"]] = relationship(
        back_populates="book",
        order_by="AiUnit.first_page_index",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def spread_start_page(self) -> int:
        """实际使用的对开配对方式；检测不出时按常规的"从第 2 页开始"。"""
        return self.spread_start_override or self.spread_start_detected or 2


class Character(Base):
    """绘本中的角色（D71、D72）。旁白也作为特殊角色。"""

    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), index=True)
    name: Mapped[str]
    is_narrator: Mapped[bool] = mapped_column(default=False)
    voice_prompt: Mapped[str | None]
    sort_order: Mapped[int] = mapped_column(default=0)

    book: Mapped[Book] = relationship(back_populates="characters")
    voices: Mapped[list["CharacterVoice"]] = relationship(
        back_populates="character", cascade="all, delete-orphan", passive_deletes=True
    )


class CharacterVoice(Base):
    """角色在某服务商 + 合成模型下的音色配置（D78）。"""

    __tablename__ = "character_voices"
    __table_args__ = (UniqueConstraint("character_id", "provider", "tts_model"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(32))
    tts_model: Mapped[str]
    voice_id: Mapped[str]
    voice_prompt_used: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    character: Mapped[Character] = relationship(back_populates="voices")


class AiUnit(Base):
    """生成单元：单页，或合并生成的左右对开两页（D71、D74）。"""

    __tablename__ = "ai_units"
    __table_args__ = (UniqueConstraint("book_id", "first_page_index"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), index=True)
    first_page_index: Mapped[int]
    page_count: Mapped[int] = mapped_column(default=1)  # 1 或 2
    # lines: [{"character_id": int | None, "text": str}]
    lines: Mapped[list[dict]] = mapped_column(JSON, default=list)
    motion_prompt: Mapped[str | None]
    # 'none' | 'queued' | 'running' | 'ready' | 'failed'
    audio_status: Mapped[str] = mapped_column(String(16), default="none")
    video_status: Mapped[str] = mapped_column(String(16), default="none")
    audio_error: Mapped[str | None]
    video_error: Mapped[str | None]
    audio_source_hash: Mapped[str | None]
    video_source_hash: Mapped[str | None]
    audio_duration_ms: Mapped[int | None]
    video_duration_s: Mapped[int | None]
    video_resolution: Mapped[str | None]
    audio_version: Mapped[int] = mapped_column(default=0)
    video_version: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    book: Mapped[Book] = relationship(back_populates="ai_units")


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("book_id", "page_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"))
    page_index: Mapped[int]  # 从 0 开始
    # 渲染后的像素尺寸
    width: Mapped[int]
    height: Mapped[int]

    book: Mapped[Book] = relationship(back_populates="pages")


class Job(Base):
    """后台任务，由 Worker 进程轮询执行。"""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 'render_pdf' | 'ai_analyze_book' | 'ai_draft_unit'
    # 'ai_voice' | 'ai_tts_unit' | 'ai_video_unit'
    type: Mapped[str] = mapped_column(String(32))
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), index=True)
    unit_id: Mapped[str | None] = mapped_column(
        ForeignKey("ai_units.id", ondelete="CASCADE"), index=True
    )
    character_id: Mapped[int | None] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), index=True
    )
    remote_task_id: Mapped[str | None]
    next_poll_at: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)
    # 'queued' | 'running' | 'done' | 'failed'
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    progress_done: Mapped[int] = mapped_column(default=0)
    progress_total: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None]
    attempts: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    book: Mapped[Book] = relationship(back_populates="jobs")


class Favorite(Base):
    """读者收藏的绘本（D55）。按账号保存，换设备登录后仍在。"""

    __tablename__ = "favorites"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    book_id: Mapped[str] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class AiCapability(Base):
    """每种 AI 能力当前使用哪家服务商（D76）。没有记录时默认阿里云百炼。"""

    __tablename__ = "ai_capabilities"

    # 'vision' | 'tts' | 'video'
    capability: Mapped[str] = mapped_column(String(16), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class AiCapabilityConfig(Base):
    """某种能力在某家服务商上的模型设置。两家各存一份，切换服务商后再切回来设置还在。"""

    __tablename__ = "ai_capability_configs"

    capability: Mapped[str] = mapped_column(String(16), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), primary_key=True)
    model: Mapped[str]
    base_url: Mapped[str]
    # 能力相关的其他设置，如视频的默认时长和清晰度（D79）
    options: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
