"""
等权持有策略（基线）。

最简单的策略：买入所有股票，等权持有，月频再平衡。
用于衡量「AI 模型是否真的比瞎买强」。
"""

import numpy as np
import pandas as pd

from strategies.signal_base import SignalGenerator


class EqualWeightStrategy(SignalGenerator):
    """等权持有全部股票。"""

    def generate(self, prices: pd.DataFrame, features=None, ai_scores=None) -> pd.DataFrame:
        """每月初重新等权分配。

        Returns:
            DataFrame with columns ['buy', 'weights'], index=date
        """
        prices = prices.sort_index()
        signals = []

        for date in pd.date_range(prices.index.min(), prices.index.max(), freq="MS"):
            valid_dates = prices.index[prices.index <= date]
            if len(valid_dates) == 0:
                continue
            signal_date = valid_dates[-1]

            # 所有当天有价格的股票
            available = prices.loc[signal_date].dropna()
            if len(available) == 0:
                continue
            stocks = available.index.tolist()
            weights = {s: 1.0 / len(stocks) for s in stocks}

            signals.append({
                "date": date,
                "buy": stocks,
                "weights": weights,
                "sell_all": True,
            })

        return pd.DataFrame(signals).set_index("date") if signals else pd.DataFrame()
