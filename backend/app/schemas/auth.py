import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["EMPLOYEE", "APPROVER", "PROCUREMENT", "ADMIN", "TECH_ADMIN"]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class DepartmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    department: DepartmentRead
    roles: list[Role]
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: UserRead


class UserCreate(BaseModel):
    username: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_.-]{2,63}$")
    password: str = Field(min_length=12, max_length=128)
    department_id: uuid.UUID
    roles: set[Role] = Field(min_length=1)
