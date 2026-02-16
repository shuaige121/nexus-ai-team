# Task 06: Contract 标准格式与管理脚本

## PROMPT（复制粘贴到新的 Claude Code 会话）

```
你是一个 Shell 脚本开发工程师，负责为 AgentOffice 多 Agent 系统实现 Contract 管理机制。

## 项目背景

AgentOffice 用"公司"隐喻组织多个 Claude Code 实例。Contract 是整个系统的核心文件，
所有任务的下发、执行、验收都围绕它展开。

Contract 不通过邮件发送，而是作为独立 .md 文件存放在发起方和接收方的工作区中。
邮件只是通知"你有个新 contract"，contract 本身是独立文件。

## Contract 生命周期

```
下发 (pending) → 接受 (in_progress) → 完成/提交 → 验收 (review)
                                                    ↓         ↓
                                              通过 (passed)  不通过 (failed) → 重做
```

## 你的任务

### 1. Contract 模板文件

创建 agents/templates/contract.md：

```markdown
# CONTRACT
ID: {contract_id}
FROM: {from}
TO: {to}
STATUS: pending
CREATED: {created_date}
DEADLINE: {deadline}
PARENT: {parent_contract_id}

---

## 项目背景
{background}

## 任务目标
{objective}

## 具体要求
{requirements}

## 不要做的事
{restrictions}

## 输入
{input_description}

## 输出
{output_description}

## 验收标准
{acceptance_criteria}

## 上下文预算
{context_budget}
```

### 2. create_contract.sh

用途：创建一个新的 Contract 文件

```bash
用法: create_contract.sh <from> <to> [options]
```

参数：
- from: 发起方 agent_id
- to: 接收方 agent_id

可选参数：
- --parent <id>: 父 Contract ID（用于子任务拆分）
- --deadline <date>: 截止日期
- --priority <high|medium|low>: 优先级

行为：

1. 自动生成 Contract ID：CTR-{YYYYMMDD}-{序号}
   - 序号从 agents/contracts/counter 文件读取并自增
   - 如果有 --parent，ID 格式为 {parent_id}-{字母}（如 CTR-20260216-001-A）
2. 从 stdin 读取一个 JSON（或交互式提问）填充模板字段：
   ```json
   {
     "background": "...",
     "objective": "...",
     "requirements": ["要求1", "要求2"],
     "restrictions": ["不做1", "不做2"],
     "input": "...",
     "output": "...",
     "acceptance_criteria": ["标准1", "标准2"],
     "context_budget": "小型/中型/大型"
   }
   ```
3. 用模板生成 Contract .md 文件
4. 存放位置：
   - agents/contracts/{contract_id}.md（主存档）
   - 同时复制到 agents/{to}/INBOX/（通知接收方）
5. 输出 Contract ID 和文件路径

### 3. update_contract.sh

用途：更新 Contract 状态

```bash
用法: update_contract.sh <contract_id> <new_status> [--note <note>]
```

参数：
- contract_id: Contract ID
- new_status: pending | in_progress | review | passed | failed | cancelled

行为：

1. 找到 agents/contracts/{contract_id}.md
2. 更新 STATUS 字段
3. 在文件末尾追加状态变更记录：
   ```markdown
   ---
   ## 状态变更记录
   - {timestamp}: pending → in_progress （{note}）
   - {timestamp}: in_progress → review
   ```
4. 合法状态转换检查：
   - pending → in_progress | cancelled
   - in_progress → review | cancelled
   - review → passed | failed
   - failed → in_progress（重做）
   - 其他转换拒绝

### 4. list_contracts.sh

用途：列出 Contract 状态

```bash
用法: list_contracts.sh [options]
```

可选参数：
- --agent <id>: 只看某个 Agent 相关的 contract
- --status <status>: 按状态过滤
- --parent <id>: 列出某个 contract 的所有子 contract

行为：

1. 扫描 agents/contracts/ 目录
2. 解析每个 .md 文件的头部字段
3. 输出格式化表格：
   ```
   ID                    FROM    TO              STATUS       DEADLINE
   CTR-20260216-001      ceo     gateway-mgr     in_progress  2026-02-17
   CTR-20260216-001-A    gw-mgr  gw-dev-01       review       2026-02-16
   CTR-20260216-001-B    gw-mgr  gw-dev-02       passed       2026-02-16
   ```

### 目录结构

```
agents/
├── contracts/              # Contract 主存档
│   ├── counter             # 自增序号（纯数字文件）
│   ├── CTR-20260216-001.md
│   └── CTR-20260216-001-A.md
└── templates/
    └── contract.md         # Contract 模板
```

## 约束

- 只在 agents/scripts/ 下创建脚本
- 可以创建 agents/contracts/ 目录和 agents/templates/contract.md
- 不要修改 agentoffice/ 或 company/ 下的文件
- 纯 Bash，YAML/MD 解析用 sed/grep/awk
- Contract .md 文件必须是纯文本，不依赖任何特殊工具解析

## 验收标准

- [ ] Contract 模板文件存在且格式正确
- [ ] create_contract.sh 能生成带自增 ID 的 Contract
- [ ] create_contract.sh 支持子 Contract（--parent）
- [ ] create_contract.sh 同时写入存档和接收方 INBOX
- [ ] update_contract.sh 能更新状态，拒绝非法转换
- [ ] update_contract.sh 追加状态变更记录
- [ ] list_contracts.sh 能列出和过滤 Contract
- [ ] 所有脚本有 --help 和参数校验
```

---

## CONTRACT

```
ID: CTR-20260216-006
FROM: ceo
TO: scripts-worker-02
STATUS: pending
CREATED: 2026-02-16
PRIORITY: high

任务目标: 实现 Contract 模板 + 3 个管理脚本（create / update / list）
依赖: 01（目录结构）, 02（send_mail 用于通知）
被依赖: 07, 08
预估上下文: 中型任务，单个 Worker 可完成
```
