"""
量化交易员学习和成长平台 — 回测对比 API

提供：
  1. 多策略对比回测 (POST /backtest/compare)
  2. 回测运行历史 (GET /backtest/history)
  3. 单次回测详情 (GET /backtest/history/{run_id})
  4. 学习看板统计 (GET /learning/stats)
"""

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = BASE_DIR / "ml" / "models"
PREPROCESSED_DIR = BASE_DIR / "ml" / "preprocessed"
BACKTEST_DIR = BASE_DIR / "ml" / "backtest"

# ── 锁定回测参数 ──
_LOCKED_PARAMS = {
    "slippage": 0.001,
    "commission": 0.0003,
    "skip_limit_up": True,
    "skip_limit_down": True,
}

# ── Schema ──


class CompareBacktestParams(BaseModel):
    """多策略对比回测参数"""
    strategies: list[str] = Field(
        ..., description="策略名列表 (至少1个,最多6个)",
        min_length=1, max_length=6,
    )
    track_name: str = Field(default="semiconductor", description="赛道名")
    initial_capital: int = Field(default=100000, ge=10000, le=10000000)
    top_n: int = Field(default=3, ge=1, le=10)
    rebalance_freq: str = Field(default="W", pattern="^(W|M)$")
    max_single_stock: float = Field(default=0.20, ge=0.05, le=0.50)
    max_single_track: float = Field(default=0.50, ge=0.10, le=0.80)
    stop_loss_pct: float = Field(default=-0.15, ge=-0.50, le=0)
    take_profit_pct: float = Field(default=0.30, ge=0, le=0.50)


# ── 数据加载 ──


async def _load_prices_and_scores(track_name: str) -> tuple[pd.DataFrame, pd.DataFrame | None, list[str]]:
    """加载指定赛道的历史价格和 AI 打分"""
    try:
        prices = pd.read_parquet(PREPROCESSED_DIR / "backtest_prices.parquet")
    except Exception:
        raise HTTPException(status_code=500, detail="回测价格数据未生成, 请先运行 pipeline")

    # 获取赛道股票列表
    from sqlalchemy import select
    from app.db.database import async_session_maker
    from app.models.track import Track, track_stock

    async with async_session_maker() as session:
        track_result = await session.execute(
            select(Track).where(Track.name == track_name, Track.is_active == 1)
        )
        track = track_result.scalar_one_or_none()
        if not track:
            raise HTTPException(status_code=404, detail=f"赛道 '{track_name}' 不存在")
        stocks_result = await session.execute(
            select(track_stock.c.stock_code).where(track_stock.c.track_id == track.id)
        )
        stock_codes = [r[0] for r in stocks_result.all()]

    # 过滤价格
    valid_cols = [c for c in prices.columns if c in stock_codes]
    if not valid_cols:
        raise HTTPException(status_code=400, detail=f"赛道 {track_name} 无可用价格数据")
    prices = prices[valid_cols]

    # 加载 AI 打分
    ai_scores = None
    scores_path = PREPROCESSED_DIR / "backtest_scores.parquet"
    if scores_path.exists():
        ai_scores = pd.read_parquet(scores_path)
        ai_scores["trade_date"] = pd.to_datetime(ai_scores["trade_date"])

    return prices, ai_scores, valid_cols


def _load_strategy(strategy_name: str):
    """动态加载策略"""
    import importlib.util as _util

    script_path = BASE_DIR / "scripts" / "run_backtest.py"
    spec = _util.spec_from_file_location("run_backtest", script_path)
    if not spec or not spec.loader:
        raise HTTPException(status_code=500, detail="策略模块加载失败")
    bt = _util.module_from_spec(spec)
    spec.loader.exec_module(bt)

    from strategies import STRATEGY_REGISTRY
    entry = STRATEGY_REGISTRY.get(strategy_name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"未知策略: {strategy_name}")
    return entry["generator"], entry["name"]


