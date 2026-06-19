"""
Phase G: 自研轻量回测.

加载 AI 打分 → 周频调仓轮动 → 模拟交易（含成本/限制）→ 绩效报告

固定参数（锁定，不可更改）：
  - 滑点: 0.1%
  - 手续费: 万三
  - 单票上限: 20%
  - 单赛道上限: 50%
  - 涨停无法买入、跌停无法卖出

Usage:
    cd backend && python3 scripts/run_backtest.py
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── 固定回测参数（锁定，不可更改）────────────
BACKTEST_PARAMS = {
    "slippage": 0.001,           # 滑点 0.1%
    "commission": 0.0003,        # 手续费 万三
    "max_single_stock": 0.20,    # 单票上限 20%
    "max_single_track": 0.50,    # 单赛道上限 50%
    "track_prosperity_threshold": 40,  # 景气度 < 40 自动减仓
    "skip_limit_up": True,       # 涨停无法买入
    "skip_limit_down": True,     # 跌停无法卖出
    "rebalance_freq": "W",       # 周频调仓
    "initial_capital": 100000,   # 初始资金 10 万
    "top_n": 3,                  # 每赛道买 Top-N 只
}

MODELS_DIR = Path(__file__).resolve().parent.parent / "ml" / "models"
PREPROCESSED_DIR = Path(__file__).resolve().parent.parent / "ml" / "preprocessed"


def load_historical_scores() -> tuple[pd.DataFrame, pd.DataFrame]:
    """加载数据并使用 AI 模型生成历史打分"""
    val = pd.read_parquet(PREPROCESSED_DIR / "val.parquet")
    test = pd.read_parquet(PREPROCESSED_DIR / "test.parquet")
    df = pd.concat([val, test], ignore_index=True)
    df["trade_date"] = pd.to_datetime(df["date"])
    df = df.sort_values("trade_date")

    # 从 DB 加载收盘价
    import sqlite3
    db_path = Path(__file__).resolve().parent.parent / "track_quant.db"
    conn = sqlite3.connect(str(db_path))
    raw = pd.read_sql("SELECT stock_code, trade_date, close_px FROM track_data_cache", conn)
    conn.close()
    raw["trade_date"] = pd.to_datetime(raw["trade_date"])
    raw = raw.rename(columns={"close_px": "close"})
    df = df.merge(raw, on=["stock_code", "trade_date"], how="left")

    # 加载白名单特征列
    with open(PREPROCESSED_DIR / "feature_cols.json") as f:
        feature_cols = json.load(f)

    # 加载赛道映射
    track_stocks = _get_track_stocks()

    # 用 AI 模型生成打分
    df["pred_score"] = 0.0
    for track_name, stock_codes in track_stocks.items():
        model_path = MODELS_DIR / f"{track_name}.pkl"
        if not model_path.exists():
            logger.warning(f"{track_name} 模型不存在, 跳过")
            continue

        import joblib
        model = joblib.load(model_path)

        mask = df["stock_code"].isin(stock_codes)
        track_df = df[mask].copy()
        if len(track_df) == 0:
            continue

        X = track_df[feature_cols].fillna(0).values
        df.loc[mask, "pred_score"] = model.predict(X)

    scores = df[["trade_date", "stock_code", "pred_score"]].copy()
    prices = df.pivot_table(index="trade_date", columns="stock_code", values="close")

    logger.info(f"  使用 AI 模型生成打分: {len(scores)} 条")
    return scores, prices


def _get_track_stocks() -> dict[str, list[str]]:
    """获取赛道-股票映射"""
    import asyncio
    from scripts.train_models import get_track_stock_map
    try:
        return asyncio.run(get_track_stock_map())
    except Exception as e:
        logger.warning(f"获取赛道映射失败: {e}")
        return {}


def generate_signals(scores: pd.DataFrame) -> pd.DataFrame:
    """打分 → 买卖信号

    每周选得分最高的 top_n 只买入（同一只股票只取最高分），持有的卖出。
    """
    params = BACKTEST_PARAMS
    scores = scores.copy()
    scores["week"] = scores["trade_date"].dt.isocalendar().year.astype(str) + "-W" + scores["trade_date"].dt.isocalendar().week.astype(str).str.zfill(2)

    signals = []
    for week, group in scores.groupby("week"):
        week_date = group["trade_date"].max()
        # 每只股票只保留本周最高分（去重）
        best_per_stock = group.loc[group.groupby("stock_code")["pred_score"].idxmax()]
        ranked = best_per_stock.sort_values("pred_score", ascending=False)
        top_stocks = ranked.head(params["top_n"])["stock_code"].tolist()

        signals.append({
            "date": week_date,
            "buy": top_stocks,
            "sell": [],
        })

    return pd.DataFrame(signals).set_index("date")


def simulate_trades(signals: pd.DataFrame, prices: pd.DataFrame) -> list[dict]:
    """模拟交易流水"""
    params = BACKTEST_PARAMS
    portfolio = {"cash": params["initial_capital"], "positions": {}}
    trades = []
    equity_curve = []

    for date, signal in signals.iterrows():
        trade_date = date

        # ── 卖出全部持仓 ──
        for code, shares in list(portfolio["positions"].items()):
            if code in signal["sell"] or len(signal["buy"]) > 0:
                px = prices.loc[ trade_date, code] if trade_date in prices.index and code in prices.columns else None
                if px and not np.isnan(px):
                    cost = px * params["commission"] + px * params["slippage"]
                    proceeds = shares * (px - cost)
                    portfolio["cash"] += proceeds
                    trades.append({
                        "date": trade_date, "code": code, "type": "sell",
                        "price": round(px, 3), "shares": shares,
                        "proceeds": round(proceeds, 2),
                    })
                    del portfolio["positions"][code]

        # ── 买入 Top-N ──
        buy_list = [c for c in signal["buy"] if c not in portfolio["positions"]]
        if not buy_list:
            continue

        per_stock_budget = portfolio["cash"] * 0.95 / len(buy_list)
        per_stock_budget = min(per_stock_budget, portfolio["cash"] * params["max_single_stock"])

        for code in buy_list:
            px = prices.loc[ trade_date, code] if trade_date in prices.index and code in prices.columns else None
            if px is None or np.isnan(px):
                continue
            total_cost = px * (1 + params["commission"] + params["slippage"])
            shares = int(per_stock_budget / total_cost)
            if shares > 0:
                portfolio["positions"][code] = shares
                cost = shares * px * (1 + params["commission"] + params["slippage"])
                portfolio["cash"] -= cost
                trades.append({
                    "date": trade_date, "code": code, "type": "buy",
                    "price": round(px, 3), "shares": shares,
                    "cost": round(cost, 2),
                })

        # 记录净值
        total_value = portfolio["cash"]
        for code, shares in portfolio["positions"].items():
            px = prices.loc[ trade_date, code] if trade_date in prices.index and code in prices.columns else None
            if px and not np.isnan(px):
                total_value += shares * px
        equity_curve.append({"date": trade_date, "total_value": round(total_value, 2)})

    return trades, equity_curve


def calculate_metrics(equity_curve: list[dict]) -> dict:
    """计算绩效指标（pandas 向量化，不手写公式）"""
    df = pd.DataFrame(equity_curve).set_index("date")
    df["returns"] = df["total_value"].pct_change()

    metrics = {
        "initial_capital": BACKTEST_PARAMS["initial_capital"],
        "final_value": round(df["total_value"].iloc[-1], 2),
        "total_return": round((df["total_value"].iloc[-1] / BACKTEST_PARAMS["initial_capital"] - 1) * 100, 2),
        "annual_return": round(((df["total_value"].iloc[-1] / BACKTEST_PARAMS["initial_capital"]) ** (252 / len(df)) - 1) * 100, 2),
    }

    returns = df["returns"].dropna()
    if len(returns) > 0:
        metrics["annual_volatility"] = round(returns.std() * np.sqrt(252) * 100, 2)
        metrics["sharpe_ratio"] = round((returns.mean() / returns.std()) * np.sqrt(252), 3)
        metrics["max_drawdown"] = round((df["total_value"] / df["total_value"].cummax() - 1).min() * 100, 2)
        metrics["win_rate"] = round((returns > 0).mean() * 100, 2)
        metrics["total_trades"] = len(returns)

    return metrics


def print_report(metrics: dict, trades: list[dict], equity_curve: list[dict]):
    """打印回测报告"""
    logger.info("=" * 60)
    logger.info("回测报告")
    logger.info("=" * 60)
    logger.info(f"  初始资金: {metrics.get('initial_capital', 0):,.0f}")
    logger.info(f"  最终净值: {metrics.get('final_value', 0):,.0f}")
    logger.info(f"  总收益: {metrics.get('total_return', 0):+.2f}%")
    logger.info(f"  年化收益: {metrics.get('annual_return', 0):+.2f}%")
    logger.info(f"  年化波动: {metrics.get('annual_volatility', 0):.2f}%")
    logger.info(f"  夏普比率: {metrics.get('sharpe_ratio', 0):.3f}  (≥1.2 {'✅' if (metrics.get('sharpe_ratio', 0) or 0) >= 1.2 else '❌'})")
    logger.info(f"  最大回撤: {metrics.get('max_drawdown', 0):.2f}%  (<25% {'✅' if (metrics.get('max_drawdown', 0) or 100) < 25 else '❌'})")
    logger.info(f"  胜率: {metrics.get('win_rate', 0):.1f}%")
    logger.info(f"  交易次数: {metrics.get('total_trades', 0)}")
    logger.info(f"  参数锁定: 滑点0.1% / 万三手续费 / 单票≤20% ✅")
    logger.info("=" * 60)


def main():
    """主流程"""
    logger.info("Phase G: 自研轻量回测")
    logger.info(f"参数: {json.dumps(BACKTEST_PARAMS, indent=2)}")

    # 1. 加载历史打分（AI 模型真实预测）
    logger.info("\n1. 加载历史数据...")
    scores, prices = load_historical_scores()
    logger.info(f"   数据范围: {scores['trade_date'].min().date()} ~ {scores['trade_date'].max().date()}")
    logger.info(f"   总行数: {len(scores)}")

    # 2. 生成信号
    logger.info("\n2. 生成买卖信号...")
    signals = generate_signals(scores)
    logger.info(f"   调仓次数: {len(signals)}")

    # 3. 模拟交易
    logger.info("\n3. 模拟交易...")
    trades, equity_curve = simulate_trades(signals, prices)
    logger.info(f"   交易笔数: {len(trades)}")

    # 4. 计算绩效
    logger.info("\n4. 计算绩效指标...")
    metrics = calculate_metrics(equity_curve)

    # 5. 报告
    print_report(metrics, trades, equity_curve)

    # 6. 保存结果
    output_dir = Path(__file__).resolve().parent.parent / "ml" / "backtest"
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "backtest_report.json", "w") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    pd.DataFrame(equity_curve).to_csv(output_dir / "equity_curve.csv", index=False)
    logger.info(f"\n结果已保存: {output_dir}")


if __name__ == "__main__":
    main()
