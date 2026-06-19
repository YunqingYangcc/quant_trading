# 数据流水线开发文档

> Phase A 实现记录  
> 更新日期：2026-06-19

---

## 一、架构总览

```
baostock (数据源)
    ↓
scripts/fetch_track_data.py  →  datas/tracks/{赛道}/{code}.csv
    ↓
TrackService.import_csv_to_cache()  →  track_data_cache 表（SQLite）
    ↓
TrackService.generate_labels()  →  shift(1) 防泄露标签
    ↓
API  /api/v1/track/labels/{code}  →  前端渲染
```

---

## 二、赛道股池定义

硬编码在 `scripts/fetch_track_data.py` 的 `UNIVERSE` 字典中：

| 赛道 | 目录名 | 股票数 | 成分股 |
|------|--------|--------|--------|
| 半导体 | `semiconductor/` | 8 | 中芯国际、北方华创、中微公司、寒武纪、风华高科、生益科技、三安光电、兆易创新 |
| AI | `ai/` | 5 | 中际旭创、工业富联、海光信息、新易盛、光迅科技 |
| 机器人 | `robot/` | 5 | 汇川技术、绿的谐波、双环传动、步科股份、中大力德 |
| 存储 | `storage/` | 5 | 兆易创新、北京君正、澜起科技、华天科技、长电科技 |

> 注：兆易创新（603986.SH）同时存在于「半导体」和「存储」两个赛道。

---

## 三、数据获取脚本

### 文件：`scripts/fetch_track_data.py`

**运行方式：**
```bash
cd .
python scripts/fetch_track_data.py
```

### 3.1 核心流程

```python
main()
  ├── 遍历 UNIVERSE（4 个赛道 × N 只股票）
  │     └── fetch_stock(code, name, track_dir)
  │           ├── rate_limit()           # 频率控制：间隔 ≥ 1s
  │           ├── bs.login()             # baostock 登录
  │           ├── bs.query_history_k_data_plus()  # 拉取前复权日线
  │           └── 写入 CSV              # datas/tracks/{赛道}/{code}.csv
  └── generate_universe_csv()           # 生成 datas/universe.csv 索引
```

### 3.2 baostock 调用参数

| 参数 | 值 | 说明 |
|------|----|------|
| `code` | `sh.688981` / `sz.000636` | baostock 格式（需 `to_bs_code()` 转换）|
| `fields` | `date,open,high,low,close,volume,amount` | 7 列 |
| `start_date` | `2000-01-01` | 拉取全量历史 |
| `end_date` | 昨日 | `datetime.now() - 1d` |
| `frequency` | `d` | 日线 |
| `adjustflag` | `2` | 前复权 |

### 3.3 代码转换

```python
def to_bs_code(code: str) -> str:
    """000636.SZ → sz.000636"""
    sym, market = code.split(".")
    return f"{market.lower()}.{sym}"
```

### 3.4 频率控制 & 重试机制

| 配置项 | 值 | 说明 |
|--------|----|------|
| `REQ_INTERVAL` | 1.0s | 每次请求前强制 sleep，防止被封 IP |
| `MAX_RETRIES` | 3 | 单只股票最大重试次数 |

失败场景（login 失败、无数据、异常）均会 `sleep(2.0)` 后重试。

### 3.5 CSV 输出格式

```
datas/tracks/semiconductor/688981.SH.csv
datas/tracks/ai/300308.SZ.csv
...
```

文件头：
```
date,open,high,low,close,volume,amount
2005-07-19,5.23,5.45,5.18,5.40,1234567,6654321.00
...
```

### 3.6 universe.csv

全量索引文件，记录所有股票的元信息：

```
code,name,track,ipo_date,status
688981.SH,中芯国际,semiconductor,2004-03-11,1
002371.SZ,北方华创,semiconductor,2010-02-09,1
...
```

---

## 四、数据库表结构

### 4.1 tracks（赛道表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | String(36) UUID | 主键 |
| `name` | String(50) | 唯一标识，如 `semiconductor` |
| `display_name` | String(100) | 中文名，如「半导体」 |
| `description` | Text | 描述 |
| `sort_order` | Integer | 排序 |
| `is_active` | Integer | 是否启用 |

### 4.2 track_stocks（自选股池表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | String(20) | 主键，如 `000636.SZ` |
| `name` | String(50) | 股票名称 |
| `ipo_date` | String(10) | 上市日期 |
| `status` | String(10) | 上市状态 |

### 4.3 track_stock（多对多关联表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `track_id` | String(36) FK | → tracks.id |
| `stock_code` | String(20) FK | → track_stocks.code |

