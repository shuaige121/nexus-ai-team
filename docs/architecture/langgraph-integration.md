# LangGraph 集成架构设计

**文档版本**: v1.0  
**作者**: Architecture Manager  
**日期**: 2026-02-19  
**状态**: 草稿，待 CEO 审批

---

## 1. 现状分析

### 1.1 两个执行宇宙的核心问题

当前 NEXUS 存在两套并行但互不通信的执行系统：

**宇宙 A — AgentOffice（文件系统驱动）**
- 入口：`agentoffice/engine/activate.py`
- 状态载体：YAML contract 文件（`company/contracts/pending/`）
- 通信协议：文件写入（INBOX/ 目录）
- 执行模式：同步递归调用（`activate()` → `route_contract()` → `activate()` 深度优先）
- 持久化：文件系统（YAML + Markdown）
- 问题：无法暂停/恢复，无并发，循环深度用 `MAX_CHAIN_DEPTH=20` 硬限制

**宇宙 B — Gateway（FastAPI + Redis + PostgreSQL）**
- 入口：`gateway/main.py`（FastAPI）
- 状态载体：PostgreSQL `work_orders` 表 + Redis Stream `nexus:work_orders`
- 通信协议：Redis Streams 消息队列
- 执行模式：异步（`asyncio`）+ Dispatcher 消费者
- 持久化：PostgreSQL（work_orders、audit_logs、agent_metrics）
- 问题：AdminAgent 只做分类路由，没有真正的 CEO→Manager→Worker 层级，执行层（`agents/execution/`）是独立模块

**根本矛盾**：AgentOffice 的层级语义（CEO/Manager/Worker/QA 角色分工、contract 流转、记忆文件）与 Gateway 的 async 基础设施（PG、Redis、WebSocket）之间没有桥梁。

### 1.2 现有代码价值评估

| 模块 | 保留 | 替换 | 理由 |
|------|------|------|------|
| `gateway/main.py` FastAPI 框架 | 保留 | - | LangGraph graph 作为 background task 插入，HTTP/WS 端点不变 |
| `gateway/auth.py` / `rate_limiter.py` | 保留 | - | 与 graph 无关，保持不变 |
| `pipeline/work_order.py` WorkOrderDB | 保留 | - | 直接复用为 PostgresSaver 的底层连接池 |
| `pipeline/queue.py` QueueManager | 保留（降级） | 触发层 | Redis Stream 从"主队列"降级为"外部事件入口"，graph 自管状态 |
| `agentoffice/engine/contract_manager.py` | 重构 | contract YAML 文件 | 合并到 LangGraph State，YAML 文件只作归档 |
| `agentoffice/engine/activate.py` | 重构 | 递归同步调用 | 拆解为 graph node 函数，保留 LLM 调用逻辑 |
| `agentoffice/engine/llm_client.py` | 保留 | - | node 函数内部直接调用 |
| `agentoffice/engine/prompt_builder.py` | 保留 | - | 同上 |
| `agents/execution/executor.py` | 保留 | - | Worker node 内部调用 |
| `agents/execution/escalation.py` | 替换 | - | Escalation 逻辑改为 graph 条件边，更清晰 |
| `agents/execution/pipeline.py` ExecutionPipeline | 替换 | - | 被 LangGraph graph 取代 |
| `nexus_v1/admin.py` AdminAgent | 保留（降级） | - | 降级为 graph 入口前的"预处理节点"，保留 compress+classify |
| `heartbeat/` | 保留 | - | 运维监控，与 graph 无关 |

---

## 2. 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         外部接入层                                        │
│                                                                         │
│   Telegram Bot ──┐                                                       │
│                  ├──▶ FastAPI Gateway (gateway/main.py)                  │
│   Web Browser ───┘     │   Auth / RateLimit / RequestID middleware       │
│                        │                                                 │
└────────────────────────┼────────────────────────────────────────────────┘
                         │  POST /api/chat  或  WS /ws
                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     LangGraph 执行层（新增）                              │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    NEXUSGraph (StateGraph)                        │   │
