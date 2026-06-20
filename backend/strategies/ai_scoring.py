"""
AI 打分策略（将现有模型封装为策略接口）。

使用已训练的 LightGBM 模型生成选股信号。
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent / "ml" / "models"
PREPROCESSED_DIR = Path(__file__).resolve().parent / "ml" / "preprocessed"


class AIScoringStrategy:
    """AI 模型打分轮动策略。"""

    def generate_signals(self, prices: pd.DataFrame, features: pd.DataFrame | None = None) -> pd.DataFrame:
        """用 AI 模型预测信号。

        优先用缓存打分，否则实时加载模型预测。
        """
        # 尝试从缓存加载
        cache_path = PREPROCESSED_DIR / "backtest_scores.parquet"
        if cache_path.exists():
            scores = pd.read_parquet(cache_path)
            scores["trade_date"] = pd.to_datetime(scores["trade_date"])
        else:
            scores = self._compute_scores(prices)

        if scores is None or scores.empty:
            return pd.DataFrame()

        # 月频调仓：每月初选 Top-3
        signals = []
        for date in pd.date_range(prices.index.min(), prices.index.max(), freq="MS"):
            valid_scores = scores[scores["trade_date"] <= date]
            if len(valid_scores) == 0:
                continue
            latest_date = valid_scores["trade_date"].max()
            latest = valid_scores[valid_scores["trade_date"] == latest_date]
            ranked = latest.sort_values("pred_score", ascending=False)
            if len(ranked) < 3:
                continue
            top3 = ranked.head(3)["stock_code"].tolist()
            weights = {s: 1.0 / 3 for s in top3}
            signals.append({
                "date": date,
                "buy": top3,
                "weights": weights,
                "sell_all": True,
            })

        return pd.DataFrame(signals).set_index("date") if signals else pd.DataFrame()

    def _compute_scores(self, prices: pd.DataFrame) -> pd.DataFrame | None:
        """用模型实时计算打分."""
        import joblib

        try:
            with open(PREPROCESSED_DIR / "feature_cols.json") as f:
                feature_cols = json.load(f)
        except Exception:
            return None

        # 合并所有赛道的模型打分
        all_scores = []
        for pkl_path in MODELS_DIR.glob("*.pkl"):
            track = pkl_path.stem
            try:
                val = pd.read_parquet(PREPROCESSED_DIR / "val.parquet")
                test = pd.read_parquet(PREPROCESSED_DIR / "test.parquet")
                df = pd.concat([val, test], ignore_index=True)
                df = df.sort_values("date")

                model = joblib.load(pkl_path)
                X = df[feature_cols].fillna(0)
                df["pred_score"] = model.predict_proba(X)[:, 1]
                df["stock_code"] = df["stock_code"]
                df["trade_date"] = pd.to_datetime(df["date"])
                all_scores.append(df[["trade_date", "stock_code", "pred_score"]])
            except Exception:
                continue

        if not all_scores:
            return None
        return pd.concat(all_scores, ignore_index=True)
