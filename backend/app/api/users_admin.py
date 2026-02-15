"""Users admin API (admin only)."""
import secrets
import string
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.user import User, UserRole

router = APIRouter()


def _require_admin(current_user: CurrentUser) -> None:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(403, "Admin only")


class AdminCreateUser(BaseModel):
    email: EmailStr
    password: str
    role: str = "user"


def _generate_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


@router.post("/", response_model=dict)
async def create_user(
    data: AdminCreateUser,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Создать пользователя вручную (admin only)."""
    _require_admin(current_user)
    if data.role not in ("admin", "user", "viewer"):
        raise HTTPException(400, "role must be admin, user or viewer")
    r = await db.execute(select(User).where(User.email == data.email))
    if r.scalar_one_or_none():
        raise HTTPException(400, "Email уже зарегистрирован")
    user = User(
        email=data.email,
        password_hash=get_password_hash(data.password),
        role=data.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.post("/generate", response_model=dict)
async def generate_user(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Сгенерировать пользователя с случайным email и паролем (admin only)."""
    _require_admin(current_user)
    for _ in range(10):
        email = f"user_{secrets.token_hex(8)}@dorvey.local"
        r = await db.execute(select(User).where(User.email == email))
        if r.scalar_one_or_none():
            continue
        password = _generate_password()
        user = User(
            email=email,
            password_hash=get_password_hash(password),
            role="user",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return {
            "id": user.id,
            "email": user.email,
            "password": password,
            "role": user.role,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "message": "Сохраните пароль — он больше не покажется",
        }
    raise HTTPException(500, "Не удалось сгенерировать уникальный email")


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
