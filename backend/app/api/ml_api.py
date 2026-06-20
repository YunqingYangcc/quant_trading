"""AI 机器学习 API（Phase E/F 实现）"""
import logging
from pathlib import Path

import asyncio
import json
import csv
from datetime import datetime

import numpy as np
import joblib
import pandas as pd
from fastapi import APIRouter, Body, HTTPException

from app.ml.model_trainer import LightGBMTrainer
from app.ml.scorer import TrackScorer
from app.schemas.track import BacktestRunParams

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


@router.get("/ml/models/all", summary="获取所有模型元信息")
async def list_all_models():
    """获取4个赛道模型的元信息"""
    models = []
    for meta_path in MODELS_DIR.glob("*_meta.json"):
        with open(meta_path) as f:
            meta = json.load(f)
            # 获取模型文件修改时间
            pkl_path = MODELS_DIR / f"{meta['track_name']}.pkl"
            if pkl_path.exists():
                import datetime
                mtime = datetime.datetime.fromtimestamp(pkl_path.stat().st_mtime)
                meta["trained_at"] = mtime.strftime("%Y-%m-%d %H:%M:%S")
            else:
                meta["trained_at"] = None
            models.append(meta)
    return models


@router.get("/ml/factors/data", summary="获取因子值数据（用于IC分析）")
async def get_factor_data(
    track_name: str | None = None,
    stock_code: str | None = None,
    max_rows: int = 5000,
):
    """从预处理数据集获取因子值，用于前端 IC 计算和相关性分析"""
    try:
        df = pd.read_parquet(PREPROCESSED_DIR / "train.parquet")
    except Exception:
        df = pd.read_parquet(PREPROCESSED_DIR / "val.parquet")

    df = df.sort_values(["stock_code", "date"]).reset_index(drop=True)

    if track_name:
        from app.db.database import async_session_maker
        from sqlalchemy import select
        from app.models.track import Track, track_stock

        async with async_session_maker() as session:
            track_result = await session.execute(
                select(Track).where(Track.name == track_name, Track.is_active == 1)
            )
            track = track_result.scalar_one_or_none()
            if track:
                stocks_result = await session.execute(
                    select(track_stock.c.stock_code).where(track_stock.c.track_id == track.id)
                )
                stock_codes = [r[0] for r in stocks_result.all()]
                if stock_codes:
                    df = df[df["stock_code"].isin(stock_codes)]

    if stock_code:
        df = df[df["stock_code"] == stock_code]

    # 加载特征列
    with open(PREPROCESSED_DIR / "feature_cols.json") as f:
        feature_cols = json.load(f)

    # 选取需要的列
    cols = ["stock_code", "date", "target"] + feature_cols
    cols = [c for c in cols if c in df.columns]
    df = df[cols]

    if len(df) > max_rows:
        df = df.head(max_rows)

    return {
        "columns": cols,
        "rows": df.values.tolist(),
        "feature_cols": feature_cols,
    }


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

            # 获取赛道内股票（含名称）
            stocks_result = await session.execute(
                select(track_stock.c.stock_code, TrackStock.name).
                where(track_stock.c.track_id == track.id).
                join(TrackStock, track_stock.c.stock_code == TrackStock.code)
            )
            stock_rows = stocks_result.all()
            stock_codes = [r.stock_code for r in stock_rows]
            stock_names = {r.stock_code: r.name for r in stock_rows}
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
        row = {"stock_code": code, "stock_name": stock_names.get(code, ""), "score": 0.0, "rank": 0}
        if code not in feature_dict:
            scores.append(row)
            continue
        try:
            pred = model.predict(feature_dict[code])[0]
            row["score"] = round(float(pred), 6)
            scores.append(row)
        except Exception as e:
            logger.warning(f"{code} 打分失败: {e}")
            row["stock_name"] = stock_names.get(code, "")
            scores.append(row)

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
    with open(report_path) as f:
        report = json.load(f)
    return report


@router.get("/backtest/equity", summary="获取回测净值曲线")
async def get_backtest_equity():
    """获取回测净值曲线数据"""
    csv_path = BACKTEST_DIR / "equity_curve.csv"
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="回测数据未生成")
    data = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return {"data": data}


