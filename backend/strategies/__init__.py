"""
量化策略注册表。

每个策略是一个 SignalGenerator：
  generate_signals(prices: pd.DataFrame, **params) -> pd.DataFrame

返回 DataFrame，index=date, columns 包含 'buy' (list[str]) 和可选的 'weights' (dict[str,float])。
"""

from strategies.equal_weight import EqualWeightStrategy
from strategies.momentum import MomentumStrategy
from strategies.ai_scoring import AIScoringStrategy

# 策略注册表 {name: (class, display_name, description)}
STRATEGY_REGISTRY: dict[str, dict] = {
    "equal_weight": {
        "name": "等权持有",
        "type": "baseline",
        "description": "等权持有所有赛道股票，不选股",
        "generator": EqualWeightStrategy(),
    },
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
        "description": "高波动组中选20日动量最强Top-3（Blitz 2011残差动量思路）",
        "generator": MomentumStrategy(lookback=20, top_n=3, rebalance="M", vol_filter=True),
    },
    "ai_scoring": {
        "name": "AI 打分轮动",
        "type": "ai",
        "description": "LightGBM 模型预测赛道内相对强弱，买Top-3",
        "generator": AIScoringStrategy(),
    },
}

BASELINE_STRATEGIES = ["equal_weight", "momentum_20d"]


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
        }
        for key, v in STRATEGY_REGISTRY.items()
    ]
