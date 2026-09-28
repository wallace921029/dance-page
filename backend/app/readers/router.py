from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password
from app.auth.sessions import delete_user_sessions
from app.deps import CurrentAdmin, DbSession
from app.models import User
from app.readers.schemas import PasswordReset, ReaderOut, ReaderUpdate

router = APIRouter(prefix="/admin/readers", tags=["读者"])


def _get_reader(db: Session, reader_id: int) -> User:
    reader = db.get(User, reader_id)
    if reader is None or reader.role != "reader":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "读者不存在")
    return reader


@router.get("")
def list_readers(_admin: CurrentAdmin, db: DbSession) -> list[ReaderOut]:
    readers = db.scalars(
        select(User).where(User.role == "reader").order_by(User.created_at.desc(), User.id.desc())
    )
    return [ReaderOut.model_validate(r) for r in readers]


@router.patch("/{reader_id}")
def update_reader(
    reader_id: int, body: ReaderUpdate, _admin: CurrentAdmin, db: DbSession
) -> ReaderOut:
    reader = _get_reader(db, reader_id)
    reader.is_disabled = body.is_disabled
    if body.is_disabled:
        # 立即登出该读者的所有设备
        delete_user_sessions(db, reader.id)
    db.commit()
    return ReaderOut.model_validate(reader)


@router.post("/{reader_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    reader_id: int, body: PasswordReset, _admin: CurrentAdmin, db: DbSession
) -> None:
    reader = _get_reader(db, reader_id)
    reader.password_hash = hash_password(body.password)
    # 重置密码后，所有设备都需要用新密码重新登录
    delete_user_sessions(db, reader.id)
    db.commit()
