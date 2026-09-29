import re
from pathlib import PurePath

from sqlalchemy.orm import Session

from app.models import AiUnit, Book, Job


def title_from_filename(filename: str) -> str:
    """默认书名取文件名（D16）。

    网上下载的文件名常带 "(作者) (来源站点)" 之类的后缀，由内向外去掉。
    """
    stem = PurePath(filename).stem.strip()
    title = stem
    while (stripped := re.sub(r"\s*[(（][^()（）]*[)）]", "", title)) != title:
        title = stripped
    return (title.strip() or stem or "未命名绘本")[:100]


def enqueue_render(db: Session, book: Book) -> Job:
    job = Job(type="render_pdf", book=book)
    db.add(job)
    return job


def latest_job(book: Book) -> Job | None:
    return max(book.jobs, key=lambda j: j.id, default=None)


def cover_url(book: Book) -> str | None:
    if book.processing_status != "ready":
        return None
    return f"/api/books/{book.id}/cover?v={book.assets_version}"


def page_url(book: Book, index: int) -> str:
    return f"/api/books/{book.id}/pages/{index}?v={book.assets_version}"


def reader_audio_url(book: Book, unit: AiUnit) -> str:
    return f"/api/books/{book.id}/ai/audio/{unit.id}?v={unit.audio_version}"


def video_by_cover(book: Book, unit: AiUnit) -> bool:
    """第 1 页是封面时，这一页由封面动画负责，不单独生成开页动画（A4）。"""
    return book.cover_page_index == 0 and unit.first_page_index == 0


def reader_video_url(book: Book, unit: AiUnit) -> str:
    return f"/api/books/{book.id}/ai/video/{unit.id}?v={unit.video_version}"


def reader_cover_video_url(book: Book) -> str | None:
    """已启用、且与当前封面对得上的封面动画（D96）"""
    frame = f"{book.cover_page_index}:{book.assets_version}"
    if (
        book.cover_video_enabled_at is None
        or book.cover_video_source_hash is None
        or book.cover_video_frame != frame
    ):
        return None
    return f"/api/books/{book.id}/cover-video?v={book.cover_video_version}"
