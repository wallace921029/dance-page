from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.book_schemas import (
    AiJobOut,
    AiUnitOut,
    BookAiOut,
    BookAiUpdate,
    CharacterCreate,
    CharacterOut,
    CharacterUpdate,
    JobEnqueuedOut,
    SpreadModeUpdate,
    SpreadOut,
    UnitUpdate,
)
from app.ai.spreads import build_spreads_out, change_spread_mode, unit_to_out
from app.deps import AppSettings, CurrentAdmin, DbSession
from app.models import AiUnit, Book, Character, Job

router = APIRouter(tags=["AI 工作台"])


def _get_book_with_ai(db: Session, book_id: str) -> Book:
    book = db.scalar(
        select(Book)
        .where(Book.id == book_id)
        .options(
            selectinload(Book.pages),
            selectinload(Book.characters),
            selectinload(Book.ai_units),
            selectinload(Book.jobs),
        )
    )
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "绘本不存在")
    return book


def _book_ai_out(book: Book) -> BookAiOut:
    active_jobs = [
        AiJobOut(
            id=j.id,
            type=j.type,
            book_id=j.book_id,
            unit_id=j.unit_id,
            character_id=j.character_id,
            status=j.status,
            progress_done=j.progress_done,
            progress_total=j.progress_total,
            error=j.error,
            created_at=j.created_at,
            started_at=j.started_at,
            finished_at=j.finished_at,
        )
        for j in book.jobs
        if j.status in ("queued", "running")
    ]
    return BookAiOut(
        story=book.story,
        read_order=book.read_order,  # type: ignore[arg-type]
        voice_ready_at=book.voice_ready_at,
        dance_ready_at=book.dance_ready_at,
        characters=[
            CharacterOut(
                id=c.id,
                book_id=c.book_id,
                name=c.name,
                is_narrator=c.is_narrator,
                voice_prompt=c.voice_prompt,
                sort_order=c.sort_order,
            )
            for c in sorted(book.characters, key=lambda c: (not c.is_narrator, c.sort_order))
        ],
        spreads=build_spreads_out(book, book.ai_units),
        running_jobs=active_jobs,
    )


# ---------- 绘本 AI 主接口 ----------


@router.get("/admin/books/{book_id}/ai")
def get_book_ai(book_id: str, _admin: CurrentAdmin, db: DbSession) -> BookAiOut:
    book = _get_book_with_ai(db, book_id)
    return _book_ai_out(book)


@router.patch("/admin/books/{book_id}/ai")
def update_book_ai(
    book_id: str, body: BookAiUpdate, _admin: CurrentAdmin, db: DbSession
) -> BookAiOut:
    book = _get_book_with_ai(db, book_id)
    if body.story is not None:
        book.story = body.story
    if body.read_order is not None:
        book.read_order = body.read_order
    db.commit()
    db.refresh(book)
    return _book_ai_out(book)


@router.post("/admin/books/{book_id}/ai/analyze", status_code=status.HTTP_202_ACCEPTED)
def analyze_book_ai(
    book_id: str, _admin: CurrentAdmin, db: DbSession
) -> JobEnqueuedOut:
    book = _get_book_with_ai(db, book_id)
    if book.processing_status != "ready":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "绘本尚未拆页完成，无法进行故事分析")

    # 检查是否已有进行中的分析任务
    existing = db.scalar(
        select(Job).where(
            Job.book_id == book_id,
            Job.type == "ai_analyze_book",
            Job.status.in_(["queued", "running"]),
        )
    )
    if existing:
        return JobEnqueuedOut(job_id=existing.id, status=existing.status)

    job = Job(type="ai_analyze_book", book_id=book_id)
    db.add(job)
    db.commit()
    return JobEnqueuedOut(job_id=job.id, status="queued")


# ---------- 角色管理 ----------


