from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.books import storage
from app.books.schemas import ReaderBookOut, ShelfBookOut
from app.deps import AppSettings, CurrentUser, DbSession
from app.models import Book, User

router = APIRouter(prefix="/books", tags=["阅读端"])

# 图片地址带版本参数（?v=），内容变化时地址随之变化，所以可以长期缓存
IMAGE_CACHE_CONTROL = "private, max-age=31536000, immutable"


def _readable_book(db: Session, book_id: str, user: User, *, with_pages: bool = False) -> Book:
    """读者只能看到已上架且处理完成的绘本；管理员可以预览下架的绘本。"""
    query = select(Book).where(Book.id == book_id, Book.processing_status == "ready")
    if user.role != "admin":
        query = query.where(Book.visibility == "listed")
    if with_pages:
        query = query.options(selectinload(Book.pages))
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
def list_shelf(_user: CurrentUser, db: DbSession) -> list[ShelfBookOut]:
    books = db.scalars(
        select(Book)
        .where(Book.visibility == "listed", Book.processing_status == "ready")
        .order_by(Book.created_at.desc())
    )
    return [ShelfBookOut.of(b) for b in books]


@router.get("/{book_id}")
def get_book(book_id: str, user: CurrentUser, db: DbSession) -> ReaderBookOut:
    return ReaderBookOut.of(_readable_book(db, book_id, user, with_pages=True))


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
