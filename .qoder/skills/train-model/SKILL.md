---
name: train-model
description: Train LightGBM models for each track in the quant system. Enforces fixed training pipeline whitelist features only → TimeSeriesSplit → save model → validate overfitting. Prevents random hyperparameter tuning and model drift. Use when training or retraining AI models.
---

# Train Model — 模型训练固定流程

## When to Use

当需要训练/重新训练赛道的 LightGBM 模型时。

**禁止**：随意调参、换模型类型、改训练流程。

## Fixed Pipeline

```
Step 1: Load     → 从 DB 加载白名单特征 + 标签
Step 2: Split    → TimeSeriesSplit（禁止 shuffle）
Step 3: Train    → LightGBM 固定参数训练 4 个赛道模型
Step 4: Validate → 过拟合检测（R² 差距 < 0.15）
Step 5: Save     → joblib 序列化到 ml/models/{track}.pkl
Step 6: Log      → 记录训练指标到 model_registry 表
```

## Step 1: Load — 只加载白名单特征

```python
# 强制：只使用白名单中的特征
whitelist = pd.read_json("configs/factor_whitelist.json")
feature_names = whitelist["factor_name"].tolist()

# 加载特征 + 标签
X = load_features(stock_codes, feature_names)  # 从 stock_features 表
y = load_labels(stock_codes, target="fwd_20d_return")  # 从标签表

# 丢弃含 NaN 的行
mask = X.notna().all(axis=1) & y.notna()
X, y = X[mask], y[mask]
```

**铁律**：
- 黑名单特征绝不进入训练输入
- 未通过 Alphalens 筛选的特征绝不进入训练输入

## Step 2: Split — 时序分割

```python
from sklearn.model_selection import TimeSeriesSplit

tscv = TimeSeriesSplit(n_splits=5)
# 最后一个 fold 作为测试集，其余累积作为训练集
# 禁止 shuffle、禁止 KFold、禁止随机分割
```

**铁律**：
- 禁止 `train_test_split(X, y, shuffle=True)`
- 禁止 `KFold`（会打乱时间顺序）
- 训练集必须严格在测试集之前

## Step 3: Train — 固定参数

```python
import lightgbm as lgb

# 固定超参数，不随意调
# 当前使用二分类目标（预测个股是否跑赢赛道当日中位数）
DEFAULT_PARAMS = {
    "objective": "binary",
    "metric": "binary_logloss",
    "boosting_type": "gbdt",
    "num_leaves": 31,
    "max_depth": 8,
    "min_child_samples": 20,
    "min_child_weight": 0.001,
    "learning_rate": 0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.9,
    "bagging_freq": 3,
    "n_estimators": 1000,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "random_state": 42,
    "verbose": -1,
}

# 每个赛道独立训练
for track_name in track_names:
    X_track, y_track = filter_by_track(X, y, track_name)
    model = lgb.LGBMClassifier(**DEFAULT_PARAMS)
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], callbacks=[lgb.early_stopping(20)])
```

**铁律**：
- 4 个赛道 = 4 个独立模型，绝不共用
- 调参必须有明确理由（如过拟合检测不通过），不能"试试看"

## Step 4: Validate — 过拟合检测

```python
from sklearn.metrics import accuracy_score

train_acc = accuracy_score(y_train, model.predict(X_train))
val_acc = accuracy_score(y_val, model.predict(X_val))
gap = train_acc - val_acc

assert gap < 0.10, f"过拟合！训练Acc={train_acc:.3f}, 验证Acc={val_acc:.3f}, 差距={gap:.3f}"
```

| 情况 | 处理 |
|:-----|:-----|
| gap < 0.10 | ✅ 通过，继续 |
| gap 0.10-0.15 | ⚠️ 警告，记录但可接受 |
| gap > 0.15 | ❌ 过拟合，减少 n_estimators 或增大 reg_lambda 后重训 |

## Step 5: Save

```python
import joblib
import os

os.makedirs("ml/models", exist_ok=True)
joblib.dump(model, f"ml/models/{track_name}.pkl")
```

## Step 6: Log

记录到 model_registry 表：

```python
log_model(
    track_name=track_name,
    version=datetime.now().strftime("%Y%m%d_%H%M%S"),
    n_features=len(feature_names),
    train_r2=train_r2,
    test_r2=test_r2,
    feature_importance_top10=top_10_features,
)
```

## 调参规则（防漂移）

| 场景 | 允许的操作 | 禁止的操作 |
|:-----|:----------|:----------|
| 过拟合 gap > 0.25 | 减 n_estimators / 增 reg_lambda | 换模型类型 |
| 欠拟合 R² < 0 | 增 num_leaves / 增 max_depth | 加更多特征（走 add-feature skill） |
| 训练太慢 | 减 n_estimators / 用 early_stopping | 换 XGBoost/CatBoost |
| 效果好想更好 | **停！接受当前结果** | 无限调参追求完美 |

## 重训触发条件

只有以下情况才触发重训：
1. 白名单特征发生变更（Phase C 筛选更新后）
2. 新增数据超过 60 个交易日
3. 模型预测精度连续 30 天低于基准

**禁止**：因为"觉得可以更好"而重训。
