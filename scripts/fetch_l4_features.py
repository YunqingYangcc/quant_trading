#!/usr/bin/env python3
"""
L3 补充数据源（P1 优先级）

按 factor-research 协议，在 L3（北向/融资/季报）基础上补充：
  4. 限售解禁 —— stock_restricted_release_queue_em
  5. 前十大股东集中度 —— stock_circulate_stock_holder

衍生因子：
  - lock_days_to_unlock: 距下次解禁天数
  - lock_unlock_ratio: 解禁数量占总股本比例
  - holder_top1_pct: 第一大股东持股占比
  - holder_top10_pct: 前十大股东持股合计
  - holder_concentration: 前十大集中度变化

用法:
    cd backend && python3 ../scripts/fetch_l4_features.py
"""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
os.chdir(str(PROJECT_ROOT / "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REQUEST_DELAY = 0.3
CACHE_DIR = PROJECT_ROOT / "datas" / "fundamentals"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


async def get_our_stocks() -> list[tuple[str, str]]:
    from app.db.database import async_session_maker
    from sqlalchemy import select
    from app.models.track import TrackStock
    async with async_session_maker() as session:
        stocks = (await session.execute(select(TrackStock))).scalars().all()
    return [(s.code.split(".")[0], s.name) for s in stocks]


# ══════════════════════════════════════════════════════════════
# 数据源 4：限售解禁（P1）
# ══════════════════════════════════════════════════════════════

def fetch_unlock_data(stocks: list[tuple[str, str]]) -> dict[str, pd.DataFrame]:
    """拉取每只股票的限售解禁排期."""
    import akshare as ak

    cache_file = CACHE_DIR / "unlock_data.csv"
    if cache_file.exists():
        age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
        if age_hours < 72:
            logger.info("  使用限售解禁缓存")
            df = pd.read_csv(cache_file)
            result = {}
            for code in df["stock_code"].unique():
                result[code] = df[df["stock_code"] == code].copy()
            return result

    logger.info(f"  拉取 {len(stocks)} 只股票限售解禁数据...")
    all_records = []
    for i, (code, name) in enumerate(stocks, 1):
        if i % 20 == 0:
            logger.info(f"    [{i}/{len(stocks)}]...")
        time.sleep(REQUEST_DELAY)
        try:
            df = ak.stock_restricted_release_queue_em(symbol=code)
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                unlock_date = row.get("解禁时间")
                all_records.append({
                    "stock_code": code,
                    "unlock_date": str(unlock_date)[:10] if unlock_date else "",
                    "unlock_shares": float(row.get("解禁数量", 0) or 0),
                    "unlock_ratio_mcap": float(row.get("占总市值比例", 0) or 0),
                    "unlock_ratio_float": float(row.get("占流通市值比例", 0) or 0),
                })
        except Exception as e:
            logger.debug(f"  {code}: {e}")
            continue

    df = pd.DataFrame(all_records)
    if not df.empty:
        df.to_csv(cache_file, index=False)

    # 按股票分组
    result = {}
    for code in df["stock_code"].unique():
        result[code] = df[df["stock_code"] == code].copy()

    logger.info(f"  限售解禁: {len(df)} 条, {len(result)} 只股票")
    return result


# ══════════════════════════════════════════════════════════════
# 数据源 5：前十大股东集中度（P1）
# ══════════════════════════════════════════════════════════════

def fetch_holder_concentration(stocks: list[tuple[str, str]]) -> dict[str, pd.DataFrame]:
    """拉取前十大股东持股变化（筹码集中度）."""
    import akshare as ak

    cache_file = CACHE_DIR / "holder_concentration.csv"
    if cache_file.exists():
        age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
        if age_hours < 72:
            logger.info("  使用股东集中度缓存")
            df = pd.read_csv(cache_file)
            result = {}
            for code in df["stock_code"].unique():
                result[code] = df[df["stock_code"] == code].copy()
            return result

    logger.info(f"  拉取 {len(stocks)} 只股票前十大股东数据...")
    all_records = []
    for i, (code, name) in enumerate(stocks, 1):
        if i % 20 == 0:
            logger.info(f"    [{i}/{len(stocks)}]...")
        time.sleep(REQUEST_DELAY)
        try:
            df = ak.stock_circulate_stock_holder(symbol=code)
            if df is None or df.empty:
                continue
            # 每期汇总：Top1 占比、Top10 合计
            df["报告期"] = df["截止日期"].astype(str).str[:10]
            df["持股占比"] = pd.to_numeric(df["占流通股比例"], errors="coerce")
            for period, grp in df.groupby("报告期"):
                if len(grp) == 0:
                    continue
                grp_sorted = grp.sort_values("持股占比", ascending=False)
                top1 = grp_sorted.iloc[0]["持股占比"] if len(grp_sorted) > 0 else 0
                top10_sum = grp_sorted.head(10)["持股占比"].sum()
                all_records.append({
                    "stock_code": code,
                    "report_date": period,
                    "holder_top1_pct": float(top1) if pd.notna(top1) else 0,
                    "holder_top10_pct": float(top10_sum) if pd.notna(top10_sum) else 0,
                    "holder_count": len(grp),
                })
        except Exception as e:
            logger.debug(f"  {code}: {e}")
            continue

    df = pd.DataFrame(all_records)
    if not df.empty:
        df.to_csv(cache_file, index=False)

    result = {}
    for code in df["stock_code"].unique():
        result[code] = df[df["stock_code"] == code].copy()

    logger.info(f"  股东集中度: {len(df)} 条, {len(result)} 只股票")
    return result


# ══════════════════════════════════════════════════════════════
# 存储到 FeatureStore
# ══════════════════════════════════════════════════════════════

async def store_features(
    unlock_data: dict[str, pd.DataFrame],
    holder_data: dict[str, pd.DataFrame],
):
    from app.db.database import async_session_maker
    from sqlalchemy import select
    from app.models.track import FeatureStore

    today = pd.Timestamp.now()
    store_map: dict[str, dict[pd.Timestamp, dict[str, float]]] = {}

    # ── 限售解禁因子 ──
    for code, df in unlock_data.items():
        if df.empty:
            continue
        df["unlock_date_dt"] = pd.to_datetime(df["unlock_date"], errors="coerce")
        df = df.dropna(subset=["unlock_date_dt"])
        # 按日期聚合（同一天可能多条）
        agg = df.groupby("unlock_date_dt").agg(
            total_unlock_ratio=("unlock_ratio_mcap", "sum"),
            total_unlock_shares=("unlock_shares", "sum"),
        ).reset_index()
        for _, row in agg.iterrows():
            d = row["unlock_date_dt"]
            # 前向传播：解禁日之前 N 天也能看到即将解禁
            for offset_days in [0, 30, 60, 90]:
                signal_date = d - pd.Timedelta(days=offset_days)
                if signal_date > today:
                    continue
                store_map.setdefault(code, {}).setdefault(signal_date, {}).update({
                    f"lock_days_to_unlock": max(offset_days, 1),
                    f"lock_unlock_ratio": float(row["total_unlock_ratio"]),
                })

    # ── 前十大股东因子 ──
    for code, df in holder_data.items():
        if df.empty:
            continue
        df = df.sort_values("report_date")
        df["holder_top1_change"] = df["holder_top1_pct"].diff()
        df["holder_top10_change"] = df["holder_top10_pct"].diff()
        for _, row in df.iterrows():
            d = pd.Timestamp(row["report_date"])
            store_map.setdefault(code, {}).setdefault(d, {}).update({
                "holder_top1_pct": _safe_float(row.get("holder_top1_pct")),
                "holder_top10_pct": _safe_float(row.get("holder_top10_pct")),
                "holder_top1_change": _safe_float(row.get("holder_top1_change")),
                "holder_top10_change": _safe_float(row.get("holder_top10_change")),
            })

    # ── 写入 DB ──
    logger.info(f"\n写入 FeatureStore (前缀 lock_/holder_)...")
    async with async_session_maker() as session:
        total = 0
        for code, date_map in store_map.items():
            for date, features in date_map.items():
                if not features:
                    continue
                date_str = date.strftime("%Y-%m-%d")
                result = await session.execute(
                    select(FeatureStore).where(
                        FeatureStore.stock_code == code,
                        FeatureStore.trade_date == date_str,
                    )
                )
                existing = result.scalars().first()
                if existing:
                    existing.features = {**existing.features, **features}
                else:
                    session.add(FeatureStore(
                        stock_code=code,
                        trade_date=date_str,
                        features=features,
                        feature_version="v2_l4",
                    ))
                total += 1
            if total % 3000 == 0:
                await session.commit()
        await session.commit()
    logger.info(f"✅ 特征已写入: {total} 条, {len(store_map)} 只")


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return f if np.isfinite(f) else None
    except (ValueError, TypeError):
        return None


# ══════════════════════════════════════════════════════════════

async def main():
    from app.db.database import ensure_database_ready
    await ensure_database_ready()

    stocks = await get_our_stocks()
    logger.info(f"赛道池: {len(stocks)} 只")

    # 4. 限售解禁
    logger.info(f"\n{'='*50}")
    logger.info("数据源 4：限售解禁 (P1)")
    logger.info(f"{'='*50}")
    unlock_data = fetch_unlock_data(stocks)

    # 5. 前十大股东
    logger.info(f"\n{'='*50}")
    logger.info("数据源 5：前十大股东集中度 (P1)")
    logger.info(f"{'='*50}")
    holder_data = fetch_holder_concentration(stocks)

    # 存储
    await store_features(unlock_data, holder_data)

    logger.info(f"\n{'='*50}")
    logger.info("L4 补充数据接入完成")
    logger.info(f"  限售解禁: {len(unlock_data)}/{len(stocks)} 只")
    logger.info(f"  股东集中度: {len(holder_data)}/{len(stocks)} 只")
    logger.info(f"  新增特征前缀: lock_ (2), holder_ (4) ≈ 6 个")


if __name__ == "__main__":
    asyncio.run(main())
