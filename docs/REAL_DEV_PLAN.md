# 赛道型量化系统 — 开发计划

> 基于「个人散户·赛道型量化系统终版开发方案」
> 更新日期：2026-06-20

---

## 〇、核心技术原则

1. **开源优先，不重复造轮子**：所有能用成熟开源库实现的功能，绝不手写数学公式/算法
2. **非数学专业友好**：依赖经过业界验证的稳定库，不自己推导统计公式
3. **分层架构**：通用特征用开源库（ta），赛道专属特征自己写（开源库没有）
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
数据清洗复权落库
    ↓
批量生成通用 + 赛道专属特征
    ↓
Alphalens 科学筛因子黑白名单
    ↓
特征标准化 / 中性化 / 去共线
    ↓
分赛道 LightGBM 滚动 AI 训练
    ↓
个股 + 赛道打分
    ↓
回测校验
    ↓
Vue 可视化展示
```

---

## 三、进度总览

| Phase | 内容 | 状态 |
|-------|------|:----:|
| Phase A | 数据流水线（拉数据→复权→落库→打标签） | ✅ |
| Phase B | 特征工程（93 通用+18 赛道特征） | ✅ |
| Phase C | Alphalens 双层筛选因子 | ✅ |
| Phase D | 特征预处理（标准化/去共线/时序分割） | ✅ |
| Phase E | 赛道 LightGBM 训练 | ✅ |
| Phase F | 个股+赛道打分 API | ✅ |
| Phase G | 回测校验（pandas 手写 → backtrader 升级） | ✅ 手写 |
| Phase H | 前端可视化（7 页面机构工作流） | ✅ |
| Phase I | 基本面数据接入（akshare） | ✅ |
| Phase J | 回测框架升级（backtrader） | ⏳ |
| Phase K | 前端占位页面填充（Alpha Research / Model Factory / Portfolio） | ✅ |

---

## 四、Checklist 详细完成情况

### Phase A：数据流水线

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

### Phase B：特征工程

> **核心原则：通用特征用 ta 库（Python 3.11 兼容，pip install 一键安装），赛道特征自己写**
> ta 库提供 40+ 业界验证指标，配合 pandas 自定义统计特征，覆盖全部需求

- [x] `pip install ta` 安装依赖（pandas-ta 不兼容 Python 3.11，已切换）
- [x] **通用量价特征** — 基于 ta 库（`features_generic.py`）
  - [x] 动量类：RSI(3), Stochastic K/D/J, Williams %R(2), ROC(5), AO, PPO = 16 特征
  - [x] 趋势类：SMA(4)+偏离度, EMA(2)+偏离度, MACD(3), ADX(3), Aroon(2), CCI(2), TRIX = 16 特征
  - [x] 波动率类：ATR(3), Bollinger(5), Donchian(3), Ulcer = 12 特征
  - [x] 量能类：OBV, AD, CMF, EMV, FI, MFI, VPT, VWAP, 量比(2), 量能动量(2) = 12 特征
  - [x] 自定义补充：收益偏度/峰度/分位/连续涨跌/Sharpe/量价相关 = 10 特征
  - [x] 价格位置：高低点位置(2) + 2 个其他 = 4 特征
- [x] **赛道专属特征** — 自己写（`features_track.py`）
  - [x] 赛道个体动量(3), 趋势强度(2), 波动率(1), 量比(1)
  - [x] Amihud 非流动性(1), 资金流(4), 反转信号(6)
  - [x] 赛道间相对强度、赛道拥挤度
- [x] `scripts/compute_features.py` — 批量计算脚本
  - [x] DB 加载 → ta 算通用特征 → features_track 算赛道特征
  - [x] 全部特征统一 shift(1) 防未来泄露
  - [x] 特征写入 `feature_store` 表（JSON 宽表，stock_code + trade_date + features）
  - [x] 输出验收报告：特征总数、NaN 比例
- [x] 验收：全部 shift(1) ✅，NaN < 50% ✅ (100% 有效)，特征数 93~111 ✅

### Phase C：Alphalens 双层筛选

> **核心原则：用 alphalens-reloaded + scipy 池化 Rank IC，不手写 IC/IR 计算**
> 22 只股票小池，截面太窄日度 IC 噪声大，采用池化 IC 为主判据

- [x] `pip install alphalens-reloaded scipy` 安装依赖
- [x] `scripts/screen_factors.py` 因子筛选脚本
  - [x] 池化 Rank IC（72,910 个 stock×date 数据点）
  - [x] 日度 IC 序列计算 IR
  - [x] 10 层分组收益方向检查
- [x] 筛选阈值：|IC|>=0.01, |IR|>=0.05（小池放宽）
- [x] 白名单 75 个因子 → FeatureWhiteList ✅
- [x] 黑名单 72 个因子 → FeatureBlackList ✅
- [x] 固化 JSON 配置 `configs/factor_whitelist.json` ✅
- [x] `GET /api/v1/track/factors/whitelist` 返回 75 个因子 ✅
- [x] `GET /api/v1/track/factors/blacklist` 返回 72 个因子 ✅

### Phase D：特征预处理

> **核心原则：用 scikit-learn 的 StandardScaler，不手写标准化公式**

- [x] `pip install scikit-learn pyarrow` 安装依赖
- [x] `scripts/preprocess_features.py` 预处理脚本
  - [x] 加载白名单 75 个因子
  - [x] NaN 中位数填充 (1,609,528 → 0)
  - [x] 去共线: 75 → 54 个特征 (剔除 21 个高相关对, |corr|>0.95)
  - [x] 时序分割: train≤2022 / val=2023 / test≥2024 (无 shuffle)
  - [x] Z-score 标准化: 仅训练集 fit, transform all
- [x] 输出 parquet 数据集: `ml/preprocessed/{train,val,test}.parquet`
- [x] 输出配置: `feature_cols.json`, `scaler_params.json`, `meta.json`
- [x] 验收:
  - max|corr| = 0.9458 < 0.95 ✅
  - 高相关对 = 0 ✅
  - 标准化 max|mean| = 0.000000 ✅
  - 标准化 std = 1.0000 ✅
  - 训练集 54,162 行 / 验证集 5,566 行 / 测试集 13,182 行 ✅

### Phase E：赛道 LightGBM 训练 ✅ 已完成（二分类）

> **核心原则：用 lightgbm 官方库 + scikit-learn TimeSeriesSplit，不手写训练循环**

- [x] `pip install lightgbm` 安装依赖（libomp symlink 复用 sklearn 自带库）
- [x] 每个赛道独立模型（6 个模型：semiconductor/ai/robot/storage/ai-power/material）
- [x] 时间滚动训练（`TimeSeriesSplit`，禁止 shuffle）
- [x] 预测目标：二分类（个股 20 日收益是否高于赛道当日中位数）
- [x] 模型序列化 `ml/models/{track}.pkl`（`joblib`）
- [x] 固定超参数：LGBMClassifier, num_leaves=31, max_depth=8, 自适应正则化
- [x] 验收：所有赛道 Acc gap < 0.10 ✅

**当前模型表现**：验证集 Acc 50-54%，接近随机但月频回测夏普可达 0.92。详见 Phase J 优化计划。

### Phase F：打分 API ✅ 已完成

- [x] 个股强弱分（赛道内排序，0.00-0.02 区间）
- [x] 赛道景气总分（0-100，sigmoid 映射）
- [x] `GET /api/v1/ml/score/{track_name}` 返回个股排名+景气度
- [x] `GET /api/v1/ml/scores` 返回所有赛道打分

### Phase G：回测校验 ✅ 已完成（手写版本）

> **核心原则：用 pandas 向量化回测（简单可靠），不引入重型回测框架**
> **注：当前手写版本已实现基础功能，后续计划迁移至 backtrader（Phase J）**

- [x] AI 打分 → 轮动策略
- [x] 模拟滑点（固定 0.1%）、手续费（万三）、涨跌停无法成交
- [x] 单票仓位上限 20%、单赛道仓位上限 50%
- [ ] 赛道景气降仓
- [x] 绩效计算：用 pandas 向量化计算夏普/回撤/分层收益（不手写公式）
- [x] 验收：夏普 ≥ 1.2 ❌（当前 0.18），回撤 < 25% ❌（当前 60%）

**当前不足**：
- 无买卖点可视化
- 无多策略对比能力
- 扩展新策略成本高
- 详见 Phase J 升级计划

### Phase H：前端可视化 ✅ 已完成（7 页面机构工作流）

> **架构**：Musk 极简暗色侧边栏，7 步机构量化工作流（DATA 3 + STRATEGY 4）
> **命名**：全英文，侧边栏零编号零间隙，Step 标签已移除

#### H.1 页面与路由

| 路由 | 页面名 | Vue 组件 | 内容 |
|:-----|:-------|:---------|:-----|
| `/` | Dashboard | HomePage.vue | 4 赛道卡片（景气环+Top3评分）+ 流水线状态 + Quick Stats |
| `/pipeline` | Data Pipeline | DataView.vue | 统计卡片 + 因子筛选流程 + 黑名单 + 最终特征 + 因子完全手册 |
| `/alpha` | Alpha Research | AlphaResearchPage.vue | 因子 IC 时序 + 相关性热力图 + 分位数组合收益 |
| `/model-factory` | Model Factory | ModelFactoryPage.vue | 模型卡片(R²)+ 特征重要性 Top10 + 一键重训 + 比对表 |
| `/track/:name` | Alpha Workstation | TrackDashboard.vue | K线主图+均线/布林/趋势线 + RSI/ATR/景气副图 + 左侧AI排名 + 右侧因子面板 |
| `/backtest` | Backtest Lab | BacktestPage.vue | 可配置回测（预设方案/资金/选股/风控）+ 9 项绩效指标 + 赛道元数据 |
| `/portfolio` | Portfolio | PortfolioPage.vue | 赛道权重环形图 + 个股持仓比例 + 风险监控 + 净值曲线 |

- [x] K 线主图：均线/布林/赛道趋势线
  - [x] 均线系统（MA5/MA20/MA60）
  - [x] 布林轨道（BB upper/lower）
  - [x] 赛道趋势线（60日线性回归）
  - [ ] 支撑压力线（P2）
- [x] 副图：成交量 + ATR + RSI（含 70/30 超买超卖线）+ 赛道景气
- [x] 左侧 AI 排名面板（RankPanel.vue，对接真实API `/ml/score/{track}`）
- [x] 右侧有效因子面板（FactorChartPanel.vue，分类图标+IC可视化）
- [x] 赛道景气仪表盘（ProsperityPanel.vue，对接真实API `/ml/scores`）
- [x] 赛道一键切换
- [x] 核心规则：只渲染白名单因子，黑名单自动隐藏
- [x] 品牌标识：量化交易跟踪系统 / Quantitative Trading & Tracking System

---

### Phase I：基本面数据接入（akshare）✅ 已完成

> **核心原则：接入 akshare 获取基本面数据，作为全新特征维度喂给 LightGBM**

- [x] `pip install akshare` 安装依赖
- [x] 基本面数据范围：PE/PB/ROE/营收增速/净利润增速/销售净利率等
- [x] 基本面数据入库 feature_store（fund_* 前缀）
- [x] 基本面特征前向填充（季度→日频）集成到 preprocess step
- [x] Alphalens 筛选通过多个基本面因子（fund_主营业务收入增长率、fund_净利润增长率 等）
- [x] 白名单已包含基本面因子
- [x] 验收：基本面因子已纳入训练

---

### Phase J：回测框架升级（backtrader）

> **核心原则：用 backtrader 替换手写回测，获取内置绩效分析+可视化能力**

- [ ] `pip install backtrader` 安装依赖
- [ ] 创建 `scripts/backtest_backtrader.py`：
  - [ ] 定义 AIScoreStrategy（AI 打分轮动策略）
  - [ ] 配置滑点/手续费（set_slippage_perc/setcommission）
  - [ ] 配置仓位限制（单票 20%/单赛道 50%）
  - [ ] 配置 Analyzer（SharpeRatio/DrawDown/Returns）
- [ ] 验证回测结果与手写版本一致
- [ ] 接入 `cerebro.plot()` 自动出图
- [ ] 实现多策略对比（不同参数/不同预测目标）
- [ ] 验收：回测结果正确性验证通过

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
| 数据源 | baostock（日线）+ akshare（基本面） | 行情+基本面数据 | baostock ✅ / akshare ⏳ Phase I |
| 后端 | FastAPI + SQLAlchemy + SQLite | API + ORM + 存储 | ✅ 运行中 :8000 |
| 前端 | Vue3 + Element Plus + ECharts | 可视化终端 | ✅ 运行中 :5173 |
| **通用特征** | **ta**（40+ 指标 + 自定义补充） | 量价技术指标计算 | ✅ Phase B 已完成 |
| **因子筛选** | **alphalens-reloaded + scipy** | IC/IR/分层检验 | ✅ Phase C 已完成 |
| **特征预处理** | **scikit-learn** | 标准化/去共线 | ✅ Phase D 已完成 |
| **AI 模型** | **LightGBM + scikit-learn** | 分赛道训练 | ✅ Phase E 已完成 |
| **回测** | **backtrader**（替换手写） | 绩效计算+可视化 | ⏳ Phase J 引入 |
| 数据库 | SQLite（可一键切 MySQL） | 持久化 | ✅ 已接入 |

### 开源库选型理由

| akshare | 数据最全的开源数据源，覆盖 A 股基本面/北向资金/龙虎榜等，pip 一键装 |
| backtrader | 轻量级回测框架，内置滑点/手续费/绩效分析/画图，社区活跃 |
| ta | 纯 Python，pip 一键装，40+ 业界标准指标，Python 3.11 兼容，非数学专业友好 |
| alphalens-reloaded | Quantopian 开源续命版，因子分析事实标准，IC/IR/分层一行搞定 |
| scikit-learn | 机器学习基础设施，StandardScaler/TimeSeriesSplit 久经验证 |
| LightGBM | 微软开源，表格数据最强，散户级数据量秒级训练 |

### 不选的库及理由（2026-06-20 修订版）

| 库 | 不选理由 |
|:---|:----------|
| TA-Lib | 需先装 C 库再装 Python 绑定，安装门槛高，对非数学专业不友好。**ta 库已够用** |
| qlib（微软） | 全栈量化框架，太重，我们需要的是组件不是框架 |
| backtrader（当前决策） | ~~重型回测框架~~ → **Phase J 重新评估**：轻量级、pip 一键装、社区活跃，决定引入替换手写回测 |
| zipline | 已停更，不推荐 |

## 七、AI Skill 质量门禁体系

为防止开发过程中 AI 行为漂移（无序加特征、无限调参、刷回测指标），已按 Phase 流水线内置 12 个 Skill（`.qoder/skills/`），分为量化业务和工程通用两层。

### 7.1 量化业务 Skill（赛道专属）

| Skill | 路径 | 解决什么问题 |
|:------|:-----|:------------|
| `/review-phase` | `.qoder/skills/review-phase/` | 阶段验收，防止跳步 |
| `/add-feature` | `.qoder/skills/add-feature/` | 新增特征必须走 6 步验证流程 |
| `/train-model` | `.qoder/skills/train-model/` | 固定训练参数，防止无限调参 |
| `/run-backtest` | `.qoder/skills/run-backtest/` | 锁定回测参数，防止刷指标 |
| `/check-data` | `.qoder/skills/check-data/` | 数据质量自动化巡检 |

### 7.2 工程通用 Skill（跨项目可复用）

| Skill | 源仓库 | 用途 |
|:------|:-------|:-----|
| `code-review-and-quality` | addyosmani/agent-skills | 多维度代码审查（Bug/安全/性能/风格/可维护性） |
| `git-commit` | github/awesome-copilot | Conventional Commit 规范生成（feat/fix/refactor 自动识别） |
| `security-audit` | ruvnet/ruflo | API 安全审计（SQL 注入/JWT/XSS/路径穿越/CVE） |
| `spec-driven-development` | addyosmani/agent-skills | 先写 Spec 验收标准，再动手编码 |
| `planning-and-task-breakdown` | addyosmani/agent-skills | 大任务拆解为有序子任务 |
| `incremental-implementation` | addyosmani/agent-skills | 多文件改动时增量垂直交付 |
| `pr-description-writer` | joyco-studio/skills | 生成结构化 PR 描述（含测试清单） |
| `pua` | tanweai/pua | 连续失败时自动加压鞭策 |

### 7.3 开发时序 Skill 调用流

```
量化开发流程：
  /check-data（数据检查）→ /add-feature × N（加特征）→ /train-model（训练）
  → /run-backtest（回测）→ /review-phase（阶段验收）

