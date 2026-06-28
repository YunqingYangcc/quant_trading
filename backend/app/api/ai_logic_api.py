"""
龙头股 AI 中长期逻辑 + 买卖价格分析.

POST /api/v1/monitor/ai-logic      — 单只业务逻辑分析
POST /api/v1/monitor/ai-logic/all  — 全量批量分析
POST /api/v1/monitor/ai-price      — 单只买卖价格建议
POST /api/v1/monitor/ai-price/all  — 全量买卖价格建议
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import requests
from fastapi import APIRouter, HTTPException, Body

router = APIRouter()
logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "configs" / "ai_config.json"

SYSTEM_PROMPT = '''你是一个严谨的 A 股科技赛道分析师。你的分析必须基于最新公开可验证的事实，禁止凭空臆测。

数据时效要求（最高优先级）：
- 今天是 2026 年 6 月 28 日。你训练数据截止日期早于此，无法确认 2024 年后最新公告/财报/政策。
- 所有涉及 2024 年后的具体数字（营收、利润、市占率、扩产规模等），必须标注 [需核实] 并提醒用户查阅最新季报。
- 如果某个论断依赖的数据你无法确认是否为最新，标注 [可能过时]，并在 sources 中写明需核实的来源方向。
- 严禁使用 2024 年前的数据当作最新数据，除非明确标注数据年份。

输出规则（违反任何一条 = 分析无效）：
1. 每个论断必须附带可验证依据。无法确认则标记 [推断] 或 [需核实] 并注明核实来源。
2. 不使用模糊表述（如"有望受益""前景广阔"），改为具体数据或直接说"暂无公开数据支持"。
3. 行业地位引用公开排名/份额数据，无法查证则只描述产业链位置并标注 [需核实最新排名]。
4. 成长驱动力引用已公告的扩产计划、新品发布、政策文件等事实，注明公告大致时间。
5. 竞争优势必须对比龙2/竞品的客观差异（产品线、客户、技术路线等）。
6. 风险提示列举具体已知风险（诉讼、政策变动、客户集中度等），不泛泛而谈。

输出格式（严格 JSON）：
{
  "status": "成功",
  "summary": "一句话，仅陈述已验证核心事实，不超过 40 字",
  "data_age_note": "数据时效：基于XX年公开数据，XX年后需自行核实",
  "verifiable_score": 8,
  "verifiable_score_note": "评分依据：...",
  "dimensions": [
    {"label": "行业地位", "content": "...", "sources": "可查于公司年报/行业协会排名"},
    {"label": "成长驱动力", "content": "...", "sources": "可查于公司公告/政府文件"},
    {"label": "竞争优势", "content": "...", "sources": "对比龙2公开财报/产品线"},
    {"label": "风险提示", "content": "...", "sources": "可查于公司公告/行业报告"}
  ]
}

verifiable_score 规则：每个维度 0-3 分，满分 12。扣分项：模糊表述(-1)、无数据支撑(-1)、推断性结论(-1)、使用过时数据(-2)。'''

PRICE_PROMPT = """你是一个严谨的 A 股量化分析师。请基于公开可查数据为以下股票输出买卖价格建议。

数据要求（最高优先级）：必须优先使用最新公开数据（最新财报、公告、市场数据）。无法获取的数据请标注 [缺数据] 并说明可能影响。禁止使用过时数据代替。

价格计算必须综合考虑以下 10 个维度：
当前估值（PE/PB/PS/Forward PE）、行业平均估值、公司成长性、盈利预测、产业趋势、政策影响、资金流向、技术形态（支撑/压力位/均线）、市场风险偏好、安全边际。

