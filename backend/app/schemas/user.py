import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.user import Role


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    name: str
    role: Role
    created_at: datetime

    model_config = {"from_attributes": True}
