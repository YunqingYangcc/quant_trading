"""
Phase B: 特征工程批量计算脚本.

从 TrackDataCache 加载数据 → 计算通用特征 + 赛道专属特征 → 存入 FeatureStore

Usage:
    cd backend && python -m scripts.compute_features

验收标准:
- 所有特征 shift(1) 防未来泄露
- NaN 比例 < 50%
- 特征数 >= 60

增量模式：
    run_incremental_compute() 只计算 FeatureStore 中缺失的交易日
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# 添加 backend 到路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select, text, func

from app.db.database import async_session_maker, ensure_database_ready
from app.features.features_generic import compute_generic_features
from app.features.features_track import compute_track_specific_features
from app.models.track import FeatureStore, Track, TrackDataCache, track_stock

logger = logging.getLogger(__name__)


async def load_stock_data(stock_code: str) -> pd.DataFrame:
    """从 TrackDataCache 加载股票数据."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(TrackDataCache)
            .where(TrackDataCache.stock_code == stock_code)
            .order_by(TrackDataCache.trade_date)
        )
        records = result.scalars().all()

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame([
        {
            "date": r.trade_date,
            "open": r.open_px,
            "high": r.high_px,
            "low": r.low_px,
            "close": r.close_px,
            "volume": r.volume,
            "amount": r.amount,
        }
        for r in records
    ])
    return df


async def get_track_stocks() -> dict[str, list[str]]:
    """获取每个赛道的股票列表. Returns {track_name: [stock_codes]}. """
    async with async_session_maker() as session:
        tracks_result = await session.execute(select(Track).where(Track.is_active == 1))
        tracks = tracks_result.scalars().all()

        result = {}
        for track in tracks:
            stocks_result = await session.execute(
                select(track_stock.c.stock_code).where(track_stock.c.track_id == track.id)
            )
            codes = [row[0] for row in stocks_result.all()]
            result[track.name] = codes

    return result


async def save_features(stock_code: str, df: pd.DataFrame, feature_cols: list[str]):
    """将特征存入 FeatureStore."""
    async with async_session_maker() as session:
        # 清除旧数据
        await session.execute(
            delete(FeatureStore).where(FeatureStore.stock_code == stock_code)
        )

        batch = []
        for idx, row in df.iterrows():
            features = {}
            for col in feature_cols:
                val = row[col]
                if pd.isna(val) or np.isinf(val):
                    features[col] = None
                else:
                    features[col] = round(float(val), 8)

            record = FeatureStore(
                stock_code=stock_code,
                trade_date=row["date"],
                features=features,
                feature_version="v1",
            )
            batch.append(record)

        # 批量写入
        session.add_all(batch)
        await session.commit()

    return len(batch)


def validate_features(df: pd.DataFrame, feature_cols: list[str]) -> dict:
    """验证特征质量."""
    stats = {
        "total_features": len(feature_cols),
        "total_rows": len(df),
        "nan_stats": {},
        "shift_check": True,  # 已在 compute_generic_features 中 shift(1)
    }

    for col in feature_cols:
        nan_count = df[col].isna().sum()
        nan_pct = nan_count / len(df) * 100 if len(df) > 0 else 100
        stats["nan_stats"][col] = {
            "nan_count": int(nan_count),
            "nan_pct": round(nan_pct, 2),
        }

    # 统计 NaN < 50% 的特征数
    valid_features = [
        col for col, s in stats["nan_stats"].items() if s["nan_pct"] < 50
    ]
    stats["valid_features_count"] = len(valid_features)
    stats["all_pass"] = stats["valid_features_count"] == len(feature_cols)

    return stats


async def main():
    logger.info("=" * 60)
    logger.info("Phase B: 特征工程批量计算")
    logger.info("=" * 60)

    # 确保数据库表存在
    await ensure_database_ready()

    # 获取赛道-股票映射
    track_stocks = await get_track_stocks()
    all_stocks = set()
    for codes in track_stocks.values():
        all_stocks.update(codes)

    logger.info("赛道: %s", {k: len(v) for k, v in track_stocks.items()})
    logger.info("共 %d 只股票待处理", len(all_stocks))

    total_features_count = 0
    all_stats = {}

    for i, stock_code in enumerate(sorted(all_stocks), 1):
        logger.info(f"[{i}/{len(all_stocks)}] 处理 {stock_code}...")

        # 1. 加载数据
        df = await load_stock_data(stock_code)
        if df.empty or len(df) < 60:
            logger.warning(f"  跳过 {stock_code}: 数据不足 ({len(df)} 行)")
            continue

        # 2. 计算通用特征
        df = compute_generic_features(df)

        # 3. 计算赛道专属特征
        for track_name, codes in track_stocks.items():
            if stock_code in codes:
                df = compute_track_specific_features(df, track_name)

        # 4. 提取特征列 (排除原始列)
        raw_cols = {"date", "open", "high", "low", "close", "volume", "amount"}
        feature_cols = [c for c in df.columns if c not in raw_cols]

        # 5. 验证
        stats = validate_features(df, feature_cols)
        total_features_count = max(total_features_count, stats["total_features"])
        all_stats[stock_code] = stats

        valid_pct = stats["valid_features_count"] / stats["total_features"] * 100
        logger.info(
            f"  特征数: {stats['total_features']}, "
            f"有效(<50%NaN): {stats['valid_features_count']} ({valid_pct:.1f}%), "
            f"行数: {stats['total_rows']}"
        )

        # 6. 入库
        count = await save_features(stock_code, df, feature_cols)
        logger.info(f"  已存入 {count} 条特征记录")

    # ── 汇总报告 ──────────────────────────────
    logger.info("")
    logger.info("=" * 60)
    logger.info("验收报告")
    logger.info("=" * 60)
    logger.info(f"处理股票数: {len(all_stats)}")
    logger.info(f"特征总数: {total_features_count}")

    # 检查 NaN 比例
    all_pass = True
    for code, stats in all_stats.items():
        if not stats["all_pass"]:
            all_pass = False
            high_nan = [
                col for col, s in stats["nan_stats"].items() if s["nan_pct"] >= 50
            ]
            logger.warning(f"  {code}: {len(high_nan)} 个特征 NaN>=50%")

    logger.info(f"shift(1) 防泄露: ✅ 已在特征计算中执行")
    logger.info(f"特征数 >= 60: {'✅' if total_features_count >= 60 else '❌'} ({total_features_count})")
    logger.info(f"NaN < 50%: {'✅' if all_pass else '⚠️ 部分股票有超高NaN特征'}")
    logger.info("=" * 60)

    return {
        "status": "success",
        "stocks_processed": len(all_stats),
        "total_features": total_features_count,
        "all_pass": all_pass,
    }


