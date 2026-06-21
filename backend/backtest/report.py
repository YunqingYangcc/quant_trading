"""
回测报告模块 (backtest.report)

提供绩效指标计算、基准对比、回撤分析等能力。
"""

import numpy as np
import pandas as pd


def calculate_metrics(equity_curve: list[dict], initial_capital: float) -> dict:
    """从权益曲线计算绩效指标"""
    if not equity_curve:
        return {}
    df = pd.DataFrame(equity_curve).set_index("date")
    df["returns"] = df["total_value"].pct_change()

    final_value = float(df["total_value"].iloc[-1])
    total_return = (final_value / initial_capital - 1) * 100
    n_days = max(len(df), 1)
    annual_return = ((final_value / initial_capital) ** (252 / n_days) - 1) * 100
    annual_return = annual_return if np.isfinite(annual_return) else 0

    metrics = {
        "initial_capital": initial_capital,
        "final_value": round(float(final_value), 2),
        "total_return": round(float(total_return), 2),
        "annual_return": round(float(annual_return), 2),
    }

    returns = df["returns"].dropna()
    if len(returns) > 0:
        std = returns.std()
        metrics["annual_volatility"] = round(float(std * np.sqrt(252) * 100), 2) if np.isfinite(std) else 0
        sharpe = (returns.mean() / std) * np.sqrt(252) if std > 0 else 0
        metrics["sharpe_ratio"] = round(float(sharpe), 3) if np.isfinite(sharpe) else 0
        dd = float((df["total_value"] / df["total_value"].cummax() - 1).min() * 100)
        metrics["max_drawdown"] = round(dd, 2) if np.isfinite(dd) else 0
        wr = float((returns > 0).mean() * 100)
        metrics["win_rate"] = round(wr, 2)
        metrics["total_trading_days"] = len(returns)

    # 滚动指标
    metrics["rolling_sharpe_252d"] = _rolling_sharpe(returns)
    metrics["rolling_vol_60d"] = _rolling_vol(returns)

    # 回撤区间
    dd = _drawdown_periods(df["total_value"])
    metrics["drawdown_periods"] = dd[:5]  # 最多5个

    return metrics


def benchmark_compare(equity_curve: list[dict], benchmark_curve: list[dict]) -> dict:
    """与基准比较：超额收益、Alpha、Beta、信息比率"""
    if not equity_curve or not benchmark_curve:
        return {"error": "数据不足"}

    df = pd.DataFrame(equity_curve).set_index("date")["total_value"]
    bm = pd.DataFrame(benchmark_curve).set_index("date")["total_value"]

    # 对齐日期
    common = df.index.intersection(bm.index)
    df = df.loc[common]
    bm = bm.loc[common]

    df_ret = df.pct_change().dropna()
    bm_ret = bm.pct_change().dropna()

    # 超额收益
    excess = df_ret - bm_ret

    # Alpha / Beta (简单线性回归)
    if len(bm_ret) > 1 and bm_ret.std() > 0:
        cov_mat = np.cov(df_ret, bm_ret)
        beta_val = cov_mat[0, 1] / cov_mat[1, 1] if cov_mat[1, 1] > 0 else 0
        alpha_val = float(df_ret.mean() - beta_val * bm_ret.mean())
    else:
        beta_val = 0.0
        alpha_val = 0.0

    # 信息比率
    excess_std = float(excess.std())
    ir = float(excess.mean() / excess_std * np.sqrt(252)) if excess_std > 0 else 0.0

    # 超额最大回撤
    excess_cum = (1 + excess).cumprod()
    excess_dd = float((excess_cum / excess_cum.cummax() - 1).min() * 100)

    # 跟踪误差
    te = float(excess.std() * np.sqrt(252) * 100)

    # 相关性
    corr = float(df_ret.corr(bm_ret))

    return {
        "alpha": round(float(alpha_val * 252 * 100), 3) if np.isfinite(alpha_val) else 0.0,
        "beta": round(beta_val, 3) if np.isfinite(beta_val) else 0.0,
        "information_ratio": round(ir, 3) if np.isfinite(ir) else 0.0,
        "excess_return": round(float((df.iloc[-1] / bm.iloc[-1] - 1) * 100), 2),
        "excess_max_drawdown": round(excess_dd, 2) if np.isfinite(excess_dd) else 0.0,
        "correlation": round(corr, 3) if np.isfinite(corr) else 0.0,
        "tracking_error": round(te, 2) if np.isfinite(te) else 0.0,
    }


def buy_and_hold_curve(prices: pd.Series, initial_capital: float = 100000) -> list[dict]:
    """生成买入并持有的权益曲线（基准用）"""
    if prices.empty:
        return []
    first_px = prices.iloc[0]
    if first_px == 0:
        return []
    shares = initial_capital / first_px
    curve = []
    for date, px in prices.items():
        curve.append({
            "date": str(date.date()) if hasattr(date, "date") else str(date),
            "total_value": round(shares * px, 2),
        })
    return curve


def equity_curve_to_df(equity_curve: list[dict]) -> pd.DataFrame:
    """权益曲线转DataFrame"""
    df = pd.DataFrame(equity_curve)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def _rolling_sharpe(returns: pd.Series, window: int = 252) -> list[dict]:
    """滚动夏普比率"""
    if len(returns) < window:
        return []
    rolling = returns.rolling(window).apply(
        lambda r: r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else 0
    )
    return [
        {"date": str(d.date()), "value": round(v, 3)}
        for d, v in rolling.dropna().items()
    ]


def _rolling_vol(returns: pd.Series, window: int = 60) -> list[dict]:
    """滚动年化波动率"""
    if len(returns) < window:
        return []
    rolling = returns.rolling(window).std() * np.sqrt(252) * 100
    return [
        {"date": str(d.date()), "value": round(v, 2)}
        for d, v in rolling.dropna().items()
    ]


def _drawdown_periods(nav: pd.Series) -> list[dict]:
    """找出主要回撤区间"""
    peak = nav.expanding().max()
    dd = (nav / peak - 1) * 100
    in_dd = dd < 0

    periods = []
    start = None
    for i, (date, is_dd) in enumerate(in_dd.items()):
        if is_dd and start is None:
            start = i
        elif not is_dd and start is not None:
            end = i
            period_dd = dd.iloc[start:end]
            if len(period_dd) > 0:
                periods.append({
                    "start": str(dd.index[start].date()),
                    "end": str(dd.index[end - 1].date()),
                    "max_drawdown": round(float(period_dd.min()), 2),
                    "duration_days": end - start,
                })
            start = None

    periods.sort(key=lambda x: x["max_drawdown"])
    return periods
