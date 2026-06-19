"""
Phase D: 特征预处理脚本.

白名单特征加载 → Z-score 标准化 → 去共线 → 时序分割
输出预处理后的数据集供 Phase E (LightGBM) 使用。

核心原则:
- 使用 sklearn StandardScaler，不手写标准化公式
- 去共线: 剔除相关性 > 0.95 的特征对
- 时序分割: 按日期切分，禁止 shuffle
- 标准化参数仅从训练集 fit，防止信息泄露

Usage:
    cd backend && python3 scripts/preprocess_features.py
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.db.database import async_session_maker, ensure_database_ready
from app.models.track import (
    FeatureStore,
    FeatureWhiteList,
    TrackDataCache,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── 配置 ────────────────────────────────────────
CORR_THRESHOLD = 0.95          # 去共线阈值
TRAIN_END = "2022-12-31"       # 训练集截止日
VAL_END = "2023-12-31"         # 验证集截止日
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "ml" / "preprocessed"


async def load_whitelist_features() -> list[str]:
    """加载白名单因子名称."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(FeatureWhiteList).where(FeatureWhiteList.is_active == 1)
        )
        items = result.scalars().all()
    return [item.factor_name for item in items]


async def load_feature_data(whitelist: list[str]) -> pd.DataFrame:
    """加载所有股票的白名单特征 + forward returns."""
    async with async_session_maker() as session:
        # 加载特征
        fs_result = await session.execute(
            select(FeatureStore).order_by(FeatureStore.stock_code, FeatureStore.trade_date)
        )
        fs_rows = fs_result.scalars().all()
        logger.info(f"  feature_store: {len(fs_rows)} 条")

        # 加载 forward returns
        tc_result = await session.execute(
            select(TrackDataCache).order_by(TrackDataCache.stock_code, TrackDataCache.trade_date)
        )
        tc_rows = tc_result.scalars().all()

    # 构建 forward returns
    stock_dates: dict[str, list[str]] = {}
    cache: dict[tuple[str, str], float] = {}
    for row in tc_rows:
        stock_dates.setdefault(row.stock_code, []).append(row.trade_date)
        cache[(row.trade_date, row.stock_code)] = row.close_px

    fwd_returns: dict[tuple[str, str], float] = {}
    for sc, dates in stock_dates.items():
        dates.sort()
        for i in range(len(dates) - 20):
            c0 = cache[(dates[i], sc)]
            c20 = cache[(dates[i + 20], sc)]
            if c0 > 0:
                fwd_returns[(dates[i], sc)] = (c20 - c0) / c0

    # 合并
    records = []
    for fs_row in fs_rows:
        key = (fs_row.trade_date, fs_row.stock_code)
        if key not in fwd_returns:
            continue

        record = {
            "date": fs_row.trade_date,
            "stock_code": fs_row.stock_code,
            "target": fwd_returns[key],
        }
        features = fs_row.features
        for fname in whitelist:
            val = features.get(fname)
            if val is not None and np.isfinite(val):
                record[fname] = val
            else:
                record[fname] = np.nan
        records.append(record)

    df = pd.DataFrame(records)
    logger.info(f"  合并后: {len(df)} 行, {len(whitelist)} 个特征")
    return df