输出格式（严格 JSON，所有价格单位为元）：
{
  "status": "成功",
  "current_price_note": "当前股价XX元，PE(TTM)XX，低于/高于行业均值XX",
  "valuation": "低估/合理/高估",
  "comprehensive_score": 72,
  "trade_plan": {
    "should_buy": "是/否/观望",
    "buy_zone": "XX-XX元",
    "position": "XX%",
    "add_zone": "XX-XX元",
    "hold_zone": "XX-XX元",
    "target_1": "XX元",
    "target_2": "XX元",
    "sell_zone": "XX-XX元",
    "risk_sell": "XX-XX元",
    "stop_loss": "XX元",
    "hold_period": "XX个月",
    "expected_return": "XX%",
    "risk_reward": "1:X"
  },
  "conclusion": {
    "new_position": "强烈买入/买入/观望/减仓/回避",
    "existing_position": "加仓/持有/减仓/清仓",
    "reason": "一句话结论依据"
  },
  "triggers": ["财报超预期->上调目标价", "政策变化->重新评估", "资金流出->止损"]
}

所有价格必须有计算依据，不能凭空给出。如果某些维度数据缺失，明确标注。"""


def _get_stock_financial_data(code: str) -> dict:
    """从 DB + 基本面 CSV 获取最新财务/市场数据注入 prompt"""
    import sqlite3
    DB = Path(__file__).resolve().parent.parent.parent / "track_quant.db"
    DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "datas" / "fundamentals"
    result = {}
    # 1. 实时价格
    try:
        conn = sqlite3.connect(str(DB))
        rows = conn.execute(
            "SELECT close_px, volume, amount, trade_date FROM track_data_cache WHERE stock_code=? ORDER BY trade_date DESC LIMIT 60",
            (code,)
        ).fetchall()
        conn.close()
        if rows:
            prices = [r[0] for r in rows if r[0]]
            volumes = [r[1] for r in rows if r[1]]
            latest = rows[0]
            prev = rows[1] if len(rows) > 1 else rows[0]
            chg = round((latest[0] - prev[0]) / prev[0] * 100, 2) if prev[0] and prev[0] > 0 else 0
            ma5 = round(sum(prices[:5]) / min(5, len(prices)), 2) if prices else 0
            ma20 = round(sum(prices[:20]) / min(20, len(prices)), 2) if prices else 0
            avg_vol = round(sum(volumes[:20]) / min(20, len(volumes)), 0) if volumes else 0
            result["latest_price"] = latest[0]
            result["price_date"] = latest[3]
            result["change_pct"] = chg
            result["ma20"] = ma20
            result["ma5"] = ma5
            result["avg_vol_20d"] = avg_vol
    except Exception:
        pass
    # 2. 融资融券数据
    try:
        import pandas as pd
        margin_path = DATA_DIR / "margin_data.csv"
        if margin_path.exists():
            df = pd.read_csv(margin_path)
            if "stock_code" in df.columns:
                row = df[df["stock_code"] == code]
                if not row.empty:
                    r = row.iloc[-1]
                    result["margin_balance"] = str(r.get("margin_balance", "")) if "margin_balance" in r else ""
                    result["short_balance"] = str(r.get("short_balance", "")) if "short_balance" in r else ""
    except Exception:
        pass
    # 3. 股东集中度
    try:
        import pandas as pd
        holder_path = DATA_DIR / "holder_concentration.csv"
        if holder_path.exists():
            df = pd.read_csv(holder_path)
            if "stock_code" in df.columns:
                row = df[df["stock_code"] == code]
                if not row.empty:
                    r = row.iloc[-1]
                    result["top10_holder_pct"] = str(r.get("top10_holder_pct", "")) if "top10_holder_pct" in r else ""
    except Exception:
        pass
    return result
    """从DB获取股票最新真实数据注入prompt"""
    import sqlite3
    DB = Path(__file__).resolve().parent.parent.parent / "track_quant.db"
    try:
        conn = sqlite3.connect(str(DB))
        rows = conn.execute(
            "SELECT close_px, open_px, high_px, low_px, volume, amount, trade_date FROM track_data_cache WHERE stock_code=? ORDER BY trade_date DESC LIMIT 60",
            (code,)
        ).fetchall()
        conn.close()
        if not rows:
            return {}
        prices = [r[0] for r in rows if r[0]]
        volumes = [r[4] for r in rows if r[4]]
        latest = rows[0]
        prev = rows[1] if len(rows) > 1 else rows[0]
        chg = round((latest[0] - prev[0]) / prev[0] * 100, 2) if prev[0] and prev[0] > 0 else 0
        ma5 = round(sum(prices[:5]) / min(5, len(prices)), 2) if prices else 0
        ma20 = round(sum(prices[:20]) / min(20, len(prices)), 2) if prices else 0
        ma60 = round(sum(prices[:60]) / min(60, len(prices)), 2) if prices else 0
        high60 = max(prices) if prices else 0
        low60 = min(prices) if prices else 0
        avg_vol = round(sum(volumes[:20]) / min(20, len(volumes)), 0) if volumes else 0
        return {
            "price": latest[0], "date": latest[6],
            "change_pct": chg,
            "ma5": ma5, "ma20": ma20, "ma60": ma60,
            "high_60d": high60, "low_60d": low60,
            "volume": latest[4], "amount": latest[5], "avg_vol_20d": avg_vol,
        }
    except Exception:
        return {}


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def _load_leaders() -> list[dict]:
    leaders_path = Path(__file__).resolve().parent.parent.parent / "configs" / "sector_leaders.json"
    with open(leaders_path, encoding="utf-8") as f:
        return json.load(f)


def _call_ai(api_key: str, base_url: str, model: str, system_prompt: str, user_prompt: str, max_tokens: int = 1200, timeout: int = 90) -> dict:
    """通用 AI 调用"""
    resp = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
            "max_tokens": max_tokens,
        },
        timeout=timeout,
    )
    if resp.status_code != 200:
        error_detail = resp.json().get("error", {}).get("message", resp.text)
        raise RuntimeError(f"AI 服务错误: {error_detail}")

    content = resp.json()["choices"][0]["message"]["content"]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            return json.loads(match.group())
        return {"status": "成功", "summary": content, "raw": content}


def _get_config() -> tuple:
    config = _load_config()
    return config.get("api_key", ""), config.get("base_url", "https://api.deepseek.com/v1"), config.get("model", "deepseek-chat")


# ── 业务逻辑分析（单只）──
@router.post("/monitor/ai-logic", summary="AI 分析单只龙头业务逻辑")
async def ai_logic_analysis(payload: dict = Body(...)):
    api_key, base_url, model = _get_config()
    api_key = payload.get("api_key") or api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="缺少 API Key")
    stock = payload.get("stock", {})
    fin = _get_stock_financial_data(stock["code"])
    data_block = ""
    if fin:
        data_block = f"""
