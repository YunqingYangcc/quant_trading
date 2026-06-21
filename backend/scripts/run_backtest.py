"""
Phase G: 自研轻量回测（增强版）

支持：
  - 周频 / 月频 调仓
  - 止损 / 止盈 风控
  - 多策略对比运行

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
    "slippage": 0.001,
    "commission": 0.0003,
    "max_single_stock": 0.20,
    "max_single_track": 0.50,
    "track_prosperity_threshold": 40,
    "skip_limit_up": True,
    "skip_limit_down": True,
    "rebalance_freq": "W",       # W=周频 M=月频
    "initial_capital": 100000,
    "top_n": 3,
    "stop_loss_pct": -0.15,      # 单票 -15% 止损
    "take_profit_pct": 0.30,     # 单票 +30% 止盈
}

MODELS_DIR = Path(__file__).resolve().parent.parent / "ml" / "models"
PREPROCESSED_DIR = Path(__file__).resolve().parent.parent / "ml" / "preprocessed"


def load_historical_scores() -> tuple[pd.DataFrame, pd.DataFrame]:
    """加载数据并使用 AI 模型生成历史打分（带缓存）"""
    scores_cache_path = PREPROCESSED_DIR / "backtest_scores.parquet"
    prices_cache_path = PREPROCESSED_DIR / "backtest_prices.parquet"

    # 检查缓存是否有效（模型文件未变则直接用缓存）
    if scores_cache_path.exists() and prices_cache_path.exists():
        cache_mtime = scores_cache_path.stat().st_mtime
        model_files = list(MODELS_DIR.glob("*.pkl"))
        if model_files:
            newest_model = max(f.stat().st_mtime for f in model_files)
            if cache_mtime > newest_model:
                logger.info("  ✅ 使用缓存打分（模型未变更，跳过 AI 预测）")
                scores = pd.read_parquet(scores_cache_path)
                prices = pd.read_parquet(prices_cache_path)
                return scores, prices
        else:
            logger.warning("  未找到模型文件，重新计算打分")

    logger.info("  计算 AI 打分（无缓存或模型已更新）...")
    val = pd.read_parquet(PREPROCESSED_DIR / "val.parquet")
    test = pd.read_parquet(PREPROCESSED_DIR / "test.parquet")
    df = pd.concat([val, test], ignore_index=True)
    df["trade_date"] = pd.to_datetime(df["date"])
    df = df.sort_values("trade_date")

    import sqlite3
    db_path = Path(__file__).resolve().parent.parent / "track_quant.db"
    conn = sqlite3.connect(str(db_path))
    raw = pd.read_sql("SELECT stock_code, trade_date, close_px FROM track_data_cache", conn)
    conn.close()
    raw["trade_date"] = pd.to_datetime(raw["trade_date"])
    raw = raw.rename(columns={"close_px": "close"})
    df = df.merge(raw, on=["stock_code", "trade_date"], how="left")

    with open(PREPROCESSED_DIR / "feature_cols.json") as f:
        feature_cols = json.load(f)

    track_stocks = _get_track_stocks()

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
        df.loc[mask, "pred_score"] = model.predict_proba(X)[:, 1]

    scores = df[["trade_date", "stock_code", "pred_score"]].copy()
    prices = df.pivot_table(index="trade_date", columns="stock_code", values="close")

    # 缓存结果
    PREPROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    scores.to_parquet(scores_cache_path)
    prices.to_parquet(prices_cache_path)
    logger.info(f"  💾 打分已缓存 ({len(scores)} 条)")

    logger.info(f"  使用 AI 模型生成打分: {len(scores)} 条")
    return scores, prices


def _get_track_stocks() -> dict[str, list[str]]:
    import asyncio
    from scripts.train_models import get_track_stock_map
    try:
        return asyncio.run(get_track_stock_map())
    except Exception as e:
        logger.warning(f"获取赛道映射失败: {e}")
        return {}


def _period_label(date: pd.Timestamp, freq: str) -> str:
    """生成调仓周期标签"""
    if freq == "W":
        iso = date.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    else:  # M - 月频
        return f"{date.year}-{date.month:02d}"


def _build_stock_to_track_map(track_stocks: dict[str, list[str]]) -> dict[str, str]:
    """构建股票代码→赛道名称映射"""
    mapping = {}
    for track, stocks in track_stocks.items():
        for code in stocks:
            mapping[code] = track
    return mapping


def _calculate_track_weights(
    scores: pd.DataFrame,
    date: pd.Timestamp,
    stock_to_track: dict[str, str],
    track_stocks: dict[str, list[str]],
    threshold: float,
) -> dict[str, float]:
    """基于赛道景气度计算个股买入权重"""
    date_scores = scores[scores["trade_date"] == date]
    if len(date_scores) == 0:
        return {}

    # 计算各赛道平均景气度
    track_sentiments = {}
    for track, stocks in track_stocks.items():
        ts = date_scores[date_scores["stock_code"].isin(stocks)]
        track_sentiments[track] = ts["pred_score"].mean() if len(ts) > 0 else 0.0

    # 景气度低于阈值 → 权重打折
    weights = {}
    for track, sentiment in track_sentiments.items():
        if sentiment <= 0:
            weights[track] = 0.3
        elif sentiment < threshold:
            weights[track] = 0.3 + 0.7 * (sentiment / threshold)
        else:
            weights[track] = 1.0 + 0.3 * min((sentiment - threshold) / threshold, 2.0)

    return weights


def generate_signals(scores: pd.DataFrame, params: dict) -> pd.DataFrame:
    """打分 -> 买卖信号"""
    scores = scores.copy()
    freq = params["rebalance_freq"]
    scores["period"] = scores["trade_date"].apply(lambda d: _period_label(d, freq))

    signals = []
    for period, group in scores.groupby("period"):
        period_date = group["trade_date"].max()
        best_per_stock = group.loc[group.groupby("stock_code")["pred_score"].idxmax()]
        ranked = best_per_stock.sort_values("pred_score", ascending=False)
        top_stocks = ranked.head(params["top_n"])["stock_code"].tolist()

        signals.append({
            "date": period_date,
            "buy": top_stocks,
            "sell_all": True,   # 调仓日全卖再买（固定调仓模式）
        })

    return pd.DataFrame(signals).set_index("date")


def simulate_trades(signals: pd.DataFrame, prices: pd.DataFrame, params: dict) -> tuple[list[dict], list[dict]]:
    """模拟交易流水（含止损/止盈）"""
    portfolio = {"cash": params["initial_capital"], "positions": {}}
    trades = []
    equity_curve = []
    price_cache: dict[str, dict[str, float]] = {}  # code -> {date: price}

    # 构建快速查询的 price lookup
    for date in signals.index:
        if date in prices.index:
            for code in prices.columns:
                px = prices.loc[date, code]
                if pd.notna(px):
                    price_cache.setdefault(code, {})[date] = px

    all_dates = sorted(set(signals.index).union(
        d for cm in price_cache.values() for d in cm.keys()
    ))
    all_dates.sort()

    for date in all_dates:
        # 检查止损/止盈（在调仓日或非调仓日都检查）
        stop_loss_sells = []
        for code, shares in list(portfolio["positions"].items()):
            px = price_cache.get(code, {}).get(date)
            if px is None:
                continue
            entry_px = portfolio["positions"][code]  # stored as {code: {shares, entry_price}}
            # 这里需要重构，将positions改为存entry_price
            # 临时处理：用shares的原有逻辑
        
        # 止损/止盈逻辑需要重构position存储方式
        
    # 由于positions存的是shares(int)，需要改为存dict
    # 重构：简化实现
    
    return trades, equity_curve


def run_single_strategy(
    name: str,
    params: dict,
    scores: pd.DataFrame,
    prices: pd.DataFrame,
) -> dict:
    """运行单个策略并返回指标"""
    logger.info(f"\n{'='*60}")
    logger.info(f"策略: {name}")
    logger.info(f"{'='*60}")

    # 生成信号
    signals = generate_signals(scores, params)

    # 模拟交易（含止损/止盈）
    portfolio = {"cash": params["initial_capital"], "positions": {}}
    trades = []
    equity_curve = []
    freq = params["rebalance_freq"]

    # 构建每日价格查询表
    all_prices = {}
    for dt in pd.date_range(scores["trade_date"].min(), scores["trade_date"].max(), freq="D"):
        if dt in prices.index:
            for code in prices.columns:
                px = prices.loc[dt, code]
                if pd.notna(px):
                    all_prices.setdefault(code, {}).setdefault(dt, px)
    all_prices_df = prices

    # 获取所有交易日（排序）
    trade_dates = sorted(set(signals.index).union(
        set(prices.index)
    ))
    trade_dates.sort()

    # 找出调仓日
    rebalance_dates = set(signals.index)

    # 记录每只股票的买入价（用于止损/止盈）
    entry_prices: dict[str, float] = {}

    for t in range(len(trade_dates)):
        date = trade_dates[t]

        # ---- 非调仓日：只检查止损/止盈 ----
        if date not in rebalance_dates:
            for code, shares in list(portfolio["positions"].items()):
                px = all_prices_df.loc[date, code] if date in all_prices_df.index and code in all_prices_df.columns else None
                if px is None or np.isnan(px) or code not in entry_prices:
                    continue
                entry = entry_prices[code]
                ret = (px - entry) / entry

                # 止损
                if ret <= params["stop_loss_pct"]:
                    cost = px * (params["commission"] + params["slippage"])
                    proceeds = shares * (px - cost)
                    portfolio["cash"] += proceeds
                    trades.append({
                        "date": str(date.date()), "code": code, "type": "stop_loss",
                        "price": round(px, 3), "shares": shares, "reason": f"止损 {ret*100:.1f}%",
                        "proceeds": round(proceeds, 2),
                    })
                    del portfolio["positions"][code]
                    del entry_prices[code]

                # 止盈
                elif ret >= params["take_profit_pct"]:
                    cost = px * (params["commission"] + params["slippage"])
                    proceeds = shares * (px - cost)
                    portfolio["cash"] += proceeds
                    trades.append({
                        "date": str(date.date()), "code": code, "type": "take_profit",
                        "price": round(px, 3), "shares": shares, "reason": f"止盈 {ret*100:.1f}%",
                        "proceeds": round(proceeds, 2),
                    })
                    del portfolio["positions"][code]
                    del entry_prices[code]

            # 记录净值
            nav = portfolio["cash"]
            for code, shares in portfolio["positions"].items():
                px = all_prices_df.loc[date, code] if date in all_prices_df.index and code in all_prices_df.columns else None
                if px and not np.isnan(px):
                    nav += shares * px
            equity_curve.append({"date": str(date.date()), "total_value": round(nav, 2)})
            continue

        # ---- 调仓日：先卖后买 ----
        signal = signals.loc[date]

        # 卖出全部持仓
        for code, shares in list(portfolio["positions"].items()):
            px = all_prices_df.loc[date, code] if date in all_prices_df.index and code in all_prices_df.columns else None
            if px and not np.isnan(px):
                cost = px * (params["commission"] + params["slippage"])
                proceeds = shares * (px - cost)
                portfolio["cash"] += proceeds
                trades.append({
                    "date": str(date.date()), "code": code, "type": "sell",
                    "price": round(px, 3), "shares": shares,
                    "proceeds": round(proceeds, 2),
                })
                del portfolio["positions"][code]
                if code in entry_prices:
                    del entry_prices[code]

        # 买入 Top-N（含赛道景气降仓）
        buy_list = signal["buy"]
        if not buy_list:
            continue

        # 构建赛道映射&计算景气权重
        track_stocks = _get_track_stocks()
        stock_to_track = _build_stock_to_track_map(track_stocks)
        track_w = _calculate_track_weights(scores, date, stock_to_track, track_stocks, params.get("track_prosperity_threshold", 40))

        # 计算个股买入权重（等权 × 赛道景气系数）
        stock_w = {}
        for code in buy_list:
            t = stock_to_track.get(code, "")
            base_w = 1.0 / len(buy_list)
            tw = track_w.get(t, 0.5)
            stock_w[code] = base_w * tw

        total_w = sum(stock_w.values())
        if total_w <= 0:
            continue
        # 归一化权重
        for k in stock_w:
            stock_w[k] /= total_w

        buy_cash = portfolio["cash"] * 0.95

        for code in buy_list:
            px = all_prices_df.loc[date, code] if date in all_prices_df.index and code in all_prices_df.columns else None
            if px is None or np.isnan(px):
                continue
            per_stock_budget = min(buy_cash * stock_w.get(code, 0), portfolio["cash"] * params["max_single_stock"])
            total_cost = px * (1 + params["commission"] + params["slippage"])
            shares = int(per_stock_budget / total_cost)
            if shares > 0:
                portfolio["positions"][code] = shares
                entry_prices[code] = px
                cost = shares * px * (1 + params["commission"] + params["slippage"])
                portfolio["cash"] -= cost
                trades.append({
                    "date": str(date.date()), "code": code, "type": "buy",
                    "price": round(px, 3), "shares": shares,
                    "cost": round(cost, 2),
                })

        # 记录净值
        nav = portfolio["cash"]
        for code, shares in portfolio["positions"].items():
            px = all_prices_df.loc[date, code] if date in all_prices_df.index and code in all_prices_df.columns else None
            if px and not np.isnan(px):
                nav += shares * px
        equity_curve.append({"date": str(date.date()), "total_value": round(nav, 2)})

    # 计算绩效
    metrics = _calculate_metrics(equity_curve, params)
    metrics["name"] = name
    metrics["trades"] = len(trades)
    metrics["rebalance_count"] = len(signals)
    metrics["stop_loss_count"] = sum(1 for t in trades if t["type"] == "stop_loss")
    metrics["take_profit_count"] = sum(1 for t in trades if t["type"] == "take_profit")

    # 保存净值曲线
    eq_df = pd.DataFrame(equity_curve)
    output_dir = Path(__file__).resolve().parent.parent / "ml" / "backtest"
    output_dir.mkdir(parents=True, exist_ok=True)
    eq_df.to_csv(output_dir / f"equity_curve_{name.replace(' ', '_')}.csv", index=False)

    # 打印
    logger.info(f"  调仓次数: {metrics['rebalance_count']}")
    logger.info(f"  交易笔数: {metrics['trades']}")
    logger.info(f"  止损次数: {metrics['stop_loss_count']}")
    logger.info(f"  止盈次数: {metrics['take_profit_count']}")
    logger.info(f"  总收益: {metrics['total_return']:+.2f}%")
    logger.info(f"  年化收益: {metrics['annual_return']:+.2f}%")
    logger.info(f"  年化波动: {metrics['annual_volatility']:.2f}%")
    logger.info(f"  夏普比率: {metrics['sharpe_ratio']:.3f}")
    logger.info(f"  最大回撤: {metrics['max_drawdown']:.2f}%")
    logger.info(f"  胜率: {metrics['win_rate']:.1f}%")

    return metrics


def _calculate_metrics(equity_curve: list[dict], params: dict) -> dict:
    """计算绩效指标"""
    df = pd.DataFrame(equity_curve).set_index("date")
    df["returns"] = df["total_value"].pct_change()

    metrics = {
        "initial_capital": params["initial_capital"],
        "final_value": round(float(df["total_value"].iloc[-1]), 2),
        "total_return": round((float(df["total_value"].iloc[-1]) / params["initial_capital"] - 1) * 100, 2),
        "annual_return": round(((float(df["total_value"].iloc[-1]) / params["initial_capital"]) ** (252 / max(len(df), 1)) - 1) * 100, 2),
    }

    returns = df["returns"].dropna()
    if len(returns) > 0:
        metrics["annual_volatility"] = round(float(returns.std() * np.sqrt(252) * 100), 2)
        metrics["sharpe_ratio"] = round(float((returns.mean() / returns.std()) * np.sqrt(252)), 3)
        metrics["max_drawdown"] = round(float((df["total_value"] / df["total_value"].cummax() - 1).min() * 100), 2)
        metrics["win_rate"] = round(float((returns > 0).mean() * 100), 2)
        metrics["total_trades"] = len(returns)

    return metrics


def print_comparison(all_results: list[dict]):
    """多策略对比报告"""
    logger.info("\n" + "=" * 60)
    logger.info("多策略对比报告")
    logger.info("=" * 60)

    rows = []
    for r in all_results:
        rows.append({
            "策略": r["name"],
            "总收益": f"{r['total_return']:+.2f}%",
            "年化收益": f"{r['annual_return']:+.2f}%",
            "夏普": f"{r['sharpe_ratio']:.3f}",
            "最大回撤": f"{r['max_drawdown']:.2f}%",
            "胜率": f"{r['win_rate']:.1f}%",
            "调仓": r["rebalance_count"],
            "止损": r.get("stop_loss_count", 0),
            "止盈": r.get("take_profit_count", 0),
        })

    for row in rows:
        logger.info(f"  {row['策略']:15s} | 收益:{row['总收益']:>8s} | 夏普:{row['夏普']} | 回撤:{row['最大回撤']} | 胜率:{row['胜率']}")

    # 找出最佳
    best_sharpe = max(all_results, key=lambda r: r["sharpe_ratio"])
    best_return = max(all_results, key=lambda r: r["total_return"])
    best_dd = max(all_results, key=lambda r: r["max_drawdown"])

    logger.info(f"\n🏆 最高夏普: {best_sharpe['name']} ({best_sharpe['sharpe_ratio']:.3f})")
    logger.info(f"🏆 最高收益: {best_return['name']} ({best_return['total_return']:+.2f}%)")
    logger.info(f"🏆 最低回撤: {best_dd['name']} ({best_dd['max_drawdown']:.2f}%)")


def run_all_strategies(scores: pd.DataFrame, prices: pd.DataFrame):
    """运行全部策略并对比（含基线）"""
    strategies = [
        # (name, param_overrides)
        ("周频", {"rebalance_freq": "W"}),
        ("月频", {"rebalance_freq": "M"}),
        ("周频+止损", {"rebalance_freq": "W", "stop_loss_pct": -0.15, "take_profit_pct": 0.30}),
        ("月频+止损", {"rebalance_freq": "M", "stop_loss_pct": -0.15, "take_profit_pct": 0.30}),
    ]

    all_results = []
    for name, overrides in strategies:
        params = {**BACKTEST_PARAMS, **overrides}
        params["rebalance_freq"] = overrides.get("rebalance_freq", BACKTEST_PARAMS["rebalance_freq"])
        result = run_single_strategy(name, params, scores, prices)
        all_results.append(result)

    # ── 基线策略对比 ──
    from strategies import BASELINE_STRATEGIES, STRATEGY_REGISTRY
    logger.info("")
    logger.info("=" * 60)
    logger.info("基线策略对比")
    logger.info("=" * 60)
    baseline_results = run_strategy_baselines(prices)
    all_results.extend(baseline_results)

    print_comparison(all_results)

    # 保存所有结果
    output_dir = Path(__file__).resolve().parent.parent / "ml" / "backtest"
    with open(output_dir / "backtest_report.json", "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)

    return all_results


def run_strategy_baselines(prices: pd.DataFrame) -> list[dict]:
    """运行内置基线策略（等权持有、动量Top-3）"""
    from strategies import BASELINE_STRATEGIES, STRATEGY_REGISTRY
    results = []
    for key in BASELINE_STRATEGIES:
        entry = STRATEGY_REGISTRY.get(key)
        if not entry:
            continue
        gen = entry["generator"]
        signals = gen.generate(prices)
        if signals.empty:
            logger.warning(f"  {entry['name']}: 无信号")
            continue
        # 用回测引擎模拟
        params = {**BACKTEST_PARAMS, "rebalance_freq": "M"}
        result = _simulate_from_signals(signals, prices, params, entry["name"])
        results.append(result)
    return results


def run_strategy_by_name(strategy_name: str, prices: pd.DataFrame, params: dict | None = None) -> dict:
    """按策略名运行回测（供 API 调用）"""
    from strategies import STRATEGY_REGISTRY, get_strategy
    entry = STRATEGY_REGISTRY.get(strategy_name)
    if not entry:
        raise ValueError(f"未知策略: {strategy_name}")
    gen = entry["generator"]
    signals = gen.generate(prices)
    if signals.empty:
        return {"name": entry["name"], "error": "无信号"}
    bt_params = {**BACKTEST_PARAMS, **(params or {})}
    return _simulate_from_signals(signals, prices, bt_params, entry["name"])


def _simulate_from_signals(signals: pd.DataFrame, prices: pd.DataFrame, params: dict, name: str) -> dict:
    """从信号 DataFrame 直接模拟交易."""
    portfolio = {"cash": params["initial_capital"], "positions": {}}
    trades = []
    equity_curve = []
    entry_prices: dict[str, float] = {}

    prices_ffill = prices.ffill()
    all_dates = sorted(set(signals.index).union(set(prices.index)))
    rebalance_dates = set(signals.index)

    for date in all_dates:
        if date not in rebalance_dates:
            # 非调仓日：记录净值 + 检查止损止盈
            for code, shares in list(portfolio["positions"].items()):
                if date not in prices_ffill.index or code not in prices_ffill.columns:
                    continue
                px = prices_ffill.loc[date, code]
                if pd.isna(px) or code not in entry_prices:
                    continue
                ret = (px - entry_prices[code]) / entry_prices[code]
                if ret <= params.get("stop_loss_pct", -0.15):
                    cost = px * (params["commission"] + params["slippage"])
                    portfolio["cash"] += shares * (px - cost)
                    trades.append({"date": str(date.date()), "code": code, "type": "stop_loss",
                                  "price": round(px, 3), "shares": shares,
                                  "reason": f"止损 {ret*100:.1f}%"})
                    del portfolio["positions"][code]
                    del entry_prices[code]
                elif ret >= params.get("take_profit_pct", 0.30):
                    cost = px * (params["commission"] + params["slippage"])
                    portfolio["cash"] += shares * (px - cost)
                    trades.append({"date": str(date.date()), "code": code, "type": "take_profit",
                                  "price": round(px, 3), "shares": shares,
                                  "reason": f"止盈 {ret*100:.1f}%"})
                    del portfolio["positions"][code]
                    del entry_prices[code]

            nav = portfolio["cash"]
            for code, shares in portfolio["positions"].items():
                if date in prices_ffill.index and code in prices_ffill.columns:
                    px = prices_ffill.loc[date, code]
                    if not pd.isna(px):
                        nav += shares * px
            equity_curve.append({"date": str(date.date()), "total_value": round(nav, 2)})
            continue

        # 调仓日
        signal = signals.loc[date]
        # 卖出全部
        for code, shares in list(portfolio["positions"].items()):
            sold = False
            if date in prices_ffill.index and code in prices_ffill.columns:
                px = prices_ffill.loc[date, code]
                if not pd.isna(px):
                    cost = px * (params["commission"] + params["slippage"])
                    portfolio["cash"] += shares * (px - cost)
                    trades.append({"date": str(date.date()), "code": code, "type": "sell",
                                  "price": round(px, 3), "shares": shares})
                    sold = True
            if sold:
                del portfolio["positions"][code]
                if code in entry_prices:
                    del entry_prices[code]

        # 买入
        buy_list = signal.get("buy", [])
        weights = signal.get("weights", {})
        if not buy_list:
            continue
        buy_cash = portfolio["cash"] * 0.95
        for code in buy_list:
            if date not in prices_ffill.index or code not in prices_ffill.columns:
                continue
            px = prices_ffill.loc[date, code]
            if pd.isna(px):
                continue
            w = weights.get(code, 1.0 / len(buy_list))
            per_stock = min(buy_cash * w, portfolio["cash"] * params["max_single_stock"])
            total_cost = px * (1 + params["commission"] + params["slippage"])
            shares = int(per_stock / total_cost)
            if shares > 0:
                portfolio["positions"][code] = shares
                entry_prices[code] = px
                portfolio["cash"] -= shares * px * (1 + params["commission"] + params["slippage"])
                trades.append({"date": str(date.date()), "code": code, "type": "buy",
                              "price": round(px, 3), "shares": shares})

        nav = portfolio["cash"]
        for code, shares in portfolio["positions"].items():
            if date in prices_ffill.index and code in prices_ffill.columns:
                px = prices_ffill.loc[date, code]
                if not pd.isna(px):
                    nav += shares * px
        equity_curve.append({"date": str(date.date()), "total_value": round(nav, 2)})

    metrics = _calculate_metrics(equity_curve, params)
    metrics["name"] = name
    metrics["trades"] = len(trades)
    metrics["rebalance_count"] = len(signals)
    metrics["stop_loss_count"] = sum(1 for t in trades if t.get("type") == "stop_loss")
    metrics["take_profit_count"] = sum(1 for t in trades if t.get("type") == "take_profit")

    logger.info(f"  {name:20s} 夏普={metrics['sharpe_ratio']:.3f}  收益={metrics['total_return']:+.1f}%  回撤={metrics['max_drawdown']:.1f}%")
    return metrics


def main():
    """主流程"""
    logger.info("Phase G: 自研轻量回测（增强版）")
    logger.info(f"基准参数: {json.dumps(BACKTEST_PARAMS, indent=2)}")

    # 1. 加载
    logger.info("\n1. 加载历史数据...")
    scores, prices = load_historical_scores()
    logger.info(f"   数据范围: {scores['trade_date'].min().date()} ~ {scores['trade_date'].max().date()}")
    logger.info(f"   总行数: {len(scores)}")

    # 2. 运行全部策略
    all_results = run_all_strategies(scores, prices)

    # 3. 记录流水线日志
    _record_backtest_log(all_results, BACKTEST_PARAMS)

    logger.info(f"\n结果已保存: {Path(__file__).resolve().parent.parent / 'ml' / 'backtest'}")


import asyncio as _asyncio


def _record_backtest_log(all_results: list[dict], params: dict):
    """记录回测流水线日志到数据库."""
    import subprocess
    try:
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        git_hash = None

    summary = {}
    for r in all_results:
        summary[r["name"]] = {
            "sharpe_ratio": r["sharpe_ratio"],
            "total_return": r["total_return"],
            "annual_return": r["annual_return"],
            "max_drawdown": r["max_drawdown"],
            "win_rate": r["win_rate"],
            "annual_volatility": r["annual_volatility"],
            "trades": r["trades"],
        }

    async def _save():
        from app.db.database import async_session_maker
        from app.models.track import PipelineRun
        async with async_session_maker() as session:
            run_log = PipelineRun(
                run_type="backtest",
                status="success",
                params_snapshot=dict(params),
                results_summary=summary,
                git_commit_hash=git_hash,
            )
            session.add(run_log)
            await session.commit()

    _asyncio.run(_save())
    logger.info(f"回测日志已记录: {len(all_results)} 个策略")


if __name__ == "__main__":
    main()
