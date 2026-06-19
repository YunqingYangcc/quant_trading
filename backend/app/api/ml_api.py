"""AI 机器学习 API（骨架，Phase E 填充）"""
import logging
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/ml/train/{track_name}", summary="训练赛道模型")
async def train_track_model(track_name: str):
    """触发指定赛道的 LightGBM 训练（Phase E 实现）"""
    return {
        "message": f"Training endpoint for {track_name}",
        "status": "not_implemented_yet",
        "phase": "E",
    }


@router.get("/ml/score/{track_name}", summary="获取赛道打分")
async def get_track_score(track_name: str):
    """获取赛道内个股 AI 强弱分（Phase F 实现）"""
    return {
        "track_name": track_name,
        "message": "Scoring endpoint ready. Implementation in Phase F.",
        "scores": [],
    }


@router.get("/ml/models/{track_name}", summary="列出赛道模型")
async def list_models(track_name: str):
    """列出赛道已训练模型"""
    return {"track_name": track_name, "models": []}
