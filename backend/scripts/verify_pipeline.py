"""
端到端流水线健康检查脚本。

检查项：
  1. 所有活跃赛道是否有已训练模型
  2. 模型是否可加载（joblib）并正常 predict_proba
  3. 特征列一致性（训练时 vs 打分时）
  4. 数据完整性快速抽查
  5. 打分 API 是否返回有效结果

Usage:
    cd backend && python3 scripts/verify_pipeline.py
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.db.database import async_session_maker, ensure_database_ready
from app.models.track import Track, track_stock

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "ml" / "models"
PREPROCESSED_DIR = BASE_DIR / "ml" / "preprocessed"

CHECK_PASS = "✅"
CHECK_FAIL = "❌"
CHECK_WARN = "⚠️"


async def check_1_active_tracks() -> list[dict]:
    """检查 1: 活跃赛道列表."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Track).where(Track.is_active == 1)
        )
        tracks = result.scalars().all()
    return [{"name": t.name, "display_name": t.display_name} for t in tracks]


async def check_2_models_exist(tracks: list[dict]) -> list[dict]:
    """检查 2: 每个赛道是否有模型文件."""
    results = []
    for track in tracks:
        name = track["name"]
        pkl = MODELS_DIR / f"{name}.pkl"
        meta = MODELS_DIR / f"{name}_meta.json"
        exists = pkl.exists()
        meta_exists = meta.exists()
        status = CHECK_PASS if exists else CHECK_FAIL
        meta_status = CHECK_PASS if meta_exists else CHECK_WARN
        results.append({
            "track": name,
            "display": track["display_name"],
            "model_file": status,
            "meta_file": meta_status,
            "pkl_path": str(pkl) if exists else "MISSING",
        })
    return results


def check_3_models_loadable(model_results: list[dict]) -> list[dict]:
    """检查 3: 模型是否可加载并预测."""
    results = []
    for mr in model_results:
        if mr["model_file"] != CHECK_PASS:
            results.append({**mr, "loadable": CHECK_FAIL, "predictable": CHECK_FAIL, "error": "No model file"})
            continue

        pkl_path = MODELS_DIR / f"{mr['track']}.pkl"
        try:
            model = joblib.load(pkl_path)
            # 尝试用一个 dummy 输入预测
            with open(PREPROCESSED_DIR / "feature_cols.json") as f:
                feature_cols = json.load(f)
            dummy = np.random.randn(1, len(feature_cols))
            pred = model.predict_proba(dummy)
            results.append({
                **mr,
                "loadable": CHECK_PASS,
                "predictable": CHECK_PASS,
                "pred_shape": str(pred.shape),
                "pred_sample": round(float(pred[0][1]), 4),
            })
        except Exception as e:
            results.append({
                **mr,
                "loadable": CHECK_FAIL,
                "predictable": CHECK_FAIL,
                "error": str(e)[:120],
            })

    return results


def check_4_feature_consistency() -> dict:
    """检查 4: 特征列一致性."""
    try:
        with open(PREPROCESSED_DIR / "feature_cols.json") as f:
            feature_cols = json.load(f)

        # 检查 train.parquet 中是否有这些列
        train = pd.read_parquet(PREPROCESSED_DIR / "train.parquet")
        missing = [c for c in feature_cols if c not in train.columns]

        return {
            "status": CHECK_PASS if not missing else CHECK_FAIL,
            "feature_count": len(feature_cols),
            "train_columns": len(train.columns),
            "missing_in_train": missing,
            "train_rows": len(train),
        }
    except Exception as e:
        return {"status": CHECK_FAIL, "error": str(e)[:120]}


def check_5_data_quality() -> dict:
    """检查 5: 数据质量快速抽查."""
    try:
        train = pd.read_parquet(PREPROCESSED_DIR / "train.parquet")
        val = pd.read_parquet(PREPROCESSED_DIR / "val.parquet")
        test = pd.read_parquet(PREPROCESSED_DIR / "test.parquet")

        # 检查时序分割是否正确
        train_max = train["date"].max() if "date" in train.columns else "N/A"
        val_min = val["date"].min() if "date" in val.columns else "N/A"
        val_max = val["date"].max() if "date" in val.columns else "N/A"
        test_min = test["date"].min() if "date" in test.columns else "N/A"

        # 检查 NaN 比例
        with open(PREPROCESSED_DIR / "feature_cols.json") as f:
            feature_cols = json.load(f)
        existing_cols = [c for c in feature_cols if c in train.columns]
        nan_ratio = train[existing_cols].isna().mean().mean() if existing_cols else 1.0

        # 检查 target 列
        target_ok = "target" in train.columns

        return {
            "status": CHECK_PASS if nan_ratio < 0.1 and target_ok else CHECK_WARN,
            "train_max_date": str(train_max),
            "val_range": f"{val_min} ~ {val_max}",
            "test_min_date": str(test_min),
            "nan_ratio": round(float(nan_ratio), 4),
            "target_exists": target_ok,
            "total_samples": len(train) + len(val) + len(test),
        }
    except Exception as e:
        return {"status": CHECK_FAIL, "error": str(e)[:120]}


