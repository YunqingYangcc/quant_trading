"""
无监督学习分析脚本。

按顺序执行三项无监督分析：
  1. 市场状态聚类 (regime) — KMeans
  2. 因子降维 (pca) — PCA
  3. 异常检测 (anomaly) — IsolationForest

结果写入 UnsupervisedResult 表，供 API 查询。

Usage:
    cd backend && python3 scripts/run_unsupervised.py --type all
    cd backend && python3 scripts/run_unsupervised.py --type regime,pca
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.db.database import async_session_maker, ensure_database_ready
from app.models.track import UnsupervisedResult
from app.ml.unsupervised import RegimeDetector, PCAAnalyzer, AnomalyDetector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PREPROCESSED_DIR = Path(__file__).resolve().parent.parent / "ml" / "preprocessed"


def load_data() -> pd.DataFrame | None:
    """加载预处理数据"""
    try:
        val = pd.read_parquet(PREPROCESSED_DIR / "val.parquet")
        test = pd.read_parquet(PREPROCESSED_DIR / "test.parquet")
        df = pd.concat([val, test], ignore_index=True)
        logger.info(f"加载数据: {len(df)} 行, {len(df.columns)} 列")
        return df
    except Exception as e:
        logger.error(f"数据加载失败: {e}")
        return None


async def save_result(session, analysis_type: str, track_name: str,
                       payload: dict, params: dict | None = None):
    """保存分析结果到数据库"""
    record = UnsupervisedResult(
        analysis_type=analysis_type,
        track_name=track_name,
        result_date=datetime.now().strftime("%Y-%m-%d"),
        payload=payload,
        params_snapshot=params,
    )
    session.add(record)
    await session.commit()
    logger.info(f"  [{analysis_type}] 结果已保存 (id={record.id})")


async def run_regime(df: pd.DataFrame):
    """运行市场状态聚类"""
    logger.info("\n" + "=" * 50)
    logger.info("1. 市场状态聚类分析")
    logger.info("=" * 50)

    detector = RegimeDetector()
    t0 = time.time()
    result = detector.analyze(df)
    elapsed = time.time() - t0

    if "error" in result:
        logger.warning(f"  失败: {result['error']}")
    else:
        summary = result["summary"]
        logger.info(f"  当前状态: {summary['current_label']}")
        logger.info(f"  总天数: {summary['total_dates']}, 状态切换: {summary['num_transitions']} 次")
        logger.info(f"  分布: {summary['regime_distribution']}")
        logger.info(f"  耗时: {elapsed:.2f}s")

    async with async_session_maker() as session:
        await save_result(session, "regime", "all", result,
                          {"n_clusters": 3})

    return result


async def run_pca(df: pd.DataFrame):
    """运行因子降维分析"""
    logger.info("\n" + "=" * 50)
    logger.info("2. 因子 PCA 降维分析")
    logger.info("=" * 50)

    analyzer = PCAAnalyzer()
    t0 = time.time()
    result = analyzer.analyze(df, n_components=2)
    elapsed = time.time() - t0

    if "error" in result:
        logger.warning(f"  失败: {result['error']}")
    else:
        logger.info(f"  特征总数: {result['total_features']}")
        logger.info(f"  PC1 解释方差: {result['explained_variance_ratio'][0]:.2%}")
        logger.info(f"  PC2 解释方差: {result['explained_variance_ratio'][1]:.2%}")
        logger.info(f"  累计解释方差: {result['cumulative_variance']:.2%}")
        logger.info(f"  PCA 数据点: {len(result['data_points'])}")
        logger.info(f"  耗时: {elapsed:.2f}s")

    async with async_session_maker() as session:
        await save_result(session, "pca", "all", result,
                          {"n_components": 2})

    return result


async def run_anomaly(df: pd.DataFrame):
    """运行异常检测"""
    logger.info("\n" + "=" * 50)
    logger.info("3. 异常检测分析")
    logger.info("=" * 50)

    detector = AnomalyDetector()
    t0 = time.time()
    result = detector.analyze(df, track_name="all", contamination=0.05)
    elapsed = time.time() - t0

    if "error" in result:
        logger.warning(f"  失败: {result['error']}")
    else:
        summary = result["summary"]
        logger.info(f"  分析股票: {summary['total_stocks']} 只")
        logger.info(f"  发现异常: {summary['total_anomalies']} 条")
        logger.info(f"  平均异常率: {summary['avg_anomaly_ratio']:.2%}")
        if result["anomalies"]:
            logger.info(f"  最异常: {result['anomalies'][0]['stock_code']} "
                        f"@{result['anomalies'][0]['date']}")
        logger.info(f"  耗时: {elapsed:.2f}s")

    async with async_session_maker() as session:
        await save_result(session, "anomaly", "all", result,
                          {"contamination": 0.05})

    return result


async def main():
    parser = argparse.ArgumentParser(description="无监督学习分析")
    parser.add_argument("--type", default="all",
                        help="分析类型: all / regime,pca,anomaly (逗号分隔)")
    args = parser.parse_args()

    await ensure_database_ready()

    types = args.type.split(",")
    if "all" in types:
        types = ["regime", "pca", "anomaly"]

    logger.info("=" * 60)
    logger.info("无监督学习分析开始")
    logger.info(f"分析类型: {', '.join(types)}")
    logger.info("=" * 60)

    # 加载数据（只加载一次）
    df = load_data()
    if df is None:
        logger.error("数据加载失败，退出")
        return

    results = {}
    if "regime" in types:
        results["regime"] = await run_regime(df)
    if "pca" in types:
        results["pca"] = await run_pca(df)
    if "anomaly" in types:
        results["anomaly"] = await run_anomaly(df)

    logger.info("\n" + "=" * 60)
    logger.info("分析完成!")
    logger.info(f"成功: {', '.join(k for k, v in results.items() if 'error' not in v)}")
    failed = [k for k, v in results.items() if 'error' in v]
    if failed:
        logger.warning(f"失败: {', '.join(failed)}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
