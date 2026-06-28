"""
推荐→复盘闭环 API.

POST /api/v1/recommendations/generate — 生成推荐
GET  /api/v1/recommendations/latest   — 最新推荐
POST /api/v1/recommendations/review   — 执行复盘
GET  /api/v1/recommendations/stats    — 复盘统计
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.db.database import async_session_maker
from sqlalchemy import select, desc, func

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/recommendations/generate", summary="生成推荐")
async def generate_recommendations():
    """基于 AI 模型打分生成今日推荐。"""
    from app.models.track import Recommendation
    from app.models.track import Track, track_stock
    import joblib
    import pandas as pd
    import numpy as np
    import json
    from pathlib import Path

    PREPROCESSED_DIR = Path(__file__).resolve().parent.parent.parent / "ml" / "preprocessed"
    MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "ml" / "models"

    # 加载特征和模型
    try:
        with open(PREPROCESSED_DIR / "feature_cols.json") as f:
            feature_cols = json.load(f)
        test_df = pd.read_parquet(PREPROCESSED_DIR / "test.parquet")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据加载失败: {e}")

    async with async_session_maker() as session:
        # 获取活跃赛道
        tracks_result = await session.execute(select(Track).where(Track.is_active == 1))
        tracks = tracks_result.scalars().all()

        recommendations = []
        today = datetime.now().strftime("%Y-%m-%d")

        for track in tracks:
            model_path = MODELS_DIR / f"{track.name}.pkl"
            if not model_path.exists():
                continue

            model = joblib.load(model_path)
            stocks_result = await session.execute(
                select(track_stock.c.stock_code).where(track_stock.c.track_id == track.id)
            )
            stock_codes = [r[0] for r in stocks_result.all()]

            for code in stock_codes:
                stock_data = test_df[test_df["stock_code"] == code]
                if len(stock_data) == 0:
                    continue
                try:
                    latest = stock_data.iloc[-1:][feature_cols]
                    score = float(model.predict_proba(latest)[0][1])
                except Exception:
                    continue

                if score > 0.55:  # 阈值
                    rec = Recommendation(
                        stock_code=code,
                        stock_name="",
                        rec_date=today,
                        buy_price_range="",
                        reasoning=f"AI 模型评分 {score:.2f}, 赛道: {track.display_name}",
                        status="pending",
                    )
                    session.add(rec)
                    recommendations.append({
                        "stock_code": code,
                        "score": round(score, 4),
                        "track": track.display_name,
                    })

        await session.commit()

    return {
        "recommend_date": today,
        "count": len(recommendations),
        "recommendations": recommendations,
    }


@router.get("/recommendations/latest", summary="获取最新推荐")
async def get_latest_recommendations(limit: int = Query(20)):
    """获取最新推荐列表。"""
    from app.models.track import Recommendation

    async with async_session_maker() as session:
        stmt = (
            select(Recommendation)
            .order_by(desc(Recommendation.created_at))
            .limit(limit)
        )
        result = await session.execute(stmt)
        recs = result.scalars().all()

    return [
        {
            "id": r.id,
            "stock_code": r.stock_code,
            "stock_name": r.stock_name,
            "rec_date": r.rec_date,
            "buy_price_range": r.buy_price_range,
            "target_price": r.target_price,
            "stop_loss": r.stop_loss,
            "reasoning": r.reasoning,
            "status": r.status,
            "review_result": r.review_result,
            "actual_performance": r.actual_performance,
            "review_date": r.review_date,
        }
        for r in recs
    ]


@router.post("/recommendations/review", summary="执行复盘")
async def review_recommendations():
    """检查昨天的所有推荐，打 GOOD/BAD/MISSED 标签。"""
    from app.models.track import Recommendation
    from app.db.database import async_session_maker as db_session
    import pandas as pd
    from pathlib import Path
    import numpy as np

    PREPROCESSED_DIR = Path(__file__).resolve().parent.parent.parent / "ml" / "preprocessed"

    try:
        test_df = pd.read_parquet(PREPROCESSED_DIR / "test.parquet")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据加载失败: {e}")

    yesterday = (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    async with db_session() as session:
        stmt = select(Recommendation).where(
            Recommendation.status == "pending",
            Recommendation.rec_date <= yesterday,
        )
        result = await session.execute(stmt)
        pending = result.scalars().all()

        reviewed = 0
        for rec in pending:
            stock_data = test_df[test_df["stock_code"] == rec.stock_code]
            if len(stock_data) < 2:
                continue
            try:
                prev = stock_data.iloc[-2]
                curr = stock_data.iloc[-1]
                if "target" in stock_data.columns:
                    perf = float(curr["target"]) if pd.notna(curr["target"]) else 0
                else:
                    perf = 0

                if perf > 0.02:
                    rec.review_result = "GOOD"
                elif perf < -0.02:
                    rec.review_result = "BAD"
                else:
                    rec.review_result = "MISSED"
                rec.actual_performance = round(perf, 4)
            except Exception:
                rec.review_result = "MISSED"
                rec.actual_performance = 0

            rec.review_date = today
            rec.status = "reviewed"
            reviewed += 1

        await session.commit()

    return {"reviewed": reviewed, "review_date": today}


@router.get("/recommendations/stats", summary="获取复盘统计")
async def get_review_stats():
    """返回复盘统计：GOOD/BAD/MISSED 占比。"""
    from app.models.track import Recommendation

    async with async_session_maker() as session:
        total_stmt = select(func.count()).select_from(Recommendation).where(Recommendation.review_result.isnot(None))
        total = (await session.execute(total_stmt)).scalar() or 1

        stmt = select(
            Recommendation.review_result,
            func.count().label("cnt"),
        ).where(Recommendation.review_result.isnot(None)).group_by(Recommendation.review_result)

        result = await session.execute(stmt)
        rows = result.all()

    stats = {row.review_result: row.cnt for row in rows}
    return {
        "total_reviewed": sum(stats.values()),
        "good": stats.get("GOOD", 0),
        "bad": stats.get("BAD", 0),
        "missed": stats.get("MISSED", 0),
        "good_rate": round(stats.get("GOOD", 0) / max(sum(stats.values()), 1), 4),
    }
