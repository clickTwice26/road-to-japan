"""Schemas shared across resources."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)


class Page[T](BaseModel):
    items: list[T]
    page: int
    per_page: int
    total: int
    pages: int


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str
    message: str
