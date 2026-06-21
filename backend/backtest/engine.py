"""
统一回测执行引擎 (backtest.engine)

职责：
  1. 根据信号(Signal)执行交易模拟
  2. 统一处理滑点/手续费/涨跌停/止损止盈
  3. 输出标准化权益曲线和交易流水

用法：
  engine = BacktestEngine(initial_capital=100000)
  equity, trades, metrics = engine.run(signals, prices_df)

信号格式 (signals)：
  - 组合模式: DataFrame, index=date, columns=['buy', 'weights', 'sell_all']
      buy: list[str] 买入股票列表
      weights: dict[str,float] 权重配置
      sell_all: bool 是否清仓再买

  - 单股模式: DataFrame, index=date, columns=['position', 'stop_loss', 'take_profit']
      position: float [0,1] 仓位比例
      stop_loss: float 可选，单次止损线
      take_profit: float 可选，单次止盈线
"""

import logging
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── 默认交易参数 ──────────────────────────
DEFAULT_PARAMS = {
    "slippage": 0.001,          # 滑点 0.1%
    "commission": 0.0003,       # 手续费万三
    "max_single_stock": 0.20,   # 单票上限 20%
    "max_single_track": 0.50,   # 单赛道上限 50%
    "skip_limit_up": True,      # 涨停无法买入
    "skip_limit_down": True,    # 跌停无法卖出
    "stop_loss_pct": -0.15,     # 默认止损 -15%
    "take_profit_pct": 0.30,    # 默认止盈 +30%
}

DEFAULT_STOCK_PARAMS = {
    "initial_capital": 100000,
    "slippage": 0.001,
    "commission": 0.0003,
    "stop_loss_pct": 0.0,       # 个股回测默认不止损
    "take_profit_pct": 0.0,     # 个股回测默认不止盈
}


class Position:
    """单个持仓记录"""
    __slots__ = ("shares", "entry_price", "entry_date")

    def __init__(self, shares: int, entry_price: float, entry_date: Any):
        self.shares = shares
        self.entry_price = entry_price
        self.entry_date = entry_date

    def market_value(self, current_price: float) -> float:
        return self.shares * current_price

    def return_pct(self, current_price: float) -> float:
        return (current_price - self.entry_price) / self.entry_price if self.entry_price else 0.0