│  │                                                                   │   │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │   │
│  │  │  INTAKE  │───▶│   CEO    │───▶│ MANAGER  │───▶│  WORKER  │  │   │
│  │  │  node    │    │  node    │    │  node    │    │  node    │  │   │
│  │  └──────────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘  │   │
│  │        ▲              │               │               │         │   │
│  │        │         interrupt()     interrupt()          │         │   │
│  │        │         (CEO审批点)     (可选暂停)           ▼         │   │
│  │        │              │               │          ┌──────────┐  │   │
│  │        │              ▼               ▼          │    QA    │  │   │
│  │        │         ┌─────────────────────────┐     │  node    │  │   │
│  │        │         │   条件路由 (边)           │     └────┬─────┘  │   │
│  │        │         │  • needs_clarification  │          │         │   │
│  │        │         │  • approved → MANAGER   │     PASS │ FAIL    │   │
│  │        │         │  • rejected → END       │          │    ▼    │   │
│  │        │         └─────────────────────────┘          │  retry  │   │
│  │        │                                               │  (max3) │   │
│  │        │                                               ▼         │   │
│  │        │                                          ┌──────────┐  │   │
│  │        │                                          │ DELIVER  │  │   │
│  │        │                                          │  node    │  │   │
│  │        │                                          └──────────┘  │   │
│  │        │                                               │         │   │
│  └────────┼───────────────────────────────────────────────┼─────────┘   │
│           │                                               │             │
│           └───────────────────────────────────────────────┘             │
│                    PostgresSaver（Checkpointer）                         │
│                    thread_id = work_order_id                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       基础设施层（保留）                                  │
│                                                                         │
│  PostgreSQL ──────────────────────────────────────────────────────────  │
│    • work_orders 表（状态记录）                                          │
│    • audit_logs 表（审计日志）                                           │
│    • agent_metrics 表（性能指标）                                        │
│    • langgraph_checkpoints 表（graph 检查点，PostgresSaver 自建）        │
│                                                                         │
│  Redis ──────────────────────────────────────────────────────────────── │
│    • nexus:work_orders Stream（外部事件入口，触发 graph 启动）           │
│    • pub/sub（WebSocket 实时推送）                                       │
│                                                                         │
│  文件系统（AgentOffice 归档模式）                                        │
│    • agents/{role}/MEMORY.md（持久记忆）                                 │
│    • company/contracts/archived/（历史合同归档）                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. State Schema 定义

### 3.1 设计原则

State 是 graph 的"共享内存"，所有 node 只通过读写 State 通信，不直接调用彼此。

以下 TypedDict 定义了 contract 流转的完整状态，覆盖从用户输入到最终交付的全周期。

