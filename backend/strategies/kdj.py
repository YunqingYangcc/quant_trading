"""
KDJ 随机指标超卖反转策略.

来源: 经典技术指标策略。
K 线 < 20 超卖区金叉买入，K 线 > 80 超买区死叉卖出。
"""

import numpy as np
import pandas as pd

from strategies.signal_base import SignalGenerator, AIEnhanceMixin


class KDJStrategy(SignalGenerator, AIEnhanceMixin):
    """KDJ 超卖反转信号，可选 AI 增强"""

    def __init__(self, period: int = 9, oversold: float = 20, overbought: float = 80,
                 top_n: int = 3, ai_enhanced: bool = False):
        self.params = {
            "period": period, "oversold": oversold, "overbought": overbought,
            "top_n": top_n, "ai_enhanced": ai_enhanced,
        }

    @staticmethod
    def _calc_kdj(high, low, close, period):
        """计算 KDJ 指标"""
        lowest_low = low.rolling(window=period).min()
        highest_high = high.rolling(window=period).max()
        rsv = (close - lowest_low) / (highest_high - lowest_low + 1e-10) * 100
        k = rsv.ewm(com=2, adjust=False).mean()
        d = k.ewm(com=2, adjust=False).mean()
        j = 3 * k - 2 * d
        return k, d, j

    def generate(self, prices: pd.DataFrame, features=None, ai_scores=None) -> pd.DataFrame:
        prices = prices.sort_index()
        period, oversold, overbought, top_n = (
            self.params["period"], self.params["oversold"],
            self.params["overbought"], self.params["top_n"]
        )

        signals = []
        for code in prices.columns:
            c = prices[code].dropna()
            if len(c) < period + 1:
                continue
            # 用 close 近似的 high/low
            h = c.rolling(5).max()
            l = c.rolling(5).min()
            k, d, j = self._calc_kdj(h, l, c, period)

            buy_signal = (k < oversold) & (k > d) & (k.shift(1) <= d.shift(1))
            sell_signal = (k > overbought) & (k < d) & (k.shift(1) >= d.shift(1))

            for dt in buy_signal[buy_signal].index:
                signals.append({"date": dt, "code": code, "action": "buy", "reason": "kdj_oversold"})
            for dt in sell_signal[sell_signal].index:
                signals.append({"date": dt, "code": code, "action": "sell", "reason": "kdj_overbought"})

        return self._to_portfolio(prices, pd.DataFrame(signals), top_n, ai_scores)

    def _to_portfolio(self, prices, raw_signals, top_n, ai_scores):
        if raw_signals.empty:
            return pd.DataFrame()
        raw_signals = raw_signals.sort_values("date")
        result, held = [], []
        all_dates = prices.index.sort_values()
        sig_dates = set(raw_signals["date"].unique())
        for date in all_dates:
            if date in sig_dates:
                for _, s in raw_signals[raw_signals["date"] == date].iterrows():
                    if s["action"] == "buy" and s["code"] not in held:
                        held.append(s["code"])
                    elif s["action"] == "sell" and s["code"] in held:
                        held.remove(s["code"])
            buy_list = held[:top_n] if len(held) >= top_n else held
            if buy_list:
                result.append({"date": date, "buy": buy_list, "weights": {x: 1.0/len(buy_list) for x in buy_list}, "sell_all": False})

        out = pd.DataFrame(result).set_index("date") if result else pd.DataFrame()
        if self.params["ai_enhanced"]:
            out = self.enhance_with_ai(out, ai_scores, top_n)
        return out
