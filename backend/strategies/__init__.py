"""
量化策略注册表。

每个策略是一个 SignalGenerator：
  generate(prices: pd.DataFrame, features=None, ai_scores=None) -> pd.DataFrame

返回 DataFrame，index=date, columns 包含 'buy' (list[str]) 和可选的 'weights' (dict[str,float])。

所有策略支持 AI 打分增强：传入 ai_scores 后，策略信号会被 AI 评分二次排序。
"""

from strategies.equal_weight import EqualWeightStrategy
from strategies.momentum import MomentumStrategy
from strategies.ai_scoring import AIScoringStrategy
from strategies.trend import MACrossStrategy, BreakoutStrategy
from strategies.mean_reversion import RSIStrategy, BollingerStrategy
from strategies.composite import MultiSignalVoting, AIConfidenceStrategy, AIFilterMixin

from strategies.signal_base import SignalGenerator, AIEnhanceMixin, to_single_stock_signals

# 策略注册表 {name: {name, type, description, generator, params}}
STRATEGY_REGISTRY: dict[str, dict] = {
    # ── 基线 ──
    "equal_weight": {
        "name": "等权持有",
        "type": "baseline",
        "description": "等权持有所有赛道股票，不选股，作为最低基准",
        "generator": EqualWeightStrategy(),
    },

    # ── 动量策略 ──
    "momentum_20d": {
        "name": "20日动量 Top-3",
        "type": "momentum",
        "description": "按过去20日收益率排序，月频买入前3名",
        "generator": MomentumStrategy(lookback=20, top_n=3, rebalance="M"),
    },
    "momentum_60d": {
        "name": "60日动量 Top-3",
        "type": "momentum",
        "description": "按过去60日收益率排序，月频买入前3名",
        "generator": MomentumStrategy(lookback=60, top_n=3, rebalance="M"),
    },
    "momentum_20d_vol": {
        "name": "20日动量+波动率 Top-3",
        "type": "momentum",
        "description": "高波动组中选20日动量最强Top-3（Blitz 2011残差动量）",
        "generator": MomentumStrategy(lookback=20, top_n=3, rebalance="M", vol_filter=True),
    },
    "momentum_20d_ai": {
        "name": "20日动量+AI增强",
        "type": "momentum",
        "description": "20日动量选股 + AI 打分二次排序",
        "generator": MomentumStrategy(lookback=20, top_n=3, rebalance="M", ai_enhanced=True),
    },

    # ── 技术指标策略 ──
    "ma_cross": {
        "name": "MA金叉死叉 Top-3",
        "type": "technical",
        "description": "5日均线上穿20日线买入，死叉卖出，AI+增强版本可选",
        "generator": MACrossStrategy(short_window=5, long_window=20, top_n=3),
    },
    "ma_cross_ai": {
        "name": "MA金叉+AI增强",
        "type": "technical",
        "description": "金叉选股 + AI 打分排序增强",
        "generator": MACrossStrategy(short_window=5, long_window=20, top_n=3),
    },
    "breakout": {
        "name": "20日突破 Top-3",
        "type": "technical",
        "description": "创20日新高买入，新低卖出",
        "generator": BreakoutStrategy(lookback=20, top_n=3),
    },
    "breakout_ai": {
        "name": "突破+AI增强",
        "type": "technical",
        "description": "突破选股 + AI 打分排序增强",
        "generator": BreakoutStrategy(lookback=20, top_n=3),
    },

    # ── 均值回归策略 ──
    "rsi_reversal": {
        "name": "RSI超卖反转",
        "type": "mean_reversion",
        "description": "RSI<30超卖买入，RSI>70超买卖出",
        "generator": RSIStrategy(period=14, oversold=30, overbought=70, top_n=3),
    },
    "bollinger_reversal": {
        "name": "布林带均值回归",
        "type": "mean_reversion",
        "description": "触及下轨买入，触及上轨卖出",
        "generator": BollingerStrategy(period=20, std_dev=2.0, top_n=3),
    },

    # ── AI 策略 ──
    "ai_scoring": {
        "name": "AI 打分轮动",
        "type": "ai",
        "description": "LightGBM 模型预测赛道内相对强弱，买Top-3",
        "generator": AIScoringStrategy(),
    },

    # ── AI 置信度 / 复合策略 ──
    "multi_vote": {
        "name": "三信号投票 (AI+动量+RSI)",
        "type": "composite",
        "description": "AI+动量+RSI 三信号投票，≥2票买入，AI置信度决定仓位",
        "generator": MultiSignalVoting(top_n=3, vote_threshold=2),
    },
    "ai_confidence": {
        "name": "AI 置信度分层轮动",
        "type": "ai",
        "description": "AI高分重仓、低分轻仓、低于0.5不买",
        "generator": AIConfidenceStrategy(top_n=5),
    },
}

# 基线策略（用于对比）
BASELINE_STRATEGIES = ["equal_weight", "momentum_20d"]

# 需要 AI 打分的策略
AI_REQUIRED_STRATEGIES = [
    k for k, v in STRATEGY_REGISTRY.items()
    if v["type"] in ("ai",) or k.endswith("_ai")
]


def get_strategy(name: str):
    """获取策略实例."""
    entry = STRATEGY_REGISTRY.get(name)
    if not entry:
        raise ValueError(f"未知策略: {name}. 可用: {list(STRATEGY_REGISTRY.keys())}")
    return entry["generator"]


def list_strategies() -> list[dict]:
    """列出所有策略（供前端使用）."""
    return [
        {
            "key": key,
            "name": v["name"],
            "type": v["type"],
            "description": v["description"],
            "is_baseline": key in BASELINE_STRATEGIES,
            "needs_ai": key in AI_REQUIRED_STRATEGIES,
        }
        for key, v in STRATEGY_REGISTRY.items()
    ]
