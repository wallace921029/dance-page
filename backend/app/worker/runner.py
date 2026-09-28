"""Worker：轮询 jobs 表，逐个执行后台任务（第一期只有 PDF 拆页）。"""

import logging
import time

from sqlalchemy import delete, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.books import storage
from app.books.render import PdfOpenError, make_cover, render_pdf
from app.clock import utcnow
from app.config import Settings
from app.models import Book, Job, Page

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
            job_type, book_id = (job.type, job.book_id) if job else (None, None)
        if job_type == "render_pdf" and book_id is not None:
            self.render_book(job_id, book_id)
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
