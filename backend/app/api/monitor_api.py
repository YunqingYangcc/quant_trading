"""
板块龙头监控 + 明日推荐 API.

GET /api/v1/monitor/leaders   — 板块龙头列表(含实时涨跌)
GET /api/v1/monitor/recommend — 明日推荐买入
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import sqlite3
from fastapi import APIRouter

router = APIRouter()
logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "configs"
DB_PATH = Path(__file__).resolve().parent.parent.parent / "track_quant.db"


def _load_leaders() -> list[dict]:
    with open(CONFIG_DIR / "sector_leaders.json", encoding="utf-8") as f:
        return json.load(f)


def _get_today_prices(codes: list[str]) -> dict:
    """从 DB 获取最新收盘价和涨跌幅"""
    result = {}
    try:
        conn = sqlite3.connect(str(DB_PATH))
        for code in codes:
            cursor = conn.execute(
                "SELECT close_px, trade_date FROM track_data_cache WHERE stock_code=? ORDER BY trade_date DESC LIMIT 2",
                (code,)
            )
            rows = cursor.fetchall()
            if len(rows) >= 2:
                today, yesterday = rows[0][0], rows[1][0]
                if today and yesterday and yesterday > 0:
                    change_pct = round((today - yesterday) / yesterday * 100, 2)
                else:
                    change_pct = 0
                result[code] = {"price": today, "change_pct": change_pct, "date": rows[0][1]}
            elif len(rows) == 1:
                result[code] = {"price": rows[0][0], "change_pct": 0, "date": rows[0][1]}
            else:
                result[code] = {"price": 0, "change_pct": 0, "date": ""}
        conn.close()
    except Exception as e:
        logger.warning(f"获取价格失败: {e}")
    return result


@router.get("/monitor/leaders", summary="板块龙头监控")
async def get_leaders():
    """返回板块龙头列表，含实时涨跌幅。"""
    leaders = _load_leaders()
    codes = list(set(l["code"] for l in leaders))
    prices = _get_today_prices(codes)

    # 按赛道分组
    grouped: dict[str, list[dict]] = {}
    for l in leaders:
        p = prices.get(l["code"], {})
        entry = {
            **l,
            "price": p.get("price", 0),
            "change_pct": p.get("change_pct", 0),
            "date": p.get("date", ""),
        }
        grouped.setdefault(l["track"], []).append(entry)

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total_stocks": len(leaders),
        "total_tracks": len(grouped),
        "groups": [
            {"track": k, "stocks": v} for k, v in grouped.items()
        ],
    }


@router.get("/monitor/recommend", summary="明日推荐买入")
async def get_recommend():
    """基于 AI 分析结果生成明日推荐买入列表。"""
    import pandas as pd
    from pathlib import Path

    PREPROCESSED_DIR = Path(__file__).resolve().parent.parent.parent / "ml" / "preprocessed"
    MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "ml" / "models"

    leaders = _load_leaders()
    try:
        test_df = pd.read_parquet(PREPROCESSED_DIR / "test.parquet")
        with open(PREPROCESSED_DIR / "feature_cols.json") as f:
            feature_cols = json.load(f)
    except Exception:
        return {"message": "数据不可用，请先运行流水线", "recommendations": []}

    import joblib
    recommendations = []

    for l in leaders:
        stock_data = test_df[test_df["stock_code"] == l["code"]]
        if len(stock_data) == 0:
            continue

        latest = stock_data.iloc[-1]

        # 用对应赛道模型打分
        track_name = None
        for t in ["semiconductor", "ai-power", "ai", "robot", "storage", "material"]:
            if t in l["track"].lower().replace("（", "").replace("）", "") or t in l["track"].split("(")[0] if "(" in l["track"] else False:
                track_name = t
                break
        if not track_name:
            track_name = "semiconductor"

        model_path = MODELS_DIR / f"{track_name}.pkl"
        if not model_path.exists():
            continue

        try:
            model = joblib.load(model_path)
            X = latest[feature_cols].fillna(0).values.reshape(1, -1)
            score = float(model.predict_proba(X)[0][1])
        except Exception:
            continue

        if score > 0.5:
            recommendations.append({
                "name": l["name"],
                "code": l["code"],
                "track": l["track"],
                "segment": l["segment"],
                "position": l["position"],
                "score": round(score, 4),
            })

    recommendations.sort(key=lambda x: x["score"], reverse=True)

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "count": len(recommendations),
        "recommendations": recommendations[:10],
    }
