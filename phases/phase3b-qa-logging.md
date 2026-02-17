# Phase 3B Contract: QA Pipeline + PostgreSQL Logging

## 工作目录
cd ~/Desktop/nexus-ai-team

## 准备
1. git checkout -b phase3b-qa-logging main

## 任务

### QA Pipeline (qa/)
1. 扩展 qa/runner.py 为完整的验证管道：
   - 格式检查（JSON schema 验证）
   - 内容完整性检查（无空字段、无 placeholder）
   - 代码执行验证（如果回复包含代码，尝试执行）
   - 安全检查（无敏感信息泄露）
2. 实现 qa/specs/ 下的多个测试规格文件
3. QA 结果写入数据库

### PostgreSQL Logging (db/)
1. 基于 db/schema.sql 实现 Python 数据库访问层
2. 在 db/client.py 中实现:
   - log_work_order() — 记录工作单创建/完成
   - log_agent_metric() — 记录 agent 的 token 用量和响应时间
   - log_audit() — 审计日志
   - query_metrics() — 按时间范围查询指标
3. 在 gateway 和 pipeline 中集成日志记录
4. 支持环境变量配置（无 PostgreSQL 时优雅降级到 SQLite/JSON）

### 文档更新
1. 更新 README.md：添加 QA 和日志配置说明
2. 更新 PROGRESS.md：记录 Phase 3B 完成状态

## 完成后
1. git add -A && git commit -m "feat: Phase 3B — QA pipeline + PostgreSQL logging"
2. git push origin phase3b-qa-logging
