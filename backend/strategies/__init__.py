"""
量化策略注册表。

每个策略是一个 SignalGenerator：
  generate(prices: pd.DataFrame, features=None, ai_scores=None) -> pd.DataFrame

返回 DataFrame，index=date, columns 包含 'buy' (list[str]) 和可选的 'weights' (dict[str,float])。

所有策略支持 AI 打分增强：传入 ai_scores 后，策略信号会被 AI 评分二次排序。

━━ 策略适配指南 ━━
新加策略只需 3 步：
  1. 在 strategies/ 下新建 .py 文件
  2. 类继承 SignalGenerator，实现 generate() 方法
  3. 在 __init__.py 中 import 你的模块 + 调用 register_strategy()

示例：
    from strategies.signal_base import register_strategy

    register_strategy(
        key="my_strat",
        name="我的策略",
        strategy_type="technical",
        description="一句话简介",
        mechanism="大白话解释怎么选股",
        market_condition="适用什么行情",
        expected_effect="预期什么效果",
        limitations="注意什么风险",
        params_detail={"period": "参数说明"},
    )
"""

from strategies.equal_weight import EqualWeightStrategy
from strategies.momentum import MomentumStrategy
from strategies.ai_scoring import AIScoringStrategy
from strategies.trend import MACrossStrategy, BreakoutStrategy
from strategies.mean_reversion import RSIStrategy, BollingerStrategy
from strategies.composite import MultiSignalVoting, AIConfidenceStrategy, AIFilterMixin
from strategies.macd import MACDCrossStrategy
from strategies.kdj import KDJStrategy
from strategies.volume_breakout import VolumeBreakoutStrategy
from strategies.bollinger_squeeze import BollingerSqueezeStrategy
from strategies.turtle import TurtleStrategy
from strategies.triple_ma import TripleMAStrategy

from strategies.signal_base import (
    SignalGenerator, AIEnhanceMixin, to_single_stock_signals,
    register_strategy, get_strategy_instance, get_strategy_meta,
    list_registered_strategies,
)

# ════════════════════════════════════════════════════════════════
# 策略注册 —— @register_strategy 装饰器方式
# 兼容旧接口：保持 STRATEGY_REGISTRY + get_strategy() + list_strategies()
# ════════════════════════════════════════════════════════════════

# ── 基线 ──

register_strategy(
    key="equal_weight",
    name="等权持有",
    strategy_type="baseline",
    description="等权持有所有赛道股票，不选股，作为最低基准",
    mechanism="所有选入赛道的股票分配相同权重，不依赖任何预测信号，纯被动持有",
    market_condition="任何时候（作为其他策略的对比基准）",
    expected_effect="收益等于赛道平均收益，跑赢它说明策略有效",
    limitations="本身不产生超额收益，只用于衡量其他策略是否值得使用",
    params_detail={
        "N/A": "无参数，就是最简单的等权持有",
    },
)(EqualWeightStrategy)

# ── 动量策略 ──

register_strategy(
    key="momentum_20d",
    name="20日动量 Top-3",
    strategy_type="momentum",
    description="按过去20日收益率排序，月频买入前3名",
    mechanism="计算每只股票过去20个交易日的累计涨幅，涨幅最高的前3只买入持有到下次调仓",
    market_condition="上涨趋势市（大盘整体向上时效果最好）",
    expected_effect="在大盘上涨阶段能跑赢等权基准 5-15%/年，震荡市表现平庸",
    limitations="遇到突发大跌或急转行情会踩踏；震荡市频繁换股反而亏手续费",
    params_detail={
        "lookback": "动量计算回溯天数，越短越敏感",
        "top_n": "每次调仓买入几只",
        "rebalance": "调仓频率，M=月频 W=周频",
        "vol_filter": "是否限制只在高波动池中选股",
    },
)(MomentumStrategy(lookback=20, top_n=3, rebalance="M"))

register_strategy(
    key="momentum_60d",
    name="60日动量 Top-3",
    strategy_type="momentum",
    description="按过去60日收益率排序，月频买入前3名",
    mechanism="计算每只股票过去60个交易日的累计涨幅，涨幅最高的前3只买入持有到下次调仓",
    market_condition="中长期上涨趋势市",
    expected_effect="比20日动量更稳健，回撤更小，但拐点反应更慢",
    limitations="在快速上涨行情中跑不赢20日动量；震荡市信号滞后",
    params_detail={
        "lookback": "动量计算回溯天数",
        "top_n": "每次调仓买入几只",
        "rebalance": "调仓频率",
    },
)(MomentumStrategy(lookback=60, top_n=3, rebalance="M"))

