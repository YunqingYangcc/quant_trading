# 赛道型量化系统 — 开发计划

> 基于「个人散户·赛道型量化系统终版开发方案」
> 更新日期：2026-06-19
> 状态：**Phase A 完成，待 Phase B**

---

## 〇、核心技术原则

1. **开源优先，不重复造轮子**：所有能用成熟开源库实现的功能，绝不手写数学公式/算法
2. **非数学专业友好**：依赖经过业界验证的稳定库，不自己推导统计公式
3. **分层架构**：通用特征用开源库（pandas-ta），赛道专属特征自己写（开源库没有）
4. **AI 辅助开发**：善用 AI 工具生成代码，但必须理解每一步逻辑

---

## 一、系统核心定位

1. **非机构全市场量化**：不做全市场海选、不做中性对冲、不做高频、不堆海量因子
2. **散户专属赛道模式**：只聚焦个人看好的核心赛道（半导体、存储、AI、机器人）
3. **交易池仅限自选股**：所有数据、因子、模型、回测、可视化只服务自选赛道池
4. **主观产业认知 + 量化数据双结合**：人定赛道方向，系统定强弱、打分、择时、风控
5. **中低频稳健模式**：周/月调仓，低换手、低滑点、极低过拟合

---

## 二、固定流水线（强制单向、不可颠倒）

```
baostock 取数
    ↓
数据清洗复权落库 ⬅ Phase A ✅
    ↓
批量生成通用 + 赛道专属特征 ⬅ Phase B ⏳
    ↓
Alphalens 科学筛因子黑白名单 ⬅ Phase C
    ↓
特征标准化 / 中性化 / 去共线 ⬅ Phase D
    ↓
分赛道 LightGBM 滚动 AI 训练 ⬅ Phase E
    ↓
个股 + 赛道打分 ⬅ Phase F
    ↓
回测校验 ⬅ Phase G
    ↓
Vue 可视化展示 ⬅ Phase H
```

---

## 三、进度总览

| Phase | 内容 | 状态 | 完成日期 |
|-------|------|------|----------|
| Phase A | 数据流水线（拉数据→复权→落库→打标签） | ✅ 已完成 | 2026-06-19 |
| Phase B | 特征工程（60+ 通用+赛道特征） | ⏳ 未开始 | - |
| Phase C | Alphalens 双层筛选因子 | ⏳ 未开始 | - |
| Phase D | 特征预处理（标准化/中性化/去共线） | ⏳ 未开始 | - |
| Phase E | 赛道 LightGBM 训练 | ⏳ 未开始 | - |
| Phase F | 个股+赛道打分 API | ⏳ 未开始 | - |
| Phase G | 回测校验 | ⏳ 未开始 | - |
| Phase H | 前端可视化（K线+特征+评分） | ⏳ 骨架完成待完善 | - |

---

## 四、Checklist 详细完成情况

### Phase A：数据流水线 ✅ 已完成

- [x] 数据源切换 baostock（前复权日线，7列：date,open,high,low,close,volume,amount）
- [x] `scripts/fetch_track_data.py` — 批量拉取 23 只股票存入 `datas/tracks/{赛道}/`
- [x] 频率控制：每次请求间隔 1s，失败重试 3 次
- [x] 赛道 Model/Schema/Service/API 全部实现
- [x] 数据库表创建（tracks, track_stocks, track_data_cache, feature_white_list, feature_black_list）
- [x] 4 条赛道初始化（半导体 8 只 / AI 5 只 / 机器人 5 只 / 存储 5 只）
- [x] CSV → TrackDataCache 导入（23 只，~64,000 条日线）
- [x] shift(1) 标签生成（fwd_1d/5d/20d_return, is_limit_up/down）
- [x] `GET /api/v1/track/tracks` 返回赛道列表+成分股 ✅
- [x] `GET /api/v1/track/labels/{code}` 返回带标签日线 ✅
- [x] 前端 TrackDashboard 选股 + K 线渲染（560px，MA5/MA20/成交量）

### Phase B：特征工程 ⏳ 待开发

