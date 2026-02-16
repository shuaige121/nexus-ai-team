# 可用工具

## 通信工具
- `send_mail.sh <from> <to> <type> <subject>` — 发送邮件
  - 允许的收件人: `ceo`, `hr`, `{department_worker_ids}`, `{department_qa_ids}`
  - 允许的邮件类型: `sub_contract`, `qa_request`, `completion_report`, `hire_request`, `fire_request`, `inquiry`, `status_update`, `rework_request`

- `check_inbox.sh dept-auth-manager` — 检查收件箱，返回未读邮件列表

- `read_mail.sh dept-auth-manager <mail_id>` — 读取指定邮件的完整内容

## 记忆工具
- `write_memory.sh dept-auth-manager <key> <value>` — 写入记忆文件，用于持久化重要信息
  - 用途: 记录 contract 详情、子任务分配、上下文预算估算、进度跟踪

## 文件工具（只读）
- `ls /home/user/nexus-ai-team/agents/dept-auth-manager/WORKSPACE` — 查看本部门 Worker 的 WORKSPACE 目录结构
  - 允许的路径: 仅限 `{department_workspace}/` 下的目录
- `cat {file_path}` — 查看本部门 Worker 的 WORKSPACE 中的文件内容（只读）
  - 允许的路径: 仅限 `{department_workspace}/` 下的文件
  - 用途: 审查交付物结构，不可修改

## 禁止使用的命令
- `vim`、`nano`、`sed`、`awk` — 禁止编辑任何文件
- `python`、`node`、`bash *.sh`（非授权脚本） — 禁止执行代码
- `git commit`、`git push` — 禁止直接操作版本控制
- `rm`、`mv`、`cp` — 禁止文件写操作
- `npm`、`pip`、`apt` — 禁止安装工具
- `cat`、`ls` 访问 `{department_workspace}/` 以外的路径 — 禁止跨部门查看
- `send_mail.sh` 发往其他部门 Worker/QA — 禁止跨部门通信
