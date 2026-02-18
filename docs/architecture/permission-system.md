# NEXUS AI-Team 权限矩阵与通信系统设计

**版本**: 1.0  
**日期**: 2026-02-19  
**作者**: 组织与安全 Manager  
**状态**: 待 CEO 审批  
**合同编号**: CEO-002

---

## 0. 背景与设计原则

### 0.1 问题陈述

架构评审（2026-02-19）明确指出当前系统的三个致命缺陷：

1. **权限边界只是装饰** — `chain-of-command.yaml` 只被用于构建上下文视图，不参与任何授权检查。`create_contract()` 接受任意 `from_agent` 和 `to_agent` 字符串，无校验。
2. **通信系统割裂** — DESIGN.md 的 INBOX 邮件系统与 agentoffice 的 contract pipeline 完全独立，互不连接。
3. **安全靠提示词** — worker 可以构造 `choice_payload.to = "board"` 绕过整个 chain of command，唯一的防线是 LLM 听话。

本设计的目标是：**把 chain of command 从"建议遵守"变成"系统级强制"。**

### 0.2 核心设计原则

| 原则 | 含义 | 实现方式 |
|------|------|----------|
| **Tool Binding 即权限** | agent 看不到的工具等于不存在 | LangGraph `bind_tools()` 在 agent 创建时锁定工具列表 |
| **通信路由即防火墙** | 邮件/合同只能发给 allowed_contacts 列表中的人 | `send_mail` 和 `create_contract` 工具内置收件人白名单校验 |
| **文件作用域即隔离** | agent 的文件操作被限定在声明的目录范围内 | 工具层面的路径前缀校验 + Linux 用户权限双重保障 |
| **显式禁止优先于隐式允许** | 每个角色有明确的 deny list | 工具绑定时排除禁止工具，运行时二次校验 |

### 0.3 强制机制层级

```
┌─────────────────────────────────────────┐
│  Layer 4: LLM System Prompt（最弱）     │  ← 当前唯一的"安全"措施
│  "请不要越权"                            │
├─────────────────────────────────────────┤
│  Layer 3: Tool Parameter Validation      │  ← 工具内置参数校验
│  send_mail 校验 to 是否在白名单          │
├─────────────────────────────────────────┤
│  Layer 2: LangGraph Tool Binding         │  ← agent 创建时绑定工具子集
│  CEO 只绑定 4 个工具，看不到其他的       │
├─────────────────────────────────────────┤
│  Layer 1: OS-Level Isolation（最强）     │  ← Linux 用户 + 文件系统权限
│  chmod 700 + sudo -u agent-name          │
└─────────────────────────────────────────┘
```

**本设计覆盖 Layer 1-3。Layer 4 作为辅助但不依赖它。**

---

## 1. 权限矩阵

### 1.1 角色总览

| 角色 | 层级 | 类型 | 汇报对象 | 工具数量 |
|------|------|------|----------|----------|
| CEO | L1 | 执行层 | Board（人类用户） | 4 |
| IT Manager | L2 | 管理层 | CEO | 12 |
| HR Manager | L2 | 管理层 | CEO | 10 |
| Product Manager | L2 | 管理层 | CEO | 9 |
| Backend Worker | L3 | 执行层 | IT Manager | 10 |
| Frontend Worker | L3 | 执行层 | IT Manager / Product Manager | 9 |
| DevOps Worker | L3 | 执行层 | IT Manager | 11 |
| QA Worker | L3 | 执行层 | IT Manager | 8 |
| Research Worker | L3 | 执行层 | Product Manager | 6 |

### 1.2 CEO

**身份**: 最高 AI 权力节点。只做决策和调度，绝不碰代码。

| 维度 | 定义 |
|------|------|
| **可用工具** | `generate_contract`, `send_mail`, `write_note`, `read_reports` |
| **可通信对象** | `it_manager`, `hr_manager`, `product_manager`（仅限 managers） |
| **可访问文件** | `company/contracts/`, `reports/`, `company/org.yaml`（只读）, 自身 `agents/ceo/` |
| **显式禁止** | 读写代码文件、直接联系任何 worker、执行 shell 命令、修改 org 配置、访问 `.env` 或凭证文件 |

