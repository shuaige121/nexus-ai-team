# Task 02: 核心通信脚本

## PROMPT（复制粘贴到新的 Claude Code 会话）

```
你是一个 Shell 脚本开发工程师，负责为 AgentOffice 多 Agent 系统编写核心通信脚本。

## 项目背景

AgentOffice 用文件系统组织多个 Claude Code 实例。Agent 之间通过往彼此的 INBOX/
目录写 .md 文件来通信（类似内部邮件）。每个 Agent 有一个 MEMORY.md 文件作为
持久记忆，有严格字数上限。

## 目录结构（已由 01 任务创建）

```
agents/
├── scripts/          # ← 你的脚本放这里
├── ceo/
│   ├── MEMORY.md
│   └── INBOX/
├── hr/
│   ├── MEMORY.md
│   └── INBOX/
└── it-support/
    ├── MEMORY.md
    └── INBOX/
```

如果 agents/ 目录还不存在，自行创建必要的结构。

## 你的任务

在 agents/scripts/ 下编写以下 4 个 Bash 脚本：

### 1. send_mail.sh

用途：Agent 向另一个 Agent 发送邮件（往目标的 INBOX/ 写文件）

```bash
用法: send_mail.sh <from> <to> <type> <subject> [priority]
```

参数：
- from: 发件人 agent ID（如 ceo、hr、dept-gateway-manager）
- to: 收件人 agent ID
- type: 邮件类型（contract | report | request | hire | fire | review |
  result | tool_request | tool_installed）
- subject: 邮件主题（用于文件名，不含空格，用连字符连接）
- priority: 可选，high | medium | low，默认 medium

行为：
- 从 stdin 读取邮件正文
- 生成文件名格式：`{timestamp}_{from}_{type}_{subject}.md`
- 文件内容格式：

```markdown
# MAIL
FROM: {from}
TO: {to}
TYPE: {type}
PRIORITY: {priority}
TIMESTAMP: {ISO 8601 时间}
---

{正文内容}
```

- 写入到 `agents/{to}/INBOX/` 目录
- 如果目标 INBOX 不存在，报错退出（不要自动创建，说明目标 Agent 不存在）
- 输出确认信息到 stdout

### 2. check_inbox.sh

用途：列出当前 Agent 的 INBOX 中的邮件

```bash
用法: check_inbox.sh <agent_id> [--unread | --all | --type <type>]
```

行为：
- 默认列出所有邮件（按时间倒序）
- --unread：只列出未读邮件（未读 = INBOX/ 下的文件，已读 = INBOX/read/ 下的）
- --type <type>：只列出指定类型的邮件
- 输出格式：每行一封邮件，显示时间、发件人、类型、主题
- 如果 INBOX 为空，输出"无邮件"

### 3. read_mail.sh

用途：读取一封邮件的完整内容，并标记为已读

```bash
用法: read_mail.sh <agent_id> <mail_filename> [--peek]
```

行为：
- 显示邮件完整内容到 stdout
- 默认将邮件从 INBOX/ 移动到 INBOX/read/（标记已读）
- --peek：只看不标记已读
- 如果文件不存在，报错

### 4. write_memory.sh

用途：写入或追加内容到 Agent 的 MEMORY.md

```bash
用法: write_memory.sh <agent_id> <action> [content]
```

参数：
- agent_id: Agent ID
- action: append | replace | clear
- content: 要写入的内容（从 stdin 读取）

行为：
- append：在末尾追加内容
- replace：替换整个文件内容
- clear：清空文件（只保留 `# Memory` 标题）
- **关键**：写入前检查字数限制（MEMORY_CHAR_LIMIT=4000 字符）
- 如果写入后会超过限制：
  - 拒绝写入
  - 输出当前字数和剩余空间
  - 提示 Agent "请先清理旧内容再写入"
- 写入成功后输出当前字数/上限

## 通用要求

- 所有脚本第一行: `#!/usr/bin/env bash`
- 所有脚本 set -euo pipefail
- 所有脚本有 --help 参数，打印用法说明
- 参数校验：缺少必填参数时报错并打印 usage
- AGENTS_ROOT 变量从环境变量 `AGENTOFFICE_ROOT` 读取，默认为脚本所在目录的上级
- 所有脚本可执行（chmod +x）
- 纯 Bash，不依赖 Python 或其他语言
- 支持中文内容（邮件正文可以是中文）

## 约束

- 只在 agents/scripts/ 下创建文件
- 不要修改 agentoffice/ 或 company/ 下的任何文件
- 不要创建 Python 代码
- 不要安装任何依赖

## 验收标准

- [ ] send_mail.sh 能成功发送邮件到目标 INBOX
- [ ] send_mail.sh 在目标不存在时正确报错
- [ ] check_inbox.sh 能列出邮件，支持 --unread 和 --type 过滤
- [ ] read_mail.sh 能读取邮件并移动到 read/ 子目录
- [ ] read_mail.sh --peek 不移动文件
- [ ] write_memory.sh 能追加、替换、清空 MEMORY.md
- [ ] write_memory.sh 在超过字数限制时拒绝写入并给出提示
- [ ] 所有脚本有 --help 输出
- [ ] 所有脚本有正确的参数校验
```

---

## CONTRACT

```
ID: CTR-20260216-002
FROM: ceo
TO: scripts-worker-01
STATUS: pending
CREATED: 2026-02-16
PRIORITY: high

任务目标: 编写 4 个核心 Bash 脚本（send_mail / check_inbox / read_mail / write_memory）
依赖: 01（目录结构，但可并行，脚本自行处理目录不存在的情况）
被依赖: 04, 05, 06, 07, 08
预估上下文: 中型任务，单个 Worker 可完成
```