### 4.4 track_data_cache（行情缓存表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 自增主键 |
| `stock_code` | String(20) FK | → track_stocks.code |
| `trade_date` | String(10) | `YYYY-MM-DD` |
| `open_px/high_px/low_px/close_px` | Float | OHLC 价格 |
| `volume` | Float | 成交量（股） |
| `amount` | Float | 成交额（元） |
| `is_stopped/is_limit_up/is_limit_down` | Integer | 停牌/涨停/跌停标记 |

### 4.5 feature_white_list / feature_black_list

Phase C 使用，已在 Phase A 建表，字段见 `app/models/track.py`。

---

## 五、数据导入流程

### CSV → SQLite

通过 `TrackService.import_csv_to_cache()` 实现：

```python
# 1. 读取 CSV
df = pd.read_csv(csv_path)  # 7列：date,open,high,low,close,volume,amount

# 2. 清空该股旧数据
DELETE FROM track_data_cache WHERE stock_code = ?

# 3. 逐行插入 TrackDataCache
for row in df.iterrows():
    TrackDataCache(stock_code=..., trade_date=..., open_px=..., ...)

# 4. commit
```

全量导入（23 只股票，约 64,000 条日线）。

---

## 六、标签生成逻辑（防未来泄露）

### 核心原则

> **shift(1)**：t 日特征只能对齐 t+1 日及以后的收益，严禁未来函数。

### `TrackService.generate_labels()` 实现

```python
# 未来收益（从 close 计算）
df["fwd_1d_return"]  = df["close_px"].pct_change(-1).shift(1)   # t日对齐t+1收益
df["fwd_5d_return"]  = df["close_px"].pct_change(-5).shift(1)
df["fwd_20d_return"] = df["close_px"].pct_change(-20).shift(1)

# 涨跌停标记
df["is_limit_up"]   = (close >= high * 0.999) & (close > open)
df["is_limit_down"] = (close <= low * 1.001) & (close < open)

# 过滤 fwd_1d_return 为 NaN 的行（最后一条）
df.dropna(subset=["fwd_1d_return"])
```

**标签说明：**

| 标签 | 含义 | 计算方式 |
|------|------|----------|
| `fwd_1d_return` | 次日收益 | `pct_change(-1).shift(1)` |
| `fwd_5d_return` | 5日收益 | `pct_change(-5).shift(1)` |
| `fwd_20d_return` | 20日收益 | `pct_change(-20).shift(1)` |
| `is_limit_up` | 是否涨停 | close ≈ high 且 close > open |
| `is_limit_down` | 是否跌停 | close ≈ low 且 close < open |

---

## 七、API 接口

### GET `/api/v1/track/tracks`

返回所有赛道列表 + 成分股。

**Response：**
```json
{
  "total": 4,
  "items": [
    {
      "id": "uuid",
      "name": "semiconductor",
      "display_name": "半导体",
      "stock_count": 8,
      "stocks": [
        {"code": "688981.SH", "name": "中芯国际", "ipo_date": "...", "status": "1"}
      ]
    }
  ]
}
```

### GET `/api/v1/track/labels/{stock_code}`

返回该股带标签的日线数据。

**Response：**
```json
{
  "stock_code": "000636.SZ",
  "data_points": [
    {
      "trade_date": "2024-01-02",
      "close_px": 12.34,
      "fwd_1d_return": 0.0123,
      "fwd_5d_return": 0.0456,
      "fwd_20d_return": 0.0789,
      "is_limit_up": false,
      "is_limit_down": false
    }
  ],
  "total": 4500
}
```

### GET `/api/v1/track/factors/whitelist`

因子白名单（Phase C 填充，Phase A 仅建表）。

### GET `/api/v1/track/factors/blacklist`

因子黑名单（Phase C 填充，Phase A 仅建表）。

---

## 八、目录结构

```
datas/
├── universe.csv                     # 全自选池索引（fetch_track_data.py 生成）
└── tracks/
    ├── semiconductor/               # 半导体赛道
    │   ├── 688981.SH.csv
    │   ├── 002371.SZ.csv
    │   └── ... (8 只)
    ├── ai/                          # AI 赛道
    │   ├── 300308.SZ.csv
    │   └── ... (5 只)
    ├── robot/                       # 机器人赛道
    │   ├── 300124.SZ.csv
    │   └── ... (5 只)
    └── storage/                     # 存储赛道
        ├── 603986.SH.csv
        └── ... (5 只)
```

---

## 九、关键约束

1. **数据源仅限 baostock**：前复权日线，7 列固定格式
2. **频率控制强制**：每次请求间隔 ≥ 1s，防止封 IP
3. **shift(1) 强制**：所有标签/特征必须向右移 1 日，防止未来函数泄露
4. **上游验收通过才允许下游读取**：Phase B 必须确认 Phase A 数据完整性后才可运行
5. **CSV 是中间介质**：拉取后存入 SQLite（track_data_cache），后续流程统一读库