**工具详细定义**:

```
generate_contract:
  description: 生成并发送合同给指定 manager
  parameters:
    to: string  # 必须是 allowed_contacts 中的值
    title: string
    body: string
    priority: enum[low, medium, high, critical]
    deadline: datetime
  validation:
    - to MUST be in caller.allowed_contacts
    - to MUST be a manager-level role (level == 2)

send_mail:
  description: 发送邮件给 chain of command 中的联系人
  parameters:
    to: string  # 必须是 allowed_contacts 中的值
    type: enum[info, approval_request, escalation]
    subject: string
    body: string
    priority: enum[low, medium, high, critical]
    attachments: list[filepath]  # 可选，文件必须在 file_scope 内
  validation:
    - to MUST be in caller.allowed_contacts
    - attachments 路径 MUST 在 caller.file_scope 内

write_note:
  description: 写入 CEO 个人笔记/决策记录
  parameters:
    title: string
    content: string
  storage: agents/ceo/notes/{timestamp}-{title_slug}.md

read_reports:
  description: 读取各部门提交的报告
  parameters:
    department: string  # 可选，筛选部门
    date_range: string  # 可选
    report_type: enum[status, completion, escalation, cost]
  scope: reports/ 目录（只读）
```

### 1.3 IT Manager

**身份**: 技术部门总管。管理所有技术类 worker，负责系统架构、工具管理、技术决策。

| 维度 | 定义 |
|------|------|
| **可用工具** | `send_mail`, `create_contract`, `read_reports`, `read_code`（只读）, `review_pr`, `manage_tools`, `assign_task`, `write_note`, `read_tech_reports`, `approve_deployment`, `request_budget`, `escalate` |
| **可通信对象** | `ceo`, `backend_worker`, `frontend_worker`, `devops_worker`, `qa_worker`, `hr_manager`（跨部门请求人员时）, `product_manager`（技术评审时） |
| **可访问文件** | 所有 `reports/tech/`、`company/contracts/`（本部门的）、`equipment/`、所有技术 worker 的 `WORKSPACE/`（只读）、`agents/it_manager/` |
| **显式禁止** | 直接写代码、直接修改生产环境、绕过 QA 合并代码、修改 org.yaml、访问 HR 人事档案 |

### 1.4 HR Manager

**身份**: 人事部门总管。管理组织结构、agent 创建/删除、JD 维护。

| 维度 | 定义 |
|------|------|
| **可用工具** | `send_mail`, `create_contract`, `create_agent_jd`, `update_agent_jd`, `deactivate_agent`, `update_org_chart`, `read_reports`, `write_note`, `list_agents`, `escalate` |
| **可通信对象** | `ceo`, `it_manager`（请求工具配置时）, `product_manager`（确认人员需求时） |
| **可访问文件** | `company/agents/`（读写 JD）、`company/org.yaml`（读写）、`company/chain-of-command.yaml`（读写）、`company/departments/`、`reports/hr/`、`agents/hr_manager/` |
| **显式禁止** | 读写代码文件、访问技术报告详情、直接联系任何 worker、修改 equipment 配置、执行部署操作 |

**关键约束**: HR Manager 是唯一可以修改 `org.yaml` 和 `chain-of-command.yaml` 的角色。这确保了组织结构变更的单一入口。但所有 org 变更必须有 CEO 的合同作为授权依据。

### 1.5 Product Manager

**身份**: 产品部门总管。管理需求、PRD、产品 backlog。

| 维度 | 定义 |
|------|------|
| **可用工具** | `send_mail`, `create_contract`, `write_prd`, `manage_backlog`, `read_reports`, `write_note`, `read_user_feedback`, `prioritize_tasks`, `escalate` |
| **可通信对象** | `ceo`, `research_worker`, `frontend_worker`（UI 需求确认时）, `it_manager`（技术可行性评估时）, `hr_manager`（请求人员时） |
| **可访问文件** | `company/contracts/`（本部门的）、`reports/product/`、`backlog/`、`docs/prd/`、`agents/product_manager/` |
| **显式禁止** | 读写代码文件、修改 org 配置、执行技术操作、直接联系 backend/devops/qa worker |