> **核心原则：通用特征用 pandas-ta（130+ 业界验证指标），赛道特征自己写**
> pandas-ta 是纯 Python 库，pip install 一键安装，无需 C 依赖，对非数学专业最友好

- [ ] `pip install pandas_ta` 安装依赖
- [ ] **通用量价特征** — 用 pandas-ta 替代手写（`features_generic.py` 重构）
  - [ ] 动量类：`ta.momentum()` — ROC, RSI, Stochastic, CCI, Williams %R, MACD
  - [ ] 均线类：`ta.trend()` — SMA, EMA, DEMA, TEMA, MACD 信号
  - [ ] 波动率类：`ta.volatility()` — ATR, Bollinger Bands, Keltner Channel, Donchian
  - [ ] 量能类：`ta.volume()` — OBV, VWAP, A/D Line, Chaikin Money Flow
  - [ ] 相对强弱：`ta.momentum()` — RSI, Stochastic RSI
  - [ ] 自定义补充：收益偏度/峰度、价格位置特征（pandas-ta 没有的）
- [ ] **赛道专属特征** — 保持自己写（`features_track.py`，开源库没有这些）
  - [ ] 赛道内相对强度（个股 vs 赛道均值）
  - [ ] 赛道拥挤度（内部相关性）
  - [ ] 赛道趋势一致性
  - [ ] 赛道间相对强弱
- [ ] `scripts/compute_features.py` — 批量计算脚本
  - [ ] 从 DB 加载 TrackDataCache → pandas-ta 算通用特征 → features_track 算赛道特征
  - [ ] 全部特征统一 shift(1) 防未来泄露
  - [ ] 特征写入新表 `stock_features`（stock_code, trade_date, feature_name, feature_value）
  - [ ] 输出验收报告：特征总数、NaN 比例、描述统计
- [ ] 验收：全部 shift(1)，NaN 比例 < 50%，特征数 60+

### Phase C：Alphalens 双层筛选 ⏳ 待开发

> **核心原则：用 alphalens-reloaded（Quantopian 开源续命版）做因子检验，不手写 IC/IR 计算**

- [ ] `pip install alphalens-reloaded` 安装依赖
- [ ] Alphalens 单因子检验（用库，不手写）
  - [ ] IC 绝对值 ≥ 0.02
  - [ ] IR ≥ 0.5
  - [ ] 10 层分组收益单调
- [ ] 写入白名单 `FeatureWhiteList`
- [ ] 写入黑名单 `FeatureBlackList`
- [ ] LightGBM 特征重要性第二轮筛选
- [ ] 固化 JSON 配置 `configs/factor_whitelist.json`
- [ ] `GET /api/v1/track/factors/whitelist` ✅
- [ ] `GET /api/v1/track/factors/blacklist` ✅

### Phase D：特征预处理 ⏳ 待开发

> **核心原则：用 scikit-learn 的 StandardScaler / VarianceThreshold，不手写标准化公式**

- [ ] Z-score 标准化 — `sklearn.preprocessing.StandardScaler`
- [ ] 市值/行业中性化（可选） — `sklearn.linear_model.LinearRegression` 残差法
- [ ] 去共线（剔除相关性 > 0.95 对） — pandas `.corr()` + 自写筛选逻辑
- [ ] 时间序列分割（训练/验证/测试） — 按时间切分，禁止 shuffle

### Phase E：赛道 LightGBM 训练 ⏳ 待开发

> **核心原则：用 lightgbm 官方库 + scikit-learn TimeSeriesSplit，不手写训练循环**

- [ ] `pip install lightgbm scikit-learn` 安装依赖
- [ ] 每个赛道独立模型（4 个模型）
- [ ] 时间滚动训练（用 `sklearn.model_selection.TimeSeriesSplit`，禁止 shuffle）
- [ ] 预测目标：future_20d_excess_return
- [ ] 模型序列化 `ml/models/{track}.pkl`（用 `joblib`）
- [ ] 验收：训练/测试 R² 差距 < 0.15，无未来泄露

