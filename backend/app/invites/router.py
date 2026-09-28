from datetime import timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.clock import utcnow
from app.deps import CurrentAdmin, DbSession
from app.invites.codes import generate_code
from app.invites.schemas import InviteCreate, InviteOut
from app.models import InviteCode

router = APIRouter(prefix="/admin/invites", tags=["邀请码"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_invite(
    _admin: CurrentAdmin, db: DbSession, body: InviteCreate | None = None
) -> InviteOut:
    body = body or InviteCreate()
    code = generate_code()
    # 31^8 种组合，几乎不会重复
    while db.scalar(select(InviteCode.id).where(InviteCode.code == code)) is not None:
        code = generate_code()
    now = utcnow()
    invite = InviteCode(code=code, created_at=now, expires_at=now + timedelta(days=body.valid_days))
    db.add(invite)
    db.commit()
    return InviteOut.model_validate(invite)


@router.get("")
def list_invites(_admin: CurrentAdmin, db: DbSession) -> list[InviteOut]:
    invites = db.scalars(
        select(InviteCode)
        .options(selectinload(InviteCode.used_by))
        .order_by(InviteCode.created_at.desc(), InviteCode.id.desc())
    )
    return [InviteOut.model_validate(i) for i in invites]


@router.post("/{invite_id}/revoke")
def revoke_invite(invite_id: int, _admin: CurrentAdmin, db: DbSession) -> InviteOut:
    invite = db.get(InviteCode, invite_id)
    if invite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "邀请码不存在")
    if invite.used_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "该邀请码已被使用，无法作废")
    if invite.revoked_at is None:
        invite.revoked_at = utcnow()
        db.commit()
    return InviteOut.model_validate(invite)