### 1.6 Backend Worker

**身份**: 后端开发工程师。只在分配的任务分支内写代码。

| 维度 | 定义 |
|------|------|
| **可用工具** | `send_mail`, `read_file`, `write_file`, `run_test`, `git_commit`, `git_push`, `git_branch`, `read_contract`, `submit_report`, `escalate` |
| **可通信对象** | `it_manager`（仅此一人） |
| **可访问文件** | 自身 `agents/backend_worker/`、任务指定的代码目录（由合同 `workspace_scope` 字段限定）、`tests/` 目录 |
| **显式禁止** | 联系 CEO 或其他部门、合并到 main/master 分支、修改 CI/CD 配置、访问 `.env`/凭证文件、修改其他 worker 的文件、读取 org 配置 |

**分支隔离**: Backend Worker 的 git 操作被限制在合同指定的 feature branch 上。`git_push` 工具会校验当前分支名是否匹配合同中的 `assigned_branch` 字段。向 `main`/`master`/`production` 推送会被工具层面拒绝。

### 1.7 Frontend Worker

**身份**: 前端开发工程师。只在分配的 UI 任务分支内工作。

| 维度 | 定义 |
|------|------|
| **可用工具** | `send_mail`, `read_file`, `write_file`, `run_test`, `git_commit`, `git_push`, `git_branch`, `read_contract`, `submit_report` |
| **可通信对象** | `it_manager`（主管）, `product_manager`（UI 需求确认，仅当合同明确授权时） |
| **可访问文件** | 自身 `agents/frontend_worker/`、任务指定的前端代码目录、`tests/frontend/`、`docs/prd/`（只读，用于理解需求） |
| **显式禁止** | 联系 CEO、修改后端代码、合并到主分支、访问数据库配置、修改其他 worker 的文件 |

### 1.8 DevOps Worker

**身份**: 运维工程师。管理部署、容器、CI/CD。

| 维度 | 定义 |
|------|------|
| **可用工具** | `send_mail`, `read_file`, `write_file`, `docker_build`, `docker_deploy`, `manage_ci_config`, `run_health_check`, `read_logs`, `read_contract`, `submit_report`, `escalate` |
| **可通信对象** | `it_manager`（仅此一人） |
| **可访问文件** | 自身 `agents/devops_worker/`、`docker/`、`docker-compose.yml`、`.github/workflows/`（CI/CD）、`logs/`（只读）、`equipment/`（只读） |
| **显式禁止** | 联系 CEO 或其他部门、修改应用代码（非 infra 代码）、直接访问生产数据库、修改 org 配置、未经 IT Manager 审批部署到生产环境 |

**部署安全**: `docker_deploy` 工具在目标为 `production` 环境时，必须验证存在 IT Manager 签发的 `deployment_approval` 类型合同。没有审批合同的生产部署会被工具层面拒绝。

### 1.9 QA Worker

**身份**: 质量保证工程师。只读代码，只写审查报告。

| 维度 | 定义 |
|------|------|
| **可用工具** | `send_mail`, `read_file`（只读）, `run_test`, `run_linter`, `write_verdict`, `read_contract`, `submit_report`, `escalate` |
| **可通信对象** | `it_manager`（仅此一人） |
| **可访问文件** | 自身 `agents/qa_worker/`、合同指定的代码目录（只读）、`tests/`（可读写测试文件）、`reports/qa/` |
| **显式禁止** | 写任何非测试/非报告文件、联系 CEO 或其他部门、修改源代码、合并或关闭 PR、修改 CI/CD 配置 |

**QA 独立性**: QA Worker 的 `write_file` 工具被限制为只能写入 `tests/` 和 `reports/qa/` 目录。这确保了 QA 无法修改被审查的源代码，保持审查的独立性。

### 1.10 Research Worker

**身份**: 研究员。搜索信息、阅读文档、撰写研究报告。没有任何代码工具。

