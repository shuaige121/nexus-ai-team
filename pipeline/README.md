# NEXUS Pipeline — Phase 2B

Redis Streams 工作单管道 + Telegram 集成

## 架构概览

```
┌─────────────┐
│   Telegram  │
│     Bot     │
└──────┬──────┘
       │ HTTP POST
       ▼
┌─────────────────────────────────────────────┐
│           FastAPI Gateway                   │
│  ┌───────────────────────────────────────┐  │
│  │  AdminAgent.create_work_order()       │  │
│  └───────────────┬───────────────────────┘  │
│                  │                           │
│  ┌───────────────▼───────────────────────┐  │
│  │  WorkOrderDB.create_work_order()      │  │
│  │  → PostgreSQL work_orders table       │  │
│  └───────────────┬───────────────────────┘  │
│                  │                           │
│  ┌───────────────▼───────────────────────┐  │
│  │  QueueManager.enqueue()               │  │
│  │  → Redis Streams nexus:work_orders    │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
                   │
                   │ Background Loop
                   ▼
┌─────────────────────────────────────────────┐
│           Dispatcher (Worker)               │
│  ┌───────────────────────────────────────┐  │
│  │  consume() from Redis Streams         │  │
│  └───────────────┬───────────────────────┘  │
│                  │                           │
│  ┌───────────────▼───────────────────────┐  │
│  │  ModelRouter.chat()                   │  │
│  │  → CEO / Director / Intern            │  │
│  └───────────────┬───────────────────────┘  │
│                  │                           │
│  ┌───────────────▼───────────────────────┐  │
│  │  update_status() → completed          │  │
│  │  insert_agent_metric() → metrics      │  │
│  │  publish_event() → WebSocket          │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

## 快速开始

### 1. 启动基础设施

```bash
# 启动 PostgreSQL + Redis
docker compose up -d postgres redis

# 初始化数据库 schema
docker compose exec postgres psql -U nexus -d nexus < db/schema.sql
```

### 2. 安装依赖

```bash
pip install -e ".[dev]"
```

### 3. 配置环境变量

```bash
cp .env.example .env

# 编辑 .env，至少配置：
# - DATABASE_URL=postgresql+psycopg://nexus:your-password@localhost:5432/nexus
# - REDIS_URL=redis://localhost:6379/0
# - ANTHROPIC_API_KEY=sk-ant-...
# - TELEGRAM_BOT_TOKEN=...
```

### 4. 启动 Gateway

```bash
uvicorn gateway.main:app --reload
```

Gateway 会自动：
- 连接 PostgreSQL
- 连接 Redis
- 启动 Dispatcher 后台循环

### 5. 启动 Telegram Bot

```bash
python3 -c "
import asyncio
from interfaces.telegram import create_telegram_bot

async def main():
    bot = create_telegram_bot()
    await bot.start()

asyncio.run(main())
"
```

## 核心模块

### WorkOrderDB (`pipeline/work_order.py`)

PostgreSQL 工作单管理：

```python
from pipeline import WorkOrderDB

db = WorkOrderDB("postgresql+psycopg://nexus:your-password@localhost:5432/nexus")
await db.connect()

# 创建工作单
await db.create_work_order(
    wo_id="WO-20260217-0001",
    intent="build_feature",
    difficulty="normal",
    owner="director",
    compressed_context="Build email feature",
    relevant_files=["main.py"],
    qa_requirements="Must run without errors",
)

# 查询工作单
wo = await db.get_work_order("WO-20260217-0001")

# 更新状态
await db.update_status("WO-20260217-0001", "completed")

# 插入 audit log
await db.insert_audit_log(
    work_order_id="WO-20260217-0001",
    session_id=None,
    actor="director",
    action="process_complete",
    status="success",
    details={"latency_ms": 1234},
)

# 插入 agent metric
await db.insert_agent_metric(
    work_order_id="WO-20260217-0001",
    agent_name="director_agent",
    role="director",
    model="claude-sonnet-4-5",
    provider="anthropic",
    success=True,
    latency_ms=1234,
    prompt_tokens=100,
    completion_tokens=50,
    cost_usd=0.0045,
)

# 查询成本
cost = await db.get_cost_summary("today")
# {'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150, 'total_cost': 0.0045}

await db.close()
```

### QueueManager (`pipeline/queue.py`)

Redis Streams 队列管理：

```python
from pipeline import QueueManager

queue = QueueManager("redis://localhost:6379/0", stream_name="nexus:work_orders")
await queue.connect()

# 生产者：入队
entry_id = await queue.enqueue(
    "WO-20260217-0001",
    {"user_message": "Build email feature", "session_id": "sess-123"},
)

# 消费者：出队
messages = await queue.consume(
    consumer_group="nexus-dispatcher",
    consumer_name="worker-1",
    count=1,
    block_ms=5000,
)

