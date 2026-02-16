# Task 07: 多进程 Agent 启动器

## PROMPT（复制粘贴到新的 Claude Code 会话）

```
你是一个系统工程师，负责为 AgentOffice 多 Agent 系统实现多进程启动和编排机制。

## 项目背景

AgentOffice 用文件系统组织多个 Claude Code 实例。每个 Agent 是一个独立的 Claude
Code 进程，运行在自己的工作区目录中，以对应的 Linux 用户身份执行。

当前系统是单进程递归调用的原型。这个任务是把它变成真正的多进程系统：
每个 Agent 是独立进程，通过 INBOX 文件通信，互不干扰。

## 核心设计

```
                        ┌──────────────────┐
                        │   orchestrator   │  ← 你要写的主控脚本
                        │  （不是 Agent）    │
                        └──────┬───────────┘
                               │ 启动/监控/日志
              ┌────────────────┼────────────────┐
              │                │                │
        ┌─────┴──────┐  ┌─────┴──────┐  ┌─────┴──────┐
        │  CEO 进程   │  │ Manager 进程│  │ Worker 进程 │
        │ claude      │  │ claude      │  │ claude      │
        │ --workdir   │  │ --workdir   │  │ --workdir   │
        │ agents/ceo/ │  │ agents/mgr/ │  │ agents/w01/ │
        └─────────────┘  └─────────────┘  └─────────────┘
              │                │                │
              └───── INBOX 文件通信 ──────────────┘
