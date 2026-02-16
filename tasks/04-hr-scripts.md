# Task 04: HR 自动化脚本

## PROMPT（复制粘贴到新的 Claude Code 会话）

```
你是一个 DevOps 工程师，负责为 AgentOffice 多 Agent 系统编写 HR 自动化工具。

## 项目背景

AgentOffice 用"公司"隐喻组织多个 Claude Code 实例。HR Agent 负责"招聘"和"裁员"
——实际上就是创建和删除 Agent 工作区（Linux 用户 + 文件夹 + 配置文件）。

当 CEO 需要新部门或新员工时，发邮件给 HR，HR 用这些脚本执行。

## 已有基础

- agents/ 目录结构已存在（01 任务创建）
- agents/scripts/ 下已有 send_mail.sh 等核心脚本（02 任务创建）
- agents/templates/ 下已有角色模板 JD.md / TOOL.md（03 任务创建）

如果这些还不存在，自行创建必要的占位结构。

## 你的任务

在 agents/scripts/ 下编写以下 2 个 Bash 脚本：

### 1. create_agent.sh

用途：创建一个新的 Agent 工作区（HR 的核心工具）

```bash
用法: create_agent.sh <agent_id> <role> <department> <reports_to> [options]
```

参数：
- agent_id: Agent 唯一标识（如 dept-gateway-dev-01）
- role: 角色类型（ceo | hr | it-support | manager | worker | qa）
- department: 所属部门（如 dept-gateway、dept-storage、hr、executive）
- reports_to: 直属上级的 agent_id

可选参数：
- --model <model>: 使用的 LLM 模型（默认 worker/qa 用 sonnet，manager 用 opus）
- --workspace: 是否创建 WORKSPACE/ 目录（worker 默认创建，其他角色不创建）

行为：

1. 验证参数完整性
2. 检查 agent_id 是否已存在（已存在则报错）
3. 创建 Linux 系统用户（用户名 = agent-{agent_id}）
   - 如果没有 sudo 权限，跳过用户创建，只创建目录结构，并输出警告
4. 创建目录结构：
   ```
   agents/{agent_id}/
   ├── JD.md          # 从 templates/{role}/JD.md 复制，替换占位符
   ├── TOOL.md        # 从 templates/{role}/TOOL.md 复制，替换占位符
   ├── MEMORY.md      # 空的，只有 # Memory
   ├── INBOX/         # 邮件接收目录
   │   └── read/      # 已读邮件
   └── WORKSPACE/     # 仅 worker 和 qa 角色创建
   ```
5. 替换模板中的占位符：
   - {agent_id} → 实际 agent_id
   - {role} → 实际角色
   - {department} → 实际部门
   - {reports_to} → 直属上级
   - {model} → LLM 模型
   - {created_date} → 创建日期
6. 设置文件权限（如果有 sudo）：
   - 工作区目录: chmod 700, chown agent-{agent_id}
   - INBOX/: chmod 733
   - JD.md, TOOL.md: chmod 444
   - MEMORY.md: chmod 600
   - WORKSPACE/: chmod 700
7. 更新组织登记表 agents/registry.yaml：
   ```yaml
   agents:
     {agent_id}:
       role: {role}
       department: {department}
       reports_to: {reports_to}
       model: {model}
       created: {date}
       status: active
   ```
8. 输出创建确认信息

### 2. delete_agent.sh

用途：删除一个 Agent（HR 的裁员工具）

```bash
用法: delete_agent.sh <agent_id> [--force]
```

行为：

1. 检查 agent_id 是否存在
2. 检查是否有下属（如果是 manager，需要先处理下属）
   - 如果有下属且没有 --force，报错并列出下属列表
   - 有 --force 则忽略此检查
3. 备份工作区到 agents/archived/{agent_id}_{timestamp}/
4. 删除工作区目录
5. 删除 Linux 用户（如果有 sudo）
6. 从 registry.yaml 中标记为 status: archived（不要删除记录）
7. 输出确认信息

### 附加：registry.yaml 管理

脚本需要管理 agents/registry.yaml 文件（组织登记表）。如果文件不存在则自动创建。

初始结构：
```yaml
# AgentOffice 组织登记表
# 由 create_agent.sh 和 delete_agent.sh 自动维护

agents: {}

departments: {}
```

create_agent.sh 还需要维护 departments 部分：
```yaml
departments:
  dept-gateway:
    name: 网关部门
    manager: dept-gateway-manager
    members:
      - dept-gateway-dev-01
      - dept-gateway-qa
```

## 通用要求

- #!/usr/bin/env bash + set -euo pipefail
- --help 参数
- 完整的参数校验
- AGENTS_ROOT 从环境变量 AGENTOFFICE_ROOT 读取
- 操作前确认提示（delete 操作，除非 --force）
- 所有输出带时间戳前缀
- 模板文件不存在时给出清晰提示（不要 crash）

## 约束

- 只在 agents/scripts/ 下创建脚本文件
- 可以创建 agents/registry.yaml
- 可以创建 agents/archived/ 目录
- 不要修改 agentoffice/ 或 company/ 下的文件
- 纯 Bash + 基础 Linux 命令（sed, grep, mkdir, chmod, chown）
- YAML 操作用简单的 sed/grep/echo（不要依赖 yq 或 python）

## 验收标准

- [ ] create_agent.sh 能创建完整的 Agent 工作区
- [ ] create_agent.sh 能从模板复制并替换占位符
- [ ] create_agent.sh 在 agent 已存在时报错
- [ ] create_agent.sh 没有 sudo 时降级运行（跳过用户创建和权限设置）
- [ ] delete_agent.sh 能备份并删除 Agent 工作区
- [ ] delete_agent.sh 在有下属时警告（除非 --force）
- [ ] registry.yaml 在创建/删除后正确更新
- [ ] 两个脚本都有 --help 输出和参数校验
```

---

## CONTRACT

```
ID: CTR-20260216-004
FROM: ceo
TO: devops-worker-01
STATUS: pending
CREATED: 2026-02-16
PRIORITY: high

任务目标: 编写 create_agent.sh 和 delete_agent.sh，实现 Agent 工作区的自动创建和删除
依赖: 01（目录结构）, 02（send_mail 等脚本）, 03（角色模板）
被依赖: 07, 08
预估上下文: 中型任务，单个 Worker 可完成
```
