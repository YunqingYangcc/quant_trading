"""
动量策略。

论文来源:
  - Jegadeesh & Titman (1993) "Returns to Buying Winners and Selling Losers"
  - Moskowitz, Ooi & Pedersen (2012) "Time Series Momentum"

A股适配:
  - 动量周期从 12 月缩短到 20/60 日（A 股动量衰减快）
  - 月频/周频调仓
  - 涨跌停过滤
"""

import numpy as np
import pandas as pd


class MomentumStrategy:
    """动量排序策略。"""

    def __init__(self, lookback: int = 20, top_n: int = 3, rebalance: str = "M", vol_filter: bool = False):
        self.lookback = lookback
        self.top_n = top_n
        self.rebalance = rebalance  # M=月频 W=周频
        self.vol_filter = vol_filter  # 是否只在高波动组中选

    def generate_signals(self, prices: pd.DataFrame, features: pd.DataFrame | None = None) -> pd.DataFrame:
        """生成买卖信号。

        Args:
            prices: pivot table, index=date, columns=stock_code, values=close
            features: 可选，用于 vol_filter

        Returns:
            DataFrame with columns ['buy', 'weights'], index=date
        """
        prices = prices.sort_index()
        daily_ret = prices.pct_change().clip(-0.5, 0.5)

        # 计算动量
        mom = (1 + daily_ret).rolling(self.lookback).apply(np.prod, raw=True) - 1

        # 波动率过滤（可选）
        if self.vol_filter:
            vol = daily_ret.rolling(self.lookback).std() * np.sqrt(252)
            vol_median = vol.median(axis=1)
            high_vol_mask = vol.sub(vol_median, axis=0) > 0
            mom[~high_vol_mask] = -np.inf  # 低波动组不考虑

        # 按月/周采样生成信号
        freq = "MS" if self.rebalance == "M" else "W-MON"
        signals = []

        for date in pd.date_range(mom.index.min(), mom.index.max(), freq=freq):
            # 找到最近的有效日期
            valid_dates = mom.index[mom.index <= date]
            if len(valid_dates) == 0:
                continue
            signal_date = valid_dates[-1]

            # 排名选 Top-N
            scores = mom.loc[signal_date].dropna()
            if len(scores) < self.top_n:
                continue
            top_stocks = scores.nlargest(self.top_n).index.tolist()

            # 等权分配
            weights = {s: 1.0 / self.top_n for s in top_stocks}
            signals.append({
                "date": date,
                "buy": top_stocks,
                "weights": weights,
                "sell_all": True,
            })

        return pd.DataFrame(signals).set_index("date") if signals else pd.DataFrame()
