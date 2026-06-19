#!/usr/bin/env python3
"""
Phase 0: 赛道数据获取脚本

从 baostock 拉取 A 股日线行情（前复权），按赛道目录存储。
CSV 格式: date,open,high,low,close,volume,amount
数据范围: 上市首日 ~ 昨日
"""

import csv
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── 目录 ──────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATAS_DIR = PROJECT_ROOT / "datas"
TRACKS_DIR = DATAS_DIR / "tracks"

# ── 赛道股池定义 ──────────────────────────────
# 每个赛道：赛道名 → [(code, name), ...]
#
UNIVERSE = {
    "semiconductor": [
        ("688981.SH", "中芯国际"),
        ("002371.SZ", "北方华创"),
        ("688012.SH", "中微公司"),
        ("688256.SH", "寒武纪"),
        ("000636.SZ", "风华高科"),
        ("600183.SH", "生益科技"),
        ("600703.SH", "三安光电"),
        ("603986.SH", "兆易创新"),
    ],
    "ai": [
        ("300308.SZ", "中际旭创"),
        ("601138.SH", "工业富联"),
        ("688041.SH", "海光信息"),
        ("300502.SZ", "新易盛"),
        ("002281.SZ", "光迅科技"),
    ],
    "robot": [
        ("300124.SZ", "汇川技术"),
        ("688017.SH", "绿的谐波"),
        ("002472.SZ", "双环传动"),
        ("688160.SH", "步科股份"),
        ("002896.SZ", "中大力德"),
    ],
    "storage": [
        ("603986.SH", "兆易创新"),
        ("300223.SZ", "北京君正"),
        ("688008.SH", "澜起科技"),
        ("002185.SZ", "华天科技"),
        ("600584.SH", "长电科技"),
    ],
}

# CSV 列定义（baostock 字段映射）
BAOSTOCK_FIELDS = "date,open,high,low,close,volume,amount"
CSV_HEADER = ["date", "open", "high", "low", "close", "volume", "amount"]


# ── 频率控制 ──────────────────────────────────
REQ_INTERVAL = 1.0  # 每次请求间隔（秒），避免被 baostock 封 IP
MAX_RETRIES = 3      # 单只股票最大重试次数
_last_req_time = 0.0


def rate_limit():
    """请求频率控制：确保每次调用间隔至少 REQ_INTERVAL 秒"""
    global _last_req_time
    elapsed = time.time() - _last_req_time
    if elapsed < REQ_INTERVAL:
        sleep_sec = REQ_INTERVAL - elapsed
        logger.debug("  频率控制: sleep %.2fs", sleep_sec)
        time.sleep(sleep_sec)
    _last_req_time = time.time()


def to_bs_code(code: str) -> str:
    """A股代码转 baostock 格式: 000636.SZ → sz.000636"""
    sym, market = code.split(".")
    market = market.lower()
    return f"{market}.{sym}"


def fetch_stock(code: str, name: str, track_dir: Path) -> bool:
    """拉取单只股票日线，保存到 track_dir/{code}.csv（含频率控制 + 重试机制）"""
    bs_code = to_bs_code(code)
    filepath = track_dir / f"{code}.csv"

    for attempt in range(1, MAX_RETRIES + 1):
        # 频率控制：每次请求前等待
        rate_limit()

        import baostock as bs

        lg = bs.login()
        if lg.error_code != "0":
            logger.error("  %s (%s): login failed (attempt %d/%d) — %s",
                         code, name, attempt, MAX_RETRIES, lg.error_msg)
            bs.logout()
            time.sleep(2.0)
            continue

        try:
            end_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            rs = bs.query_history_k_data_plus(
                bs_code,
                BAOSTOCK_FIELDS,
                start_date="2000-01-01",
                end_date=end_date,
                frequency="d",
                adjustflag="2",  # 前复权
            )

            rows = []
            while rs.next():
                row = rs.get_row_data()
                if not row[0] or row[0].startswith("20"):
                    rows.append(row)

            if not rows:
                logger.warning("  %s (%s): 无数据 (attempt %d/%d)",
                               code, name, attempt, MAX_RETRIES)
                bs.logout()
                time.sleep(2.0)
                continue

            # 写入 CSV
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADER)
                writer.writerows(rows)

            logger.info("  %s (%s): %d 条记录 → %s", code, name, len(rows), filepath.name)
            return True

        except Exception as e:
            logger.error("  %s (%s): 异常 (attempt %d/%d) — %s",
                         code, name, attempt, MAX_RETRIES, e)
            time.sleep(2.0)
        finally:
            bs.logout()

    logger.error("  %s (%s): 已重试 %d 次，放弃", code, name, MAX_RETRIES)
    return False


def generate_universe_csv():
    """生成 universe.csv（全自选池索引）"""
    import baostock as bs

    lg = bs.login()
    if lg.error_code != "0":
        logger.error("universe: baostock login failed")
        return

    rows = []
    try:
        for track_name, stocks in UNIVERSE.items():
            for code, stock_name in stocks:
                rate_limit()  # 频率控制
                bs_code = to_bs_code(code)
                rs = bs.query_stock_basic(bs_code)
                ipo_date = ""
                status = ""
                if rs.next():
                    row_data = rs.get_row_data()
                    if row_data:
                        ipo_date = row_data[1] if len(row_data) > 1 else ""
                        status = row_data[2] if len(row_data) > 2 else ""
                rows.append([code, stock_name, track_name, ipo_date, status])
                logger.info("  universe: %s %s → %s", code, stock_name, track_name)

        universe_path = DATAS_DIR / "universe.csv"
        with open(universe_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["code", "name", "track", "ipo_date", "status"])
            writer.writerows(rows)
        logger.info("universe.csv 已生成: %d 条记录", len(rows))
    finally:
        bs.logout()


def main():
    import baostock as bs

    logger.info("=" * 60)
    logger.info("Phase 0: 赛道数据获取")
    logger.info("=" * 60)

    # Step 1: 拉取每只股票数据
    total_ok = 0
    total_fail = 0
    for track_name, stocks in UNIVERSE.items():
        track_dir = TRACKS_DIR / track_name
        track_dir.mkdir(parents=True, exist_ok=True)
        logger.info("\n--- %s (%d 只) ---", track_name, len(stocks))
        for code, name in stocks:
            ok = fetch_stock(code, name, track_dir)
            if ok:
                total_ok += 1
            else:
                total_fail += 1

    # Step 2: 生成 universe.csv
    logger.info("\n--- 生成 universe.csv ---")
    generate_universe_csv()

    # Step 3: 汇总
    logger.info("\n" + "=" * 60)
    logger.info("完成! 成功 %d / 失败 %d", total_ok, total_fail)
    logger.info("赛道目录: %s", TRACKS_DIR)
    logger.info("索引文件: %s", DATAS_DIR / "universe.csv")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
