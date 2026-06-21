"""
布林带缩口突破策略.

来源: John Bollinger "Bollinger on Bollinger Bands" (2001).
布林带宽度收缩至极低水平后，向上突破上轨买入，向下突破下轨卖出。
缩口意味着低波动率积累，突破意味着方向选择。
"""

import numpy as np
import pandas as pd

from strategies.signal_base import SignalGenerator, AIEnhanceMixin


class BollingerSqueezeStrategy(SignalGenerator, AIEnhanceMixin):
    """布林缩口突破信号，可选 AI 增强"""

    def __init__(self, period: int = 20, std_dev: float = 2.0,
                 squeeze_threshold: float = 0.1, top_n: int = 3,
                 ai_enhanced: bool = False):
        self.params = {
            "period": period, "std_dev": std_dev,
            "squeeze_threshold": squeeze_threshold,
            "top_n": top_n, "ai_enhanced": ai_enhanced,
        }

    def generate(self, prices: pd.DataFrame, features=None, ai_scores=None) -> pd.DataFrame:
        prices = prices.sort_index()
        p, sd, th, top_n = self.params["period"], self.params["std_dev"], self.params["squeeze_threshold"], self.params["top_n"]

        result = []
        for code in prices.columns:
            close = prices[code].dropna()
            if len(close) < p * 3:
                continue
            sma = close.rolling(p).mean()
            std = close.rolling(p).std()
            upper = sma + sd * std
            lower = sma - sd * std
            bb_width = (upper - lower) / sma.replace(0, np.nan)
            bw_rank = bb_width.rolling(p * 2).rank(pct=True)

            buy_signal = (bw_rank < th) & (bw_rank.shift(1) >= th) & (close > upper.shift(1))
            sell_signal = (bw_rank < th) & (bw_rank.shift(1) >= th) & (close < lower.shift(1))

            for dt in buy_signal[buy_signal].index:
                result.append({"date": dt, "code": code, "action": "buy", "reason": "bb_squeeze_up"})
            for dt in sell_signal[sell_signal].index:
                result.append({"date": dt, "code": code, "action": "sell", "reason": "bb_squeeze_down"})

        return self._to_portfolio(prices, pd.DataFrame(result), top_n, ai_scores)

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