register_strategy(
    key="momentum_20d_vol",
    name="20日动量+波动率 Top-3",
    strategy_type="momentum",
    description="高波动组中选20日动量最强Top-3（Blitz 2011残差动量）",
    mechanism="筛选波动率高于赛道中位数的股票再按动量排序选Top-3，聚焦高活跃度个股",
    market_condition="高波动的上涨趋势市",
    expected_effect="在赛道内部分化明显时，聚焦高活跃股能提高选股胜率",
    limitations="低波动环境下选股池缩小，信号稀疏",
    params_detail={
        "lookback": "动量计算回溯天数",
        "top_n": "选股数量",
        "vol_filter": "波动率过滤开关",
    },
)(MomentumStrategy(lookback=20, top_n=3, rebalance="M", vol_filter=True))

register_strategy(
    key="momentum_20d_ai",
    name="20日动量+AI增强",
    strategy_type="momentum",
    description="20日动量选股 + AI 打分二次排序",
    mechanism="先用20日动量选出候选池，再用AI模型打分重新排序，只保留得分最高的Top-3",
    market_condition="AI模型有效的任何市场（需模型训练充分）",
    expected_effect="预期比纯动量策略提升夏普 0.2-0.5，减少踩雷概率",
    limitations="依赖AI模型质量；模型过拟合期会降低效果",
    params_detail={
        "lookback": "动量计算回溯天数",
        "top_n": "选股数量",
        "ai_enhanced": "AI增强开关",
    },
)(MomentumStrategy(lookback=20, top_n=3, rebalance="M", ai_enhanced=True))

# ── 技术指标策略 ──

register_strategy(
    key="ma_cross",
    name="MA金叉死叉 Top-3",
    strategy_type="technical",
    description="5日均线上穿20日线买入，死叉卖出，AI+增强版本可选",
    mechanism="跟踪每只股票的5日均线和20日均线，短期均线上穿长期均线（金叉）时买入，下穿（死叉）时卖出",
    market_condition="有明显趋势的行情——上涨趋势反复出金叉，下跌趋势反复出死叉",
    expected_effect="趋势市能抓中段主升浪，避开下跌段；震荡市频繁假信号",
    limitations="震荡市频繁金叉死叉反复被割；滞后于价格变化，大涨开头抓不住",
    params_detail={
        "short_window": "短期均线天数，越小对价格越敏感",
        "long_window": "长期均线天数，越大越稳健但越滞后",
        "top_n": "同一天最多买入几只",
    },
)(MACrossStrategy(short_window=5, long_window=20, top_n=3))

register_strategy(
    key="ma_cross_ai",
    name="MA金叉+AI增强",
    strategy_type="technical",
    description="金叉选股 + AI 打分排序增强",
    mechanism="所有金叉股票中，用AI模型打分筛选质量最高的",
    market_condition="AI有效时（模型训练充分）",
    expected_effect="过滤掉金叉中的假信号，提高胜率",
    limitations="金叉数量本身少的行情下，AI筛选空间有限",
    params_detail={
        "short_window": "短期均线天数",
        "long_window": "长期均线天数",
        "top_n": "选股数量",
    },
)(MACrossStrategy(short_window=5, long_window=20, top_n=3))

register_strategy(
    key="breakout",
    name="20日突破 Top-3",
    strategy_type="technical",
    description="创20日新高买入，新低卖出",
    mechanism="当股票价格创出近20个交易日的新高时买入，创出新低时卖出",
    market_condition="强势上涨趋势市（突破信号在牛市中准确率最高）",
    expected_effect="在大牛市中能抓住主升浪；熊市中频繁假突破导致亏损",
    limitations="假突破在震荡市中非常常见——刚突破买入就跌回来",
    params_detail={
        "lookback": "突破观察窗口天数",
        "top_n": "选股数量",
    },
)(BreakoutStrategy(lookback=20, top_n=3))

register_strategy(
    key="breakout_ai",
    name="突破+AI增强",
    strategy_type="technical",
    description="突破选股 + AI 打分排序增强",
    mechanism="突破信号股票用AI打分过滤，只买入AI评分最高的",
    market_condition="AI模型有效时",
    expected_effect="减少假突破带来的亏损，提高突破信号胜率",
    limitations="突破信号本身较少时，AI筛选会进一步减少交易机会",
    params_detail={
        "lookback": "突破观察窗口",
        "top_n": "选股数量",
    },
)(BreakoutStrategy(lookback=20, top_n=3))

# ── 均值回归策略 ──

