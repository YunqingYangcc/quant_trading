"""
通用量价特征 (Generic Quantitative Features) — 基于 ta 库.

覆盖 6 大类 60+ 特征：
1. 动量类 (Momentum): RSI, Stochastic, Williams %R, ROC, Awesome Oscillator, PPO, TSI
2. 趋势类 (Trend): SMA, EMA, MACD, ADX, Aroon, CCI, DPO, TRIX
3. 波动率类 (Volatility): ATR, Bollinger Bands, Donchian, Keltner, Ulcer
4. 量能类 (Volume): OBV, AD, CMF, EMV, Force Index, MFI, VPT, VWAP
5. 衍生统计类: 偏离度, 偏度, 峰度, 分位, 连续涨跌
6. 价格位置类: 高低点位置, 量价相关性

所有特征统一 shift(1) 防未来泄露。
"""

import numpy as np
import pandas as pd
import ta


def compute_generic_features(df: pd.DataFrame) -> pd.DataFrame:
    """计算通用量价特征。

    Args:
        df: 必须包含列 ['close', 'open', 'high', 'low', 'volume', 'amount']
            且按日期升序排列。

    Returns:
        原始 DataFrame 拼接所有特征列（已 shift(1)）。
    """
    c = df["close"].astype(float)
    o = df["open"].astype(float)
    h = df["high"].astype(float)
    l = df["low"].astype(float)
    v = df["volume"].astype(float)
    amt = df["amount"].astype(float)

    out: dict[str, pd.Series] = {}

    # ══════════════════════════════════════════════
    # 1. 动量类 (Momentum) — 16 features
    # ══════════════════════════════════════════════
    # RSI
    for p in [6, 14, 24]:
        out[f"rsi_{p}"] = ta.momentum.RSIIndicator(c, window=p).rsi()

    # Stochastic K/D
    stoch = ta.momentum.StochasticOscillator(h, l, c, window=14, smooth_window=3)
    out["stoch_k"] = stoch.stoch()
    out["stoch_d"] = stoch.stoch_signal()
    out["stoch_j"] = 3 * out["stoch_k"] - 2 * out["stoch_d"]

    # Williams %R
    for p in [14, 28]:
        out[f"willr_{p}"] = ta.momentum.WilliamsRIndicator(h, l, c, lbp=p).williams_r()

    # ROC (Rate of Change)
    for p in [1, 5, 10, 20, 60]:
        out[f"roc_{p}"] = ta.momentum.ROCIndicator(c, window=p).roc()

    # Awesome Oscillator
    out["ao"] = ta.momentum.AwesomeOscillatorIndicator(h, l).awesome_oscillator()

    # PPO (Percentage Price Oscillator)
    ppo = ta.momentum.PercentagePriceOscillator(c)
    out["ppo"] = ppo.ppo()
    out["ppo_signal"] = ppo.ppo_signal()

    # ══════════════════════════════════════════════
    # 2. 趋势类 (Trend) — 16 features
    # ══════════════════════════════════════════════
    # SMA & 偏离度
    for p in [5, 10, 20, 60]:
        sma = ta.trend.SMAIndicator(c, window=p).sma_indicator()
        out[f"sma_{p}"] = sma
        out[f"sma_dev_{p}"] = (c - sma) / sma.replace(0, np.nan)

    # EMA & 偏离度
    for p in [12, 26]:
        ema = ta.trend.EMAIndicator(c, window=p).ema_indicator()
        out[f"ema_{p}"] = ema
        out[f"ema_dev_{p}"] = (c - ema) / ema.replace(0, np.nan)

    # MACD
    macd = ta.trend.MACD(c)
    out["macd"] = macd.macd()
    out["macd_signal"] = macd.macd_signal()
    out["macd_hist"] = macd.macd_diff()

    # ADX (Average Directional Index)
    adx = ta.trend.ADXIndicator(h, l, c, window=14)
    out["adx"] = adx.adx()
    out["adx_pos"] = adx.adx_pos()
    out["adx_neg"] = adx.adx_neg()

    # Aroon
    aroon = ta.trend.AroonIndicator(h, l, window=25)
    out["aroon_up"] = aroon.aroon_up()
    out["aroon_down"] = aroon.aroon_down()

    # CCI
    for p in [14, 20]:
        out[f"cci_{p}"] = ta.trend.CCIIndicator(h, l, c, window=p).cci()

    # TRIX
    out["trix"] = ta.trend.TRIXIndicator(c, window=15).trix()

    # ══════════════════════════════════════════════
    # 3. 波动率类 (Volatility) — 12 features
    # ══════════════════════════════════════════════
    # ATR
    for p in [5, 14, 20]:
        out[f"atr_{p}"] = ta.volatility.AverageTrueRange(h, l, c, window=p).average_true_range()

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(c, window=20, window_dev=2)
    out["bb_upper"] = bb.bollinger_hband()
    out["bb_lower"] = bb.bollinger_lband()
    out["bb_mid"] = bb.bollinger_mavg()
    out["bb_width"] = (bb.bollinger_hband() - bb.bollinger_lband()) / bb.bollinger_mavg()
    out["bb_pct"] = bb.bollinger_pband()  # 价格在布林带中的位置 (0~1)

    # Donchian Channel
    dc = ta.volatility.DonchianChannel(h, l, c, window=20)
    out["dc_upper"] = dc.donchian_channel_hband()
    out["dc_lower"] = dc.donchian_channel_lband()
    out["dc_mid"] = dc.donchian_channel_mband()

    # Ulcer Index
    out["ulcer_14"] = ta.volatility.UlcerIndex(c, window=14).ulcer_index()

    # ══════════════════════════════════════════════
    # 4. 量能类 (Volume) — 12 features
    # ══════════════════════════════════════════════
    # OBV
    out["obv"] = ta.volume.OnBalanceVolumeIndicator(c, v).on_balance_volume()

    # Accumulation/Distribution
    out["ad"] = ta.volume.AccDistIndexIndicator(h, l, c, v).acc_dist_index()

    # CMF (Chaikin Money Flow)
    out["cmf"] = ta.volume.ChaikinMoneyFlowIndicator(h, l, c, v).chaikin_money_flow()

    # Ease of Movement
    out["emv"] = ta.volume.EaseOfMovementIndicator(h, l, v).ease_of_movement()

    # Force Index
    out["fi_13"] = ta.volume.ForceIndexIndicator(c, v, window=13).force_index()

    # MFI (Money Flow Index)
    out["mfi"] = ta.volume.MFIIndicator(h, l, c, v, window=14).money_flow_index()

    # Volume Price Trend
    out["vpt"] = ta.volume.VolumePriceTrendIndicator(c, v).volume_price_trend()

    # VWAP
    out["vwap"] = ta.volume.VolumeWeightedAveragePrice(h, l, c, v).volume_weighted_average_price()

    # 量比
    for p in [5, 20]:
        out[f"vol_ratio_{p}"] = v / v.rolling(p).mean().replace(0, np.nan)

    # 量能动量
    out["vol_roc_5"] = ta.momentum.ROCIndicator(v, window=5).roc()
    out["vol_roc_20"] = ta.momentum.ROCIndicator(v, window=20).roc()

    # ══════════════════════════════════════════════
    # 5. 衍生统计类 — 10 features
    # ══════════════════════════════════════════════
    daily_ret = c.pct_change()

    # 收益率偏度
    for p in [20, 60]:
        out[f"ret_skew_{p}"] = daily_ret.rolling(p).skew()

    # 收益率峰度
    out["ret_kurt_20"] = daily_ret.rolling(20).kurt()

    # 收益率分位 (当前值在过去 N 日中的分位 0~1)
    for p in [20, 60]:
        out[f"ret_pctile_{p}"] = _rolling_percentile(daily_ret, p)

    # 连续上涨/下跌天数
    out["consec_up"] = _consecutive_count(daily_ret > 0)
    out["consec_down"] = _consecutive_count(daily_ret < 0)

    # 收益波动比 (Sharpe-like)
    out["sharpe_20"] = daily_ret.rolling(20).mean() / daily_ret.rolling(20).std().replace(0, np.nan)

    # 量价相关性
    vol_ret = v.pct_change()
    for p in [10, 20]:
        out[f"pv_corr_{p}"] = daily_ret.rolling(p).corr(vol_ret)

    # ══════════════════════════════════════════════
    # 6. 价格位置类 — 4 features
    # ══════════════════════════════════════════════
    for p in [20, 60]:
        roll_high = h.rolling(p).max()
        roll_low = l.rolling(p).min()
        hl_range = (roll_high - roll_low).replace(0, np.nan)
        out[f"price_pos_{p}"] = (c - roll_low) / hl_range

    # ── 拼接 & shift(1) 防未来泄露 ──────────────
    result = pd.DataFrame(out, index=df.index)
    result = result.shift(1)

    return pd.concat([df, result], axis=1)


# ══════════════════════════════════════════════════════════
# 内部工具函数 (ta 库不覆盖的自定义特征)
# ══════════════════════════════════════════════════════════


def _rolling_percentile(series: pd.Series, window: int) -> pd.Series:
    """当前值在过去 N 日中的分位 (0~1)."""
    def pctile_rank(x):
        return np.sum(x[:-1] < x[-1]) / (len(x) - 1) if len(x) > 1 else np.nan
    return series.rolling(window).apply(pctile_rank, raw=True)


def _consecutive_count(mask: pd.Series) -> pd.Series:
    """连续为 True 的天数 (负数表示连续为 False)."""
    result = np.zeros(len(mask), dtype=float)
    count = 0
    for i in range(len(mask)):
        val = mask.iloc[i]
        if pd.isna(val):
            count = 0
        elif val:
            count = max(count, 0) + 1
        else:
            count = min(count, 0) - 1
        result[i] = count
    return pd.Series(result, index=mask.index)
