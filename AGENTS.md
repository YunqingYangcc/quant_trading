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

## 关键约束

1. 所有时序数据 shift(1) 防未来泄露
2. 黑名单特征全程禁用
3. 上游不验收通过，下游禁止读取数据
4. 赛道模型独立训练、不通用
