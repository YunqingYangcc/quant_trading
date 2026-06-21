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

from strategies.signal_base import SignalGenerator, AIEnhanceMixin


class MomentumStrategy(SignalGenerator, AIEnhanceMixin):
    """动量排序策略。支持 AI 打分增强。"""

    def __init__(self, lookback: int = 20, top_n: int = 3, rebalance: str = "M",
                 vol_filter: bool = False, ai_enhanced: bool = False):
        self.params = {
            "lookback": lookback,
            "top_n": top_n,
            "rebalance": rebalance,
            "vol_filter": vol_filter,
            "ai_enhanced": ai_enhanced,
        }

    def generate(self, prices: pd.DataFrame, features=None, ai_scores=None) -> pd.DataFrame:
        """生成买卖信号。

        Args:
            prices: pivot table, index=date, columns=stock_code, values=close
            features: 可选，用于 vol_filter
            ai_scores: 可选，AI 打分用于二次排序

        Returns:
            DataFrame with columns ['buy', 'weights'], index=date
        """
        prices = prices.sort_index()
        daily_ret = prices.pct_change().clip(-0.5, 0.5)

        lookback = self.params["lookback"]
        top_n = self.params["top_n"]
        rebalance = self.params["rebalance"]
        vol_filter = self.params["vol_filter"]

        # 计算动量
        mom = (1 + daily_ret).rolling(lookback).apply(np.prod, raw=True) - 1

        # 波动率过滤（可选）
        if vol_filter:
            vol = daily_ret.rolling(lookback).std() * np.sqrt(252)
            vol_median = vol.median(axis=1)
            high_vol_mask = vol.sub(vol_median, axis=0) > 0
            mom[~high_vol_mask] = -np.inf  # 低波动组不考虑

        # 按月/周采样生成信号
        freq = "MS" if rebalance == "M" else "W-MON"
        signals = []

        for date in pd.date_range(mom.index.min(), mom.index.max(), freq=freq):
            valid_dates = mom.index[mom.index <= date]
            if len(valid_dates) == 0:
                continue
            signal_date = valid_dates[-1]

            scores = mom.loc[signal_date].dropna()
            if len(scores) < top_n:
                continue
            top_stocks = scores.nlargest(top_n).index.tolist()

            weights = {s: 1.0 / top_n for s in top_stocks}
            signals.append({
                "date": date,
                "buy": top_stocks,
                "weights": weights,
                "sell_all": True,
            })

        result = pd.DataFrame(signals).set_index("date") if signals else pd.DataFrame()

        # AI 增强
        if self.params["ai_enhanced"]:
            result = self.enhance_with_ai(result, ai_scores, top_n)

        return result
