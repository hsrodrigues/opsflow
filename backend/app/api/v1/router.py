"""Aggregates every versioned router under a single `api_router`.

Each resource (users, vehicles, ...) gets its own module as its fase is
implemented, registered here with `api_router.include_router(...)`.
"""
from fastapi import APIRouter

from app.api.v1.activation import router as activation_router
from app.api.v1.auth import router as auth_router
from app.api.v1.carriers import router as carriers_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.drivers import router as drivers_router
from app.api.v1.license import router as license_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.occurrences import router as occurrences_router
from app.api.v1.operations import router as operations_router
from app.api.v1.platform import router as platform_router
from app.api.v1.products import router as products_router
from app.api.v1.reports import router as reports_router
from app.api.v1.routes import router as routes_router
from app.api.v1.schedules import router as schedules_router
from app.api.v1.users import router as users_router
from app.api.v1.vehicles import router as vehicles_router

api_router = APIRouter()
api_router.include_router(activation_router)
api_router.include_router(auth_router)
api_router.include_router(carriers_router)
api_router.include_router(dashboard_router)
api_router.include_router(drivers_router)
api_router.include_router(license_router)
api_router.include_router(notifications_router)
api_router.include_router(occurrences_router)
api_router.include_router(operations_router)
api_router.include_router(platform_router)
api_router.include_router(products_router)
api_router.include_router(reports_router)
api_router.include_router(routes_router)
api_router.include_router(schedules_router)
api_router.include_router(users_router)
api_router.include_router(vehicles_router)
