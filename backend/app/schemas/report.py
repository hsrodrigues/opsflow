"""Schemas for `/api/v1/reports` (seção 17)."""
from datetime import datetime

from pydantic import BaseModel


class ReportPreview(BaseModel):
    title: str
    subtitle: str
    tenant_name: str
    columns: list[str]
    rows: list[list[str]]
    generated_at: datetime
    row_count: int