```python
# langgraph_core/state.py

from __future__ import annotations

from typing import Annotated, Literal, TypedDict
import operator

# ─── 枚举类型 ────────────────────────────────────────────────────────────────

ContractStatus = Literal[
    "intake",           # 刚进入 graph，未分类
    "ceo_review",       # CEO 正在分析和拆分需求
    "ceo_approved",     # CEO 已批准，等待分发给 Manager
    "ceo_rejected",     # CEO 拒绝，需要用户澄清
    "manager_planning", # Manager 正在估算上下文预算、拆分子任务
    "manager_dispatched", # Manager 已分配子任务给 Worker
    "worker_executing", # Worker 正在执行
    "qa_reviewing",     # QA 正在验收
    "qa_passed",        # QA 通过，等待最终交付
    "qa_failed",        # QA 失败，等待返工
    "delivered",        # 已交付给用户（Board）
    "escalated",        # 超过重试次数，上报 Board
    "failed",           # 终态：失败
]

AgentRole = Literal["ceo", "manager", "worker", "qa", "board"]

Priority = Literal["low", "medium", "high", "critical"]

# ─── 子任务单元 ───────────────────────────────────────────────────────────────

class SubTask(TypedDict):
    """Manager 拆分出的最小工作单元。"""
    subtask_id: str          # 格式: ST-{parent_contract_id}-{seq}
    description: str         # 任务描述
    assigned_worker: str     # Worker agent_id（如 dept-gw-dev-01）
    acceptance_criteria: list[str]
    estimated_tokens: int    # Manager 预估的上下文消耗
    workspace_path: str      # Worker 的 WORKSPACE 路径
    reference_files: list[str]
    status: Literal["pending", "in_progress", "completed", "failed"]
    output: str | None       # Worker 产出
    retry_count: int         # 已重试次数

class QAResult(TypedDict):
    """QA 对单个子任务的验收结果。"""
    subtask_id: str
    passed: bool
    feedback: str            # 不通过时的具体原因
    reviewer: str            # QA agent_id
    reviewed_at: str         # ISO 8601 时间戳

# ─── 主 State ────────────────────────────────────────────────────────────────

class NEXUSState(TypedDict):
    """
    NEXUS LangGraph 主状态结构。
    thread_id 对应 work_order_id，由 PostgresSaver 持久化。
    """

    # ── 身份字段 ──────────────────────────────────────────────────────────────
    contract_id: str         # 全局唯一合同 ID，格式: CTR-{YYYYMMDD}-{seq}
    work_order_id: str       # 对应 PostgreSQL work_orders.id
    thread_id: str           # LangGraph thread，等于 work_order_id

    # ── 输入字段 ──────────────────────────────────────────────────────────────
    raw_user_message: str    # 用户原始输入（Board 指令）
    session_id: str | None   # WebSocket session_id，用于实时推送

    # ── 流程控制字段 ──────────────────────────────────────────────────────────
    status: ContractStatus
    current_node: str        # 当前所在 node 名称，用于 resume 时定位
    priority: Priority
    created_at: str          # ISO 8601
    updated_at: str          # ISO 8601

    # ── CEO 字段 ─────────────────────────────────────────────────────────────
    ceo_analysis: str | None        # CEO 对需求的分析摘要
    ceo_decision: Literal[
        "approve", "reject", "clarify"
    ] | None
    ceo_clarification_question: str | None  # CEO 需要用户澄清的问题
    modules: list[dict] | None       # CEO 拆分的功能模块列表（参考 JD.md 格式）

    # ── Manager 字段 ──────────────────────────────────────────────────────────
    target_manager: str | None       # 被分配的 Manager agent_id
    context_budget: dict | None      # Manager 的上下文预算估算结果
    subtasks: Annotated[             # 使用 operator.add 支持并发追加
        list[SubTask],
        operator.add
    ]

    # ── Worker 字段 ───────────────────────────────────────────────────────────
    worker_outputs: Annotated[       # 使用 operator.add 支持并发追加
        list[dict],
        operator.add
    ]
    escalation_chain: list[AgentRole]  # 已尝试的角色（escalation 历史）
    qa_retry_count: int              # 当前 QA 轮次（max: 3）

    # ── QA 字段 ───────────────────────────────────────────────────────────────
    qa_results: Annotated[
        list[QAResult],
        operator.add
    ]
    qa_overall_passed: bool | None

    # ── 交付字段 ──────────────────────────────────────────────────────────────
    final_output: str | None         # 最终交付给 Board 的内容
    delivery_method: Literal[
        "websocket", "telegram", "api_response"
    ] | None
    error: str | None                # 终态为 failed 时的错误信息

    # ── 审计字段 ──────────────────────────────────────────────────────────────
    audit_trail: Annotated[          # 追加式，记录每个关键操作
        list[dict],
        operator.add
    ]
```

### 3.2 State 字段说明

**分区设计原则**：State 按角色分区，每个 node 只写入自己分区的字段，读取上游分区的字段。

| 分区 | 字段前缀 | 写入 Node | 读取 Node |
|------|----------|-----------|-----------|
| 身份区 | `contract_id`, `work_order_id` | INTAKE | 全部 |
| 流程控制区 | `status`, `current_node` | 所有 node | 所有 node |
| CEO 区 | `ceo_*`, `modules` | CEO node | MANAGER node |
| Manager 区 | `target_manager`, `context_budget`, `subtasks` | MANAGER node | WORKER node |
| Worker 区 | `worker_outputs`, `escalation_chain` | WORKER node | QA node |
| QA 区 | `qa_results`, `qa_overall_passed` | QA node | DELIVER/retry |
| 交付区 | `final_output`, `delivery_method` | DELIVER node | - |

**Annotated + operator.add**：`subtasks`、`worker_outputs`、`qa_results`、`audit_trail` 四个列表字段使用 `Annotated[list, operator.add]`，支持 Send API 并发子任务时安全合并结果，无需手动 merge。

---

## 4. Graph 结构定义

### 4.1 节点清单

