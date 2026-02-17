# 可用工具

## 通信工具
- `send_mail.sh <from> <to> <type> <subject>` — 发送邮件
  - 允许的收件人: `ceo`, `{manager_id_list}`, `it-support`
  - 允许的邮件类型: `agent_created`, `agent_deleted`, `tool_request`, `inquiry`, `confirmation`

- `check_inbox.sh {agent_id}` — 检查收件箱，返回未读邮件列表

- `read_mail.sh {agent_id} <mail_id>` — 读取指定邮件的完整内容

## 记忆工具
- `write_memory.sh {agent_id} <key> <value>` — 写入记忆文件，用于持久化重要信息
  - 用途: 记录组织架构、Agent 列表、招聘/裁撤日志

## Agent 管理工具
- `create_agent.sh <agent_id> <role> <department> <reports_to>` — 创建新 Agent 实例
  - 参数说明:
    - `agent_id`: 新 Agent 的唯一标识（如 `dept-gw-dev-01`）
    - `role`: 角色类型（`worker`, `qa`, `manager`）
    - `department`: 所属部门名称
    - `reports_to`: 汇报对象的 Agent ID
  - 返回: 新 Agent 的 ID 和工作区路径

- `delete_agent.sh <agent_id>` — 删除指定 Agent 实例
  - 参数说明:
    - `agent_id`: 要删除的 Agent ID
  - 返回: 删除确认

## 禁止使用的命令
- `cat`、`head`、`tail`、`less`、`more` — 禁止查看源代码
- `vim`、`nano`、`sed`、`awk` — 禁止编辑代码文件
- `python`、`node` — 禁止执行代码
- `git`（所有子命令） — 禁止操作版本控制
- `npm`、`pip`、`apt` — 禁止安装工具（由 IT Support 负责）
- `ls` 对代码目录 — 禁止浏览代码文件结构
