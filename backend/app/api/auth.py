"""Auth API."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token, decode_token
from app.models.user import User
from app.schemas.auth import UserCreate, UserLogin, TokenResponse, UserResponse, RefreshTokenRequest, TwoFACodeRequest, TwoFASetupResponse, TwoFAVerifyRequest, TwoFAVerifySetupRequest
from app.core.two_fa import generate_secret, get_provisioning_uri, verify_totp
from app.api.deps import CurrentUser
from app.models.user import UserRole

router = APIRouter()


@router.post("/register", response_model=UserResponse)
async def register(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    # First user in system becomes admin
    count = await db.execute(select(User))
    is_first = len(count.scalars().all()) == 0
    user = User(
        email=data.email,
        password_hash=get_password_hash(data.password),
        role=UserRole.ADMIN.value if is_first else UserRole.USER.value,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/bootstrap-admin")
async def bootstrap_admin(
    data: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """One-time: if no admins exist, promote this user to admin (verify password)."""
    r = await db.execute(select(func.count(User.id)).where(User.role == UserRole.ADMIN.value))
    admin_count = r.scalar() or 0
    if admin_count > 0:
        raise HTTPException(403, "Admin already exists")
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    user.role = UserRole.ADMIN.value
    await db.commit()
    return {"status": "ok", "message": "Admin granted"}


@router.post("/login")
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.two_fa_secret:
        return {"requires_2fa": True, "temp_token": create_access_token(user.id), "user_id": user.id}
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/login/2fa", response_model=TokenResponse)
async def login_2fa(data: TwoFAVerifyRequest, db: AsyncSession = Depends(get_db)):
    from app.core.security import decode_token
    payload = decode_token(data.temp_token) if data.temp_token else None
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid or expired temp token")
    user_id = int(payload.get("sub", 0))
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.two_fa_secret or not verify_totp(user.two_fa_secret, data.code):
        raise HTTPException(status_code=401, detail="Invalid 2FA code")
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/2fa/setup", response_model=TwoFASetupResponse)
async def setup_2fa(current_user: CurrentUser):
    if current_user.two_fa_secret:
        raise HTTPException(status_code=400, detail="2FA already enabled")
    secret = generate_secret()
    return TwoFASetupResponse(
        secret=secret,
        provisioning_uri=get_provisioning_uri(current_user.email, secret),
    )


@router.post("/2fa/verify")
async def verify_2fa_enable(data: TwoFAVerifySetupRequest, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    if not verify_totp(data.secret, data.code):
        raise HTTPException(status_code=400, detail="Invalid code")
    current_user.two_fa_secret = data.secret
    await db.commit()
    return {"status": "ok", "message": "2FA enabled"}


@router.post("/2fa/disable")
async def disable_2fa(data: TwoFACodeRequest, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    if not current_user.two_fa_secret or not verify_totp(current_user.two_fa_secret, data.code):
        raise HTTPException(status_code=400, detail="Invalid code")
    current_user.two_fa_secret = None
    await db.commit()
    return {"status": "ok", "message": "2FA disabled"}


@router.get("/me")
async def get_me(current_user: CurrentUser):
    """Current user info (for 2FA status etc.)."""
    return {"id": current_user.id, "email": current_user.email, "has_2fa": bool(current_user.two_fa_secret)}


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )
