"""
赛道分类与标签系统 ORM 模型.

赛道 = Track = 个人选定的投资方向（半导体/AI/机器人/存储）
每个赛道包含多只股票，每只股票可属于多个赛道。
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text, Table
from sqlalchemy.orm import relationship

from app.db.database import Base


# ── 多对多关联表：赛道 <-> 股票 ────────────────
track_stock = Table(
    "track_stock",
    Base.metadata,
    Column("track_id", String(36), ForeignKey("tracks.id"), primary_key=True),
    Column("stock_code", String(20), ForeignKey("track_stocks.code"), primary_key=True),
)


class Track(Base):
    """赛道表"""

    __tablename__ = "tracks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(50), unique=True, nullable=False, index=True)  # semiconductor, ai, robot, storage
    display_name = Column(String(100), nullable=False)  # 半导体, AI, 机器人, 存储
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)  # 排序
    is_active = Column(Integer, default=1)  # 是否启用
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # 关系
    stocks = relationship("TrackStock", secondary=track_stock, back_populates="tracks")


class TrackStock(Base):
    """自选股池表 - 基础股票信息"""

    __tablename__ = "track_stocks"

    code = Column(String(20), primary_key=True)  # 000636.SZ
    name = Column(String(50), nullable=False)
    ipo_date = Column(String(10), nullable=True)
    status = Column(String(10), nullable=True)  # 上市状态
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # 关系
    tracks = relationship("Track", secondary=track_stock, back_populates="stocks")


class TrackDataCache(Base):
    """赛道数据缓存表 - 存储每只股票最新 N 日原始数据
    数据格式: CSV 7 列 (date,open,high,low,close,volume,amount)
    """

    __tablename__ = "track_data_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), ForeignKey("track_stocks.code"), index=True, nullable=False)
    trade_date = Column(String(10), nullable=False)  # YYYY-MM-DD
    open_px = Column(Float, default=0)
    high_px = Column(Float, default=0)
    low_px = Column(Float, default=0)
    close_px = Column(Float, default=0)
    volume = Column(Float, default=0)  # 成交量（股）
    amount = Column(Float, default=0)  # 成交额（元）
    is_stopped = Column(Integer, default=0)  # 是否停牌
    is_limit_up = Column(Integer, default=0)  # 是否涨停
    is_limit_down = Column(Integer, default=0)  # 是否跌停
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class FeatureWhiteList(Base):
    """因子白名单 - 经 Alphalens + LightGBM 双层筛选后的有效因子"""

    __tablename__ = "feature_white_list"

    id = Column(Integer, primary_key=True, autoincrement=True)
    factor_name = Column(String(100), unique=True, nullable=False)
    factor_type = Column(String(20), nullable=False)  # generic / track_specific
    category = Column(String(50), nullable=True)  # momentum / volatility / volume / etc.
    ic_mean = Column(Float, default=0)  # IC 均值
    ir = Column(Float, default=0)  # IR
    rank_ic = Column(Float, default=0)  # 秩 IC
    lgb_importance = Column(Float, default=0)  # LightGBM 特征重要性
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class FeatureBlackList(Base):
    """因子黑名单 - 统计无效或被 AI 淘汰的因子"""

    __tablename__ = "feature_black_list"

    id = Column(Integer, primary_key=True, autoincrement=True)
    factor_name = Column(String(100), unique=True, nullable=False)
    reason = Column(String(200), nullable=True)  # 淘汰原因: ic_too_low / ir_too_low / not_monotonic / lgb_importance_zero
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class FeatureStore(Base):
    """特征存储 - 每只股票每日的特征 JSON"""

    __tablename__ = "feature_store"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False, index=True)
    trade_date = Column(String(10), nullable=False)
    features = Column(JSON, nullable=False)  # {"mom_1d": 0.02, "ma_dev_5d": -0.01, ...}
    feature_version = Column(String(20), default="v1")  # 特征版本
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ScoreHistory(Base):
    """评分历史表 - 每次训练的模型评分结果"""

    __tablename__ = "score_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    track_name = Column(String(50), nullable=False, index=True)
    model_id = Column(String(100), nullable=False)
    stock_code = Column(String(20), nullable=False)
    stock_name = Column(String(50), nullable=True)
    score = Column(Float, default=0)
    rank = Column(Integer, default=0)
    train_r2 = Column(Float, default=0)  # 训练 R²
    val_r2 = Column(Float, default=0)  # 验证 R²
    test_r2 = Column(Float, default=0)  # 测试 R²
    params_snapshot = Column(JSON, nullable=True)  # 训练参数快照
    scored_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class FeatureConfig(Base):
    """特征配置表 - 特征的定义/释义/参数/启用状态"""

    __tablename__ = "feature_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    feature_name = Column(String(100), unique=True, nullable=False, index=True)  # rsi_6, sma_5 等
    display_name = Column(String(100), nullable=False, default="")  # 中文名: "6日RSI"
    category = Column(String(50), nullable=True)  # momentum / trend / volatility / volume / statistical / track_specific
    description = Column(Text, nullable=True)  # 大白话释义
    formula = Column(Text, nullable=True)  # 计算公式
    interpretation = Column(Text, nullable=True)  # 解读方法
    default_params = Column(JSON, nullable=True)  # 默认参数 {"window": 14}
    is_enabled = Column(Integer, default=1)  # 是否启用
    is_user_defined = Column(Integer, default=0)  # 用户自定义标记
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class UnsupervisedResult(Base):
    """无监督学习分析结果表 - 市场状态/因子降维/异常检测"""

    __tablename__ = "unsupervised_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_type = Column(String(20), nullable=False, index=True)  # regime / pca / anomaly / daily_report
    track_name = Column(String(50), nullable=True)  # 赛道名，pca/全市场时为空
    result_date = Column(String(10), nullable=False)  # 分析运行日期
    payload = Column(JSON, nullable=False)  # 分析结果 JSON
    params_snapshot = Column(JSON, nullable=True)  # 分析参数快照
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Recommendation(Base):
    """推荐记录表 - 每日推荐 + 次日复盘评分"""

    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False, index=True)
    stock_name = Column(String(50), nullable=True)
    rec_date = Column(String(10), nullable=False)  # 推荐日期
    buy_price_range = Column(String(50), nullable=True)  # 建议买入区间: "15.20-15.80"
    target_price = Column(Float, nullable=True)  # 目标价
    stop_loss = Column(Float, nullable=True)  # 止损价
    reasoning = Column(Text, nullable=True)  # 推荐理由
    status = Column(String(20), default="pending")  # pending / reviewed
    review_result = Column(String(20), nullable=True)  # GOOD / BAD / MISSED
    actual_performance = Column(Float, nullable=True)  # 实际收益%
    review_date = Column(String(10), nullable=True)  # 复盘日期
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Prediction(Base):
    """AI预测记录表 - 每次分析的快照 + 复盘追踪"""

    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False, index=True)
    stock_name = Column(String(50), nullable=True)
    overall_rating = Column(String(5), nullable=True)
    action = Column(String(10), nullable=True)
    opportunity_score = Column(Float, default=0)
    risk_score = Column(Float, default=0)
    suggested_buy = Column(String(50), nullable=True)
    target_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    analysis_snapshot = Column(JSON, nullable=True)
    status = Column(String(20), default="pending")
    review_result = Column(String(20), nullable=True)
    actual_return = Column(Float, nullable=True)
    review_date = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PipelineRun(Base):
    """流水线运行记录 - 每次训练/回测的日志"""

    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_type = Column(String(20), nullable=False, index=True)  # train / backtest
    status = Column(String(20), nullable=False, default="success")  # success / failed
    params_snapshot = Column(JSON, nullable=True)  # 使用的参数
    results_summary = Column(JSON, nullable=True)  # 结果摘要
    git_commit_hash = Column(String(40), nullable=True)  # Git commit
    feature_count = Column(Integer, nullable=True)  # 特征数
    duration_seconds = Column(Float, nullable=True)  # 耗时
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
