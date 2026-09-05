from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.manual_update import router as manual_update_router
from app.api.v1.routing import router as routing_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Dynamic Deadhead Minimizer API",
    description="Load-to-truck heat mapping, relocation vector analysis, and triangulation loop routing.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routing_router, prefix="/api/v1")
app.include_router(manual_update_router, prefix="/api/v1")


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