【最新真实市场数据（来自数据库，非模型训练数据）】
最新收盘价: {fin.get('latest_price','?')}元 (日期: {fin.get('price_date','?')})
今日涨跌幅: {fin.get('change_pct','?')}%
MA5: {fin.get('ma5','?')}  MA20: {fin.get('ma20','?')}
20日均量: {fin.get('avg_vol_20d','?')}
融资余额: {fin.get('margin_balance','未获取')}
融券余额: {fin.get('short_balance','未获取')}
前十大股东持股: {fin.get('top10_holder_pct','未获取')}
请基于以上真实最新数据进行分析，不要使用训练数据中的过时数字。
"""
    else:
        data_block = "【注意：无法获取最新真实数据，必须标注 [缺实时数据]】\n"
    user_prompt = f"""请分析以下龙头股的中长期投资逻辑：\n股票名称：{stock['name']}\n股票代码：{stock['code']}\n所属赛道：{stock['track']}\n细分环节：{stock['segment']}\n定位：{stock['position']}\n{data_block}\n请按 JSON 格式输出。"""
    try:
        result = _call_ai(api_key, base_url, model, SYSTEM_PROMPT, user_prompt, 1000, 45)
        return {"stock": stock, "analysis": result, "real_data": fin, "model": model, "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── 业务逻辑分析（全量批量）──
@router.post("/monitor/ai-logic/all", summary="每日全量业务逻辑分析")
async def ai_logic_all():
    api_key, base_url, model = _get_config()
    if not api_key:
        raise HTTPException(status_code=400, detail="缺少 API Key")
    leaders = _load_leaders()
    results, failed = [], []
    for i, stock in enumerate(leaders):
        try:
            user_prompt = f"""请分析以下龙头股的中长期投资逻辑：\n股票名称：{stock['name']}\n股票代码：{stock['code']}\n所属赛道：{stock['track']}\n细分环节：{stock['segment']}\n定位：{stock['position']}\n请按 JSON 格式输出。"""
            analysis = _call_ai(api_key, base_url, model, SYSTEM_PROMPT, user_prompt, 1000, 45)
            results.append({"stock": stock, "analysis": analysis, "status": "success"})
        except Exception as e:
            logger.warning(f"  {stock['name']} 失败: {e}")
            failed.append({"name": stock["name"], "code": stock["code"], "error": str(e)})
    return {"total": len(leaders), "success": len(results), "failed": len(failed), "model": model, "results": results, "failures": failed, "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


# ── 买卖价格分析（单只）──
@router.post("/monitor/ai-price", summary="AI 买卖价格建议")
async def ai_price_analysis(payload: dict = Body(...)):
    api_key, base_url, model = _get_config()
    api_key = payload.get("api_key") or api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="缺少 API Key")
    stock = payload.get("stock", {})
    real = _get_stock_real_data(stock["code"])
    data_block = ""
    if real:
        data_block = f"""
