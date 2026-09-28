"""Worker：轮询 jobs 表，逐个执行后台任务（PDF 拆页、AI 分析 / 草稿 / 音色 / 朗读 / 视频）。

视频一段要几分钟，拆成"提交"和"查询"两步（docs/06 第 6.7 节）：提交后任务进入 waiting，
Worker 继续处理别的任务，到 next_poll_at 再查询；服务商那边同时最多 MAX_REMOTE_VIDEOS 个。
"""

import logging
import time
from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.ai import audio, providers, speech, video, voices
from app.ai.providers import ProviderError
from app.ai.settings import (
    load_active_config,
    load_config,
    load_credentials,
    missing_credentials,
)
from app.ai.spreads import calculate_spread_layout
from app.ai.vision import analyze_book_story, describe_cover_motion, draft_unit_content
from app.books import storage
from app.books.render import PdfOpenError, make_cover, render_pdf
from app.books.storage import delete_ai_unit_files
from app.clock import utcnow
from app.config import Settings
from app.models import AiUnit, Book, Character, CharacterVoice, Job, Page

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 1.0
DB_NOT_READY_RETRY_SECONDS = 2.0

VIDEO_JOB_TYPES = ("ai_cover_video",)
# 同时在服务商那边排队 / 生成的视频任务上限
MAX_REMOTE_VIDEOS = 3
# 视频任务每隔多久查询一次；查询出错（如网络抖动）也按这个间隔重试
VIDEO_POLL_INTERVAL = timedelta(seconds=15)
# 提交后这么久还没生成好就算失败
VIDEO_MAX_WAIT = timedelta(minutes=30)


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
        """上次退出时正在执行的任务（进程被杀、服务器重启）重新放回队列。
        已提交给服务商的视频任务改为等待查询，不重新提交（避免重复付费）。"""
        with self.session_factory() as db:
            submitted = db.execute(
                update(Job)
                .where(Job.status == "running", Job.remote_task_id.is_not(None))
                .values(status="waiting", next_poll_at=utcnow())
            )
            result = db.execute(update(Job).where(Job.status == "running").values(status="queued"))
            db.commit()
            if result.rowcount or submitted.rowcount:
                logger.info(
                    "已将 %d 个中断的任务重新排队，%d 个视频任务继续查询",
                    result.rowcount,
                    submitted.rowcount,
                )

    def claim_next(self) -> int | None:
        with self.session_factory() as db:
            # 先查询到时间的视频任务
            job_id = db.scalar(
                select(Job.id)
                .where(Job.status == "waiting", Job.next_poll_at <= utcnow())
                .order_by(Job.next_poll_at)
                .limit(1)
            )
            if job_id is not None:
                result = db.execute(
                    update(Job)
                    .where(Job.id == job_id, Job.status == "waiting")
                    .values(status="running")
                )
                db.commit()
                return job_id if result.rowcount == 1 else None

            query = select(Job.id).where(Job.status == "queued")
            remote_videos = db.scalar(
                select(func.count())
                .select_from(Job)
                .where(
                    Job.type.in_(VIDEO_JOB_TYPES),
                    Job.remote_task_id.is_not(None),
                    Job.status.in_(["waiting", "running"]),
                )
            )
            if remote_videos >= MAX_REMOTE_VIDEOS:
                # 服务商那边已经排满，新的视频任务先不提交，其他任务照常执行
                query = query.where(Job.type.not_in(VIDEO_JOB_TYPES))
            job_id = db.scalar(query.order_by(Job.id).limit(1))
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
            job_type, book_id, unit_id, character_id = (
                (job.type, job.book_id, job.unit_id, job.character_id)
                if job
                else (None, None, None, None)
            )
        if job_type == "render_pdf" and book_id is not None:
            self.render_book(job_id, book_id)
        elif job_type == "ai_analyze_book" and book_id is not None:
            self.analyze_book(job_id, book_id)
        elif job_type == "ai_draft_unit" and unit_id is not None:
            self.draft_unit(job_id, unit_id)
        elif job_type == "ai_voice" and character_id is not None:
            self.design_voice(job_id, character_id)
        elif job_type == "ai_tts_unit" and unit_id is not None:
            self.synthesize_unit(job_id, unit_id)
        elif job_type == "ai_cover_video" and book_id is not None:
            self.cover_video(job_id, book_id)
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
            storage.delete_ai_voice_files(self.settings, book_id)

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
                            "added": line.get("added") is True,
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
                            "added": line.get("added") is True,
                        }
                        for line in p_left_data.get("lines", [])
                        if isinstance(line, dict)
                    ]
                    lines_r = [
                        {
                            "character_id": get_char_id(line.get("character")),
                            "text": line.get("text", ""),
                            "added": line.get("added") is True,
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
            # 封面动画的动作描述草稿（D96）：管理员填过的不覆盖
            cover_motion = raw_pages.get(book.cover_page_index, {}).get("motion_prompt")
            if not book.cover_motion_prompt and cover_motion:
                book.cover_motion_prompt = cover_motion
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
                {
                    "character_id": get_cid(line.get("character")),
                    "text": line.get("text", ""),
                    "added": line.get("added") is True,
                }
                for line in result.get("lines", [])
                if isinstance(line, dict)
            ]
            unit.motion_prompt = result.get("motion_prompt")
            db.commit()

        self._finish(job_id)
        logger.info("单元草稿生成完成 unit=%s", unit_id)

    # ---------- 角色音色 ----------

    def design_voice(self, job_id: int, character_id: int) -> None:
        logger.info("开始设计角色音色 character=%s", character_id)
        with self.session_factory() as db:
            character = db.get(Character, character_id)
            if character is None:
                self._finish(job_id, error="角色已被删除")
                return
            book = db.get(Book, character.book_id)
            assert book is not None  # 角色随绘本级联删除
            prompt = (character.voice_prompt or "").strip()
            if not prompt:
                self._finish(job_id, error=f"请先填写角色「{character.name}」的音色描述")
                return

            config = load_active_config(db, "tts")
            credentials = load_credentials(self.settings, config.provider)
            missing = missing_credentials("tts", config.provider, credentials)
            if missing:
                self._finish(job_id, error=f"请先在 .env 中设置 {'、'.join(missing)}")
                return
            text = voices.preview_text(character, book.ai_units, book.language)
            name = voices.preferred_name(character)
            book_id = book.id

        try:
            designed = providers.design_voice(
                config, credentials, prompt=prompt, preview_text=text, name=name
            )
        except ProviderError as e:
            logger.warning("音色设计失败 character=%s: %s", character_id, e)
            self._finish(job_id, error=str(e))
            return
        except Exception as e:
            logger.exception("音色设计出现异常 character=%s", character_id)
            self._finish(job_id, error=f"音色设计失败：{e}")
            return

        with self.session_factory() as db:
            character = db.get(Character, character_id)
            if character is None:
                self._finish(job_id, error="角色已被删除")
                return
            # 同一"服务商 + 合成模型"只保留一个音色：新音色换新记录（试听地址随之变化）
            old = db.scalar(
                select(CharacterVoice).where(
                    CharacterVoice.character_id == character_id,
                    CharacterVoice.provider == config.provider,
                    CharacterVoice.tts_model == config.model,
                )
            )
            if old is not None:
                storage.ai_voice_path(self.settings, book_id, old.id).unlink(missing_ok=True)
                db.delete(old)
                db.flush()
            voice = CharacterVoice(
                character_id=character_id,
                provider=config.provider,
                tts_model=config.model,
                voice_id=designed.voice_id,
                voice_prompt_used=prompt,
            )
            db.add(voice)
            db.flush()
            path = storage.ai_voice_path(self.settings, book_id, voice.id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(designed.preview_wav)
            db.commit()

        self._finish(job_id)
        logger.info("音色设计完成 character=%s voice=%s", character_id, designed.voice_id)

    # ---------- 单元朗读 ----------

    def synthesize_unit(self, job_id: int, unit_id: str) -> None:
        """逐行用说话人的音色合成，行间停顿后拼成一段 .m4a（docs/06 第 6.4 节）。"""
        logger.info("开始生成朗读 unit=%s", unit_id)
        with self.session_factory() as db:
            unit = db.get(AiUnit, unit_id)
            if unit is None:
                self._finish(job_id, error="单元已被删除")
                return
            if not unit.audio_enabled:
                # 排队期间开页关闭了朗读（D95）：不生成，保留原来的朗读
                unit.audio_status = "ready" if unit.audio_source_hash else "none"
                db.commit()
                self._finish(job_id)
                return
            book = db.get(Book, unit.book_id)
            assert book is not None  # 单元随绘本级联删除
            config = load_active_config(db, "tts")
            credentials = load_credentials(self.settings, config.provider)
            missing = missing_credentials("tts", config.provider, credentials)
            try:
                if missing:
                    raise speech.SpeechError(f"请先在 .env 中设置 {'、'.join(missing)}")
                lines = speech.resolve_lines(unit, book.characters, config)
                speech.check_lines(lines)
            except speech.SpeechError as e:
                self._fail_audio(job_id, unit_id, str(e))
                return
            unit.audio_status = "running"
            unit.audio_error = None
            db.commit()
            book_id = book.id

        try:
            segments = []
            for i, line in enumerate(lines, start=1):
                assert line.voice_id is not None  # check_lines 已确认
                data = providers.synthesize(
                    config, credentials, text=line.text, voice=line.voice_id
                )
                try:
                    segments.append(audio.decode_to_pcm(data))
                except audio.AudioDecodeError as e:
                    raise ProviderError(f"第 {i} 行的合成音频无法解码") from e
            pcm = audio.join_lines(segments)
        except ProviderError as e:
            logger.warning("朗读生成失败 unit=%s: %s", unit_id, e)
            self._fail_audio(job_id, unit_id, str(e))
            return
        except Exception as e:
            logger.exception("朗读生成出现异常 unit=%s", unit_id)
            self._fail_audio(job_id, unit_id, f"朗读生成失败：{e}")
            return

        with self.session_factory() as db:
            unit = db.get(AiUnit, unit_id)
            if unit is None:
                self._finish(job_id, error="单元已被删除")
                return
            audio.write_m4a(pcm, storage.ai_audio_path(self.settings, book_id, unit_id))
            unit.audio_status = "ready"
            unit.audio_error = None
            # 记录生成时用的台词和音色；之后草稿或音色改了，就显示"需要重新生成"
            unit.audio_source_hash = speech.source_hash(lines, config)
            unit.audio_duration_ms = audio.duration_ms(pcm)
            unit.audio_version += 1
            db.commit()

        self._finish(job_id)
        logger.info("朗读生成完成 unit=%s，共 %d 行", unit_id, len(lines))

    def _fail_audio(self, job_id: int, unit_id: str, message: str) -> None:
        with self.session_factory() as db:
            unit = db.get(AiUnit, unit_id)
            if unit is not None:
                unit.audio_status = "failed"
                unit.audio_error = message
                db.commit()
        self._finish(job_id, error=message)

    # ---------- 封面动画（D96） ----------

    def cover_video(self, job_id: int, book_id: str) -> None:
        with self.session_factory() as db:
            job = db.get(Job, job_id)
            submitted = job is not None and job.remote_task_id is not None
        if submitted:
            self._poll_cover_video(job_id, book_id)
        else:
            self._submit_cover_video(job_id, book_id)

    def _submit_cover_video(self, job_id: int, book_id: str) -> None:
        logger.info("提交封面动画 book=%s", book_id)
        with self.session_factory() as db:
            book = db.get(Book, book_id)
            if book is None or book.processing_status != "ready":
                self._finish(job_id, error="绘本未就绪或已被删除")
                return
            config = load_active_config(db, "video")
            credentials = load_credentials(self.settings, config.provider)
            missing = missing_credentials("video", config.provider, credentials)
            if missing:
                self._fail_cover(job_id, book_id, f"请先在 .env 中设置 {'、'.join(missing)}")
                return
            frame_path = storage.page_path(self.settings, book_id, book.cover_page_index)
            motion = (book.cover_motion_prompt or "").strip()
            story = book.story
            names = [c.name for c in book.characters if not c.is_narrator]
            book.cover_video_status = "running"
            book.cover_video_error = None
            db.commit()

        # 没填动作描述：先让视觉模型看封面写一句具体的（笼统的描述模型容易不动，D96），存为草稿
        if not motion:
            try:
                motion = self._write_cover_motion(frame_path, story, names)
            except ProviderError as e:
                self._fail_cover(job_id, book_id, f"自动写动作描述失败：{e}。请手动填写后再生成")
                return
            with self.session_factory() as db:
                book = db.get(Book, book_id)
                if book is None:
                    return
                if not book.cover_motion_prompt:
                    book.cover_motion_prompt = motion
                    db.commit()

        with self.session_factory() as db:
            book = db.get(Book, book_id)
            if book is None:
                return
            resolution = str(config.options.get("resolution") or "720P")
            payload = {
                "provider": config.provider,
                "resolution": resolution,
                "source_hash": video.cover_source_hash(motion, config, resolution),
                "frame": video.cover_frame_key(book.cover_page_index, book.assets_version),
            }
        prompt = video.cover_prompt(motion)

        try:
            task_id = providers.submit_video(
                config,
                credentials,
                frame_jpeg=video.frame_jpeg(frame_path),
                prompt=prompt,
                negative_prompt=video.NEGATIVE_PROMPT,
                resolution=resolution,
            )
        except ProviderError as e:
            logger.warning("封面动画提交失败 book=%s: %s", book_id, e)
            self._fail_cover(job_id, book_id, str(e))
            return
        except Exception as e:
            logger.exception("封面动画提交出现异常 book=%s", book_id)
            self._fail_cover(job_id, book_id, f"提交失败：{e}")
            return

        with self.session_factory() as db:
            db.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(
                    status="waiting",
                    remote_task_id=task_id,
                    payload=payload,
                    next_poll_at=utcnow() + VIDEO_POLL_INTERVAL,
                )
            )
            db.commit()
        logger.info("封面动画已提交 book=%s task=%s", book_id, task_id)

    def _poll_cover_video(self, job_id: int, book_id: str) -> None:
        with self.session_factory() as db:
            job = db.get(Job, job_id)
            if job is None or db.get(Book, book_id) is None:
                return  # 绘本已删除，任务随之删除
            payload = dict(job.payload or {})
            task_id = job.remote_task_id
            started_at = job.started_at or utcnow()
            # 用提交时的服务商查询（中途在 AI 配置里换了服务商也不影响）
            config = load_config(db, "video", payload.get("provider", "dashscope"))
            credentials = load_credentials(self.settings, config.provider)

        timed_out = utcnow() - started_at > VIDEO_MAX_WAIT
        try:
            result = providers.poll_video(config, credentials, task_id)
        except ProviderError as e:
            if timed_out:
                self._fail_cover(job_id, book_id, f"生成超时：{e}")
            else:
                logger.warning("查询封面动画出错，稍后重试 book=%s: %s", book_id, e)
                self._wait_again(job_id)
            return

        if result.status == "running":
            if timed_out:
                self._fail_cover(job_id, book_id, "生成超时，请重试")
            else:
                self._wait_again(job_id)
            return
        if result.status == "failed":
            self._fail_cover(job_id, book_id, result.error or "生成失败")
            return

        try:
            assert result.video_url is not None
            data = providers.download(result.video_url)
            path = storage.ai_cover_video_path(self.settings, book_id)
            video.save_video(data, path)
        except (ProviderError, video.VideoProcessError) as e:
            self._fail_cover(job_id, book_id, str(e))
            return

        with self.session_factory() as db:
            book = db.get(Book, book_id)
            if book is None:
                return
            book.cover_video_status = "ready"
            book.cover_video_error = None
            book.cover_video_version += 1
            book.cover_video_source_hash = payload.get("source_hash")
            book.cover_video_frame = payload.get("frame")
            book.cover_video_resolution = payload.get("resolution")
            db.commit()
        self._finish(job_id)
        logger.info("封面动画生成完成 book=%s", book_id)

    def _wait_again(self, job_id: int) -> None:
        with self.session_factory() as db:
            db.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(status="waiting", next_poll_at=utcnow() + VIDEO_POLL_INTERVAL)
            )
            db.commit()

    def _fail_cover(self, job_id: int, book_id: str, message: str) -> None:
        with self.session_factory() as db:
            book = db.get(Book, book_id)
            if book is not None:
                book.cover_video_status = "failed"
                book.cover_video_error = message
                db.commit()
        self._finish(job_id, error=message)

    def _write_cover_motion(self, cover_path: Path, story: str | None, names: list[str]) -> str:
        with self.session_factory() as db:
            config = load_active_config(db, "vision")
        api_key = load_credentials(self.settings, config.provider).get("api_key")
        if not api_key:
            raise ProviderError("故事与台词识别的服务商没有设置 API Key")
        return describe_cover_motion(cover_path, story, names, config, api_key)