| 维度 | 定义 |
|------|------|
| **可用工具** | `send_mail`, `web_search`, `read_url`, `write_report`, `read_contract`, `submit_report` |
| **可通信对象** | `product_manager`（仅此一人） |
| **可访问文件** | 自身 `agents/research_worker/`、`reports/research/`、`docs/`（只读） |
| **显式禁止** | 读写代码文件、执行 shell 命令、访问 git、联系技术部门的任何人、访问内部系统配置 |

---

## 2. 权限矩阵汇总表

### 2.1 工具绑定矩阵

| 工具 | CEO | IT Mgr | HR Mgr | PM | Backend | Frontend | DevOps | QA | Research |
|------|-----|--------|--------|----|---------|----------|--------|----|----------|
| generate_contract | **Y** | - | - | - | - | - | - | - | - |
| create_contract | - | **Y** | **Y** | **Y** | - | - | - | - | - |
| send_mail | **Y** | **Y** | **Y** | **Y** | **Y** | **Y** | **Y** | **Y** | **Y** |
| write_note | **Y** | **Y** | **Y** | **Y** | - | - | - | - | - |
| read_reports | **Y** | **Y** | **Y** | **Y** | - | - | - | - | - |
| read_tech_reports | - | **Y** | - | - | - | - | - | - | - |
| read_code | - | **Y**(RO) | - | - | - | - | - | - | - |
| review_pr | - | **Y** | - | - | - | - | - | - | - |
| manage_tools | - | **Y** | - | - | - | - | - | - | - |
| assign_task | - | **Y** | - | - | - | - | - | - | - |
| approve_deployment | - | **Y** | - | - | - | - | - | - | - |
| request_budget | - | **Y** | - | - | - | - | - | - | - |
| create_agent_jd | - | - | **Y** | - | - | - | - | - | - |
| update_agent_jd | - | - | **Y** | - | - | - | - | - | - |
| deactivate_agent | - | - | **Y** | - | - | - | - | - | - |
| update_org_chart | - | - | **Y** | - | - | - | - | - | - |
| list_agents | - | - | **Y** | - | - | - | - | - | - |
| write_prd | - | - | - | **Y** | - | - | - | - | - |
| manage_backlog | - | - | - | **Y** | - | - | - | - | - |
| read_user_feedback | - | - | - | **Y** | - | - | - | - | - |
| prioritize_tasks | - | - | - | **Y** | - | - | - | - | - |
| read_file | - | - | - | - | **Y** | **Y** | **Y** | **Y**(RO) | - |
| write_file | - | - | - | - | **Y** | **Y** | **Y** | **Y*** | - |
| run_test | - | - | - | - | **Y** | **Y** | - | **Y** | - |
| git_commit | - | - | - | - | **Y** | **Y** | - | - | - |
| git_push | - | - | - | - | **Y** | **Y** | - | - | - |
| git_branch | - | - | - | - | **Y** | **Y** | - | - | - |
| docker_build | - | - | - | - | - | - | **Y** | - | - |
| docker_deploy | - | - | - | - | - | - | **Y** | - | - |
| manage_ci_config | - | - | - | - | - | - | **Y** | - | - |
| run_health_check | - | - | - | - | - | - | **Y** | - | - |
| read_logs | - | - | - | - | - | - | **Y** | - | - |
| run_linter | - | - | - | - | - | - | - | **Y** | - |
| write_verdict | - | - | - | - | - | - | - | **Y** | - |
| web_search | - | - | - | - | - | - | - | - | **Y** |
| read_url | - | - | - | - | - | - | - | - | **Y** |
| write_report | - | - | - | - | - | - | - | - | **Y** |
| read_contract | - | - | - | - | **Y** | **Y** | **Y** | **Y** | **Y** |
| submit_report | - | - | - | - | **Y** | **Y** | **Y** | **Y** | **Y** |
| escalate | - | **Y** | **Y** | **Y** | **Y** | - | **Y** | **Y** | - |

> `*` QA 的 write_file 仅限 `tests/` 和 `reports/qa/` 目录  
> `RO` = Read Only

### 2.2 通信矩阵

