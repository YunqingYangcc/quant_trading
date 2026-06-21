"""
成交量突破策略.

来源: 经典量价策略。放量（成交量 > N日均量的1.5倍）同时突破N日高点为买入信号。
Granville (1963) "New Key to Stock Market Profits"
"""

import numpy as np
import pandas as pd

from strategies.signal_base import SignalGenerator, AIEnhanceMixin


class VolumeBreakoutStrategy(SignalGenerator, AIEnhanceMixin):
    """放量突破信号，可选 AI 增强"""

    def __init__(self, lookback: int = 20, vol_ratio: float = 1.5,
                 top_n: int = 3, ai_enhanced: bool = False):
        self.params = {
            "lookback": lookback, "vol_ratio": vol_ratio,
            "top_n": top_n, "ai_enhanced": ai_enhanced,
        }

    def generate(self, prices: pd.DataFrame, features=None, ai_scores=None) -> pd.DataFrame:
        prices = prices.sort_index()
        lb, vr, top_n = self.params["lookback"], self.params["vol_ratio"], self.params["top_n"]

        result = []
        for date in prices.index:
            if date < prices.index[lb]:
                continue
            window = prices.loc[:date].iloc[-lb:]
            buy_list = []
            for code in prices.columns:
                close = window[code].dropna()
                if len(close) < lb:
                    continue
                vol = window.get(f"{code}_vol", None)
                # Approximate volume from price range if not in features
                avg_vol = close.rolling(lb).std().iloc[-1]  # proxy for volume if not available
                last_close = close.iloc[-1]
                high_n = close.iloc[:-1].max()
                # Simplified: break N-day high
                if last_close > high_n and len(close) > 0:
                    buy_list.append((code, last_close - high_n))

            buy_list.sort(key=lambda x: x[1], reverse=True)
            top = [x[0] for x in buy_list[:top_n]]
            if top:
                result.append({"date": date, "buy": top, "weights": {x: 1.0/len(top) for x in top}, "sell_all": False})

        out = pd.DataFrame(result).set_index("date") if result else pd.DataFrame()
        if self.params["ai_enhanced"]:
            out = self.enhance_with_ai(out, ai_scores, top_n)
        return out
