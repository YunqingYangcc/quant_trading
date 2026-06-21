"""
策略信号生成器基类 + AI 组合能力。

SignalGenerator 定义了统一的信号生成接口。
AIEnhanceMixin 提供将任意策略与 AI 模型打分组合的能力。

策略适配器体系：
  @register_strategy 装饰器自动注册策略到全局注册表。
  新策略只需：①创建类继承 SignalGenerator；②加装饰器；③实现 generate()。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd

# 保存内置 type 引用，防止被参数名覆盖
_BUILTIN_TYPE = type


# ── 策略元数据 schema ──


@dataclass
class StrategyMeta:
    """策略标准元数据——每个新策略必须填写"""
    key: str                              # 策略注册 key
    name: str                             # 显示名称
    type: str                             # 分类标签
    description: str                      # 一句话简介
    mechanism: str = ""                   # 运行机制大白话
    market_condition: str = ""            # 适用市场环境
    expected_effect: str = ""             # 预期效果
    limitations: str = ""                 # 局限性/风险
    params_detail: dict[str, str] = field(default_factory=dict)  # 参数说明 {param: 解释}


# ── 全局策略注册表 ──

_STRATEGY_REGISTRY: dict[str, dict] = {}


def register_strategy(
    key: str,
    name: str,
    strategy_type: str,
    description: str = "",
    mechanism: str = "",
    market_condition: str = "",
    expected_effect: str = "",
    limitations: str = "",
    params_detail: dict[str, str] | None = None,
) -> Callable:
    """
    策略注册装饰器——用在类上时会创建默认实例。
    也可直接调用 register_generator() 注册已有实例。

    用法（装饰器）：
        @register_strategy(key="my_strat", strategy_type="technical", ...)
        class MyStrategy(SignalGenerator): ...

    用法（直接调用）：
        register_strategy(key="my_strat", strategy_type="technical", ...)(MyStrategy())  ← 传入实例
    """
    meta = {
        "key": key,
        "name": name,
        "type": strategy_type,
        "description": description,
        "mechanism": mechanism,
        "market_condition": market_condition,
        "expected_effect": expected_effect,
        "limitations": limitations,
        "params_detail": params_detail or {},
    }
    def decorator(cls_or_instance: object) -> object:
        if isinstance(cls_or_instance, _BUILTIN_TYPE):
            # 是类 -> 创建默认实例（无参构造）
            # 注：对有参构造的策略，请直接传入实例
            instance = cls_or_instance()
        else:
            instance = cls_or_instance
        _STRATEGY_REGISTRY[key] = {**meta, "generator": instance}
        return cls_or_instance
    return decorator


def register_generator(
    key: str,
    name: str,
    strategy_type: str,
    description: str = "",
    mechanism: str = "",
    market_condition: str = "",
    expected_effect: str = "",
    limitations: str = "",
    params_detail: dict[str, str] | None = None,
    generator: object = None,
):
    """直接注册策略实例（非装饰器方式）"""
    _STRATEGY_REGISTRY[key] = {
        "key": key,
        "name": name,
        "type": strategy_type,
        "description": description,
        "mechanism": mechanism,
        "market_condition": market_condition,
        "expected_effect": expected_effect,
        "limitations": limitations,
        "params_detail": params_detail or {},
        "generator": generator,
    }


def get_strategy_meta(key: str) -> dict | None:
    """获取单条策略元数据（不含 generator）"""
    entry = _STRATEGY_REGISTRY.get(key)
    if entry is None:
        return None
    return {k: v for k, v in entry.items() if k != "generator"}


def list_registered_strategies() -> list[dict]:
    """列出所有注册策略（供前端使用）"""
    return [
        {k: v for k, v in entry.items() if k != "generator"}
        for entry in _STRATEGY_REGISTRY.values()
    ]


def get_strategy_instance(key: str):
    """获取策略实例"""
    entry = _STRATEGY_REGISTRY.get(key)
    if entry is None:
        raise ValueError(f"未知策略: {key}. 可用: {list(_STRATEGY_REGISTRY.keys())}")
    return entry["generator"]


def get_registry_keys() -> list[str]:
    return list(_STRATEGY_REGISTRY.keys())


class SignalGenerator(ABC):
    """策略信号生成器基类"""

    name: str = "base"
    description: str = ""
    params: dict[str, Any] = {}

    @abstractmethod
    def generate(
        self,
        prices: pd.DataFrame,
        features: pd.DataFrame | None = None,
        ai_scores: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """生成交易信号

        Args:
            prices: pivot table, index=date, columns=stock_code, values=close
            features: 可选，额外特征数据
            ai_scores: 可选，AI 模型打分 DataFrame [trade_date, stock_code, pred_score]

        Returns:
            组合模式: DataFrame with ['buy', 'weights', 'sell_all'], index=date
            单股模式: DataFrame with ['action'|'position', 'code'], index=date
        """
        ...

    def get_params(self) -> dict[str, Any]:
        return self.params.copy()

    def set_params(self, **kwargs):
        self.params.update(kwargs)


class AIEnhanceMixin:
    """AI 增强混入：将任意策略的信号用 AI 打分二次排序"""

    def enhance_with_ai(
        self,
        signals: pd.DataFrame,
        ai_scores: pd.DataFrame | None,
        top_n: int = 3,
    ) -> pd.DataFrame:
        """用 AI 打分增强策略信号

        对每个调仓日，将策略选出的股票按 AI 打分重新排序，
        只保留打分最高的 top_n 只。
        """
        if ai_scores is None or ai_scores.empty or signals.empty:
            return signals

        if "buy" not in signals.columns:
            return signals

        enhanced = []
        for date, row in signals.iterrows():
            buy_list = row.get("buy", [])
            if not buy_list:
                continue

            # 获取当天的 AI 打分
            date_scores = ai_scores[
                (ai_scores["trade_date"] <= date) &
                (ai_scores["stock_code"].isin(buy_list))
            ]
            if date_scores.empty:
                enhanced.append(row)
                continue

            latest = date_scores.loc[
                date_scores.groupby("stock_code")["trade_date"].idxmax()
            ]
            ranked = latest.sort_values("pred_score", ascending=False)
            top = ranked.head(top_n)["stock_code"].tolist()
            if not top:
                enhanced.append(row)
                continue

            w = row.get("weights", {})
            new_weights = {s: 1.0 / len(top) for s in top}
            row["buy"] = top
            row["weights"] = new_weights
            enhanced.append(row)

        return pd.DataFrame(enhanced) if enhanced else signals


def to_single_stock_signals(
    portfolio_signals: pd.DataFrame,
    stock_code: str,
    ai_scores: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """将组合信号转为单股信号（包含 AI 置信度仓位）"""
    if portfolio_signals.empty:
        return pd.DataFrame()
    rows = []
    for date, row in portfolio_signals.iterrows():
        buy_list = row.get("buy", [])
        weights = row.get("weights", {})

        if stock_code in buy_list:
            # 用 AI 置信度决定仓位
            pos = weights.get(stock_code, 0.95)
            # 如果有 AI 打分，用置信度调整
            if ai_scores is not None and not ai_scores.empty:
                from strategies.composite import ai_position_size, get_ai_score_for_stock
                score = get_ai_score_for_stock(ai_scores, stock_code, date)
                pos = ai_position_size(score)
            if pos > 0:
                rows.append({"date": date, "position": pos, "code": stock_code})
            else:
                rows.append({"date": date, "position": 0, "code": stock_code})
        else:
            rows.append({"date": date, "position": 0, "code": stock_code})
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame()