```
节点名称          对应角色              主要职责
──────────────    ──────────────────    ──────────────────────────────────────────
INTAKE            Admin (Qwen3 local)   接收原始输入，compress + classify，
                                        写入 work_orders 表，构建初始 State
CEO               CEO (Opus)            分析需求，拆分模块，做 approve/reject/clarify 决策
                                        [interrupt() 点：等待 Board 确认]
MANAGER           Manager (Sonnet)      估算上下文预算，拆分子任务，分配 Worker
WORKER            Worker (Haiku/Sonnet) 执行子任务，写 WORKSPACE，生成输出
QA                QA (Sonnet)           对照验收标准检查 Worker 输出，输出 PASS/FAIL
DELIVER           -（系统节点）         汇总结果，推送 WebSocket/Telegram，更新 PG 状态
CLARIFY           -（系统节点）         向用户返回澄清问题，等待输入后重回 CEO
```

### 4.2 Graph 结构定义（伪代码）

```python
# langgraph_core/graph.py

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import interrupt, Send

from .state import NEXUSState
from .nodes import (
    intake_node,
    ceo_node,
    manager_node,
    worker_node,
    qa_node,
    deliver_node,
    clarify_node,
)
from .routing import (
    route_after_ceo,
    route_after_qa,
    route_workers,
)

def build_nexus_graph(checkpointer: AsyncPostgresSaver) -> CompiledGraph:
    """构建并编译 NEXUS LangGraph。"""

    builder = StateGraph(NEXUSState)

    # ── 添加节点 ──────────────────────────────────────────────────────────────
    builder.add_node("INTAKE",   intake_node)
    builder.add_node("CEO",      ceo_node)
    builder.add_node("MANAGER",  manager_node)
    builder.add_node("WORKER",   worker_node)   # 支持 Send API 并发
    builder.add_node("QA",       qa_node)        # 支持 Send API 并发
    builder.add_node("DELIVER",  deliver_node)
    builder.add_node("CLARIFY",  clarify_node)

    # ── 固定边 ────────────────────────────────────────────────────────────────
    builder.add_edge(START,      "INTAKE")
    builder.add_edge("INTAKE",   "CEO")
    builder.add_edge("MANAGER",  "WORKER")   # 实际由 route_workers() 扩展为 Send
    builder.add_edge("CLARIFY",  "CEO")      # 用户回答澄清问题后，重回 CEO
    builder.add_edge("DELIVER",  END)

    # ── 条件边：CEO 决策路由 ──────────────────────────────────────────────────
    builder.add_conditional_edges(
        "CEO",
        route_after_ceo,
        {
            "approve":  "MANAGER",   # CEO 批准 → 分配给 Manager
            "clarify":  "CLARIFY",   # CEO 需要澄清 → 返回用户
            "reject":   END,         # CEO 拒绝（需求不合理）→ 直接结束
        }
    )

    # ── 条件边：QA 结果路由 ───────────────────────────────────────────────────
    builder.add_conditional_edges(
        "QA",
        route_after_qa,
        {
            "passed":       "DELIVER",  # QA 全部通过 → 交付
            "retry_worker": "WORKER",   # QA 失败且未超重试次数 → Worker 返工
            "escalate":     "DELIVER",  # QA 失败超过 3 次 → 上报 Board（特殊 DELIVER）
        }
    )

    # ── Send API：Manager → 多个 Worker 并发 ─────────────────────────────────
    # route_workers() 返回 list[Send("WORKER", subtask_state)]
    # 每个 Send 携带独立的子任务 State patch，并发执行
    builder.add_conditional_edges(
        "MANAGER",
        route_workers,   # 返回 Send API 对象列表
        ["WORKER"]
    )

    return builder.compile(checkpointer=checkpointer)
```

### 4.3 路由函数定义

```python
# langgraph_core/routing.py

from langgraph.types import Send
from .state import NEXUSState

def route_after_ceo(state: NEXUSState) -> str:
    """CEO 节点执行完毕后的路由逻辑。"""
    decision = state.get("ceo_decision")
    if decision == "approve":
        return "approve"
    elif decision == "clarify":
        return "clarify"
    else:
        return "reject"

def route_after_qa(state: NEXUSState) -> str:
    """QA 节点执行完毕后的路由逻辑。"""
    if state.get("qa_overall_passed"):
        return "passed"

    retry_count = state.get("qa_retry_count", 0)
    if retry_count < 3:
        return "retry_worker"
    else:
        return "escalate"

def route_workers(state: NEXUSState) -> list[Send]:
    """
    Manager 完成规划后，为每个子任务生成一个 Send 对象，
    实现 Worker 并发执行。
    """
    sends = []
    for subtask in state.get("subtasks", []):
        sends.append(
            Send("WORKER", {
                "current_subtask": subtask,
                "contract_id": state["contract_id"],
                "work_order_id": state["work_order_id"],
            })
        )
    return sends
```

