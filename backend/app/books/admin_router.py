import shutil

from fastapi import APIRouter, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.books import storage
from app.books.render import make_cover
from app.books.schemas import AdminBookDetailOut, AdminBookOut, BookUpdate
from app.books.service import enqueue_render, title_from_filename
from app.deps import AppSettings, CurrentStaff, DbSession
from app.models import Book

router = APIRouter(prefix="/admin/books", tags=["绘本管理"])

COPY_CHUNK_SIZE = 1024 * 1024


def _get_book(db: Session, book_id: str) -> Book:
    book = db.scalar(
        select(Book)
        .where(Book.id == book_id)
        .options(selectinload(Book.pages), selectinload(Book.jobs))
    )
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "绘本不存在")
    return book


@router.post("", status_code=status.HTTP_201_CREATED)
def upload_book(
    file: UploadFile, _admin: CurrentStaff, db: DbSession, settings: AppSettings
) -> AdminBookOut:
    filename = file.filename or "未命名.pdf"
    book = Book(title=title_from_filename(filename), original_filename=filename, file_size=0)
    db.add(book)
    db.flush()  # 生成 book.id

    # 上传内容已由框架暂存在临时文件里，这里分块复制，不把整个文件读进内存
    dest = storage.original_pdf_path(settings, book.id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        size = 0
        with dest.open("wb") as out:
            while chunk := file.file.read(COPY_CHUNK_SIZE):
                if size == 0 and not chunk.startswith(b"%PDF-"):
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, "只支持 PDF 文件")
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(
                        status.HTTP_413_CONTENT_TOO_LARGE,
                        f"文件超过 {settings.max_upload_mb}MB 上限",
                    )
                out.write(chunk)
        if size == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "文件是空的")
    except BaseException:
        db.rollback()
        storage.delete_book_files(settings, book.id)
        raise

    book.file_size = size
    enqueue_render(db, book)
    db.commit()
    return AdminBookOut.of(_get_book(db, book.id))


@router.get("")
def list_books(_admin: CurrentStaff, db: DbSession) -> list[AdminBookOut]:
    books = db.scalars(
        select(Book).options(selectinload(Book.jobs)).order_by(Book.created_at.desc())
    )
    return [AdminBookOut.of(b) for b in books]


@router.get("/{book_id}")
def get_book(book_id: str, _admin: CurrentStaff, db: DbSession) -> AdminBookDetailOut:
    return AdminBookDetailOut.of(_get_book(db, book_id))


@router.patch("/{book_id}")
def update_book(
    book_id: str, body: BookUpdate, _admin: CurrentStaff, db: DbSession, settings: AppSettings
) -> AdminBookDetailOut:
    book = _get_book(db, book_id)
    fields = body.model_fields_set

    if "cover_page_index" in fields and body.cover_page_index != book.cover_page_index:
        if book.processing_status != "ready":
            raise HTTPException(status.HTTP_409_CONFLICT, "绘本处理完成后才能更换封面")
        index = body.cover_page_index
        if index is None or not 0 <= index < book.page_count:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "封面页超出范围")
        make_cover(
            storage.page_path(settings, book.id, index), storage.cover_path(settings, book.id)
        )
        book.cover_page_index = index
        book.assets_version += 1

    # 这几项不允许清空，传 null 视为不修改
    for name in ("title", "orientation", "visibility"):
        if name in fields and getattr(body, name) is not None:
            setattr(book, name, getattr(body, name))
    # 这两项传 null 表示清空（语言未设置 / 对开配对改回自动检测）
    for name in ("language", "spread_start_override"):
        if name in fields:
            setattr(book, name, getattr(body, name))

    db.commit()
    return AdminBookDetailOut.of(_get_book(db, book.id))


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(book_id: str, _admin: CurrentStaff, db: DbSession, settings: AppSettings) -> None:
    book = _get_book(db, book_id)
    db.delete(book)
    db.commit()
    # 处理中的 Worker 会在下一页发现绘本已删除并停止
    shutil.rmtree(storage.book_dir(settings, book_id), ignore_errors=True)