【最新真实市场数据（来自数据库，非模型训练数据）】
最新收盘价: {real['price']}元 (日期: {real['date']})
今日涨跌幅: {real['change_pct']}%
MA5: {real['ma5']}  MA20: {real['ma20']}  MA60: {real['ma60']}
60日最高: {real['high_60d']}  60日最低: {real['low_60d']}
最新成交量: {real['volume']}  20日均量: {real['avg_vol_20d']}
请基于以上真实数据计算买卖价格，不要使用训练数据中的过时价格。
"""
    else:
        data_block = "【注意：无法获取最新真实数据，请基于公开知识估算，并标注 [缺实时数据]】\n"
    user_prompt = f"""请为以下股票输出买卖价格建议：\n股票名称：{stock['name']}\n股票代码：{stock['code']}\n所属赛道：{stock['track']}\n细分环节：{stock['segment']}\n定位：{stock['position']}\n{data_block}\n请按 JSON 格式输出，所有价格以元为单位。"""
    try:
        result = _call_ai(api_key, base_url, model, PRICE_PROMPT, user_prompt, 1500, 90)
        return {"stock": stock, "analysis": result, "real_data": real, "model": model, "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── 买卖价格分析（全量批量）──
@router.post("/monitor/ai-price/all", summary="全量买卖价格建议")
async def ai_price_all():
    api_key, base_url, model = _get_config()
    if not api_key:
        raise HTTPException(status_code=400, detail="缺少 API Key")
    leaders = _load_leaders()
    results, failed = [], []
    for i, stock in enumerate(leaders):
        try:
            user_prompt = f"""请为以下股票输出买卖价格建议：\n股票名称：{stock['name']}\n股票代码：{stock['code']}\n所属赛道：{stock['track']}\n细分环节：{stock['segment']}\n定位：{stock['position']}\n请按 JSON 格式输出。"""
            analysis = _call_ai(api_key, base_url, model, PRICE_PROMPT, user_prompt, 1500, 90)
            results.append({"stock": stock, "analysis": analysis, "status": "success"})
        except Exception as e:
            logger.warning(f"  {stock['name']} 价格分析失败: {e}")
            failed.append({"name": stock["name"], "code": stock["code"], "error": str(e)})
    return {"total": len(leaders), "success": len(results), "failed": len(failed), "model": model, "results": results, "failures": failed, "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
