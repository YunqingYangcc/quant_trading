"""
均值回归类策略：RSI、布林带
"""

import numpy as np
import pandas as pd

from strategies.signal_base import SignalGenerator, AIEnhanceMixin


class RSIStrategy(SignalGenerator, AIEnhanceMixin):
    """RSI 均值回归策略

    RSI 低于 oversold_threshold → 买入（超卖反弹预期）
    RSI 高于 overbought_threshold → 卖出（超买回调预期）
    """

    name = "rsi_reversal"
    description = "RSI 均值回归: 超卖买入, 超买卖出"

    def __init__(self, period: int = 14, oversold: int = 30, overbought: int = 70, top_n: int = 3):
        self.params = {
            "period": period,
            "oversold": oversold,
            "overbought": overbought,
            "top_n": top_n,
        }

    def generate(self, prices: pd.DataFrame, features=None, ai_scores=None) -> pd.DataFrame:
        prices = prices.sort_index()
        signals_list = []

        for code in prices.columns:
            px = prices[code].dropna()
            if len(px) < self.params["period"] + 1:
                continue

            delta = px.diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            avg_gain = gain.rolling(self.params["period"]).mean()
            avg_loss = loss.rolling(self.params["period"]).mean()
            rs = avg_gain / avg_loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))

            # 超卖 → 买入信号 (RSI 从下向上穿过 oversold)
            buy_signal = (rsi.shift(1) <= self.params["oversold"]) & (rsi > self.params["oversold"])
            # 超买 → 卖出信号 (RSI 从上向下穿过 overbought)
            sell_signal = (rsi.shift(1) >= self.params["overbought"]) & (rsi < self.params["overbought"])

            for d in buy_signal[buy_signal].index:
                signals_list.append({"date": d, "buy": [code], "weights": {code: 1.0}, "sell_all": False})
            for d in sell_signal[sell_signal].index:
                signals_list.append({"date": d, "buy": [], "weights": {}, "sell_all": True})

        if not signals_list:
            return pd.DataFrame()

        signals = pd.DataFrame(signals_list)
        merged = []
        for date, group in signals.groupby("date"):
            buys = []
            for _, row in group.iterrows():
                buys.extend(row.get("buy", []))
            buys = list(dict.fromkeys(buys))

            # RSI 信号太多时，只保留 AI 打分最高的 top_n
            if len(buys) > self.params["top_n"] and ai_scores is not None and not ai_scores.empty:
                date_scores = ai_scores[
                    (ai_scores["trade_date"] <= date) &
                    (ai_scores["stock_code"].isin(buys))
                ]
                if not date_scores.empty:
                    latest = date_scores.loc[
                        date_scores.groupby("stock_code")["trade_date"].idxmax()
                    ]
                    buys = latest.nlargest(self.params["top_n"], "pred_score")["stock_code"].tolist()

            merged.append({
                "date": date,
                "buy": buys[:self.params["top_n"]],
                "weights": {s: 1.0 / min(len(buys), self.params["top_n"]) for s in buys[:self.params["top_n"]]},
                "sell_all": True,
            })

        result = pd.DataFrame(merged).set_index("date")
        return self.enhance_with_ai(result, ai_scores, self.params["top_n"])


class BollingerStrategy(SignalGenerator, AIEnhanceMixin):
    """布林带均值回归策略

    价格触及下轨 → 买入（超卖反弹）
    价格触及上轨 → 卖出（超买回调）
    """

    name = "bollinger_reversal"
    description = "布林带均值回归: 下轨买入, 上轨卖出"

    def __init__(self, period: int = 20, std_dev: float = 2.0, top_n: int = 3):
        self.params = {
            "period": period,
            "std_dev": std_dev,
            "top_n": top_n,
        }

    def generate(self, prices: pd.DataFrame, features=None, ai_scores=None) -> pd.DataFrame:
        prices = prices.sort_index()
        signals_list = []

        for code in prices.columns:
            px = prices[code].dropna()
            if len(px) < self.params["period"] + 1:
                continue

            ma = px.rolling(self.params["period"]).mean()
            std = px.rolling(self.params["period"]).std()
            upper = ma + self.params["std_dev"] * std
            lower = ma - self.params["std_dev"] * std

            # 触及下轨 → 买入
            touch_lower = (px.shift(1) >= lower.shift(1)) & (px < lower)
            # 触及上轨 → 卖出
            touch_upper = (px.shift(1) <= upper.shift(1)) & (px > upper)

            for d in touch_lower[touch_lower].index:
                signals_list.append({"date": d, "buy": [code], "weights": {code: 1.0}, "sell_all": False})
            for d in touch_upper[touch_upper].index:
                signals_list.append({"date": d, "buy": [], "weights": {}, "sell_all": True})

        if not signals_list:
            return pd.DataFrame()

        signals = pd.DataFrame(signals_list)
        merged = []
        for date, group in signals.groupby("date"):
            buys = []
            for _, row in group.iterrows():
                buys.extend(row.get("buy", []))
            buys = list(dict.fromkeys(buys))

            if len(buys) > self.params["top_n"] and ai_scores is not None and not ai_scores.empty:
                date_scores = ai_scores[
                    (ai_scores["trade_date"] <= date) &
                    (ai_scores["stock_code"].isin(buys))
                ]
                if not date_scores.empty:
                    latest = date_scores.loc[
                        date_scores.groupby("stock_code")["trade_date"].idxmax()
                    ]
                    buys = latest.nlargest(self.params["top_n"], "pred_score")["stock_code"].tolist()

            merged.append({
                "date": date,
                "buy": buys[:self.params["top_n"]],
                "weights": {s: 1.0 / min(len(buys), self.params["top_n"]) for s in buys[:self.params["top_n"]]},
                "sell_all": True,
            })

        result = pd.DataFrame(merged).set_index("date")
        return self.enhance_with_ai(result, ai_scores, self.params["top_n"])
