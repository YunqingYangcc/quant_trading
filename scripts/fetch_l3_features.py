#!/usr/bin/env python3
"""
L3 预期/资金流数据接入（P0 优先级）

按 factor-research 协议，逐层推进数据维度：
  L1 量价 → ✅ 已完成（75 技术指标）
  L2 基本面 → ✅ 已完成（16 个 fund_* 特征）
  L3 预期/资金流 → ★ 当前接入
  L4 另类数据 → 暂不接入

数据源：
  1. 北向资金（P0）— stock_hsgt_individual_em
  2. 融资融券（P1）— stock_margin_detail_sse/szse
  3. 业绩报表（P1）— stock_yjbb_em（补充季度环比维度）

衍生因子（经济学逻辑见 factor-research Skill）：
  - hsgt_hold_pct：北向持仓占流通股比例（外资定价权）
  - hsgt_flow_5d/20d：5/20 日净增持速率（聪明钱方向）
  - hsgt_momentum：增持加速度（二次导数，趋势拐点）
  - margin_balance：融资余额（杠杆情绪）
  - margin_change_5d/20d：融资余额变化率
  - qoq_revenue_growth：营收季度环比（已有同比，补充环比）
  - qoq_profit_growth：利润季度环比

用法:
    cd backend && python3 ../scripts/fetch_l3_features.py
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── 路径：切到 backend 确保 SQLite 路径正确 ──
os.chdir(str(PROJECT_ROOT / "backend"))

# ── 配置 ──
REQUEST_DELAY = 0.5  # API 间隔（秒），防限流
HSGT_START = "20180101"  # 北向数据起始日
CACHE_DIR = PROJECT_ROOT / "datas" / "fundamentals"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


async def get_our_stocks() -> list[tuple[str, str]]:
    """获取赛道池所有股票 (code, name). 返回纯数字代码（去后缀）。"""
    from app.db.database import async_session_maker
    from sqlalchemy import select
    from app.models.track import TrackStock

    async with async_session_maker() as session:
        result = await session.execute(select(TrackStock))
        stocks = result.scalars().all()
    # 去掉 .SH/.SZ 后缀
    return [(s.code.split(".")[0], s.name) for s in stocks]


# ══════════════════════════════════════════════════════════════
# 数据源 1：北向资金（P0）
# ══════════════════════════════════════════════════════════════

def fetch_hsgt_single(code: str, name: str, retries: int = 3) -> pd.DataFrame | None:
    """拉取单只股票北向资金日数据."""
    import akshare as ak

    cache_file = CACHE_DIR / f"hsgt_{code}.csv"
    # 有缓存且不超过 1 天 → 直接用
    if cache_file.exists():
        age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
        if age_hours < 24:
            logger.info(f"  {code} {name}: 使用缓存 ({age_hours:.0f}h前)")
            df = pd.read_csv(cache_file)
            df["持股日期"] = pd.to_datetime(df["持股日期"])
            return df

    for attempt in range(retries):
        try:
            df = ak.stock_hsgt_individual_em(symbol=code)
            if df is None or df.empty:
                logger.debug(f"  {code} {name}: 无北向数据")
                return None
            # 标准化列名
            df.columns = [c.strip() for c in df.columns]
            df["持股日期"] = pd.to_datetime(df["持股日期"])
            df = df.sort_values("持股日期")
            # 缓存
            df.to_csv(cache_file, index=False)
            logger.info(f"  {code} {name}: {len(df)} 条北向记录")
            return df
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                logger.warning(f"  {code} {name}: 北向数据获取失败 - {e}")
    return None


async def fetch_all_hsgt(stocks: list[tuple[str, str]]) -> dict[str, pd.DataFrame]:
    """批量拉取北向资金数据."""
    logger.info(f"\n{'='*50}")
    logger.info("数据源 1/3：北向资金 (P0)")
    logger.info(f"{'='*50}")

    results = {}
    for i, (code, name) in enumerate(stocks, 1):
        logger.info(f"[{i}/{len(stocks)}] {code} {name}")
        df = fetch_hsgt_single(code, name)
        if df is not None and not df.empty:
            results[code] = df
        time.sleep(REQUEST_DELAY)

    logger.info(f"北向数据: {len(results)}/{len(stocks)} 只股票有数据")
    return results


# ══════════════════════════════════════════════════════════════
# 数据源 2：融资融券（P1）
# ══════════════════════════════════════════════════════════════

def fetch_margin_data(stock_codes: list[str], lookback_years: int = 3) -> pd.DataFrame:
    """拉取赛道股票的融资融券数据（月度采样，每日量太大）."""
    import akshare as ak

    cache_file = CACHE_DIR / "margin_data.csv"
    if cache_file.exists():
        age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
        if age_hours < 24:
            logger.info("  使用融资融券缓存")
            df = pd.read_csv(cache_file)
            df["date"] = pd.to_datetime(df["date"])
            return df

    # 采样：每月取第 15 日附近
    end_date = datetime.now()
    dates = []
    for year in range(end_date.year - lookback_years, end_date.year + 1):
        for month in range(1, 13):
            d = datetime(year, month, min(15, 28))
            if d <= end_date:
                dates.append(d.strftime("%Y%m%d"))

    all_records = []
    code_set = set(stock_codes)

    logger.info(f"  拉取融资融券数据 ({len(dates)} 个采样日)...")
    for i, date_str in enumerate(dates):
        if i % 12 == 0:
            logger.info(f"    [{i+1}/{len(dates)}] {date_str[:6]}...")
        time.sleep(REQUEST_DELAY * 0.5)

        try:
            df_sse = ak.stock_margin_detail_sse(date=date_str)
            df_szse = ak.stock_margin_detail_szse(date=date_str)
            df_all = pd.concat([df_sse, df_szse], ignore_index=True)
            df_all.columns = [c.strip() for c in df_all.columns]

            # 筛选赛道股票
            code_col = "标的证券代码"
            if code_col not in df_all.columns:
                for c in df_all.columns:
                    if "代码" in str(c):
                        code_col = c
                        break
            mask = df_all[code_col].isin(code_set)
            df_filtered = df_all[mask]
            for _, row in df_filtered.iterrows():
                all_records.append({
                    "date": pd.Timestamp(date_str),
                    "stock_code": row[code_col],
                    "margin_balance": float(row.get("融资余额", 0) or 0),
                    "margin_buy": float(row.get("融资买入额", 0) or 0),
                    "margin_repay": float(row.get("融资偿还额", 0) or 0),
                    "short_volume": float(row.get("融券余量", 0) or 0),
                })
        except Exception as e:
            logger.debug(f"    {date_str}: {e}")
            continue

    df = pd.DataFrame(all_records)
    if not df.empty:
        df.to_csv(cache_file, index=False)
        logger.info(f"  融资融券: {len(df)} 条记录 (覆盖 {df['stock_code'].nunique()} 只股票)")
    else:
        logger.info("  融资融券: 无赛道股票数据")
    return df


# ══════════════════════════════════════════════════════════════
# 数据源 3：业绩报表（补充季度环比）（P1）
# ══════════════════════════════════════════════════════════════

def fetch_quarterly_reports(stock_codes: list[str]) -> pd.DataFrame:
    """拉取季度业绩报表，提取环比增长维度."""
    import akshare as ak

    cache_file = CACHE_DIR / "quarterly_reports.csv"
    if cache_file.exists():
        age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
        if age_hours < 72:  # 季度数据 3 天有效
            logger.info("  使用业绩报表缓存")
            return pd.read_csv(cache_file)

    code_set = set(stock_codes)
    all_frames = []
    # 拉取近 3 年季度报表
    for year in range(2022, 2027):
        for quarter in ["0331", "0630", "0930", "1231"]:
            date_str = f"{year}{quarter}"
            try:
                df = ak.stock_yjbb_em(date=date_str)
                df.columns = [c.strip() for c in df.columns]
                mask = df["股票代码"].isin(code_set)
                df_filtered = df[mask]
                if not df_filtered.empty:
                    all_frames.append(df_filtered)
                time.sleep(REQUEST_DELAY * 0.5)
            except Exception as e:
                logger.debug(f"  {date_str}: {e}")
                continue

    if not all_frames:
        return pd.DataFrame()

    df = pd.concat(all_frames, ignore_index=True)
    if not df.empty:
        df.to_csv(cache_file, index=False)
    logger.info(f"  业绩报表: {len(df)} 条 ({len(df)//len(stock_codes)} 季度/股)")
    return df


# ══════════════════════════════════════════════════════════════
# 存储到 FeatureStore
# ══════════════════════════════════════════════════════════════

async def store_l3_features(
    hsgt_data: dict[str, pd.DataFrame],
    margin_data: pd.DataFrame,
    quarterly_data: pd.DataFrame,
    stocks: list[tuple[str, str]],
):
    """将 L3 因子写入 FeatureStore 表（前缀 hsgt_/margin_/qoq_）."""
    from app.db.database import async_session_maker
    from app.models.track import FeatureStore

    # 构建 {stock_code: {date: {feature: value}}}
    store_map: dict[str, dict[pd.Timestamp, dict[str, float]]] = {}

    # ── 北向资金因子 ──
    for code, df in hsgt_data.items():
        if df.empty:
            continue
        df = df.sort_values("持股日期")
        # 持仓占比
        df["hsgt_hold_pct"] = df.get("持股数量占A股百分比", 0).astype(float)
        # 增持金额
        df["hsgt_flow_raw"] = df.get("今日增持资金", 0).astype(float)
        # 5日/20日净增持速率
        df["hsgt_flow_5d"] = df["hsgt_flow_raw"].rolling(5).sum()
        df["hsgt_flow_20d"] = df["hsgt_flow_raw"].rolling(20).sum()
        # 增持加速度（20日 - 5日）
        df["hsgt_momentum"] = df["hsgt_flow_5d"] - df["hsgt_flow_20d"].shift(5)

        for _, row in df.iterrows():
            date = row["持股日期"]
            store_map.setdefault(code, {}).setdefault(date, {}).update({
                "hsgt_hold_pct": _safe_float(row.get("hsgt_hold_pct")),
                "hsgt_flow_5d": _safe_float(row.get("hsgt_flow_5d")),
                "hsgt_flow_20d": _safe_float(row.get("hsgt_flow_20d")),
                "hsgt_momentum": _safe_float(row.get("hsgt_momentum")),
            })

    # ── 融资融券因子 ──
    if not margin_data.empty:
        for code, grp in margin_data.groupby("stock_code"):
            grp = grp.sort_values("date")
            grp["margin_change_1m"] = grp["margin_balance"].pct_change()
            grp["margin_change_3m"] = grp["margin_balance"].pct_change(3)
            grp["margin_intensity"] = grp["margin_buy"] / (grp["margin_balance"] + 1)
            for _, row in grp.iterrows():
                date = row["date"]
                store_map.setdefault(code, {}).setdefault(date, {}).update({
                    "margin_change_1m": _safe_float(row.get("margin_change_1m")),
                    "margin_change_3m": _safe_float(row.get("margin_change_3m")),
                    "margin_intensity": _safe_float(row.get("margin_intensity")),
                    "margin_balance": _safe_float(row.get("margin_balance")),
                })

    # ── 季度环比因子 ──
    if not quarterly_data.empty:
        col_map = {
            "营业总收入-季度环比增长": "qoq_revenue_growth",
            "净利润-季度环比增长": "qoq_profit_growth",
        }
        for _, row in quarterly_data.iterrows():
            code = row["股票代码"]
            # 用最新公告日期作为对齐日期
            announce_date = pd.Timestamp(row.get("最新公告日期", row.get("最新公告日期", "")))
            for src_col, tgt_col in col_map.items():
                val = row.get(src_col)
                if val and not pd.isna(val):
                    store_map.setdefault(code, {}).setdefault(announce_date, {})[tgt_col] = float(val)

    # ── 写入数据库 ──
    logger.info(f"\n写入 FeatureStore (前缀 hsgt_/margin_/qoq_)...")
    async with async_session_maker() as session:
        total = 0
        for code, date_map in store_map.items():
            for date, features in date_map.items():
                if not features:
                    continue
                # 查找已有记录（按 stock_code + trade_date）
                from sqlalchemy import select

                date_str = date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)[:10]
                result = await session.execute(
                    select(FeatureStore).where(
                        FeatureStore.stock_code == code,
                        FeatureStore.trade_date == date_str,
                    )
                )
                existing = result.scalars().first()
                if existing:
                    # 合并特征
                    merged = {**existing.features, **features}
                    existing.features = merged
                else:
                    record = FeatureStore(
                        stock_code=code,
                        trade_date=date_str,
                        features=features,
                        feature_version="v2_l3",
                    )
                    session.add(record)
                total += 1

            if total % 5000 == 0:
                await session.commit()
                logger.info(f"  已写入 {total} 条...")

        await session.commit()

    logger.info(f"✅ L3 特征已写入 FeatureStore: {total} 条记录, {len(store_map)} 只股票")


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return f if np.isfinite(f) else None
    except (ValueError, TypeError):
        return None


# ══════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════

async def main():
    from app.db.database import ensure_database_ready

    await ensure_database_ready()

    stocks = await get_our_stocks()
    logger.info(f"赛道池: {len(stocks)} 只股票")
    stock_codes = [c for c, _ in stocks]

    # ── 1. 北向资金 ──
    hsgt_data = await fetch_all_hsgt(stocks)

    # ── 2. 融资融券 ──
    logger.info(f"\n{'='*50}")
    logger.info("数据源 2/3：融资融券 (P1)")
    logger.info(f"{'='*50}")
    margin_data = fetch_margin_data(stock_codes)

    # ── 3. 业绩报表 ──
    logger.info(f"\n{'='*50}")
    logger.info("数据源 3/3：业绩报表季度环比 (P1)")
    logger.info(f"{'='*50}")
    quarterly_data = fetch_quarterly_reports(stock_codes)

    # ── 存储 ──
    await store_l3_features(hsgt_data, margin_data, quarterly_data, stocks)

    # ── 汇总 ──
    hsgt_codes = set(hsgt_data.keys())
    margin_codes = set(margin_data["stock_code"].unique()) if not margin_data.empty else set()
    qoq_codes = set(quarterly_data["股票代码"].unique()) if not quarterly_data.empty else set()

    logger.info(f"\n{'='*50}")
    logger.info("L3 数据接入完成")
    logger.info(f"{'='*50}")
    logger.info(f"  北向资金: {len(hsgt_codes)}/{len(stocks)} 只")
    logger.info(f"  融资融券: {len(margin_codes)}/{len(stocks)} 只")
    logger.info(f"  业绩环比: {len(qoq_codes)}/{len(stocks)} 只")
    logger.info(f"  新增特征前缀: hsgt_ (4), margin_ (4), qoq_ (2) ≈ 10 个")
    logger.info(f"  下一步: cd backend && python3 scripts/screen_factors.py")


if __name__ == "__main__":
    asyncio.run(main())
