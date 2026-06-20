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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import r2_score, mean_squared_error, accuracy_score
from sklearn.model_selection import TimeSeriesSplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.db.database import async_session_maker, ensure_database_ready
from app.models.track import Track, track_stock

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── 固定超参数（禁止调参刷指标）────────────────
LGB_PARAMS = {
    "objective": "binary",
    "metric": "binary_logloss",
    "boosting_type": "gbdt",
    "num_leaves": 31,
    "max_depth": 6,
    "min_child_samples": 20,
    "min_child_weight": 0.001,
    "learning_rate": 0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.9,
    "bagging_freq": 3,
    "n_estimators": 1000,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "verbose": -1,
    "random_state": 42,
}

TIMESERIES_SPLITS = 3     # TimeSeriesSplit 折数
ACC_GAP_THRESHOLD = 0.10  # 训练/验证准确率差距阈值

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
    params: dict | None = None,
) -> dict:
    """训练单个赛道的 LightGBM 模型.

    Args:
        params: 可选超参数覆盖，不传则使用 LGB_PARAMS 默认值

    Returns:
        dict with training metrics
    """
    effective_params = {**LGB_PARAMS, **(params or {})}
    # 自适应正则化：小样本赛道用更强的正则防过拟合
    n_stocks = len(stock_codes)
    if n_stocks <= 10:
        effective_params["reg_alpha"] = 0.5
        effective_params["reg_lambda"] = 2.0
        logger.info(f"  {track_name}: 小样本赛道 ({n_stocks}只), 启用强正则化")
    elif n_stocks <= 15:
        effective_params["reg_alpha"] = 0.05
        effective_params["reg_lambda"] = 0.5
        logger.info(f"  {track_name}: 中等样本赛道 ({n_stocks}只), 启用中正则化")
    else:
        logger.info(f"  {track_name}: 充足样本赛道 ({n_stocks}只), 启用松绑参数")
    # 过滤到该赛道的股票
    train_track = train_df[train_df["stock_code"].isin(stock_codes)].copy()
    val_track = val_df[val_df["stock_code"].isin(stock_codes)].copy()
    test_track = test_df[test_df["stock_code"].isin(stock_codes)].copy()

    if len(train_track) < 100:
        logger.warning(f"  {track_name}: 训练数据不足 ({len(train_track)} 行), 跳过")
        return {"status": "skipped", "reason": "insufficient_data"}

    # ── 转换目标：连续收益 → 二分类标签 ─────
    # 对每个日期，判断个股收益是否超过赛道当日中位数
    for df_tmp in [train_track, val_track, test_track]:
        if len(df_tmp) == 0:
            continue
        med = df_tmp.groupby("date")["target"].transform("median")
        df_tmp["target_binary"] = (df_tmp["target"] > med).astype(int)

    X_train = train_track[feature_cols]
    y_train = train_track["target_binary"].values
    X_val = val_track[feature_cols]
    y_val = val_track["target_binary"].values
    X_test = test_track[feature_cols]
    y_test = test_track["target_binary"].values

    logger.info(f"  数据: train={len(train_track)}, val={len(val_track)}, test={len(test_track)}")

    # ── TimeSeriesSplit 交叉验证 ─────────────
    tscv = TimeSeriesSplit(n_splits=TIMESERIES_SPLITS)
    cv_scores = []

    for fold, (train_idx, val_idx) in enumerate(tscv.split(X_train)):
        X_fold_train, X_fold_val = X_train.iloc[train_idx], X_train.iloc[val_idx]
        y_fold_train, y_fold_val = y_train[train_idx], y_train[val_idx]

        model_cv = lgb.LGBMClassifier(**effective_params)
        model_cv.fit(
            X_fold_train, y_fold_train,
            eval_set=[(X_fold_val, y_fold_val)],
            callbacks=[lgb.early_stopping(20)],
        )

        y_pred_proba = model_cv.predict_proba(X_fold_val, num_iteration=model_cv.best_iteration_)[:, 1]
        y_pred = (y_pred_proba > 0.5).astype(int)
        acc = accuracy_score(y_fold_val, y_pred)
        cv_scores.append(acc)

    cv_mean = np.mean(cv_scores)
    cv_std = np.std(cv_scores)
    logger.info(f"  CV Accuracy: {cv_mean:.4f} ± {cv_std:.4f}")

    # ── 最终模型: 用全部训练集训练 ─────────
    model = lgb.LGBMClassifier(**effective_params)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(20)],
    )

    best_iter = model.best_iteration_
    logger.info(f"  最佳迭代轮数: {best_iter}/{effective_params['n_estimators']}")

    # ── 评估 ─────────────────
    y_train_pred = (model.predict_proba(X_train, num_iteration=best_iter)[:, 1] > 0.5).astype(int)
    y_val_pred = (model.predict_proba(X_val, num_iteration=best_iter)[:, 1] > 0.5).astype(int)
    y_test_pred = (model.predict_proba(X_test, num_iteration=best_iter)[:, 1] > 0.5).astype(int) if len(y_test) > 0 else []

    train_acc = accuracy_score(y_train, y_train_pred)
    val_acc = accuracy_score(y_val, y_val_pred)
    test_acc = accuracy_score(y_test, y_test_pred) if len(y_test_pred) > 0 else 0.0

    acc_gap = train_acc - val_acc
    overfitting = acc_gap > ACC_GAP_THRESHOLD

    logger.info(f"  Train Acc: {train_acc:.4f}, Val Acc: {val_acc:.4f}, Test Acc: {test_acc:.4f}")
    logger.info(f"  Acc gap (train-val): {acc_gap:.4f} {'⚠️ 过拟合!' if overfitting else '✅'}")

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
        "objective": "binary",
        "cv_mean_acc": round(cv_mean, 4),
        "cv_std_acc": round(cv_std, 4),
        "train_acc": round(train_acc, 4),
        "val_acc": round(val_acc, 4),
        "test_acc": round(test_acc, 4),
        "acc_gap": round(acc_gap, 4),
        "overfitting": overfitting,
        "params": effective_params,
        "top_features": [{"name": n, "importance": int(i)} for n, i in top10],
    }
    meta_path = MODELS_DIR / f"{track_name}_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    return {
        "status": "trained",
        "track_name": track_name,
        "n_stocks": len(stock_codes),
        "train_acc": train_acc,
        "val_acc": val_acc,
        "test_acc": test_acc,
        "acc_gap": acc_gap,
        "overfitting": overfitting,
        "cv_mean": cv_mean,
    }


