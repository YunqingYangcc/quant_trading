"""
因子降维分析器 (PCA Factor Analyzer).

对全部特征矩阵做 PCA 降维到 2 个主成分，产出：
  1. 各主成分解释方差比例 (explained_variance_ratio)
  2. 因子载荷矩阵 (每个因子在各主成分上的权重)
  3. 因子在 2D 空间的坐标 (用于可视化散点图)
  4. 降维后的数据点坐标

帮助用户理解 100+ 因子的结构，发现冗余。

依赖: scikit-learn (已安装)
数据: 预处理后的 parquet 文件 (val + test)
"""

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

PREPROCESSED_DIR = Path(__file__).resolve().parent.parent.parent.parent / "ml" / "preprocessed"


class PCAAnalyzer:
    """因子降维分析器"""

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

    def analyze(self, df: pd.DataFrame | None = None, n_components: int = 2) -> dict:
        """运行 PCA 分析。

        Args:
            df: 预处理数据，为 None 时自动加载
            n_components: 主成分数 (默认 2)

        Returns:
            dict: {
                "analysis_type": "pca",
                "explained_variance_ratio": [float, ...],
                "cumulative_variance": float,
                "factor_loadings": [{"feature": str, "pc1": float, "pc2": float, "category": str}, ...],
                "data_points": [{"pc1": float, "pc2": float, "category": str}, ...],
                "categories": {category: {"count": int, "explanations": str}, ...},
            }
        """
        if df is None:
            df = self._load_data()
        if df is None or df.empty:
            return {"analysis_type": "pca", "error": "数据为空"}

        available = [c for c in self.feature_cols if c in df.columns]
        if len(available) < 3:
            return {"analysis_type": "pca", "error": f"可用特征不足 ({len(available)})"}

        # 提取特征矩阵，填充 NaN 为列均值
        X = df[available].copy()
        X = X.fillna(X.mean())

        # 标准化
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # PCA
        pca = PCA(n_components=min(n_components, len(available)))
        X_pca = pca.fit_transform(X_scaled)

        # 因子载荷 (loadings = components_ * sqrt(eigenvalues))
        loadings = pca.components_.T * np.sqrt(pca.explained_variance_)

        # 构建因子载荷表
        category_map = self._categorize_features(available)
        factor_loadings = []
        for i, feat in enumerate(available):
            factor_loadings.append({
                "feature": feat,
                "pc1": round(float(loadings[i, 0]), 4),
                "pc2": round(float(loadings[i, 1]), 4) if n_components >= 2 else 0,
                "category": category_map.get(feat, "other"),
            })

        # 聚合每类的因子载荷均值
        cat_stats = {}
        for fl in factor_loadings:
            cat = fl["category"]
            if cat not in cat_stats:
                cat_stats[cat] = {"count": 0, "pc1_sum": 0.0, "pc2_sum": 0.0}
            cat_stats[cat]["count"] += 1
            cat_stats[cat]["pc1_sum"] += abs(fl["pc1"])
            cat_stats[cat]["pc2_sum"] += abs(fl["pc2"])

        # 从配置中获取特征释义
        feat_descriptions = self._load_feature_descriptions()

        categories_summary = {}
        for cat, stats in cat_stats.items():
            categories_summary[cat] = {
                "count": stats["count"],
                "avg_pc1_loading": round(stats["pc1_sum"] / stats["count"], 4),
                "avg_pc2_loading": round(stats["pc2_sum"] / stats["count"], 4),
                "explanations": feat_descriptions.get(cat, f"{cat} 类特征"),
            }

        # 构建数据点 (最多采 2000 个点，避免前端渲染卡顿)
        n_samples = min(2000, len(X_pca))
        sample_idx = np.random.RandomState(42).choice(len(X_pca), n_samples, replace=False)
        data_points = [
            {"pc1": round(float(X_pca[i, 0]), 4), "pc2": round(float(X_pca[i, 1]), 4) if n_components >= 2 else 0}
            for i in sample_idx
        ]

        return {
            "analysis_type": "pca",
            "track_name": "all",
            "explained_variance_ratio": [round(float(v), 4) for v in pca.explained_variance_ratio_],
            "cumulative_variance": round(float(np.sum(pca.explained_variance_ratio_)), 4),
            "total_features": len(available),
            "factor_loadings": factor_loadings,
            "data_points": data_points,
            "categories": categories_summary,
            "category_map": category_map,
        }

    def _categorize_features(self, features: list[str]) -> dict[str, str]:
        """将特征归类"""
        category_map = {}
        for feat in features:
            if feat.startswith("track_"):
                category_map[feat] = "赛道专属"
            elif feat.startswith("fund_"):
                category_map[feat] = "基本面"
            elif any(feat.startswith(p) for p in ["rsi", "stoch", "willr", "roc", "ao", "ppo"]):
                category_map[feat] = "动量"
            elif any(feat.startswith(p) for p in ["sma", "ema", "macd", "adx", "aroon", "cci", "trix"]):
                category_map[feat] = "趋势"
            elif any(feat.startswith(p) for p in ["atr", "bb_", "ulcer"]):
                category_map[feat] = "波动率"
            elif any(feat.startswith(p) for p in ["obv", "cmf", "fi_", "mfi", "vpt", "vol_"]):
                category_map[feat] = "量能"
            else:
                category_map[feat] = "统计"
        return category_map

    def _load_feature_descriptions(self) -> dict[str, str]:
        """加载特征分类的说明文字"""
        return {
            "动量": "衡量价格变化速度，超买超卖信号",
            "趋势": "识别价格方向，跟随趋势信号",
            "波动率": "衡量价格波动幅度，风险管理参考",
            "量能": "成交量相关的资金流向信号",
            "统计": "统计衍生特征，如偏度、分位数等",
            "赛道专属": f"赛道特有的量价/资金面特征 ({len([c for c in self.feature_cols if c.startswith('track_')])}个)",
            "基本面": "公司财务/股东结构等基本面数据",
        }

    def _load_data(self) -> pd.DataFrame | None:
        try:
            val = pd.read_parquet(PREPROCESSED_DIR / "val.parquet")
            test = pd.read_parquet(PREPROCESSED_DIR / "test.parquet")
            df = pd.concat([val, test], ignore_index=True)
            logger.info(f"PCAAnalyzer: 加载 {len(df)} 行数据")
            return df
        except Exception as e:
            logger.error(f"PCAAnalyzer 数据加载失败: {e}")
            return None
