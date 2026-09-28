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


def ai_dir(settings: Settings, book_id: str) -> Path:
    return book_dir(settings, book_id) / "ai"


def ai_audio_path(settings: Settings, book_id: str, unit_id: str) -> Path:
    return ai_dir(settings, book_id) / "audio" / f"{unit_id}.m4a"


def ai_video_path(settings: Settings, book_id: str, unit_id: str) -> Path:
    return ai_dir(settings, book_id) / "video" / f"{unit_id}.mp4"


def ai_voice_path(settings: Settings, book_id: str, voice_id: int) -> Path:
    return ai_dir(settings, book_id) / "voices" / f"{voice_id}.wav"


def delete_ai_unit_files(settings: Settings, book_id: str, unit_id: str) -> None:
    ai_audio_path(settings, book_id, unit_id).unlink(missing_ok=True)
    ai_video_path(settings, book_id, unit_id).unlink(missing_ok=True)


def delete_ai_voice_files(settings: Settings, book_id: str) -> None:
    shutil.rmtree(ai_dir(settings, book_id) / "voices", ignore_errors=True)


def ai_cover_video_path(settings: Settings, book_id: str) -> Path:
    """封面动画（D96）"""
    return ai_dir(settings, book_id) / "video" / "cover.mp4"
