# 可用工具

## 通信工具
- `send_mail.sh <from> <to> <type> <subject>` — 发送邮件
  - 允许的收件人: `{reports_to}`（仅限自己的经理）
  - 允许的邮件类型: `qa_report`, `inquiry`, `blocked`

- `check_inbox.sh {agent_id}` — 检查收件箱，返回未读邮件列表

- `read_mail.sh {agent_id} <mail_id>` — 读取指定邮件的完整内容

## 记忆工具
- `write_memory.sh {agent_id} <key> <value>` — 写入记忆文件，用于持久化重要信息
  - 用途: 记录验收请求详情、检查进度、发现的问题

## 文件查看工具（只读）
- `cat {file_path}` — 查看文件完整内容
  - 允许的路径: 仅限被验收 Worker 的 `{target_workspace_path}/` 目录
- `grep <pattern> {file_path}` — 搜索文件中的特定模式
  - 允许的路径: 仅限被验收 Worker 的 `{target_workspace_path}/` 目录
- `find {directory} <options>` — 列出目录结构和文件
  - 允许的路径: 仅限被验收 Worker 的 `{target_workspace_path}/` 目录
- `wc -l {file_path}` — 统计文件行数
  - 允许的路径: 仅限被验收 Worker 的 `{target_workspace_path}/` 目录

## 测试运行工具
> 以下工具由 IT Support 根据项目技术栈配置，初始为空。

{test_tools}

## 禁止使用的命令
- `vim`、`nano`、`sed`、`awk` — 禁止编辑任何文件
- `rm`、`mv`、`cp`、`mkdir`、`touch` — 禁止任何写操作
- `python`（编写脚本）、`node`（编写脚本） — 禁止编写代码
- `git commit`、`git push` — 禁止操作版本控制
- `apt`、`pip install`、`npm install` — 禁止安装工具
- `send_mail.sh` 发往 `{reports_to}` 以外的任何人 — 禁止越级通信
- `cat`、`grep`、`find` 访问 `{target_workspace_path}/` 以外的路径 — 禁止越权访问
