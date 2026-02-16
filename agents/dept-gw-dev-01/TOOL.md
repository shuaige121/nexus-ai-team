# 可用工具

## 通信工具
- `send_mail.sh <from> <to> <type> <subject>` — 发送邮件
  - 允许的收件人: `dept-gw-manager`（仅限自己的经理）
  - 允许的邮件类型: `task_completed`, `context_overflow`, `blocked`, `inquiry`

- `check_inbox.sh dept-gw-dev-01` — 检查收件箱，返回未读邮件列表

- `read_mail.sh dept-gw-dev-01 <mail_id>` — 读取指定邮件的完整内容

## 记忆工具
- `write_memory.sh dept-gw-dev-01 <key> <value>` — 写入记忆文件，用于持久化重要信息
  - 用途: 记录 sub-contract 详情、实现进度、技术决策

## 编程工具
> 以下工具由 IT Support 根据任务需求配置，初始为空。

{programming_tools}

## 文件工具
- 在 `/home/user/nexus-ai-team/agents/dept-gw-dev-01/WORKSPACE/` 下的所有标准文件操作（创建、编辑、删除）
  - 允许的路径: 仅限 `/home/user/nexus-ai-team/agents/dept-gw-dev-01/WORKSPACE/` 及其子目录

## 禁止使用的命令
- 访问 `/home/user/nexus-ai-team/agents/dept-gw-dev-01/WORKSPACE/` 以外的任何路径 — 禁止越权访问
- `send_mail.sh` 发往 `dept-gw-manager` 以外的任何人 — 禁止越级通信
- `git commit`、`git push`、`git checkout` — 禁止操作版本控制
- `apt`、`pip install`、`npm install` — 禁止自行安装工具
- `rm -rf /`、`chmod`、`chown` — 禁止危险系统操作
- `curl`、`wget` — 禁止网络访问（除非 IT Support 明确授权）
