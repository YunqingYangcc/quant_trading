"""
Phase E: LightGBM 分赛道训练.

加载预处理数据 → 分赛道独立训练 → TimeSeriesSplit → 模型保存 → 过拟合检测

核心原则:
- 每个赛道独立模型（4 个），绝不共用
- TimeSeriesSplit 时间滚动训练，禁止 shuffle
- 固定超参数，不随机调参
- 预测目标: future_20d_excess_return (target 列)

Usage:
    cd backend && python3 scripts/train_models.py
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.db.database import async_session_maker, ensure_database_ready
from app.models.track import Track, track_stock

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── 固定超参数（禁止调参刷指标）────────────────
LGB_PARAMS = {
    "objective": "regression",
    "metric": "mse",
    "boosting_type": "gbdt",
    "num_leaves": 8,           # 减小树复杂度 31→8
    "max_depth": 4,            # 限制深度
    "min_child_samples": 50,   # 增加样本数下限 20→50
    "min_child_weight": 10,    # 最小叶子权重
    "learning_rate": 0.01,     # 降低学习率 0.05→0.01
    "feature_fraction": 0.6,   # 降低特征采样 0.8→0.6
    "bagging_fraction": 0.7,   # 降低数据采样 0.8→0.7
    "bagging_freq": 3,         # 每3轮bag一次
    "n_estimators": 100,       # 减少迭代次数 200→100
    "reg_alpha": 5.0,          # L1正则大幅增强 0→5
    "reg_lambda": 10.0,        # L2正则大幅增强 0→10
    "verbose": -1,
    "random_state": 42,
}

TIMESERIES_SPLITS = 3     # TimeSeriesSplit 折数
R2_GAP_THRESHOLD = 0.15   # 训练/测试 R² 差距阈值

PREPROCESSED_DIR = Path(__file__).resolve().parent.parent / "ml" / "preprocessed"
MODELS_DIR = Path(__file__).resolve().parent.parent / "ml" / "models"


async def get_track_stock_map() -> dict[str, list[str]]:
    """获取赛道-股票映射."""
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


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    """加载预处理数据."""
    train = pd.read_parquet(PREPROCESSED_DIR / "train.parquet")
    val = pd.read_parquet(PREPROCESSED_DIR / "val.parquet")
    test = pd.read_parquet(PREPROCESSED_DIR / "test.parquet")

    with open(PREPROCESSED_DIR / "feature_cols.json") as f:
        feature_cols = json.load(f)

    return train, val, test, feature_cols


def train_track_model(
    track_name: str,
    stock_codes: list[str],
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: list[str],
) -> dict:
    """训练单个赛道的 LightGBM 模型.

    Returns:
        dict with training metrics
    """
    # 过滤到该赛道的股票
    train_track = train_df[train_df["stock_code"].isin(stock_codes)].copy()
    val_track = val_df[val_df["stock_code"].isin(stock_codes)].copy()
    test_track = test_df[test_df["stock_code"].isin(stock_codes)].copy()

    if len(train_track) < 100:
        logger.warning(f"  {track_name}: 训练数据不足 ({len(train_track)} 行), 跳过")
        return {"status": "skipped", "reason": "insufficient_data"}

    X_train = train_track[feature_cols].values
    y_train = train_track["target"].values
    X_val = val_track[feature_cols].values
    y_val = val_track["target"].values
    X_test = test_track[feature_cols].values
    y_test = test_track["target"].values

    logger.info(f"  数据: train={len(train_track)}, val={len(val_track)}, test={len(test_track)}")

    # ── TimeSeriesSplit 交叉验证 ─────────────
    tscv = TimeSeriesSplit(n_splits=TIMESERIES_SPLITS)
    cv_scores = []

    for fold, (train_idx, val_idx) in enumerate(tscv.split(X_train)):
        X_fold_train, X_fold_val = X_train[train_idx], X_train[val_idx]
        y_fold_train, y_fold_val = y_train[train_idx], y_train[val_idx]

        model_cv = lgb.LGBMRegressor(**LGB_PARAMS)
        model_cv.fit(
            X_fold_train, y_fold_train,
            eval_set=[(X_fold_val, y_fold_val)],
        )

        y_pred = model_cv.predict(X_fold_val)
        r2 = r2_score(y_fold_val, y_pred)
        cv_scores.append(r2)

    cv_mean = np.mean(cv_scores)
    cv_std = np.std(cv_scores)
    logger.info(f"  CV R²: {cv_mean:.4f} ± {cv_std:.4f}")

    # ── 最终模型: 用全部训练集训练 ─────────
    model = lgb.LGBMRegressor(**LGB_PARAMS)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
    )

    # ── 评估 ─────────────────
    y_train_pred = model.predict(X_train)
    y_val_pred = model.predict(X_val)

    train_r2 = r2_score(y_train, y_train_pred)
    val_r2 = r2_score(y_val, y_val_pred)
    test_r2 = r2_score(y_test, model.predict(X_test)) if len(y_test) > 0 else 0.0

    r2_gap = train_r2 - val_r2
    overfitting = r2_gap > R2_GAP_THRESHOLD

    logger.info(f"  Train R²: {train_r2:.4f}, Val R²: {val_r2:.4f}, Test R²: {test_r2:.4f}")
    logger.info(f"  R² gap (train-val): {r2_gap:.4f} {'⚠️ 过拟合!' if overfitting else '✅'}")

    # ── 特征重要性 Top 10 ─────────
    importances = model.feature_importances_
    imp_pairs = sorted(zip(feature_cols, importances), key=lambda x: -x[1])
    top10 = imp_pairs[:10]
    logger.info(f"  特征重要性 Top 5:")
    for fname, imp in top10[:5]:
        logger.info(f"    {fname:40s} {imp}")

    # ── 保存模型 ─────────
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODELS_DIR / f"{track_name}.pkl"
    joblib.dump(model, model_path)
    logger.info(f"  模型已保存: {model_path}")

    # ── 保存元信息 ─────
    meta = {
        "track_name": track_name,
        "stock_codes": stock_codes,
        "n_stocks": len(stock_codes),
        "train_rows": len(train_track),
        "val_rows": len(val_track),
        "test_rows": len(test_track),
        "cv_mean_r2": round(cv_mean, 4),
        "cv_std_r2": round(cv_std, 4),
        "train_r2": round(train_r2, 4),
        "val_r2": round(val_r2, 4),
        "test_r2": round(test_r2, 4),
        "r2_gap": round(r2_gap, 4),
        "overfitting": overfitting,
        "params": LGB_PARAMS,
        "top_features": [{"name": n, "importance": int(i)} for n, i in top10],
    }
    meta_path = MODELS_DIR / f"{track_name}_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    return {
        "status": "trained",
        "track_name": track_name,
        "n_stocks": len(stock_codes),
        "train_r2": train_r2,
        "val_r2": val_r2,
        "test_r2": test_r2,
        "r2_gap": r2_gap,
        "overfitting": overfitting,
        "cv_mean": cv_mean,
    }


async def main():
    logger.info("=" * 60)
    logger.info("Phase E: LightGBM 分赛道训练")
    logger.info("=" * 60)
    logger.info(f"超参数: {json.dumps(LGB_PARAMS, indent=2)}")
    logger.info(f"TimeSeriesSplit: {TIMESERIES_SPLITS} folds")
    logger.info(f"R² gap 阈值: {R2_GAP_THRESHOLD}")

    await ensure_database_ready()

    # 1. 加载数据
    logger.info("\n加载预处理数据...")
    train_df, val_df, test_df, feature_cols = load_data()
    logger.info(f"  特征数: {len(feature_cols)}")
    logger.info(f"  Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")

    # 2. 获取赛道映射
    track_map = await get_track_stock_map()
    logger.info(f"  赛道: {', '.join(f'{k}({len(v)})' for k, v in track_map.items())}")

    # 3. 分赛道训练
    results = {}
    for track_name, stock_codes in track_map.items():
        logger.info(f"\n{'─' * 40}")
        logger.info(f"训练赛道: {track_name} ({len(stock_codes)} 只股票)")
        logger.info(f"{'─' * 40}")

        result = train_track_model(
            track_name, stock_codes,
            train_df, val_df, test_df, feature_cols
        )
        results[track_name] = result

    # 4. 汇总报告
    logger.info("\n" + "=" * 60)
    logger.info("训练报告")
    logger.info("=" * 60)

    all_pass = True
    for track_name, r in results.items():
        if r["status"] == "skipped":
            logger.info(f"  {track_name:15s} ❌ 跳过 ({r['reason']})")
            all_pass = False
        elif r["overfitting"]:
            logger.info(f"  {track_name:15s} ⚠️ 过拟合 (R²gap={r['r2_gap']:.4f})")
            all_pass = False
        else:
            logger.info(f"  {track_name:15s} ✅ Train={r['train_r2']:.4f} Val={r['val_r2']:.4f} Test={r['test_r2']:.4f} gap={r['r2_gap']:.4f}")

    trained_count = sum(1 for r in results.values() if r["status"] == "trained")
    no_overfit_count = sum(1 for r in results.values() if r["status"] == "trained" and not r["overfitting"])

    logger.info(f"\n模型数: {trained_count}/4")
    logger.info(f"无过拟合: {no_overfit_count}/{trained_count}")
    logger.info(f"R² gap < {R2_GAP_THRESHOLD}: {'✅' if all_pass else '⚠️'}")
    logger.info(f"TimeSeriesSplit (无 shuffle): ✅")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