def _run_single_strategy(
    gen,
    prices: pd.DataFrame,
    ai_scores: pd.DataFrame | None,
    params: dict,
) -> tuple[list[dict], list[dict], dict]:
    """运行单个策略回测, 返回 (equity_curve, trades, metrics)"""
    from backtest.engine import BacktestEngine

    # 生成信号
    signals = gen.generate(prices, ai_scores=ai_scores)
    if signals.empty:
        return [], [], {"error": "无信号"}

    # 执行回测
    engine = BacktestEngine(params={
        "initial_capital": params["initial_capital"],
        "slippage": _LOCKED_PARAMS["slippage"],
        "commission": _LOCKED_PARAMS["commission"],
        "max_single_stock": params["max_single_stock"],
        "max_single_track": params["max_single_track"],
        "skip_limit_up": _LOCKED_PARAMS["skip_limit_up"],
        "skip_limit_down": _LOCKED_PARAMS["skip_limit_down"],
        "stop_loss_pct": params["stop_loss_pct"],
        "take_profit_pct": params["take_profit_pct"],
    })

    equity_curve, trades, metrics = engine.run(signals, prices)
    return equity_curve, trades, metrics


def _calc_benchmark(prices: pd.DataFrame, initial_capital: float) -> list[dict]:
    """简单基准: 等权持有所有股票"""
    from backtest.report import buy_and_hold_curve

    # 等权组合净值
    weights = 1.0 / len(prices.columns)
    combined = prices.apply(lambda col: col * weights, axis=1).sum(axis=1)
    return buy_and_hold_curve(combined, initial_capital)


# ── 多策略对比 ──


@router.post("/backtest/compare", summary="多策略对比回测")
async def compare_strategies(params: CompareBacktestParams):
    """运行多个策略回测并返回对比结果

    返回每个策略的净值曲线、交易明细和指标, 以及基准曲线。
    """
    prices, ai_scores, stock_codes = await _load_prices_and_scores(params.track_name)

    # 转为每个strategy配置参数
    bt_params = {
        "initial_capital": params.initial_capital,
        "top_n": params.top_n,
        "rebalance_freq": params.rebalance_freq,
        "max_single_stock": params.max_single_stock,
        "max_single_track": params.max_single_track,
        "stop_loss_pct": params.stop_loss_pct,
        "take_profit_pct": params.take_profit_pct,
    }

    results = {}
    for strategy_name in params.strategies:
        try:
            gen, display_name = _load_strategy(strategy_name)
        except HTTPException:
            results[strategy_name] = {"error": f"未知策略: {strategy_name}"}
            continue

        try:
            equity_curve, trades, metrics = _run_single_strategy(
                gen, prices, ai_scores, bt_params
            )
            results[strategy_name] = {
                "name": display_name,
                "equity_curve": equity_curve,
                "trades": trades,
                "metrics": metrics,
            }
        except Exception as e:
            logger.error(f"策略 {strategy_name} 回测失败: {e}")
            results[strategy_name] = {"error": str(e), "name": display_name}

    # 基准
    benchmark_curve = _calc_benchmark(prices, params.initial_capital)

    return {
        "strategies": results,
        "benchmark_curve": benchmark_curve,
        "params": bt_params,
        "stock_count": len(stock_codes),
        "track_name": params.track_name,
    }


# ── 回测运行历史 ──


@router.get("/backtest/history", summary="获取回测运行历史")
async def list_backtest_history(limit: int = Query(default=20, ge=1, le=100)):
    """获取最近 N 次回测运行记录"""
    from sqlalchemy import select, desc
    from app.models.track import PipelineRun
    from app.db.database import async_session_maker
    from app.schemas.track import PipelineRunResponse

    async with async_session_maker() as session:
        q = (
            select(PipelineRun)
            .where(PipelineRun.run_type == "backtest")
            .order_by(desc(PipelineRun.created_at))
            .limit(limit)
        )
        result = await session.execute(q)
        records = result.scalars().all()

    return [PipelineRunResponse.model_validate(r) for r in records]