register_strategy(
    key="rsi_reversal",
    name="RSI超卖反转",
    strategy_type="mean_reversion",
    description="RSI<30超卖买入，RSI>70超买卖出",
    mechanism="RSI指标低于30（超卖区）时买入，预期价格会反弹回均值；RSI高于70（超买区）时卖出",
    market_condition="震荡市/横盘整理（价格围绕均值上下波动时最有效）",
    expected_effect="震荡市中能低买高卖，预期年化超额收益 5-10%",
    limitations="单边大涨行情中，超卖信号很少错过上涨；单边大跌中抄底抄在半山腰",
    params_detail={
        "period": "RSI计算周期，14日为标准",
        "oversold": "超卖阈值，越低买入条件越严格",
        "overbought": "超买阈值，越高卖出条件越严格",
        "top_n": "选股数量",
    },
)(RSIStrategy(period=14, oversold=30, overbought=70, top_n=3))

register_strategy(
    key="bollinger_reversal",
    name="布林带均值回归",
    strategy_type="mean_reversion",
    description="触及下轨买入，触及上轨卖出",
    mechanism="价格跌破布林带下轨（2倍标准差）时买入，突破上轨时卖出，赌价格回归均值",
    market_condition="横盘震荡或宽幅震荡市",
    expected_effect="强震荡市中效果极佳，能精准低买高卖",
    limitations="突破上下轨意味着强趋势——追趋势的行情中抄底可能亏更多",
    params_detail={
        "period": "布林带计算周期",
        "std_dev": "标准差倍数，越大信号越少但越可靠",
        "top_n": "选股数量",
    },
)(BollingerStrategy(period=20, std_dev=2.0, top_n=3))

# ── AI 策略 ──

register_strategy(
    key="ai_scoring",
    name="AI 打分轮动",
    strategy_type="ai",
    description="LightGBM 模型预测赛道内相对强弱，买Top-3",
    mechanism="用训练好的LightGBM模型对赛道内每只股票打分，买入预测得分最高的前3只",
    market_condition="模型充分训练的赛道（需定期重新训练）",
    expected_effect="预期夏普 1.0-1.5，赛道内最强策略之一",
    limitations="完全依赖模型质量；市场风格突变时模型失效；需要模型训练流水线支撑",
    params_detail={
        "N/A": "自动使用最新训练的模型打分",
    },
)(AIScoringStrategy())

register_strategy(
    key="ai_confidence",
    name="AI 置信度分层轮动",
    strategy_type="ai",
    description="AI高分重仓、低分轻仓、低于0.5不买",
    mechanism="AI打分>=0.8的股票重仓(50%)，0.6-0.8的配置(30%)，0.5-0.6的轻仓(15%)，低于0.5不买",
    market_condition="AI模型置信度可信时",
    expected_effect="风控更好——低分不硬买，高分敢重仓，预期最大回撤比纯AI打分降低5-10%",
    limitations="打分分布过于集中时，仓位区分不明显；模型校准不准时误导仓位管理",
    params_detail={
        "top_n": "初始候选股票数",
    },
)(AIConfidenceStrategy(top_n=5))

# ── 复合策略 ──

register_strategy(
    key="multi_vote",
    name="三信号投票 (AI+动量+RSI)",
    strategy_type="composite",
    description="AI+动量+RSI 三信号投票，≥2票买入，AI置信度决定仓位",
    mechanism="三个独立信号同时判断——AI模型预测、20日动量排名、RSI均值回归信号，至少2个同意买入才下单",
    market_condition="各种行情——多信号互相验证，适应面最广",
    expected_effect="综合表现最稳定，预期夏普 0.8-1.3，各类行情下都有一定表现",
    limitations="信号共振要求高，交易频率低；极端行情下三个信号可能同时错误",
    params_detail={
        "top_n": "选股数量",
        "vote_threshold": "最少需要几个信号同意（默认2）",
    },
)(MultiSignalVoting(top_n=3, vote_threshold=2))

# ── MACD ──

register_strategy(
    key="macd_cross",
    name="MACD 金叉死叉 Top-3",
    strategy_type="technical",
    description="12/26/9 MACD 金叉买入，死叉卖出",
    mechanism="MACD快线(DIF)上穿慢线(DEA)形成金叉时买入，下穿形成死叉时卖出，经典趋势跟随指标",
    market_condition="有明显上涨趋势的行情",
    expected_effect="趋势行情中金叉买入后继续上涨概率较高，比单纯MA金叉更灵敏",
    limitations="震荡市中频繁金叉死叉；对大幅跳空低开反应慢",
    params_detail={
        "fast": "快线周期",
        "slow": "慢线周期",
        "signal": "信号线周期",
        "top_n": "选股数量",
    },
)(MACDCrossStrategy(fast=12, slow=26, signal=9, top_n=3))

