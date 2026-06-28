"""
策略详情 API.

提供策略元数据查询 + 历史绩效查询。
数据来源: strategies 模块已注册的元数据 + pipeline_runs 表中的回测历史。
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from app.db.database import async_session_maker
from sqlalchemy import select, desc

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/strategies/list", summary="获取所有策略元数据")
async def list_strategies():
    """返回已注册的 12+ 策略的元数据列表（不含 generator 实例）。"""
    from strategies.signal_base import list_registered_strategies
    try:
        return list_registered_strategies()
    except Exception as e:
        # 如果 strategies 模块未导入，手动触发导入
        import strategies  # noqa: F401
        import importlib
        importlib.reload(strategies)
        from strategies.signal_base import list_registered_strategies
        return list_registered_strategies()


@router.get("/strategies/{key}", summary="获取单个策略详情")
async def get_strategy_detail(key: str):
    """返回单个策略的完整元数据 + 历史绩效摘要。"""
    from strategies.signal_base import get_strategy_meta, list_registered_strategies

    meta = get_strategy_meta(key)
    if meta is None:
        # 触发导入重试
        import strategies  # noqa: F401
        from strategies.signal_base import get_strategy_meta
        meta = get_strategy_meta(key)

    if meta is None:
        raise HTTPException(status_code=404, detail=f"未知策略: {key}")

    # 查询历史绩效
    performance = await _get_strategy_performance(key)
    return {**meta, "performance": performance}


@router.get("/strategies/{key}/performance", summary="获取策略在各赛道的绩效")
async def get_strategy_performance(key: str):
    """返回策略在各赛道的最新回测绩效指标。"""
    perf = await _get_strategy_performance(key)
    return {"strategy_key": key, "performance": perf}


async def _get_strategy_performance(key: str) -> list[dict]:
    """从 pipeline_runs 表中查询策略在各赛道的绩效"""
    from app.models.track import PipelineRun
    import json

    results = []
    async with async_session_maker() as session:
        stmt = (
            select(PipelineRun)
            .where(PipelineRun.run_type == "backtest")
            .order_by(desc(PipelineRun.created_at))
            .limit(500)
        )
        result = await session.execute(stmt)
        records = result.scalars().all()

    # 按赛道去重，取最新的一次
    seen = set()
    for r in records:
        params = r.params_snapshot or {}
        strategy = params.get("strategy", "")
        track = params.get("track_name", "")
        perf_key = f"{key}:{track}"

        if strategy != key and key not in (params.get("strategy_key", ""), ""):
            # 宽松匹配：如果 strategy 字段不匹配，检查 results_summary
            summary = r.results_summary or {}
            if isinstance(summary, dict):
                strat_name = summary.get("strategy", summary.get("strategy_key", ""))
                if strat_name != key:
                    continue
            else:
                continue

        if perf_key in seen:
            continue
        seen.add(perf_key)

        summary = r.results_summary or {}
        perf_entry = {
            "track_name": track,
            "sharpe": summary.get("sharpe", summary.get("sharpe_ratio", 0)),
            "annual_return": summary.get("annual_return", summary.get("total_return", 0)),
            "max_drawdown": summary.get("max_drawdown", summary.get("max_dd", 0)),
            "win_rate": summary.get("win_rate", 0),
            "backtest_date": str(r.created_at)[:10] if r.created_at else "",
        }
        # 确保数值类型
        for k in ("sharpe", "annual_return", "max_drawdown", "win_rate"):
            try:
                perf_entry[k] = round(float(perf_entry[k] or 0), 4)
            except (ValueError, TypeError):
                perf_entry[k] = 0.0

        results.append(perf_entry)

    return results
