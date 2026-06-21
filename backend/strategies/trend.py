"""
趋势类策略：MA 金叉死叉、MACD、N日突破
"""

import numpy as np
import pandas as pd

from strategies.signal_base import SignalGenerator, AIEnhanceMixin


class MACrossStrategy(SignalGenerator, AIEnhanceMixin):
    """MA 金叉死叉策略

    短期均线上穿长期均线 → 买入
    短期均线下穿长期均线 → 卖出
    """

    name = "ma_cross"
    description = "MA 金叉死叉: 短线上穿长线买入, 下穿卖出"

    def __init__(self, short_window: int = 5, long_window: int = 20, top_n: int = 3):
        self.params = {
            "short_window": short_window,
            "long_window": long_window,
            "top_n": top_n,
        }

    def generate(self, prices: pd.DataFrame, features=None, ai_scores=None) -> pd.DataFrame:
        prices = prices.sort_index()
        signals_list = []

        for code in prices.columns:
            px = prices[code].dropna()
            if len(px) < self.params["long_window"] + 1:
                continue
            ma_short = px.rolling(self.params["short_window"]).mean()
            ma_long = px.rolling(self.params["long_window"]).mean()

            # 金叉: ma_short 上穿 ma_long
            cross_over = (ma_short > ma_long) & (ma_short.shift(1) <= ma_long.shift(1))
            # 死叉: ma_short 下穿 ma_long
            cross_under = (ma_short < ma_long) & (ma_short.shift(1) >= ma_long.shift(1))

            buy_dates = cross_over[cross_over].index
            sell_dates = cross_under[cross_under].index

            for d in buy_dates:
                signals_list.append({"date": d, "buy": [code], "weights": {code: 1.0}, "sell_all": False})
            for d in sell_dates:
                signals_list.append({"date": d, "buy": [], "weights": {}, "sell_all": True})

        if not signals_list:
            return pd.DataFrame()

        signals = pd.DataFrame(signals_list)
        # 合并同日信号（同一天多个金叉，选 top_n）
        merged = []
        for date, group in signals.groupby("date"):
            buys = []
            for _, row in group.iterrows():
                buys.extend(row.get("buy", []))
            if len(buys) > self.params["top_n"]:
                # 如果有 AI 打分，用 AI 筛选
                if ai_scores is not None and not ai_scores.empty:
                    date_scores = ai_scores[
                        (ai_scores["trade_date"] <= date) &
                        (ai_scores["stock_code"].isin(buys))
                    ]
                    if not date_scores.empty:
                        latest = date_scores.loc[
                            date_scores.groupby("stock_code")["trade_date"].idxmax()
                        ]
                        buys = latest.nlargest(self.params["top_n"], "pred_score")["stock_code"].tolist()
                    else:
                        buys = buys[:self.params["top_n"]]
                else:
                    buys = buys[:self.params["top_n"]]
            merged.append({
                "date": date,
                "buy": buys,
                "weights": {s: 1.0 / len(buys) for s in buys} if buys else {},
                "sell_all": True,
            })

        result = pd.DataFrame(merged).set_index("date")
        return self.enhance_with_ai(result, ai_scores, self.params["top_n"])


class BreakoutStrategy(SignalGenerator, AIEnhanceMixin):
    """N日突破策略

    价格创 N 日新高 → 买入
    价格创 N 日新低 → 卖出
    """

    name = "breakout"
    description = f"N日突破: 创N日新高买入, 新低卖出"

    def __init__(self, lookback: int = 20, top_n: int = 3):
        self.params = {"lookback": lookback, "top_n": top_n}

    def generate(self, prices: pd.DataFrame, features=None, ai_scores=None) -> pd.DataFrame:
        prices = prices.sort_index()
        high = prices.rolling(self.params["lookback"]).max()
        low = prices.rolling(self.params["lookback"]).min()

        signals_list = []
        for code in prices.columns:
            px = prices[code].dropna()
            if len(px) < self.params["lookback"] + 1:
                continue
            h = high[code]
            l = low[code]

            # 突破前高
            breakout = (px >= h) & (px.shift(1) < h.shift(1))
            # 跌破前低
            breakdown = (px <= l) & (px.shift(1) > l.shift(1))

            for d in breakout[breakout].index:
                signals_list.append({"date": d, "buy": [code], "weights": {code: 1.0}, "sell_all": False})
            for d in breakdown[breakdown].index:
                signals_list.append({"date": d, "buy": [], "weights": {}, "sell_all": True})

        if not signals_list:
            return pd.DataFrame()

        signals = pd.DataFrame(signals_list)
        merged = []
        for date, group in signals.groupby("date"):
            buys = []
            has_sell = False
            for _, row in group.iterrows():
                buys.extend(row.get("buy", []))
                if not row.get("buy") and row.get("sell_all"):
                    has_sell = True

            # 去重
            buys = list(dict.fromkeys(buys))

            merged.append({
                "date": date,
                "buy": buys[:self.params["top_n"]],
                "weights": {s: 1.0 / min(len(buys), self.params["top_n"]) for s in buys[:self.params["top_n"]]},
                "sell_all": has_sell or True,
            })

        result = pd.DataFrame(merged).set_index("date")
        return self.enhance_with_ai(result, ai_scores, self.params["top_n"])
