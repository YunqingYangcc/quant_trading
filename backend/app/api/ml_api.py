"""AI 机器学习 API（Phase E/F 实现）"""
import logging
from pathlib import Path

import asyncio
import json
import csv
import uuid
import time
from datetime import datetime

import numpy as np
import joblib
import pandas as pd
from fastapi import APIRouter, Body, HTTPException

from app.schemas.track import BacktestRunParams, PipelineRunResponse, TrainModelParams

logger = logging.getLogger(__name__)
router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ── 流水线异步任务管理 ──
_pipeline_tasks: dict[str, dict] = {}  # task_id → {status, steps, logs, cancel_event}
MODELS_DIR = BASE_DIR / "ml" / "models"
PREPROCESSED_DIR = BASE_DIR / "ml" / "preprocessed"


@router.post("/ml/train/{track_name}", summary="训练赛道模型（可传参+自动打分落库）")
async def train_track_model(track_name: str, params: TrainModelParams = Body(default=None)):
    """触发指定赛道的 LightGBM 训练，训练后自动打分并保存到数据库"""
    import sys as _sys
    import importlib.util as _util

    script_path = BASE_DIR / "scripts" / "train_models.py"
    spec = _util.spec_from_file_location("train_models", script_path)
    if not spec or not spec.loader:
        raise HTTPException(status_code=500, detail="训练脚本加载失败")
    tm = _util.module_from_spec(spec)
    spec.loader.exec_module(tm)

    try:
        track_map = await tm.get_track_stock_map()
        if track_name not in track_map:
            raise HTTPException(status_code=404, detail=f"赛道 '{track_name}' 不存在")

        train_df, val_df, test_df, feature_cols = tm.load_data()

        # 合并用户自定义参数
        user_params = params.model_dump(exclude_none=True) if params else {}

        result = tm.train_track_model(
            track_name, track_map[track_name],
            train_df, val_df, test_df, feature_cols,
            params=user_params if user_params else None,
        )

        if result["status"] == "skipped":
            return result

        # ── 训练成功后自动打分并落库 ──
        from app.db.database import async_session_maker
        from sqlalchemy import select
        from app.models.track import Track, TrackStock, track_stock, ScoreHistory

        async with async_session_maker() as session:
            # 获取股票名称
            track_result = await session.execute(
                select(Track).where(Track.name == track_name, Track.is_active == 1)
            )
            track = track_result.scalar_one_or_none()
            stock_names = {}
            if track:
                stocks_result = await session.execute(
                    select(track_stock.c.stock_code, TrackStock.name).
                    where(track_stock.c.track_id == track.id).
                    join(TrackStock, track_stock.c.stock_code == TrackStock.code)
                )
                stock_names = {r.stock_code: r.name for r in stocks_result.all()}

            # 加载模型 & 最新特征进行打分
            import joblib
            model_path = MODELS_DIR / f"{track_name}.pkl"
            model = joblib.load(model_path)

            test_df = pd.read_parquet(PREPROCESSED_DIR / "test.parquet")
            test_df = test_df[test_df["stock_code"].isin(track_map[track_name])]

            scores = []
            for code in track_map[track_name]:
                stock_data = test_df[test_df["stock_code"] == code]
                row = {"stock_code": code, "stock_name": stock_names.get(code, ""), "score": 0.0, "rank": 0}
                if len(stock_data) > 0:
                    try:
                        latest = stock_data.iloc[-1:][feature_cols]
                        pred = model.predict_proba(latest)[0][1]
                        row["score"] = round(float(pred), 6)
                    except Exception:
                        pass
                scores.append(row)

            scores.sort(key=lambda x: x["score"], reverse=True)
            for i, s in enumerate(scores):
                s["rank"] = i + 1

            # 保存到 score_history 表
            effective_params = {**tm.LGB_PARAMS, **user_params}
            for s in scores:
                sh = ScoreHistory(
                    track_name=track_name,
                    model_id=track_name,
                    stock_code=s["stock_code"],
                    stock_name=s["stock_name"],
                    score=s["score"],
                    rank=s["rank"],
                    train_r2=result.get("train_r2", 0),
                    val_r2=result.get("val_r2", 0),
                    test_r2=result.get("test_r2", 0),
                    params_snapshot=effective_params,
                )
                session.add(sh)
            await session.commit()

        # 赛道景气分
        if scores:
            median_score = np.median([s["score"] for s in scores])
            track_sentiment = round(100.0 / (1.0 + np.exp(-median_score * 5)), 2)
        else:
            track_sentiment = 0.0

        return {
            **result,
            "params_used": effective_params,
            "scores": scores,
            "track_sentiment": track_sentiment,
            "top_stock": scores[0]["stock_code"] if scores else "",
        }
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
            pred = model.predict_proba(feature_dict[code])[0][1]
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