| 发送者 → 接收者 | CEO | IT Mgr | HR Mgr | PM | Backend | Frontend | DevOps | QA | Research |
|------------------|-----|--------|--------|----|---------|----------|--------|----|----------|
| **CEO** | - | **Y** | **Y** | **Y** | **X** | **X** | **X** | **X** | **X** |
| **IT Manager** | **Y** | - | **Y*** | **Y*** | **Y** | **Y** | **Y** | **Y** | **X** |
| **HR Manager** | **Y** | **Y*** | - | **Y*** | **X** | **X** | **X** | **X** | **X** |
| **Product Mgr** | **Y** | **Y*** | **Y*** | - | **X** | **Y*** | **X** | **X** | **Y** |
| **Backend** | **X** | **Y** | **X** | **X** | - | **X** | **X** | **X** | **X** |
| **Frontend** | **X** | **Y** | **X** | **Y*** | **X** | - | **X** | **X** | **X** |
| **DevOps** | **X** | **Y** | **X** | **X** | **X** | **X** | - | **X** | **X** |
| **QA** | **X** | **Y** | **X** | **X** | **X** | **X** | **X** | - | **X** |
| **Research** | **X** | **X** | **X** | **Y** | **X** | **X** | **X** | **X** | - |

> **Y** = 始终允许  
> **Y*** = 有条件允许（跨部门协作需要合同授权，或限定特定邮件类型）  
> **X** = 系统级拦截，不可通信

**跨部门有条件通信规则**:

- IT Manager <-> HR Manager: 仅限 `tool_request` 和 `staffing_request` 类型邮件
- IT Manager <-> Product Manager: 仅限 `tech_review` 和 `feasibility_request` 类型邮件
- HR Manager <-> Product Manager: 仅限 `staffing_request` 类型邮件
- Product Manager -> Frontend Worker: 仅限 `requirement_clarification` 类型，且必须有活跃合同关联
- Frontend Worker -> Product Manager: 仅限 `question` 类型，且必须有活跃合同关联

---

## 3. 邮件/通信系统

### 3.1 邮件格式

所有 agent 间通信统一使用结构化邮件。邮件是系统中唯一的 agent 间通信机制。

```yaml
mail:
  id: "MAIL-{timestamp}-{random_4}"     # 系统自动生成，不可伪造
  from: string                            # 系统自动填充为当前 agent ID，不可覆盖
  to: string                              # 必须在发送者的 allowed_contacts 中
  type: enum                              # 见 3.2 邮件类型
  subject: string                         # 最大 200 字符
  body: string                            # 最大 10000 字符
  priority: enum[low, medium, high, critical]
  attachments:                            # 可选
    - path: string                        # 必须在发送者的 file_scope 内
      description: string
  reply_to: string | null                 # 关联的原始邮件 ID
  contract_ref: string | null             # 关联的合同 ID
  created_at: datetime                    # 系统自动填充
  read_at: datetime | null                # 接收者读取时自动填充
  status: enum[sent, delivered, read, failed, rejected]
```

**关键安全设计**:

1. `from` 字段由系统根据调用者身份自动填充，agent 无法伪造发送者
2. `to` 字段在 `send_mail` 工具内部校验，必须在 `allowed_contacts` 白名单中
3. `attachments.path` 必须在发送者的 `file_scope` 范围内，防止泄露无权访问的文件
4. `id` 由系统生成，包含时间戳和随机数，不可被 agent 预测或伪造

### 3.2 邮件类型

| 类型 | 说明 | 允许的发送者 | 典型场景 |
|------|------|-------------|----------|
| `contract` | 正式工作合同 | CEO, Managers | CEO 下达任务给 Manager，Manager 分配任务给 Worker |
| `report` | 工作报告/汇报 | 全部角色 | Worker 完成任务后向 Manager 汇报 |
| `approval_request` | 请求审批 | Managers, Workers | DevOps 请求 IT Manager 审批部署 |
| `info` | 信息通知 | 全部角色 | 非正式的信息传递 |
| `escalation` | 问题升级 | Managers, Workers | Worker 遇到无法解决的问题，升级到 Manager |
| `question` | 需求确认/疑问 | Workers | Frontend Worker 向 Product Manager 确认 UI 需求 |
| `verdict` | QA 审查结论 | QA Worker | QA 提交 PASS/FAIL 审查结果 |
| `staffing_request` | 人员请求 | Managers | IT Manager 向 HR Manager 请求新增 Worker |
| `tool_request` | 工具请求 | Managers | HR Manager 向 IT Manager 请求配置工具 |
| `tech_review` | 技术评审 | IT Manager | IT Manager 向 Product Manager 反馈技术可行性 |
| `requirement_clarification` | 需求澄清 | Product Manager | PM 向 Frontend Worker 发送需求细节 |
| `deployment_approval` | 部署审批 | IT Manager | IT Manager 审批通过 DevOps 的部署请求 |