register_strategy(
    key="macd_cross_ai",
    name="MACD 金叉+AI 增强",
    strategy_type="technical",
    description="金叉选股 + AI 打分二次排序",
    mechanism="MACD金叉候选池中，用AI打分筛选最高质量的金叉信号",
    market_condition="AI模型有效时",
    expected_effect="减少假金叉造成的亏损",
    limitations="金叉信号少时AI筛选空间有限",
    params_detail={
        "fast": "快线周期",
        "slow": "慢线周期",
        "signal": "信号线周期",
        "top_n": "选股数量",
    },
)(MACDCrossStrategy(fast=12, slow=26, signal=9, top_n=3, ai_enhanced=True))

# ── KDJ ──

register_strategy(
    key="kdj_oversold",
    name="KDJ 超卖反转 Top-3",
    strategy_type="mean_reversion",
    description="K<20 超卖金叉买入，K>80 超买卖出",
    mechanism="KDJ指标中K值低于20（超卖区）且形成金叉时买入，K值高于80（超买区）时卖出",
    market_condition="震荡市/短期超卖反弹行情",
    expected_effect="捕捉短期超卖反弹机会，适合短线交易",
    limitations="超卖后继续超卖（暴跌行情中K值可以连续几天低于20）；频繁交易增加手续费",
    params_detail={
        "period": "KDJ计算周期",
        "oversold": "超卖阈值",
        "overbought": "超买阈值",
        "top_n": "选股数量",
    },
)(KDJStrategy(period=9, oversold=20, overbought=80, top_n=3))

# ── 成交量突破 ──

register_strategy(
    key="volume_breakout",
    name="放量突破 Top-3",
    strategy_type="technical",
    description="突破20日高点 + 放量 = 买入信号",
    mechanism="价格突破20日新高且成交量放大到均量的1.5倍以上时买入——量价齐升确认突破有效性",
    market_condition="放量上涨的强势行情",
    expected_effect="量价配合的突破成功率更高，能有效过滤无量假突破",
    limitations="缩量上涨行情中信号稀少；突发利好的放量涨停可能买不进去",
    params_detail={
        "lookback": "突破观察窗口",
        "vol_ratio": "成交量放大倍数阈值",
        "top_n": "选股数量",
    },
)(VolumeBreakoutStrategy(lookback=20, vol_ratio=1.5, top_n=3))

register_strategy(
    key="volume_breakout_ai",
    name="放量突破+AI 增强",
    strategy_type="technical",
    description="放量突破选股 + AI 打分排序",
    mechanism="放量突破信号股票中，用AI打分筛选得分最高的",
    market_condition="AI模型有效时",
    expected_effect="进一步过滤劣质突破信号",
    limitations="放量突破信号本身就不多，AI筛选后更少",
    params_detail={
        "lookback": "突破观察窗口",
        "vol_ratio": "成交量放大倍数",
        "top_n": "选股数量",
    },
)(VolumeBreakoutStrategy(lookback=20, vol_ratio=1.5, top_n=3, ai_enhanced=True))

# ── 布林缩口 ──

register_strategy(
    key="bollinger_squeeze",
    name="布林缩口突破 Top-3",
    strategy_type="volatility",
    description="布林带宽收窄后突破上轨买入",
    mechanism="布林带宽大幅收窄（波动率压缩到极致）后价格突破上轨时买入——压缩越紧爆发越猛",
    market_condition="横盘整理后即将爆发的变盘节点",
    expected_effect="捕捉横盘后的爆发性行情，预期盈亏比高",
    limitations="横盘整理期可能很长，信号间隔大；压缩后也可能向下突破（止损要设好）",
    params_detail={
        "period": "布林带计算周期",
        "std_dev": "标准差倍数",
        "squeeze_threshold": "缩口阈值，越小条件越严格",
        "top_n": "选股数量",
    },
)(BollingerSqueezeStrategy(period=20, std_dev=2.0, squeeze_threshold=0.1, top_n=3))

# ── 海龟通道 ──

