from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.clock import utcnow
from app.invites.codes import normalize_code
from app.models import InviteCode, User

_UNUSABLE_MESSAGES = {
    "used": "该邀请码已被使用",
    "expired": "该邀请码已过期，请联系管理员重新获取",
    "revoked": "该邀请码已作废，请联系管理员重新获取",
}


def find_usable_invite(db: Session, raw_code: str) -> InviteCode:
    invite = db.scalar(select(InviteCode).where(InviteCode.code == normalize_code(raw_code)))
    if invite is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "邀请码不存在，请检查是否输入正确")
    if invite.status != "unused":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, _UNUSABLE_MESSAGES[invite.status])
    return invite


def claim_invite(db: Session, invite: InviteCode, user: User) -> None:
    """把邀请码标记为已被该用户使用。条件更新保证并发注册时一码只能用一次。"""
    result = db.execute(
        update(InviteCode)
        .where(
            InviteCode.id == invite.id,
            InviteCode.used_at.is_(None),
            InviteCode.revoked_at.is_(None),
        )
        .values(used_at=utcnow(), used_by_user_id=user.id)
    )
    if result.rowcount != 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, _UNUSABLE_MESSAGES["used"])