def check_6_backtest_results() -> dict:
    """检查 6: 回测结果文件."""
    report_path = BASE_DIR / "ml" / "backtest" / "backtest_report.json"
    curve_path = BASE_DIR / "ml" / "backtest" / "equity_curve.csv"

    report_exists = report_path.exists()
    curve_exists = curve_path.exists()

    if report_exists:
        try:
            with open(report_path) as f:
                report = json.load(f)
            # 检查是否是多策略报告
            if isinstance(report, list):
                strategies = [r.get("name", "?") for r in report]
                sharpe_values = {r["name"]: r.get("sharpe_ratio", 0) for r in report}
            else:
                strategies = ["single"]
                sharpe_values = {"single": report.get("metrics", {}).get("sharpe_ratio", 0)}
            return {
                "status": CHECK_PASS,
                "report_exists": True,
                "curve_exists": curve_exists,
                "strategies": strategies,
                "sharpe_values": sharpe_values,
            }
        except Exception as e:
            return {"status": CHECK_WARN, "report_exists": True, "error": str(e)[:120]}

    return {
        "status": CHECK_WARN,
        "report_exists": False,
        "curve_exists": curve_exists,
        "message": "回测报告未生成，运行 python3 scripts/run_backtest.py",
    }


def print_report(checks: dict):
    """打印格式化报告."""
    print("\n" + "=" * 70)
    print("  TrackQuant 端到端流水线健康检查报告")
    print("=" * 70)

    # 检查 1-2: 赛道 & 模型
    tracks = checks.get("active_tracks", [])
    models = checks.get("models", [])
    print(f"\n📊 活跃赛道: {len(tracks)} 个")
    for t in tracks:
        print(f"   • {t['name']} ({t['display_name']})")

    print(f"\n📦 模型文件:")
    all_models_ok = True
    for m in models:
        ok = m["model_file"] == CHECK_PASS
        all_models_ok = all_models_ok and ok
        load = m.get("loadable", CHECK_WARN)
        pred = m.get("predictable", CHECK_WARN)
        pred_info = f"p={m.get('pred_sample', 'N/A')}" if load == CHECK_PASS else ""
        print(f"   {m['model_file']} {load} {pred} {m['track']:15s} {pred_info}")
        if m.get("error"):
            print(f"      ⚠️ {m['error']}")

    # 检查 4: 特征
    fc = checks.get("feature_consistency", {})
    print(f"\n🔧 特征一致性: {fc.get('status', CHECK_FAIL)}")
    print(f"   特征数: {fc.get('feature_count', '?')}, 训练集列数: {fc.get('train_columns', '?')}, 行数: {fc.get('train_rows', '?'):,}")
    if fc.get("missing_in_train"):
        print(f"   ❌ 缺失列: {fc['missing_in_train']}")

    # 检查 5: 数据质量
    dq = checks.get("data_quality", {})
    print(f"\n🔍 数据质量: {dq.get('status', CHECK_FAIL)}")
    print(f"   NaN 比例: {dq.get('nan_ratio', '?')}")
    print(f"   总样本: {dq.get('total_samples', '?'):,}")
    print(f"   时序: train≤{dq.get('train_max_date', '?')} | val={dq.get('val_range', '?')} | test≥{dq.get('test_min_date', '?')}")
    print(f"   target列: {'✅' if dq.get('target_exists') else '❌'}")

    # 检查 6: 回测
    bt = checks.get("backtest", {})
    print(f"\n📈 回测结果: {bt.get('status', CHECK_WARN)}")
    if bt.get("report_exists"):
        strategies = bt.get("strategies", [])
        sharpe = bt.get("sharpe_values", {})
        for s in strategies:
            sv = sharpe.get(s, 0)
            sv_flag = "✅" if sv >= 1.2 else ("⚠️" if sv >= 0.5 else "❌")
            print(f"   {sv_flag} {s}: 夏普 {sv:.3f}")
    else:
        print(f"   {bt.get('message', 'N/A')}")

    # 总结
    print(f"\n{'=' * 70}")
    all_pass = all_models_ok and fc.get("status") == CHECK_PASS
    print(f"  总评: {'✅ 流水线健康' if all_pass else '⚠️ 存在问题，详见上方'} ")
    print("=" * 70)


async def main():
    await ensure_database_ready()

    checks = {}

    # 1. 活跃赛道
    tracks = await check_1_active_tracks()
    checks["active_tracks"] = tracks

    # 2. 模型文件
    model_results = await check_2_models_exist(tracks)
    checks["models"] = model_results

    # 3. 模型可加载性
    checks["models"] = check_3_models_loadable(model_results)

    # 4. 特征一致性
    checks["feature_consistency"] = check_4_feature_consistency()

    # 5. 数据质量
    checks["data_quality"] = check_5_data_quality()

    # 6. 回测结果
    checks["backtest"] = check_6_backtest_results()

    print_report(checks)


if __name__ == "__main__":
    asyncio.run(main())
