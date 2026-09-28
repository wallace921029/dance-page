from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

from app.books.service import cover_url, latest_job, page_url
from app.models import Book

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


class ShelfBookOut(BaseModel):
    id: str
    title: str
    orientation: Orientation
    page_count: int
    cover_url: str

    @classmethod
    def of(cls, book: Book) -> "ShelfBookOut":
        return cls(
            id=book.id,
            title=book.title,
            orientation=book.orientation,
            page_count=book.page_count,
            cover_url=cover_url(book),
        )


class ReaderBookOut(ShelfBookOut):
    language: Language | None
    # 跨页大图从第几页开始两两配对（D43），阅读端对开显示时使用
    spread_start_page: SpreadStartPage
    pages: list[PageOut]

    @classmethod
    def of(cls, book: Book) -> "ReaderBookOut":
        return cls(
            **ShelfBookOut.of(book).model_dump(),
            language=book.language,
            spread_start_page=book.spread_start_page,
            pages=_pages(book),
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
