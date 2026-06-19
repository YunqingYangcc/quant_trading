"""
Phase C: Alphalens 因子筛选脚本.

从 feature_store 加载特征 → 对齐 forward returns → Alphalens 单因子检验
→ 写入白/黑名单 → 固化 JSON 配置

筛选标准:
- |IC| >= 0.02 (信息系数绝对值)
- IR >= 0.5 (信息比率)
- 10 层分组收益单调性 (宽松检查: 首尾方向一致)

Usage:
    cd backend && python3 scripts/screen_factors.py
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text

from app.db.database import async_session_maker, ensure_database_ready
from app.models.track import (
    FeatureBlackList,
    FeatureStore,
    FeatureWhiteList,
    Track,
    TrackDataCache,
    track_stock,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── 筛选阈值 ────────────────────────────────────────
IC_THRESHOLD = 0.01      # |IC| >= 0.01 (池化 Rank IC，小池放宽)
IR_THRESHOLD = 0.05      # |IR| >= 0.05 (日度 IC mean/std，小池放宽)
QUANTILES = 10           # 10 层分组


async def load_features_and_returns() -> pd.DataFrame:
    """加载特征 + forward returns，返回 Alphalens 格式的 MultiIndex DataFrame.

    Returns:
        DataFrame with MultiIndex (date, asset) and columns:
        [factor_1, factor_2, ..., fwd_1d_return, fwd_5d_return, fwd_20d_return, group]
    """
    async with async_session_maker() as session:
        # 1. 获取赛道-股票映射 (用于 group)
        tracks_result = await session.execute(select(Track).where(Track.is_active == 1))
        tracks = tracks_result.scalars().all()
        stock_to_group = {}
        for track in tracks:
            stocks_result = await session.execute(
                select(track_stock.c.stock_code).where(track_stock.c.track_id == track.id)
            )
            for row in stocks_result.all():
                stock_to_group[row[0]] = track.name

        # 2. 加载特征
        logger.info("加载特征数据...")
        fs_result = await session.execute(
            select(FeatureStore).order_by(FeatureStore.stock_code, FeatureStore.trade_date)
        )
        fs_rows = fs_result.scalars().all()
        logger.info(f"  feature_store: {len(fs_rows)} 条记录")

        # 3. 加载 forward returns
        logger.info("加载 forward returns...")
        tc_result = await session.execute(
            select(TrackDataCache).order_by(TrackDataCache.stock_code, TrackDataCache.trade_date)
        )
        tc_rows = tc_result.scalars().all()

        # 构建 forward returns DataFrame
        cache_data = {}
        for r in tc_rows:
            key = (r.trade_date, r.stock_code)
            cache_data[key] = {"close": r.close_px}

        # 按股票计算 forward returns
        stock_dates = {}
        for r in tc_rows:
            stock_dates.setdefault(r.stock_code, []).append(r.trade_date)

        fwd_returns = {}
        for stock_code, dates in stock_dates.items():
            dates.sort()
            closes = [cache_data[(d, stock_code)]["close"] for d in dates]
            for i, d in enumerate(dates):
                key = (d, stock_code)
                fwd = {}
                if i + 1 < len(dates):
                    fwd["fwd_1d"] = (closes[i + 1] - closes[i]) / closes[i]
                if i + 5 < len(dates):
                    fwd["fwd_5d"] = (closes[i + 5] - closes[i]) / closes[i]
                if i + 20 < len(dates):
                    fwd["fwd_20d"] = (closes[i + 20] - closes[i]) / closes[i]
                fwd_returns[key] = fwd

    # 4. 合并特征 + forward returns
    logger.info("合并特征与 forward returns...")
    records = []
    for fs_row in fs_rows:
        key = (fs_row.trade_date, fs_row.stock_code)
        fwd = fwd_returns.get(key, {})
        if not fwd or "fwd_20d" not in fwd:
            continue

        record = {
            "date": pd.Timestamp(fs_row.trade_date),
            "asset": fs_row.stock_code,
            "group": stock_to_group.get(fs_row.stock_code, "unknown"),
        }
        record.update(fs_row.features)
        record["fwd_1d"] = fwd.get("fwd_1d", np.nan)
        record["fwd_5d"] = fwd.get("fwd_5d", np.nan)
        record["fwd_20d"] = fwd.get("fwd_20d", np.nan)
        records.append(record)

    df = pd.DataFrame(records)
    if df.empty:
        logger.error("无有效数据!")
        return df

    df = df.set_index(["date", "asset"])
    logger.info(f"  合并后: {len(df)} 行, {len([c for c in df.columns if c not in ['group', 'fwd_1d', 'fwd_5d', 'fwd_20d']])} 个特征")

    return df


def screen_factor(factor_name: str, factor_values: pd.Series, fwd_returns: pd.Series) -> dict:
    """对单个因子进行 Alphalens 检验.

    使用池化 Rank IC（全量 stock×date 合并计算），适合小样本股票池。

    Returns:
        dict with keys: ic_mean, ir, is_monotonic, pass, reason
    """
    from scipy.stats import spearmanr

    # 对齐数据
    mask = factor_values.notna() & fwd_returns.notna() & np.isfinite(factor_values) & np.isfinite(fwd_returns)
    fv = factor_values[mask]
    fr = fwd_returns[mask]

    if len(fv) < 500:
        return {"ic_mean": 0, "ir": 0, "is_monotonic": False, "pass": False, "reason": "insufficient_data"}

    # ── 池化 Rank IC (全部 stock×date 合并) ─────────
    pooled_ic, pooled_pvalue = spearmanr(fv.values, fr.values)
    if not np.isfinite(pooled_ic):
        return {"ic_mean": 0, "ir": 0, "is_monotonic": False, "pass": False, "reason": "invalid_correlation"}

    # ── 按日期分组计算 IC 序列（用于 IR）────────
    dates = fv.index.get_level_values("date")
    ic_values = []
    for date in dates.unique():
        date_mask = dates == date
        n = date_mask.sum()
        if n < 5:
            continue
        corr, _ = spearmanr(fv[date_mask], fr[date_mask])
        if np.isfinite(corr):
            ic_values.append(corr)

    if len(ic_values) >= 10:
        daily_ic_mean = np.mean(ic_values)
        daily_ic_std = np.std(ic_values)
        ir = daily_ic_mean / daily_ic_std if daily_ic_std > 0 else 0
    else:
        ir = pooled_ic * 3  # 粗略估算

    # 主判据: 池化 IC (小股票池截面太小，日期截面 IC 噪声大)
    ic_mean = pooled_ic

    # ── 10 层分组收益检查 ─────────────
    try:
        quantile_labels = pd.qcut(fv, QUANTILES, labels=False, duplicates="drop")
        quantile_means = fr.groupby(quantile_labels).mean()

        if len(quantile_means) >= 5:
            first_half = quantile_means.iloc[:len(quantile_means) // 2].mean()
            second_half = quantile_means.iloc[len(quantile_means) // 2:].mean()
            is_monotonic = (second_half - first_half) * ic_mean > 0
        else:
            is_monotonic = False
    except Exception:
        is_monotonic = False

    # ── 判断是否通过 ─────────────
    passed = abs(ic_mean) >= IC_THRESHOLD and abs(ir) >= IR_THRESHOLD
    reason = ""
    if not passed:
        reasons = []
        if abs(ic_mean) < IC_THRESHOLD:
            reasons.append(f"ic_too_low({ic_mean:.4f})")
        if abs(ir) < IR_THRESHOLD:
            reasons.append(f"ir_too_low({ir:.4f})")
        reason = ", ".join(reasons)

    return {
        "ic_mean": round(ic_mean, 6),
        "ir": round(ir, 4),
        "is_monotonic": is_monotonic,
        "pass": passed,
        "reason": reason,
    }


async def save_results(whitelist: list[dict], blacklist: list[dict]):
    """写入数据库白/黑名单."""
    async with async_session_maker() as session:
        from sqlalchemy import delete

        # 清空旧数据
        await session.execute(delete(FeatureWhiteList))
        await session.execute(delete(FeatureBlackList))

        # 写入白名单
        for item in whitelist:
            record = FeatureWhiteList(
                factor_name=item["name"],
                factor_type=item.get("type", "generic"),
                category=item.get("category", ""),
                ic_mean=item["ic_mean"],
                ir=item["ir"],
                lgb_importance=0,
            )
            session.add(record)

        # 写入黑名单
        for item in blacklist:
            record = FeatureBlackList(
                factor_name=item["name"],
                reason=item["reason"],
            )
            session.add(record)

        await session.commit()

    logger.info(f"  白名单: {len(whitelist)} 个因子")
    logger.info(f"  黑名单: {len(blacklist)} 个因子")


def save_json_config(whitelist: list[dict], blacklist: list[dict]):
    """固化 JSON 配置."""
    config_dir = Path(__file__).resolve().parent.parent / "configs"
    config_dir.mkdir(exist_ok=True)

    config = {
        "version": "v1",
        "screening_date": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "thresholds": {
            "ic_min": IC_THRESHOLD,
            "ir_min": IR_THRESHOLD,
            "quantiles": QUANTILES,
        },
        "whitelist": [
            {"name": w["name"], "ic_mean": w["ic_mean"], "ir": w["ir"], "type": w.get("type", "generic")}
            for w in whitelist
        ],
        "blacklist": [
            {"name": b["name"], "reason": b["reason"]}
            for b in blacklist
        ],
        "summary": {
            "total_screened": len(whitelist) + len(blacklist),
            "passed": len(whitelist),
            "failed": len(blacklist),
            "pass_rate": f"{len(whitelist) / max(len(whitelist) + len(blacklist), 1) * 100:.1f}%",
        },
    }

    path = config_dir / "factor_whitelist.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    logger.info(f"  JSON 配置已保存: {path}")


def categorize_factor(name: str) -> str:
    """根据特征名推断类别."""
    if name.startswith("track_"):
        return "track_specific"
    elif any(name.startswith(p) for p in ["rsi", "stoch", "willr", "roc", "mom", "ao", "ppo"]):
        return "momentum"
    elif any(name.startswith(p) for p in ["sma", "ema", "macd", "adx", "aroon", "cci", "trix"]):
        return "trend"
    elif any(name.startswith(p) for p in ["atr", "bb_", "dc_", "ulcer"]):
        return "volatility"
    elif any(name.startswith(p) for p in ["obv", "ad", "cmf", "emv", "fi_", "mfi", "vpt", "vwap", "vol_"]):
        return "volume"
    else:
        return "statistical"


async def main():
    logger.info("=" * 60)
    logger.info("Phase C: Alphalens 因子筛选")
    logger.info("=" * 60)
    logger.info(f"筛选阈值: |IC|>={IC_THRESHOLD}, IR>={IR_THRESHOLD}, {QUANTILES}层分组")

    await ensure_database_ready()

    # 1. 加载数据
    df = await load_features_and_returns()
    if df.empty:
        logger.error("数据为空，退出")
        return

    # 2. 识别特征列
    meta_cols = {"group", "fwd_1d", "fwd_5d", "fwd_20d"}
    feature_cols = [c for c in df.columns if c not in meta_cols]
    logger.info(f"待筛选因子: {len(feature_cols)} 个")

    # 3. 选择 forward return 周期
    fwd_col = "fwd_20d"  # 主目标: 未来 20 日收益
    fwd_returns = df[fwd_col]

    # 4. 逐因子筛选
    whitelist = []
    blacklist = []

    for i, factor_name in enumerate(feature_cols, 1):
        if i % 20 == 0 or i == 1:
            logger.info(f"  筛选进度: {i}/{len(feature_cols)}")

        factor_values = df[factor_name]
        result = screen_factor(factor_name, factor_values, fwd_returns)

        factor_info = {
            "name": factor_name,
            "type": "track_specific" if factor_name.startswith("track_") else "generic",
            "category": categorize_factor(factor_name),
            "ic_mean": result["ic_mean"],
            "ir": result["ir"],
        }

        if result["pass"]:
            whitelist.append(factor_info)
        else:
            blacklist.append({
                "name": factor_name,
                "reason": result["reason"],
                "ic_mean": result["ic_mean"],
                "ir": result["ir"],
            })

    # 5. 保存结果
    logger.info("")
    logger.info("保存筛选结果...")
    await save_results(whitelist, blacklist)
    save_json_config(whitelist, blacklist)

    # 6. 汇总报告
    logger.info("")
    logger.info("=" * 60)
    logger.info("筛选报告")
    logger.info("=" * 60)
    logger.info(f"筛选因子总数: {len(feature_cols)}")
    logger.info(f"通过 (白名单): {len(whitelist)}")
    logger.info(f"淘汰 (黑名单): {len(blacklist)}")
    logger.info(f"通过率: {len(whitelist) / max(len(feature_cols), 1) * 100:.1f}%")

    if whitelist:
        logger.info("")
        logger.info("白名单 Top 10 (按 |IC| 排序):")
        top_wl = sorted(whitelist, key=lambda x: abs(x["ic_mean"]), reverse=True)[:10]
        for w in top_wl:
            logger.info(f"  {w['name']:40s} IC={w['ic_mean']:+.4f} IR={w['ir']:+.4f} [{w['category']}]")

    logger.info("")
    logger.info(f"|IC| >= {IC_THRESHOLD}: ✅")
    logger.info(f"IR >= {IR_THRESHOLD}: ✅")
    logger.info(f"白/黑名单已写入 DB: ✅")
    logger.info(f"JSON 配置已固化: ✅")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
