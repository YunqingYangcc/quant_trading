# AGENTS.md - 赛道量化系统

赛道型量化系统，聚焦个人看好的核心赛道（半导体/AI/机器人/存储），量化数据辅助选股。

**Tech Stack**: Python 3.10+ (FastAPI, SQLAlchemy 2.0, Pydantic) | Vue 3 + TypeScript (Vite, Element Plus, ECharts) | SQLite

## 项目结构

```
backend/app/          # FastAPI 后端
  api/track.py        # 赛道 CRUD + 标签数据
  api/ml_api.py       # AI 模型 API（Phase E 填充）
  services/           # 业务逻辑
  models/             # SQLAlchemy ORM
  schemas/            # Pydantic DTO
  features/           # 特征工程
  db/                 # 数据库连接
frontend/             # Vue 3 前端
scripts/              # 数据获取脚本
datas/tracks/         # 赛道股票 CSV 数据
docs/                 # 开发文档
```

## 构建命令

```bash
# 后端
cd backend && pip install -e .
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend && npm install && npm run dev
```

## 开发计划

见 `docs/REAL_DEV_PLAN.md`（Phase A-H 流水线）

## 可用 Skills

项目集成了 12 个 Skill（`.qoder/skills/`），分为量化业务和工程通用两类：

### 量化业务 Skill（赛道专属）

| Skill | 触发方式 | 用途 |
|:------|:---------|:-----|
| `/add-feature` | 说"加个特征"自动触发 | 新增特征必须走 6 步验证流程（计算→入库→Alphalens→白名单） |
| `/check-data` | 说"检查数据"自动触发 | 数据质量巡检：完整性/未来泄露/NaN/重复 |
| `/train-model` | 说"训练模型"自动触发 | LightGBM 固定参数训练，防无限调参 |
| `/run-backtest` | 说"跑回测"自动触发 | 锁定滑点/手续费/仓位，防刷指标 |
| `/review-phase` | `/review-phase B` 等 | 按阶段清单验收，防跳步 |

### 工程通用 Skill（跨项目可用）

| Skill | 使用场景 |
|:------|:---------|
| `code-review-and-quality` | 提交前多维度代码审查（Bug/安全/性能/风格） |
| `git-commit` | 生成 Conventional Commit 规范提交信息 |
| `security-audit` | API 安全审计（SQL 注入/JWT/XSS） |
| `spec-driven-development` | 新功能先写 Spec 再写代码，防需求漂移 |
| `planning-and-task-breakdown` | 大任务拆解为有序子任务 |
| `incremental-implementation` | 多文件改动时增量交付，不一次改崩 |
| `pr-description-writer` | 生成结构化 PR 描述 |
| `pua` | 连续失败时自动触发加压鞭策 |

### 开发时序中的 Skill 调用

```
Phase 开发 → /check-data（数据检查）→ /add-feature（加特征）→ /train-model（训练）
          → /run-backtest（回测）→ /review-phase（验收）
提交代码 → code-review-and-quality（代码审查）→ git-commit（提交）
启动新功能 → spec-driven-development → planning-and-task-breakdown
          → incremental-implementation → pr-description-writer
```

## 关键约束

1. 所有时序数据 shift(1) 防未来泄露
2. 黑名单特征全程禁用
3. 上游不验收通过，下游禁止读取数据
4. 赛道模型独立训练、不通用