### 3.3 路由规则

邮件路由在 `send_mail` 工具的实现层面强制执行。以下是伪代码逻辑：

```python
def send_mail(caller_agent_id: str, mail: Mail) -> Result:
    # 1. 强制覆盖 from 字段（防伪造）
    mail.from_ = caller_agent_id

    # 2. 查询发送者的角色定义
    sender_role = load_role(caller_agent_id)

    # 3. 校验收件人是否在允许列表中
    if mail.to not in sender_role.allowed_contacts:
        return Rejected(
            reason=f"Communication denied: {caller_agent_id} is not authorized "
                   f"to contact {mail.to}. Allowed contacts: {sender_role.allowed_contacts}"
        )

    # 4. 校验邮件类型是否被允许
    contact_rule = sender_role.contact_rules.get(mail.to)
    if contact_rule and contact_rule.allowed_types:
        if mail.type not in contact_rule.allowed_types:
            return Rejected(
                reason=f"Mail type '{mail.type}' not allowed for "
                       f"{caller_agent_id} -> {mail.to}. "
                       f"Allowed types: {contact_rule.allowed_types}"
            )

    # 5. 校验附件路径
    for attachment in mail.attachments:
        if not is_within_scope(attachment.path, sender_role.file_scope):
            return Rejected(
                reason=f"Attachment path '{attachment.path}' is outside "
                       f"sender's file scope"
            )

    # 6. 生成邮件 ID 和时间戳
    mail.id = generate_mail_id()
    mail.created_at = now()
    mail.status = "sent"

    # 7. 投递到接收者的邮箱
    deliver_to_inbox(mail.to, mail)
    mail.status = "delivered"

    return Success(mail_id=mail.id)
```

### 3.4 跨部门通信协议

跨部门协作是通过各自 Manager 中继完成的，不允许 Worker 直接跨部门通信。

**标准流程**:

```
Backend Worker 需要 Frontend Worker 配合
         │
         ▼
Backend Worker ──[report]──> IT Manager
         "需要前端配合实现 API 对接"
         │
         ▼
IT Manager ──[info]──> Product Manager
         "后端 API 就绪，需要前端对接"
         │
         ▼
Product Manager ──[requirement_clarification]──> Frontend Worker
         "请对接后端 API，详见附件"
         │
         ▼
Frontend Worker ──[report]──> Product Manager / IT Manager
         "前端对接完成"
```

**唯一例外**: Frontend Worker 可以在有活跃合同的前提下直接与 Product Manager 通信（限 `question` 类型）。这是因为 UI 开发中频繁的需求确认如果每次都经过两层 Manager 中继，效率太低。但这个直通通道的前提是必须存在 IT Manager 或 Product Manager 签发的包含跨部门授权的合同。

### 3.5 存储设计

邮件使用 PostgreSQL 存储，表结构如下：