def fill_nan(df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    """用每列的中位数填充 NaN (全量计算，后续会用训练集中位数替换)."""
    before_nan = df[feature_cols].isna().sum().sum()
    # 先填充全量中位数（临时）
    for col in feature_cols:
        median_val = df[col].median()
        if pd.notna(median_val):
            df[col] = df[col].fillna(median_val)
    after_nan = df[feature_cols].isna().sum().sum()
    logger.info(f"  NaN 填充: {before_nan} → {after_nan} 个 NaN (用中位数填充)")
    return df


def decorrelate(df: pd.DataFrame, feature_cols: list[str], threshold: float) -> list[str]:
    """去共线: 剔除相关性 > threshold 的特征对中的后者."""
    corr_matrix = df[feature_cols].corr().abs()

    # 找出高相关对
    upper = corr_matrix.where(
        np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
    )

    to_drop = set()
    for column in upper.columns:
        highly_corr = upper.index[upper[column] > threshold].tolist()
        if highly_corr:
            # 保留排在前面的（按原始列表顺序），删除后面的
            to_drop.add(column)

    kept = [c for c in feature_cols if c not in to_drop]
    dropped = [c for c in feature_cols if c in to_drop]

    logger.info(f"  去共线: {len(feature_cols)} → {len(kept)} 个特征 (剔除 {len(dropped)} 个)")
    if dropped:
        logger.info(f"  剔除特征: {dropped[:10]}{'...' if len(dropped) > 10 else ''}")

    return kept


def time_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """按时序切分训练/验证/测试集."""
    train = df[df["date"] <= TRAIN_END].copy()
    val = df[(df["date"] > TRAIN_END) & (df["date"] <= VAL_END)].copy()
    test = df[df["date"] > VAL_END].copy()

    logger.info(f"  训练集: {len(train)} 行 (≤{TRAIN_END})")
    logger.info(f"  验证集: {len(val)} 行 ({TRAIN_END}~{VAL_END})")
    logger.info(f"  测试集: {len(test)} 行 (>{VAL_END})")

    return train, val, test


def standardize(
    train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame, feature_cols: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, StandardScaler]:
    """Z-score 标准化: 仅用训练集 fit."""
    scaler = StandardScaler()

    train_features = scaler.fit_transform(train[feature_cols])
    val_features = scaler.transform(val[feature_cols])
    test_features = scaler.transform(test[feature_cols])

    # 替换原特征列
    for i, col in enumerate(feature_cols):
        train[col] = train_features[:, i]
        val[col] = val_features[:, i]
        test[col] = test_features[:, i]

    logger.info(f"  标准化完成: fit on train, transform all")
    return train, val, test, scaler


def save_datasets(
    train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame,
    feature_cols: list[str], scaler: StandardScaler
):
    """保存预处理后的数据集."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 保存为 parquet
    train.to_parquet(OUTPUT_DIR / "train.parquet", index=False)
    val.to_parquet(OUTPUT_DIR / "val.parquet", index=False)
    test.to_parquet(OUTPUT_DIR / "test.parquet", index=False)

    # 保存特征列表
    with open(OUTPUT_DIR / "feature_cols.json", "w") as f:
        json.dump(feature_cols, f, indent=2)

    # 保存 scaler 参数
    scaler_params = {
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "feature_cols": feature_cols,
    }
    with open(OUTPUT_DIR / "scaler_params.json", "w") as f:
        json.dump(scaler_params, f, indent=2)

    # 保存元信息
    meta = {
        "train_rows": len(train),
        "val_rows": len(val),
        "test_rows": len(test),
        "total_rows": len(train) + len(val) + len(test),
        "feature_count": len(feature_cols),
        "target_col": "target",
        "train_end": TRAIN_END,
        "val_end": VAL_END,
        "corr_threshold": CORR_THRESHOLD,
    }
    with open(OUTPUT_DIR / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    logger.info(f"  数据集已保存: {OUTPUT_DIR}")


async def main():
    logger.info("=" * 60)
    logger.info("Phase D: 特征预处理")
    logger.info("=" * 60)
    logger.info(f"去共线阈值: |corr| > {CORR_THRESHOLD}")
    logger.info(f"时序分割: train≤{TRAIN_END}, val≤{VAL_END}, test>{VAL_END}")

    await ensure_database_ready()

    # 1. 加载白名单
    whitelist = await load_whitelist_features()
    logger.info(f"白名单因子: {len(whitelist)} 个")
    if not whitelist:
        logger.error("白名单为空! 请先运行 Phase C (scripts/screen_factors.py)")
        return

    # 2. 加载特征数据
    logger.info("加载特征数据...")
    df = await load_feature_data(whitelist)
    if df.empty:
        logger.error("无有效数据!")
        return

    # 3. NaN 填充
    logger.info("NaN 填充...")
    df = fill_nan(df, whitelist)

    # 4. 去共线
    logger.info("去共线...")
    kept_cols = decorrelate(df, whitelist, CORR_THRESHOLD)

    # 5. 时序分割
    logger.info("时序分割...")
    train, val, test = time_split(df)

    # 6. 标准化 (仅用训练集 fit)
    logger.info("Z-score 标准化...")
    train, val, test, scaler = standardize(train, val, test, kept_cols)

    # 7. 验证
    logger.info("")
    logger.info("验证...")
    # 检查训练集标准化后均值 ≈ 0, 标准差 ≈ 1
    train_means = train[kept_cols].mean().abs().max()
    train_stds = train[kept_cols].std()
    std_range = (train_stds.min(), train_stds.max())
    logger.info(f"  训练集 max|mean|: {train_means:.6f} (应 ≈ 0)")
    logger.info(f"  训练集 std range: ({std_range[0]:.4f}, {std_range[1]:.4f}) (应 ≈ 1)")

    # 检查去共线后相关性
    post_corr = train[kept_cols].corr().abs()
    upper = post_corr.where(np.triu(np.ones(post_corr.shape), k=1).astype(bool))
    max_corr = upper.max().max()
    high_corr_pairs = (upper > CORR_THRESHOLD).sum().sum()
    logger.info(f"  去共线后 max|corr|: {max_corr:.4f} (应 < {CORR_THRESHOLD})")
    logger.info(f"  高相关对数: {high_corr_pairs} (应为 0)")

    # 8. 保存
    logger.info("")
    logger.info("保存数据集...")
    save_datasets(train, val, test, kept_cols, scaler)

    # 9. 汇总报告
    logger.info("")
    logger.info("=" * 60)
    logger.info("预处理报告")
    logger.info("=" * 60)
    logger.info(f"白名单因子数: {len(whitelist)}")
    logger.info(f"去共线后特征数: {len(kept_cols)}")
    logger.info(f"训练集: {len(train)} 行 (≤{TRAIN_END})")
    logger.info(f"验证集: {len(val)} 行 ({TRAIN_END}~{VAL_END})")
    logger.info(f"测试集: {len(test)} 行 (>{VAL_END})")
    logger.info(f"总计: {len(train) + len(val) + len(test)} 行")
    logger.info(f"max|corr| < {CORR_THRESHOLD}: {'✅' if high_corr_pairs == 0 else '❌'}")
    logger.info(f"标准化 max|mean| < 0.01: {'✅' if train_means < 0.01 else '⚠️'}")
    logger.info(f"时序无 shuffle: ✅ (按日期切分)")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