```

Orchestrator 不是 Agent，它是进程管理器。它：
- 启动 Agent 进程
- 监控 Agent 进程状态
- 收集日志
- 检测 INBOX 变化并唤醒对应 Agent

## 你的任务

在 agents/scripts/ 下编写以下脚本：

### 1. start_agent.sh

用途：启动单个 Agent 的 Claude Code 进程

```bash
用法: start_agent.sh <agent_id> [options]
```

可选参数：
- --model <model>: 覆盖默认模型
- --background: 后台运行
- --log <file>: 日志输出到指定文件

行为：

1. 读取 agents/registry.yaml 获取 Agent 配置（role, model 等）
2. 确认 Agent 工作区存在（JD.md, TOOL.md, MEMORY.md, INBOX/）
3. 构建 Claude Code 启动命令：
   ```bash
   claude \
     --workdir "agents/{agent_id}" \
     --model "{model}" \
     --system-prompt "$(cat agents/{agent_id}/JD.md)" \
     --allowedTools "$(cat agents/{agent_id}/TOOL.md | extract_tools)" \
     --appendSystemPrompt "检查你的INBOX，阅读最新邮件，按照JD.md的工作流程执行。"
   ```
   注意：claude CLI 的实际参数以当前版本为准，上面只是示意。
   关键是：
   - 工作目录指向 Agent 自己的文件夹
   - 系统提示词从 JD.md 加载
   - 可用工具从 TOOL.md 派生
4. 如果有 sudo 权限且 Linux 用户存在，以对应用户身份启动：
   ```bash
   sudo -u agent-{agent_id} claude ...
   ```
5. 记录 PID 到 agents/{agent_id}/.pid
6. 如果 --background，用 nohup 后台运行，日志写到 agents/{agent_id}/agent.log
7. 输出进程信息

### 2. stop_agent.sh

用途：停止单个 Agent 进程

```bash
用法: stop_agent.sh <agent_id> [--force]
```

行为：

1. 读取 agents/{agent_id}/.pid
2. 发送 SIGTERM（优雅停止）
3. 等待 10 秒，如果还没退出且 --force，发 SIGKILL
4. 清理 .pid 文件
5. 输出确认信息

### 3. orchestrator.sh

用途：主编排脚本，管理所有 Agent 的生命周期

```bash
用法: orchestrator.sh <command> [options]
```

命令：

- `start` — 启动所有 active Agent
  1. 读取 registry.yaml
  2. 按优先级启动：CEO → Managers → Workers/QA
  3. 每个 Agent 用 start_agent.sh --background 启动
  4. 等待所有 Agent 启动完成

- `stop` — 停止所有 Agent
  1. 按反序停止：Workers/QA → Managers → CEO
  2. 优雅关闭

- `status` — 显示所有 Agent 状态
  ```
  AGENT ID              ROLE      PID     STATUS    INBOX
  ceo                   ceo       12345   running   2 unread
  dept-gw-manager       manager   12346   running   0 unread
  dept-gw-dev-01        worker    12347   running   1 unread
  dept-gw-qa            qa        -       stopped   0 unread
  ```

- `restart <agent_id>` — 重启单个 Agent

- `logs <agent_id>` — 查看 Agent 日志（tail -f）

- `dispatch <agent_id>` — 唤醒指定 Agent 处理 INBOX
  - 如果 Agent 没在运行，启动它
  - 如果 Agent 在运行，发送信号或写 trigger 文件

### 4. inbox_watcher.sh（可选，加分项）

用途：监控所有 Agent 的 INBOX，有新邮件时自动唤醒对应 Agent

```bash
用法: inbox_watcher.sh [--interval <seconds>]
```

行为：
- 每隔 N 秒（默认 5）扫描所有 Agent 的 INBOX/
- 检测到新 .md 文件时，调用 orchestrator.sh dispatch {agent_id}
- 用 inotifywait（如果可用）替代轮询
- 后台运行

## 重要设计决策

### Agent 运行模式

Agent 不是常驻进程。它的生命周期是：
1. 被唤醒（收到邮件/被 dispatch）
2. 读取 INBOX 中最新邮件
3. 按 JD.md 的工作流程处理
4. 输出结果（发邮件、写文件等）
5. 等待或退出

这意味着 start_agent.sh 启动的进程可能会自然退出。orchestrator 需要处理这种情况：
Agent 退出不是错误，而是它完成了当前工作。下次有新邮件时再启动它。

### 日志收集

每个 Agent 的 stdout/stderr 重定向到 agents/{agent_id}/agent.log。
orchestrator logs 命令可以查看实时日志。

### 进程隔离

即使没有 Linux 用户隔离，进程隔离也能防止上下文交叉污染：
- 每个 Claude Code 进程只看到自己的 workdir
- 系统提示词（JD.md）限制了行为边界
- 可用工具（TOOL.md）限制了能力边界

## 约束

- 只在 agents/scripts/ 下创建脚本
- 纯 Bash
- 不依赖 Docker 或 Kubernetes
- claude CLI 命令用变量表示（CLAUDE_CMD=${CLAUDE_CMD:-claude}），方便测试时 mock
- 不要修改 agentoffice/ 或 company/ 下的文件

## 验收标准

- [ ] start_agent.sh 能启动单个 Agent 进程并记录 PID
- [ ] start_agent.sh --background 能后台运行并输出日志
- [ ] stop_agent.sh 能优雅停止 Agent
- [ ] orchestrator.sh start 能按序启动所有 Agent
- [ ] orchestrator.sh stop 能按序停止所有 Agent
- [ ] orchestrator.sh status 能显示所有 Agent 状态和 INBOX 情况
- [ ] orchestrator.sh dispatch 能唤醒指定 Agent
- [ ] 所有脚本有 --help 和参数校验
- [ ] Agent 自然退出时 orchestrator 不报错
```

---

## CONTRACT

```
ID: CTR-20260216-007
FROM: ceo
TO: systems-worker-01
STATUS: pending
CREATED: 2026-02-16
PRIORITY: high

任务目标: 实现多进程 Agent 启动器（start/stop/orchestrator）
依赖: 01（目录结构）, 02（核心脚本）, 04（create_agent / registry.yaml）
被依赖: 08
预估上下文: 大型任务，建议拆分但单 Worker 可尝试
```
