"""
赛道专属特征。

计算赛道级别的指标：赛道趋势、赛道相对强弱、赛道拥挤度、赛道资金流等。
"""

import numpy as np
import pandas as pd


def compute_track_specific_features(
    track_df: pd.DataFrame,
    track_name: str,
) -> pd.DataFrame:
    """计算赛道专属特征，叠加到个股 DataFrame 上。

    Args:
        track_df: 赛道内某只股票的数据，含 ['date','close','volume','amount']
        track_name: 赛道名称

    Returns:
        含赛道特征列的 DataFrame
    """
    df = track_df.copy()
    c = df["close"].values.astype(float)
    v = df["volume"].values.astype(float)
    n = len(c)

    out = {}

    # ── 赛道个体动量 ────────────────────────────
    for period in [5, 20, 60]:
        out[f"track_{track_name}_mom_{period}d"] = _pct_change(c, period)

    # ── 赛道个体趋势强度 ──────────────────────────
    # 用线性回归斜率表示趋势强度
    for period in [20, 60]:
        out[f"track_{track_name}_trend_{period}d"] = _linear_slope(c, period)

    # ── 赛道个体波动 ────────────────────────────
    for period in [20]:
        out[f"track_{track_name}_volatility_{period}d"] = _rolling_std(
            _pct_change(c, 1), period
        )
        out[f"track_{track_name}_volume_ratio_{period}d"] = _safe_div(
            v, _sma(v, period)
        )

    # ── 赛道量价指标 ────────────────────────────
    # Amihud 非流动性指标: |return| / volume
    ret = _pct_change(c, 1)
    amihud = np.full_like(c, np.nan, dtype=float)
    mask = v > 0
    amihud[mask] = np.abs(ret[mask]) / v[mask]
    amihud_ma = _sma(np.nan_to_num(amihud, nan=0.0), 20)
    out[f"track_{track_name}_amihud_illiq"] = amihud_ma

    # ── 赛道资金驱动指标 ──────────────────────────
    # 用 (close - open) * volume 近似资金方向
    delta = df["close"].values.astype(float) - df["open"].values.astype(float)
    money_flow = delta * v
    for period in [5, 20]:
        out[f"track_{track_name}_money_flow_{period}d"] = _sma(money_flow, period)
        out[f"track_{track_name}_money_flow_ratio_{period}d"] = _safe_div(
            _sma(money_flow, period), _sma(np.abs(money_flow), period)
        )

    # ── 赛道反转信号 ────────────────────────────
    for period in [5, 20]:
        ret_p = _pct_change(c, 1)
        out[f"track_{track_name}_max_ret_{period}d"] = _rolling_max(ret_p, period)
        out[f"track_{track_name}_min_ret_{period}d"] = _rolling_min(ret_p, period)
        out[f"track_{track_name}_avg_ret_{period}d"] = _sma(ret_p, period)

    # shift(1) 防未来泄露
    result = pd.DataFrame(out)
    result = result.shift(1)
    result = pd.concat([df, result], axis=1)

    return result


# ── 赛道间相对强度 ──────────────────────────────


def compute_cross_track_relative_strength(
    track_returns: dict[str, np.ndarray],
    date_aligned: bool = True,
) -> dict[str, np.ndarray]:
    """计算赛道间相对强度。

    Args:
        track_returns: {track_name: ndarray of daily returns}
        date_aligned: 是否已按日期对齐

    Returns:
        {track_name: relative_strength_ratio} 相对全市场中位数的强度
    """
    if not track_returns:
        return {}

    names = list(track_returns.keys())
    all_ret = np.column_stack([track_returns[n] for n in names])
    median_ret = np.nanmedian(all_ret, axis=1)

    result = {}
    for i, name in enumerate(names):
        result[name] = _safe_div(track_returns[name], median_ret + 1e-10)

    return result


def compute_track_crowdedness(
    track_returns_matrix: np.ndarray,
    window: int = 60,
) -> np.ndarray:
    """计算赛道拥挤度（内部个股平均相关系数）。

    Args:
        track_returns_matrix: shape (n_days, n_stocks)
        window: 滚动窗口

    Returns:
        shape (n_days,) 的拥挤度序列
    """
    n_days, n_stocks = track_returns_matrix.shape
    crowdedness = np.full(n_days, np.nan, dtype=float)

    for i in range(window, n_days):
        window_data = track_returns_matrix[i - window:i]
        corr_matrix = np.corrcoef(window_data.T)
        # 取上三角平均值（不包括对角线）
        triu_indices = np.triu_indices(n_stocks, k=1)
        if triu_indices[0].size > 0:
            crowdedness[i] = np.nanmean(corr_matrix[triu_indices])

    return crowdedness


# ══════════════════════════════════════════════════════════
# 内部工具（与 features_generic 复用，保持独立运行能力）
# ══════════════════════════════════════════════════════════


def _pct_change(arr: np.ndarray, period: int = 1) -> np.ndarray:
    result = np.full_like(arr, np.nan, dtype=float)
    if period < len(arr):
        result[period:] = (arr[period:] - arr[:-period]) / (arr[:-period] + 1e-10)
    return result


def _sma(arr: np.ndarray, period: int) -> np.ndarray:
    result = np.full_like(arr, np.nan, dtype=float)
    if len(arr) >= period:
        s = pd.Series(arr)
        result[:] = s.rolling(period, min_periods=period).mean().values
    return result


def _rolling_std(arr: np.ndarray, period: int) -> np.ndarray:
    result = np.full_like(arr, np.nan, dtype=float)
    for i in range(period - 1, len(arr)):
        result[i] = np.std(arr[i - period + 1:i + 1])
    return result


def _rolling_max(arr: np.ndarray, period: int) -> np.ndarray:
    result = np.full_like(arr, np.nan, dtype=float)
    for i in range(period - 1, len(arr)):
        result[i] = np.max(arr[i - period + 1:i + 1])
    return result


def _rolling_min(arr: np.ndarray, period: int) -> np.ndarray:
    result = np.full_like(arr, np.nan, dtype=float)
    for i in range(period - 1, len(arr)):
        result[i] = np.min(arr[i - period + 1:i + 1])
    return result


def _linear_slope(arr: np.ndarray, period: int) -> np.ndarray:
    """计算滚动线性回归斜率"""
    result = np.full_like(arr, np.nan, dtype=float)
    x = np.arange(period)
    for i in range(period - 1, len(arr)):
        y = arr[i - period + 1:i + 1]
        if np.any(np.isnan(y)):
            continue
        slope = np.polyfit(x, y, 1)[0]
        result[i] = slope
    return result


def _safe_div(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.where(np.abs(b) < 1e-10, 0.0, a / b)
