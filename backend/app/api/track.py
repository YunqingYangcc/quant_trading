"""
赛道管理 API 路由.

管理赛道 CRUD、自选股池、标签数据查询。
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status


from app.schemas.track import (
    StockTrackAssign,
    TrackCreate,
    TrackListResponse,
    TrackResponse,
    TrackUpdate,
)
from app.services.track_service import TrackService

logger = logging.getLogger(__name__)

router = APIRouter()


def get_track_service():
    return TrackService()


# ── 赛道 CRUD ──────────────────────────────────────


@router.get("/tracks", response_model=TrackListResponse, summary="列出所有赛道")
async def list_tracks(
    service: TrackService = Depends(get_track_service),

):
    items = await service.list_tracks()
    return TrackListResponse(total=len(items), items=items)


@router.post("/tracks", response_model=TrackResponse, summary="创建赛道")
async def create_track(
    data: TrackCreate,
    service: TrackService = Depends(get_track_service),

):
    track = await service.create_track(data)
    result = await service.get_track(track.id)
    if not result:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return result


@router.get("/tracks/{track_id}", response_model=TrackResponse, summary="获取赛道详情")
async def get_track(
    track_id: str,
    service: TrackService = Depends(get_track_service),

):
    result = await service.get_track(track_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return result


@router.put("/tracks/{track_id}", summary="更新赛道")
async def update_track(
    track_id: str,
    data: TrackUpdate,
    service: TrackService = Depends(get_track_service),

):
    ok = await service.update_track(track_id, data)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return {"message": "Updated"}


@router.delete("/tracks/{track_id}", summary="删除赛道")
async def delete_track(
    track_id: str,
    service: TrackService = Depends(get_track_service),

):
    ok = await service.delete_track(track_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return {"message": "Deleted"}


# ── 自选股管理 ──────────────────────────────────────


@router.post("/stocks/assign", summary="股票分配赛道")
async def assign_stock(
    data: StockTrackAssign,
    service: TrackService = Depends(get_track_service),

):
    ok = await service.assign_stock_to_tracks(
        data.stock_code, data.stock_name, data.track_ids
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    return {"message": "Assigned"}


@router.get("/stocks", summary="列出自选股")
async def list_stocks(
    track_id: str | None = Query(None, description="按赛道筛选"),
    service: TrackService = Depends(get_track_service),

):
    return await service.list_stocks(track_id)


# ── 标签数据 ──────────────────────────────────────


@router.get("/labels/{stock_code}", summary="获取带标签的日线数据")
async def get_labels(
    stock_code: str,
    service: TrackService = Depends(get_track_service),

):
    try:
        labels = await service.generate_labels(stock_code)
        return {"stock_code": stock_code, "data_points": labels, "total": len(labels)}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error("generate_labels failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ── 因子黑白名单 ──────────────────────────────────────


@router.get("/factors/whitelist", summary="因子白名单")
async def get_whitelist(
    service: TrackService = Depends(get_track_service),

):
    return await service.get_whitelist()


@router.get("/factors/blacklist", summary="因子黑名单")
async def get_blacklist(
    service: TrackService = Depends(get_track_service),

):
    return await service.get_blacklist()
