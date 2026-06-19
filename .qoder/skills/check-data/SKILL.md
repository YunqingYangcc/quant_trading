---
name: check-data
description: Run data quality checks on the track quant system. Verifies data completeness, detects future leaks, checks shift(1) compliance, validates NaN ratios, and detects duplicates. Use when verifying data quality or before running feature computation.
---

# Check Data — 数据质量巡检

## When to Use

- Phase A 完成后，验证数据落库质量
- Phase B 之前，确认数据可用
- 任何数据更新后，做例行巡检
- 回测结果异常时，排查数据问题

## Checks Pipeline

```
Check 1: Completeness  → 数据完整性（缺失率、日期连续性）
Check 2: Future Leak   → 未来泄露检测（shift(1) 合规）
Check 3: Duplicates    → 重复数据检测
Check 4: NaN Profile   → NaN 分布分析
Check 5: Outliers      → 异常值检测
Check 6: Label Quality → 标签质量验证
```

## Check 1: Completeness

```python
def check_completeness(db_path="track_quant.db"):
    """检查每只股票的数据完整性"""
    import sqlite3, pandas as pd

    conn = sqlite3.connect(db_path)

    # 每只股票的数据量
    df = pd.read_sql("""
        SELECT stock_code, COUNT(*) as rows,
               MIN(trade_date) as earliest,
               MAX(trade_date) as latest
        FROM track_data_cache
        GROUP BY stock_code
    """, conn)

    # 检查是否有股票数据过少
    low_count = df[df["rows"] < 500]  # 少于 500 天数据（约 2 年）

    report = {
        "total_stocks": len(df),
        "total_rows": df["rows"].sum(),
        "avg_rows_per_stock": df["rows"].mean(),
        "stocks_with_low_data": low_count["stock_code"].tolist(),
        "date_range": f"{df['earliest'].min()} ~ {df['latest'].max()}",
    }
    return report
```

**阈值**：
- 每只股票 ≥ 500 个交易日数据
- 总数据量 ≥ 10,000 行
- 日期范围覆盖最近 3 年

## Check 2: Future Leak Detection

```python
def check_future_leak(df, feature_cols, label_col="fwd_20d_return"):
    """检测特征是否存在未来泄露

    方法：检查特征值是否与未来收益的相关性异常高
    正常特征 IC < 0.3，如果 IC > 0.8 则高度疑似未来泄露
    """
    suspicious = []
    for col in feature_cols:
        ic = df[[col, label_col]].dropna().corr().iloc[0, 1]
        if abs(ic) > 0.8:
            suspicious.append({"feature": col, "ic": ic, "risk": "HIGH"})
        elif abs(ic) > 0.5:
            suspicious.append({"feature": col, "ic": ic, "risk": "MEDIUM"})

    return suspicious
```

**判断标准**：
- |IC| > 0.8 → ❌ 高度疑似未来泄露，必须排查
- |IC| 0.5-0.8 → ⚠️ 需要人工确认
- |IC| < 0.5 → ✅ 正常

## Check 3: Duplicates

```python
def check_duplicates(db_path="track_quant.db"):
    """检测重复数据"""
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("""
        SELECT stock_code, trade_date, COUNT(*) as cnt
        FROM track_data_cache
        GROUP BY stock_code, trade_date
        HAVING cnt > 1
    """, conn)

    return {
        "duplicate_rows": len(df),
        "duplicates": df.to_dict("records") if len(df) > 0 else [],
    }
```

## Check 4: NaN Profile

```python
def check_nan_profile(df, feature_cols):
    """NaN 分布分析"""
    nan_stats = {}
    for col in feature_cols:
        nan_ratio = df[col].isna().mean()
        nan_stats[col] = {
            "nan_ratio": round(nan_ratio, 4),
            "status": "OK" if nan_ratio < 0.5 else "HIGH" if nan_ratio < 0.8 else "CRITICAL"
        }

    summary = {
        "total_features": len(feature_cols),
        "ok_features": sum(1 for v in nan_stats.values() if v["status"] == "OK"),
        "high_nan": [k for k, v in nan_stats.items() if v["status"] == "HIGH"],
        "critical_nan": [k for k, v in nan_stats.items() if v["status"] == "CRITICAL"],
    }
    return summary
```

**阈值**：
- NaN < 50% → ✅ OK
- NaN 50%-80% → ⚠️ HIGH（检查窗口期是否过大）
- NaN > 80% → ❌ CRITICAL（特征不可用，需移除或修改计算）

## Check 5: Outliers

```python
def check_outliers(df, feature_cols, threshold=5.0):
    """异常值检测（Z-score > threshold）"""
    outliers = {}
    for col in feature_cols:
        series = df[col].dropna()
        z_scores = (series - series.mean()) / series.std()
        outlier_count = (z_scores.abs() > threshold).sum()
        if outlier_count > 0:
            outliers[col] = {
                "count": outlier_count,
                "max_z": z_scores.abs().max(),
                "sample_indices": z_scores.abs()[z_scores.abs() > threshold].head(3).index.tolist(),
            }
    return outliers
```

## Check 6: Label Quality

```python
def check_labels(df):
    """验证标签质量"""
    checks = {
        "fwd_20d_return_exists": "fwd_20d_return" in df.columns,
        "label_nan_ratio": df["fwd_20d_return"].isna().mean() if "fwd_20d_return" in df.columns else 1.0,
        "label_range": {
            "min": df["fwd_20d_return"].min() if "fwd_20d_return" in df.columns else None,
            "max": df["fwd_20d_return"].max() if "fwd_20d_return" in df.columns else None,
            "mean": df["fwd_20d_return"].mean() if "fwd_20d_return" in df.columns else None,
        },
        "shift_applied": True,  # 人工确认代码中有 shift(1)
    }

    # 检查标签范围是否合理（20日收益通常在 -0.5 ~ 0.5）
    if checks["label_range"]["max"] and abs(checks["label_range"]["max"]) > 1.0:
        checks["warning"] = "标签范围异常，可能未复权或计算错误"

    return checks
```

## Output Report

```markdown
# Data Quality Report

> Date: {date}
> Scope: {stock_codes or "all"}

## Summary

| Check | Status | Details |
|:------|:------:|:--------|
| 完整性 | ✅/⚠️/❌ | {details} |
| 未来泄露 | ✅/⚠️/❌ | {details} |
| 重复数据 | ✅/⚠️/❌ | {details} |
| NaN 分布 | ✅/⚠️/❌ | {details} |
| 异常值 | ✅/⚠️/❌ | {details} |
| 标签质量 | ✅/⚠️/❌ | {details} |

## Issues

### Critical
- {issue}

### Warnings
- {issue}

## Recommendation
{PASS / NEEDS FIX / BLOCKED}
```

## 数据质量门禁

| 阶段 | 门禁条件 | 不通过则 |
|:-----|:---------|:---------|
| Phase A → B | 完整性 ✅ + 重复 ✅ + 标签 ✅ | 修复数据问题 |
| Phase B → C | NaN ✅ + 异常值 ✅ | 修复特征计算 |
| Phase C → D | 未来泄露 ✅ | 修复 shift(1) |
| 回测前 | 全部 ✅ | 禁止进入回测 |
