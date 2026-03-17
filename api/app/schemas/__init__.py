from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class MessageResponse(BaseModel):
    message: str


class Pagination(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserBase(BaseModel):
    username: str
    is_active: bool = True
    is_public: bool = True

    model_config = ConfigDict(from_attributes=True)


class UserRead(UserBase):
    id: str

    model_config = ConfigDict(from_attributes=True)