@router.post("/backtest/run", summary="手动运行回测")
async def run_backtest(params: BacktestRunParams = Body(...)):
    """根据传入参数运行回测，返回绩效报告"""
    import sys as _sys
    import importlib.util as _util

    # 加载回测脚本模块
    script_path = BASE_DIR / "scripts" / "run_backtest.py"
    spec = _util.spec_from_file_location("run_backtest", script_path)
    if not spec or not spec.loader:
        raise HTTPException(status_code=500, detail="回测脚本加载失败")
    bt = _util.module_from_spec(spec)
    spec.loader.exec_module(bt)

    # 注入可配置参数（覆盖默认锁定参数）
    bt.BACKTEST_PARAMS.update({
        "initial_capital": params.initial_capital,
        "top_n": params.top_n,
        "rebalance_freq": params.rebalance_freq,
        "max_single_stock": params.max_single_stock,
        "max_single_track": params.max_single_track,
    })

    # 在后台线程中运行回测
    loop = asyncio.get_event_loop()
    try:
        scores, prices = await loop.run_in_executor(None, bt.load_historical_scores)
        signals = await loop.run_in_executor(None, bt.generate_signals, scores)
        trades, equity_curve = await loop.run_in_executor(None, bt.simulate_trades, signals, prices)
        metrics = await loop.run_in_executor(None, bt.calculate_metrics, equity_curve)
    except Exception as e:
        logger.error(f"回测执行失败: {e}")
        raise HTTPException(status_code=500, detail=f"回测执行失败: {e}")

    # 获取赛道与股票元数据
    track_info = []
    try:
        from app.db.database import async_session_maker
        from sqlalchemy import select
        from app.models.track import Track
        async with async_session_maker() as session:
            result = await session.execute(select(Track).where(Track.is_active == 1))
            tracks = result.scalars().all()
            for t in tracks:
                track_info.append({
                    "name": t.name,
                    "display_name": t.display_name,
                    "stock_count": t.stock_count,
                })
    except Exception:
        pass

    # 日期范围
    date_start = str(equity_curve[0]["date"])[:10] if equity_curve else ""
    date_end = str(equity_curve[-1]["date"])[:10] if equity_curve else ""

    # 构建完整报告
    report = {
        "params": {
            "initial_capital": params.initial_capital,
            "top_n": params.top_n,
            "rebalance_freq": "周频" if params.rebalance_freq == "W" else "月频",
            "max_single_stock": f"{params.max_single_stock * 100:.0f}%",
            "max_single_track": f"{params.max_single_track * 100:.0f}%",
        },
        "locked_params": {
            "slippage": "0.1%",
            "commission": "万三",
            "limit_rules": "涨跌停限制",
        },
        "metadata": {
            "tracks": track_info,
            "trade_count": len(equity_curve),
            "date_start": date_start,
            "date_end": date_end,
            "run_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
        "metrics": metrics,
    }

    # 保存结果（含上下文）
    report_path = BACKTEST_DIR / "backtest_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    pd.DataFrame(equity_curve).to_csv(BACKTEST_DIR / "equity_curve.csv", index=False)

    return report


@router.get("/portfolio/summary", summary="获取投资组合摘要")
async def get_portfolio_summary():
    """获取组合配置建议（基于当前赛道景气度）"""
    from app.db.database import async_session_maker
    from sqlalchemy import select
    from app.models.track import Track

    async with async_session_maker() as session:
        result = await session.execute(select(Track).where(Track.is_active == 1))
        tracks = result.scalars().all()

    scores_data = await get_all_track_scores()

    track_config = []
    total_sentiment = 0
    for track in tracks:
        info = scores_data.get(track.name, {})
        sentiment = info.get("track_sentiment", 0) or 0
        total_sentiment += sentiment
        stock_scores = info.get("scores", [])
        track_config.append({
            "name": track.name,
            "display_name": track.display_name,
            "sentiment": sentiment,
            "stock_count": len(stock_scores),
            "top_stock": info.get("top_stock", ""),
            "stocks": stock_scores,
        })

    # 权重归一化
    for t in track_config:
        t["weight"] = round(t["sentiment"] / total_sentiment * 100, 1) if total_sentiment > 0 else 25.0

    # 风险指标
    import math
    report_path = BACKTEST_DIR / "backtest_report.json"
    risk_metrics = {}
    if report_path.exists():
        with open(report_path) as f:
            bt = json.load(f)
        m = bt.get("metrics", {})
        risk_metrics = {
            "total_return": m.get("total_return", 0),
            "annual_volatility": m.get("annual_volatility", 0),
            "max_drawdown": m.get("max_drawdown", 0),
            "sharpe_ratio": m.get("sharpe_ratio", 0),
            "win_rate": m.get("win_rate", 0),
            "total_trades": m.get("total_trades", 0),
        }

    return {
        "tracks": track_config,
        "risk_metrics": risk_metrics,
        "total_sentiment": round(total_sentiment, 2),
    }

