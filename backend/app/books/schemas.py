from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

from app.books.service import (
    cover_url,
    latest_job,
    page_url,
    reader_audio_url,
    reader_cover_video_url,
    reader_video_url,
    video_by_cover,
)
from app.models import AiUnit, Book

Language = Literal["zh", "en"]
Orientation = Literal["portrait", "landscape"]
Visibility = Literal["listed", "unlisted"]
SpreadStartPage = Literal[2, 3]


class PageOut(BaseModel):
    index: int
    width: int
    height: int
    url: str


def _pages(book: Book) -> list[PageOut]:
    return [
        PageOut(
            index=p.page_index, width=p.width, height=p.height, url=page_url(book, p.page_index)
        )
        for p in book.pages
    ]


# ---------- 阅读端 ----------


DEFAULT_COVER_ASPECT = 3 / 4


class ShelfBookOut(BaseModel):
    id: str
    title: str
    orientation: Orientation
    page_count: int
    cover_url: str
    # 封面宽高比：书架据此在图片加载前就排好封面框，收藏按钮贴在封面左上角
    cover_aspect: float
    # 当前用户是否收藏（D55）
    is_favorite: bool
    favorited_at: datetime | None
    # 管理员确认过的 AI 内容（D61、D67）：有朗读的书在书名前显示音乐符号（D70）
    voice_ready: bool
    dance_ready: bool
    # 封面动画（D96）：像魔法报纸上的照片，在书架和阅读页封面上循环播放
    cover_video_url: str | None

    @classmethod
    def of(
        cls, book: Book, *, cover_aspect: float | None, favorited_at: datetime | None
    ) -> "ShelfBookOut":
        return cls(
            id=book.id,
            title=book.title,
            orientation=book.orientation,
            page_count=book.page_count,
            cover_url=cover_url(book),
            cover_aspect=cover_aspect or DEFAULT_COVER_ASPECT,
            is_favorite=favorited_at is not None,
            favorited_at=favorited_at,
            voice_ready=book.voice_ready_at is not None,
            dance_ready=book.dance_ready_at is not None,
            cover_video_url=reader_cover_video_url(book),
        )


class ReaderUnitOut(BaseModel):
    """一个生成单元的朗读 / 动画。只有管理员确认过的那一类产物才会出现（docs/06 第 7 节）。"""

    # 单元覆盖的页码：单页，或合并生成的左右两页
    pages: list[int]
    # 朗读（Voice Ready 后才有）
    audio_url: str | None
    audio_duration_ms: int | None
    # 动画（Dance Ready! 后才有）：合并单元的视频是两页宽，左页放左半边、右页放右半边（D74）
    video_url: str | None


def reader_has_audio(book: Book, unit: AiUnit) -> bool:
    # 开页关闭朗读后读者听不到（D95）
    return (
        book.voice_ready_at is not None
        and unit.audio_source_hash is not None
        and unit.audio_enabled
    )


def reader_has_video(book: Book, unit: AiUnit) -> bool:
    return (
        book.dance_ready_at is not None
        and unit.video_source_hash is not None
        and unit.video_enabled
        and not video_by_cover(book, unit)
    )


def _reader_units(book: Book) -> list[ReaderUnitOut]:
    units = []
    for u in sorted(book.ai_units, key=lambda u: u.first_page_index):
        audio, video = reader_has_audio(book, u), reader_has_video(book, u)
        if audio or video:
            units.append(
                ReaderUnitOut(
                    pages=list(range(u.first_page_index, u.first_page_index + u.page_count)),
                    audio_url=reader_audio_url(book, u) if audio else None,
                    audio_duration_ms=u.audio_duration_ms if audio else None,
                    video_url=reader_video_url(book, u) if video else None,
                )
            )
    return units


class ReaderBookOut(ShelfBookOut):
    language: Language | None
    # 跨页大图从第几页开始两两配对（D43），阅读端对开显示时使用
    spread_start_page: SpreadStartPage
    pages: list[PageOut]
    # 书架封面用的是哪一页；阅读页只在它是第 1 页时播放封面动画
    cover_page_index: int
    # 对开时"分别生成"的两页的朗读顺序（D69）
    read_order: Literal["left_first", "right_first"]
    units: list[ReaderUnitOut]

    @classmethod
    def of(cls, book: Book, *, favorited_at: datetime | None) -> "ReaderBookOut":
        cover = next((p for p in book.pages if p.page_index == book.cover_page_index), None)
        return cls(
            **ShelfBookOut.of(
                book,
                cover_aspect=cover.width / cover.height if cover else None,
                favorited_at=favorited_at,
            ).model_dump(),
            language=book.language,
            spread_start_page=book.spread_start_page,
            pages=_pages(book),
            cover_page_index=book.cover_page_index,
            read_order=book.read_order,
            units=_reader_units(book),
        )


# ---------- 管理端 ----------


class Progress(BaseModel):
    done: int
    total: int


class AdminBookOut(BaseModel):
    id: str
    title: str
    original_filename: str
    file_size: int
    language: Language | None
    orientation: Orientation | None
    cover_page_index: int
    page_count: int
    spread_start_page: SpreadStartPage
    spread_start_detected: SpreadStartPage | None
    spread_start_override: SpreadStartPage | None
    visibility: Visibility
    processing_status: Literal["processing", "ready", "failed"]
    processing_error: str | None
    # 处理中时的拆页进度
    progress: Progress | None
    cover_url: str | None
    cover_video_ready: bool
    dance_ready: bool
    voice_ready: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, book: Book) -> "AdminBookOut":
        job = latest_job(book)
        progress = (
            Progress(done=job.progress_done, total=job.progress_total)
            if job is not None and book.processing_status == "processing"
            else None
        )
        return cls(
            id=book.id,
            title=book.title,
            original_filename=book.original_filename,
            file_size=book.file_size,
            language=book.language,
            orientation=book.orientation,
            cover_page_index=book.cover_page_index,
            page_count=book.page_count,
            spread_start_page=book.spread_start_page,
            spread_start_detected=book.spread_start_detected,
            spread_start_override=book.spread_start_override,
            visibility=book.visibility,
            processing_status=book.processing_status,
            processing_error=book.processing_error,
            progress=progress,
            cover_url=cover_url(book),
            cover_video_ready=book.cover_video_status == "ready",
            dance_ready=book.dance_ready_at is not None,
            voice_ready=book.voice_ready_at is not None,
            created_at=book.created_at,
            updated_at=book.updated_at,
        )


class AdminBookDetailOut(AdminBookOut):
    pages: list[PageOut]

    @classmethod
    def of(cls, book: Book) -> "AdminBookDetailOut":
        return cls(**AdminBookOut.of(book).model_dump(), pages=_pages(book))


class BookUpdate(BaseModel):
    """只修改请求中出现的字段。language / spread_start_override 传 null 表示清空（改回自动）。"""

    title: str | None = None
    language: Language | None = None
    orientation: Orientation | None = None
    cover_page_index: int | None = None
    spread_start_override: SpreadStartPage | None = None
    visibility: Visibility | None = None

    @field_validator("title")
    @classmethod
    def _check_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not 1 <= len(value) <= 100:
            raise ValueError("书名需为 1–100 个字")
        return value
