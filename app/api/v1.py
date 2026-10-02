"""Aggregates every module router under /api/v1. Add new modules here."""

from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.catalog.router_admin import router as catalog_admin_router
from app.modules.catalog.router_store import router as catalog_store_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(catalog_store_router)
api_router.include_router(catalog_admin_router)
