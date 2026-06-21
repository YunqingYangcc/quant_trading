"""
为所有 FeatureConfig 生成完整释义/公式/解读。

运行方式: cd backend && python -m scripts.fill_feature_descriptions
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.db.database import async_session_maker
from app.models.track import FeatureConfig


# ══════════════════════════════════════════════════════════
# 特征释义生成器 —— 通过特征名模式匹配，动态生成释义
# ══════════════════════════════════════════════════════════


def gen_description(name: str) -> str:
    """根据特征名生成大白话释义"""
    
    # ── RSI ──
    if name.startswith("rsi_"):
        n = name.split("_")[1]
        return f"{n}日相对强弱指标，衡量近期价格变动的速度和幅度。值越大说明上涨越猛，越小说明下跌越狠。"

    # ── Stochastic ──
    if name == "stoch_k":
        return "随机指标K线，衡量收盘价在最近14日价格范围内的位置。K线>80说明价格处于高位，<20说明处于低位。"
    if name == "stoch_d":
        return "随机指标D线，K线的3日移动平均平滑线。D线>80并拐头向下为卖出信号。"
    if name == "stoch_j":
        return "随机指标J线，J=3K-2D。J>100为超买区，J<0为超卖区，比K/D更敏感。"

    # ── Williams %R ──
    if name.startswith("willr_"):
        n = name.split("_")[1]
        return f"{n}日威廉指标，反映收盘价在最近{n}日最高最低之间的位置。值>-20超买，<-80超卖。"

    # ── ROC ──
    if name.startswith("roc_"):
        n = name.split("_")[1]
        return f"{n}日价格变动率，当前收盘价比{n}日前涨跌百分之几。上穿0轴为加速上涨信号。"

    # ── AO ──
    if name == "ao":
        return "Awesome Oscillator（动量震荡），5日与34日简单均线的差值。正值表示短期动量强于长期。"

    # ── PPO ──
    if name == "ppo":
        return "百分比价格震荡器，类似MACD但用百分比表示。衡量短期均线相对于长期均线的偏离程度。"
    if name == "ppo_signal":
        return "PPO信号线，PPO的9日EMA平滑线。PPO上穿信号线为买入信号。"

    # ── SMA ──
    if name.startswith("sma_") and not "dev" in name:
        n = name.split("_")[1]
        return f"{n}日简单移动平均线。收盘价高于{n}MA表示{n}日趋势偏强，低于则表示偏弱。"
    if name.startswith("sma_dev_"):
        n = name.split("_")[2]
        return f"{n}日偏离度，(收盘价-{n}日均线)÷{n}日均线。偏离>+5%可能回调，<-5%可能反弹。"

    # ── EMA ──
    if name.startswith("ema_") and not "dev" in name:
        n = name.split("_")[1]
        return f"{n}日指数移动平均线，对近期价格赋予更高权重。比SMA更灵敏地反映价格变化。"
    if name.startswith("ema_dev_"):
        n = name.split("_")[2]
        return f"{n}日指数移动偏离度，(收盘价-{n}日EMA)÷{n}日EMA。"

    # ── MACD ──
    if name == "macd":
        return "MACD快线，12日EMA减去26日EMA。MACD>0为多头市场，<0为空头市场。"
    if name == "macd_signal":
        return "MACD信号线，MACD的9日EMA。MACD上穿信号线=金叉买入，下穿=死叉卖出。"
    if name == "macd_hist":
        return "MACD柱状图，MACD减去信号线的差值。柱体变大为趋势加速，缩小为趋势衰减。"

    # ── ADX ──
    if name == "adx":
        return "平均趋向指数，衡量趋势强度（非方向）。ADX>25为趋势行情，<20为震荡行情。"
    if name == "adx_pos":
        return "正向方向指标+DI，衡量上涨趋势强度。+DI上穿-DI为买入信号。"
    if name == "adx_neg":
        return "负向方向指标-DI，衡量下跌趋势强度。-DI上穿+DI为卖出信号。"

    # ── Aroon ──
    if name == "aroon_up":
        return "阿隆上升指标，衡量价格创N日新高的天数比例。值越高说明上涨趋势越强。"
    if name == "aroon_down":
        return "阿隆下降指标，衡量价格创N日新低的 days 比例。值越高说明下跌趋势越强。"

    # ── CCI ──
    if name.startswith("cci_"):
        n = name.split("_")[1]
        return f"{n}日商品通道指标，衡量价格相对于统计均值的偏离程度。CCI>+100超买，<-100超卖。"

    # ── TRIX ──
    if name == "trix":
        return "三重指数平滑移动平均，价格的三重指数平滑后的变动率。用于过滤短期噪音识别趋势。"

    # ── ATR ──
    if name.startswith("atr_"):
        n = name.split("_")[1]
        return f"{n}日平均真实波幅，衡量价格波动剧烈程度。ATR越大波动越剧烈，止损应设更宽。"

    # ── Bollinger ──
    if name == "bb_upper":
        return "布林带上轨，20日均线+2倍标准差。价格触及上轨说明超买，可能回调。"
    if name == "bb_lower":
        return "布林带下轨，20日均线-2倍标准差。价格触及下轨说明超卖，可能反弹。"
    if name == "bb_mid":
        return "布林带中轨，20日简单移动平均线。"
    if name == "bb_width":
        return "布林带宽，(上轨-下轨)÷中轨。带宽扩大说明波动加大，收窄说明变盘在即。"
    if name == "bb_pct":
        return "布林带位置，价格在布林带中的位置(0~1)。值接近1说明在上轨附近，接近0在下轨附近。"

    # ── Donchian ──
    if name == "dc_upper":
        return "唐奇安通道上轨，20日最高价。价格突破上轨为突破买入信号。"
    if name == "dc_lower":
        return "唐奇安通道下轨，20日最低价。价格跌破下轨为跌破卖出信号。"
    if name == "dc_mid":
        return "唐奇安通道中轨，(上轨+下轨)÷2。"

    # ── Ulcer ──
    if name.startswith("ulcer"):
        return "溃疡指数，衡量回撤深度和持续时间的风险指标。值越小说明回撤控制越好。"

    # ── OBV ──
    if name == "obv":
        return "能量潮指标，累计成交量按价格方向加权。OBV与价格同步新高说明上涨健康。"

    # ── AD ──
    if name == "ad":
        return "积累/分配线，利用收盘价在最高最低中的位置加权成交量。衡量资金是在流入还是流出。"

    # ── CMF ──
    if name == "cmf":
        return "佳庆资金流指标，20日资金流量累计。CMF>0资金净流入，<0资金净流出。"

    # ── EMV ──
    if name == "emv":
        return "简易波动指标，结合价格波动和成交量判断趋势。正值上涨轻松，负值下跌轻松。"

    # ── Force Index ──
    if name.startswith("fi_"):
        return "力量指数，价格变动×成交量。衡量多头或空头力量的强弱。"

    # ── MFI ──
    if name == "mfi":
        return "资金流量指标，类似RSI但加入成交量。MFI>80超买，<20超卖。"

    # ── VPT ──
    if name == "vpt":
        return "量价趋势指标，累计量价趋势线。用于判断量价配合的健康程度。"

    # ── VWAP ──
    if name == "vwap":
        return "成交量加权均价，机构大单交易的重要参考。价格>VWAP说明多头主导。"

    # ── Volume ──
    if name.startswith("vol_ratio_"):
        n = name.split("_")[2]
        return f"当前成交量与{n}日均量的比值。>1.5明显放量，<0.5明显缩量。量比突然放大常预示变盘。"
    if name.startswith("vol_roc_"):
        n = name.split("_")[2]
        return f"{n}日成交量变动率，成交量的增速。正值说明量能在放大。"

    # ── 衍生统计 ──
    if name.startswith("ret_skew_"):
        n = name.split("_")[2]
        return f"{n}日收益率偏度，衡量收益分布的不对称性。正偏态说明大涨次数比大跌多。"
    if name == "ret_kurt_20":
        return "20日收益率峰度，衡量收益分布的尾部风险。值>3说明容易出现极端收益。"
    if name.startswith("ret_pctile_"):
        n = name.split("_")[2]
        return f"当前收益率在最近{n}日中的分位排名(0~1)。>0.8说明近期表现很好。"
    if name == "consec_up":
        return "连续上涨天数。数字越大说明上涨持续性越强，也需警惕回调。"
    if name == "consec_down":
        return "连续下跌天数。数字越大说明下跌越惨烈，可能超跌反弹。"
    if name == "sharpe_20":
        return "20日滚动夏普比，衡量风险调整后收益。值越大单位风险带来的收益越高。"
    if name.startswith("pv_corr_"):
        n = name.split("_")[2]
        return f"{n}日量价相关性，价格变动与成交量变动的相关系数。正相关说明上涨带量，健康。"

    # ── 价格位置 ──
    if name.startswith("price_pos_"):
        n = name.split("_")[2]
        return f"{n}日价格位置，(收盘价-近期最低)÷(近期最高-近期最低)。值接近1说明处于高位。"

    # ── 赛道特征 ──
    if name.startswith("track_"):
        track_name, metric, period = _parse_track_feature(name)
        track_display = track_name.replace("-", "/").replace("_", "-")
        
        if metric == "mom" and period:
            return f"赛道{track_display}内个股{period}日相对动量，衡量该股在赛道中的短期表现。"
        if metric == "trend" and period:
            return f"赛道{track_display}内个股{period}日趋势斜率，线性回归拟合的方向强度。"
        if metric == "volatility" and period:
            return f"赛道{track_display}内个股{period}日波动率，衡量股价稳定性。"
        if metric == "volume_ratio" and period:
            return f"赛道{track_display}内个股{period}日量比，在该赛道中的放量/缩量程度。"
        if metric == "amihud_illiq":
            return f"赛道{track_display}内Amihud非流动性指标，衡量交易冲击成本。值大=流动性差。"
        if metric == "money_flow" and period:
            return f"赛道{track_display}内个股{period}日资金流，(收盘-开盘)×成交量近似估算。"
        if metric == "money_flow_ratio" and period:
            return f"赛道{track_display}内个股{period}日资金流比率。接近1=持续流入，接近0=持续流出。"
        if metric == "max_ret" and period:
            return f"赛道{track_display}内个股最近{period}日最大单日涨幅，捕捉脉冲行情。"
        if metric == "min_ret" and period:
            return f"赛道{track_display}内个股最近{period}日最大单日跌幅，识别恐慌抛售。"
        if metric == "avg_ret" and period:
            return f"赛道{track_display}内个股最近{period}日平均日收益率，衡量中枢表现。"
        
        return f"赛道{track_display}专属特征，同赛道内横向对比使用。"

    return ""


def gen_formula(name: str) -> str:
    """根据特征名生成计算公式"""
    
    if name.startswith("rsi_"):
        n = name.split("_")[1]
        return f"RSI = 100 - 100/(1+RS)，RS = {n}日平均涨幅 ÷ {n}日平均跌幅"
    if name == "stoch_k":
        return "%K = (收盘价 - 9日最低) / (9日最高 - 9日最低) × 100"
    if name == "stoch_d":
        return "%D = %K 的 3 日简单移动平均"
    if name == "stoch_j":
        return "J = 3 × %K - 2 × %D"
    if name.startswith("willr_"):
        n = name.split("_")[1]
        return f"%R = ({n}日最高 - 收盘) / ({n}日最高 - {n}日最低) × -100"
    if name.startswith("roc_"):
        n = name.split("_")[1]
        return f"ROC = (今收 ÷ {n}日前收盘 - 1) × 100"
    if name == "ao":
        return "AO = 5日简单均线(中价) - 34日简单均线(中价)，中价=(H+L)/2"
    if name == "ppo":
        return "PPO = (12日EMA - 26日EMA) / 26日EMA × 100"
    if name == "ppo_signal":
        return "PPO_Signal = PPO 的 9 日 EMA"
    if name.startswith("sma_") and not "dev" in name:
        n = name.split("_")[1]
        return f"SMA = 最近{n}日收盘价之和 ÷ {n}"
    if name.startswith("sma_dev_"):
        n = name.split("_")[2]
        return f"偏离度 = (收盘价 - {n}日SMA) / {n}日SMA"
    if name.startswith("ema_") and not "dev" in name:
        n = name.split("_")[1]
        return f"EMA = 当前价 × (2/({int(n)+1})) + 前日EMA × (1 - 2/({int(n)+1}))"
    if name.startswith("ema_dev_"):
        n = name.split("_")[2]
        return f"偏离度 = (收盘价 - {n}日EMA) / {n}日EMA"
    if name == "macd":
        return "MACD = 12日EMA - 26日EMA"
    if name == "macd_signal":
        return "Signal = MACD 的 9 日 EMA"
    if name == "macd_hist":
        return "Histogram = MACD - Signal"
    if name == "adx":
        return "ADX = 100×|+DI - -DI| / (+DI + -DI) 的 14 日平滑移动均线"
    if name == "adx_pos":
        return "+DI = 14日正向动向 ÷ 14日真实波幅 × 100"
    if name == "adx_neg":
        return "-DI = 14日负向动向 ÷ 14日真实波幅 × 100"
    if name == "aroon_up":
        return "Aroon_Up = (25 - 最近N日最高价距今天数) / 25 × 100"
    if name == "aroon_down":
        return "Aroon_Down = (25 - 最近N日最低价距今天数) / 25 × 100"
    if name.startswith("cci_"):
        n = name.split("_")[1]
        return f"CCI = (TP - TP的{n}日SMA) / (0.015×TP的平均绝对偏差)，TP=(H+L+C)/3"
    if name == "trix":
        return "TRIX = 三重EMA的变动率，EMA3 = EMA(EMA(EMA(close)))"
    if name.startswith("atr_"):
        n = name.split("_")[1]
        return f"ATR = {n}日TR均值，TR=MAX(H-L, |H-前收|, |L-前收|)"
    if name == "bb_upper":
        return "BB_Upper = 20日SMA + 2×20日标准差"
    if name == "bb_lower":
        return "BB_Lower = 20日SMA - 2×20日标准差"
    if name == "bb_mid":
        return "BB_Mid = 20日SMA"
    if name == "bb_width":
        return "BB_Width = (BB_Upper - BB_Lower) / BB_Mid"
    if name == "bb_pct":
        return "BB_% = (收盘价 - BB_Lower) / (BB_Upper - BB_Lower)"
    if name == "dc_upper":
        return "DC_Upper = 20日最高价"
    if name == "dc_lower":
        return "DC_Lower = 20日最低价"
    if name == "dc_mid":
        return "DC_Mid = (DC_Upper + DC_Lower) / 2"
    if name.startswith("ulcer"):
        return "Ulcer = sqrt(Σ(回撤百分比²)/N)，回撤=(最高-当前)/最高"
    if name == "obv":
        return "OBV = Σ(成交量×方向)，方向=涨+1/跌-1"
    if name == "ad":
        return "A/D = Σ(((收盘-最低)-(最高-收盘))/(最高-最低)×成交量)"
    if name == "cmf":
        return "CMF = Σ(资金流量×成交量)/Σ(成交量)，资金流量=(C-L-(H-C))/(H-L)"
    if name == "emv":
        return "EMV = (H+L)/2的变化率 × 成交量比率"
    if name.startswith("fi_"):
        return "FI = 价格变动 × 成交量"
    if name == "mfi":
        return "MFI = 100 - 100/(1+正资金流/负资金流)，14日"
    if name == "vpt":
        return "VPT = 累计(成交量×当日收益率)"
    if name == "vwap":
        return "VWAP = Σ(典型价×成交量)/Σ(成交量)，典型价=(H+L+C)/3"
    if name.startswith("vol_ratio_"):
        n = name.split("_")[2]
        return f"量比 = 当前成交量 / {n}日平均成交量"
    if name.startswith("vol_roc_"):
        n = name.split("_")[2]
        return f"量能ROC = (今量/{n}日前量 - 1)×100"
    if name.startswith("ret_skew_"):
        n = name.split("_")[2]
        return f"偏度 = (1/N)Σ((日收益率-均值)/标准差)³"
    if name == "ret_kurt_20":
        return "峰度 = (1/N)Σ((日收益率-均值)/标准差)⁴ - 3"
    if name.startswith("ret_pctile_"):
        n = name.split("_")[2]
        return f"分位 = 当日收益率在最近{n}日中的百分位排名"
    if name == "consec_up":
        return "连续上涨天数 = 累计日收益率>0的天数，遇跌归零"
    if name == "consec_down":
        return "连续下跌天数 = 累计日收益率<0的天数（负值），遇涨归零"
    if name == "sharpe_20":
        return "20日夏普 = 20日平均收益率 / 20日收益率标准差"
    if name.startswith("pv_corr_"):
        n = name.split("_")[2]
        return f"{n}日量价Pearson相关系数"
    if name.startswith("price_pos_"):
        n = name.split("_")[2]
        return f"位置 = (收盘价 - {n}日最低) / ({n}日最高 - {n}日最低)"
    
    # 赛道特征公式
    if name.startswith("track_"):
        _, metric, period = _parse_track_feature(name)
        if metric == "mom" and period:
            return f"动量 = (今收 / {period}日前收盘) - 1"
        if metric == "trend" and period:
            return f"趋势 = 最近{period}日收盘价线性回归斜率(polyfit)"
        if metric == "volatility" and period:
            return f"波动率 = 最近{period}日日收益率的标准差"
        if metric == "volume_ratio" and period:
            return f"量比 = 成交量 / {period}日平均成交量"
        if metric == "amihud_illiq":
            return "非流动性 = 20日平均(|日收益率| / 成交额)"
        if metric == "money_flow" and period:
            return f"资金流 = SMA((收盘-开盘)×成交量, {period})"
        if metric == "money_flow_ratio" and period:
            return f"资金流比率 = SMA(正资金流, {period}) / SMA(|资金流|, {period})"
        if metric in ("max_ret", "min_ret", "avg_ret") and period:
            return f"最近{period}日的收益率统计值"
        return ""
    
    return ""


def gen_interpretation(name: str) -> str:
    """根据特征名生成解读方法"""
    
    if name.startswith("rsi_"):
        n = name.split("_")[1]
        return f"RSI>70超买(可能回调)，RSI<30超卖(可能反弹)。{n}日周期越长信号越平滑。"
    if name == "stoch_k":
        return "K线>80并拐头向下→卖出。K线<20并拐头向上→买入。"
    if name == "stoch_d":
        return "D线比K线平滑，D线>80拐头确认超买。金叉(D上穿K)=买入。"
    if name == "stoch_j":
        return "J线最敏感，J>100视为超买风险区，J<0视为超卖机会区。"
    if name.startswith("willr_"):
        return "值>-20超买，<-80超卖。极端值常预示短期反转。"
    if name.startswith("roc_"):
        return "ROC上穿0轴→价格加速上涨。ROC下穿0轴→加速下跌。ROC>0多头主导。"
    if name == "ao":
        return "AO>0且上升→动量增强。AO<0且下降→动量衰减。AO上穿0轴=买入信号。"
    if name == "ppo" or name == "ppo_signal":
        return "PPO>0短期均值>长期均值(多头)。PPO上穿信号线=金叉买入。"
    if name.startswith("sma_") and not "dev" in name:
        n = name.split("_")[1]
        return f"收盘>{n}MA→短/中期强势。收盘<{n}MA→弱势。{n}MA走平可能变盘。"
    if name.startswith("sma_dev_"):
        n = name.split("_")[2]
        return f"偏离>+5%→短期过热可能回调。偏离<-5%→短期超跌可能反弹。偏离越大回归概率越高。"
    if name.startswith("ema_dev_"):
        return "正值说明价格在均线上方(多头优势)。负值在下方(空头优势)。"
    if name == "macd":
        return "MACD>0→多头。MACD<0→空头。MACD向上=动能增强。"
    if name == "macd_signal":
        return "MACD上穿Signal=金叉买入。下穿=死叉卖出。金叉在0轴上方更可靠。"
    if name == "macd_hist":
        return "柱体扩大=趋势加速。柱体缩小=趋势衰减。柱体由红转绿=顶背离信号。"
    if name == "adx":
        return "ADX>25→趋势行情(顺势交易)。ADX<20→震荡行情(高抛低吸)。ADX上升=趋势在加强。"
    if name == "adx_pos" or name == "adx_neg":
        return "+DI上穿-DI→买入。-DI上穿+DI→卖出。配合ADX>25使用更可靠。"
    if name == "aroon_up":
        return "Aroon_Up>70→上涨趋势强劲。<30→上涨趋势弱或横盘。"
    if name == "aroon_down":
        return "Aroon_Down>70→下跌趋势强劲。<30→下跌趋势弱或横盘。"
    if name.startswith("cci_"):
        return "CCI>+100超买(可能回调)。CCI<-100超卖(可能反弹)。CCI从超卖区回升=买入时机。"
    if name == "trix":
        return "TRIX上穿0轴→多头趋势确认。TRIX下穿0轴→空头趋势。TRIX金叉=买入信号。"
    if name.startswith("atr_"):
        return "ATR越大→波动越剧烈，止损需放宽。ATR与价格同向上升=趋势健康。ATR低位=盘整待变。"
    if name == "bb_upper":
        return "价格触及上轨→超买压力，可能回调至中轨。"
    if name == "bb_lower":
        return "价格触及下轨→超卖支撑，可能反弹至中轨。"
    if name == "bb_width":
        return "带宽从窄变宽→变盘启动。带宽从宽变窄→趋势减弱。"
    if name == "bb_pct":
        return "%B>1在上轨外(极度超买)。%B<0在下轨外(极度超卖)。%B在0.2~0.8之间为正常区间。"
    if name == "dc_upper":
        return "价格突破上轨→突破买入信号。上轨走平价格回落→假突破。"
    if name == "dc_lower":
        return "价格跌破下轨→突破卖出信号。下轨走平价格回升→假跌破。"
    if name.startswith("ulcer"):
        return "Ulcer<5→回撤控制极好。Ulcer>15→回撤过大，需要警惕。"
    if name == "obv":
        return "OBV与价格同步新高→上涨健康。OBV背离价格(价格新高OBV不新高)→趋势可能反转。"
    if name == "ad":
        return "A/D与价格同步上升→资金在积累。A/D背离价格→资金在悄悄出货。"
    if name == "cmf":
        return "CMF>0→资金净流入(持仓)。CMF<0→资金净流出(减仓)。CMF与价格背离=危险信号。"
    if name == "emv":
        return "EMV>0→上涨轻松(量价配合好)。EMV<0→下跌轻松(抛压重)。"
    if name.startswith("fi_"):
        return "FI>0→多头力量强。FI<0→空头力量强。FI巨幅波动→极端行情。"
    if name == "mfi":
        return "MFI>80→超买(回调风险)。MFI<20→超卖(反弹机会)。MFI与价格背离=反转信号。"
    if name == "vpt":
        return "VPT上升→量价配合好。VPT下降→量价背离。VPT新高确认上涨趋势。"
    if name == "vwap":
        return "价格>VWAP→多头主导(适合做多)。价格<VWAP→空头主导(适合观望)。"
    if name.startswith("vol_ratio_"):
        n = name.split("_")[2]
        return f"量比>1.5→明显放量，关注方向选择。>3→极端放量，可能有重大事件。量比<0.5→缩量整理。"
    if name.startswith("vol_roc_"):
        return "量能ROC>0→量能放大。ROC持续上升→量能加速，行情可能爆发。"
    if name.startswith("ret_skew_"):
        return "正偏态→大涨次数多(适合做多)。负偏态→大跌次数多(需谨慎)。"
    if name == "ret_kurt_20":
        return "峰度>3→容易出现极端行情(黑天鹅风险高)。峰度<3→收益分布较温和。"
    if name.startswith("ret_pctile_"):
        return "分位>0.8→近期表现优秀(但可能追高)。分位<0.2→近期表现差(可能超跌机会)。"
    if name == "consec_up":
        return "连涨>5天→短期过热，注意回调风险。连涨阶段量能萎缩→上涨乏力。"
    if name == "consec_down":
        return "连跌>5天→短期超卖，关注反弹机会。连跌放量→恐慌盘涌出(可能是最后一跌)。"
    if name == "sharpe_20":
        return "夏普>1→风险调整后收益好。夏普<0→收益无法覆盖波动(不如买理财)。"
    if name.startswith("pv_corr_"):
        return "正相关→上涨带量(健康的上涨)。负相关→上涨缩量(量价背离，需警惕)。"
    if name.startswith("price_pos_"):
        return "位置>0.8→处于区间高位(可能回调)。位置<0.2→处于区间低位(可能反弹)。"
        
    # 赛道专属特征
    if name.startswith("track_"):
        _, metric, _ = _parse_track_feature(name)
        
        if metric == "mom":
            return "正值→该股在赛道内表现领先。负值→落后。赛道内相对排名比绝对值更重要。"
        if metric == "trend":
            return "正斜率→赛道内趋势向上。负斜率→向下。斜率绝对值越大趋势越强。"
        if metric == "volatility":
            return "波动率大→该股在赛道内弹性好(适合波段)。波动率小→走势稳健。"
        if metric == "volume_ratio":
            return "量比>1.2→赛道内放量。<0.8→赛道内缩量。同赛道内横向比更有意义。"
        if metric == "amihud_illiq":
            return "值越大交易成本越高。同赛道内比较：大盘股流动性好(值小)，小盘股差(值大)。"
        if metric == "money_flow":
            return "正值→资金净流入。持续为正说明正在被加仓。趋势方向比绝对值更重要。"
        if metric == "money_flow_ratio":
            return ">0.5→流入为主。<0.5→流出为主。>0.8说明赛道内资金最青睐。"
        if metric in ("max_ret", "min_ret", "avg_ret"):
            return "在赛道内比较：最大涨幅高说明弹性好，最大跌幅大说明风险高，均值衡量中枢。"
        
        return "赛道维度下的相对评估指标，横向对比同赛道个股效果更佳。"
    
    return "IC值为正: 因子值越大，未来收益越高。IC值为负: 因子值越小，未来收益越低。"


# ══════════════════════════════════════════════════════════
# 解析工具
# ══════════════════════════════════════════════════════════


def _parse_track_feature(name: str) -> tuple[str, str, str]:
    """解析赛道特征名，返回 (track_name, metric, period).
    
    支持复合 metric 名：amihud_illiq, money_flow, money_flow_ratio
    赛道名：ai, ai-power, semiconductor, robot, storage, material
    
    举例:
      track_semiconductor_mom_5d  → ("semiconductor", "mom", "5")
      track_ai_amihud_illiq       → ("ai", "amihud_illiq", "")
      track_ai-power_money_flow_ratio_20d → ("ai-power", "money_flow_ratio", "20")
    """
    suffix = name.replace("track_", "", 1)
    
    # 按长度降序，确保复合名（money_flow_ratio）优先于简单名（money_flow）
    metrics = sorted(["mom", "trend", "volatility", "volume_ratio", 
                       "amihud_illiq", "money_flow_ratio", "money_flow",
                       "max_ret", "min_ret", "avg_ret"],
                      key=len, reverse=True)
    
    for m in metrics:
        search = f"_{m}_" if not suffix.endswith(f"_{m}") else f"_{m}"
        if search in suffix:
            idx = suffix.index(search)
            track_name = suffix[:idx]
            rest = suffix[idx + len(search):]
            period = rest[:-1] if rest.endswith("d") else ""
            return (track_name, m, period)
    
    return ("unknown", "unknown", "")


async def main():
    async with async_session_maker() as session:
        result = await session.execute(select(FeatureConfig))
        configs = result.scalars().all()
        
        updated = 0
        for cfg in configs:
            dirty = False
            
            desc = gen_description(cfg.feature_name)
            if desc and (not cfg.description or len(cfg.description) < 10):
                cfg.description = desc
                dirty = True
            
            formula = gen_formula(cfg.feature_name)
            if formula and (not cfg.formula or len(cfg.formula) < 3):
                cfg.formula = formula
                dirty = True
            
            interp = gen_interpretation(cfg.feature_name)
            if interp:
                old_is_default = (not cfg.interpretation or 
                    cfg.interpretation.startswith("IC值为正"))
                if old_is_default:
                    cfg.interpretation = interp
                    dirty = True
            
            if dirty:
                updated += 1
        
        await session.commit()
        
        print(f"Total configs: {len(configs)}")
        print(f"Updated: {updated}")
        
        # 验证
        result2 = await session.execute(select(FeatureConfig))
        configs2 = result2.scalars().all()
        have_desc = sum(1 for c in configs2 if c.description and len(c.description) > 10)
        have_formula = sum(1 for c in configs2 if c.formula and len(c.formula) > 3)
        have_interp = sum(1 for c in configs2 if c.interpretation and not c.interpretation.startswith("IC值为正"))
        print(f"\nVerification:")
        print(f"  有释义: {have_desc}/{len(configs2)}")
        print(f"  有公式: {have_formula}/{len(configs2)}")
        print(f"  有独特点读: {have_interp}/{len(configs2)}")


if __name__ == "__main__":
    asyncio.run(main())
