from collections.abc import Sequence
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
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
    CharacterVoiceOut,
    GenerateAllOut,
    JobEnqueuedOut,
    SpreadModeUpdate,
    SpreadOut,
    SpreadSwitchesUpdate,
    UnitUpdate,
)
from app.ai.settings import (
    CapabilityConfig,
    load_active_config,
    load_credentials,
    missing_credentials,
)
from app.ai.speech import SpeechError, check_lines, resolve_lines, source_hash
from app.ai.spreads import (
    SpreadLayoutItem,
    build_spreads_out,
    change_spread_mode,
    find_spread,
    unit_to_out,
    units_in_spread,
)
from app.ai.voices import current_voice, voice_state
from app.books import storage
from app.clock import utcnow
from app.deps import AppSettings, CurrentAdmin, DbSession
from app.models import AiUnit, Book, Character, CharacterVoice, Job

router = APIRouter(tags=["AI 工作台"])

# 试听地址带版本参数，重新生成后地址随之变化，所以可以长期缓存
MEDIA_CACHE_CONTROL = "private, max-age=31536000, immutable"


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


def _character_out(
    character: Character, tts: CapabilityConfig, voice_jobs: Sequence[Job]
) -> CharacterOut:
    voice = current_voice(character, tts)
    status_, error = voice_state(voice, voice_jobs)
    return CharacterOut(
        id=character.id,
        book_id=character.book_id,
        name=character.name,
        is_narrator=character.is_narrator,
        voice_prompt=character.voice_prompt,
        sort_order=character.sort_order,
        voice=CharacterVoiceOut(
            id=voice.id,
            provider=voice.provider,
            tts_model=voice.tts_model,
            voice_prompt_used=voice.voice_prompt_used,
            created_at=voice.created_at,
            # SQLite 会复用刚删除的记录 ID，所以用服务商的音色 ID 作版本参数
            preview_url=(
                f"/api/admin/books/{character.book_id}/ai/voices/{voice.id}"
                f"?v={quote(voice.voice_id)}"
            ),
        )
        if voice
        else None,
        voice_status=status_,
        voice_error=error,
        voice_outdated=voice is not None
        and (voice.voice_prompt_used or "") != (character.voice_prompt or "").strip(),
    )


def _single_character_out(db: Session, character: Character) -> CharacterOut:
    voice_jobs = db.scalars(
        select(Job).where(Job.character_id == character.id, Job.type == "ai_voice")
    ).all()
    return _character_out(character, load_active_config(db, "tts"), voice_jobs)


def _current_audio_hash(unit: AiUnit, characters: Sequence[Character], tts: CapabilityConfig):
    try:
        return source_hash(resolve_lines(unit, characters, tts), tts)
    except SpeechError:
        return None


def _book_ai_out(db: Session, book: Book) -> BookAiOut:
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
    tts = load_active_config(db, "tts")
    return BookAiOut(
        story=book.story,
        read_order=book.read_order,  # type: ignore[arg-type]
        voice_ready_at=book.voice_ready_at,
        dance_ready_at=book.dance_ready_at,
        characters=[
            _character_out(
                c, tts, [j for j in book.jobs if j.type == "ai_voice" and j.character_id == c.id]
            )
            for c in sorted(book.characters, key=lambda c: (not c.is_narrator, c.sort_order))
        ],
        spreads=build_spreads_out(
            book,
            book.ai_units,
            {u.id: _current_audio_hash(u, book.characters, tts) for u in book.ai_units},
        ),
        running_jobs=active_jobs,
    )


# ---------- 绘本 AI 主接口 ----------


@router.get("/admin/books/{book_id}/ai")
def get_book_ai(book_id: str, _admin: CurrentAdmin, db: DbSession) -> BookAiOut:
    book = _get_book_with_ai(db, book_id)
    return _book_ai_out(db, book)


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
    return _book_ai_out(db, book)


@router.post("/admin/books/{book_id}/ai/analyze", status_code=status.HTTP_202_ACCEPTED)
def analyze_book_ai(book_id: str, _admin: CurrentAdmin, db: DbSession) -> JobEnqueuedOut:
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


# ---------- Voice Ready ----------


@router.put("/admin/books/{book_id}/ai/voice-ready")
def confirm_voice_ready(book_id: str, _admin: CurrentAdmin, db: DbSession) -> BookAiOut:
    """确认 Voice Ready：读者从此能听到已生成的朗读（D61）。没生成朗读的页面不显示朗读按钮。"""
    book = _get_book_with_ai(db, book_id)
    if not any(u.audio_source_hash is not None and u.audio_enabled for u in book.ai_units):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "还没有生成任何朗读")
    if book.voice_ready_at is None:
        book.voice_ready_at = utcnow()
        db.commit()
    return _book_ai_out(db, book)


@router.delete("/admin/books/{book_id}/ai/voice-ready")
def cancel_voice_ready(book_id: str, _admin: CurrentAdmin, db: DbSession) -> BookAiOut:
    book = _get_book_with_ai(db, book_id)
    book.voice_ready_at = None
    db.commit()
    return _book_ai_out(db, book)


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
    return _single_character_out(db, char)


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
    return _single_character_out(db, char)