### 4.4 interrupt() 放置策略

```
interrupt() 的放置必须在 node 函数内部，在 LLM 调用之前或之后均可。
NEXUS 设计两个 interrupt 点：

位置 1：CEO node 内，CEO 完成需求分析后
────────────────────────────────────────
场景：CEO 对需求有疑问，或模块拆分涉及高优先级/高风险决策
触发条件：ceo_decision == "clarify"，或合同金额/复杂度超过阈值
行为：graph 暂停，通过 WebSocket/Telegram 向 Board 推送问题
恢复：Board 回复后，调用 graph.invoke(resume_input, config) 继续

  def ceo_node(state: NEXUSState) -> dict:
      # ... CEO LLM 分析 ...
      analysis = call_ceo_llm(state)
      
      if analysis.needs_board_confirmation:
          # graph 在此暂停，等待外部 resume
          user_input = interrupt({
              "question": analysis.clarification_question,
              "modules_draft": analysis.modules,
              "contract_id": state["contract_id"],
          })
          # Board resume 后，user_input 包含 Board 的回复
          # 继续执行 ...

位置 2（可选）：Manager node 内，Manager 拆分完子任务后
────────────────────────────────────────────────────────
场景：Manager 估算子任务量超出预期，需要 CEO/Board 确认资源投入
触发条件：estimated_total_tokens > 100K 或 workers_needed > 5
行为：暂停并向 CEO 推送预估报告
恢复：CEO 或 Board 确认后继续

注意：interrupt() 只能在 graph 节点函数中调用，不能在工具函数中调用。
      恢复时使用 Command(resume=value) 通过同一 thread_id 重入。
```

---

## 5. FastAPI 集成方案

### 5.1 集成架构

LangGraph graph 以 **background coroutine** 的方式嵌入 FastAPI，不阻塞 HTTP 端点。

```
HTTP POST /api/chat
    │
    ├─ 创建 work_order_id（UUID）
    ├─ 写入 PostgreSQL work_orders（status=queued）
    ├─ enqueue 到 Redis Stream（可选，作为审计记录）
    ├─ 启动 asyncio.create_task(graph.ainvoke(...))
    └─ 立即返回 {"ok": true, "work_order_id": "..."}

WS /ws
    │
    ├─ 连接建立，注册 session_id → connection 映射
    ├─ 收到用户消息：触发 graph.ainvoke()
    │   graph 执行过程中，每个 node 完成后通过
    │   queue.publish_event() 推送进度到对应 session_id
    └─ interrupt() 触发时：推送"等待 Board 决策"消息

# 恢复 interrupt 的端点
POST /api/contracts/{contract_id}/resume
    │
    ├─ 接收 Board 的回复内容
    └─ 调用 graph.ainvoke(
           Command(resume={"board_reply": ...}),
           config={"configurable": {"thread_id": work_order_id}}
       )
```

### 5.2 关键改动：`gateway/main.py`

```python
# 新增：在 lifespan 中初始化 graph
@asynccontextmanager
async def lifespan(app: FastAPI):
    global db, queue, nexus_graph  # 新增 nexus_graph

    # ... 原有初始化 ...

    # 新增：初始化 LangGraph checkpointer（复用 PG 连接池）
    checkpointer = AsyncPostgresSaver.from_conn_string(settings.database_url)
    await checkpointer.setup()  # 自动建 langgraph_checkpoints 表

    nexus_graph = build_nexus_graph(checkpointer)

    yield
    # ... 原有 cleanup ...

# 修改：/api/chat 端点，启动 graph 而非直接调用 pipeline
@app.post("/api/chat")
async def chat(body: ChatRequest):
    work_order_id = generate_work_order_id()

    initial_state = NEXUSState(
        contract_id=generate_contract_id(),
        work_order_id=work_order_id,
        thread_id=work_order_id,
        raw_user_message=body.content,
        session_id=None,
        status="intake",
        # ... 其他字段初始化为 None / [] ...
    )

    config = {"configurable": {"thread_id": work_order_id}}

    # 非阻塞启动 graph
    asyncio.create_task(
        nexus_graph.ainvoke(initial_state, config=config)
    )

    return {"ok": True, "work_order_id": work_order_id, "status": "queued"}

# 新增：Board 恢复 interrupt 的端点
@app.post("/api/contracts/{contract_id}/resume")
async def resume_contract(contract_id: str, body: ResumeRequest):
    config = {"configurable": {"thread_id": body.work_order_id}}
    await nexus_graph.ainvoke(
        Command(resume={"board_reply": body.reply}),
        config=config,
    )
    return {"ok": True}
```

