"""
Dashboard 聚合 API - 每日交易建议

GET /api/v1/dashboard/suggestions

第一性原理：
  所有数据（趋势/策略排名/信号）已经存在，只是分散在各处。
  本接口将它们聚合为一行一赛道的交易决策摘要。
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PREPROCESSED_DIR = BASE_DIR / "ml" / "preprocessed"


async def _get_active_tracks():
    """获取所有活跃赛道"""
    from sqlalchemy import select
    from app.db.database import async_session_maker
    from app.models.track import Track, track_stock

    async with async_session_maker() as session:
        result = await session.execute(
            select(Track).where(Track.is_active == 1).order_by(Track.sort_order)
        )
        tracks = result.scalars().all()

        output = []
        for t in tracks:
            stocks_result = await session.execute(
                select(track_stock.c.stock_code).where(track_stock.c.track_id == t.id)
            )
            stock_codes = [r[0] for r in stocks_result.all()]
            output.append({
                "name": t.name,
                "display_name": t.display_name,
                "stock_codes": stock_codes,
            })
    return output


async def _get_best_strategy_for_track(track_name: str) -> dict | None:
    """从回测历史中获取指定赛道夏普最高的策略"""
    from sqlalchemy import select, desc
    from app.db.database import async_session_maker
    from app.models.track import PipelineRun

    async with async_session_maker() as session:
        q = (
            select(PipelineRun)
            .where(PipelineRun.run_type == "backtest")
            .order_by(desc(PipelineRun.created_at))
            .limit(200)
        )
        result = await session.execute(q)
        records = result.scalars().all()

    best_sharpe = -999
    best_strategy = None

    for r in records:
        summary = r.results_summary or {}
        params = r.params_snapshot or {}
        bt_track = params.get("track_name", "")
        if bt_track and bt_track != track_name:
            continue
        if isinstance(summary, dict):
            for sname, smetrics in summary.items():
                if isinstance(smetrics, dict) and not smetrics.get("error"):
                    sharpe = smetrics.get("sharpe_ratio", 0)
                    if isinstance(sharpe, (int, float)) and sharpe > best_sharpe:
                        best_sharpe = sharpe
                        best_strategy = {
                            "key": sname,
                            "name": smetrics.get("name", sname),
                            "sharpe": round(sharpe, 3),
                        }
    return best_strategy


def _detect_trend(prices: pd.DataFrame, stock_codes: list[str]) -> dict:
    """检测赛道趋势：基于成分股 MA5/MA20/MA60 排列方向"""
    valid_cols = [c for c in stock_codes if c in prices.columns]
    if not valid_cols:
        return {"direction": "neutral", "label": "数据不足", "score": 50}

    recent = prices[valid_cols].dropna(how="all").tail(60)
    if len(recent) < 20:
        return {"direction": "neutral", "label": "数据不足", "score": 50}

    scores = []
    for col in valid_cols:
        series = recent[col].dropna()
        if len(series) < 60:
            continue
        ma5 = series.rolling(5).mean().iloc[-1]
        ma20 = series.rolling(20).mean().iloc[-1]
        ma60 = series.rolling(60).mean().iloc[-1]
        last_close = series.iloc[-1]

        if last_close > ma5 > ma20 > ma60:
            scores.append(1.0)
        elif last_close > ma20 > ma60:
            scores.append(0.6)
        elif last_close < ma5 < ma20 < ma60:
            scores.append(-1.0)
        elif last_close < ma20 < ma60:
            scores.append(-0.6)
        else:
            scores.append(0.0)

    if not scores:
        return {"direction": "neutral", "label": "数据不足", "score": 50}

    avg_score = sum(scores) / len(scores)
    score_pct = int((avg_score + 1) / 2 * 100)

    if avg_score > 0.3:
        return {"direction": "up", "label": "多头排列", "score": score_pct}
    elif avg_score < -0.3:
        return {"direction": "down", "label": "空头排列", "score": score_pct}
    else:
        return {"direction": "neutral", "label": "震荡整理", "score": score_pct}


def _load_stock_names() -> dict[str, str]:
    """从 universe.csv 加载股票代码→名称映射"""
    universe_path = BASE_DIR.parent / "datas" / "universe.csv"
    if not universe_path.exists():
        return {}
    df = pd.read_csv(universe_path, dtype=str)
    name_map = {}
    for _, row in df.iterrows():
        name_map[row["code"].strip()] = row["name"].strip()
    return name_map


def _generate_top_picks(prices: pd.DataFrame, stock_codes: list[str]) -> list[dict]:
    """用最近 20 日动量选出 Top-3 股票"""
    valid_cols = [c for c in stock_codes if c in prices.columns]
    if not valid_cols:
        return []

    track_prices = prices[valid_cols].dropna(how="all")
    if len(track_prices) < 20:
        return []

    name_map = _load_stock_names()
    recent_ret = track_prices.pct_change(20).iloc[-1].dropna()
    top = recent_ret.nlargest(3)

    picks = []
    for code in top.index:
        picks.append({"code": code, "name": name_map.get(code, "")})
    return picks


def _load_prices() -> pd.DataFrame | None:
    """加载回测价格数据"""
    prices_path = PREPROCESSED_DIR / "backtest_prices.parquet"
    if prices_path.exists():
        return pd.read_parquet(prices_path)
    return None


@router.get("/dashboard/suggestions", summary="每日交易建议")
async def get_suggestions():
    """返回所有赛道的决策摘要：趋势方向 + 推荐策略 + Top-N 股票"""
    tracks = await _get_active_tracks()
    if not tracks:
        raise HTTPException(status_code=404, detail="没有活跃赛道")

    prices = _load_prices()

    suggestions = []
    for t in tracks:
        if prices is not None:
            trend = _detect_trend(prices, t["stock_codes"])
        else:
            trend = {"direction": "neutral", "label": "无价格数据", "score": 50}

        best = await _get_best_strategy_for_track(t["name"])

        if prices is not None:
            top_picks = _generate_top_picks(prices, t["stock_codes"])
        else:
            top_picks = []

        suggestions.append({
            "track_name": t["name"],
            "display_name": t["display_name"],
            "stock_count": len(t["stock_codes"]),
            "trend": trend["direction"],
            "trend_label": trend["label"],
            "best_strategy": best,
            "top_picks": top_picks,
        })

    from datetime import datetime, timezone
    return {
        "suggestions": suggestions,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
