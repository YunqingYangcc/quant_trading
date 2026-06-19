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
