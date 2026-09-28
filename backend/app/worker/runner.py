"""Worker：轮询 jobs 表，逐个执行后台任务（第一期只有 PDF 拆页）。"""

import logging
import time

from sqlalchemy import delete, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.ai.providers import ProviderError
from app.ai.settings import load_active_config, load_credentials
from app.ai.spreads import calculate_spread_layout
from app.ai.vision import analyze_book_story, draft_unit_content
from app.books import storage
from app.books.render import PdfOpenError, make_cover, render_pdf
from app.books.storage import delete_ai_unit_files
from app.clock import utcnow
from app.config import Settings
from app.models import AiUnit, Book, Character, Job, Page

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 1.0
DB_NOT_READY_RETRY_SECONDS = 2.0


class Worker:
    def __init__(self, settings: Settings, session_factory: sessionmaker[Session]):
        self.settings = settings
        self.session_factory = session_factory

    def wait_for_database(self) -> None:
        """表结构由 API 进程在启动时迁移；API 还没启动完成时先等待。"""
        while True:
            try:
                with self.session_factory() as db:
                    db.execute(select(Job.id).limit(1))
                return
            except OperationalError:
                logger.info("数据库尚未就绪，等待 API 完成迁移…")
                time.sleep(DB_NOT_READY_RETRY_SECONDS)

    def recover(self) -> None:
        """上次退出时正在执行的任务（进程被杀、服务器重启）重新放回队列。"""
        with self.session_factory() as db:
            result = db.execute(update(Job).where(Job.status == "running").values(status="queued"))
            db.commit()
            if result.rowcount:
                logger.info("已将 %d 个中断的任务重新排队", result.rowcount)

    def claim_next(self) -> int | None:
        with self.session_factory() as db:
            job_id = db.scalar(
                select(Job.id).where(Job.status == "queued").order_by(Job.id).limit(1)
            )
            if job_id is None:
                return None
            # 条件更新：即使将来有多个 Worker，同一任务也只会被领取一次
            result = db.execute(
                update(Job)
                .where(Job.id == job_id, Job.status == "queued")
                .values(status="running", started_at=utcnow(), attempts=Job.attempts + 1)
            )
            db.commit()
            return job_id if result.rowcount == 1 else None

    def run_once(self) -> bool:
        """执行一个排队中的任务。没有任务时返回 False。"""
        job_id = self.claim_next()
        if job_id is None:
            return False
        with self.session_factory() as db:
            job = db.get(Job, job_id)
            job_type, book_id, unit_id = (
                (job.type, job.book_id, job.unit_id) if job else (None, None, None)
            )
        if job_type == "render_pdf" and book_id is not None:
            self.render_book(job_id, book_id)
        elif job_type == "ai_analyze_book" and book_id is not None:
            self.analyze_book(job_id, book_id)
        elif job_type == "ai_draft_unit" and unit_id is not None:
            self.draft_unit(job_id, unit_id)
        elif job_type is not None:
            self._finish(job_id, error=f"未知的任务类型：{job_type}")
        return True

    def run_forever(self) -> None:
        self.wait_for_database()
        self.recover()
        logger.info("Worker 已启动")
        while True:
            try:
                if not self.run_once():
                    time.sleep(POLL_INTERVAL_SECONDS)
            except OperationalError:
                # 数据库短暂被锁等情况，稍后重试
                logger.exception("数据库操作失败，稍后重试")
                time.sleep(POLL_INTERVAL_SECONDS)

    # ---------- PDF 拆页 ----------

    def render_book(self, job_id: int, book_id: str) -> None:
        settings = self.settings
        logger.info("开始拆页 book=%s", book_id)

        def on_progress(done: int, total: int) -> bool:
            with self.session_factory() as db:
                if db.get(Book, book_id) is None:
                    return False  # 绘本已被删除，停止处理
                db.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(progress_done=done, progress_total=total)
                )
                db.commit()
            return True

        try:
            result = render_pdf(
                storage.original_pdf_path(settings, book_id),
                storage.pages_dir(settings, book_id),
                on_progress=on_progress,
            )
        except PdfOpenError as e:
            self._fail(job_id, book_id, str(e))
            return
        except Exception:
            if not self._book_exists(book_id):
                return self._discard(book_id)
            logger.exception("拆页失败 book=%s", book_id)
            self._fail(job_id, book_id, "处理失败，请重新上传；如仍失败请检查 PDF 是否完好")
            return
        if result is None:
            return self._discard(book_id)

        with self.session_factory() as db:
            book = db.get(Book, book_id)
            if book is None:
                return self._discard(book_id)
            if not 0 <= book.cover_page_index < len(result.pages):
                book.cover_page_index = 0
            make_cover(
                storage.page_path(settings, book_id, book.cover_page_index),
                storage.cover_path(settings, book_id),
            )
            db.execute(delete(Page).where(Page.book_id == book_id))
            db.add_all(
                Page(book_id=book_id, page_index=i, width=p.width, height=p.height)
                for i, p in enumerate(result.pages)
            )
            book.page_count = len(result.pages)
            # 管理员在处理完成前已手动设置的版式不覆盖
            book.orientation = book.orientation or result.orientation
            book.spread_start_detected = result.spread_start_page
            book.processing_status = "ready"
            book.processing_error = None
            book.assets_version += 1
            db.commit()
        self._finish(job_id)
        logger.info("拆页完成 book=%s，共 %d 页", book_id, len(result.pages))

    def _book_exists(self, book_id: str) -> bool:
        with self.session_factory() as db:
            return db.get(Book, book_id) is not None

    def _discard(self, book_id: str) -> None:
        """处理过程中绘本被删除：清理 Worker 可能又写出来的文件（任务记录已随绘本级联删除）。"""
        logger.info("绘本已删除，停止处理 book=%s", book_id)
        storage.delete_book_files(self.settings, book_id)

    def _fail(self, job_id: int, book_id: str, message: str) -> None:
        with self.session_factory() as db:
            book = db.get(Book, book_id)
            if book is not None:
                book.processing_status = "failed"
                book.processing_error = message
                db.commit()
        self._finish(job_id, error=message)

    def _finish(self, job_id: int, error: str | None = None) -> None:
        with self.session_factory() as db:
            db.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(status="failed" if error else "done", error=error, finished_at=utcnow())
            )
            db.commit()

    # ---------- AI 故事分析 ----------

    def analyze_book(self, job_id: int, book_id: str) -> None:
        logger.info("开始分析绘本故事 book=%s", book_id)
        with self.session_factory() as db:
            book = db.get(Book, book_id)
            if book is None or book.processing_status != "ready":
                self._finish(job_id, error="绘本未就绪或已被删除")
                return

            config = load_active_config(db, "vision")
            credentials = load_credentials(self.settings, config.provider)
            api_key = credentials.get("api_key")
            if not api_key:
                self._finish(job_id, error=f"未配置 {config.provider} API Key")
                return

            page_paths = [
                storage.page_path(self.settings, book.id, p) for p in range(book.page_count)
            ]
            for p_path in page_paths:
                if not p_path.exists():
                    self._finish(job_id, error=f"页面图片不存在：{p_path.name}")
                    return

            layout = calculate_spread_layout(
                book.page_count, book.orientation, book.spread_start_page
            )
            spreads_to_eval = [
                [item.left_page_index, item.right_page_index]
                for item in layout
                if item.left_page_index is not None and item.right_page_index is not None
            ]
            language = book.language
            read_order = book.read_order

        # 调用视觉大模型
        try:
            result = analyze_book_story(
                page_paths=page_paths,
                language=language,
                spreads_to_evaluate=spreads_to_eval,
                config=config,
                api_key=api_key,
            )
        except ProviderError as e:
            logger.warning("分析绘本失败（服务商错误） book=%s: %s", book_id, e)
            self._finish(job_id, error=str(e))
            return
        except Exception as e:
            logger.exception("分析绘本出现异常 book=%s", book_id)
            self._finish(job_id, error=f"分析失败：{e}")
            return

        with self.session_factory() as db:
            book = db.get(Book, book_id)
            if book is None:
                self._finish(job_id, error="绘本已被删除")
                return

            book.story = result.get("story")

            # 清理现有的单元和文件
            existing_units = db.scalars(select(AiUnit).where(AiUnit.book_id == book_id)).all()
            for u in existing_units:
                delete_ai_unit_files(self.settings, book_id, u.id)
            db.execute(delete(AiUnit).where(AiUnit.book_id == book_id))
            db.execute(delete(Character).where(Character.book_id == book_id))
            db.flush()

            # 创建角色
            char_map: dict[str, Character] = {}
            narrator_char: Character | None = None
            for idx, c_data in enumerate(result.get("characters", [])):
                name = (c_data.get("name") or "").strip()
                if not name:
                    continue
                is_narrator = bool(c_data.get("is_narrator", False))
                char = Character(
                    book_id=book.id,
                    name=name,
                    is_narrator=is_narrator,
                    voice_prompt=c_data.get("voice_prompt"),
                    sort_order=idx,
                )
                db.add(char)
                db.flush()
                char_map[name] = char
                if is_narrator and narrator_char is None:
                    narrator_char = char

            if narrator_char is None and char_map:
                narrator_char = next(iter(char_map.values()))
                narrator_char.is_narrator = True
            elif narrator_char is None:
                narrator_char = Character(
                    book_id=book.id, name="旁白", is_narrator=True, sort_order=0
                )
                db.add(narrator_char)
                db.flush()
                char_map["旁白"] = narrator_char

            def get_char_id(raw_name: str | None) -> int:
                if not raw_name:
                    return narrator_char.id
                raw = raw_name.strip()
                if raw in char_map:
                    return char_map[raw].id
                for k, v in char_map.items():
                    if k in raw or raw in k:
                        return v.id
                return narrator_char.id

            raw_pages = {
                p["page_index"]: p
                for p in result.get("pages", [])
                if isinstance(p, dict) and "page_index" in p
            }

            suggestions_map: dict[tuple[int, int], bool] = {}
            for s in result.get("spread_suggestions", []):
                pages = s.get("pages", [])
                if len(pages) == 2:
                    suggestions_map[(pages[0], pages[1])] = bool(s.get("is_same_scene", False))

            # 创建单元
            for item in layout:
                left_p = item.left_page_index
                right_p = item.right_page_index
                if left_p is None or right_p is None:
                    p_idx = right_p if left_p is None else left_p
                    p_data = raw_pages.get(p_idx, {})
                    lines = [
                        {
                            "character_id": get_char_id(line.get("character")),
                            "text": line.get("text", ""),
                        }
                        for line in p_data.get("lines", [])
                        if isinstance(line, dict)
                    ]
                    unit = AiUnit(
                        book_id=book_id,
                        first_page_index=p_idx,
                        page_count=1,
                        lines=lines,
                        motion_prompt=p_data.get("motion_prompt"),
                    )
                    db.add(unit)
                else:
                    is_same = suggestions_map.get((left_p, right_p), False)
                    p_left_data = raw_pages.get(left_p, {})
                    p_right_data = raw_pages.get(right_p, {})
                    lines_l = [
                        {
                            "character_id": get_char_id(line.get("character")),
                            "text": line.get("text", ""),
                        }
                        for line in p_left_data.get("lines", [])
                        if isinstance(line, dict)
                    ]
                    lines_r = [
                        {
                            "character_id": get_char_id(line.get("character")),
                            "text": line.get("text", ""),
                        }
                        for line in p_right_data.get("lines", [])
                        if isinstance(line, dict)
                    ]
                    prompt_l = p_left_data.get("motion_prompt")
                    prompt_r = p_right_data.get("motion_prompt")

                    if is_same:
                        lines = (
                            lines_r + lines_l if read_order == "right_first" else lines_l + lines_r
                        )
                        prompts = [p for p in (prompt_l, prompt_r) if p]
                        unit = AiUnit(
                            book_id=book_id,
                            first_page_index=left_p,
                            page_count=2,
                            lines=lines,
                            motion_prompt="；".join(prompts) if prompts else None,
                        )
                        db.add(unit)
                    else:
                        unit_l = AiUnit(
                            book_id=book_id,
                            first_page_index=left_p,
                            page_count=1,
                            lines=lines_l,
                            motion_prompt=prompt_l,
                        )
                        unit_r = AiUnit(
                            book_id=book_id,
                            first_page_index=right_p,
                            page_count=1,
                            lines=lines_r,
                            motion_prompt=prompt_r,
                        )
                        db.add(unit_l)
                        db.add(unit_r)

            book.voice_ready_at = None
            book.dance_ready_at = None
            db.commit()

        self._finish(job_id)
        logger.info("绘本分析完成 book=%s", book_id)

    # ---------- 单元草稿重做 ----------

    def draft_unit(self, job_id: int, unit_id: str) -> None:
        logger.info("开始重新生成单元草稿 unit=%s", unit_id)
        with self.session_factory() as db:
            unit = db.get(AiUnit, unit_id)
            if unit is None:
                self._finish(job_id, error="单元不存在")
                return

            book = db.get(Book, unit.book_id)
            if book is None:
                self._finish(job_id, error="绘本不存在")
                return

            config = load_active_config(db, "vision")
            credentials = load_credentials(self.settings, config.provider)
            api_key = credentials.get("api_key")
            if not api_key:
                self._finish(job_id, error=f"未配置 {config.provider} API Key")
                return

            story = book.story
            language = book.language
            characters = [
                {"id": c.id, "name": c.name, "is_narrator": c.is_narrator} for c in book.characters
            ]
            page_indexes = list(
                range(unit.first_page_index, unit.first_page_index + unit.page_count)
            )
            page_paths = [storage.page_path(self.settings, book.id, p) for p in page_indexes]

        try:
            result = draft_unit_content(
                page_paths=page_paths,
                page_indexes=page_indexes,
                story=story,
                characters=characters,
                language=language,
                config=config,
                api_key=api_key,
            )
        except ProviderError as e:
            logger.warning("草稿生成失败（服务商错误） unit=%s: %s", unit_id, e)
            self._finish(job_id, error=str(e))
            return
        except Exception as e:
            logger.exception("草稿生成出现异常 unit=%s", unit_id)
            self._finish(job_id, error=f"生成草稿失败：{e}")
            return

        with self.session_factory() as db:
            unit = db.get(AiUnit, unit_id)
            if unit is None:
                self._finish(job_id, error="单元已被删除")
                return

            chars = db.scalars(select(Character).where(Character.book_id == unit.book_id)).all()
            char_map = {c.name: c.id for c in chars}
            narrator_id = next((c.id for c in chars if c.is_narrator), None)

            def get_cid(name: str | None) -> int | None:
                if not name:
                    return narrator_id
                raw = name.strip()
                if raw in char_map:
                    return char_map[raw]
                for k, v in char_map.items():
                    if k in raw or raw in k:
                        return v
                return narrator_id

            unit.lines = [
                {"character_id": get_cid(line.get("character")), "text": line.get("text", "")}
                for line in result.get("lines", [])
                if isinstance(line, dict)
            ]
            unit.motion_prompt = result.get("motion_prompt")
            db.commit()

        self._finish(job_id)
        logger.info("单元草稿生成完成 unit=%s", unit_id)

