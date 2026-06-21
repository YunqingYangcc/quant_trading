"""赛道量化系统 — FastAPI 入口"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.database import ensure_database_ready

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Track Quant API...")
    if settings.DB_AUTO_CREATE_SCHEMA:
        await ensure_database_ready()
        logger.info("Database tables created/verified")
    logger.info("Application ready")
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="Quant Trading API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from app.api.track import router as track_router
from app.api.ml_api import router as ml_router
from app.api.backtest_api import router as backtest_router
from app.api.dashboard_api import router as dashboard_router

app.include_router(track_router, prefix="/api/v1/track", tags=["赛道管理"])
app.include_router(ml_router, prefix="/api/v1", tags=["AI 模型"])
app.include_router(backtest_router, prefix="/api/v1", tags=["回测对比与学习"])
app.include_router(dashboard_router, prefix="/api/v1", tags=["Dashboard 决策建议"])


@app.get("/", summary="根路由")
async def root():
    return {"service": "Quant Trading API", "version": "1.0.0", "status": "running"}


@app.get("/health", summary="健康检查")
async def health():
    from sqlalchemy import text
    from app.db.database import async_session_maker
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
    return {"status": "healthy" if db_status == "connected" else "degraded", "database": db_status}