class BacktestEngine:
    """统一回测执行引擎，支持组合模式和单股模式"""

    def __init__(self, params: dict | None = None):
        p = {**DEFAULT_PARAMS, **(params or {})}
        self.initial_capital = p.get("initial_capital", 100000)
        self.slippage = p["slippage"]
        self.commission = p["commission"]
        self.max_single_stock = p["max_single_stock"]
        self.max_single_track = p["max_single_track"]
        self.skip_limit_up = p["skip_limit_up"]
        self.skip_limit_down = p["skip_limit_down"]
        self.stop_loss_pct = p.get("stop_loss_pct", -0.15)
        self.take_profit_pct = p.get("take_profit_pct", 0.30)

        # 内部状态
        self.cash: float = self.initial_capital
        self.positions: dict[str, Position] = {}
        self.trades: list[dict] = []
        self.equity_curve: list[dict] = []
        self._prices: pd.DataFrame | None = None

    def reset(self):
        """重置引擎状态"""
        self.cash = self.initial_capital
        self.positions.clear()
        self.trades.clear()
        self.equity_curve.clear()

    def run(
        self,
        signals: pd.DataFrame,
        prices: pd.DataFrame,
        limit_up_dates: dict[str, list] | None = None,
        limit_down_dates: dict[str, list] | None = None,
    ) -> tuple[list[dict], list[dict], dict]:
        """运行回测

        Args:
            signals: 信号 DataFrame
            prices: 价格 DataFrame (index=date, columns=stock_code)
            limit_up_dates: {stock_code: [dates]} 涨停日期
            limit_down_dates: {stock_code: [dates]} 跌停日期

        Returns:
            (equity_curve, trades, metrics)
        """
        self.reset()
        self._prices = prices

        # 判断模式
        is_portfolio = "buy" in signals.columns or "weights" in signals.columns

        prices_ffill = prices.ffill()
        all_dates = sorted(set(signals.index).union(set(prices.index)))
        rebalance_dates = set(signals.index)

        for date in all_dates:
            if date not in prices_ffill.index:
                continue

            # 检查止损止盈（非调仓日和调仓日都要检查）
            self._check_stops(date, prices_ffill)

            if date in rebalance_dates:
                signal = signals.loc[date]
                if is_portfolio:
                    self._execute_portfolio_rebalance(date, signal, prices_ffill,
                                                       limit_up_dates, limit_down_dates)
                else:
                    self._execute_single_stock_action(date, signal, prices_ffill,
                                                       limit_up_dates, limit_down_dates)

            self._record_nav(date, prices_ffill)

        metrics = self._calculate_metrics()
        return self.equity_curve, self.trades, metrics

    def _check_stops(self, date: Any, prices_ffill: pd.DataFrame):
        """检查止损止盈"""
        for code in list(self.positions.keys()):
            pos = self.positions[code]
            if date not in prices_ffill.index or code not in prices_ffill.columns:
                continue
            px = prices_ffill.loc[date, code]
            if pd.isna(px):
                continue
            ret = pos.return_pct(px)

            if self.stop_loss_pct < 0 and ret <= self.stop_loss_pct:
                self._close_position(code, date, px, "stop_loss", f"止损 {ret*100:.1f}%")
            elif self.take_profit_pct > 0 and ret >= self.take_profit_pct:
                self._close_position(code, date, px, "take_profit", f"止盈 {ret*100:.1f}%")

    def _execute_portfolio_rebalance(
        self, date: Any, signal: pd.Series, prices_ffill: pd.DataFrame,
        limit_up_dates: dict[str, list] | None = None,
        limit_down_dates: dict[str, list] | None = None,
    ):
        """组合模式：先卖后买"""
        sell_all = signal.get("sell_all", True)

        # 卖出
        if sell_all:
            for code in list(self.positions.keys()):
                px = self._get_trade_price(code, date, prices_ffill, is_buy=False, limit_dates=limit_down_dates)
                if px is not None and not pd.isna(px):
                    self._close_position(code, date, px, "sell")

        # 买入
        buy_list = signal.get("buy", [])
        weights = signal.get("weights", {})
        if not buy_list:
            return
        buy_cash = self.cash * 0.95
        for code in buy_list:
            px = self._get_trade_price(code, date, prices_ffill, is_buy=True, limit_dates=limit_up_dates)
            if px is None or pd.isna(px):
                continue
            w = weights.get(code, 1.0 / len(buy_list))
            budget = min(buy_cash * w, self.cash * self.max_single_stock)
            total_cost = px * (1 + self.commission + self.slippage)
            shares = int(budget / total_cost)
            if shares > 0:
                self._open_position(code, date, px, shares)

    def _execute_single_stock_action(
        self, date: Any, signal: pd.Series, prices_ffill: pd.DataFrame,
        limit_up_dates: dict[str, list] | None = None,
        limit_down_dates: dict[str, list] | None = None,
    ):
        """单股模式：根据信号买卖"""
        action = signal.get("action", signal.get("position", 0))
        code = signal.get("code", signal.get("stock_code", ""))

        if isinstance(action, (int, float)):
            # position 模式：0=空仓 1=满仓
            target_pct = float(action)
            has_position = len(self.positions) > 0

            if target_pct <= 0 and has_position:
                for c in list(self.positions.keys()):
                    px = self._get_trade_price(c, date, prices_ffill, is_buy=False, limit_dates=limit_down_dates)
                    if px is not None and not pd.isna(px):
                        self._close_position(c, date, px, "sell")
            elif target_pct > 0 and not has_position:
                if code:
                    px = self._get_trade_price(code, date, prices_ffill, is_buy=True, limit_dates=limit_up_dates)
                    if px is not None and not pd.isna(px):
                        budget = self.cash * target_pct * 0.95
                        total_cost = px * (1 + self.commission + self.slippage)
                        shares = int(budget / total_cost)
                        if shares > 0:
                            self._open_position(code, date, px, shares)
                else:
                    # 没有指定 code，买 available 的
                    for c in prices_ffill.columns:
                        px = self._get_trade_price(c, date, prices_ffill, is_buy=True, limit_dates=limit_up_dates)
                        if px is not None and not pd.isna(px):
                            budget = self.cash * target_pct * 0.95
                            total_cost = px * (1 + self.commission + self.slippage)
                            shares = int(budget / total_cost)
                            if shares > 0:
                                self._open_position(c, date, px, shares)
                            break
        else:
            # action 模式：buy/sell/hold
            if action == "sell":
                for c in list(self.positions.keys()):
                    px = self._get_trade_price(c, date, prices_ffill, is_buy=False, limit_dates=limit_down_dates)
                    if px is not None and not pd.isna(px):
                        self._close_position(c, date, px, "sell")
            elif action == "buy" and code:
                px = self._get_trade_price(code, date, prices_ffill, is_buy=True, limit_dates=limit_up_dates)
                if px is not None and not pd.isna(px):
                    budget = self.cash * 0.95
                    total_cost = px * (1 + self.commission + self.slippage)
                    shares = int(budget / total_cost)
                    if shares > 0:
                        self._open_position(code, date, px, shares)
            # hold: do nothing

    def _get_trade_price(self, code: str, date: Any, prices_ffill: pd.DataFrame,
                         is_buy: bool = True, limit_dates: dict[str, list] | None = None) -> float | None:
        """获取交易价格，检查涨跌停"""
        if date not in prices_ffill.index or code not in prices_ffill.columns:
            return None
        px = prices_ffill.loc[date, code]
        if pd.isna(px):
            return None
        # 涨跌停过滤
        if limit_dates is not None:
            dates_list = limit_dates.get(code, [])
            if is_buy and self.skip_limit_up and date in dates_list:
                return None
            if not is_buy and self.skip_limit_down and date in dates_list:
                return None
        return px

    def _open_position(self, code: str, date: Any, price: float, shares: int):
        """开仓"""
        cost = shares * price * (1 + self.commission + self.slippage)
        if cost > self.cash:
            shares = int(self.cash / (price * (1 + self.commission + self.slippage)))
            if shares <= 0:
                return
            cost = shares * price * (1 + self.commission + self.slippage)
        self.cash -= cost
        self.positions[code] = Position(shares, price, date)
        self.trades.append({
            "date": str(date.date()) if hasattr(date, "date") else str(date),
            "code": code, "type": "buy",
            "price": round(price, 3), "shares": shares,
            "cost": round(cost, 2),
        })

    def _close_position(self, code: str, date: Any, price: float,
                        trade_type: str = "sell", reason: str = ""):
        """平仓"""
        pos = self.positions.get(code)
        if pos is None:
            return
        proceeds = pos.shares * price * (1 - self.commission - self.slippage)
        profit = proceeds - pos.shares * pos.entry_price
        self.cash += proceeds
        trade = {
            "date": str(date.date()) if hasattr(date, "date") else str(date),
            "code": code, "type": trade_type,
            "price": round(price, 3), "shares": pos.shares,
            "proceeds": round(proceeds, 2), "profit": round(profit, 2),
        }
        if reason:
            trade["reason"] = reason
        self.trades.append(trade)
        del self.positions[code]

    def _record_nav(self, date: Any, prices_ffill: pd.DataFrame):
        """记录每日净值"""
        nav = self.cash
        for code, pos in self.positions.items():
            if date in prices_ffill.index and code in prices_ffill.columns:
                px = prices_ffill.loc[date, code]
                if not pd.isna(px):
                    nav += pos.market_value(px)
        self.equity_curve.append({
            "date": str(date.date()) if hasattr(date, "date") else str(date),
            "total_value": round(nav, 2),
        })

    def _calculate_metrics(self) -> dict:
        """计算绩效指标"""
        if not self.equity_curve:
            return {}
        df = pd.DataFrame(self.equity_curve).set_index("date")
        df["returns"] = df["total_value"].pct_change()

        final_value = float(df["total_value"].iloc[-1])
        total_return = (final_value / self.initial_capital - 1) * 100
        n_days = max(len(df), 1)
        annual_return = ((final_value / self.initial_capital) ** (252 / n_days) - 1) * 100

        metrics = {
            "initial_capital": self.initial_capital,
            "final_value": round(float(final_value), 2),
            "total_return": round(float(total_return), 2),
            "annual_return": round(float(annual_return), 2),
        }

        returns = df["returns"].dropna()
        if len(returns) > 0:
            std = returns.std()
            metrics["annual_volatility"] = round(float(std * np.sqrt(252) * 100), 2)
            # 防除零
            sharpe = (returns.mean() / std) * np.sqrt(252) if std > 0 else 0
            metrics["sharpe_ratio"] = round(float(sharpe), 3) if np.isfinite(sharpe) else 0
            dd = (df["total_value"] / df["total_value"].cummax() - 1).min() * 100
            metrics["max_drawdown"] = round(float(dd), 2) if np.isfinite(dd) else 0
            wr = (returns > 0).mean() * 100
            metrics["win_rate"] = round(float(wr), 2)
            metrics["total_trades"] = len(self.trades)

        # 补充统计
        buy_trades = [t for t in self.trades if t["type"] == "buy"]
        sell_trades = [t for t in self.trades if t["type"] == "sell"]
        stop_trades = [t for t in self.trades if t["type"] in ("stop_loss", "take_profit")]
        metrics["buy_count"] = len(buy_trades)
        metrics["sell_count"] = len(sell_trades)
        metrics["stop_count"] = len(stop_trades)

        return metrics


