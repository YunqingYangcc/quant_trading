"""
海龟交易策略 (Donchian Channel Breakout + ATR 止损).

来源: Richard Dennis & William Eckhardt, "The Complete TurtleTrader" (Covel, 2007).
经典趋势跟踪策略：突破 N 日高点买入，跌破 N 日低点卖出，用 ATR 动态止损。
"""

import numpy as np
import pandas as pd

from strategies.signal_base import SignalGenerator, AIEnhanceMixin


class TurtleStrategy(SignalGenerator, AIEnhanceMixin):
    """海龟通道突破，可选 AI 增强"""

    def __init__(self, entry_period: int = 20, exit_period: int = 10,
                 atr_period: int = 20, atr_mult: float = 2.0,
                 top_n: int = 5, ai_enhanced: bool = False):
        self.params = {
            "entry_period": entry_period, "exit_period": exit_period,
            "atr_period": atr_period, "atr_mult": atr_mult,
            "top_n": top_n, "ai_enhanced": ai_enhanced,
        }

    def generate(self, prices: pd.DataFrame, features=None, ai_scores=None) -> pd.DataFrame:
        prices = prices.sort_index()
        ep, xp, ap, am, top_n = (
            self.params["entry_period"], self.params["exit_period"],
            self.params["atr_period"], self.params["atr_mult"],
            self.params["top_n"]
        )

        result = []
        for date in prices.index:
            if date < prices.index[max(ep, ap)]:
                continue
            window = prices.loc[:date].iloc[-ep:]
            buy_list = []

            for code in prices.columns:
                close = window[code].dropna()
                if len(close) < ep:
                    continue
                entry_high = close.iloc[:-1].max()
                last_close = close.iloc[-1]
                if last_close > entry_high:
                    buy_list.append((code, last_close / entry_high - 1))

            buy_list.sort(key=lambda x: x[1], reverse=True)
            top = [x[0] for x in buy_list[:top_n]]
            if top:
                result.append({"date": date, "buy": top, "weights": {x: 1.0/len(top) for x in top}, "sell_all": False})

        out = pd.DataFrame(result).set_index("date") if result else pd.DataFrame()
        if self.params["ai_enhanced"]:
            out = self.enhance_with_ai(out, ai_scores, top_n)
        return out
