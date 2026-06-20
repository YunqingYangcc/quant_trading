#!/usr/bin/env python3
"""
Phase I: 基本面数据接入（akshare）

获取 PE/PB/ROE/毛利率/资产负债率等基本面指标，
存储到 feature_store 表供后续特征工程使用。

用法:
    cd backend && python3 ../scripts/fetch_fundamentals.py
"""
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# 要提取的基本面字段
FUNDAMENTAL_FIELDS = [
    "摊薄每股收益(元)", "每股净资产_调整前(元)", "每股经营性现金流(元)",
    "净资产收益率(%)", "主营业务收入增长率(%)", "净利润增长率(%)",
    "净资产增长率(%)", "总资产增长率(%)",
    "销售毛利率(%)", "销售净利率(%)",
    "资产负债率(%)", "流动比率", "速动比率",
    "应收账款周转率(次)", "存货周转率(次)", "总资产周转率(次)",
]


async def main():
    import akshare as ak
    import pandas as pd
    import numpy as np

    from app.db.database import async_session_maker
    from app.models.track import TrackStock, FeatureStore

    # 1. 获取所有股票代码
    async with async_session_maker() as session:
        from sqlalchemy import select
        result = await session.execute(select(TrackStock))
        stocks = result.scalars().all()

    logger.info(f"共 {len(stocks)} 只股票")

    # 2. 逐只股票获取基本面数据
    total_rows = 0
    for stock in stocks:
        code = stock.code
        symbol = code.split(".")[0]  # 002371.SZ → 002371
        try:
            df = ak.stock_financial_analysis_indicator(symbol=symbol, start_year="2018")
        except Exception as e:
            logger.warning(f"{code}: 基本面获取失败 — {e}")
            continue

        if df.empty:
            continue

        # 提取需要的字段
        cols = ["日期"] + [c for c in FUNDAMENTAL_FIELDS if c in df.columns]
        df = df[cols].copy()
        df.columns = [c.replace("(", "_").replace(")", "").replace("%", "pct").replace(" ", "_")
                      for c in df.columns]

        # 将季度日期转为 datetime
        df["trade_date"] = pd.to_datetime(df["日期"], errors="coerce")
        df = df.dropna(subset=["trade_date"]).sort_values("trade_date")

        if df.empty:
            continue

        # 3. 入库：每个季度一条特征记录
        async with async_session_maker() as session:
            saved = 0
            for _, row in df.iterrows():
                date_str = row["trade_date"].strftime("%Y-%m-%d")
                features = {}
                for c in df.columns:
                    if c in ("日期", "trade_date"):
                        continue
                    val = row[c]
                    if pd.notna(val) and np.isfinite(val):
                        features[f"fund_{c}"] = round(float(val), 4)

                if features:
                    # 检查是否已存在
                    existing = await session.execute(
                        select(FeatureStore).where(
                            FeatureStore.stock_code == code,
                            FeatureStore.trade_date == date_str
                        ).limit(1)
                    )
                    existing_row = existing.scalar_one_or_none()
                    if existing_row:
                        # 追加基本面字段
                        merged = dict(existing_row.features or {})
                        merged.update(features)
                        existing_row.features = merged
                    else:
                        session.add(FeatureStore(
                            stock_code=code,
                            trade_date=date_str,
                            features=features,
                        ))
                    saved += 1

            await session.commit()
            total_rows += saved
            logger.info(f"  {code} ({stock.name}): {saved} 条基本面记录")

    logger.info(f"\n完成! 共入库 {total_rows} 条基本面记录")


if __name__ == "__main__":
    asyncio.run(main())