### 5.3 保留端点清单

以下现有端点**无需修改**：

| 端点 | 状态 | 说明 |
|------|------|------|
| `GET /health` | 保留 | 无关 |
| `GET /api/health/detailed` | 保留 | 无关 |
| `GET /api/agents` | 保留 | 读取静态配置 |
| `GET /api/skills` | 保留 | SkillRegistry 无关 |
| `GET /api/work-orders` | 保留 | 读 PG，graph 写入后可查 |
| `GET /api/metrics` | 保留 | 读 PG |
| `WS /ws` | 小改 | 消息触发改为调用 graph，进度推送保持 |

---

## 6. Checkpointer 方案

### 6.1 选型：AsyncPostgresSaver

**结论：使用 `langgraph-checkpoint-postgres` 的 `AsyncPostgresSaver`，复用现有 PostgreSQL 实例。**

理由：
- 现有 PG 已有 `work_orders`、`audit_logs` 等表，运维统一，无需引入新中间件
- `AsyncPostgresSaver` 支持 `asyncio`，与 FastAPI 的 async 模型完全匹配
- LangGraph 官方支持，稳定性有保障
- 相比 `MemorySaver`（只在内存，重启丢失）或 `SqliteSaver`（无法水平扩展），PG 更适合生产

**不选 RedisCheckpointer 的原因**：
- Redis 已承担 Stream 队列职责，双重角色会增加复杂度
- Redis 重启后 checkpoint 可能丢失（需要 AOF/RDB 配置）
- graph state 通常 1-10KB，PG 处理无压力

### 6.2 数据库表布局

```
PostgreSQL nexus 数据库
│
├── work_orders           ← 现有，gateway/pipeline 写入
├── audit_logs            ← 现有
├── agent_metrics         ← 现有
│
├── langgraph_checkpoints ← 新增，PostgresSaver 自动建表
│   ├── thread_id        （= work_order_id）
│   ├── checkpoint_id    （每个 node 完成后的快照 ID）
│   ├── parent_checkpoint_id
│   ├── checkpoint        （JSONB，graph state 序列化）
│   ├── metadata          （JSONB）
│   └── created_at
│
└── langgraph_writes      ← 新增，pending writes 暂存
```

### 6.3 thread_id 设计

`thread_id` = `work_order_id`，实现 **1 合同 = 1 执行线程 = 1 检查点序列**。

这样的好处是：
- `GET /api/contracts/{id}/state` 可以直接用 `thread_id` 查询当前 graph state
- 断点续传（如 interrupt 后 Board 延迟回复）天然支持
- 出问题时可以 replay：`graph.get_state_history(config)` 遍历所有历史快照

---

## 7. 迁移计划

### Phase L0：基础设施准备（1-2 天）

**目标**：安装依赖，建立 graph 骨架，跑通最简单的 INTAKE → CEO → END 路径。

1. 安装 `langgraph`、`langgraph-checkpoint-postgres` 依赖
2. 在 `pyproject.toml` 中添加依赖声明
3. 创建 `langgraph_core/` 目录结构（见第 8 节）
4. 定义 `NEXUSState`（`state.py`）
5. 实现 `intake_node`（直接复用 `AdminAgent.create_work_order()` 逻辑）
6. 实现最简 `ceo_node`（仅调用 LLM，不含 interrupt）
7. 编写 `build_nexus_graph()` 函数，使用 `MemorySaver` 临时 checkpointer
8. 写集成测试：验证 State 流通

**不动的代码**：`gateway/main.py`、所有现有端点、`pipeline/`、`agentoffice/`

---

### Phase L1：CEO 节点完整实现（2-3 天）

**目标**：CEO 能做真实决策，interrupt() 点可用。

1. 完善 `ceo_node`：集成 `agentoffice/engine/llm_client.py` 和 `prompt_builder.py`
2. 加入 `interrupt()` 调用（clarify 路径）
3. 实现 `clarify_node`（向 WebSocket 推送问题）
4. 在 `gateway/main.py` 新增 `POST /api/contracts/{id}/resume` 端点
5. 将 `AsyncPostgresSaver` 替换 `MemorySaver`
6. 运行端到端测试：用户提问 → CEO 分析 → CEO 要求澄清 → Board 回复 → CEO 批准

