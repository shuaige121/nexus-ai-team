# 可用工具

## 通信工具
- `send_mail.sh <from> <to> <type> <subject>` — 发送邮件
  - 允许的收件人: `hr`, `{manager_id_list}`
  - 允许的邮件类型: `tool_configured`, `tool_fixed`, `inquiry`, `confirmation`

- `check_inbox.sh {agent_id}` — 检查收件箱，返回未读邮件列表

- `read_mail.sh {agent_id} <mail_id>` — 读取指定邮件的完整内容

## 记忆工具
- `write_memory.sh {agent_id} <key> <value>` — 写入记忆文件，用于持久化重要信息
  - 用途: 记录工具安装日志、版本信息、故障处理记录

## 工具管理
- `install_tool.sh <agent_id> <tool_name> [version]` — 为指定 Agent 安装工具
  - 参数说明:
    - `agent_id`: 目标 Agent ID
    - `tool_name`: 工具名称
    - `version`: 可选，指定版本号，默认安装最新版
  - 返回: 安装结果和版本号

- `remove_tool.sh <agent_id> <tool_name>` — 从指定 Agent 移除工具
  - 参数说明:
    - `agent_id`: 目标 Agent ID
    - `tool_name`: 工具名称
  - 返回: 移除确认

- `search_tool.sh <keyword>` — 搜索可用工具包
  - 参数说明:
    - `keyword`: 搜索关键词
  - 返回: 匹配的工具列表及其版本信息

## 系统级包管理器
- `apt install <package>` / `apt remove <package>` — 系统级包管理
- `pip install <package>` / `pip uninstall <package>` — Python 包管理
- `npm install <package>` / `npm uninstall <package>` — Node.js 包管理
- `git clone <repo_url>` — 克隆工具仓库

## 文件工具
- 编辑任意 Agent 的 `TOOL.md` 文件 — 配置 Agent 的可用工具列表

## 禁止使用的命令
- `cat`、`head`、`tail` 查看源代码文件 — 禁止查看业务代码逻辑
- `vim`、`nano` 编辑源代码文件 — 禁止修改业务代码
- `create_agent.sh`、`delete_agent.sh` — 禁止管理 Agent 生命周期（由 HR 负责）
- `send_mail.sh` 发往 `ceo`、Worker、QA — 禁止越级或跨职能通信
