"""
MACD 金叉 / 死叉信号策略.

来源: 经典技术指标策略，MACD 上穿信号线买入、下穿卖出。
Apple (2008) "The MACD: A Combo of Indicators for the Best of Both Worlds"
"""

import numpy as np
import pandas as pd

from strategies.signal_base import SignalGenerator, AIEnhanceMixin


class MACDCrossStrategy(SignalGenerator, AIEnhanceMixin):
    """MACD 金叉死叉信号，可选 AI 增强"""

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9,
                 top_n: int = 3, ai_enhanced: bool = False):
        self.params = {
            "fast": fast, "slow": slow, "signal": signal,
            "top_n": top_n, "ai_enhanced": ai_enhanced,
        }

    def generate(self, prices: pd.DataFrame, features=None, ai_scores=None) -> pd.DataFrame:
        prices = prices.sort_index()
        fast, slow, sig_p, top_n = self.params["fast"], self.params["slow"], self.params["signal"], self.params["top_n"]

        signals = []
        for code in prices.columns:
            close = prices[code].dropna()
            if len(close) < slow + sig_p:
                continue

            ema_fast = close.ewm(span=fast, adjust=False).mean()
            ema_slow = close.ewm(span=slow, adjust=False).mean()
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=sig_p, adjust=False).mean()

            # 金叉: macd 上穿 signal
            cross_up = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
            cross_down = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))

            for date in cross_up[cross_up].index:
                signals.append({"date": date, "code": code, "action": "buy", "reason": "macd_golden_cross"})
            for date in cross_down[cross_down].index:
                signals.append({"date": date, "code": code, "action": "sell", "reason": "macd_dead_cross"})

        return self._to_portfolio(prices, pd.DataFrame(signals), top_n, ai_scores)

    def _to_portfolio(self, prices, raw_signals, top_n, ai_scores):
        """将买卖信号转为组合信号"""
        if raw_signals.empty:
            return pd.DataFrame()

        raw_signals = raw_signals.sort_values("date")
        result = []
        held: list[str] = []

        all_dates = prices.index.sort_values()
        sig_dates = set(raw_signals["date"].unique())

        for date in all_dates:
            if date in sig_dates:
                day_sigs = raw_signals[raw_signals["date"] == date]
                for _, s in day_sigs.iterrows():
                    if s["action"] == "buy" and s["code"] not in held:
                        held.append(s["code"])
                    elif s["action"] == "sell" and s["code"] in held:
                        held.remove(s["code"])

            buy_list = held[:top_n] if len(held) >= top_n else held
            if buy_list:
                w = {s: 1.0 / len(buy_list) for s in buy_list}
                result.append({"date": date, "buy": buy_list, "weights": w, "sell_all": False})

        out = pd.DataFrame(result).set_index("date") if result else pd.DataFrame()
        if self.params["ai_enhanced"]:
            out = self.enhance_with_ai(out, ai_scores, top_n)
        return out
