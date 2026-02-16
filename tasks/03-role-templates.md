# Task 03: 角色 JD 与 TOOL 模板

## PROMPT（复制粘贴到新的 Claude Code 会话）

```
你是一个技术架构师，负责为 AgentOffice 多 Agent 系统编写所有角色的 JD.md 和 TOOL.md 模板。

## 项目背景

AgentOffice 用"公司"隐喻组织多个 Claude Code 实例。每个 Agent 启动时只看到自己
工作区里的文件，JD.md 定义它是谁、能做什么、不能做什么；TOOL.md 列出它能使用的工具。

核心原则：
- **信息最小化**：每个 Agent 只知道它该知道的，多一个字都不给
- **确定性操作不用 LLM**：能用脚本做的绝不用 LLM
- **选择题代替作文题**：Agent 的决策通过有限选项表达，不是自由发挥

## 你的任务

在 agents/templates/ 下创建所有角色的 JD.md 和 TOOL.md 模板文件。

### 需要创建的角色模板

#### 1. CEO（agents/templates/ceo/）

JD.md 要点：
- 身份：公司 CEO，最高决策者
- 汇报对象：董事会（用户）
- 直接下属：部门经理们、HR
- **能做**：分析项目需求、拆分模块、给经理发 contract、看经理汇报、做最终验收
- **不能做**：看代码、改代码、直接给 Worker 发消息、做技术决策
- **看到的信息**：项目概述、文件树（只有文件名没有内容）、各模块 contract 状态
- 如果需要了解某个文件的技术细节：发 request 邮件给经理，让经理安排人总结

TOOL.md 要点：
- send_mail.sh（只能发给经理和 HR，不能发给 Worker）
- check_inbox.sh
- read_mail.sh
- write_memory.sh
- 查看项目文件树的命令（ls -R，但不能 cat）

#### 2. HR（agents/templates/hr/）

JD.md 要点：
- 身份：人力资源总监
- 汇报对象：CEO
- **能做**：创建/删除 Agent、写 JD.md、管理组织结构
- **不能做**：看代码、参与技术讨论、给 Worker 分配任务
- 触发条件：收到 CEO 的 hire/fire 邮件

TOOL.md 要点：
- send_mail.sh
- check_inbox.sh / read_mail.sh
- write_memory.sh
- create_agent.sh（04 任务会实现）
- delete_agent.sh（04 任务会实现）

#### 3. IT Support（agents/templates/it-support/）

JD.md 要点：
- 身份：IT 运维工程师
- 汇报对象：CEO
- **能做**：安装/删除/搜索工具、修改任何 Agent 的 TOOL.md、管理系统环境
- **不能做**：看代码逻辑、参与业务讨论、修改 JD.md 或 MEMORY.md
- 触发条件：收到任何人的 tool_request 邮件

TOOL.md 要点：
- send_mail.sh
- check_inbox.sh / read_mail.sh
- write_memory.sh
- install_tool.sh（05 任务会实现）
- remove_tool.sh（05 任务会实现）
- search_tool.sh（05 任务会实现）
- 系统命令：apt, pip, npm, git clone 等

#### 4. 部门经理（agents/templates/manager/）

JD.md 要点：
- 身份：部门经理，负责本部门交付
- 汇报对象：CEO
- 直接下属：本部门的 Worker 和 QA
- **能做**：
  - 估算上下文预算（这是核心能力！）
  - 拆分子任务、写子 contract
  - 给 HR 发招聘请求
  - 查看本部门所有 Worker 的代码
  - 安排 QA 验收
  - 合并通过的工作
  - 向 CEO 汇报
- **不能做**：自己写代码、跨部门看代码、直接和其他部门的 Worker 通信
- 上下文预算估算指南：
  - 1 行代码 ≈ 5-10 tokens
  - 1 个中文字 ≈ 1-2 tokens
  - 每个 Worker 舒适上下文：不超过 20K tokens
  - 据此决定拆几个 Worker

TOOL.md 要点：
- send_mail.sh（能发给 CEO、本部门 Worker、本部门 QA、HR）
- check_inbox.sh / read_mail.sh
- write_memory.sh
- 查看本部门 Worker 的 WORKSPACE（只读）

#### 5. Worker / 工程师（agents/templates/worker/）

JD.md 要点：
- 身份：工程师，负责执行具体编码任务
- 汇报对象：部门经理
- **能做**：在 WORKSPACE/ 里写代码、跑测试、发完成报告给经理
- **不能做**：
  - 看 WORKSPACE 以外的任何文件
  - 跟经理以外的人通信
  - 自行决定做 contract 以外的事
  - 修改自己的 JD.md 或 TOOL.md
- 如果上下文不够了：停下来发邮件给经理说"任务比预期大，建议继续拆分"

TOOL.md 要点：
- send_mail.sh（只能发给自己的经理）
- check_inbox.sh / read_mail.sh
- write_memory.sh
- 编程相关工具（由 IT Support 根据需要配置）
- 测试工具

#### 6. QA（agents/templates/qa/）

JD.md 要点：
- 身份：质量检验员
- 汇报对象：部门经理
- **能做**：读代码、跑测试、对照 contract 验收标准检查、写验收报告
- **不能做**：改代码、写代码、跟 Worker 直接通信
- 输出格式：逐条对照验收标准，每条标注通过/不通过+原因

TOOL.md 要点：
- send_mail.sh（只能发给自己的经理）
- check_inbox.sh / read_mail.sh
- write_memory.sh
- 代码阅读工具（cat、grep、find 等，但没有写权限）
- 测试运行工具（只运行，不修改）

### JD.md 统一格式

每个 JD.md 遵循以下结构：

```markdown
# {角色名}

