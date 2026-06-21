#!/usr/bin/env python3
"""
每日数据更新：拉取最新行情 → 导入数据库

用法:
    cd /path/to/track_quant
    python3 scripts/daily_update.py
"""
import asyncio
import csv
import logging
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "backend"))

# 拉取最新数据（用已有脚本）
def fetch_data():
    """调用 fetch_track_data 拉取最新 CSV"""
    from importlib.util import spec_from_file_location, module_from_spec
    path = str(BASE / "scripts" / "fetch_track_data.py")
    spec = spec_from_file_location("fetch_track_data", path)
    if not spec or not spec.loader:
        log.error("无法加载 fetch_track_data.py")
        return
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    log.info("=== 开始拉取数据 ===")
    mod.main()
    log.info("=== 拉取完成 ===")

# 导入数据库
async def import_to_db():
    from app.db.database import async_session_maker
    from app.models.track import TrackDataCache, TrackStock, track_stock
    from sqlalchemy import select, delete as d

    # 读取 universe.csv 获取完整股票列表
    stocks = []
    with open(BASE / "datas" / "universe.csv") as f:
        for row in csv.DictReader(f):
            stocks.append((row["code"], row["name"], row["track"]))

    async with async_session_maker() as session:
        existing = {r[0] for r in (await session.execute(select(TrackStock.code))).all()}

        new_stocks = 0
        for code, name, track in stocks:
            if code not in existing:
                session.add(TrackStock(code=code, name=name))
                existing.add(code)
                new_stocks += 1

            # 赛道关联
            from app.models.track import Track
            tr = await session.execute(select(Track.id).where(Track.name == track))
            tid = tr.scalar_one_or_none()
            if tid:
                rel = await session.execute(
                    select(track_stock).where(
                        track_stock.c.stock_code == code,
                        track_stock.c.track_id == tid,
                    )
                )
                if not rel.first():
                    await session.execute(
                        track_stock.insert().values(track_id=tid, stock_code=code)
                    )

        await session.flush()

        # 读取每个 CSV，用 UPSERT 方式写入最新数据
        # 策略：先删该股最新一天的数据（如果有），再写入新数据
        total = 0
        for code, name, track in stocks:
            csv_path = BASE / "datas" / "tracks" / track / f"{code}.csv"
            if not csv_path.exists():
                continue

            with open(csv_path, encoding="utf-8") as f:
                reader = list(csv.DictReader(f))
                if not reader:
                    continue

            # 取 CSV 最新一条（最后一行）
            last = reader[-1]
            try:
                latest_date = last["date"]
                # 检查数据库中是否已有该日数据
                exist = await session.execute(
                    select(TrackDataCache.id)
                    .where(TrackDataCache.stock_code == code)
                    .where(TrackDataCache.trade_date == latest_date)
                )
                if exist.first():
                    continue  # 已有今日数据，跳过

                # 写入新数据
                for row in reader:
                    # 只导入当天的数据（提高效率）
                    if row["date"] == latest_date:
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
                        total += 1
                        break  # 一天只有一条
            except (ValueError, KeyError):
                continue

        await session.commit()
        log.info(f"数据更新完毕: 新增 {new_stocks} 只股票, {total} 条日线")

        # 小白后的生成标签
        from app.services.track_service import TrackService
        service = TrackService()
        for code, _, _ in stocks:
            try:
                await service.generate_labels(code)
            except Exception as e:
                log.warning(f"  {code} 标签生成失败: {e}")

async def main():
    start = datetime.now()
    log.info("=" * 60)
    log.info("每日数据更新开始")
    log.info(f"时间: {start.strftime('%Y-%m-%d %H:%M')}")

    # Step 1: 拉取数据
    fetch_data()

    # Step 2: 导入数据库
    log.info("=== 导入数据库 ===")
    await import_to_db()

    elapsed = (datetime.now() - start).total_seconds()
    log.info(f"完成! 耗时 {elapsed:.0f} 秒")

if __name__ == "__main__":
    asyncio.run(main())
