"""
赛道 LightGBM 时序训练器。

核心设计：
  1. 每个赛道独立模型
  2. 严格时间滚动训练（禁止 shuffle）
  3. 目标：预测未来 N 日个股超额收益
  4. 输出：个股强弱分 + 赛道景气总分
"""

import json
import logging
import pickle
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parent / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


class LightGBMTrainer:
    """赛道 LightGBM 训练器"""

    def __init__(self, track_name: str, model_dir: str | Path | None = None):
        self.track_name = track_name
        self.model_dir = Path(model_dir) if model_dir else MODELS_DIR
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.model = None
        self.feature_names: list[str] = []
        self.train_metrics: dict[str, Any] = {}
        self.model_id: str = ""

    def train(
        self,
        X: pd.DataFrame,
        y: np.ndarray,
        train_end_idx: int = -1,
        tune: bool = False,
    ) -> dict[str, Any]:
        """时间序列滚动训练。

        Args:
            X: 特征 DataFrame（行=时间序列，列=特征）
            y: 目标变量（未来 N 日超额收益）
            train_end_idx: 训练集截止索引（-1=用全部数据的 80%）
            tune: 是否调参

        Returns:
            metrics dict
        """
        import lightgbm as lgb

        # 列去重
        X = X.loc[:, ~X.columns.duplicated()]

        # 去掉全 NaN 和全 0 列
        X = X.dropna(axis=1, how="all")
        X = X.loc[:, (X != 0).any()]

        # 去掉 y 中 NaN 的行
        valid = ~np.isnan(y)
        X_clean = X[valid]
        y_clean = y[valid]

        n = len(X_clean)
        if n < 100:
            raise ValueError(f"Too few samples for training: {n}")

        if train_end_idx < 0 or train_end_idx >= n:
            split = int(n * 0.8)
        else:
            split = train_end_idx

        X_train = X_clean.iloc[:split]
        y_train = y_clean[:split]
        X_val = X_clean.iloc[split:]
        y_val = y_clean[split:]

        self.feature_names = X_train.columns.tolist()

        params = {
            "objective": "regression",
            "metric": "mse",
            "boosting_type": "gbdt",
            "num_leaves": 31,
            "max_depth": 5,
            "learning_rate": 0.05,
            "n_estimators": 500,
            "min_child_samples": 20,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "reg_alpha": 0.1,
            "reg_lambda": 0.1,
            "verbosity": -1,
            "random_state": 42,
        }

        if tune and len(X_train) > 500:
            # 简单调参：调整 num_leaves 和 learning_rate
            best_score = float("inf")
            best_params = dict(params)
            for leaves in [15, 31, 63]:
                for lr in [0.03, 0.05, 0.1]:
                    p = dict(params)
                    p["num_leaves"] = leaves
                    p["learning_rate"] = lr
                    model = lgb.LGBMRegressor(**p, n_estimators=200)
                    model.fit(
                        X_train, y_train,
                        eval_set=[(X_val, y_val)],
                        callbacks=[lgb.early_stopping(10)],
                    )
                    score = model.best_score_["valid_0"]["l2"]
                    if score < best_score:
                        best_score = score
                        best_params = p
            params = best_params

        # 最终训练
        self.model = lgb.LGBMRegressor(**params)
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(20)],
        )

        # 评估
        train_pred = self.model.predict(X_train)
        val_pred = self.model.predict(X_val)
        train_r2 = float(np.corrcoef(y_train, train_pred)[0, 1] ** 2) if len(y_train) > 1 else 0
        val_r2 = float(np.corrcoef(y_val, val_pred)[0, 1] ** 2) if len(y_val) > 1 else 0

        # 特征重要性
        importance = dict(zip(
            self.feature_names,
            self.model.feature_importances_.tolist(),
        ))
        sorted_imp = dict(sorted(importance.items(), key=lambda x: -x[1]))

        self.train_metrics = {
            "model_id": self.model_id,
            "track_name": self.track_name,
            "n_train": len(X_train),
            "n_val": len(X_val),
            "n_features": len(self.feature_names),
            "train_r2": round(train_r2, 6),
            "val_r2": round(val_r2, 6),
            "feature_importance": sorted_imp,
            "params": params,
        }

        return self.train_metrics

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """预测"""
        if self.model is None:
            raise RuntimeError("Model not trained yet")
        X_clean = X[self.feature_names].copy()
        X_clean = X_clean.fillna(0)
        return self.model.predict(X_clean)

    def save(self, name: str | None = None) -> str:
        """保存模型到磁盘"""
        if self.model is None:
            raise RuntimeError("No model to save")

        self.model_id = name or f"{self.track_name}_{uuid.uuid4().hex[:8]}"
        path = self.model_dir / f"{self.model_id}.pkl"

        payload = {
            "model": self.model,
            "feature_names": self.feature_names,
            "metrics": self.train_metrics,
            "track_name": self.track_name,
            "saved_at": datetime.now().isoformat(),
        }
        with open(path, "wb") as f:
            pickle.dump(payload, f)

        logger.info("Model saved: %s", path)
        return self.model_id

    def load(self, model_id: str) -> bool:
        """加载已训练的模型"""
        path = self.model_dir / f"{model_id}.pkl"
        if not path.exists():
            logger.warning("Model not found: %s", path)
            return False

        with open(path, "rb") as f:
            payload = pickle.load(f)

        self.model = payload["model"]
        self.feature_names = payload["feature_names"]
        self.train_metrics = payload["metrics"]
        self.track_name = payload["track_name"]
        self.model_id = model_id
        return True

    def list_models(self) -> list[dict[str, Any]]:
        """列出该赛道所有已保存模型"""
        results = []
        for p in self.model_dir.glob(f"{self.track_name}_*.pkl"):
            try:
                with open(p, "rb") as f:
                    payload = pickle.load(f)
                results.append({
                    "model_id": p.stem,
                    "track_name": payload.get("track_name", ""),
                    "saved_at": payload.get("saved_at", ""),
                    "val_r2": payload.get("metrics", {}).get("val_r2", 0),
                    "n_features": payload.get("metrics", {}).get("n_features", 0),
                })
            except Exception:
                continue
        return sorted(results, key=lambda x: x["saved_at"], reverse=True)
