"""
异常检测器 (Anomaly Detector).

对每只股票的特征时序，用 IsolationForest 检测异常交易日。
产出：每只股票每天是否异常及异常分数。

异常的含义：该股票当日的量价行为显著偏离其自身的历史模式，
可能对应突发利好/利空、资金异动等。

依赖: scikit-learn (已安装)
数据: 预处理后的 parquet 文件 (val + test)
"""

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)

PREPROCESSED_DIR = Path(__file__).resolve().parent.parent.parent.parent / "ml" / "preprocessed"


class AnomalyDetector:
    """异常检测器"""

    def __init__(self):
        self.feature_cols: list[str] = []
        self._load_feature_cols()

    def _load_feature_cols(self):
        path = PREPROCESSED_DIR / "feature_cols.json"
        if path.exists():
            with open(path) as f:
                self.feature_cols = json.load(f)
        else:
            logger.warning("feature_cols.json 不存在")
            self.feature_cols = []

    def analyze(self, df: pd.DataFrame | None = None,
                track_name: str = "all",
                stock_codes: list[str] | None = None,
                contamination: float = 0.05) -> dict:
        """运行异常检测。

        Args:
            df: 预处理数据，为 None 时自动加载
            track_name: 赛道名 (用于返回信息)
            stock_codes: 要分析的股票代码列表，None 时分析全部
            contamination: 预计的异常比例 (0.01~0.1)

        Returns:
            dict: {
                "analysis_type": "anomaly",
                "track_name": str,
                "anomalies": [{"stock_code": str, "date": str, "score": float, "features": {...}}, ...],
                "summary": {"total_stocks": int, "anomaly_count": int, ...},
            }
        """
        if df is None:
            df = self._load_data()
        if df is None or df.empty:
            return {"analysis_type": "anomaly", "track_name": track_name, "error": "数据为空", "anomalies": []}

        available = [c for c in self.feature_cols if c in df.columns]
        if len(available) < 3:
            return {"analysis_type": "anomaly", "track_name": track_name,
                    "error": f"可用特征不足 ({len(available)})", "anomalies": []}

        if stock_codes:
            df = df[df["stock_code"].isin(stock_codes)]

        # 逐股票检测异常
        all_anomalies = []
        stock_stats = {}

        for stock_code, group in df.groupby("stock_code"):
            group = group.sort_values("date")
            if len(group) < 20:
                continue

            X = group[available].fillna(0).values

            # IsolationForest
            iso_forest = IsolationForest(
                n_estimators=100,
                contamination=contamination,
                random_state=42,
            )
            preds = iso_forest.fit_predict(X)
            scores = iso_forest.score_samples(X)  # 越负越异常

            anomaly_mask = preds == -1
            n_anomalies = int(anomaly_mask.sum())

            stock_stats[stock_code] = {
                "total_days": len(group),
                "anomaly_count": n_anomalies,
                "anomaly_ratio": round(n_anomalies / len(group), 4),
            }

            if n_anomalies > 0:
                for i in range(len(group)):
                    if anomaly_mask[i]:
                        row = group.iloc[i]
                        # 挑选几个关键特征展示
                        key_features = {}
                        for feat in available:
                            if any(kw in feat for kw in ("ret", "vol_ratio", "rsi", "bb_width", "sharpe")):
                                key_features[feat] = round(float(row[feat]), 4) if pd.notna(row[feat]) else None
                        all_anomalies.append({
                            "stock_code": stock_code,
                            "date": str(row["date"]),
                            "anomaly_score": round(float(scores[i]), 4),
                            "key_features": key_features,
                        })

        # 按异常分数排序，取 Top 50
        all_anomalies.sort(key=lambda x: x["anomaly_score"])
        top_anomalies = all_anomalies[:50]

        # 汇总
        total_anomalies = len(all_anomalies)
        total_stocks = len(stock_stats)
        avg_ratio = np.mean([s["anomaly_ratio"] for s in stock_stats.values()]) if stock_stats else 0

        return {
            "analysis_type": "anomaly",
            "track_name": track_name,
            "anomalies": top_anomalies,
            "summary": {
                "total_stocks": total_stocks,
                "total_anomalies": total_anomalies,
                "avg_anomaly_ratio": round(float(avg_ratio), 4),
                "contamination": contamination,
                "stock_stats": stock_stats,
            },
        }

    def _load_data(self) -> pd.DataFrame | None:
        try:
            val = pd.read_parquet(PREPROCESSED_DIR / "val.parquet")
            test = pd.read_parquet(PREPROCESSED_DIR / "test.parquet")
            df = pd.concat([val, test], ignore_index=True)
            logger.info(f"AnomalyDetector: 加载 {len(df)} 行数据")
            return df
        except Exception as e:
            logger.error(f"AnomalyDetector 数据加载失败: {e}")
            return None
