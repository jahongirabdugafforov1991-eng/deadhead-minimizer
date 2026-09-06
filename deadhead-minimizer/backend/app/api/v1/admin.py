"""
One-time database bootstrap endpoint.

Render's free tier doesn't provide shell access, so there's no easy way to run
`psql -f migrations/001_initial_schema.sql` or `python -m scripts.seed_kma_data`
against the live database by hand. This endpoint does both, triggered by a single
authenticated HTTP request instead.

Usage: set ADMIN_BOOTSTRAP_SECRET in the backend service's environment variables
to some random string, then visit (or POST to):
  https://<your-backend-url>/api/v1/admin/bootstrap-db?secret=<that string>

Safe to call more than once — the migration uses IF NOT EXISTS / CREATE OR REPLACE
throughout, and the seed upsert is keyed on (kma_code, equipment_type).

Consider clearing ADMIN_BOOTSTRAP_SECRET (or this whole route) once the pilot's
database is stood up — it can execute arbitrary schema SQL if the secret leaks.
"""

from pathlib import Path

import asyncpg
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from scripts.seed_kma_data import EQUIPMENT_FOR_SEED, SEED_KMAS, UPSERT_SQL, classify

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"


def _asyncpg_dsn(database_url: str) -> str:
    """asyncpg.connect() wants a plain postgres:// / postgresql:// DSN, not the
    SQLAlchemy '+asyncpg' driver suffix our app.core.config normalizes to."""
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _run_migrations() -> list[str]:
    """
    Runs every .sql file in migrations/, in filename order (001_..., 002_..., etc).
    Safe to call repeatedly — each migration is written with IF NOT EXISTS /
    exception-guarded CREATE TYPE, so re-running an already-applied one is a
    no-op rather than an error. This means adding a new numbered migration file
    to the repo is all that's needed — the next bootstrap-db call picks it up.
    """
    if not MIGRATIONS_DIR.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Migrations directory not found at {MIGRATIONS_DIR}",
        )

    applied: list[str] = []
    conn = await asyncpg.connect(dsn=_asyncpg_dsn(settings.DATABASE_URL))
    try:
        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            sql = sql_file.read_text()
            # Simple query protocol runs the whole multi-statement file (including
            # DO $$ ... $$ blocks) in one call — see note in the old single-file
            # version of this function for why SQLAlchemy's execute() can't do this.
            await conn.execute(sql)
            applied.append(sql_file.name)
    finally:
        await conn.close()

    return applied


async def _run_seed() -> int:
    async with AsyncSessionLocal() as session:
        for kma in SEED_KMAS:
            ratio = round(kma.load_count / kma.truck_count, 2)
            await session.execute(
                UPSERT_SQL,
                {
                    "kma_code": kma.kma_code,
                    "kma_name": kma.kma_name,
                    "zip3": kma.zip3,
                    "equipment_type": EQUIPMENT_FOR_SEED.value,
                    "lon": kma.lon,
                    "lat": kma.lat,
                    "load_count": kma.load_count,
                    "truck_count": kma.truck_count,
                    "ratio": ratio,
                    "avg_outbound_rpm": kma.avg_outbound_rpm,
                    "avg_inbound_rpm": kma.avg_inbound_rpm,
                    "zone_classification": classify(ratio),
                },
            )
        await session.commit()
    return len(SEED_KMAS)


@router.post("/bootstrap-db")
async def bootstrap_db(secret: str = Query(..., description="Must match ADMIN_BOOTSTRAP_SECRET")) -> dict:
    if not settings.ADMIN_BOOTSTRAP_SECRET or secret != settings.ADMIN_BOOTSTRAP_SECRET:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing secret")

    applied_migrations = await _run_migrations()
    seeded_count = await _run_seed()

    return {
        "migrations_applied": applied_migrations,
        "seeded_markets": seeded_count,
        "equipment_type": EQUIPMENT_FOR_SEED.value,
    }