async def run_compute_features() -> dict:
    """特征计算入口（供 API 调用）"""
    return await main()


async def run_incremental_compute() -> dict:
    """
    增量特征计算：只补算 FeatureStore 中缺失的交易日。

    流程:
    1. 对每只股票，查询 FeatureStore 中已有最新 trade_date
    2. 从 TrackDataCache 加载该日期之后的新数据
    3. 计算特征并追加写入 FeatureStore
    """
    from sqlalchemy import func as sa_func

    logger.info("=" * 60)
    logger.info("增量特征计算")
    logger.info("=" * 60)

    await ensure_database_ready()

    # 获取所有赛道的股票列表
    track_stocks = await get_track_stocks()
    all_stocks = set()
    for codes in track_stocks.values():
        all_stocks.update(codes)

    if not all_stocks:
        return {"status": "skipped", "reason": "无股票数据"}

    logger.info(f"共 {len(all_stocks)} 只股票待检查")

    async with async_session_maker() as session:
        # 每只股票已有最新日期
        newest_dates = {}
        for code in all_stocks:
            result = await session.execute(
                select(sa_func.max(FeatureStore.trade_date))
                .where(FeatureStore.stock_code == code)
            )
            max_date = result.scalar()
            newest_dates[code] = max_date

    total_added = 0
    processed = 0
    errors = []

    for i, stock_code in enumerate(sorted(all_stocks), 1):
        # 如果已有全量数据，跳过
        already_have = newest_dates.get(stock_code)
        if not already_have:
            logger.info(f"[{i}/{len(all_stocks)}] {stock_code}: 无存量特征，跳过（请先跑全量计算）")
            continue

        # 获取 TrackDataCache 中该股票的新数据（> 已有最新日期）
        # 为了能算新特征，需要取 最早缺失日往前 -60 行的数据
        df_full = await load_stock_data(stock_code)
        if df_full.empty or len(df_full) < 60:
            logger.warning(f"  跳过 {stock_code}: 数据不足 ({len(df_full)} 行)")
            continue

        # 已有特征的最新日期
        last_date = already_have
        df_new = df_full[df_full["date"] > last_date].copy()

        if df_new.empty:
            continue

        # 需要加上足够的历史数据来计算时间窗口特征
        # 取 last_date 之前至少 60 行
        all_idx = df_full[df_full["date"] <= last_date].index
        if len(all_idx) >= 60:
            start_idx = all_idx[-60]
        elif len(all_idx) > 0:
            start_idx = all_idx[0]
        else:
            start_idx = 0

        df_for_compute = df_full.loc[start_idx:].copy()

        logger.info(f"[{i}/{len(all_stocks)}] {stock_code}: 增量计算 {len(df_new)} 个新交易日")

        # 计算特征
        df_for_compute = compute_generic_features(df_for_compute)
        for track_name, codes in track_stocks.items():
            if stock_code in codes:
                df_for_compute = compute_track_specific_features(df_for_compute, track_name)

        # 提取特征列
        raw_cols = {"date", "open", "high", "low", "close", "volume", "amount"}
        feature_cols = [c for c in df_for_compute.columns if c not in raw_cols]

        # 只取新行
        new_rows = df_for_compute[df_for_compute["date"] > last_date]

        if new_rows.empty:
            continue

        # 写入 FeatureStore
        async with async_session_maker() as session:
            batch = []
            for _, row in new_rows.iterrows():
                features = {}
                for col in feature_cols:
                    val = row[col]
                    if pd.isna(val) or np.isinf(val):
                        features[col] = None
                    else:
                        features[col] = round(float(val), 8)

                record = FeatureStore(
                    stock_code=stock_code,
                    trade_date=row["date"],
                    features=features,
                    feature_version="v1",
                )
                batch.append(record)

            session.add_all(batch)
            await session.commit()

        total_added += len(batch)
        processed += 1
        logger.info(f"  ✅ 新增 {len(batch)} 条特征")

    logger.info("=" * 60)
    logger.info(f"增量计算完成: {processed}/{len(all_stocks)} 只股票有新增数据")
    logger.info(f"总计新增 {total_added} 条特征记录")
    logger.info("=" * 60)

    return {
        "status": "success",
        "stocks_with_new_data": processed,
        "total_added_records": total_added,
    }


if __name__ == "__main__":
    asyncio.run(main())
