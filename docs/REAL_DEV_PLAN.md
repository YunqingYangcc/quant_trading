# 赛道型量化系统 — 开发计划

> 基于「个人散户·赛道型量化系统终版开发方案」
> 更新日期：2026-06-19
> 状态：**Phase A 完成，待 Phase B**

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

- [ ] 通用量价特征 `features_generic.py`
  - [ ] 动量类（momentum_1d/5d/10d/20d 等）
  - [ ] 均线类（ma5/ma10/ma20/ma60 偏离度）
  - [ ] 波动率类（ATR, volatility）
  - [ ] RSI 震荡类
  - [ ] 量能类（volume_ratio, obv 等）
  - [ ] 相对强弱类
- [ ] 赛道专属特征 `features_track.py`
  - [ ] 赛道内相对强度
  - [ ] 赛道拥挤度
  - [ ] 赛道趋势一致性
- [ ] 特征入库（可复用 TrackDataCache 扩列或新建特征表）
- [ ] 验收：全部 shift(1)，NaN 比例 < 50%，特征数 60+

### Phase C：Alphalens 双层筛选 ⏳ 待开发

- [ ] Alphalens 单因子检验
  - [ ] IC 绝对值 ≥ 0.02
  - [ ] IR ≥ 0.5
  - [ ] 10 层分组收益单调
- [ ] 写入白名单 `FeatureWhiteList`
- [ ] 写入黑名单 `FeatureBlackList`
- [ ] LightGBM 特征重要性第二轮筛选
- [ ] 固化 JSON 配置
- [ ] `GET /api/v1/track/factors/whitelist` ✅
- [ ] `GET /api/v1/track/factors/blacklist` ✅

### Phase D：特征预处理 ⏳ 待开发

- [ ] Z-score 标准化
- [ ] 市值/行业中性化（可选）
- [ ] 去共线（剔除相关性 > 0.95 对）
- [ ] 时间序列分割（训练/验证/测试）

### Phase E：赛道 LightGBM 训练 ⏳ 待开发

- [ ] 每个赛道独立模型（4 个模型）
- [ ] 时间滚动训练（禁止 shuffle）
- [ ] 预测目标：future_20d_excess_return
- [ ] 模型序列化 `ml/models/{track}.pkl`
- [ ] 验收：训练/测试 R² 差距 < 0.15，无未来泄露

### Phase F：打分 API ⏳ 待开发

- [ ] 个股强弱分（赛道内排序）
- [ ] 赛道景气总分（0-100）
- [ ] `GET /api/v1/api/ml/score/{track_name}` ✅

### Phase G：回测校验 ⏳ 待开发

- [ ] AI 打分 → 轮动策略
- [ ] 模拟滑点、手续费、涨跌停
- [ ] 单票/单赛道仓位上限
- [ ] 赛道景气降仓
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

| 层 | 技术 | 状态 |
|:---|:-----|:-----|
| 数据源 | baostock（前复权日线） | ✅ 可用 |
| 后端 | FastAPI + SQLAlchemy + SQLite | ✅ 运行中 :8000 |
| 前端 | Vue3 + Element Plus + ECharts | ✅ 运行中 :3000 |
| 特征工程 | Python / pandas / numpy | ⏸️ 代码已写待运行 |
| AI 模型 | LightGBM | ⏸️ 代码已写待运行 |
| 回测引擎 | 自研轻量化（track_backtester） | ⏸️ 代码已写待运行 |
| 数据库 | SQLite（可一键切 MySQL） | ✅ 已接入 |

## 七、下一步

**立即开始 Phase B**：运行特征工程脚本，对 23 只股票批量计算 60+ 特征。