提交代码流程：
  code-review-and-quality（自动代码审查）→ git-commit（规范提交）

启动新功能流程：
  spec-driven-development（写 Spec）→ planning-and-task-breakdown（拆任务）
  → incremental-implementation（增量实现）→ pr-description-writer（PR 描述）
```

### 7.4 触发方式

1. **显式调用**：`/review-phase B`、`/check-data`、`/git-commit`
2. **自动匹配**：说"加个特征"→ AI 自动走 add-feature 流程；说"审查代码"→ 自动调 code-review-and-quality
3. **主动插入**：开发过程中 AI 遇到连续失败自动触发 pua 加压，切换方案
4. **手动安装新 Skill**：`npx skills add <仓库> --skill <名称>`（国内加速：已预配 ghfast.top 代理）

### 7.5 安装命令

```bash
# 国内网络已预配 ghfast.top 加速，npx skills add 可直接使用
npx skills add addyosmani/agent-skills --skill code-review-and-quality -y
npx skills add github/awesome-copilot --skill git-commit -y
npx skills add ruvnet/ruflo --skill security-audit -y
npx skills add addyosmani/agent-skills --skill spec-driven-development -y
npx skills add addyosmani/agent-skills --skill planning-and-task-breakdown -y
npx skills add addyosmani/agent-skills --skill incremental-implementation -y
npx skills add joyco-studio/skills --skill pr-description-writer -y
```

## 八、下一步（量化研究员视角）

> Phase K 已完成，当前 R² 接近 0 是最大瓶颈。以下优先级按**对交易决策的实际帮助**排序。

### P0（紧急）：模型能学到信号吗？

**现状诊断**：4 个模型 Train R² 0.05~0.09，Test R² 接近 0。意味着 AI 打分基本无效，后续回测、组合、持仓全是建立在随机噪声上。

```
核心问题链：R²≈0 → 打分无效 → 轮动策略 ≈ 随机选股 → 回测无意义 → 组合不可信
```

1. **松绑超参数**：num_leaves 8→20, reg_alpha 5→1, lr 0.01→0.05（当前正则过强，模型欠拟合）
2. **换预测目标**：绝对收益 → 赛道内相对排名（排名比精确值更容易预测）
3. **加基本面特征**：PE/PB/ROE/北向资金（全新信息维度，akshare，Phase I）
4. 验证：重新训练后 Test R² 是否 > 0，夏普是否 > 0.5

**验收标准**：至少 3/4 赛道 Test R² > 0，回测夏普 > 0.5

### P1（高优）：前端对交易有用吗？

当前前端已完整但缺少**交易决策直接支撑**的功能：

1. **Alpha Research 深度化** — IC 分析能用了，但缺少手持计算视角：
   - 因子择时：哪些因子当前处于历史高位/低位（分位数）
   - 因子组合：选最好几个因子等权合成，看历史净值
   - 个股因子暴露：选中某只股票，告诉我是哪些因子在驱动它的打分

2. **打分回溯** — 历史打分 vs 实际表现，回答"AI 上次说它强，后来真强了吗？"
   - 当前已打分但没有历史记录
   - 每次打分存到 score_history 表
   - 前端展示回溯精度曲线

3. **回测买卖点可视化** — 回测报告里加入买卖标记
   - 在 equity_curve 上标出入场/出场点
   - 直观看到哪些交易赚钱、哪些亏钱

### P2（中优）：模型诊断与监控

研究员需要知道模型什么时候可能失效：

1. **特征重要性漂移监控** — 每次重训记录 Top10 特征，前后对比
2. **打分分布监控** — 赛道内打分是否过度集中（所有票都一样 = 模型退化）
3. **IC 衰减监控** — 上线后 IC 是否持续衰减（过拟合信号）

### P3（低优但顺手）

1. **回测框架升级 backtrader**（Phase J）— 手写版够用，不阻塞
2. **支撑压力线** — K 线主图叠加
3. **多策略对比** — 不同参数/预测目标的回测结果并列对比
4. **暗色模式** — 用户体验优化
