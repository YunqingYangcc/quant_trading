"""
复合策略：AI 过滤 + 多信号投票 + 置信度仓位

信号层融合：
  - AI 打分：模型预测相对强弱
  - 动量：过去 N 日收益率
  - RSI：超买超卖判断

策略模式：
  1. AI Filter — 技术指标选股 → AI 打分 < 阈值 → 过滤掉
  2. Multi-Vote — AI + 动量 + RSI 分别投票，≥ 阈值票数通过
  3. Confidence Sizing — AI 置信度决定仓位比例
"""

import numpy as np
import pandas as pd

from strategies.signal_base import SignalGenerator


def ai_confidence(score: float) -> float:
    """AI 打分转置信度 (0~1)"""
    return 2.0 * abs(score - 0.5)


def ai_position_size(score: float) -> float:
    """AI 置信度决定仓位比例

    score > 0.8 → 满仓 (1.0)
    score 0.6~0.8 → 中仓 (0.6)
    score 0.5~0.6 → 轻仓 (0.3)
    score < 0.5 → 不买 (0.0)
    """
    if score >= 0.8:
        return 1.0
    elif score >= 0.6:
        return 0.6
    elif score >= 0.5:
        return 0.3
    return 0.0


def get_ai_score_for_stock(
    ai_scores: pd.DataFrame | None,
    stock_code: str,
    date: pd.Timestamp,
) -> float:
    """获取某只股票在指定日期的 AI 打分"""
    if ai_scores is None or ai_scores.empty:
        return 0.5
    mask = (ai_scores["stock_code"] == stock_code) & (ai_scores["trade_date"] <= date)
    subset = ai_scores[mask]
    if subset.empty:
        return 0.5
    return float(subset.loc[subset["trade_date"].idxmax(), "pred_score"])


# ── AI 过滤 Mixin ──────────────────────────────

class AIFilterMixin:
    """AI 过滤混入：用 AI 打分筛选候选股票

    用法：在策略 generate() 中调用 self.filter_by_ai(buy_list, ai_scores, date, threshold)
    """

    def filter_by_ai(
        self,
        stocks: list[str],
        ai_scores: pd.DataFrame | None,
        date: pd.Timestamp,
        threshold: float = 0.5,
    ) -> list[str]:
        if ai_scores is None or ai_scores.empty or not stocks:
            return stocks
        date_scores = ai_scores[
            (ai_scores["trade_date"] <= date) &
            (ai_scores["stock_code"].isin(stocks))
        ]
        if date_scores.empty:
            return stocks
        latest = date_scores.loc[
            date_scores.groupby("stock_code")["trade_date"].idxmax()
        ]
        passed = latest[latest["pred_score"] >= threshold]
        return passed["stock_code"].tolist()

    def filter_with_confidence(
        self,
        stocks: list[str],
        ai_scores: pd.DataFrame | None,
        date: pd.Timestamp,
    ) -> list[tuple[str, float]]:
        """返回 (stock, confidence) 列表，按置信度降序"""
        if ai_scores is None or ai_scores.empty or not stocks:
            return [(s, 1.0) for s in stocks]
        date_scores = ai_scores[
            (ai_scores["trade_date"] <= date) &
            (ai_scores["stock_code"].isin(stocks))
        ]
        if date_scores.empty:
            return [(s, 1.0) for s in stocks]
        latest = date_scores.loc[
            date_scores.groupby("stock_code")["trade_date"].idxmax()
        ]
        result = []
        for _, row in latest.iterrows():
            conf = ai_confidence(row["pred_score"])
            pos_size = ai_position_size(row["pred_score"])
            if pos_size > 0:
                result.append((row["stock_code"], pos_size))
        result.sort(key=lambda x: x[1], reverse=True)
        return result


# ── 多信号投票策略 ────────────────────────────