@router.get("/ml/score/history/{track_name}", summary="获取赛道评分历史")
async def get_score_history(track_name: str, limit: int = 5):
    """获取赛道最近 N 次训练的评分历史"""
    from app.db.database import async_session_maker
    from sqlalchemy import select, desc
    from app.models.track import ScoreHistory

    async with async_session_maker() as session:
        result = await session.execute(
            select(ScoreHistory)
            .where(ScoreHistory.track_name == track_name)
            .order_by(desc(ScoreHistory.scored_at))
            .limit(limit * 50)  # 每批次最多 50 只股票
        )
        records = result.scalars().all()

    # 按 scored_at 分组
    from collections import defaultdict
    groups = defaultdict(list)
    for r in records:
        key = r.scored_at.isoformat()
        groups[key].append({
            "id": r.id,
            "stock_code": r.stock_code,
            "stock_name": r.stock_name,
            "score": r.score,
            "rank": r.rank,
            "train_r2": r.train_r2,
            "val_r2": r.val_r2,
            "test_r2": r.test_r2,
            "params_snapshot": r.params_snapshot,
        })

    history = []
    for scored_at, scores in sorted(groups.items(), key=lambda x: x[0], reverse=True)[:limit]:
        history.append({
            "scored_at": scored_at,
            "track_name": track_name,
            "model_id": track_name,
            "params_snapshot": scores[0]["params_snapshot"] if scores else None,
            "train_r2": scores[0]["train_r2"] if scores else 0,
            "val_r2": scores[0]["val_r2"] if scores else 0,
            "test_r2": scores[0]["test_r2"] if scores else 0,
            "scores": sorted(scores, key=lambda x: x["rank"]),
        })

    return history


@router.get("/ml/models/{track_name}", summary="列出赛道模型")
async def list_models(track_name: str):
    """列出赛道已训练模型的元信息（直接读 *_meta.json）"""
    models = []
    meta_path = MODELS_DIR / f"{track_name}_meta.json"
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
        pkl_path = MODELS_DIR / f"{track_name}.pkl"
        if pkl_path.exists():
            import datetime as dt
            mtime = dt.datetime.fromtimestamp(pkl_path.stat().st_mtime)
            meta["trained_at"] = mtime.strftime("%Y-%m-%d %H:%M:%S")
        else:
            meta["trained_at"] = None
        models.append(meta)
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


# ── 策略回测 API ──

@router.get("/backtest/strategies", summary="列出可用策略")
async def list_backtest_strategies():
    """返回所有注册的策略列表（供前端下拉框）"""
    from strategies import list_strategies
    return list_strategies()


@router.post("/backtest/strategy/{strategy_name}", summary="按策略运行回测")
async def run_strategy_backtest(strategy_name: str):
    """指定策略名称运行回测，返回绩效指标"""
    import sys as _sys
    import importlib.util as _util
    import pandas as pd

    script_path = BASE_DIR / "scripts" / "run_backtest.py"
    spec = _util.spec_from_file_location("run_backtest", script_path)
    if not spec or not spec.loader:
        raise HTTPException(status_code=500, detail="回测脚本加载失败")
    bt = _util.module_from_spec(spec)
    spec.loader.exec_module(bt)

    try:
        prices = pd.read_parquet(PREPROCESSED_DIR / "backtest_prices.parquet")
        result = bt.run_strategy_by_name(strategy_name, prices)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"策略回测失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backtest/single/{stock_code}", summary="单只股票回测")
