#!/usr/bin/env python3
"""
增量数据更新脚本：只拉取最近 30 天数据，合并到已有 CSV 中。
再自动导入到 SQLite 数据库。

用法:
  python scripts/update_data.py                    # 更新所有赛道
  python scripts/update_data.py --tracks ai robot  # 只更新指定赛道
  python scripts/update_data.py --codes 000636.SZ  # 只更新指定股票
"""

import argparse
import csv
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATAS_DIR = PROJECT_ROOT / "datas"
TRACKS_DIR = DATAS_DIR / "tracks"

UNIVERSE = {
    "semiconductor": [
        ("688981.SH", "中芯国际"), ("002371.SZ", "北方华创"),
        ("688012.SH", "中微公司"), ("000636.SZ", "风华高科"),
        ("600183.SH", "生益科技"), ("600703.SH", "三安光电"),
        ("603986.SH", "兆易创新"), ("603501.SH", "韦尔股份"),
        ("002049.SZ", "紫光国微"), ("688396.SH", "华润微"),
        ("300782.SZ", "卓胜微"), ("300661.SZ", "圣邦股份"),
        ("688126.SH", "沪硅产业"), ("600584.SH", "长电科技"),
        ("300604.SZ", "长川科技"), ("688728.SH", "格科微"),
        ("600745.SH", "闻泰科技"),
        ("300567.SZ", "精测电子"),
        ("603290.SH", "斯达半导"), ("600460.SH", "士兰微"),
        ("002156.SZ", "通富微电"), ("688072.SH", "拓荆科技"),
    ],
    "ai": [
        ("300308.SZ", "中际旭创"), ("601138.SH", "工业富联"),
        ("688041.SH", "海光信息"), ("300502.SZ", "新易盛"),
        ("002281.SZ", "光迅科技"), ("688256.SH", "寒武纪"),
        ("603019.SH", "中科曙光"), ("000977.SZ", "浪潮信息"),
        ("300394.SZ", "天孚通信"), ("603083.SH", "剑桥科技"),
        ("000988.SZ", "华工科技"), ("002230.SZ", "科大讯飞"),
        ("688111.SH", "金山办公"), ("300418.SZ", "昆仑万维"),
    ],
    "robot": [
        ("300124.SZ", "汇川技术"), ("688017.SH", "绿的谐波"),
        ("002472.SZ", "双环传动"), ("688160.SH", "步科股份"),
        ("002896.SZ", "中大力德"), ("002747.SZ", "埃斯顿"),
        ("300607.SZ", "拓斯达"), ("688320.SH", "禾川科技"),
        ("300161.SZ", "华中数控"), ("000837.SZ", "秦川机床"),
        ("300503.SZ", "昊志机电"), ("301368.SZ", "丰立智能"),
        ("300024.SZ", "机器人"), ("002979.SZ", "雷赛智能"),
    ],
    "storage": [
        ("603986.SH", "兆易创新"), ("300223.SZ", "北京君正"),
        ("688008.SH", "澜起科技"), ("002185.SZ", "华天科技"),
        ("600584.SH", "长电科技"), ("301308.SZ", "江波龙"),
        ("688110.SH", "东芯股份"), ("688525.SH", "佰维存储"),
        ("001309.SZ", "德明利"), ("688766.SH", "普冉股份"),
        ("688123.SH", "聚辰股份"),
        ("000021.SZ", "深科技"),
    ],
    "material": [
        ("688019.SH", "安集科技"), ("300054.SZ", "鼎龙股份"),
        ("002409.SZ", "雅克科技"), ("300346.SZ", "南大光电"),
        ("300236.SZ", "上海新阳"), ("605358.SH", "立昂微"),
        ("002129.SZ", "TCL中环"),
        ("300666.SZ", "江丰电子"),
        ("603690.SH", "至纯科技"),
        ("688596.SH", "正帆科技"),
        ("688106.SH", "金宏气体"),
        ("300316.SZ", "晶盛机电"),
        ("688126.SH", "沪硅产业"),
        ("688268.SH", "华特气体"),
    ],
    "ai-power": [
        ("002837.SZ", "英维克"), ("002335.SZ", "科华数据"),
        ("600406.SH", "国电南瑞"), ("600900.SH", "长江电力"),
        ("601985.SH", "中国核电"), ("300274.SZ", "阳光电源"),
        ("688676.SH", "金盘科技"), ("300737.SZ", "科创新源"),
        ("002518.SZ", "科士达"),
        ("603912.SH", "佳力图"),
        ("300286.SZ", "安科瑞"),
        ("300693.SZ", "盛弘股份"),
        ("600995.SH", "南网储能"),
        ("000400.SZ", "许继电气"), ("601126.SH", "四方股份"),
        ("002028.SZ", "思源电气"),
    ],
}

