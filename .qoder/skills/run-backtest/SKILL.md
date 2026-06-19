---
name: run-backtest
description: Run backtesting for the track quant system. Uses fixed parameters (slippage, commission, position limits) that cannot be changed to chase better Sharpe. Outputs performance metrics. Use when running or evaluating backtests.
---

# Run Backtest — 回测固定流程

## When to Use

当需要用 AI 打分结果跑回测验证策略效果时。

**禁止**：为了刷高夏普/降低回撤而修改回测参数。

## Fixed Parameters (锁定，不可更改)

```python
BACKTEST_PARAMS = {
    # 交易成本
    "slippage": 0.001,        # 滑点 0.1%（固定）
    "commission": 0.0003,     # 手续费 万三（固定）

    # 仓位控制
    "max_single_stock": 0.20, # 单票上限 20%
    "max_single_track": 0.50, # 单赛道上限 50%
    "total_position": 1.0,    # 满仓 = 100%

    # 赛道景气降仓
    "track_prosperity_threshold": 40,  # 景气度 < 40 自动减仓至 50%

    # 交易限制
    "skip_limit_up": True,    # 涨停无法买入
    "skip_limit_down": True,  # 跌停无法卖出
    "rebalance_freq": "weekly",  # 周频调仓

    # 初始资金
    "initial_capital": 100000,  # 10 万起步
}
```

**铁律：以上参数在回测前锁定，跑完后无论结果好坏都不可修改重跑。**

## Pipeline

```
Step 1: Load Scores  → 加载历史 AI 打分数据
Step 2: Generate Signals → 打分 → 排序 → 生成买卖信号
Step 3: Simulate     → 模拟交易（含成本/限制）
Step 4: Calculate    → 计算绩效指标
Step 5: Report       → 输出回测报告
```

## Step 1: Load Scores

```python
# 从 score_history 表加载历史打分
scores = load_score_history(start_date, end_date)
# 只包含白名单特征训练出的模型打分
```

## Step 2: Generate Signals

```python
def generate_signals(scores, track_name):
    """每周调仓：买 top-3，卖 bottom-3"""
    weekly_scores = scores.resample("W").last()

    signals = pd.DataFrame()
    for week, data in weekly_scores.groupby("date"):
        ranked = data.sort_values("stock_score", ascending=False)
        top_3 = ranked.head(3).index    # 买入
        bottom_3 = ranked.tail(3).index  # 卖出
        signals.loc[week, "buy"] = top_3
        signals.loc[week, "sell"] = bottom_3

    return signals
```

## Step 3: Simulate

```python
def simulate_trades(signals, prices, params):
    """模拟交易，严格执行固定参数"""
    portfolio = {"cash": params["initial_capital"], "positions": {}}

    for date, signal in signals.iterrows():
        # 卖出
        for code in signal["sell"]:
            if code in portfolio["positions"]:
                price = prices.loc[date, code]
                cost = price * params["commission"] + price * params["slippage"]
                proceeds = portfolio["positions"][code] * (price - cost)
                portfolio["cash"] += proceeds
                del portfolio["positions"][code]

        # 买入（等权分配）
        buy_list = signal["buy"]
        per_stock_cash = portfolio["cash"] * 0.95 / len(buy_list)  # 留 5% 现金
        per_stock_cash = min(per_stock_cash, portfolio["cash"] * params["max_single_stock"])

        for code in buy_list:
            price = prices.loc[date, code]
            if prices.loc[date, "is_limit_up"]:  # 涨停跳过
                continue
            shares = int(per_stock_cash / (price * (1 + params["commission"] + params["slippage"])))
            if shares > 0:
                portfolio["positions"][code] = shares
                portfolio["cash"] -= shares * price * (1 + params["commission"] + params["slippage"])

    return portfolio_history
```

## Step 4: Calculate Metrics

```python
def calculate_metrics(portfolio_history):
    """用 pandas 向量化计算，不手写公式"""
    returns = portfolio_history["total_value"].pct_change().dropna()

    metrics = {
        "annual_return": (1 + returns.mean()) ** 252 - 1,
        "annual_volatility": returns.std() * np.sqrt(252),
        "sharpe_ratio": (returns.mean() / returns.std()) * np.sqrt(252),
        "max_drawdown": (portfolio_history["total_value"] / portfolio_history["total_value"].cummax() - 1).min(),
        "win_rate": (returns > 0).mean(),
    }
    return metrics
```

## Step 5: Report

```markdown
# Backtest Report

> Period: {start} ~ {end}
> Track: {track_name}

## Performance

| Metric | Value | Threshold | Status |
|:-------|:------|:----------|:------:|
| 年化收益 | {x}% | - | - |
| 夏普比率 | {x} | ≥ 1.2 | ✅/❌ |
| 最大回撤 | {x}% | < 25% | ✅/❌ |
| 胜率 | {x}% | - | - |

## Decile Analysis

| 分层 | 年化收益 | 单调性 |
|:-----|:---------|:------:|
| Top 20% (高分池) | {x}% | - |
| Mid 60% | {x}% | - |
| Bottom 20% (低分池) | {x}% | ✅ 单调 / ❌ 不单调 |
```

## 验收标准

| 指标 | 底线 | 不达标处理 |
|:-----|:-----|:----------|
| 夏普比率 | ≥ 1.2 | 检查特征质量，走 add-feature 优化 |
| 最大回撤 | < 25% | 检查仓位控制逻辑 |
| 分层单调性 | Top > Mid > Bottom | 检查模型打分有效性 |

**禁止**：
- 改滑点/手续费让夏普好看
- 改仓位上限让回撤好看
- 换回测时间段挑最好的一段
- 反复调策略参数直到指标达标

## 不达标时的正确做法

```
夏普 < 1.2  → 不是改回测参数，而是回到上游：
  1. 检查特征质量（走 /check-data）
  2. 检查模型是否过拟合（走 /train-model Step 4）
  3. 增加有效特征（走 /add-feature）

回撤 > 25%  → 不是放宽阈值，而是：
  1. 检查是否单票/单赛道过于集中
  2. 检查赛道景气降仓是否生效
```