@router.get("/backtest/history/{run_id}", summary="获取单次回测详情")
async def get_backtest_detail(run_id: int):
    """获取单次回测完整详情（含结果数据）"""
    from sqlalchemy import select
    from app.models.track import PipelineRun
    from app.db.database import async_session_maker

    async with async_session_maker() as session:
        result = await session.execute(
            select(PipelineRun).where(PipelineRun.id == run_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            raise HTTPException(status_code=404, detail=f"回测记录 {run_id} 不存在")

    from app.schemas.track import PipelineRunResponse
    base = PipelineRunResponse.model_validate(record)

    # 尝试回读已保存的 equity/trades
    detail = {"run": base.model_dump()}

    detail_path = BACKTEST_DIR / f"run_{run_id}_detail.json"
    if detail_path.exists():
        with open(detail_path) as f:
            detail["detail"] = json.load(f)

    return detail


# ── 学习看板统计 ──


@router.get("/learning/stats", summary="获取学习看板统计")
async def get_learning_stats():
    """累计实验次数、最佳夏普策略、最差回撤策略、学习进度等"""
    from sqlalchemy import select, desc, func
    from app.models.track import PipelineRun, Track
    from app.db.database import async_session_maker

    async with async_session_maker() as session:
        # 实验次数
        count_q = select(func.count(PipelineRun.id)).where(
            PipelineRun.run_type == "backtest"
        )
        total_experiments = (await session.execute(count_q)).scalar() or 0

        # 赛道数
        track_count_q = select(func.count(Track.id)).where(Track.is_active == 1)
        total_tracks = (await session.execute(track_count_q)).scalar() or 0

        # 最近回测记录
        recent_q = (
            select(PipelineRun)
            .where(PipelineRun.run_type == "backtest")
            .order_by(desc(PipelineRun.created_at))
            .limit(100)
        )
        recent = (await session.execute(recent_q)).scalars().all()

    # 从历史记录中提取最佳和最差
    best_sharpe = 0
    best_sharpe_strategy = "无"
    worst_drawdown = 0
    worst_drawdown_strategy = "无"
    strategy_experiments = {}

    for r in recent:
        summary = r.results_summary or {}
        if isinstance(summary, dict):
            for sname, smetrics in summary.items():
                if isinstance(smetrics, dict):
                    strategy_experiments[sname] = strategy_experiments.get(sname, 0) + 1
                    sharpe = smetrics.get("sharpe_ratio", 0)
                    if isinstance(sharpe, (int, float)) and sharpe > best_sharpe:
                        best_sharpe = sharpe
                        best_sharpe_strategy = sname
                    dd = abs(smetrics.get("max_drawdown", 0))
                    if isinstance(dd, (int, float)) and dd > worst_drawdown:
                        worst_drawdown = dd
                        worst_drawdown_strategy = sname

    return {
        "total_experiments": total_experiments,
        "total_tracks": total_tracks,
        "best_sharpe": round(best_sharpe, 3),
        "best_sharpe_strategy": best_sharpe_strategy,
        "worst_drawdown": round(worst_drawdown, 2),
        "worst_drawdown_strategy": worst_drawdown_strategy,
        "strategy_experiments": strategy_experiments,
    }


# ── 保存回测结果（供 /backtest/run 等调用） ──


def save_backtest_detail(run_id: int, equity_curve: list[dict], trades: list[dict], metrics: dict):
    """将单次回测的完整结果持久化到磁盘"""
    BACKTEST_DIR.mkdir(parents=True, exist_ok=True)
    detail = {
        "equity_curve": equity_curve,
        "trades": trades,
        "metrics": metrics,
        "trade_count": len(trades),
        "equity_points": len(equity_curve),
    }
    detail_path = BACKTEST_DIR / f"run_{run_id}_detail.json"
    with open(detail_path, "w") as f:
        json.dump(detail, f, indent=2, ensure_ascii=False, default=str)
    return detail_path
