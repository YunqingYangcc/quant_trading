"""
赛道打分器。

使用已训练的 LightGBM 模型输出：
  1. 个股强弱分（赛道内选股排序）
  2. 赛道景气总分（判断当前赛道是否可持仓）
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

from app.ml.model_trainer import LightGBMTrainer

logger = logging.getLogger(__name__)


class TrackScorer:
    """赛道打分器"""

    def __init__(self, track_name: str):
        self.track_name = track_name
        self.trainer = LightGBMTrainer(track_name)
        self._latest_model_id: str | None = None

    def load_latest_model(self) -> bool:
        """加载该赛道最新模型"""
        models = self.trainer.list_models()
        if not models:
            logger.warning("No model found for track: %s", self.track_name)
            return False
        latest = models[0]
        ok = self.trainer.load(latest["model_id"])
        if ok:
            self._latest_model_id = latest["model_id"]
        return ok

    def score_stocks(
        self,
        feature_dict: dict[str, pd.DataFrame],
    ) -> dict[str, Any]:
        """个股打分：返回赛道内每只股票的最新强弱分

        Args:
            feature_dict: {stock_code: feature_df}, feature_df 的最后一行是当前时刻特征

        Returns:
            {
                "track_name": str,
                "model_id": str,
                "scores": [
                    {"stock_code": str, "score": float, "rank": int},
                    ...
                ],
                "track_sentiment": float,  # 赛道景气总分 0-100
                "top_stock": str,
                "top_score": float,
            }
        """
        if self.trainer.model is None:
            if not self.load_latest_model():
                return {
                    "track_name": self.track_name,
                    "model_id": "",
                    "scores": [],
                    "track_sentiment": 0.0,
                    "top_stock": "",
                    "top_score": 0.0,
                }

        scores = []
        for stock_code, df in feature_dict.items():
            try:
                # 只取最新一行
                latest = df.iloc[-1:].copy()
                pred = self.trainer.predict(latest)
                score = float(pred[0])
                scores.append({"stock_code": stock_code, "score": round(score, 6)})
            except Exception as e:
                logger.warning("Score failed for %s: %s", stock_code, e)
                scores.append({"stock_code": stock_code, "score": 0.0})

        # 排序
        scores.sort(key=lambda x: x["score"], reverse=True)
        for i, s in enumerate(scores):
            s["rank"] = i + 1

        # 赛道景气总分 = 个股分数中位数映射到 0-100
        if scores:
            median_score = np.median([s["score"] for s in scores])
            # sigmoid 映射到 0-100
            track_sentiment = round(100.0 / (1.0 + np.exp(-median_score * 5)), 2)
        else:
            track_sentiment = 0.0

        return {
            "track_name": self.track_name,
            "model_id": self._latest_model_id or "",
            "scores": scores,
            "track_sentiment": track_sentiment,
            "top_stock": scores[0]["stock_code"] if scores else "",
            "top_score": scores[0]["score"] if scores else 0.0,
        }

    def batch_score_all_tracks(
        self,
        all_features: dict[str, dict[str, pd.DataFrame]],
    ) -> dict[str, Any]:
        """批量打分所有赛道

        Args:
            all_features: {track_name: {stock_code: feature_df}}

        Returns:
            {track_name: score_result}
        """
        results = {}
        for track_name, features in all_features.items():
            self.track_name = track_name
            self.trainer = LightGBMTrainer(track_name)
            results[track_name] = self.score_stocks(features)
        return results
