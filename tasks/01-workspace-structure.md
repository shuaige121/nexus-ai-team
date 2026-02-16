# Task 01: Agent 工作区目录结构

## PROMPT（复制粘贴到新的 Claude Code 会话）

```
你是一个 DevOps 工程师，负责为 AgentOffice 多 Agent 系统搭建基础目录结构。

## 项目背景

AgentOffice 是一个用文件系统组织多个 Claude Code 实例的系统。每个 Agent（CEO、HR、
部门经理、工程师、QA、IT Support）拥有独立的工作文件夹，这是它的全部世界。

## 你的任务

在项目根目录创建 `agents/` 目录结构，这是所有 Agent 工作区的根。

### 目标结构

```
agents/
├── scripts/              # 所有共享脚本（后续任务会填充）
│   └── .gitkeep
├── templates/            # JD/TOOL 模板（后续任务会填充）
│   └── .gitkeep
├── ceo/
│   ├── JD.md             # 只读，定义角色身份和职责
│   ├── TOOL.md           # 只读，列出可用工具
│   ├── MEMORY.md         # 读写，持久记忆（有字数上限）
│   └── INBOX/            # 接收邮件的目录
│       └── .gitkeep
├── hr/
│   ├── JD.md
│   ├── TOOL.md
│   ├── MEMORY.md
│   └── INBOX/
│       └── .gitkeep
└── it-support/
    ├── JD.md
    ├── TOOL.md
    ├── MEMORY.md
    └── INBOX/
        └── .gitkeep
```

注意：部门目录（dept-xxx/）和 Worker 目录不在这里创建，由 HR 的 create_agent.sh
在运行时动态创建。这里只创建固定存在的 3 个角色（CEO、HR、IT Support）。

### 初始文件内容

JD.md —— 先写一行占位：`# [角色名] — 待填充`（03-role-templates 任务会补全）
TOOL.md —— 先写一行占位：`# 可用工具 — 待填充`
MEMORY.md —— 空文件，只写一行：`# Memory`

### 权限设计说明

在目录结构的 README 中说明设计意图（实际权限由后续任务设置）：
- 每个 Agent 的工作区：chmod 700（只有自己能读写）
- INBOX/：chmod 733（别人可以写入文件，但不能读取已有文件）
- JD.md、TOOL.md：chmod 444（所有人只读）
- Worker 的 WORKSPACE/：chmod 700（只有自己能读写）

### 额外产出

创建 `agents/README.md`，说明：
1. 这个目录是什么（Agent 工作区根目录）
2. 目录结构约定（固定角色 vs 动态创建的角色）
3. 权限设计说明
4. 与旧的 company/agents/ 的关系（那是 Python 原型的数据目录，这是新的真实工作区）

## 约束

- 不要创建任何 Python 代码
- 不要修改 agentoffice/ 或 company/ 下的任何文件
- 不要安装任何依赖
- 所有文件放在 agents/ 目录下
- JD.md 和 TOOL.md 只写占位内容，不要写完整模板（那是 03 的任务）

## 验收标准

- [ ] agents/ 目录存在且结构正确
- [ ] ceo/、hr/、it-support/ 三个工作区都有 JD.md、TOOL.md、MEMORY.md、INBOX/
- [ ] scripts/ 和 templates/ 目录存在
- [ ] agents/README.md 存在且内容完整
- [ ] 没有修改 agentoffice/ 或 company/ 下的任何文件
```

---

## CONTRACT

```
ID: CTR-20260216-001
FROM: ceo
TO: infra-worker-01
STATUS: pending
CREATED: 2026-02-16
PRIORITY: high

任务目标: 创建 agents/ 目录结构，作为所有 Agent 工作区的根
依赖: 无
被依赖: 02, 04, 05, 06, 07, 08
预估上下文: 小型任务，单个 Worker 可完成
```