for msg in messages:
    wo_id = msg["work_order_id"]
    payload = msg["payload"]

    # ... process work order ...

    # ACK
    await queue.ack(msg["entry_id"], consumer_group="nexus-dispatcher")

# Pub/Sub 事件推送
await queue.publish_event(
    "nexus:progress:WO-20260217-0001",
    {"status": "in_progress", "progress": 50},
)

await queue.close()
```

### Dispatcher (`pipeline/dispatcher.py`)

工作单分发器（后台循环）：

```python
from pipeline import Dispatcher, QueueManager, WorkOrderDB
from nexus_v1.model_router import ModelRouter

db = WorkOrderDB("postgresql+psycopg://...")
queue = QueueManager("redis://...")
router = ModelRouter()

await db.connect()
await queue.connect()

dispatcher = Dispatcher(db, queue, router)

# 启动后台循环
await dispatcher.start()

# ... dispatcher 持续运行 ...

# 停止
await dispatcher.stop()
```

## 端到端测试

```bash
# 单元测试（无需外部服务）
pytest tests/test_pipeline_integration.py::test_work_order_creation -v

# 集成测试（需要 PostgreSQL + Redis）
pytest tests/test_pipeline_integration.py -v

# E2E 测试（需要 Gateway 运行）
uvicorn gateway.main:app &
sleep 3
pytest tests/test_pipeline_integration.py::test_telegram_gateway_integration -v
```

## 数据流

### 1. 用户发送消息

Telegram → `gateway_client.send_message()` → `POST /api/chat`

### 2. 创建工作单

```python
wo = admin_agent.create_work_order(user_message="...")
await db.create_work_order(...)  # → PostgreSQL
await queue.enqueue(wo.id, {...})  # → Redis Streams
```

### 3. Dispatcher 处理

```python
# 后台循环
messages = await queue.consume(...)
for msg in messages:
    wo = await db.get_work_order(msg["work_order_id"])
    await db.update_status(wo["id"], "in_progress")

    # 调用 LLM
    response = router.chat([...], role=wo["owner"])

    # 记录 metrics
    await db.insert_agent_metric(...)
    await db.update_status(wo["id"], "completed")

    # 推送进度
    await queue.publish_event(f"nexus:progress:{wo['id']}", {...})

    await queue.ack(msg["entry_id"])
```

## 成本计算

基于 PROJECT_PLAN.md 的定价（USD per 1M tokens）：

| Role     | Input  | Output |
|----------|--------|--------|
| CEO      | $5.00  | $25.00 |
| Director | $3.00  | $15.00 |
| Intern   | $0.80  | $4.00  |
| Admin    | $0.00  | $0.00  | (local model)

计算公式：

```python
cost = (prompt_tokens / 1_000_000) * input_price + \
       (completion_tokens / 1_000_000) * output_price
```

## WebSocket 实时推送

Dispatcher 通过 Redis Pub/Sub 发布进度事件：

```python
await queue.publish_event(
    f"nexus:progress:{work_order_id}",
    {
        "work_order_id": "WO-...",
        "status": "in_progress",  # queued / in_progress / completed / failed
        "data": {...},
    },
)
```

Gateway WebSocket 可以订阅这些事件（待实现）。

## 故障处理

### 重试机制

Work order 有 `retry_count` 字段。Dispatcher 失败时会：
1. 更新状态为 `failed`
2. `retry_count += 1`
3. 记录 `last_error`
4. ACK 消息（避免阻塞队列）

手动重试：
```python
# 重新入队
await queue.enqueue(wo_id, {...})
```

### 死信队列

如果 `retry_count > 3`，应该：
1. 更新状态为 `blocked`
2. 通知 Board（人工介入）

## 监控

查询系统状态：

```python
status = await db.get_system_status()
# {
#   "work_orders": {
#     "queued": 5,
#     "in_progress": 2,
#     "completed": 100,
#     "failed": 3
#   },
#   "timestamp": "2026-02-17T12:34:56"
# }
```

查询成本：

```python
cost_today = await db.get_cost_summary("today")
cost_week = await db.get_cost_summary("week")
cost_month = await db.get_cost_summary("month")
```

查询 audit logs：

```python
logs = await db.get_recent_audit_logs(limit=10)
```

## 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `DATABASE_URL` | Yes | PostgreSQL 连接 URL |
| `REDIS_URL` | Yes | Redis 连接 URL |
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot token |
| `API_SECRET` | No | Gateway auth (dev 可留空) |

## Phase 3 计划

- [ ] WebSocket 订阅进度事件（Redis Pub/Sub → WebSocket broadcast）
- [ ] /status /cost /audit 查询真实数据
- [ ] 图片/语音消息处理
- [ ] QA 验证集成
- [ ] 死信队列和人工介入
- [ ] Prometheus metrics 导出
