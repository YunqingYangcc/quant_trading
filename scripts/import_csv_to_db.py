#!/usr/bin/env python3
"""将 datas/tracks/ 下的 CSV 导入到 SQLite 数据库"""
import asyncio
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATAS_DIR = PROJECT_ROOT / "datas"
TRACKS_DIR = DATAS_DIR / "tracks"

sys.path.insert(0, str(PROJECT_ROOT / "backend"))

UNIVERSE = {
    "semiconductor": [
        ("688981.SH", "中芯国际"), ("002371.SZ", "北方华创"),
        ("688012.SH", "中微公司"), ("688256.SH", "寒武纪"),
        ("000636.SZ", "风华高科"), ("600183.SH", "生益科技"),
        ("600703.SH", "三安光电"), ("603986.SH", "兆易创新"),
    ],
    "ai": [
        ("300308.SZ", "中际旭创"), ("601138.SH", "工业富联"),
        ("688041.SH", "海光信息"), ("300502.SZ", "新易盛"),
        ("002281.SZ", "光迅科技"),
    ],
    "robot": [
        ("300124.SZ", "汇川技术"), ("688017.SH", "绿的谐波"),
        ("002472.SZ", "双环传动"), ("688160.SH", "步科股份"),
        ("002896.SZ", "中大力德"),
    ],
    "storage": [
        ("603986.SH", "兆易创新"), ("300223.SZ", "北京君正"),
        ("688008.SH", "澜起科技"), ("002185.SZ", "华天科技"),
        ("600584.SH", "长电科技"),
    ],
}

TRACK_DISPLAY = {
    "semiconductor": "半导体", "ai": "AI", "robot": "机器人", "storage": "存储",
}


async def main():
    from app.db.database import async_session_maker, engine, Base
    from app.models.track import Track, TrackStock, TrackDataCache, track_stock

    # 建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_maker() as session:
        # 1. 创建赛道
        track_objs = {}
        for i, (name, stocks) in enumerate(UNIVERSE.items()):
            t = Track(name=name, display_name=TRACK_DISPLAY[name], sort_order=i)
            session.add(t)
            await session.flush()
            track_objs[name] = t
            print(f"  赛道: {t.display_name} ({name})")

        # 2. 创建股票 + 关联
        all_stocks = {}
        for name, stocks in UNIVERSE.items():
            for code, stock_name in stocks:
                if code not in all_stocks:
                    s = TrackStock(code=code, name=stock_name)
                    session.add(s)
                    all_stocks[code] = s

                await session.execute(
                    track_stock.insert().values(
                        track_id=track_objs[name].id, stock_code=code
                    )
                )
        await session.flush()
        print(f"  股票: {len(all_stocks)} 只")

        # 3. 导入 CSV 数据
        total_rows = 0
        for name, stocks in UNIVERSE.items():
            for code, stock_name in stocks:
                csv_path = TRACKS_DIR / name / f"{code}.csv"
                if not csv_path.exists():
                    print(f"  [跳过] {csv_path}")
                    continue

                with open(csv_path, encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    rows = 0
                    for row in reader:
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
                            rows += 1
                        except (ValueError, KeyError):
                            continue

                total_rows += rows
                print(f"  {code} ({stock_name}): {rows} 条")

        await session.commit()
        print(f"\n完成! 导入 {total_rows} 条日线数据")


if __name__ == "__main__":
    asyncio.run(main())
