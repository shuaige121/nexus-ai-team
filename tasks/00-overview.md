# AgentOffice 实施任务总览

## 目标

把当前的 Python 单进程原型，演进为设计文档描述的完整系统：
每个 Agent 是独立的 Claude Code 进程，通过文件系统邮件通信，Linux 权限硬隔离。

## 任务依赖关系

```
Wave 1（可并行，无依赖）:
├── 01-workspace-structure   创建 /agents/ 目录结构
├── 02-core-scripts          send_mail / check_inbox / write_memory
└── 03-role-templates        所有角色的 JD.md + TOOL.md 模板

Wave 2（依赖 Wave 1）:
├── 04-hr-scripts            create_agent.sh / delete_agent.sh（依赖 01+02）
├── 05-it-support            IT Support 角色 + 工具管理脚本（依赖 01+02+03）
└── 06-contract-format       Contract .md 格式 + 解析脚本（依赖 02）

Wave 3（依赖 Wave 1+2）:
├── 07-multi-process         多进程 Agent 启动器（依赖 01+02+04）
└── 08-integration-test      端到端流程验证（依赖全部）
```

## 执行建议

1. 开 3 个 Claude Code 窗口，同时跑 01、02、03
2. 01+02 完成后，开 3 个窗口跑 04、05、06
3. Wave 2 全部完成后跑 07
4. 最后用 08 做端到端验收

## 每个任务文件的使用方法

每个 .md 文件包含两部分：
- **PROMPT**：直接复制粘贴到新的 Claude Code 会话中
- **CONTRACT**：正式的任务规格书，嵌在 prompt 里

打开新终端 → 启动 claude → 粘贴对应的 prompt → 让 agent 执行。

## 产出位置

所有产出统一放在项目根目录的 `agents/` 目录下（注意：不是 `company/agents/`，
那是旧原型的数据目录）。脚本放在 `agents/scripts/`，模板放在 `agents/templates/`。