**不动的代码**：`agentoffice/engine/` 函数级别保持不变，CEO node 内部调用

---

### Phase L2：Manager + Worker 节点（3-4 天）

**目标**：完整的 CEO → Manager → Worker 流程跑通，Send API 并发生效。

1. 实现 `manager_node`：集成上下文预算估算逻辑（参考 Manager JD.md 的估算公式）
2. 实现 `route_workers()`：返回 `Send` 对象列表
3. 实现 `worker_node`：集成 `ExecutionAgent.execute()`（来自 `agents/execution/executor.py`）
4. 测试并发 Worker：同一合同下 3 个子任务并发执行，State 正确合并
5. 实现 `EscalationManager` 逻辑迁移到条件边（`route_after_qa` 中体现）

**可以停用的代码**：`agents/execution/pipeline.py` 的 `ExecutionPipeline` 类（被 graph 取代）

---

### Phase L3：QA 节点 + 完整循环（2-3 天）

**目标**：QA 验收、重试循环、最终交付全部跑通。

1. 实现 `qa_node`：集成 `agents/execution/executor.py` 的 self-test 逻辑，改为独立 QA agent
2. 实现 `route_after_qa()`：pass/retry/escalate 三路路由
3. 实现 `deliver_node`：更新 PG 状态，WebSocket 推送，归档 contract YAML
4. 完整 E2E 测试：用户输入 → CEO → Manager → Worker(x3 并发) → QA → 重试 → DELIVER
5. 压力测试：同时处理 5 个合同，验证 PG checkpointer 无冲突

---

### Phase L4：Gateway 切换（1-2 天）

**目标**：`/api/chat` 端点从原有 `Dispatcher + pipeline` 切换到 graph。

1. 修改 `gateway/main.py`：`lifespan` 中初始化 `nexus_graph`
2. 修改 `POST /api/chat`：触发 `graph.ainvoke()`
3. 保留原有 `WorkOrderDB`、`QueueManager` 初始化（兼容性）
4. 回归测试所有现有端点
5. 灰度切换：新增 `?use_graph=true` 参数，允许 A/B 对比

**可以停用的代码**：`agents/execution/escalation.py` 中的 `EscalationManager`（逻辑已内化为路由边）

---

### Phase L5：AgentOffice 融合（持续）

**目标**：AgentOffice 的文件系统操作成为 graph node 的副作用，而不是主流程。

1. `deliver_node` 负责将最终 contract 归档为 YAML 到 `company/contracts/archived/`
2. Worker node 执行完毕后同步写入对应 Agent 的 `MEMORY.md`
3. AgentOffice 的 `activate()` 保留作为"离线模式"入口（无 PG/Redis 时可用）
4. `agentoffice/engine/contract_manager.py` 降级为归档工具，不再是主流程

---

## 8. 文件结构提案

```
~/Desktop/nexus-ai-team/
│
├── langgraph_core/                    ← 新增目录（核心集成层）
│   ├── __init__.py
│   ├── state.py                       ← NEXUSState TypedDict 定义
│   ├── graph.py                       ← build_nexus_graph()，graph 编译
│   ├── routing.py                     ← 所有条件路由函数
│   │
│   ├── nodes/                         ← 每个 node 独立文件
│   │   ├── __init__.py
│   │   ├── intake_node.py             ← Admin 分类（复用 AdminAgent）
│   │   ├── ceo_node.py                ← CEO 决策（含 interrupt）
│   │   ├── manager_node.py            ← 上下文预算 + 子任务拆分
│   │   ├── worker_node.py             ← 执行（复用 ExecutionAgent）
│   │   ├── qa_node.py                 ← 验收（独立 QA 逻辑）
│   │   ├── deliver_node.py            ← 交付 + 归档
│   │   └── clarify_node.py            ← 澄清问询（向 Board 推送）
│   │
│   └── config.py                      ← graph 级别配置（retry 次数等常量）
│
├── gateway/
│   ├── main.py                        ← 改动：lifespan 注入 nexus_graph，
│   │                                     新增 /api/contracts/{id}/resume 端点
│   ├── schemas.py                     ← 改动：新增 ResumeRequest Pydantic 模型
│   └── ...（其他文件不变）
│
├── agentoffice/                       ← 保留，降级为"离线模式"和"归档工具"
│   └── ...（所有文件保留，不删除）
│
├── agents/
│   ├── execution/                     ← 保留 executor.py，停用 pipeline.py
│   │   ├── executor.py               （保留：worker_node 内部调用）
│   │   ├── escalation.py             （停用：逻辑已移入路由边）
│   │   └── pipeline.py               （停用：被 graph 取代）
│   └── ...
│
├── pipeline/
│   ├── work_order.py                  ← 保留：WorkOrderDB，供 nodes 使用
│   ├── queue.py                       ← 保留：降级为事件入口
│   └── ...
│
├── docs/
│   └── architecture/
│       └── langgraph-integration.md   ← 本文档
│
└── tests/
    └── langgraph/                     ← 新增测试目录
        ├── test_state.py              ← State 序列化/合并测试
        ├── test_graph_smoke.py        ← 最简 graph 冒烟测试
        ├── test_ceo_node.py
        ├── test_manager_worker.py     ← Send API 并发测试
        └── test_qa_retry.py           ← QA 重试循环测试
```

