from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import DbSession

router = APIRouter(tags=["system"])


@router.get("/health", summary="Liveness probe (process is up)")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe (database reachable)")
async def ready(db: DbSession) -> dict[str, str]:
    await db.execute(text("SELECT 1"))
    return {"status": "ready"}
