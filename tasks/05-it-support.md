# Task 05: IT Support 角色与工具管理

## PROMPT（复制粘贴到新的 Claude Code 会话）

```
你是一个 DevOps 工程师，负责为 AgentOffice 多 Agent 系统实现 IT Support 角色的工具管理功能。

## 项目背景

AgentOffice 用"公司"隐喻组织多个 Claude Code 实例。IT Support 是一个职能角色，
负责管理所有 Agent 的工具环境。

Worker 说"我需要一个 JSON 校验工具"，IT Support 去找合适的工具、安装到 Worker
的工作区、更新 Worker 的 TOOL.md。TOOL.md 是每个 Agent 的"可用工具清单"，
Agent 只被允许使用 TOOL.md 里列出的工具。

## 核心理念

每个 Agent 的 TOOL.md 就是它的工具白名单。IT Support 是唯一有权修改其他 Agent
TOOL.md 的角色。这实现了工具级别的隔离——Worker A 有 pytest 但没有 curl，
Worker B 有 curl 但没有 pytest。

## 你的任务

在 agents/scripts/ 下编写以下 3 个 Bash 脚本：

### 1. install_tool.sh

用途：为指定 Agent 安装工具并更新其 TOOL.md

```bash
用法: install_tool.sh <target_agent_id> <tool_name> [options]
```

参数：
- target_agent_id: 目标 Agent
- tool_name: 工具名称或包名

可选参数：
- --type <type>: 安装方式（apt | pip | npm | binary | script | github）
- --source <url>: 安装来源（GitHub URL 或下载地址）
- --description <desc>: 工具用途描述（写入 TOOL.md）
- --usage <usage>: 使用示例（写入 TOOL.md）
- --dry-run: 只显示将执行的操作，不实际执行

行为：

1. 验证目标 Agent 存在
2. 检查工具是否已在目标的 TOOL.md 中
3. 根据 --type 执行安装：
   - apt: sudo apt-get install -y {tool_name}
   - pip: pip install {tool_name} （安装到 Agent 的虚拟环境，如果有）
   - npm: npm install -g {tool_name}
   - binary: 下载二进制到 agents/{target}/bin/
   - script: 复制脚本到 agents/{target}/bin/
   - github: git clone {source} 到 agents/{target}/tools/{tool_name}/
   - 如果没指定 --type，尝试自动检测（apt search → pip search → 报错）
4. 更新目标 Agent 的 TOOL.md，在适当的分类下添加：
   ```markdown
   - `{tool_name}` — {description}
     - 用法: `{usage}`
     - 安装方式: {type}
     - 安装日期: {date}
   ```
5. 记录安装日志到 agents/it-support/install_log.md

### 2. remove_tool.sh

用途：从指定 Agent 卸载工具并更新其 TOOL.md

```bash
用法: remove_tool.sh <target_agent_id> <tool_name> [--force]
```

行为：

1. 验证目标 Agent 存在
2. 检查工具是否在目标的 TOOL.md 中（不在则报错）
3. 读取安装日志确定安装方式
4. 执行卸载
5. 从 TOOL.md 中移除对应条目
6. 记录到卸载日志

### 3. search_tool.sh

用途：搜索可安装的工具（供 IT Support 查找合适工具时使用）

```bash
用法: search_tool.sh <keyword> [--type <apt|pip|npm|github>]
```

行为：

1. 根据 --type 在对应包管理器中搜索：
   - apt: apt-cache search {keyword}
   - pip: pip search {keyword}（或 pip index versions）
   - npm: npm search {keyword}
   - github: 使用 gh search repos 或 curl GitHub API
   - 不指定 type 则搜索所有
2. 输出格式化的搜索结果：
   ```
   [apt] tool-name — 描述
   [pip] tool-name — 描述
   [github] user/repo — 描述 (⭐ stars)
   ```
3. 最多输出 10 条结果

### 附加：TOOL.md 格式规范

IT Support 更新 TOOL.md 时必须遵循以下格式：

```markdown
# 可用工具

> 最后更新: {date} by IT Support

## 通信工具
- `send_mail.sh <from> <to> <type> <subject>` — 发送邮件
- `check_inbox.sh <agent_id>` — 检查收件箱
- `read_mail.sh <agent_id> <filename>` — 读取邮件
- `write_memory.sh <agent_id> <action>` — 写入记忆

## 编程工具
- `python3` — Python 解释器
  - 用法: `python3 script.py`
  - 安装方式: apt
  - 安装日期: 2026-02-16

## 测试工具
- `pytest` — Python 测试框架
  - 用法: `pytest tests/`
  - 安装方式: pip
  - 安装日期: 2026-02-16

## 禁止使用的命令
以下命令不在白名单中，禁止使用：
- 不要使用未列出的命令
- 如需新工具，请发 tool_request 邮件给 IT Support
```

分类包括：通信工具、文件工具、编程工具、测试工具、构建工具、其他工具、禁止使用的命令。

## 约束

- 只在 agents/scripts/ 下创建脚本文件
- 可以创建 agents/it-support/install_log.md
- 不要修改 agentoffice/ 或 company/ 下的文件
- 纯 Bash
- search_tool.sh 中 GitHub 搜索需要 gh CLI（如果不可用则跳过 GitHub 搜索）
- 安装操作如果没有 sudo 权限，给出清晰提示

## 验收标准

- [ ] install_tool.sh 能安装工具并更新目标 TOOL.md
- [ ] install_tool.sh --dry-run 只显示不执行
- [ ] install_tool.sh 检查工具是否已安装
- [ ] remove_tool.sh 能卸载工具并更新 TOOL.md
- [ ] search_tool.sh 能在至少一个包管理器中搜索
- [ ] TOOL.md 更新后格式正确、分类正确
- [ ] 安装日志被记录
- [ ] 所有脚本有 --help 和参数校验
```

---

## CONTRACT

```
ID: CTR-20260216-005
FROM: ceo
TO: devops-worker-02
STATUS: pending
CREATED: 2026-02-16
PRIORITY: medium

任务目标: 实现 IT Support 的 3 个工具管理脚本
依赖: 01（目录结构）, 02（核心脚本）, 03（TOOL.md 模板）
被依赖: 08
预估上下文: 中型任务，单个 Worker 可完成
```
