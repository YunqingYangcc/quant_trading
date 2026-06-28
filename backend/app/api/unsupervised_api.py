"""
无监督学习 API (Unsupervised Learning).

提供三项无监督分析能力的 HTTP API：
  1. POST /unsupervised/run     — 触发分析
  2. GET  /unsupervised/regime  — 获取市场状态结果
  3. GET  /unsupervised/pca     — 获取 PCA 结果
  4. GET  /unsupervised/anomaly — 获取异常检测结果

调用方式: 前端手动触发 + 页面渲染结果。
"""

import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from app.db.database import async_session_maker

from sqlalchemy import select, desc

logger = logging.getLogger(__name__)
router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PREPROCESSED_DIR = BASE_DIR / "ml" / "preprocessed"


@router.post("/unsupervised/run", summary="运行无监督学习分析")
async def run_unsupervised(types: str = Query("all", description="分析类型: all/regime/pca/anomaly, 逗号分隔")):
    """触发无监督学习分析，结果自动保存到数据库。"""
    from app.ml.unsupervised import RegimeDetector, PCAAnalyzer, AnomalyDetector
    from app.models.track import UnsupervisedResult

    # 1. 加载预处理数据
    try:
        import pandas as pd
        val = pd.read_parquet(PREPROCESSED_DIR / "val.parquet")
        test = pd.read_parquet(PREPROCESSED_DIR / "test.parquet")
        df = pd.concat([val, test], ignore_index=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据加载失败: {e}")

    # 2. 判读分析类型
    analysis_types = ["regime", "pca", "anomaly"] if types == "all" else types.split(",")
    results = {}

    for atype in analysis_types:
        atype = atype.strip()
        try:
            if atype == "regime":
                detector = RegimeDetector()
                result = detector.analyze(df)
            elif atype == "pca":
                analyzer = PCAAnalyzer()
                result = analyzer.analyze(df, n_components=2)
            elif atype == "anomaly":
                detector = AnomalyDetector()
                result = detector.analyze(df, track_name="all", contamination=0.05)
            else:
                continue

            # 3. 保存到数据库
            async with async_session_maker() as session:
                record = UnsupervisedResult(
                    analysis_type=atype,
                    track_name=result.get("track_name", "all"),
                    result_date=datetime.now().strftime("%Y-%m-%d"),
                    payload=result,
                )
                session.add(record)
                await session.commit()

            results[atype] = {"status": "success", "message": f"{atype} 分析完成"}

        except Exception as e:
            logger.error(f"{atype} 分析失败: {e}")
            results[atype] = {"status": "failed", "message": str(e)}

    return {"message": "分析完成", "results": results}


@router.get("/unsupervised/regime", summary="获取市场状态分析结果")
async def get_regime(limit: int = Query(1, description="返回最近 N 次结果")):
    """获取市场状态聚类的最新结果。"""
    from app.models.track import UnsupervisedResult

    async with async_session_maker() as session:
        stmt = (select(UnsupervisedResult)
                .where(UnsupervisedResult.analysis_type == "regime")
                .order_by(desc(UnsupervisedResult.created_at))
                .limit(limit))
        result = await session.execute(stmt)
        records = result.scalars().all()

    if not records:
        return {"analysis_type": "regime", "message": "暂无分析结果，请先执行 POST /unsupervised/run"}

    outputs = []
    for r in records:
        outputs.append({
            "id": r.id,
            "track_name": r.track_name,
            "result_date": r.result_date,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "data": r.payload,
        })
    return outputs[0] if len(outputs) == 1 else outputs


@router.get("/unsupervised/pca", summary="获取因子降维分析结果")
async def get_pca(limit: int = Query(1)):
    """获取 PCA 因子降维的最新结果。"""
    from app.models.track import UnsupervisedResult

    async with async_session_maker() as session:
        stmt = (select(UnsupervisedResult)
                .where(UnsupervisedResult.analysis_type == "pca")
                .order_by(desc(UnsupervisedResult.created_at))
                .limit(limit))
        result = await session.execute(stmt)
        records = result.scalars().all()

    if not records:
        return {"analysis_type": "pca", "message": "暂无分析结果，请先执行 POST /unsupervised/run"}

    outputs = []
    for r in records:
        outputs.append({
            "id": r.id,
            "result_date": r.result_date,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "data": r.payload,
        })
    return outputs[0] if len(outputs) == 1 else outputs


@router.get("/unsupervised/anomaly", summary="获取异常检测结果")
async def get_anomaly(limit: int = Query(1)):
    """获取异常检测的最新结果。"""
    from app.models.track import UnsupervisedResult

    async with async_session_maker() as session:
        stmt = (select(UnsupervisedResult)
                .where(UnsupervisedResult.analysis_type == "anomaly")
                .order_by(desc(UnsupervisedResult.created_at))
                .limit(limit))
        result = await session.execute(stmt)
        records = result.scalars().all()

    if not records:
        return {"analysis_type": "anomaly", "message": "暂无分析结果，请先执行 POST /unsupervised/run"}

    outputs = []
    for r in records:
        outputs.append({
            "id": r.id,
            "track_name": r.track_name,
            "result_date": r.result_date,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "data": r.payload,
        })
    return outputs[0] if len(outputs) == 1 else outputs