async def main():
    logger.info("=" * 60)
    logger.info("Phase E: LightGBM 分赛道训练")
    logger.info("=" * 60)
    logger.info(f"超参数: {json.dumps(LGB_PARAMS, indent=2)}")
    logger.info(f"TimeSeriesSplit: {TIMESERIES_SPLITS} folds")
    logger.info(f"ACC gap 阈值: {ACC_GAP_THRESHOLD}")

    await ensure_database_ready()

    # 1. 加载数据
    logger.info("\n加载预处理数据...")
    train_df, val_df, test_df, feature_cols = load_data()
    logger.info(f"  特征数: {len(feature_cols)}")
    logger.info(f"  Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")

    # 2. 获取赛道映射
    track_map = await get_track_stock_map()
    logger.info(f"  赛道: {', '.join(f'{k}({len(v)})' for k, v in track_map.items())}")

    # 3. 分赛道训练（并行）
    logger.info(f"\n开始并行训练 {len(track_map)} 个赛道...")
    results = {}
    with ThreadPoolExecutor(max_workers=min(4, len(track_map))) as executor:
        futures = {}
        for track_name, stock_codes in track_map.items():
            future = executor.submit(
                train_track_model,
                track_name, stock_codes,
                train_df, val_df, test_df, feature_cols,
                None,
            )
            futures[future] = track_name

        for future in as_completed(futures):
            track_name = futures[future]
            try:
                result = future.result()
                results[track_name] = result
            except Exception as e:
                logger.error(f"{track_name} 训练异常: {e}")
                results[track_name] = {"status": "failed", "error": str(e)}

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
            logger.info(f"  {track_name:15s} ⚠️ 过拟合 (acc_gap={r['acc_gap']:.4f})")
            all_pass = False
        else:
            logger.info(f"  {track_name:15s} ✅ Train={r['train_acc']:.4f} Val={r['val_acc']:.4f} Test={r['test_acc']:.4f} gap={r['acc_gap']:.4f}")

    trained_count = sum(1 for r in results.values() if r["status"] == "trained")
    no_overfit_count = sum(1 for r in results.values() if r["status"] == "trained" and not r["overfitting"])

    logger.info(f"\n模型数: {trained_count}/4")
    logger.info(f"无过拟合: {no_overfit_count}/{trained_count}")
    logger.info(f"ACC gap < {ACC_GAP_THRESHOLD}: {'✅' if all_pass else '⚠️'}")
    logger.info(f"TimeSeriesSplit (无 shuffle): ✅")
    logger.info("=" * 60)

    # 5. 记录流水线日志
    await _record_pipeline_run(results, train_df, feature_cols)


async def _record_pipeline_run(results: dict, train_df: pd.DataFrame, feature_cols: list[str]):
    """记录训练流水线日志到数据库."""
    import subprocess
    import time
    try:
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        git_hash = None

    summary = {}
    for name, r in results.items():
        if r["status"] == "trained":
            summary[name] = {
                "train_acc": r["train_acc"],
                "val_acc": r["val_acc"],
                "test_acc": r["test_acc"],
                "acc_gap": r["acc_gap"],
                "overfitting": r["overfitting"],
                "n_stocks": r.get("n_stocks", 0),
            }

    from app.db.database import async_session_maker
    from app.models.track import PipelineRun

    async with async_session_maker() as session:
        run_log = PipelineRun(
            run_type="train",
            status="success",
            params_snapshot=dict(LGB_PARAMS),
            results_summary=summary,
            git_commit_hash=git_hash,
            feature_count=len(feature_cols),
        )
        session.add(run_log)
        await session.commit()
    logger.info(f"训练日志已记录: {len(results)} 个赛道")


if __name__ == "__main__":
    asyncio.run(main())
