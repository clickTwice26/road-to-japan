"""Schemas shared across resources."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    per_page: int
    total: int
    pages: int


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str
    message: str
