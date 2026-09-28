import re
from pathlib import PurePath

from sqlalchemy.orm import Session

from app.models import Book, Job


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