BAOSTOCK_FIELDS = "date,open,high,low,close,volume,amount"
CSV_HEADER = ["date", "open", "high", "low", "close", "volume", "amount"]
MAX_RETRIES = 3
_last_req_time = 0.0


def rate_limit():
    global _last_req_time
    elapsed = time.time() - _last_req_time
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    _last_req_time = time.time()


def to_bs_code(code: str) -> str:
    sym, market = code.split(".")
    return f"{market.lower()}.{sym}"


def get_latest_date_in_csv(filepath: Path) -> str | None:
    """读取 CSV 中最后一条日期"""
    if not filepath.exists():
        return None
    with open(filepath, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        last_date = None
        for row in reader:
            last_date = row["date"]
    return last_date


def merge_csv(existing_path: Path, new_rows: list[list[str]]) -> int:
    """合并新数据到已有 CSV，去重（按 date），返回净增条数"""
    existing = {}
    if existing_path.exists():
        with open(existing_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing[row["date"]] = [
                    row["date"], row["open"], row["high"], row["low"],
                    row["close"], row["volume"], row["amount"],
                ]

    added = 0
    for row in new_rows:
        if row[0] not in existing:
            existing[row[0]] = row
            added += 1

    sorted_dates = sorted(existing.keys())
    with open(existing_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        for d in sorted_dates:
            writer.writerow(existing[d])

    return added


def fetch_stock_incremental(code: str, name: str, track_dir: Path, days: int = 30) -> bool:
    """增量拉取某只股票最近 days 天的数据，合并到已有 CSV"""
    import baostock as bs

    filepath = track_dir / f"{code}.csv"

    # 已有 CSV 的最新日期
    latest_date = get_latest_date_in_csv(filepath)
    today = datetime.now()
    yesterday = today - timedelta(days=1)

    if latest_date:
        latest = datetime.strptime(latest_date, "%Y-%m-%d")
        # 如果已经包含昨天数据，跳过
        if latest >= yesterday - timedelta(days=1):
            logger.info("  %s (%s): 已是最新 (最新=%s), 跳过", code, name, latest_date)
            return True

    # 从 latest_date 次日 or days 天前 开始拉
    if latest_date:
        start_date = (datetime.strptime(latest_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")

    end_date = yesterday.strftime("%Y-%m-%d")

    bs_code = to_bs_code(code)

    for attempt in range(1, MAX_RETRIES + 1):
        rate_limit()
        lg = bs.login()
        if lg.error_code != "0":
            logger.error("  %s (%s): login failed (attempt %d/%d)", code, name, attempt, MAX_RETRIES)
            bs.logout()
            time.sleep(2.0)
            continue

        try:
            rs = bs.query_history_k_data_plus(
                bs_code,
                BAOSTOCK_FIELDS,
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="2",
            )

            rows = []
            while rs.next():
                row = rs.get_row_data()
                if row[0] and not row[0].startswith("20"):
                    continue  # 跳过非日期行（如空行）
                if row[0] and row[0] >= (start_date if latest_date else "2000-01-01"):
                    rows.append(row)

            if not rows:
                logger.info("  %s (%s): 无新数据 (%s ~ %s)", code, name, start_date, end_date)
                return True

            added = merge_csv(filepath, rows)
            logger.info("  %s (%s): 新增 %d 条 (%s ~ %s)", code, name, added, start_date, end_date)
            return True

        except Exception as e:
            logger.error("  %s (%s): 异常 (attempt %d/%d) — %s", code, name, attempt, MAX_RETRIES, e)
            time.sleep(2.0)
        finally:
            bs.logout()

    logger.error("  %s (%s): 已重试 %d 次，放弃", code, name, MAX_RETRIES)
    return False


def import_to_db():
    """将 CSV 数据导入 SQLite"""
    import asyncio
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))

    async def _import():
        from app.db.database import async_session_maker, engine, Base
        from app.models.track import Track, TrackStock, TrackDataCache

        # 确保表存在
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with async_session_maker() as session:
            total = 0
            for track_name, stocks in UNIVERSE.items():
                for code, stock_name in stocks:
                    csv_path = TRACKS_DIR / track_name / f"{code}.csv"
                    if not csv_path.exists():
                        continue

                    # 清除该股票旧缓存
                    from sqlalchemy import delete
                    await session.execute(
                        delete(TrackDataCache).where(TrackDataCache.stock_code == code)
                    )

                    # 重新导入
                    count = 0
                    with open(csv_path, encoding="utf-8") as f:
                        for row in csv.DictReader(f):
                            try:
                                session.add(TrackDataCache(
                                    stock_code=code,
                                    trade_date=row["date"],
                                    open_px=float(row["open"]),
                                    high_px=float(row["high"]),
                                    low_px=float(row["low"]),
                                    close_px=float(row["close"]),
                                    volume=float(row["volume"]),
                                    amount=float(row["amount"]),
                                ))
                                count += 1
                            except (ValueError, KeyError):
                                continue

                    total += count
                    logger.info("  导入DB: %s (%s): %d 条", code, stock_name, count)

            await session.commit()
            logger.info("  DB导入完成: 共 %d 条", total)

    asyncio.run(_import())


def main():
    parser = argparse.ArgumentParser(description="增量更新赛道数据")
    parser.add_argument("--tracks", nargs="*", help="指定赛道名（如 ai robot），默认全部")
    parser.add_argument("--codes", nargs="*", help="指定股票代码（如 000636.SZ），默认全部")
    parser.add_argument("--days", type=int, default=30, help="拉取最近天数（默认 30）")
    parser.add_argument("--no-db", action="store_true", help="只更新 CSV，不导入数据库")
    args = parser.parse_args()

    track_names = args.tracks or list(UNIVERSE.keys())
    specific_codes = set(args.codes or [])

    logger.info("=" * 60)
    logger.info("增量更新赛道数据")
    logger.info("  天数: 最近 %d 天", args.days)
    logger.info("  赛道: %s", ", ".join(track_names))
    if specific_codes:
        logger.info("  股票: %s", ", ".join(specific_codes))

    ok = fail = 0
    for track_name in track_names:
        if track_name not in UNIVERSE:
            logger.warning("未知赛道: %s，跳过", track_name)
            continue

        stocks = UNIVERSE[track_name]
        track_dir = TRACKS_DIR / track_name
        track_dir.mkdir(parents=True, exist_ok=True)

        for code, name in stocks:
            if specific_codes and code not in specific_codes:
                continue
            if fetch_stock_incremental(code, name, track_dir, args.days):
                ok += 1
            else:
                fail += 1

    logger.info("=" * 60)
    logger.info("CSV 更新完成: 成功 %d / 失败 %d", ok, fail)

    if not args.no_db:
        logger.info("\n--- 导入数据库 ---")
        import_to_db()

    logger.info("全部完成!")


if __name__ == "__main__":
    main()
