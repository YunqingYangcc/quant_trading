"""
赛道分类与标签系统 Pydantic Schema.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── 赛道 ──────────────────────────────────────


class TrackCreate(BaseModel):
    name: str = Field(..., description="赛道标识名", examples=["semiconductor"])
    display_name: str = Field(..., description="赛道中文名", examples=["半导体"])
    description: str | None = None
    sort_order: int = 0


class TrackUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    sort_order: int | None = None
    is_active: int | None = None


class TrackStockInfo(BaseModel):
    code: str
    name: str
    ipo_date: str | None = None
    status: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TrackResponse(BaseModel):
    id: str
    name: str
    display_name: str
    description: str | None = None
    sort_order: int
    is_active: int
    stock_count: int = 0
    stocks: list[TrackStockInfo] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrackListResponse(BaseModel):
    total: int
    items: list[TrackResponse]


# ── 自选股 ──────────────────────────────────────


class StockTrackAssign(BaseModel):
    stock_code: str = Field(..., description="股票代码", examples=["000636.SZ"])
    stock_name: str = Field(..., description="股票名称", examples=["风华高科"])
    track_ids: list[str] = Field(..., description="所属赛道 ID 列表")


class StockResponse(BaseModel):
    code: str
    name: str
    ipo_date: str | None = None
    status: str | None = None
    tracks: list[str] = []  # track names
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── 因子白名单 / 黑名单 ──────────────────────


class FactorWhiteListResponse(BaseModel):
    id: int
    factor_name: str
    factor_type: str
    category: str | None = None
    ic_mean: float = 0
    ir: float = 0
    rank_ic: float = 0
    lgb_importance: float = 0
    is_active: int = 1
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FactorBlackListResponse(BaseModel):
    id: int
    factor_name: str
    reason: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── 数据标签 ──────────────────────────────────────


class LabeledDataPoint(BaseModel):
    """带标签的日线数据点"""
    stock_code: str
    trade_date: str
    open_px: float
    high_px: float
    low_px: float
    close_px: float
    volume: float
    amount: float
    is_stopped: bool
    is_limit_up: bool
    is_limit_down: bool
    # 未来收益标签（shift(1) 防止未来函数）
    fwd_1d_return: float | None = None
    fwd_5d_return: float | None = None
    fwd_20d_return: float | None = None
    fwd_1d_excess_return: float | None = None  # 超额收益（相对赛道中位数）
    fwd_5d_excess_return: float | None = None
    fwd_20d_excess_return: float | None = None


class LabeledDataResponse(BaseModel):
    stock_code: str
    stock_name: str
    track_names: list[str]
    data_points: list[LabeledDataPoint]
    total: int


# ── 回测参数 ──────────────────────────────────────


class TrainModelParams(BaseModel):
    """训练模型可配置参数（可选覆盖，不传则用默认值）"""
    num_leaves: int | None = Field(default=None, description="叶子节点数", ge=4, le=128)
    max_depth: int | None = Field(default=None, description="最大深度", ge=3, le=20)
    learning_rate: float | None = Field(default=None, description="学习率", gt=0, le=0.5)
    n_estimators: int | None = Field(default=None, description="迭代轮数", ge=100, le=5000)
    reg_alpha: float | None = Field(default=None, description="L1 正则", ge=0, le=10)
    reg_lambda: float | None = Field(default=None, description="L2 正则", ge=0, le=10)
    feature_fraction: float | None = Field(default=None, description="特征采样比例", gt=0, le=1)
    bagging_fraction: float | None = Field(default=None, description="样本采样比例", gt=0, le=1)
    min_child_samples: int | None = Field(default=None, description="叶节点最小样本", ge=5, le=200)


class ScoreHistoryResponse(BaseModel):
    """评分历史记录"""
    id: int
    track_name: str
    model_id: str
    stock_code: str
    stock_name: str | None = None
    score: float = 0
    rank: int = 0
    train_r2: float = 0
    val_r2: float = 0
    test_r2: float = 0
    params_snapshot: dict | None = None
    scored_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BacktestRunParams(BaseModel):
    """人工回测可配置参数"""
    initial_capital: int = Field(default=100000, description="初始资金", ge=10000)
    top_n: int = Field(default=3, description="每赛道买入 Top-N 只", ge=1, le=10)
    rebalance_freq: str = Field(default="W", description="调仓频率: W=周频, M=月频")
    max_single_stock: float = Field(default=0.20, description="单票上限", ge=0.05, le=0.50)
    max_single_track: float = Field(default=0.50, description="单赛道上限", ge=0.10, le=0.80)


class PipelineRunResponse(BaseModel):
    """流水线运行记录"""
    id: int
    run_type: str
    status: str
    params_snapshot: dict | None = None
    results_summary: dict | None = None
    git_commit_hash: str | None = None
    feature_count: int | None = None
    duration_seconds: float | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
