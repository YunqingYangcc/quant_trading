"""无监督学习分析模块。

提供三种无监督分析能力：
1. 市场状态聚类 (RegimeDetector) — KMeans 将市场分为牛市/熊市/震荡
2. 因子降维 (PCAAnalyzer) — PCA 分析因子结构和冗余
3. 异常检测 (AnomalyDetector) — IsolationForest 发现异动股票
"""

from app.ml.unsupervised.regime_detector import RegimeDetector
from app.ml.unsupervised.pca_analyzer import PCAAnalyzer
from app.ml.unsupervised.anomaly_detector import AnomalyDetector

__all__ = ["RegimeDetector", "PCAAnalyzer", "AnomalyDetector"]
