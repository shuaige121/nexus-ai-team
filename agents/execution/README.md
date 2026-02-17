# NEXUS Execution Layer (Phase 2A)

## 概述

Phase 2A 实现了 NEXUS 的执行层，包括三个执行 agent（CEO/Director/Intern）和自动 escalation 系统。

## 架构

```
User Message
    ↓
Admin Agent (compress + classify)
    ↓
┌───────────────────────────────┐
│   Escalation Manager          │
│                               │
│   Intern (Haiku)             │
│      ↓ (fails)               │
│   Director (Sonnet)          │
│      ↓ (fails)               │
│   CEO (Opus)                 │
│      ↓ (fails 3x)            │
│   → Board Notification       │
└───────────────────────────────┘
    ↓
QA Validation (self-test)
    ↓
Return Result
```

## 组件

### 1. ExecutionAgent (`executor.py`)

负责执行 work order 的核心 agent。

**功能：**
- 根据 difficulty 使用对应模型（CEO/Director/Intern）
- 执行任务并生成输出
- 自我测试验证输出质量
- 支持 role override（用于 escalation）

**模型映射：**
- **CEO** → Claude Opus 4.6 (complex tasks)
- **Director** → Claude Sonnet 4.5 (normal tasks)
- **Intern** → Claude Haiku 3.5 (trivial tasks)

**示例：**
```python
from agents.execution.executor import ExecutionAgent
from nexus_v1.admin import WorkOrder

agent = ExecutionAgent()
work_order = WorkOrder(
    id="WO-001",
    intent="build_feature",
    difficulty="normal",
    owner="director",
    compressed_context="Build a calculator function",
    relevant_files=[],
    qa_requirements="Must add two numbers correctly"
)

result = agent.execute(work_order)
print(f"Success: {result.success}")
print(f"Output: {result.output}")
```

### 2. EscalationManager (`escalation.py`)

管理自动 escalation 流程。

**Escalation 规则：**
1. 从 work order 的 owner 开始执行
2. 如果失败，升级到下一级别
3. Escalation chain: Intern → Director → CEO
4. 最多尝试 3 次
5. 3 次失败后上报 Board

**示例：**
```python
from agents.execution.escalation import EscalationManager

mgr = EscalationManager()
result = mgr.execute_with_escalation(work_order)

if result.status == "success":
    print("完成！")
elif result.status == "escalated":
    print(f"经过 {result.attempt_count} 次尝试完成")
elif result.status == "needs_board":
    print(f"需要 Board 干预: {result.board_notification}")
```

### 3. ExecutionPipeline (`pipeline.py`)

完整的执行流水线。

**流程：**
1. Admin Agent：压缩 + 分类
2. Routing：根据 difficulty 分配 owner
3. Execution：执行 + escalation
4. QA：验证输出
5. Return：返回结果

**示例：**
```python
import asyncio
from agents.execution.pipeline import ExecutionPipeline

async def main():
    pipeline = ExecutionPipeline()
    result = await pipeline.process("Build a calculator")

    print(f"Work Order: {result.work_order_id}")
    print(f"Success: {result.success}")
    print(f"Output: {result.output}")
    print(f"Escalation: {result.escalation_info}")

asyncio.run(main())
```

## Gateway 集成

Phase 2A 已经集成到 FastAPI gateway 的 `/api/chat` 端点：

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Write a function to add two numbers",
    "conversation": []
  }'
```

**响应：**
```json
{
  "ok": true,
  "work_order_id": "WO-20260217-0001",
  "output": "def add(a, b):\n    return a + b",
  "qa_passed": true,
  "escalation": {
    "status": "success",
    "chain": ["director"],
    "attempts": 1
  }
}
```

## 测试

### 单元测试

```bash
# 测试 ExecutionAgent
python3 -m unittest tests/execution/test_executor.py -v

# 测试 EscalationManager
python3 -m unittest tests/execution/test_escalation.py -v

# 测试 ExecutionPipeline
python3 -m unittest tests/execution/test_pipeline.py -v
```

### 集成测试

```bash
# 完整流程测试
python3 -m unittest tests/test_integration_phase2a.py -v
```

## 测试覆盖

- ✅ 成功执行（无 escalation）
- ✅ Intern → Director escalation
- ✅ Director → CEO escalation
- ✅ 完整 escalation chain（Intern → Director → CEO）
- ✅ Board escalation（3 次失败）
- ✅ Self-test 通过/失败
- ✅ Unclear difficulty 处理
- ✅ 异常处理
- ✅ Role override
- ✅ 完整 pipeline 集成

## 配置

执行层使用环境变量配置模型：

```bash
# .env
ANTHROPIC_API_KEY=your-key-here
NEXUS_MODEL_CEO=claude-opus-4-6
NEXUS_MODEL_DIRECTOR=claude-sonnet-4-5-20250929
NEXUS_MODEL_INTERN=claude-haiku-3-5
NEXUS_MODEL_ADMIN=qwen3:8b
```

## 下一步

- [ ] Phase 2B: Telegram Bot 集成
- [ ] Phase 3: Web GUI
- [ ] Phase 3: 完整 QA framework（使用 qa/runner.py）
- [ ] Phase 4: PostgreSQL 日志和审计
- [ ] Phase 4: Redis Streams 消息队列
- [ ] Phase 5: 监控和指标

## 文件结构

```
agents/execution/
├── __init__.py          # Package exports
├── executor.py          # ExecutionAgent
├── escalation.py        # EscalationManager
├── pipeline.py          # ExecutionPipeline
└── README.md           # 本文档

tests/execution/
├── __init__.py
├── test_executor.py     # ExecutionAgent 测试
├── test_escalation.py   # EscalationManager 测试
└── test_pipeline.py     # ExecutionPipeline 测试

tests/
└── test_integration_phase2a.py  # 集成测试
```