register_strategy(
    key="turtle",
    name="海龟通道突破 Top-5",
    strategy_type="trend",
    description="20日唐奇安通道高点突破买入，宽止损，经典趋势跟踪",
    mechanism="价格突破20日最高价时买入，跌破10日最低价时卖出，海龟交易法则的简化版，仓位更分散(Top-5)",
    market_condition="持续上涨的大趋势行情",
    expected_effect="趋势跟踪经典策略，在大牛市中能吃到主升浪，选5只更分散风险",
    limitations="宽止损导致单笔亏损大；震荡市反复被假突破消耗本金",
    params_detail={
        "entry_period": "买入通道天数",
        "exit_period": "卖出通道天数",
        "top_n": "选股数量(5只更分散)",
    },
)(TurtleStrategy(entry_period=20, exit_period=10, top_n=5))

register_strategy(
    key="turtle_ai",
    name="海龟通道+AI 增强",
    strategy_type="trend",
    description="通道突破 + AI 打分增强",
    mechanism="海龟通道突破股票中，用AI打分排序只买得分最高的Top-5",
    market_condition="AI模型有效时",
    expected_effect="减少假突破，提高海龟策略胜率",
    limitations="通道突破信号本身就少，AI筛选后更少",
    params_detail={
        "entry_period": "买入通道天数",
        "exit_period": "卖出通道天数",
        "top_n": "选股数量",
    },
)(TurtleStrategy(entry_period=20, exit_period=10, top_n=5, ai_enhanced=True))

# ── 三均线 ──

register_strategy(
    key="triple_ma",
    name="三均线多头排列 Top-3",
    strategy_type="trend",
    description="MA5>MA20>MA60 多头排列买入，稳健趋势跟踪",
    mechanism="短期均线(MA5) > 中期均线(MA20) > 长期均线(MA60)且股价在MA5上方时买入——最稳健的上涨趋势确认信号",
    market_condition="中长期稳定上涨趋势（慢牛市）",
    expected_effect="趋势确认最严格的策略之一，买入后继续上涨概率高，最大回撤控制好",
    limitations="信号稀少——等三线多头时行情已经走了一大段；震荡市长时间无信号",
    params_detail={
        "short": "短期均线天数",
        "mid": "中期均线天数",
        "long": "长期均线天数",
        "top_n": "选股数量",
    },
)(TripleMAStrategy(short=5, mid=20, long=60, top_n=3))

register_strategy(
    key="triple_ma_ai",
    name="三均线+AI 增强",
    strategy_type="trend",
    description="多头排列 + AI 打分增强",
    mechanism="三线多头排列股票池中，用AI打分选出最优的",
    market_condition="AI模型有效且三线多头信号出现时",
    expected_effect="在最强趋势中再精选，预期表现更优",
    limitations="三线多头信号本身稀少，AI筛选空间有限",
    params_detail={
        "short": "短期均线天数",
        "mid": "中期均线天数",
        "long": "长期均线天数",
        "top_n": "选股数量",
    },
)(TripleMAStrategy(short=5, mid=20, long=60, top_n=3, ai_enhanced=True))

# ════════════════════════════════════════════════════════════════
# 兼容旧接口
# ════════════════════════════════════════════════════════════════

BASELINE_STRATEGIES = ["equal_weight", "momentum_20d"]

STRATEGY_REGISTRY: dict[str, dict] = {}
AI_REQUIRED_STRATEGIES: list[str] = []

def _rebuild_compat():
    """从新注册表重建旧接口"""
    global STRATEGY_REGISTRY, AI_REQUIRED_STRATEGIES
    STRATEGY_REGISTRY.clear()
    AI_REQUIRED_STRATEGIES.clear()
    for meta in list_registered_strategies():
        key = meta["key"]
        STRATEGY_REGISTRY[key] = {
            "name": meta["name"],
            "type": meta["type"],
            "description": meta["description"],
            "generator": get_strategy_instance(key),
        }
        if meta["type"] in ("ai",) or key.endswith("_ai"):
            AI_REQUIRED_STRATEGIES.append(key)

_rebuild_compat()


def get_strategy(name: str):
    """获取策略实例（兼容旧接口）"""
    return get_strategy_instance(name)


def list_strategies() -> list[dict]:
    """列出所有策略（供前端使用，含丰富元数据）"""
    metas = list_registered_strategies()
    result = []
    for m in metas:
        result.append({
            "key": m["key"],
            "name": m["name"],
            "type": m["type"],
            "description": m["description"],
            "mechanism": m.get("mechanism", ""),
            "market_condition": m.get("market_condition", ""),
            "expected_effect": m.get("expected_effect", ""),
            "limitations": m.get("limitations", ""),
            "params_detail": m.get("params_detail", {}),
            "is_baseline": m["key"] in BASELINE_STRATEGIES,
            "needs_ai": m["key"] in AI_REQUIRED_STRATEGIES,
        })
    return result
