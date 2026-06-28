"""
个股 AI 量化分析 API (RichOne 风格).

GET /api/v1/ml/analysis/{stock_code} — 综合评级 + 7维度 + 价格建议 + 关键指标
POST /api/v1/ml/predictions/save       — 保存预测
GET  /api/v1/ml/predictions/list       — 预测列表
POST /api/v1/ml/predictions/review     — 复盘预测
GET  /api/v1/ml/predictions/stats      — 胜率统计

数据来源: 预处理 parquet + TrackDataCache 实时价格.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Body

from app.db.database import async_session_maker
from sqlalchemy import select, desc, func

router = APIRouter()
logger = logging.getLogger(__name__)

PREPROCESSED_DIR = Path(__file__).resolve().parent.parent.parent / "ml" / "preprocessed"
DB_PATH = Path(__file__).resolve().parent.parent.parent / "track_quant.db"


def _safe_get(row, col, default=0) -> float:
    try:
        v = row.get(col)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return default
        return float(v)
    except (ValueError, TypeError):
        return default


def _get_realtime_price(stock_code: str) -> dict:
    """从 DB 获取最新收盘价和 MA 值."""
    try:
        import sqlite3
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT close_px, trade_date FROM track_data_cache WHERE stock_code=? ORDER BY trade_date DESC LIMIT 60",
            (stock_code,)
        )
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            return {}
        prices = [r[0] for r in rows if r[0]]
        if len(prices) < 20:
            return {"close": prices[0] if prices else 0}
        return {
            "close": prices[0],
            "ma5": round(sum(prices[:5]) / 5, 2),
            "ma20": round(sum(prices[:20]) / 20, 2),
            "ma60": round(sum(prices[:60]) / 60, 2) if len(prices) >= 60 else round(sum(prices) / len(prices), 2),
            "high_60": max(prices[:60]) if len(prices) >= 60 else max(prices),
            "low_60": min(prices[:60]) if len(prices) >= 60 else min(prices),
        }
    except Exception:
        return {}


# ========== 路由 ==========


@router.get("/ml/analysis/{stock_code}", summary="个股 AI 量化分析（RichOne风格）")
async def get_stock_analysis(stock_code: str):
    """返回 综合评级 + 7维度 + 价格建议 + 关键指标."""
    try:
        test_df = pd.read_parquet(PREPROCESSED_DIR / "test.parquet")
    except Exception:
        try:
            test_df = pd.read_parquet(PREPROCESSED_DIR / "val.parquet")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"数据加载失败: {e}")

    stock_data = test_df[test_df["stock_code"] == stock_code]
    if len(stock_data) == 0:
        return {
            "stock_code": stock_code,
            "message": "该股票暂无特征数据",
            "overall_rating": "N/A", "action": "N/A",
            "opportunity_score": 0, "risk_score": 0,
            "dimensions": {}, "indicators": {}, "price_advice": {},
        }

    latest = stock_data.iloc[-1]
    price_info = _get_realtime_price(stock_code)
    close = price_info.get("close", 0)
    ma20 = price_info.get("ma20", 0)

    # 7 维度评分
    dims = {
        "trend": _trend(latest),
        "momentum": _momentum(latest),
        "volume": _volume(latest),
        "risk": _risk(latest),
        "position": _position(latest, price_info),
        "liquidity": _liquidity(latest),
        "model_learning": _model_learning(latest, stock_code),
    }

    # 综合评分
    scores = [d["score"] for d in dims.values()]
    overall = round(float(np.mean(scores)), 1)
    opp_score = round(float(np.mean([dims["trend"]["score"], dims["momentum"]["score"], dims["position"]["score"]])), 1)
    risk_score = round(float(np.mean([dims["risk"]["score"], 100 - dims["volume"]["score"], 100 - dims["liquidity"]["score"]])), 1)

    # 评级
    if overall >= 75:
        rating, action = "A", "BUY"
    elif overall >= 60:
        rating, action = "B", "HOLD"
    elif overall >= 40:
        rating, action = "C", "HOLD"
    else:
        rating, action = "D", "SELL"

    # 买卖建议
    if close > 0 and ma20 > 0:
        buy_low = round(ma20 * 0.97, 2)
        buy_high = round(ma20 * 1.03, 2)
        target = round(close * 1.15, 2)
        stop = round(close * 0.92, 2)
    else:
        buy_low, buy_high, target, stop = 0, 0, 0, 0

    # 关键指标
    indicators = {
        "ma5": price_info.get("ma5", 0),
        "ma20": ma20,
        "rsi14": round(_safe_get(latest, "rsi_14"), 2),
        "momentum_20d": round(_safe_get(latest, "roc_20") * 100, 2),
    }

    return {
        "stock_code": stock_code,
        "overall_rating": rating,
        "action": action,
        "opportunity_score": round(opp_score, 1),
        "risk_score": round(risk_score, 1),
        "overall_score": overall,
        "price_advice": {
            "suggested_buy": f"{buy_low} - {buy_high}",
            "target_price": target,
            "stop_loss": stop,
        },
        "indicators": indicators,
        "dimensions": dims,
        "generated_at": datetime.now().strftime("%H:%M:%S"),
    }


# ========== 7 维度计算 ==========

def _trend(row) -> dict:
    s = 50
    sma20 = _safe_get(row, "sma_dev_20")
    ema12 = _safe_get(row, "ema_dev_12")
    adx = _safe_get(row, "adx")
    if sma20 > 0: s += 15
    if ema12 > 0: s += 10
    if adx > 25: s += 12
    elif adx > 15: s += 5
    s = min(100, max(0, s))
    desc = "偏多" if sma20 > 0 and adx > 15 else "偏空" if sma20 < -0.02 else "震荡"
    return {"score": s, "label": "趋势结构", "description": desc,
            "detail": "价格、MA5、MA20、MA60 的排列关系"}


def _momentum(row) -> dict:
    s = 50
    rsi = _safe_get(row, "rsi_14")
    roc20 = _safe_get(row, "roc_20")
    if 40 < rsi < 70: s += 10
    elif rsi > 75: s -= 5
    if roc20 > 0: s += 15
    else: s -= 8
    if rsi > 60 and roc20 > 0: s += 5
    s = min(100, max(0, s))
    desc = "动能较好" if s > 55 else "动能偏弱" if s < 45 else "动能一般"
    return {"score": s, "label": "动量强弱", "description": desc,
            "detail": "近5日、近20日收益和 RSI14 的综合判断"}


def _volume(row) -> dict:
    v5 = _safe_get(row, "vol_ratio_5")
    mfi = _safe_get(row, "mfi")
    s = 50
    if v5 > 1.2: s += 15
    elif v5 < 0.8: s -= 10
    if mfi > 55: s += 10
    elif mfi < 30: s -= 10
    s = min(100, max(0, s))
    desc = "放量活跃" if v5 > 1.2 else "量能偏低" if v5 < 0.8 else "量能一般"
    return {"score": s, "label": "量能确认", "description": desc,
            "detail": "最新成交量相对20日均量和换手率"}


def _risk(row) -> dict:
    s = 50
    sharpe = _safe_get(row, "sharpe_20")
    bb = _safe_get(row, "bb_width")
    if sharpe > 0.5: s += 18
    elif sharpe > 0: s += 8
    else: s -= 10
    if bb > 0.15: s -= 8
    s = min(100, max(0, s))
    desc = "风险可控" if s > 55 else "风险偏高" if s < 40 else "风险适中"
    return {"score": s, "label": "风险约束", "description": desc,
            "detail": "波动率、短线涨跌幅和 RSI 过热程度"}


def _position(row, price_info: dict) -> dict:
    s = 50
    pp = _safe_get(row, "price_pos_60")
    rp = _safe_get(row, "ret_pctile_20")
    if 30 < pp < 70: s += 10
    elif pp > 80: s -= 12
    elif pp < 20: s += 8
    if rp > 0.6: s += 8
    elif rp < 0.3: s -= 5
    s = min(100, max(0, s))
    desc = "位置偏强" if pp > 60 else "位置偏低" if pp < 30 else "中部"
    return {"score": s, "label": "价格位置", "description": desc,
            "detail": "当前价在近60日高低区间中的位置"}


def _liquidity(row) -> dict:
    s = 50
    v20 = _safe_get(row, "vol_ratio_20")
    cmf = _safe_get(row, "cmf")
    if v20 > 1.0: s += 15
    elif v20 < 0.6: s -= 10
    if cmf > 0.05: s += 10
    s = min(100, max(0, s))
    desc = "流动性好" if s > 55 else "流动性一般" if s > 40 else "流动性偏低"
    return {"score": s, "label": "流动性", "description": desc,
            "detail": "成交额和换手率决定交易滑点风险"}


def _model_learning(row, stock_code: str) -> dict:
    """基于历史预测复盘给额外修正."""
    try:
        import sqlite3
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT review_result FROM predictions WHERE stock_code=? AND review_result IS NOT NULL ORDER BY created_at DESC LIMIT 10",
            (stock_code,)
        )
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            return {"score": 50, "label": "模型学习", "description": "无历史", "detail": "暂无复盘记录"}
        good = sum(1 for r in rows if r[0] == "GOOD")
        bad = sum(1 for r in rows if r[0] == "BAD")
        if good > bad * 2:
            return {"score": 65, "label": "模型学习", "description": "加分 (历史准确率高)", "detail": f"近10次: {good}对 {bad}错"}
        elif bad > good:
            return {"score": 35, "label": "模型学习", "description": "减分 (历史准确率低)", "detail": f"近10次: {good}对 {bad}错"}
        return {"score": 50, "label": "模型学习", "description": "中性", "detail": f"近10次: {good}对 {bad}错"}
    except Exception:
        return {"score": 50, "label": "模型学习", "description": "无数据", "detail": "暂无复盘记录"}


# ========== 预测追踪 API ==========


@router.post("/ml/predictions/save", summary="保存预测记录")
async def save_prediction(payload: dict = Body(...)):
    """保存单次分析结果作为预测记录."""
    from app.models.track import Prediction

    async with async_session_maker() as session:
        pred = Prediction(
            stock_code=payload.get("stock_code", ""),
            stock_name=payload.get("stock_name", ""),
            overall_rating=payload.get("overall_rating", ""),
            action=payload.get("action", ""),
            opportunity_score=payload.get("opportunity_score", 0),
            risk_score=payload.get("risk_score", 0),
            suggested_buy=payload.get("suggested_buy", ""),
            target_price=payload.get("target_price", 0),
            stop_loss=payload.get("stop_loss", 0),
            analysis_snapshot=payload,
            status="pending",
        )
        session.add(pred)
        await session.commit()
        return {"id": pred.id, "message": "预测已保存"}


@router.get("/ml/predictions/list", summary="预测列表")
async def list_predictions(limit: int = Query(20), stock_code: str = Query("")):
    """查询预测历史."""
    from app.models.track import Prediction

    async with async_session_maker() as session:
        stmt = select(Prediction).order_by(desc(Prediction.created_at))
        if stock_code:
            stmt = stmt.where(Prediction.stock_code == stock_code)
        if limit:
            stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        preds = result.scalars().all()

    return [{
        "id": p.id,
        "stock_code": p.stock_code,
        "stock_name": p.stock_name,
        "overall_rating": p.overall_rating,
        "action": p.action,
        "opportunity_score": p.opportunity_score,
        "risk_score": p.risk_score,
        "suggested_buy": p.suggested_buy,
        "target_price": p.target_price,
        "stop_loss": p.stop_loss,
        "status": p.status,
        "review_result": p.review_result,
        "actual_return": p.actual_return,
        "analysis_snapshot": p.analysis_snapshot,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    } for p in preds]


@router.post("/ml/predictions/review", summary="复盘预测")
async def review_predictions():
    """对 pending 状态的预测进行复盘."""
    from app.models.track import Prediction

    try:
        test_df = pd.read_parquet(PREPROCESSED_DIR / "test.parquet")
    except Exception:
        try:
            test_df = pd.read_parquet(PREPROCESSED_DIR / "val.parquet")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"数据加载失败: {e}")

    async with async_session_maker() as session:
        stmt = select(Prediction).where(Prediction.status == "pending").limit(100)
        result = await session.execute(stmt)
        pending = result.scalars().all()

        reviewed = 0
        for p in pending:
            stock_data = test_df[test_df["stock_code"] == p.stock_code]
            if len(stock_data) < 2:
                continue
            try:
                curr = stock_data.iloc[-1]
                ret = float(curr.get("target", 0)) if "target" in stock_data.columns else 0
                if pd.isna(ret):
                    ret = 0
            except Exception:
                ret = 0

            if ret > 0.02:
                p.review_result = "GOOD"
            elif ret < -0.02:
                p.review_result = "BAD"
            else:
                p.review_result = "MISSED"
            p.actual_return = round(ret, 4)
            p.status = "reviewed"
            p.review_date = datetime.now().strftime("%Y-%m-%d")
            reviewed += 1

        await session.commit()

    return {"reviewed": reviewed}


@router.get("/ml/predictions/stats", summary="预测胜率统计")
async def prediction_stats(stock_code: str = Query("")):
    """返回预测胜率统计."""
    from app.models.track import Prediction

    async with async_session_maker() as session:
        stmt = select(Prediction).where(Prediction.review_result.isnot(None))
        if stock_code:
            stmt = stmt.where(Prediction.stock_code == stock_code)
        result = await session.execute(stmt)
        preds = result.scalars().all()

    if not preds:
        return {"total": 0, "good": 0, "bad": 0, "missed": 0, "win_rate": 0}

    good = sum(1 for p in preds if p.review_result == "GOOD")
    bad = sum(1 for p in preds if p.review_result == "BAD")
    missed = sum(1 for p in preds if p.review_result == "MISSED")
    total = good + bad + missed
    win_rate = round(good / max(total, 1) * 100, 1)

    return {"total": total, "good": good, "bad": bad, "missed": missed,
            "win_rate": win_rate, "stock_code": stock_code or "all"}