def generate_momentum_signals(
    prices: pd.DataFrame,
    lookback: int = 20,
    top_n: int = 3,
    freq: str = "MS",
) -> pd.DataFrame:
    """生成动量排序信号（兼容原 MomentumStrategy）"""
    daily_ret = prices.pct_change().clip(-0.5, 0.5)
    mom = (1 + daily_ret).rolling(lookback).apply(np.prod, raw=True) - 1
    signals = []
    for date in pd.date_range(mom.index.min(), mom.index.max(), freq=freq):
        valid = mom.index[mom.index <= date]
        if len(valid) == 0:
            continue
        sd = valid[-1]
        scores = mom.loc[sd].dropna()
        if len(scores) < top_n:
            continue
        top = scores.nlargest(top_n).index.tolist()
        signals.append({"date": date, "buy": top, "weights": {s: 1.0/top_n for s in top}, "sell_all": True})
    return pd.DataFrame(signals).set_index("date") if signals else pd.DataFrame()


def generate_ai_signals(
    scores: pd.DataFrame,
    top_n: int = 3,
    freq: str = "MS",
) -> pd.DataFrame:
    """根据 AI 打分生成调仓信号"""
    scores = scores.copy()
    scores["period"] = scores["trade_date"].apply(
        lambda d: f"{d.year}-{d.month:02d}" if freq == "MS" else f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"
    )
    signals = []
    for period, group in scores.groupby("period"):
        period_date = group["trade_date"].max()
        best_per_stock = group.loc[group.groupby("stock_code")["pred_score"].idxmax()]
        ranked = best_per_stock.sort_values("pred_score", ascending=False)
        top = ranked.head(top_n)["stock_code"].tolist()
        signals.append({"date": period_date, "buy": top, "weights": {s: 1.0/len(top) for s in top}, "sell_all": True})
    return pd.DataFrame(signals).set_index("date") if signals else pd.DataFrame()