@router.delete("/admin/books/{book_id}/ai/characters/{character_id}")
def delete_character(
    book_id: str, character_id: int, _admin: CurrentAdmin, db: DbSession, settings: AppSettings
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

    for voice in char.voices:
        storage.ai_voice_path(settings, book_id, voice.id).unlink(missing_ok=True)
    db.delete(char)
    db.commit()
    return {"ok": True}


# ---------- 角色音色 ----------


@router.post(
    "/admin/books/{book_id}/ai/characters/{character_id}/voice",
    status_code=status.HTTP_202_ACCEPTED,
)
def design_character_voice(
    book_id: str, character_id: int, _admin: CurrentAdmin, db: DbSession, settings: AppSettings
) -> JobEnqueuedOut:
    """按角色的音色描述，为当前朗读设置设计音色（重新生成会替换原来的音色）。"""
    char = db.scalar(
        select(Character).where(Character.id == character_id, Character.book_id == book_id)
    )
    if char is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "角色不存在")
    if not (char.voice_prompt or "").strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先填写该角色的音色描述")
    tts = load_active_config(db, "tts")
    missing = missing_credentials("tts", tts.provider, load_credentials(settings, tts.provider))
    if missing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"请先在 .env 中设置 {'、'.join(missing)}")

    existing = db.scalar(
        select(Job).where(
            Job.character_id == character_id,
            Job.type == "ai_voice",
            Job.status.in_(["queued", "running"]),
        )
    )
    if existing:
        return JobEnqueuedOut(job_id=existing.id, status=existing.status)

    job = Job(type="ai_voice", book_id=book_id, character_id=character_id)
    db.add(job)
    db.commit()
    return JobEnqueuedOut(job_id=job.id, status="queued")


@router.get("/admin/books/{book_id}/ai/voices/{voice_id}", response_class=FileResponse)
def get_voice_preview(
    book_id: str, voice_id: int, _admin: CurrentAdmin, db: DbSession, settings: AppSettings
):
    voice = db.scalar(
        select(CharacterVoice)
        .join(Character)
        .where(CharacterVoice.id == voice_id, Character.book_id == book_id)
    )
    path = storage.ai_voice_path(settings, book_id, voice_id)
    if voice is None or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "试听音频不存在")
    return FileResponse(
        path, media_type="audio/wav", headers={"Cache-Control": MEDIA_CACHE_CONTROL}
    )


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


def _spread_or_404(book: Book, first_page: int) -> tuple[SpreadLayoutItem, list[AiUnit]]:
    spread = find_spread(book, first_page)
    if spread is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "开页不存在")
    units = units_in_spread(book, spread)
    if not units:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "这个开页还没有生成单元，请先分析整本故事")
    return spread, units


@router.patch("/admin/books/{book_id}/ai/spreads/{first_page}")
def update_spread_switches(
    book_id: str,
    first_page: int,
    body: SpreadSwitchesUpdate,
    _admin: CurrentAdmin,
    db: DbSession,
) -> SpreadOut:
    """开页的"朗读""动画"开关（D95）：关闭后一键生成跳过、阅读端也不播放，已生成的文件保留。"""
    book = _get_book_with_ai(db, book_id)
    spread, units = _spread_or_404(book, first_page)
    for unit in units:
        if body.audio_enabled is not None:
            unit.audio_enabled = body.audio_enabled
            if not body.audio_enabled:
                _cancel_queued_audio(db, unit)
        if body.video_enabled is not None:
            unit.video_enabled = body.video_enabled
    db.commit()
    return next(s for s in _book_ai_out(db, book).spreads if s.index == spread.index)


def _cancel_queued_audio(db: Session, unit: AiUnit) -> None:
    """撤掉还没开始的朗读任务；正在合成的由 Worker 发现开关已关后放弃。"""
    queued = db.scalars(
        select(Job).where(Job.unit_id == unit.id, Job.type == "ai_tts_unit", Job.status == "queued")
    ).all()
    for job in queued:
        db.delete(job)
    if queued and unit.audio_status == "queued":
        unit.audio_status = "ready" if unit.audio_source_hash else "none"


# ---------- 单元草稿与重做 ----------


@router.patch("/admin/ai/units/{unit_id}")
def update_unit(unit_id: str, body: UnitUpdate, _admin: CurrentAdmin, db: DbSession) -> AiUnitOut:
    unit = db.get(AiUnit, unit_id)
    if unit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "单元不存在")

    if body.lines is not None:
        unit.lines = [line.model_dump() for line in body.lines]
    if body.motion_prompt is not None:
        unit.motion_prompt = body.motion_prompt

    db.commit()
    db.refresh(unit)
    return unit_to_out(
        unit, _current_audio_hash(unit, unit.book.characters, load_active_config(db, "tts"))
    )


@router.post("/admin/ai/units/{unit_id}/draft", status_code=status.HTTP_202_ACCEPTED)
def draft_unit_ai(unit_id: str, _admin: CurrentAdmin, db: DbSession) -> JobEnqueuedOut:
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


# ---------- 单元朗读 ----------


