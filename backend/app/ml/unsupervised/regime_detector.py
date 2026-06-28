"""
市场状态聚类器 (Market Regime Detector).

对每个赛道，基于聚合特征（收益、波动率、成交量等），
用 KMeans (n=3) 将市场分为 3 种状态：
  - 牛市 (1): 上涨趋势强，赚钱效应好
  - 震荡 (0): 方向不明，波动率偏低
  - 熊市 (2): 下跌趋势明显，亏钱效应显著

依赖: scikit-learn (已安装)
数据: 预处理后的 parquet 文件 (val + test)
"""

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

PREPROCESSED_DIR = Path(__file__).resolve().parent.parent.parent.parent / "ml" / "preprocessed"

REGIME_META = {
    0: {"label": "震荡", "description": "市场方向不明，波动率偏低，适合观望或轻仓", "color": "#909399"},
    1: {"label": "牛市", "description": "上涨趋势明显，赚钱效应好，可积极持仓", "color": "#67C23A"},
    2: {"label": "熊市", "description": "下跌趋势明显，亏钱效应显著，适合防守", "color": "#F56C6C"},
}


class RegimeDetector:
    """市场状态聚类器"""

    def __init__(self):
        self.feature_cols: list[str] = []
        self._load_feature_cols()

    def _load_feature_cols(self):
        path = PREPROCESSED_DIR / "feature_cols.json"
        if path.exists():
            with open(path) as f:
                self.feature_cols = json.load(f)
        else:
            logger.warning("feature_cols.json 不存在，PCA 分析器无法工作")
            self.feature_cols = []

    def _select_features(self) -> list[str]:
        """挑选适合市场状态聚类的基础特征（不含赛道专属特征）"""
        if not self.feature_cols:
            return []
        # 排除赛道专属特征 (track_ 开头) 和基本面特征 (fund_ 开头)
        # 保留通用量价特征
        generic = [c for c in self.feature_cols if not c.startswith(("track_", "fund_"))]
        # 从中挑选关键特征
        key_prefixes = ("rsi", "adx", "bb_width", "price_pos", "sharpe",
                        "vol_ratio", "sma_dev", "ret_skew", "ret_pctile")
        selected = [c for c in generic if any(c.startswith(p) for p in key_prefixes)]
        if len(selected) < 5:
            # 回退到前 15 个通用特征
            selected = generic[:15]
        return selected[:15]  # 限制特征数，避免维度灾难

    def analyze(self, df: pd.DataFrame | None = None) -> dict:
        """运行市场状态聚类分析。

        Args:
            df: 预处理后的 DataFrame (含 date, stock_code, 特征列)
                 为 None 时自动从 parquet 加载

        Returns:
            dict: {
                "analysis_type": "regime",
                "track_name": "all",
                "regimes": [{"date": str, "regime": int, "label": str, "color": str}, ...],
                "summary": {...}
            }
        """
        if df is None:
            df = self._load_data()

        if df is None or df.empty:
            return {"analysis_type": "regime", "track_name": "all", "error": "数据为空", "regimes": []}

        features = self._select_features()
        available = [c for c in features if c in df.columns]
        if len(available) < 3:
            return {"analysis_type": "regime", "track_name": "all", "error": "可用特征不足", "regimes": []}

        # 按日期聚合：取所有股票当日特征的均值
        daily = df.groupby("date")[available].mean()
        # 排除全 NaN 行
        daily = daily.dropna(how="any")

        if len(daily) < 15:
            return {"analysis_type": "regime", "track_name": "all",
                    "error": f"有效日期不足 ({len(daily)} < 15)", "regimes": []}

        # 标准化
        scaler = StandardScaler()
        X = scaler.fit_transform(daily.values)

        # KMeans 聚类
        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        raw_labels = kmeans.fit_predict(X)

        # 智能标签映射：用收益率相关特征确定牛熊
        ret_features = [i for i, c in enumerate(available)
                        if any(kw in c for kw in ("sharpe", "sma_dev", "price_pos"))]
        if ret_features:
            ret_centers = kmeans.cluster_centers_[:, ret_features].mean(axis=1)
            sorted_idx = np.argsort(ret_centers)  # 低→高: 熊市→震荡→牛市
            label_map = {sorted_idx[2]: 1, sorted_idx[1]: 0, sorted_idx[0]: 2}
        else:
            # 兜底：用范数排序
            norms = np.linalg.norm(kmeans.cluster_centers_, axis=1)
            sorted_idx = np.argsort(norms)
            label_map = {sorted_idx[2]: 1, sorted_idx[1]: 0, sorted_idx[0]: 2}

        mapped = np.array([label_map[l] for l in raw_labels])

        # 构建结果序列
        regime_series = []
        for i, d in enumerate(daily.index):
            regime = int(mapped[i])
            meta = REGIME_META.get(regime, {"label": "未知", "description": "", "color": "#999"})
            regime_series.append({
                "date": str(d),
                "regime": regime,
                "label": meta["label"],
                "color": meta["color"],
            })

        # 统计
        regimes_arr = np.array([r["regime"] for r in regime_series])
        counts = {regime: int(np.sum(regimes_arr == regime)) for regime in [0, 1, 2]}
        transitions = int(np.sum(regimes_arr[1:] != regimes_arr[:-1]))

        return {
            "analysis_type": "regime",
            "track_name": "all",
            "regimes": regime_series,
            "summary": {
                "total_dates": len(regime_series),
                "regime_distribution": {
                    REGIME_META[k]["label"]: v for k, v in counts.items() if v > 0
                },
                "num_transitions": transitions,
                "current_regime": regime_series[-1]["regime"] if regime_series else -1,
                "current_label": regime_series[-1]["label"] if regime_series else "未知",
                "regime_meta": REGIME_META,
            },
        }

    def _load_data(self) -> pd.DataFrame | None:
        """从预处理 parquet 加载数据"""
        try:
            val = pd.read_parquet(PREPROCESSED_DIR / "val.parquet")
            test = pd.read_parquet(PREPROCESSED_DIR / "test.parquet")
            df = pd.concat([val, test], ignore_index=True)
            logger.info(f"RegimeDetector: 加载 {len(df)} 行数据")
            return df
        except Exception as e:
            logger.error(f"RegimeDetector 数据加载失败: {e}")
            return None