---

## 9. 关键架构决策记录（ADR）

### ADR-001：为什么不把 AgentOffice 整体替换

**决策**：AgentOffice 保留，降级为"离线模式"而不是删除。

**理由**：
- AgentOffice 的文件系统隔离设计是 NEXUS 的核心哲学（信息最小化原则），不应丢弃
- LangGraph 是调度骨架，AgentOffice 是角色约束机制，两者职责不重叠
- 降级后 AgentOffice 可以作为无网络环境下的 fallback 运行模式

### ADR-002：为什么选 PostgresSaver 而不是 RedisCheckpointer

**决策**：使用 PostgresSaver，复用现有 PG 实例。

**理由**：已在第 6 节详述。核心是运维单一化和事务一致性。

### ADR-003：interrupt() 为什么只放在 CEO node

**决策**：当前阶段只在 CEO node 设置 interrupt，Manager node 暂不设置。

**理由**：
- interrupt 会阻塞整个 thread，多个 interrupt 点会使 graph 状态机变复杂
- CEO 是唯一需要 Board 主动审批的节点（对应 NEXUS "分权"设计：Board 批准大方向，不干预执行细节）
- Manager node 的暂停逻辑可以通过超时重试机制替代，而非 interrupt

### ADR-004：Worker 并发方案

**决策**：使用 LangGraph Send API，在 `route_workers()` 中返回 `list[Send]`。

**理由**：
- AgentOffice 的 `activate.py` 注释已明确"当前同步/顺序执行，计划未来用 asyncio.gather 并行"
- Send API 是 LangGraph 官方的 fan-out 机制，比手动 asyncio.gather 更安全（State 合并有框架保证）
- 每个 Worker 子任务是独立的，天然适合 fan-out 模式

### ADR-005：escalation 逻辑去哪了

**决策**：`EscalationManager` 的 Intern → Director → CEO 升级链迁移为 `route_after_qa` 中的条件路由。

**理由**：
- escalation 的本质是"条件路由 + 状态变更"，与 graph 条件边的语义完全吻合
- `qa_retry_count` 在 State 中显式记录，比原来在 `EscalationResult` 对象中更可观测
- `escalation_chain` 字段记录历史，用于 DELIVER node 的 Board 报告

---

## 10. 风险与注意事项

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| LangGraph 版本更新破坏 API | 中 | 高 | 在 `pyproject.toml` 中 pin 版本，升级前跑完整回归测试 |
| PostgresSaver 写入延迟影响实时性 | 低 | 中 | node 内部操作完成立即 yield，checkpoint 写入在 background |
| Send API 并发 Worker 状态合并错误 | 低 | 高 | 对 `Annotated[list, operator.add]` 字段写专项测试 |
| interrupt() 后 Board 长时间不回复 | 中 | 中 | 设置超时（如 24h），超时后自动走 `reject` 路径 |
| 现有代码与 graph 双重写入 PG | 中 | 中 | Phase L4 切换前保持 pipeline 路径关闭（feature flag） |
| agentoffice 同步递归调用栈溢出 | 已存在 | 中 | Phase L3 后 agentoffice 退出主流程，风险消除 |

---

*文档结束。Engineer 团队请参照本文档各节实施，有疑问通过 contract 向架构 Manager 提交澄清请求。*