class MultiSignalVoting(SignalGenerator):
    """多信号投票策略

    每个调仓日，三个信号源各自投票：
      - AI 信号：pred_score > 0.5 投买入
      - 动量信号：past_20d_return > 0 投买入
      - RSI 信号：RSI < 40（超卖区域）投买入

    得票 ≥ 2 → 买入，仓位按 AI 置信度决定
    """

    name = "multi_vote"
    description = "AI+动量+RSI 三信号投票，≥2票买入，AI置信度决定仓位"

    def __init__(self, top_n: int = 3, vote_threshold: int = 2):
        self.params = {"top_n": top_n, "vote_threshold": vote_threshold}

    def generate(self, prices: pd.DataFrame, features=None, ai_scores=None) -> pd.DataFrame:
        prices = prices.sort_index()
        daily_ret = prices.pct_change().clip(-0.5, 0.5)

        # 预计算动量
        mom = (1 + daily_ret).rolling(20).apply(np.prod, raw=True) - 1

        # 预计算 RSI
        rsi_cache = {}
        for code in prices.columns:
            px = prices[code].dropna()
            if len(px) < 15:
                continue
            delta = px.diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            avg_gain = gain.rolling(14).mean()
            avg_loss = loss.rolling(14).mean()
            rs = avg_gain / avg_loss.replace(0, np.nan)
            rsi_cache[code] = 100 - (100 / (1 + rs))

        signals = []
        freq = "MS"  # 月频调仓

        for date in pd.date_range(prices.index.min(), prices.index.max(), freq=freq):
            valid = prices.index[prices.index <= date]
            if len(valid) == 0:
                continue
            signal_date = valid[-1]

            candidates = []
            for code in prices.columns:
                px = prices[code].dropna()
                if len(px) < 30:
                    continue

                # --- AI 投票 ---
                ai_score = get_ai_score_for_stock(ai_scores, code, signal_date)
                ai_vote = 1 if ai_score > 0.5 else 0

                # --- 动量投票 ---
                if signal_date in mom.index and code in mom.columns:
                    mom_val = mom.loc[signal_date, code]
                    mom_vote = 1 if pd.notna(mom_val) and mom_val > 0 else 0
                else:
                    mom_vote = 0

                # --- RSI 投票 ---
                if code in rsi_cache and signal_date in rsi_cache[code].index:
                    rsi_val = rsi_cache[code].loc[signal_date]
                    rsi_vote = 1 if pd.notna(rsi_val) and rsi_val < 40 else 0
                else:
                    rsi_vote = 0

                total_votes = ai_vote + mom_vote + rsi_vote
                if total_votes >= self.params["vote_threshold"]:
                    # 用 AI 置信度决定仓位
                    pos_size = ai_position_size(ai_score)
                    candidates.append((code, pos_size, total_votes))

            if not candidates:
                continue

            # 按置信度排序取 Top-N
            candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)
            top = candidates[:self.params["top_n"]]
            buy_list = [c[0] for c in top]
            weights = {c[0]: c[1] for c in top}
            # 归一化权重
            total_w = sum(weights.values())
            if total_w > 0:
                for k in weights:
                    weights[k] /= total_w

            signals.append({
                "date": date,
                "buy": buy_list,
                "weights": weights,
                "sell_all": True,
            })

        return pd.DataFrame(signals).set_index("date") if signals else pd.DataFrame()


# ── 纯 AI 置信度轮动策略 ─────────────────────

class AIConfidenceStrategy(SignalGenerator):
    """AI 置信度分层轮动

    根据 AI 打分和置信度动态分配仓位：
      - pred_score > 0.8: 满仓 (weight=1.0)
      - pred_score 0.6~0.8: 中仓 (weight=0.6)
      - pred_score 0.5~0.6: 轻仓 (weight=0.3)
      - pred_score < 0.5: 不买

    比纯 Top-N 更精细——高分重仓，低分轻仓或放弃。
    """

    name = "ai_confidence"
    description = "AI 置信度分层轮动：高分重仓、低分轻仓、低于0.5不买"

    def __init__(self, top_n: int = 5):
        self.params = {"top_n": top_n}

    def generate(self, prices: pd.DataFrame, features=None, ai_scores=None) -> pd.DataFrame:
        if ai_scores is None or ai_scores.empty:
            return pd.DataFrame()

        ai_scores = ai_scores.copy()
        ai_scores["trade_date"] = pd.to_datetime(ai_scores["trade_date"])

        signals = []
        freq = "MS"

        for date in pd.date_range(prices.index.min(), prices.index.max(), freq=freq):
            date_scores = ai_scores[ai_scores["trade_date"] <= date]
            if date_scores.empty:
                continue
            latest_date = date_scores["trade_date"].max()
            latest = date_scores[date_scores["trade_date"] == latest_date].copy()

            # 计算置信度和仓位
            latest["position_size"] = latest["pred_score"].apply(ai_position_size)
            latest = latest[latest["position_size"] > 0]

            if latest.empty:
                continue

            # 按仓位大小排序取 Top-N
            ranked = latest.sort_values("position_size", ascending=False)
            top = ranked.head(self.params["top_n"])

            buy_list = top["stock_code"].tolist()
            weights = dict(zip(top["stock_code"], top["position_size"]))
            total_w = sum(weights.values())
            if total_w > 0:
                for k in weights:
                    weights[k] /= total_w

            signals.append({
                "date": date,
                "buy": buy_list,
                "weights": weights,
                "sell_all": True,
            })

        return pd.DataFrame(signals).set_index("date") if signals else pd.DataFrame()