async def run_single_stock_backtest(
    stock_code: str,
    strategy: str = "momentum_20d",
    lookback: int = 20,
    stop_loss: float = 0,
):
    """对单只股票运行趋势跟踪回测，返回交易明细+绩效
    
    参数:
      stock_code: 股票代码
      strategy: 策略名 (momentum_20d/momentum_60d)
      lookback: 动量周期 (天)
      stop_loss: 止损比例 (%, 0=不止损)
    """
    import sqlite3
    import pandas as pd
    import numpy as np

    db_path = BASE_DIR / "track_quant.db"
    conn = sqlite3.connect(str(db_path))
    # 加载单只股票日线
    df = pd.read_sql(
        f"SELECT trade_date, close_px FROM track_data_cache WHERE stock_code='{stock_code}' ORDER BY trade_date",
        conn
    )
    conn.close()
    if df.empty:
        raise HTTPException(status_code=404, detail=f"未找到 {stock_code} 数据")

    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.set_index("trade_date").sort_index()
    close = df["close_px"]

    # 趋势跟踪：动量 > 0 时买入
    mom = close.pct_change(lookback)
    signals = (mom > 0).astype(int)

    # 止损线
    stop_loss_ratio = -abs(stop_loss) / 100 if stop_loss else -999

    # 模拟交易
    params = {"initial_capital": 100000, "commission": 0.0003, "slippage": 0.001}
    cash = params["initial_capital"]
    position = 0
    trades = []
    equity = []

    for i in range(lookback + 1, len(close)):
        date = close.index[i]
        px = close.iloc[i]
        sig = signals.iloc[i-1]  # 用前一天信号

        # 卖出（信号转空 + 止损）
        should_sell = (sig == 0 and position > 0)
        if position > 0 and entry_px:
            current_ret = (px - entry_px) / entry_px
            if current_ret <= stop_loss_ratio:
                should_sell = True  # 止损触发

        if should_sell:
            proceeds = position * px * (1 - params["commission"] - params["slippage"])
            profit = proceeds - position * entry_px if entry_px else 0
            trades.append({"date": str(date.date()), "type": "sell", "price": round(px, 3),
                          "shares": position, "profit": round(profit, 2)})
            cash += proceeds
            position = 0

        # 买入
        if sig == 1 and position == 0:
            shares = int(cash * 0.95 / (px * (1 + params["commission"] + params["slippage"])))
            if shares > 0:
                cost = shares * px * (1 + params["commission"] + params["slippage"])
                cash -= cost
                position = shares
                entry_px = px
                trades.append({"date": str(date.date()), "type": "buy", "price": round(px, 3),
                              "shares": shares})

        nav = cash + position * px
        equity.append({"date": str(date.date()), "total_value": round(nav, 2)})

    # 绩效
    eq_df = pd.DataFrame(equity).set_index("date")
    eq_df["returns"] = eq_df["total_value"].pct_change()
    rets = eq_df["returns"].dropna()
    metrics = {
        "stock_code": stock_code,
        "strategy": strategy,
        "total_return": round((eq_df["total_value"].iloc[-1] / params["initial_capital"] - 1) * 100, 2),
        "sharpe": round(float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0, 3),
        "max_drawdown": round(float((eq_df["total_value"] / eq_df["total_value"].cummax() - 1).min() * 100), 2),
        "win_rate": round(float((rets > 0).mean() * 100), 2),
        "total_trades": len(trades),
    }

    return {
        "metrics": metrics,
        "trades": trades[-20:],  # 最近 20 笔
        "equity": equity[-252:],  # 最近一年净值
    }


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


@router.post("/ml/compute-features", summary="计算特征")
async def api_compute_features():
    """触发特征计算（Phase B）"""
    try:
        from scripts.compute_features import run_compute_features
        result = await run_compute_features()
        return result
    except Exception as e:
        logger.error(f"特征计算失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ml/screen-factors", summary="因子筛选")
