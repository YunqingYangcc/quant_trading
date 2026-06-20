---
name: review-phase
description: Review a development phase (A-H) of the track quant system. Reads REAL_DEV_PLAN.md checklist, verifies code files exist and are correct, checks API endpoints, runs validation where applicable. Outputs a structured pass/fail report. Use when user says "/review-phase" or asks to review/check a phase.
---

# Phase Review — 赛道量化系统阶段验收

## Usage

```
/review-phase A    # 验收 Phase A
/review-phase B    # 验收 Phase B
/review-phase all  # 验收所有阶段
```

## Review Workflow

### Step 1: Load Context

1. Read `docs/REAL_DEV_PLAN.md` — 获取目标 Phase 的 Checklist
2. Read `docs/PRD.md` — 获取对应模块的产品需求
3. Identify all checklist items for the target phase

### Step 2: File & Code Verification

For each checklist item, verify:

| Check Type | How |
|:-----------|:----|
| **File exists** | Glob/read the referenced file path |
| **Function/class exists** | Grep for the function/class name in the file |
| **API endpoint** | Read the route file, check `@router` decorator |
| **DB table** | Read the model file, check `__tablename__` |
| **Import chain** | Verify the file is importable (check `__init__.py` exports) |

### Step 3: Logic Spot-Check

For code files that exist, spot-check:

- **shift(1)**: All features/labels have `shift(1)` or `_shift(..., 1)` applied
- **No future leak**: No look-ahead in rolling calculations
- **Error handling**: Try/except or validation on inputs
- **Blacklist respect**: If applicable, code checks whitelist/blacklist before using features

### Step 4: Run Verification (if applicable)

| Phase | Verification Command |
|:------|:--------------------|
| A | `cd backend && python -c "from app.models.track import Track, TrackStock, TrackDataCache; print('Models OK')"` |
| B | `cd backend && python -c "from app.features.features_generic import compute_all_generic_features; print('Features OK')"` |
| C | Check `configs/factor_whitelist.json` exists if screening was run |
| E | Check `ml/models/*.pkl` exist if training was run |
| F | `curl -s http://localhost:8000/api/v1/ml/score/semiconductor 2>/dev/null \|\| echo "Server not running"` |

**Note**: Only run commands if the server/scripts are expected to be working for that phase. Skip if phase is not yet started.

### Step 5: Output Report

Use this exact format:

```markdown
# Phase {X} Review Report

> Review Date: {date}
> Phase Status: {✅ PASS / ⚠️ PARTIAL / ❌ FAIL}

## Checklist

| # | Item | Status | Notes |
|:--|:-----|:------:|:------|
| 1 | {checklist item description} | ✅/⚠️/❌ | {details} |

## File Verification

| File | Exists | Key Functions | shift(1) |
|:-----|:------:|:-------------|:--------:|
| {path} | ✅/❌ | {list} | ✅/❌/N/A |

## Issues & Blockers

### Critical (must fix)
- {issue description}

### Warnings (should fix)
- {warning description}

### Suggestions (nice to have)
- {suggestion description}

## Summary

- **Checklist items**: X/Y passed
- **Files verified**: X/Y exist
- **Critical issues**: X
- **Recommendation**: {PASS / PARTIAL PASS / BLOCKED}

## Next Phase Readiness

{Brief assessment of whether the phase is ready to move to the next one,
 and what prerequisites remain if not}
```

## Phase-Specific Checks

### Phase A: Data Pipeline
- [ ] `scripts/fetch_track_data.py` exists and imports baostock
- [ ] `datas/tracks/{semiconductor,ai,robot,storage}/` directories have CSV files
- [ ] DB has 5 tables: tracks, track_stocks, track_stock, track_data_cache, feature_white_list, feature_black_list
- [ ] Labels API returns data with fwd_1d/5d/20d_return columns
- [ ] Frontend TrackDashboard.vue renders K-line chart

### Phase B: Feature Engineering
- [ ] `features_generic.py` uses pandas-ta (not hand-written numpy for standard indicators)
- [ ] `features_track.py` has track-specific features
- [ ] `scripts/compute_features.py` exists: DB load → compute → store
- [ ] All features have `shift(1)` applied
- [ ] Feature count ≥ 60
- [ ] NaN ratio < 50% per feature

### Phase C: Alphalens Screening
- [ ] alphalens-reloaded is used (not hand-written IC/IR)
- [ ] IC ≥ 0.02, IR ≥ 0.5, monotonic decile returns
- [ ] WhiteList/BlackList tables populated
- [ ] `configs/factor_whitelist.json` exists
- [ ] Blacklisted factors are never imported in training code

### Phase D: Feature Preprocessing
- [ ] StandardScaler from sklearn (not hand-written)
- [ ] Correlation > 0.95 pairs removed
- [ ] Time-based train/val/test split (no shuffle)

### Phase E: LightGBM Training
- [ ] 6 separate models (one per track)
- [ ] TimeSeriesSplit used (no shuffle)
- [ ] Target: 二分类（高于/低于赛道当日中位数）
- [ ] Models saved to `ml/models/{track}.pkl`
- [ ] Train/Val accuracy gap < 0.10

### Phase F: Scoring API
- [ ] Stock score (0-100) within track
- [ ] Track prosperity score (0-100)
- [ ] API endpoint returns scores

### Phase G: Backtest
- [ ] Slippage 0.1%, commission 万三
- [ ] Position limits: single stock ≤20%, single track ≤50%
- [ ] Track prosperity-based position reduction
- [ ] Stop loss -15%, take profit +30%
- [ ] Sharpe ≥ 1.2 (当前月频 0.92), max drawdown < 25%

### Phase H: Frontend Visualization
- [ ] K-line + Bollinger bands on main chart
- [ ] Sub-charts: volume, ATR, RSI, track prosperity
- [ ] Stock AI ranking panel (left)
- [ ] Valid factor panel (right)
- [ ] Only whitelisted factors rendered (blacklist hidden)

## Constraints

- **Never modify code** during review — this is read-only verification
- **Never run destructive commands** (drop tables, delete files)
- If the backend server is not running, skip API checks and note it
- Report missing dependencies as warnings, not critical failures
