# Equipment Framework

`equipment/` 存放“机器做机器事”的自动化资产（脚本、任务、模板、数据与运行日志），用于承载可重复、可编排、可监控的确定性工作。

## 目录结构

```text
equipment/
├── scripts/     # 一次性或可复用脚本（抓取、转换、同步）
├── jobs/        # 定时任务定义与任务入口
├── templates/   # 通用模板（报告、消息、配置片段）
├── data/        # 运行时数据缓存（默认不放敏感数据）
└── logs/        # 设备任务日志（建议按日期/任务名分层）
```

## 约定

1. 每个脚本都应支持 `--help`，并返回明确退出码。
2. 所有任务日志必须包含 `job_name`、`started_at`、`ended_at`、`status`。
3. 若任务写入数据库或外部系统，必须在 `audit_logs` 记录操作摘要。
4. 长任务应可重试，并具备幂等保护（重复执行不产生重复副作用）。

## 命名建议

- 脚本：`verb_noun.py`，例如 `sync_contacts.py`
- 任务：`<frequency>_<purpose>.py`，例如 `hourly_health_report.py`
- 模板：`<domain>_<format>.template`，例如 `report_markdown.template`
