"""
通用量价特征工厂。

生成所有通用技术指标（动量/波动率/均线/量能/RSI/ATR等）。
所有特征通过 shift(1) 防止未来泄露。
"""

import numpy as np
import pandas as pd


def compute_all_generic_features(df: pd.DataFrame) -> pd.DataFrame:
    """计算全部通用量价特征，返回含特征列的 DataFrame。

    Args:
        df: 必须包含 columns ['date','open','high','low','close','volume','amount']
             已按 date 升序排列

    Returns:
        原 df + 特征列（均已 shift(1) 对齐，无未来泄露）
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    required = {"close", "open", "high", "low", "volume", "amount"}
    missing = required - set(df.columns.str.lower())
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    df = df.copy()
    c = df["close"].values.astype(float)
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    v = df["volume"].values.astype(float)
    a = df["amount"].values.astype(float)
    n = len(c)

    out = {}

    # ── 1. 动量特征 (Momentum) ─────────────────────
    for period in [5, 10, 20, 60]:
        out[f"mom_{period}d"] = _pct_change(c, period)
        out[f"log_mom_{period}d"] = _log_return(c, period)

    # ── 2. 均线特征 (Moving Average) ─────────────────
    for period in [5, 10, 20, 60]:
        ma = _sma(c, period)
        out[f"ma_{period}"] = ma
        out[f"ma_{period}_pct"] = _safe_div(c - ma, ma)  # 偏离度
        out[f"ma_{period}_cross"] = np.where(c > ma, 1.0, 0.0)  # 价格在均线上方

    # 均线金叉/死叉信号
    ma5 = _sma(c, 5)
    ma20 = _sma(c, 20)
    ma5_prev = _shift(ma5, 1)
    ma20_prev = _shift(ma20, 1)
    out["ma_golden_cross"] = np.where((ma5 > ma20) & (ma5_prev <= ma20_prev), 1.0, 0.0)
    out["ma_death_cross"] = np.where((ma5 < ma20) & (ma5_prev >= ma20_prev), 1.0, 0.0)

    # ── 3. 波动率特征 (Volatility) ──────────────────
    for period in [5, 10, 20]:
        out[f"volatility_{period}d"] = _rolling_std(c, period)
        out[f"volatility_{period}d_pct"] = _rolling_std(_pct_change(c, 1), period)

    # ── 4. ATR (平均真实波幅) ────────────────────────
    for period in [14, 20]:
        out[f"atr_{period}"] = _atr(h, l, c, period)
        out[f"atr_{period}_pct"] = _safe_div(_atr(h, l, c, period), c)

    # ── 5. RSI (相对强弱指标) ────────────────────────
    for period in [6, 14, 20]:
        out[f"rsi_{period}"] = _rsi(c, period)

    # ── 6. 量能特征 (Volume) ────────────────────────
    for period in [5, 10, 20]:
        out[f"volume_{period}d_ma"] = _sma(v, period)
        out[f"volume_ratio_{period}d"] = _safe_div(v, _sma(v, period))  # 量比
        out[f"amount_{period}d_ma"] = _sma(a, period)
        out[f"amount_ratio_{period}d"] = _safe_div(a, _sma(a, period))

    # 价量背离
    out["volume_price_divergence"] = _safe_div(
        _pct_change(c, 1) * _pct_change(v, 1),  # 同号为正（量价齐升/齐跌）
        _rolling_std(c, 20) + 1e-8,
    )

    # ── 7. 布林带 (Bollinger Bands) ────────────────
    for period in [20]:
        ma_b = _sma(c, period)
        std_b = _rolling_std(c, period)
        out[f"bb_upper_{period}"] = ma_b + 2 * std_b
        out[f"bb_lower_{period}"] = ma_b - 2 * std_b
        out[f"bb_width_{period}"] = _safe_div(2 * std_b, ma_b)  # 带宽
        out[f"bb_position_{period}"] = _safe_div(
            c - ma_b + 2 * std_b, 4 * std_b
        )  # 0-1 位置

    # ── 8. 相对强弱 (Relative Strength) ─────────────
    up = np.where((c - _shift(c, 1)) > 0, c - _shift(c, 1), 0)
    down = np.where((_shift(c, 1) - c) > 0, _shift(c, 1) - c, 0)
    for period in [14, 20]:
        avg_up = _sma(up, period)
        avg_down = _sma(down, period)
        out[f"rs_{period}"] = _safe_div(avg_up, avg_down + 1e-10)

    # ── 9. 价格位置特征 ────────────────────────────
    for period in [20, 60]:
        hh = _rolling_max(h, period)
        ll = _rolling_min(l, period)
        out[f"price_position_{period}d"] = _safe_div(c - ll, hh - ll + 1e-10)
        out[f"high_pct_{period}d"] = _safe_div(c, hh)  # 距近期高点
        out[f"low_pct_{period}d"] = _safe_div(c, ll)  # 距近期低点

    # ── 10. 换手率特征 ────────────────────────────
    out["turnover_rate"] = _safe_div(v, _sma(v, 60) + 1e-8)  # 相对 60 日量比

    # ── 11. 资金特征 ──────────────────────────────
    out["avg_price"] = _safe_div(a, v + 1e-8)  # 均价
    out["avg_price_ratio"] = _safe_div(_safe_div(a, v + 1e-8), c)  # 均价/收盘价
    out["amount_change_1d"] = _pct_change(a, 1)  # 成交额变化

    # ── 12. 收益偏度/峰度 ──────────────────────────
    ret_1d = _pct_change(c, 1)
    for period in [20]:
        out[f"return_skew_{period}d"] = _rolling_skew(ret_1d, period)
        out[f"return_kurt_{period}d"] = _rolling_kurt(ret_1d, period)

    # ── 全部 shift(1) 防未来泄露 ────────────────────
    result = pd.DataFrame(out)
    result = result.shift(1)
    result = pd.concat([df, result], axis=1)

    return result


# ══════════════════════════════════════════════════════════
# 内部工具函数
# ══════════════════════════════════════════════════════════


def _pct_change(arr: np.ndarray, period: int = 1) -> np.ndarray:
    result = np.full_like(arr, np.nan, dtype=float)
    if period < len(arr):
        result[period:] = (arr[period:] - arr[:-period]) / (arr[:-period] + 1e-10)
    return result


def _log_return(arr: np.ndarray, period: int = 1) -> np.ndarray:
    result = np.full_like(arr, np.nan, dtype=float)
    if period < len(arr):
        result[period:] = np.log(arr[period:] / (arr[:-period] + 1e-10))
    return result


def _sma(arr: np.ndarray, period: int) -> np.ndarray:
    result = np.full_like(arr, np.nan, dtype=float)
    if len(arr) >= period:
        cumsum = np.cumsum(arr)
        result[period - 1:] = cumsum[period - 1:] / period
        result[period - 1:] -= np.concatenate([[0], cumsum[:len(arr) - period]]) / period
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


def _rolling_skew(arr: np.ndarray, period: int) -> np.ndarray:
    """滚动偏度"""
    result = np.full_like(arr, np.nan, dtype=float)
    for i in range(period - 1, len(arr)):
        s = np.array(arr[i - period + 1:i + 1])
        s = s[~np.isnan(s)]
        if len(s) > 2:
            result[i] = float(pd.Series(s).skew())
    return result


def _rolling_kurt(arr: np.ndarray, period: int) -> np.ndarray:
    """滚动峰度"""
    result = np.full_like(arr, np.nan, dtype=float)
    for i in range(period - 1, len(arr)):
        s = np.array(arr[i - period + 1:i + 1])
        s = s[~np.isnan(s)]
        if len(s) > 3:
            result[i] = float(pd.Series(s).kurtosis())
    return result


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    """平均真实波幅"""
    prev_close = _shift(close, 1)
    tr = np.maximum(
        high - low,
        np.maximum(
            np.abs(high - prev_close),
            np.abs(low - prev_close),
        ),
    )
    return _sma(tr, period)


def _rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """相对强弱指标"""
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = _sma(gain, period)
    avg_loss = _sma(loss, period)
    rs = _safe_div(avg_gain, avg_loss + 1e-10)
    return np.where(avg_loss == 0, 100.0, 100.0 - 100.0 / (1.0 + rs))


def _shift(arr: np.ndarray, period: int = 1) -> np.ndarray:
    result = np.full_like(arr, np.nan, dtype=float)
    if period < len(arr):
        result[period:] = arr[:-period]
    return result


def _safe_div(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.where(np.abs(b) < 1e-10, 0.0, a / b)