## 身份
一句话描述。

## 汇报关系
- 上级: {谁}
- 下属: {谁，没有就写"无"}

## 职责
- 职责 1
- 职责 2

## 权限边界
### 允许
- ...

### 禁止
- ...

## 工作流程
收到邮件后的标准处理流程，用编号步骤写清楚。

## 输出格式
你的所有输出必须是以下 JSON 格式：
（定义该角色的标准输出格式）
```

### TOOL.md 统一格式

```markdown
# 可用工具

## 通信工具
- `send_mail.sh <to> <type> <subject>` — 发送邮件
  - 允许的收件人: {列表}
  - 允许的邮件类型: {列表}

## 文件工具
- （按角色列出）

## 编程工具（仅 Worker/QA）
- （按角色列出）

## 禁止使用的命令
- （明确列出不允许用的命令）
```

## 约束

- 只在 agents/templates/ 下创建文件
- 每个角色一个子目录：ceo/、hr/、it-support/、manager/、worker/、qa/
- 不要修改 agentoffice/ 或 company/ 下的任何文件
- 不要写任何 Python 或 Bash 代码
- JD.md 用中文写
- TOOL.md 中脚本名用英文，说明用中文
- 模板中用 {占位符} 表示运行时替换的值

## 验收标准

- [ ] 6 个角色目录都存在，每个包含 JD.md 和 TOOL.md
- [ ] 每个 JD.md 都有身份、汇报关系、职责、权限边界、工作流程、输出格式
- [ ] 每个 TOOL.md 都有通信工具、文件工具、禁止命令
- [ ] CEO 的 JD 明确禁止看代码
- [ ] Worker 的 JD 明确禁止看 WORKSPACE 以外的文件
- [ ] QA 的 JD 明确禁止改代码
- [ ] Manager 的 JD 包含上下文预算估算指南
- [ ] 所有模板格式一致
```

---

## CONTRACT

```
ID: CTR-20260216-003
FROM: ceo
TO: architect-worker-01
STATUS: pending
CREATED: 2026-02-16
PRIORITY: high

任务目标: 编写 6 个角色的 JD.md 和 TOOL.md 模板
依赖: 无（独立任务）
被依赖: 05, 08
预估上下文: 中型任务，单个 Worker 可完成（大量文本编写）
```
