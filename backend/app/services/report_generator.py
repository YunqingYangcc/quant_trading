"""
自然语言回测报告生成器.

不依赖 LLM API，用规则模板从回测 metrics 生成中文分析文本。
"""

from typing import Any


def generate_backtest_report(
    strategy_name: str = "",
    sharpe: float = 0,
    max_dd: float = 0,
    win_rate: float = 0,
    annual_return: float = 0,
    benchmark_sharpe: float = 0,
    total_trades: int = 0,
    best_track: str = "",
    worst_track: str = "",
    extra: dict[str, Any] | None = None,
) -> str:
    """根据回测指标生成自然语言分析报告。

    返回一段中文分析文本，可直接嵌入回测结果页面。
    """
    extra = extra or {}
    parts = []

    # 1. 总体评价
    if sharpe > 1.0:
        parts.append(
            f"本轮回测中，{strategy_name} 策略表现优异 (Sharpe {sharpe:.2f})，"
            "超额收益显著，策略有效性得到数据支撑。"
        )
    elif sharpe > 0.5:
        parts.append(
            f"本轮回测中，{strategy_name} 策略表现合格 (Sharpe {sharpe:.2f})，"
            "能够产生正超额收益，但在某些行情下仍需优化。"
        )
    elif sharpe > 0:
        parts.append(
            f"本轮回测中，{strategy_name} 策略勉强为正 (Sharpe {sharpe:.2f})，"
            "收益有限，可能需要调整参数或结合其他策略使用。"
        )
    else:
        parts.append(
            f"本轮回测中，{strategy_name} 策略表现不佳 (Sharpe {sharpe:.2f})，"
            "当前参数下未产生正超额收益，建议重新评估策略逻辑。"
        )

    # 2. 基准对比
    if benchmark_sharpe:
        diff = sharpe - benchmark_sharpe
        if diff > 0.3:
            parts.append(f"相比基准策略 (Sharpe {benchmark_sharpe:.2f})，超额收益显著 (+{diff:.2f})。")
        elif diff > 0:
            parts.append(f"相比基准策略 (Sharpe {benchmark_sharpe:.2f})，略优 (+{diff:.2f})。")
        else:
            parts.append(f"相比基准策略 (Sharpe {benchmark_sharpe:.2f})，略逊 ({diff:.2f})。")

    # 3. 风险分析
    dd_pct = abs(max_dd) * 100 if max_dd else 0
    if dd_pct < 10:
        parts.append(f"最大回撤仅 {dd_pct:.1f}%，风控表现优秀，持仓体验良好。")
    elif dd_pct < 20:
        parts.append(f"最大回撤 {dd_pct:.1f}%，处于可接受范围，但需关注极端行情下的尾部风险。")
    else:
        parts.append(f"最大回撤 {dd_pct:.1f}%，风险偏高。建议收紧止损或降低单票仓位上限。")

    # 4. 胜率分析
    wr = win_rate * 100 if win_rate < 1 else win_rate
    if wr > 55:
        parts.append(f"胜率 {wr:.1f}%，策略选股质量较高。")
    elif wr > 45:
        parts.append(f"胜率 {wr:.1f}%，接近随机，收益主要靠盈亏比支撑。")
    else:
        parts.append(f"胜率 {wr:.1f}%，偏低，策略可能过度交易或在不利行情中频繁进出。")

    # 5. 赛道归因
    if best_track:
        parts.append(f"最佳赛道为 {best_track}，该赛道在该策略下表现突出。")
    if worst_track:
        parts.append(f"{worst_track} 赛道表现偏弱，可能是主要拖累来源。")

    # 6. 交易频率
    if total_trades > 50:
        parts.append(f"交易频率较高 ({total_trades} 笔)，需关注手续费和滑点对收益的侵蚀。")
    elif total_trades > 0:
        parts.append(f"交易频率适中 ({total_trades} 笔)，换手率合理。")

    # 7. 总结
    if sharpe > 0.8:
        parts.append("整体来看，该策略在当前参数下表现稳健，建议继续跟踪并关注行情适配性。")
    elif sharpe > 0.3:
        parts.append("策略有一定效果但不够稳定，建议结合市场状态聚类结果，在牛市行情中加大配置。")
    else:
        parts.append("建议重新审视策略逻辑和参数，考虑与其他策略组合使用以降低波动。")

    return "\n\n".join(parts)


def generate_recommendation_report(
    stock_code: str = "",
    score: float = 0,
    trends: list[str] | None = None,
    risks: list[str] | None = None,
) -> str:
    """为单只股票的推荐生成分析报告。"""
    parts = []
    if score > 0.7:
        parts.append(f"{stock_code} AI 综合评分 {score:.2f}，位于高分区间，多维度信号共振。")
    elif score > 0.55:
        parts.append(f"{stock_code} AI 综合评分 {score:.2f}，处于中等偏上，部分维度表现突出。")
    else:
        parts.append(f"{stock_code} AI 综合评分 {score:.2f}，当前信号偏弱，建议观望。")

    if trends:
        parts.append("积极信号: " + "、".join(trends))
    if risks:
        parts.append("风险提示: " + "、".join(risks))

    return "\n".join(parts)