```sql
CREATE TABLE mails (
    id          VARCHAR(32) PRIMARY KEY,    -- MAIL-{timestamp}-{random}
    from_agent  VARCHAR(64) NOT NULL,
    to_agent    VARCHAR(64) NOT NULL,
    mail_type   VARCHAR(32) NOT NULL,
    subject     VARCHAR(200) NOT NULL,
    body        TEXT NOT NULL,
    priority    VARCHAR(8) NOT NULL DEFAULT 'medium',
    attachments JSONB DEFAULT '[]',
    reply_to    VARCHAR(32) REFERENCES mails(id),
    contract_ref VARCHAR(32),
    status      VARCHAR(16) NOT NULL DEFAULT 'sent',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at TIMESTAMPTZ,
    read_at     TIMESTAMPTZ,

    -- 审计字段
    rejected_reason TEXT,  -- 如果被拦截，记录原因
    route_log   JSONB      -- 路由过程日志（用于审计）
);

-- 索引
CREATE INDEX idx_mails_to_agent ON mails(to_agent, status);
CREATE INDEX idx_mails_from_agent ON mails(from_agent);
CREATE INDEX idx_mails_contract_ref ON mails(contract_ref);
CREATE INDEX idx_mails_created_at ON mails(created_at);

-- 拦截日志（所有被拒绝的通信尝试都记录在这里）
CREATE TABLE mail_rejections (
    id          SERIAL PRIMARY KEY,
    from_agent  VARCHAR(64) NOT NULL,
    to_agent    VARCHAR(64) NOT NULL,
    mail_type   VARCHAR(32),
    reason      TEXT NOT NULL,
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_rejections_from ON mail_rejections(from_agent);
CREATE INDEX idx_rejections_at ON mail_rejections(attempted_at);
```

**为什么用 PostgreSQL 而不是文件系统**:

1. **事务安全**: 邮件投递是原子操作，不会出现"写了一半"的邮件
2. **查询效率**: 按部门、时间、类型筛选邮件远比遍历文件系统高效
3. **审计追踪**: 所有拒绝的通信尝试都被记录，可以审计是否有 agent 试图越权
4. **并发安全**: 多个 agent 同时收发邮件不会出现文件锁冲突
5. **与现有架构一致**: 项目已经有 `nexus.db`（SQLite），迁移到 PostgreSQL 是自然的升级路径

---

## 4. Chain of Command 执行规则

### 4.1 层级定义

```
Level 0: Board（人类用户）
    │
Level 1: CEO（AI）
    │
    ├── Level 2: IT Manager
    │       ├── Level 3: Backend Worker
    │       ├── Level 3: Frontend Worker
    │       ├── Level 3: DevOps Worker
    │       └── Level 3: QA Worker
    │
    ├── Level 2: HR Manager
    │       └── (动态创建的 HR Worker)
    │
    └── Level 2: Product Manager
            ├── Level 3: Research Worker
            └── Level 3: Frontend Worker（共管）
```

### 4.2 通信规则（系统级强制）

| 规则编号 | 规则 | 强制方式 |
|----------|------|----------|
| C-01 | CEO 只能联系 Level 2 Manager | `send_mail` 工具白名单 |
| C-02 | Manager 只能联系自己部门的 Worker + CEO + 有条件的跨部门 Manager | `send_mail` 工具白名单 + 邮件类型校验 |
| C-03 | Worker 只能联系自己的直属 Manager | `send_mail` 工具白名单 |
| C-04 | Worker 之间不可直接通信 | `allowed_contacts` 不包含任何其他 worker |
| C-05 | 跨部门通信必须通过 Manager 中继 | Worker 的 `allowed_contacts` 不包含其他部门的任何人 |
| C-06 | 违规通信被拦截并记录到 `mail_rejections` | `send_mail` 路由校验失败时写入审计表 |
| C-07 | 合同只能沿 chain of command 向下传递 | `create_contract` 校验 sender.level < receiver.level 或 sender 是 receiver 的直属上级 |

### 4.3 合同流转规则

```
Board（人类）
  │  口头/手动指令
  ▼
CEO
  │  generate_contract（只能发给 managers）
  ▼
Manager
  │  create_contract（只能发给自己部门的 workers）
  ▼
Worker
  │  submit_report（只能发给自己的 manager）
  ▼
Manager
  │  send_mail(type=report)（向 CEO 汇报）
  ▼
CEO
  │  send_mail(type=report)（向 Board 汇报）
  ▼
Board
```

**合同不可反向流动**: Worker 不能创建合同（没有 `create_contract` 工具）。Manager 不能创建合同发给 CEO（`create_contract` 校验 level 关系）。CEO 不能创建合同发给 Board（Board 是人类用户，不在 agent 系统中）。