def _check_tts_credentials(db: Session, settings: AppSettings) -> CapabilityConfig:
    tts = load_active_config(db, "tts")
    missing = missing_credentials("tts", tts.provider, load_credentials(settings, tts.provider))
    if missing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"请先在 .env 中设置 {'、'.join(missing)}")
    return tts


def _active_job(db: Session, unit_id: str, job_type: str) -> Job | None:
    return db.scalar(
        select(Job).where(
            Job.unit_id == unit_id,
            Job.type == job_type,
            Job.status.in_(["queued", "running"]),
        )
    )


def _enqueue_audio(db: Session, unit: AiUnit) -> Job:
    unit.audio_status = "queued"
    unit.audio_error = None
    job = Job(type="ai_tts_unit", book_id=unit.book_id, unit_id=unit.id)
    db.add(job)
    return job


@router.post("/admin/ai/units/{unit_id}/audio", status_code=status.HTTP_202_ACCEPTED)
def generate_unit_audio(
    unit_id: str, _admin: CurrentAdmin, db: DbSession, settings: AppSettings
) -> JobEnqueuedOut:
    """生成（或重新生成）该单元的朗读。"""
    unit = db.get(AiUnit, unit_id)
    if unit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "单元不存在")
    if not unit.audio_enabled:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "这个开页已关闭朗读")
    tts = _check_tts_credentials(db, settings)
    try:
        check_lines(resolve_lines(unit, unit.book.characters, tts))
    except SpeechError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e

    existing = _active_job(db, unit_id, "ai_tts_unit")
    if existing:
        return JobEnqueuedOut(job_id=existing.id, status=existing.status)
    job = _enqueue_audio(db, unit)
    db.commit()
    return JobEnqueuedOut(job_id=job.id, status="queued")


@router.post("/admin/books/{book_id}/ai/generate-all", status_code=status.HTTP_202_ACCEPTED)
def generate_all(
    book_id: str,
    _admin: CurrentAdmin,
    db: DbSession,
    settings: AppSettings,
    # 动画（video）在 A4 加入
    type: Literal["audio"] = Query(),
) -> GenerateAllOut:
    """把需要生成的单元（未生成、失败或台词 / 音色已改）都放进队列（docs/06 第 6.6 节）。"""
    book = _get_book_with_ai(db, book_id)
    tts = _check_tts_credentials(db, settings)

    units = sorted(book.ai_units, key=lambda u: u.first_page_index)
    return GenerateAllOut(queued=_enqueue_audios(db, book, units, tts, only_needed=True))


def _enqueue_audios(
    db: Session, book: Book, units: list[AiUnit], tts: CapabilityConfig, *, only_needed: bool
) -> int:
    """把单元放进朗读队列，返回放入的数量。跳过关闭了朗读（D95）、没有台词、已在队列里的；
    only_needed 时也跳过已是最新的。有说话人缺音色时一个都不放，报出角色名。"""
    todo: list[AiUnit] = []
    missing_voices: list[str] = []
    for unit in units:
        if not unit.audio_enabled:
            continue
        lines = resolve_lines(unit, book.characters, tts)
        if not lines or _active_job(db, unit.id, "ai_tts_unit"):
            continue
        current = source_hash(lines, tts)
        up_to_date = unit.audio_status == "ready" and current == unit.audio_source_hash
        if only_needed and current is not None and up_to_date:
            continue
        missing_voices += [line.character_name for line in lines if line.voice_id is None]
        todo.append(unit)

    if missing_voices:
        names = "」「".join(dict.fromkeys(missing_voices))
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"请先为角色「{names}」生成音色")
    for unit in todo:
        _enqueue_audio(db, unit)
    db.commit()
    return len(todo)


@router.post(
    "/admin/books/{book_id}/ai/spreads/{first_page}/audio", status_code=status.HTTP_202_ACCEPTED
)
def generate_spread_audio(
    book_id: str, first_page: int, _admin: CurrentAdmin, db: DbSession, settings: AppSettings
) -> GenerateAllOut:
    """生成（或重新生成）这个开页里所有单元的朗读。"""
    book = _get_book_with_ai(db, book_id)
    _, units = _spread_or_404(book, first_page)
    if not any(u.audio_enabled for u in units):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "这个开页已关闭朗读")
    tts = _check_tts_credentials(db, settings)
    queued = _enqueue_audios(db, book, units, tts, only_needed=False)
    if not queued and not any(_active_job(db, u.id, "ai_tts_unit") for u in units):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "这个开页没有台词，不需要朗读")
    return GenerateAllOut(queued=queued)


@router.get("/admin/ai/units/{unit_id}/audio", response_class=FileResponse)
def get_unit_audio(unit_id: str, _admin: CurrentAdmin, db: DbSession, settings: AppSettings):
    unit = db.get(AiUnit, unit_id)
    if unit is None or unit.audio_source_hash is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "朗读音频不存在")
    path = storage.ai_audio_path(settings, unit.book_id, unit_id)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "朗读音频不存在")
    return FileResponse(
        path, media_type="audio/mp4", headers={"Cache-Control": MEDIA_CACHE_CONTROL}
    )
