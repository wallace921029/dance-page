from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import and_, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased, selectinload

from app.books import storage
from app.books.schemas import ReaderBookOut, ShelfBookOut, reader_has_audio, reader_has_video
from app.books.service import reader_cover_video_url
from app.deps import AppSettings, CurrentUser, DbSession
from app.models import AiUnit, Book, Favorite, Page, User

router = APIRouter(prefix="/books", tags=["阅读端"])

# 图片、朗读地址带版本参数（?v=），内容变化时地址随之变化，所以可以长期缓存
IMAGE_CACHE_CONTROL = "private, max-age=31536000, immutable"


def _readable_book(db: Session, book_id: str, user: User, *, with_pages: bool = False) -> Book:
    """读者只能看到已上架且处理完成的绘本；管理员可以预览下架的绘本。"""
    query = select(Book).where(Book.id == book_id, Book.processing_status == "ready")
    if user.role != "admin":
        query = query.where(Book.visibility == "listed")
    if with_pages:
        query = query.options(selectinload(Book.pages), selectinload(Book.ai_units))
    book = db.scalar(query)
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "绘本不存在")
    return book


def _image_response(path: Path) -> FileResponse:
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "图片不存在")
    return FileResponse(
        path, media_type="image/webp", headers={"Cache-Control": IMAGE_CACHE_CONTROL}
    )


@router.get("")
def list_shelf(user: CurrentUser, db: DbSession) -> list[ShelfBookOut]:
    cover = aliased(Page)
    rows = db.execute(
        select(Book, Favorite.created_at, cover.width, cover.height)
        .outerjoin(Favorite, and_(Favorite.book_id == Book.id, Favorite.user_id == user.id))
        .outerjoin(cover, and_(cover.book_id == Book.id, cover.page_index == Book.cover_page_index))
        .where(Book.visibility == "listed", Book.processing_status == "ready")
        .order_by(Book.created_at.desc())
    )
    return [
        ShelfBookOut.of(
            book,
            cover_aspect=width / height if width and height else None,
            favorited_at=favorited_at,
        )
        for book, favorited_at, width, height in rows
    ]


@router.get("/{book_id}")
def get_book(book_id: str, user: CurrentUser, db: DbSession) -> ReaderBookOut:
    book = _readable_book(db, book_id, user, with_pages=True)
    favorite = db.get(Favorite, (user.id, book.id))
    return ReaderBookOut.of(book, favorited_at=favorite.created_at if favorite else None)


@router.put("/{book_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
def add_favorite(book_id: str, user: CurrentUser, db: DbSession) -> None:
    """收藏（重复调用无副作用）。只能收藏自己能看到的绘本。"""
    _readable_book(db, book_id, user)
    if db.get(Favorite, (user.id, book_id)) is not None:
        return
    db.add(Favorite(user_id=user.id, book_id=book_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # 并发的重复请求已经收藏过了


@router.delete("/{book_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(book_id: str, user: CurrentUser, db: DbSession) -> None:
    """取消收藏（重复调用无副作用）。绘本已下架时也可以取消。"""
    db.execute(delete(Favorite).where(Favorite.user_id == user.id, Favorite.book_id == book_id))
    db.commit()


@router.get("/{book_id}/cover", response_class=FileResponse)
def get_cover(book_id: str, user: CurrentUser, db: DbSession, settings: AppSettings):
    _readable_book(db, book_id, user)
    return _image_response(storage.cover_path(settings, book_id))


@router.get("/{book_id}/pages/{index}", response_class=FileResponse)
def get_page(book_id: str, index: int, user: CurrentUser, db: DbSession, settings: AppSettings):
    book = _readable_book(db, book_id, user)
    if not 0 <= index < book.page_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "页面不存在")
    return _image_response(storage.page_path(settings, book_id, index))


@router.get("/{book_id}/ai/audio/{unit_id}", response_class=FileResponse)
def get_unit_audio(
    book_id: str, unit_id: str, user: CurrentUser, db: DbSession, settings: AppSettings
):
    """已确认 Voice Ready 的绘本的单元朗读（docs/06 第 7 节）。"""
    book = _readable_book(db, book_id, user)
    unit = db.get(AiUnit, unit_id)
    if unit is None or unit.book_id != book.id or not reader_has_audio(book, unit):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "朗读不存在")
    path = storage.ai_audio_path(settings, book_id, unit_id)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "朗读不存在")
    return FileResponse(
        path, media_type="audio/mp4", headers={"Cache-Control": IMAGE_CACHE_CONTROL}
    )


@router.get("/{book_id}/cover-video", response_class=FileResponse)
def get_cover_video(book_id: str, user: CurrentUser, db: DbSession, settings: AppSettings):
    """已启用的封面动画（D96）。FileResponse 支持分段请求，iPad Safari 播放视频需要。"""
    book = _readable_book(db, book_id, user)
    path = storage.ai_cover_video_path(settings, book_id)
    if reader_cover_video_url(book) is None or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "封面动画不存在")
    return FileResponse(
        path, media_type="video/mp4", headers={"Cache-Control": IMAGE_CACHE_CONTROL}
    )


@router.get("/{book_id}/ai/video/{unit_id}", response_class=FileResponse)
def get_unit_video(
    book_id: str, unit_id: str, user: CurrentUser, db: DbSession, settings: AppSettings
):
    """已确认 Dance Ready! 的绘本的开页动画（FileResponse 支持 iPad Safari 需要的分段请求）。"""
    book = _readable_book(db, book_id, user)
    unit = db.get(AiUnit, unit_id)
    if unit is None or unit.book_id != book.id or not reader_has_video(book, unit):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "动画不存在")
    path = storage.ai_video_path(settings, book_id, unit_id)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "动画不存在")
    return FileResponse(
        path, media_type="video/mp4", headers={"Cache-Control": IMAGE_CACHE_CONTROL}
    )