### 4.4 升级（Escalation）协议

当 Worker 遇到无法解决的问题时：

```
Worker ──[escalation]──> Manager
    │
    ▼
Manager 判断：
    ├── 可自行解决 → 回复 Worker 指导
    ├── 需要跨部门 → 联系对应 Manager
    └── 超出权限 → ──[escalation]──> CEO
                          │
                          ▼
                     CEO 判断：
                          ├── 分派给其他 Manager
                          └── 升级到 Board（人类介入）
```

**Escalation 必须逐级上报**: Worker 的 `escalate` 工具只能发给直属 Manager。Manager 的 `escalate` 工具只能发给 CEO。CEO 的升级通过 `write_note` 记录，由 Board（人类）定期检查或通过外部通知机制。

### 4.5 异常处理

| 场景 | 处理方式 |
|------|----------|
| 目标 agent 不存在 | 邮件被拒绝，写入 `mail_rejections`，返回错误给发送者 |
| 目标 agent 已停用 | 邮件被拒绝，自动通知发送者的上级 |
| Manager 无响应 | Worker 在超时后可再次发送 escalation，系统在 3 次无响应后自动通知 CEO |
| CEO 无响应 | 系统在超时后通知 Board（外部通知渠道：邮件/webhook） |
| 违规通信尝试 | 拦截、记录到审计表、通知被拦截者"你没有权限联系此人" |
| Worker 试图伪造 from 字段 | 系统自动覆盖为真实调用者 ID，伪造行为被静默忽略 |

---

## 5. 实施路径

### Phase 1: YAML 规范落地（本文档）
- [x] 定义 `roles.yaml` — 每个角色的工具、通信、文件作用域
- [x] 定义 `mail-protocol.yaml` — 邮件格式、类型、路由规则
- [x] 本文档作为设计规范

### Phase 2: LangGraph Tool Binding 实现
- [ ] 为每个工具实现参数校验逻辑（`send_mail` 白名单校验等）
- [ ] 在 agent 创建时根据 `roles.yaml` 进行 `bind_tools()`
- [ ] 实现 `from` 字段自动填充（防伪造）

### Phase 3: 数据库层
- [ ] 创建 PostgreSQL `mails` 和 `mail_rejections` 表
- [ ] 实现邮件投递和查询 API
- [ ] 实现审计日志查询

### Phase 4: 测试与审计
- [ ] 模拟越权通信场景，验证拦截有效
- [ ] 模拟合同反向流动，验证拒绝有效
- [ ] 审计日志覆盖率检查

---

## 6. 与现有系统的兼容性说明

### 6.1 org.yaml 与 chain-of-command.yaml

架构评审指出这两个文件存在 ID 不一致问题（`hr_lead` vs `hr.manager`）。本设计统一使用以下命名规范：

| 旧 ID（org.yaml） | 旧 ID（chain-of-command.yaml） | 新统一 ID |
|-------------------|-------------------------------|-----------|
| hr_lead | hr.manager | hr_manager |
| it_admin | it.manager | it_manager |
| eng_manager | - | it_manager（合并） |
| pm | - | product_manager |
| qa_lead | - | qa_worker（降级为 worker，QA 不需要独立部门 manager） |
| frontend_dev | - | frontend_worker |
| backend_dev | - | backend_worker |
| devops | - | devops_worker |
| recruiter | - | （按需由 HR Manager 创建） |
| sec_analyst | - | （按需由 IT Manager 创建） |
| designer | - | （按需由 Product Manager 创建） |
| exec_assistant | - | （按需由 CEO 创建） |

### 6.2 两套通信系统的统一

本设计将 DESIGN.md 的 INBOX 邮件概念与 agentoffice 的 contract pipeline 统一为一个系统：

- **邮件** = 所有 agent 间通信的载体（存储在 PostgreSQL）
- **合同** = 特殊类型的邮件（`type: contract`），带有额外的状态机（pending → in_progress → review → passed/failed）
- 不再有独立的 `company/contracts/pending/` 文件目录，合同作为邮件的子类型统一管理

---

*文档结束。待 CEO 审批后进入 Phase 2 实施。*
