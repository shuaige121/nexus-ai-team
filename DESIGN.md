# AgentOffice — 多 Agent 协作系统设计方案

一句话概述：用文件系统 + Linux 权限 + 邮件机制，把多个 Claude Code 实例组织成一家"公司"，每个 Agent 只能在自己的工作区内操作，通过结构化邮件协作，彻底解决上下文爆炸和角色越权问题。

## 要解决的问题

目前用 AI 做稍微复杂的项目，都会碰到三个致命问题：

- **上下文爆炸**：代码一多，AI 的上下文窗口被塞满，开始忘记指令、跑偏、偷懒
- **角色混乱**：让 AI 当架构师，它写着写着就自己改代码去了，CEO 干了程序员的活
- **没有验收**：AI 自己写自己检查，等于没检查

核心洞察：问题不是 AI 不够聪明，而是给它看了太多不该看的东西。

## 设计理念

### 信息最小化原则
每个 Agent 只知道它该知道的，多一个字都不给。CEO 看不到代码，Worker 看不到其他模块，QA 改不了源码。不是靠提示词"请求"它不要越界，而是物理上就没有能力越界。

### 上下文预算管理
一个项目可能需要 200K tokens 的上下文才能完成。如果塞给一个 Claude，它会爆掉、跑偏、偷懒。但如果拆成 10 个 Worker，每个人只需要 20K tokens，每个人的上下文都在舒适区内。

### 公司隐喻
直接用人人都懂的公司组织结构：CEO、经理、工程师、HR、QA。每个角色的职责和边界天然清晰。

## 工作区结构

每个 Agent 拥有一个独立文件夹，就是它的全部世界：

```
/agents/
├── ceo/
│   ├── JD.md
│   ├── TOOL.md
│   ├── MEMORY.md
│   └── INBOX/
├── hr/
│   ├── JD.md
│   ├── TOOL.md
│   ├── MEMORY.md
│   └── INBOX/
├── it-support/
│   ├── JD.md
│   ├── TOOL.md
│   ├── MEMORY.md
│   └── INBOX/
├── dept-gateway/
│   ├── manager/
│   │   ├── JD.md / TOOL.md / MEMORY.md / INBOX/
│   ├── dev-01/
│   │   ├── JD.md / TOOL.md / MEMORY.md / INBOX/ / WORKSPACE/
│   ├── dev-02/
│   │   └── ...
│   └── qa/
│       ├── JD.md / TOOL.md / MEMORY.md / INBOX/
```

### 工作区文件说明

| 文件 | 权限 | 用途 |
|------|------|------|
| JD.md | 只读 | 定义身份、角色、职责边界、汇报关系 |
| TOOL.md | 只读 | 可用工具和命令，由 IT Support 维护 |
| MEMORY.md | 读写 | 持久记忆，有字数上限（2000-4000字） |
| INBOX/ | 外部可写入 | 接收邮件（contract、报告、请求等） |
| WORKSPACE/ | 读写 | 实际工作文件，只有需要干活的角色才有 |

### 隔离机制

- 每个 Agent 对应一个 Linux 系统用户
- 每个用户只有自己文件夹的读写权限（chmod 700）
- INBOX 设为 733（别人可写入，不能读）
- JD.md 和 TOOL.md 设为 444（所有人只读）
- 以对应用户身份启动：`sudo -u agent-name claude --workdir /agents/agent-name`

## 邮件系统

Agent 之间唯一的通信方式。格式：

```markdown
# MAIL
FROM: ceo
TO: dept-gateway-manager
TYPE: contract
PRIORITY: high
---
## 任务：...
### 需求 / 验收标准 / 截止时间
```

邮件类型：contract / report / request / hire / fire / review / result / tool_request / tool_installed

## Contract 标准格式

```markdown
# CONTRACT
ID: CTR-20250216-001
FROM: ceo
TO: dept-gateway-manager
STATUS: pending | in_progress | review | passed | failed | cancelled
CREATED: 2025-02-16
DEADLINE: 2025-02-17
---
## 项目背景 / 任务目标 / 具体要求 / 不要做的事 / 输入 / 输出 / 验收标准 / 上下文预算
```

## 角色定义

- **CEO**: 只管方向，不碰代码。发contract给经理和HR。需要了解代码时发request，经理安排人总结。
- **HR**: 创建和删除Agent工作区。工具：create_agent.sh / delete_agent.sh
- **IT Support**: 管工具和环境。可修改任意Agent的TOOL.md。工具：install_tool.sh / remove_tool.sh / search_tool.sh
- **部门经理**: 估算上下文预算、拆分任务、分配Worker、安排QA验收、合并结果。不自己写代码。
- **Worker**: 只看分配的文件，按contract干活，完成后发report。
- **QA**: 只读权限，对照验收标准检查，输出通过/不通过。

## 核心脚本

- create_agent.sh / delete_agent.sh（HR）
- install_tool.sh / remove_tool.sh / search_tool.sh（IT Support）
- send_mail.sh / check_inbox.sh（所有人）
- write_memory.sh（所有人）
- start_agent.sh（启动Agent）

依赖：Linux + Claude Code CLI + Bash，无其他依赖。

## 落地路径

1. **阶段一：手动验证**（1-2天）— 3个文件夹，tmux模拟3个Agent，跑通最小任务
2. **阶段二：脚本化**（2-3天）— 核心bash脚本 + Linux用户隔离
3. **阶段三：跑真实项目**（1周）— 实战检验，迭代优化
4. **阶段四：开源发布** — GitHub + README + 介绍文章
