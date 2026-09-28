"""绘本文件的存放位置：DATA_DIR/books/{book_id}/ 下的原始 PDF、页面图和封面。"""

import shutil
from pathlib import Path

from app.books.render import page_file_name
from app.config import Settings


def book_dir(settings: Settings, book_id: str) -> Path:
    return settings.data_dir / "books" / book_id


def original_pdf_path(settings: Settings, book_id: str) -> Path:
    return book_dir(settings, book_id) / "original.pdf"


def pages_dir(settings: Settings, book_id: str) -> Path:
    return book_dir(settings, book_id) / "pages"


def page_path(settings: Settings, book_id: str, index: int) -> Path:
    return pages_dir(settings, book_id) / page_file_name(index)


def cover_path(settings: Settings, book_id: str) -> Path:
    return book_dir(settings, book_id) / "cover.webp"


def delete_book_files(settings: Settings, book_id: str) -> None:
    shutil.rmtree(book_dir(settings, book_id), ignore_errors=True)
