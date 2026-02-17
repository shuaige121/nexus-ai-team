# Phase 4A Contract: Heartbeat Monitoring

## 工作目录
cd ~/Desktop/nexus-ai-team

## 准备
1. git checkout -b phase4a-heartbeat main

## 任务

### Heartbeat System (heartbeat/)
1. heartbeat/monitor.py — 周期性健康检查：
   - 检查 gateway 是否响应
   - 检查各 agent 最后活跃时间
   - 检查 Redis/PostgreSQL 连通性
   - 检查 GPU 状态（如果有 Ollama）
   - 检查 token 预算是否超支
2. heartbeat/alerts.py — 告警通知：
   - 严重问题 → Telegram 通知 Board（用户）
   - 一般问题 → 写入日志 + 自动尝试恢复
3. heartbeat/recovery.py — 自动恢复：
   - Gateway 无响应 → 自动重启
   - Agent 卡死 → kill + 重启
   - 磁盘满 → 自动清理日志
4. 实现 systemd service 或 cron 方式运行

### Gateway 集成
1. GET /api/health/detailed — 详细健康报告
2. WebSocket 推送健康状态变化

### 文档更新
1. 更新 README.md 和 PROGRESS.md

## 完成后
1. git add -A && git commit -m "feat: Phase 4A — Heartbeat monitoring + auto-recovery"
2. git push origin phase4a-heartbeat