async def api_screen_factors():
    """触发 Alphalens 因子筛选（Phase C）"""
    try:
        from scripts.screen_factors import run_screen_factors
        result = await run_screen_factors()
        return result
    except Exception as e:
        logger.error(f"因子筛选失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ml/preprocess", summary="特征预处理")
async def api_preprocess():
    """触发特征预处理（Phase D）"""
    try:
        from scripts.preprocess_features import run_preprocess_features
        result = await run_preprocess_features()
        return result
    except Exception as e:
        logger.error(f"特征预处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ml/run-pipeline", summary="运行全流水线（异步+可取消）")
async def api_run_pipeline(step: str = "all", track_name: str | None = None):
    """按序执行量化流水线，返回 task_id 用于轮询状态。
    - step=all: 全部步骤
    - step=compute: 仅计算特征
    - step=screen: 仅因子筛选
    - step=preprocess: 仅预处理
    - step=train: 仅训练模型
    - step=backtest: 仅回测
    - track_name: 指定赛道（仅 train 步骤按赛道运行，其他步骤全局执行）

    轮询 GET /ml/pipeline-status/{task_id}
    取消 POST /ml/pipeline-cancel/{task_id}
    """
    task_id = uuid.uuid4().hex[:12]
    cancel_event = asyncio.Event()

    _pipeline_tasks[task_id] = {
        "status": "running",
        "step": "",
        "steps": {},
        "logs": [],
        "cancel_event": cancel_event,
        "started_at": datetime.now().isoformat(),
    }

    # 在后台运行
    asyncio.create_task(_run_pipeline_background(task_id, step, track_name, cancel_event))

    return {"task_id": task_id, "status": "started"}


@router.get("/ml/pipeline-status/{task_id}", summary="获取流水线运行状态")
async def api_pipeline_status(task_id: str):
    """轮询流水线任务状态，返回当前步骤、日志"""
    task = _pipeline_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    return {
        "task_id": task_id,
        "status": task["status"],
        "step": task["step"],
        "logs": task["logs"],
        "steps": task["steps"],
        "started_at": task["started_at"],
        "finished_at": task.get("finished_at"),
    }


@router.post("/ml/pipeline-cancel/{task_id}", summary="取消流水线运行")
async def api_pipeline_cancel(task_id: str):
    """取消正在运行的流水线任务"""
    task = _pipeline_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    if task["status"] != "running":
        return {"task_id": task_id, "status": task["status"], "message": "任务未在运行"}
    task["cancel_event"].set()
    task["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 收到取消请求...")
    return {"task_id": task_id, "status": "cancelling"}


async def _run_pipeline_background(task_id: str, step: str, track_name: str | None, cancel_event: asyncio.Event):
    """后台执行流水线，检查 cancel_event"""
    task = _pipeline_tasks[task_id]
    steps_order = ["compute", "screen", "preprocess", "train", "backtest"]
    step_names = {
        "compute": "Phase B 特征计算",
        "screen": "Phase C 因子筛选",
        "preprocess": "Phase D 特征预处理",
        "train": "Phase E 模型训练",
        "backtest": "Phase G 回测校验",
    }
    start_idx = 0 if step == "all" else (steps_order.index(step) if step in steps_order else 0)

    for s in steps_order[start_idx:]:
        if cancel_event.is_set():
            task["status"] = "cancelled"
            task["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 流水线已取消")
            task["finished_at"] = datetime.now().isoformat()
            return

        task["step"] = s
        if track_name:
            task["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ▶ 赛道 [{track_name}] 开始 {step_names.get(s, s)}...")
        else:
            task["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ▶ 开始 {step_names.get(s, s)}...")
        t0 = time.time()

        try:
            result = await _run_single_step(s, track_name)
            elapsed = time.time() - t0
            task["steps"][s] = result
            if result.get("status") == "failed":
                task["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ {step_names.get(s, s)} 失败 ({elapsed:.1f}s): {result.get('error', '')}")
                if step != "all":
                    task["status"] = "failed"
                    task["finished_at"] = datetime.now().isoformat()
                    return
            else:
                task["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ {step_names.get(s, s)} 完成 ({elapsed:.1f}s)")
        except Exception as e:
            elapsed = time.time() - t0
            task["steps"][s] = {"status": "failed", "error": str(e)}
            task["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ {step_names.get(s, s)} 异常 ({elapsed:.1f}s): {e}")
            if step != "all":
                task["status"] = "failed"
                task["finished_at"] = datetime.now().isoformat()
                return

    task["status"] = "completed"
    task["step"] = ""
    if track_name:
        task["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] 🎉 赛道 [{track_name}] 流水线全部完成")
    else:
        task["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] 🎉 流水线全部完成")
    task["finished_at"] = datetime.now().isoformat()


