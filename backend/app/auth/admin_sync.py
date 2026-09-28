import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password, verify_password
from app.auth.sessions import delete_user_sessions
from app.config import Settings
from app.models import User

logger = logging.getLogger(__name__)


def sync_admin(db: Session, settings: Settings) -> None:
    """启动时把环境变量里的管理员账号密码同步到 users 表，保证有且只有一个管理员。"""
    conflict = db.scalar(
        select(User).where(User.username == settings.admin_username, User.role != "admin")
    )
    if conflict is not None:
        raise RuntimeError(
            f"ADMIN_USERNAME={settings.admin_username!r} 与已有读者的用户名冲突，"
            "请换一个管理员用户名"
        )

    admin = db.scalar(select(User).where(User.role == "admin"))
    if admin is None:
        db.add(
            User(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                role="admin",
            )
        )
        logger.info("已创建管理员 %s", settings.admin_username)
    else:
        if admin.username != settings.admin_username:
            logger.info("管理员用户名 %s → %s", admin.username, settings.admin_username)
            admin.username = settings.admin_username
        if not verify_password(admin.password_hash, settings.admin_password):
            admin.password_hash = hash_password(settings.admin_password)
            # 改了密码，之前登录的设备全部需要重新登录
            delete_user_sessions(db, admin.id)
            logger.info("管理员密码已更新")
        admin.is_disabled = False
    db.commit()
