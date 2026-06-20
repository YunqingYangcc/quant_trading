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
        ("688012.SH", "中微公司"), ("000636.SZ", "风华高科"),
        ("600183.SH", "生益科技"), ("600703.SH", "三安光电"),
        ("603986.SH", "兆易创新"), ("603501.SH", "韦尔股份"),
        ("002049.SZ", "紫光国微"), ("688396.SH", "华润微"),
        ("300782.SZ", "卓胜微"), ("300661.SZ", "圣邦股份"),
        ("688126.SH", "沪硅产业"), ("600584.SH", "长电科技"),
        ("300604.SZ", "长川科技"), ("688728.SH", "格科微"),
        ("600745.SH", "闻泰科技"),
    ],
    "ai": [
        ("300308.SZ", "中际旭创"), ("601138.SH", "工业富联"),
        ("688041.SH", "海光信息"), ("300502.SZ", "新易盛"),
        ("002281.SZ", "光迅科技"), ("688256.SH", "寒武纪"),
        ("603019.SH", "中科曙光"), ("000977.SZ", "浪潮信息"),
        ("300394.SZ", "天孚通信"), ("603083.SH", "剑桥科技"),
        ("000988.SZ", "华工科技"), ("002230.SZ", "科大讯飞"),
        ("688498.SZ", "源杰科技"),
    ],
    "robot": [
        ("300124.SZ", "汇川技术"), ("688017.SH", "绿的谐波"),
        ("002472.SZ", "双环传动"), ("688160.SH", "步科股份"),
        ("002896.SZ", "中大力德"), ("002747.SZ", "埃斯顿"),
        ("300607.SZ", "拓斯达"), ("688320.SH", "禾川科技"),
        ("300161.SZ", "华中数控"), ("000837.SZ", "秦川机床"),
        ("300503.SZ", "昊志机电"), ("301368.SZ", "丰立智能"),
    ],
    "storage": [
        ("603986.SH", "兆易创新"), ("300223.SZ", "北京君正"),
        ("688008.SH", "澜起科技"), ("002185.SZ", "华天科技"),
        ("600584.SH", "长电科技"), ("301308.SZ", "江波龙"),
        ("688110.SH", "东芯股份"), ("688525.SH", "佰维存储"),
        ("001309.SZ", "德明利"), ("688766.SH", "普冉股份"),
        ("688123.SH", "聚辰股份"),
    ],
    "material": [
        ("688019.SH", "安集科技"), ("300054.SZ", "鼎龙股份"),
        ("002409.SZ", "雅克科技"), ("300346.SZ", "南大光电"),
        ("300236.SZ", "上海新阳"), ("605358.SH", "立昂微"),
        ("002129.SZ", "TCL中环"), ("300567.SZ", "精测电子"),
    ],
    "ai-power": [
        ("002837.SZ", "英维克"), ("002335.SZ", "科华数据"),
        ("600406.SH", "国电南瑞"), ("600900.SH", "长江电力"),
        ("601985.SH", "中国核电"), ("300274.SZ", "阳光电源"),
        ("688676.SH", "金盘科技"), ("300737.SZ", "科创新源"),
    ],
}

TRACK_DISPLAY = {
    "semiconductor": "半导体", "ai": "AI", "robot": "机器人",
    "storage": "存储", "material": "上游材料", "ai-power": "电力AI",
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
