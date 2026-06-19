---
name: add-feature
description: Add a new feature/indicator to the track quant system. Enforces the mandatory flow compute → store → Alphalens validate → whitelist/blacklist. Prevents unvalidated features from entering training or visualization. Use when adding any new technical indicator or factor.
---

# Add Feature — 新增特征强制流程

## When to Use

当需要新增任何特征/因子/指标时（无论通用还是赛道专属），必须走此流程。

**禁止**：直接在 `features_generic.py` 或 `features_track.py` 中加完就用。

## Mandatory Flow

```
Step 1: Define    → 定义特征名称、类别、计算逻辑
Step 2: Compute   → 在特征文件中实现（pandas-ta 优先）
Step 3: Store     → 入库 stock_features 表
Step 4: Validate  → Alphalens 单因子检验（Phase C 后）
Step 5: Decide    → 通过 → 白名单 / 淘汰 → 黑名单
Step 6: Verify    → 确认 shift(1)、NaN < 50%、无未来泄露
```

## Step 1: Define

填写特征定义卡：

```
特征名称：{英文 snake_case，如 mom_20d}
特征类别：{momentum / trend / volatility / volume / track_specific}
计算逻辑：{一句话描述，如"20日动量 = (close - close_20d_ago) / close_20d_ago"}
开源库覆盖：{pandas-ta 有 / 需要自写}
预期 IC 方向：{正/负/不确定}
```

**规则**：
- 名称必须英文 snake_case，禁止中文
- 通用特征优先查 pandas-ta 是否有：`df.ta.strategy(name='all')` 覆盖 130+ 指标
- 只有 pandas-ta 没有的特征才自写（收益偏度/峰度、赛道专属等）

## Step 2: Compute

### 通用特征 → 改 `features_generic.py`

```python
# 优先用 pandas-ta
import pandas_ta as ta

def compute_all_generic_features(df: pd.DataFrame) -> pd.DataFrame:
    # pandas-ta 已有的指标，一行搞定
    df.ta.momentum(append=True)   # RSI, Stochastic, CCI, Williams %R, ROC
    df.ta.trend(append=True)      # SMA, EMA, MACD
    df.ta.volatility(append=True) # ATR, Bollinger, Keltner
    df.ta.volume(append=True)     # OBV, VWAP, CMF

    # pandas-ta 没有的，才自写
    df["return_skew_20d"] = df["close"].pct_change().rolling(20).skew()

    # 统一 shift(1) 防未来泄露
    feature_cols = [c for c in df.columns if c not in RAW_COLS]
    df[feature_cols] = df[feature_cols].shift(1)
    return df
```

### 赛道专属特征 → 改 `features_track.py`

赛道特征没有开源库覆盖，自写但必须遵守 shift(1)。

## Step 3: Store

运行特征计算脚本，确保新特征入库：

```bash
cd backend && python -m scripts.compute_features
```

验证入库成功：
```python
# 检查新特征是否出现在 stock_features 表
import sqlite3
conn = sqlite3.connect("track_quant.db")
df = pd.read_sql("SELECT DISTINCT feature_name FROM stock_features WHERE feature_name LIKE '%新特征名%'", conn)
print(f"特征已入库: {len(df)} 条")
```

## Step 4: Validate (Phase C 之后)

**Phase B 阶段**：暂跳过 Alphalens，但必须记录特征，待 Phase C 统一筛选。

**Phase C 之后**：每个新特征必须通过 Alphalens 三门槛：

| 检验项 | 门槛 | 不通过则 |
|:-------|:-----|:---------|
| \|IC\| 均值 | ≥ 0.02 | → 黑名单 |
| IR | ≥ 0.5 | → 黑名单 |
| 10 层分组收益 | 单调递增/递减 | → 黑名单 |

## Step 5: Decide

```
通过 Alphalens 三门槛 → FeatureWhiteList 表 + configs/factor_whitelist.json
任意一项不通过        → FeatureBlackList 表（记录淘汰原因）
```

**黑名单铁律：黑名单特征禁止出现在以下任何环节：**
- 模型训练输入
- 打分计算
- 前端可视化

## Step 6: Verify

自检清单：

- [ ] `shift(1)` 已应用（检查代码中有 `.shift(1)` 或 `result = result.shift(1)`）
- [ ] NaN 比例 < 50%（`df[new_feature].isna().mean()`）
- [ ] 无未来泄露（特征值只依赖当日及之前的数据）
- [ ] 已入库 `stock_features` 表
- [ ] Phase C 后：已进入白名单或黑名单

## Anti-Patterns (禁止)

| 禁止行为 | 为什么 |
|:---------|:------|
| 加完特征直接训练 | 未经 Alphalens 验证的特征可能是噪音 |
| 同时加 10+ 特征不做筛选 | 特征越多过拟合风险越高 |
| 手写 RSI/MACD/ATR 等标准指标 | pandas-ta 已有，手写易出错 |
| 特征不加 shift(1) | 未来泄露，回测好看实盘亏钱 |
| 在前端直接展示未筛选的特征 | 噪音指标干扰决策 |
