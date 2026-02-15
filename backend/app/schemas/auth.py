"""Auth schemas."""

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: str  # str чтобы принять admin@dorvey.local и др. нестандартные домены
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TwoFACodeRequest(BaseModel):
    code: str


class TwoFAVerifyRequest(BaseModel):
    code: str
    temp_token: str


class TwoFAVerifySetupRequest(BaseModel):
    secret: str
    code: str


class TwoFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class UserResponse(BaseModel):
    id: int
    email: str
    role: str

    class Config:
        from_attributes = True
