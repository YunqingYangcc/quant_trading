"""
个股模拟日报 API.

GET /api/v1/daily-report/latest  — 最新个股日报（含推荐+胜率）
GET /api/v1/daily-report/stock/{code} — 单只个股日报详情
数据: 板块龙头 + AI分析 + 预测统计
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from app.db.database import async_session_maker
from sqlalchemy import select, desc, func

router = APIRouter()
logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "configs"


def _load_leaders() -> list[dict]:
    p = CONFIG_DIR / "sector_leaders.json"
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return []


def _get_prices(codes: list[str]) -> dict:
    import sqlite3
    DB = Path(__file__).resolve().parent.parent.parent / "track_quant.db"
    result = {}
    try:
        conn = sqlite3.connect(str(DB))
        for code in codes:
            rows = conn.execute(
                "SELECT close_px, trade_date FROM track_data_cache WHERE stock_code=? ORDER BY trade_date DESC LIMIT 2",
                (code,)
            ).fetchall()
            if len(rows) >= 2:
                t, y = rows[0][0], rows[1][0]
                chg = round((t - y) / y * 100, 2) if t and y else 0
                result[code] = {"price": t, "change_pct": chg}
            elif rows:
                result[code] = {"price": rows[0][0], "change_pct": 0}
            else:
                result[code] = {"price": 0, "change_pct": 0}
        conn.close()
    except Exception:
        pass
    return result


async def _get_prediction_stats(stock_code: str) -> dict:
    from app.models.track import Prediction
    async with async_session_maker() as session:
        total = await session.execute(
            select(func.count()).select_from(Prediction).where(
                Prediction.stock_code == stock_code,
                Prediction.review_result.isnot(None),
            )
        )
        total_n = total.scalar() or 0
        good = await session.execute(
            select(func.count()).select_from(Prediction).where(
                Prediction.stock_code == stock_code,
                Prediction.review_result == "GOOD",
            )
        )
        good_n = good.scalar() or 0
        win_rate = round(good_n / max(total_n, 1) * 100, 1)
        return {"total": total_n, "good": good_n, "win_rate": win_rate}


@router.get("/daily-report/latest", summary="个股模拟日报（最新）")
async def get_latest():
    leaders = _load_leaders()
    codes = [l["code"] for l in leaders]
    prices = _get_prices(codes)

    rows = []
    for l in leaders:
        p = prices.get(l["code"], {})
        stats = await _get_prediction_stats(l["code"])
        rows.append({
            "name": l["name"],
            "code": l["code"],
            "track": l["track"],
            "segment": l["segment"],
            "position": l["position"],
            "price": p.get("price", 0),
            "change_pct": p.get("change_pct", 0),
            "pred_total": stats["total"],
            "pred_good": stats["good"],
            "pred_win_rate": stats["win_rate"],
        })

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total": len(rows),
        "stocks": rows,
    }


@router.get("/daily-report/stock/{code}", summary="单只个股日报")
async def get_stock_report(code: str):
    leaders = _load_leaders()
    stock = next((l for l in leaders if l["code"] == code), None)
    if not stock:
        raise HTTPException(status_code=404, detail=f"未找到股票: {code}")

    prices = _get_prices([code])
    stats = await _get_prediction_stats(code)

    # 查询该股票的预测历史
    from app.models.track import Prediction
    async with async_session_maker() as session:
        stmt = (
            select(Prediction)
            .where(Prediction.stock_code == code)
            .order_by(desc(Prediction.created_at))
            .limit(20)
        )
        result = await session.execute(stmt)
        preds = result.scalars().all()
        history = [{
            "date": p.created_at.isoformat()[:10] if p.created_at else "",
            "rating": p.overall_rating,
            "action": p.action,
            "opportunity_score": p.opportunity_score,
            "risk_score": p.risk_score,
            "result": p.review_result,
            "actual_return": p.actual_return,
        } for p in preds]

    return {
        "stock": {**stock, "price": prices.get(code, {}).get("price", 0), "change_pct": prices.get(code, {}).get("change_pct", 0)},
        "stats": stats,
        "prediction_history": history,
    }
