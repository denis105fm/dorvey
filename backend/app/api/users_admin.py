"""Users admin API (admin only)."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.user import User, UserRole

router = APIRouter()


def _require_admin(current_user: CurrentUser) -> None:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(403, "Admin only")


@router.get("/", response_model=List[dict])
async def list_users(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """List all users (admin only)."""
    _require_admin(current_user)
    r = await db.execute(select(User).order_by(User.created_at.desc()))
    users = r.scalars().all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "role": u.role.value if hasattr(u.role, "value") else str(u.role),
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "has_2fa": bool(u.two_fa_secret),
        }
        for u in users
    ]
