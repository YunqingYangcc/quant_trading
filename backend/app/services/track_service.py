"""
赛道管理服务层.

管理赛道 CRUD、自选股池、数据打标签（shift(1) 防未来泄露）。
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.db.database import async_session_maker
from app.db.sql_repository import SQLRepository
from app.models.track import (
    FeatureBlackList,
    FeatureWhiteList,
    Track,
    TrackDataCache,
    TrackStock,
    track_stock,
)
from app.schemas.track import (
    TrackCreate,
    TrackListResponse,
    TrackResponse,
    TrackStockInfo,
    TrackUpdate,
)

logger = logging.getLogger(__name__)

DATAS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "datas"
TRACKS_DIR = DATAS_DIR / "tracks"


class TrackService:
    """赛道管理服务"""

    def __init__(self):
        self.track_repo = SQLRepository(Track)
        self.stock_repo = SQLRepository(TrackStock)

    # ── 赛道 CRUD ──────────────────────────────

    async def create_track(self, data: TrackCreate) -> Track:
        track = Track(
            name=data.name,
            display_name=data.display_name,
            description=data.description,
            sort_order=data.sort_order,
        )
        async with async_session_maker() as session:
            session.add(track)
            await session.commit()
            await session.refresh(track)
        return track

    async def list_tracks(self) -> list[dict[str, Any]]:
        """列出所有赛道（含股票列表和数量）"""
        async with async_session_maker() as session:
            from sqlalchemy import func, select

            result = await session.execute(
                select(
                    Track,
                    func.count(track_stock.c.stock_code).label("stock_count"),
                ).outerjoin(
                    track_stock, Track.id == track_stock.c.track_id
                ).group_by(Track.id).order_by(Track.sort_order)
            )
            rows = result.all()

            # 获取所有 track_stock 关联（含股票信息）
            track_ids = [t.id for t, _ in rows]
            all_stocks = {}
            if track_ids:
                stocks_result = await session.execute(
                    select(TrackStock, track_stock.c.track_id)
                    .join(track_stock, TrackStock.code == track_stock.c.stock_code)
                    .where(track_stock.c.track_id.in_(track_ids))
                )
                for stock, tid in stocks_result.all():
                    all_stocks.setdefault(tid, []).append({
                        "code": stock.code,
                        "name": stock.name,
                        "ipo_date": stock.ipo_date,
                        "status": stock.status,
                    })

            tracks = []
            for track, count in rows:
                tracks.append({
                    "id": track.id,
                    "name": track.name,
                    "display_name": track.display_name,
                    "description": track.description,
                    "sort_order": track.sort_order,
                    "is_active": track.is_active,
                    "stock_count": count,
                    "stocks": all_stocks.get(track.id, []),
                    "created_at": track.created_at,
                })
            return tracks

    async def get_track(self, track_id: str) -> dict[str, Any] | None:
        async with async_session_maker() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(Track).where(Track.id == track_id)
            )
            track = result.scalars().first()
            if not track:
                return None

            # 获取关联股票
            stocks = await session.execute(
                select(TrackStock)
                .join(track_stock)
                .where(track_stock.c.track_id == track_id)
            )
            stock_list = [
                {"code": s.code, "name": s.name, "ipo_date": s.ipo_date, "status": s.status}
                for s in stocks.scalars().all()
            ]

            return {
                "id": track.id,
                "name": track.name,
                "display_name": track.display_name,
                "description": track.description,
                "sort_order": track.sort_order,
                "is_active": track.is_active,
                "stock_count": len(stock_list),
                "stocks": stock_list,
                "created_at": track.created_at,
            }

    async def update_track(self, track_id: str, data: TrackUpdate) -> bool:
        async with async_session_maker() as session:
            from sqlalchemy import select

            result = await session.execute(select(Track).where(Track.id == track_id))
            track = result.scalars().first()
            if not track:
                return False

            update_data = data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(track, key, value)
            await session.commit()
            return True

    async def delete_track(self, track_id: str) -> bool:
        async with async_session_maker() as session:
            from sqlalchemy import delete, select

            track = await session.get(Track, track_id)
            if not track:
                return False
            # 删除关联
            await session.execute(
                delete(track_stock).where(track_stock.c.track_id == track_id)
            )
            await session.delete(track)
            await session.commit()
            return True

    # ── 股票管理 ──────────────────────────────

    async def assign_stock_to_tracks(
        self, stock_code: str, stock_name: str, track_ids: list[str]
    ) -> bool:
        """将股票加入指定赛道"""
        async with async_session_maker() as session:
            from sqlalchemy import select

            # 确保股票存在
            result = await session.execute(
                select(TrackStock).where(TrackStock.code == stock_code)
            )
            stock = result.scalars().first()
            if not stock:
                stock = TrackStock(code=stock_code, name=stock_name)
                session.add(stock)
                await session.flush()

            # 清除旧关联
            from app.models.track import track_stock as ts

            await session.execute(
                ts.delete().where(ts.c.stock_code == stock_code)
            )

            # 建立新关联
            for tid in track_ids:
                track = await session.get(Track, tid)
                if track:
                    await session.execute(
                        ts.insert().values(track_id=tid, stock_code=stock_code)
                    )

            await session.commit()
            return True

    async def list_stocks(self, track_id: str | None = None) -> list[dict[str, Any]]:
        """列出自选股，可按赛道筛选"""
        async with async_session_maker() as session:
            from sqlalchemy import select

            if track_id:
                result = await session.execute(
                    select(TrackStock)
                    .join(track_stock)
                    .where(track_stock.c.track_id == track_id)
                )
            else:
                result = await session.execute(select(TrackStock))

            stocks = result.scalars().all()
            return [
                {
                    "code": s.code,
                    "name": s.name,
                    "ipo_date": s.ipo_date,
                    "status": s.status,
                    "created_at": s.created_at,
                }
                for s in stocks
            ]

    # ── CSV 数据导入 ──────────────────────────

    async def import_csv_to_cache(
        self, stock_code: str, df: pd.DataFrame | None = None
    ) -> int:
        """从 CSV 文件导入数据到 TrackDataCache"""
        if df is None:
            # 从文件读取
            csv_path = self._find_csv(stock_code)
            if not csv_path:
                logger.warning("CSV not found: %s", stock_code)
                return 0
            df = pd.read_csv(csv_path)
            df.columns = [c.strip().lower() for c in df.columns]

        required = {"date", "open", "high", "low", "close", "volume", "amount"}
        if not required.issubset(set(df.columns)):
            logger.warning("CSV columns mismatch for %s: got %s", stock_code, list(df.columns))
            return 0

        async with async_session_maker() as session:
            from sqlalchemy import delete, select

            # 清除旧数据
            await session.execute(
                delete(TrackDataCache).where(TrackDataCache.stock_code == stock_code)
            )

            count = 0
            for _, row in df.iterrows():
                try:
                    record = TrackDataCache(
                        stock_code=stock_code,
                        trade_date=str(row["date"]),
                        open_px=float(row["open"]),
                        high_px=float(row["high"]),
                        low_px=float(row["low"]),
                        close_px=float(row["close"]),
                        volume=float(row["volume"]),
                        amount=float(row["amount"]),
                    )
                    session.add(record)
                    count += 1
                except (ValueError, KeyError):
                    continue

            if count > 0:
                await session.commit()
            return count

    # ── 数据打标签（shift(1) 防未来泄露）──

    async def generate_labels(self, stock_code: str) -> list[dict[str, Any]]:
        """生成带标签的数据（shift(1) 防止未来函数）"""
        async with async_session_maker() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(TrackDataCache)
                .where(TrackDataCache.stock_code == stock_code)
                .order_by(TrackDataCache.trade_date)
            )
            records = result.scalars().all()

        if len(records) < 21:
            return []

        # 转 DataFrame
        import pandas as pd

        df = pd.DataFrame(
            [
                {
                    "stock_code": r.stock_code,
                    "trade_date": r.trade_date,
                    "close_px": r.close_px,
                    "open_px": r.open_px,
                    "high_px": r.high_px,
                    "low_px": r.low_px,
                    "volume": r.volume,
                    "amount": r.amount,
                }
                for r in records
            ]
        )

        # 计算未来收益（shift -1 = 防未来泄露：用 t 日数据预测 t+1 日收益）
        df["fwd_1d_return"] = df["close_px"].pct_change(-1).shift(1)  # t 日对齐 t+1 收益
        df["fwd_5d_return"] = df["close_px"].pct_change(-5).shift(1)
        df["fwd_20d_return"] = df["close_px"].pct_change(-20).shift(1)

        # 赛道中位数收益（用于计算超额收益）
        # 需要在服务层外部计算，这里只做个股标签

        # 标记涨跌停
        df["is_limit_up"] = (df["close_px"] >= df["high_px"] * 0.999) & (
            df["close_px"] > df["open_px"]
        )
        df["is_limit_down"] = (df["close_px"] <= df["low_px"] * 1.001) & (
            df["close_px"] < df["open_px"]
        )

        # 去除 NaN
        df = df.dropna(subset=["fwd_1d_return"])

        # 替换 NaN/inf 为 None（JSON 兼容）
        records = df.to_dict("records")
        for r in records:
            for k, v in r.items():
                if v is not None and not isinstance(v, (int, float, str, bool)):
                    r[k] = None
                elif isinstance(v, float):
                    if v != v or v == float("inf") or v == float("-inf"):
                        r[k] = None

        return records

    # ── 因子黑/白名单管理 ──────────────────────

    async def add_to_whitelist(
        self,
        factor_name: str,
        factor_type: str,
        category: str | None = None,
        ic_mean: float = 0,
        ir: float = 0,
        lgb_importance: float = 0,
    ) -> FeatureWhiteList:
        async with async_session_maker() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(FeatureWhiteList).where(FeatureWhiteList.factor_name == factor_name)
            )
            existing = result.scalars().first()
            if existing:
                existing.ic_mean = ic_mean
                existing.ir = ir
                existing.lgb_importance = lgb_importance
                await session.commit()
                return existing

            item = FeatureWhiteList(
                factor_name=factor_name,
                factor_type=factor_type,
                category=category,
                ic_mean=ic_mean,
                ir=ir,
                lgb_importance=lgb_importance,
            )
            session.add(item)
            await session.commit()
            await session.refresh(item)
            return item

    async def add_to_blacklist(self, factor_name: str, reason: str) -> bool:
        async with async_session_maker() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(FeatureBlackList).where(FeatureBlackList.factor_name == factor_name)
            )
            existing = result.scalars().first()
            if existing:
                return True

            item = FeatureBlackList(factor_name=factor_name, reason=reason)
            session.add(item)
            # 同时从白名单移除
            await session.execute(
                type(
                    "del", (), {"where": lambda self, c: None}
                )()  # 暂略
            )
            result2 = await session.execute(
                select(FeatureWhiteList).where(FeatureWhiteList.factor_name == factor_name)
            )
            wl = result2.scalars().first()
            if wl:
                wl.is_active = 0

            await session.commit()
            return True

    async def get_whitelist(self) -> list[dict[str, Any]]:
        async with async_session_maker() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(FeatureWhiteList).where(FeatureWhiteList.is_active == 1)
            )
            items = result.scalars().all()
            return [
                {
                    "id": i.id,
                    "factor_name": i.factor_name,
                    "factor_type": i.factor_type,
                    "category": i.category,
                    "ic_mean": i.ic_mean,
                    "ir": i.ir,
                    "lgb_importance": i.lgb_importance,
                    "created_at": i.created_at,
                }
                for i in items
            ]

    async def get_blacklist(self) -> list[dict[str, Any]]:
        async with async_session_maker() as session:
            from sqlalchemy import select

            result = await session.execute(select(FeatureBlackList))
            items = result.scalars().all()
            return [
                {
                    "id": i.id,
                    "factor_name": i.factor_name,
                    "reason": i.reason,
                    "created_at": i.created_at,
                }
                for i in items
            ]

    # ── 内部工具 ──────────────────────────────

    def _find_csv(self, stock_code: str) -> Path | None:
        """在赛道目录或 datas 根目录找 CSV"""
        candidates = [
            DATAS_DIR / f"{stock_code}.csv",
        ]
        # 在 tracks 子目录搜
        if TRACKS_DIR.is_dir():
            for sub in TRACKS_DIR.iterdir():
                if sub.is_dir():
                    candidates.append(sub / f"{stock_code}.csv")

        for p in candidates:
            if p.exists():
                return p
        return None
