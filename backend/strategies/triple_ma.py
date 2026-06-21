"""
三均线多头排列策略.

来源: 经典趋势跟踪策略。短/中/长三条均线呈多头排列（短期>中期>长期）时买入，
出现死叉或空头排列时卖出。
"""

import numpy as np
import pandas as pd

from strategies.signal_base import SignalGenerator, AIEnhanceMixin


class TripleMAStrategy(SignalGenerator, AIEnhanceMixin):
    """三均线多头排列，可选 AI 增强"""

    def __init__(self, short: int = 5, mid: int = 20, long: int = 60,
                 top_n: int = 3, ai_enhanced: bool = False):
        self.params = {
            "short": short, "mid": mid, "long": long,
            "top_n": top_n, "ai_enhanced": ai_enhanced,
        }

    def generate(self, prices: pd.DataFrame, features=None, ai_scores=None) -> pd.DataFrame:
        prices = prices.sort_index()
        s, m, l, top_n = self.params["short"], self.params["mid"], self.params["long"], self.params["top_n"]

        result = []
        for date in prices.index:
            if date < prices.index[l + 1]:
                continue
            window = prices.loc[:date].iloc[-l - 1:]
            buy_list = []

            for code in prices.columns:
                close = window[code].dropna()
                if len(close) < l:
                    continue
                ma_s = close.rolling(s).mean().iloc[-1]
                ma_m = close.rolling(m).mean().iloc[-1]
                ma_l = close.rolling(l).mean().iloc[-1]

                if pd.isna(ma_s) or pd.isna(ma_m) or pd.isna(ma_l):
                    continue

                # 多头排列 + 刚形成（前一周期不是）
                bullish = ma_s > ma_m > ma_l
                close_s = close.iloc[-1]
                if bullish:
                    buy_list.append((code, (close_s - ma_l) / ma_l))

            buy_list.sort(key=lambda x: x[1], reverse=True)
            top = [x[0] for x in buy_list[:top_n]]
            if top:
                result.append({"date": date, "buy": top, "weights": {x: 1.0/len(top) for x in top}, "sell_all": False})

        out = pd.DataFrame(result).set_index("date") if result else pd.DataFrame()
        if self.params["ai_enhanced"]:
            out = self.enhance_with_ai(out, ai_scores, top_n)
        return out
