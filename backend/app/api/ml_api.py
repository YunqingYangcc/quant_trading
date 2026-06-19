"""AI 机器学习 API（Phase E/F 实现）"""
import logging
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException

from app.ml.model_trainer import LightGBMTrainer
from app.ml.scorer import TrackScorer

logger = logging.getLogger(__name__)
router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = BASE_DIR / "ml" / "models"
PREPROCESSED_DIR = BASE_DIR / "ml" / "preprocessed"


@router.post("/ml/train/{track_name}", summary="训练赛道模型")
async def train_track_model(track_name: str):
    """触发指定赛道的 LightGBM 训练"""
    from scripts.train_models import load_data, get_track_stock_map, train_track_model as train_one

    try:
        track_map = await get_track_stock_map()
        if track_name not in track_map:
            raise HTTPException(status_code=404, detail=f"赛道 '{track_name}' 不存在")

        train_df, val_df, test_df, feature_cols = load_data()
        with open(PREPROCESSED_DIR / "feature_cols.json") as f:
            import json
            feature_cols = json.load(f)

        result = train_one(
            track_name, track_map[track_name],
            train_df, val_df, test_df, feature_cols
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"训练失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ml/train/all", summary="训练所有赛道模型")
async def train_all_models():
    """训练全部 4 个赛道模型"""
    from scripts.train_models import main as run_training
    try:
        await run_training()
        return {"message": "All models trained"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ml/score/{track_name}", summary="获取赛道打分")
async def get_track_score(track_name: str):
    """获取赛道内个股 AI 强弱分（Phase F 实现）"""
    from app.db.database import async_session_maker
    from sqlalchemy import select
    from app.models.track import Track, TrackStock, track_stock, FeatureWhiteList

    # 加载白名单特征列
    try:
        async with async_session_maker() as session:
            track_result = await session.execute(
                select(Track).where(Track.name == track_name, Track.is_active == 1)
            )
            track = track_result.scalar_one_or_none()
            if not track:
                raise HTTPException(status_code=404, detail=f"赛道 '{track_name}' 不存在")

            # 获取赛道内股票
            stocks_result = await session.execute(
                select(track_stock.c.stock_code).where(track_stock.c.track_id == track.id)
            )
            stock_codes = [r[0] for r in stocks_result.all()]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 加载最新特征
    try:
        with open(PREPROCESSED_DIR / "feature_cols.json") as f:
            import json
            feature_cols = json.load(f)

        # 从 parquet 加载最新一条特征
        test_df = pd.read_parquet(PREPROCESSED_DIR / "test.parquet")
        test_df = test_df[test_df["stock_code"].isin(stock_codes)]

        # 每只股票取最新行
        feature_dict = {}
        for code in stock_codes:
            stock_data = test_df[test_df["stock_code"] == code]
            if len(stock_data) > 0:
                latest = stock_data.iloc[-1:][feature_cols]
                feature_dict[code] = latest
    except Exception as e:
        logger.error(f"特征加载失败: {e}")
        raise HTTPException(status_code=500, detail=f"特征加载失败: {e}")

    # 打分（直接加载 joblib 模型，绕过 LightGBMTrainer 的 pickle 格式）
    model_path = MODELS_DIR / f"{track_name}.pkl"
    if not model_path.exists():
        return {
            "track_name": track_name,
            "model_id": "",
            "scores": [],
            "track_sentiment": 0.0,
            "message": "模型未训练，请先运行 python3 scripts/train_models.py",
        }

    import joblib
    model = joblib.load(model_path)

    scores = []
    for code in stock_codes:
        if code not in feature_dict:
            scores.append({"stock_code": code, "score": 0.0, "rank": 0})
            continue
        try:
            pred = model.predict(feature_dict[code])[0]
            scores.append({"stock_code": code, "score": round(float(pred), 6), "rank": 0})
        except Exception as e:
            logger.warning(f"{code} 打分失败: {e}")
            scores.append({"stock_code": code, "score": 0.0, "rank": 0})

    # 排序排名
    scores.sort(key=lambda x: x["score"], reverse=True)
    for i, s in enumerate(scores):
        s["rank"] = i + 1

    # 赛道景气分
    if scores:
        import numpy as np
        median_score = np.median([s["score"] for s in scores])
        track_sentiment = round(100.0 / (1.0 + np.exp(-median_score * 5)), 2)
    else:
        track_sentiment = 0.0

    return {
        "track_name": track_name,
        "model_id": track_name,
        "scores": scores,
        "track_sentiment": track_sentiment,
        "top_stock": scores[0]["stock_code"] if scores else "",
        "top_score": scores[0]["score"] if scores else 0.0,
    }


@router.get("/ml/scores", summary="获取所有赛道打分")
async def get_all_track_scores():
    """获取所有赛道打分"""
    from app.db.database import async_session_maker
    from sqlalchemy import select
    from app.models.track import Track

    async with async_session_maker() as session:
        result = await session.execute(select(Track).where(Track.is_active == 1))
        tracks = result.scalars().all()

    all_scores = {}
    for track in tracks:
        try:
            scores = await get_track_score(track.name)
            all_scores[track.name] = {
                "display_name": track.display_name,
                "track_sentiment": scores.get("track_sentiment", 0),
                "top_stock": scores.get("top_stock", ""),
                "scores": scores.get("scores", []),
            }
        except Exception as e:
            all_scores[track.name] = {"error": str(e)}

    return all_scores


@router.get("/ml/models/{track_name}", summary="列出赛道模型")
async def list_models(track_name: str):
    """列出赛道已训练模型"""
    trainer = LightGBMTrainer(track_name)
    models = trainer.list_models()
    return {"track_name": track_name, "models": models}


BACKTEST_DIR = BASE_DIR / "ml" / "backtest"


@router.get("/backtest/report", summary="获取回测报告")
async def get_backtest_report():
    """获取最新回测结果"""
    report_path = BACKTEST_DIR / "backtest_report.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="回测报告未生成, 请先运行 python3 scripts/run_backtest.py")
    import json
    with open(report_path) as f:
        report = json.load(f)
    return report


@router.get("/backtest/equity", summary="获取回测净值曲线")
async def get_backtest_equity():
    """获取回测净值曲线数据"""
    csv_path = BACKTEST_DIR / "equity_curve.csv"
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="回测数据未生成")
    import csv
    data = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return {"data": data}