### Phase F：打分 API ⏳ 待开发

- [ ] 个股强弱分（赛道内排序）
- [ ] 赛道景气总分（0-100）
- [ ] `GET /api/v1/api/ml/score/{track_name}` ✅

### Phase G：回测校验 ⏳ 待开发

> **核心原则：用 pandas 向量化回测（简单可靠），不引入重型回测框架**

- [ ] AI 打分 → 轮动策略
- [ ] 模拟滑点（固定 0.1%）、手续费（万三）、涨跌停无法成交
- [ ] 单票仓位上限 20%、单赛道仓位上限 50%
- [ ] 赛道景气降仓
- [ ] 绩效计算：用 pandas 向量化计算夏普/回撤/分层收益（不手写公式）
- [ ] 验收：夏普 ≥ 1.2，回撤 < 25%，分层单调

### Phase H：前端可视化 ⏳ 待完善

- [ ] K 线主图：均线/布林/赛道趋势线/支撑压力线
- [ ] 副图：成交量/ATR/RSI/赛道景气
- [ ] 个股 AI 强弱排名（左侧面板）
- [ ] 有效因子展示（右侧面板）
- [ ] 赛道一键切换
- [ ] 核心规则：只渲染白名单因子，黑名单自动隐藏

---

## 五、执行约束（强制遵守）

1. **上游不验收通过，下游禁止读取数据**
2. **黑名单特征全程禁用**
3. **所有时序数据严格防未来泄露（shift(1)）**
4. **赛道模型独立训练、不通用**
5. **前端只渲染 AI 筛选后的有效因子**
6. **全程可自动化运行、可日志追溯、可迭代更新**

---

## 六、当前技术栈

| 层 | 技术 | 角色 | 状态 |
|:---|:-----|:-----|:-----|
| 数据源 | baostock（前复权日线） | 行情数据 | ✅ 可用 |
| 后端 | FastAPI + SQLAlchemy + SQLite | API + ORM + 存储 | ✅ 运行中 :8000 |
| 前端 | Vue3 + Element Plus + ECharts | 可视化终端 | ✅ 运行中 :3000 |
| **通用特征** | **pandas-ta**（130+ 指标） | 量价技术指标计算 | ⏳ Phase B 引入 |
| **因子筛选** | **alphalens-reloaded** | IC/IR/分层检验 | ⏳ Phase C 引入 |
| **特征预处理** | **scikit-learn** | 标准化/去共线 | ⏳ Phase D 引入 |
| **AI 模型** | **LightGBM + scikit-learn** | 分赛道训练 | ⏳ Phase E 引入 |
| **回测** | **pandas 向量化**（轻量自研） | 绩效计算 | ⏳ Phase G 引入 |
| 数据库 | SQLite（可一键切 MySQL） | 持久化 | ✅ 已接入 |

### 开源库选型理由

| 库 | 为什么选它 |
|:---|:----------|
| pandas-ta | 纯 Python，pip 一键装，130+ 业界标准指标，API 友好，非数学专业最友好 |
| alphalens-reloaded | Quantopian 开源续命版，因子分析事实标准，IC/IR/分层一行搞定 |
| scikit-learn | 机器学习基础设施，StandardScaler/TimeSeriesSplit 久经验证 |
| LightGBM | 微软开源，表格数据最强，散户级数据量秒级训练 |

### 不选的库及理由

| 库 | 不选理由 |
|:---|:----------|
| TA-Lib | 需先装 C 库再装 Python 绑定，安装门槛高，对非数学专业不友好 |
| qlib（微软） | 全栈量化框架，太重，我们需要的是组件不是框架 |
| backtrader/zipline | 重型回测框架，散户小资金不需要，pandas 向量化够用 |

## 七、下一步

**立即开始 Phase B**：
1. `pip install pandas_ta` 安装依赖
2. 重构 `features_generic.py`：用 pandas-ta 替换手写 numpy 公式
3. 创建 `scripts/compute_features.py`：DB加载 → 计算 → 入库 → 验收报告
4. 对 23 只股票批量计算 60+ 特征并入库