@router.post(
    "/admin/books/{book_id}/ai/characters",
    status_code=status.HTTP_201_CREATED,
)
def create_character(
    book_id: str, body: CharacterCreate, _admin: CurrentAdmin, db: DbSession
) -> CharacterOut:
    book = _get_book_with_ai(db, book_id)
    sort_order = max((c.sort_order for c in book.characters), default=0) + 1
    char = Character(
        book_id=book.id,
        name=body.name,
        is_narrator=body.is_narrator,
        voice_prompt=body.voice_prompt,
        sort_order=sort_order,
    )
    db.add(char)
    db.commit()
    db.refresh(char)
    return CharacterOut(
        id=char.id,
        book_id=char.book_id,
        name=char.name,
        is_narrator=char.is_narrator,
        voice_prompt=char.voice_prompt,
        sort_order=char.sort_order,
    )


@router.patch("/admin/books/{book_id}/ai/characters/{character_id}")
def update_character(
    book_id: str,
    character_id: int,
    body: CharacterUpdate,
    _admin: CurrentAdmin,
    db: DbSession,
) -> CharacterOut:
    char = db.scalar(
        select(Character).where(Character.id == character_id, Character.book_id == book_id)
    )
    if char is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "角色不存在")

    if body.name is not None:
        char.name = body.name
    if body.is_narrator is not None:
        char.is_narrator = body.is_narrator
    if body.voice_prompt is not None:
        char.voice_prompt = body.voice_prompt
    if body.sort_order is not None:
        char.sort_order = body.sort_order

    db.commit()
    db.refresh(char)
    return CharacterOut(
        id=char.id,
        book_id=char.book_id,
        name=char.name,
        is_narrator=char.is_narrator,
        voice_prompt=char.voice_prompt,
        sort_order=char.sort_order,
    )


@router.delete("/admin/books/{book_id}/ai/characters/{character_id}")
def delete_character(
    book_id: str, character_id: int, _admin: CurrentAdmin, db: DbSession
) -> dict[str, bool]:
    char = db.scalar(
        select(Character).where(Character.id == character_id, Character.book_id == book_id)
    )
    if char is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "角色不存在")

    # 如果有单元的 lines 引用了该角色，将其置为 None
    units = db.scalars(select(AiUnit).where(AiUnit.book_id == book_id)).all()
    for u in units:
        lines = u.lines or []
        changed = False
        new_lines = []
        for line in lines:
            if line.get("character_id") == character_id:
                new_lines.append({**line, "character_id": None})
                changed = True
            else:
                new_lines.append(line)
        if changed:
            u.lines = new_lines

    db.delete(char)
    db.commit()
    return {"ok": True}


# ---------- 开页分别 / 合并 ----------


@router.put("/admin/books/{book_id}/ai/spreads/{first_page}")
def update_spread_mode(
    book_id: str,
    first_page: int,
    body: SpreadModeUpdate,
    _admin: CurrentAdmin,
    db: DbSession,
    settings: AppSettings,
) -> SpreadOut:
    book = _get_book_with_ai(db, book_id)
    try:
        return change_spread_mode(db, settings, book, first_page, body.mode)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e


# ---------- 单元草稿与重做 ----------


@router.patch("/admin/ai/units/{unit_id}")
def update_unit(
    unit_id: str, body: UnitUpdate, _admin: CurrentAdmin, db: DbSession
) -> AiUnitOut:
    unit = db.get(AiUnit, unit_id)
    if unit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "单元不存在")

    if body.lines is not None:
        unit.lines = [line.model_dump() for line in body.lines]
    if body.motion_prompt is not None:
        unit.motion_prompt = body.motion_prompt

    db.commit()
    db.refresh(unit)
    return unit_to_out(unit)


@router.post("/admin/ai/units/{unit_id}/draft", status_code=status.HTTP_202_ACCEPTED)
def draft_unit_ai(
    unit_id: str, _admin: CurrentAdmin, db: DbSession
) -> JobEnqueuedOut:
    unit = db.get(AiUnit, unit_id)
    if unit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "单元不存在")

    existing = db.scalar(
        select(Job).where(
            Job.unit_id == unit_id,
            Job.type == "ai_draft_unit",
            Job.status.in_(["queued", "running"]),
        )
    )
    if existing:
        return JobEnqueuedOut(job_id=existing.id, status=existing.status)

    job = Job(type="ai_draft_unit", book_id=unit.book_id, unit_id=unit_id)
    db.add(job)
    db.commit()
    return JobEnqueuedOut(job_id=job.id, status="queued")
