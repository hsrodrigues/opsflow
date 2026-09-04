"""Aggregates every versioned router under a single `api_router`.

Each resource (auth, users, vehicles, ...) gets its own module starting in
Fase 2/3, registered here with `api_router.include_router(...)`. Kept empty
of business routers in Fase 1 on purpose — there is no service/schema layer
yet for them to call into.
"""
from fastapi import APIRouter

api_router = APIRouter()