async def _run_single_step(step_name: str, track_name: str | None = None) -> dict:
    """执行单个流水线步骤"""
    if step_name == "compute":
        from scripts.compute_features import run_compute_features
        return await run_compute_features()
    elif step_name == "screen":
        from scripts.screen_factors import run_screen_factors
        return await run_screen_factors()
    elif step_name == "preprocess":
        from scripts.preprocess_features import run_preprocess_features
        return await run_preprocess_features()
    elif step_name == "train":
        if track_name:
            import importlib.util as _util
            script_path = BASE_DIR / "scripts" / "train_models.py"
            spec = _util.spec_from_file_location("train_models", script_path)
            if not spec or not spec.loader:
                return {"status": "failed", "error": "训练脚本加载失败"}
            tm = _util.module_from_spec(spec)
            spec.loader.exec_module(tm)
            track_map = await tm.get_track_stock_map()
            if track_name not in track_map:
                return {"status": "failed", "error": f"赛道 '{track_name}' 不存在"}
            train_df, val_df, test_df, feature_cols = tm.load_data()
            result = tm.train_track_model(
                track_name, track_map[track_name],
                train_df, val_df, test_df, feature_cols,
                params=None,
            )

            # 记录单赛道训练日志
            try:
                from app.db.database import async_session_maker
                from app.models.track import PipelineRun
                import subprocess as _sp
                try:
                    git_hash = _sp.check_output(
                        ["git", "rev-parse", "--short", "HEAD"], stderr=_sp.DEVNULL, text=True
                    ).strip()
                except Exception:
                    git_hash = None
                async with async_session_maker() as _session:
                    _run_log = PipelineRun(
                        run_type="train",
                        status="success",
                        params_snapshot={"scope": "single", "track_name": track_name},
                        results_summary={track_name: result},
                        git_commit_hash=git_hash,
                        feature_count=len(feature_cols),
                    )
                    _session.add(_run_log)
                    await _session.commit()
            except Exception as _e:
                logger.warning(f"单赛道训练日志记录失败: {_e}")

            return {"status": "success", "track": track_name, "result": result}
        else:
            from scripts.train_models import main as train_all
            await train_all()
            return {"status": "success"}
    elif step_name == "backtest":
        import subprocess
        result = subprocess.run(
            ["python3", "scripts/run_backtest.py"],
            capture_output=True, text=True, cwd=BASE_DIR, timeout=300
        )
        return {
            "status": "success" if result.returncode == 0 else "failed",
            "log": result.stdout[-800:] if result.stdout else "",
        }
    return {"status": "failed", "error": f"未知步骤: {step_name}"}


@router.get("/ml/pipeline-runs", summary="获取流水线运行记录")
async def get_pipeline_runs(limit: int = 10, run_type: str | None = None):
    """获取最近 N 次流水线运行记录（训练/回测）"""
    from sqlalchemy import select, desc
    from app.models.track import PipelineRun
    from app.db.database import async_session_maker

    async with async_session_maker() as session:
        q = select(PipelineRun).order_by(desc(PipelineRun.created_at))
        if run_type:
            q = q.where(PipelineRun.run_type == run_type)
        q = q.limit(limit)
        result = await session.execute(q)
        records = result.scalars().all()

    return [PipelineRunResponse.model_validate(r) for r in records]

