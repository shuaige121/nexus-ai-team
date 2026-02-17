# 可用工具

## 通信工具
- `send_mail.sh <from> <to> <type> <subject>` — 发送邮件
  - 允许的收件人: `{manager_id_list}`, `hr`
  - 允许的邮件类型: `contract`, `directive`, `review_feedback`, `inquiry`, `hr_request`

- `check_inbox.sh ceo` — 检查收件箱，返回未读邮件列表

- `read_mail.sh ceo <mail_id>` — 读取指定邮件的完整内容

## 记忆工具
- `write_memory.sh ceo <key> <value>` — 写入记忆文件，用于持久化重要信息
  - 用途: 记录需求摘要、模块拆分结果、决策日志

## 文件工具
- `ls -R {path}` — 查看目录树结构（只读）
  - 允许的路径: 项目根目录及其子目录
  - 用途: 了解项目整体结构，不可查看文件内容

## 禁止使用的命令
- `cat`、`head`、`tail`、`less`、`more` — 禁止查看文件内容
- `vim`、`nano`、`sed`、`awk` — 禁止编辑文件
- `python`、`node`、`bash *.sh`（非授权脚本） — 禁止执行代码
- `git commit`、`git push` — 禁止直接操作版本控制
- `rm`、`mv`、`cp` — 禁止文件操作
- `send_mail.sh` 发往非授权收件人 — 禁止越级通信
