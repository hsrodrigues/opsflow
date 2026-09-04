"""Aggregates every versioned router under a single `api_router`.

Each resource (users, vehicles, ...) gets its own module as its fase is
implemented, registered here with `api_router.include_router(...)`.
"""
from fastapi import APIRouter

from app.api.v1.auth import router as auth_router

api_router = APIRouter()
api_router.include_router(auth_router)
