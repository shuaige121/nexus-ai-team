## UAT 测试场景 — Phase 4A Heartbeat

### 测试 1: 健康检查
1. cd ~/Desktop/nexus-ai-team
2. 运行 heartbeat monitor 的单次检查
3. 验证返回 gateway/redis/postgresql 各项状态

### 测试 2: 告警触发
1. 故意让 gateway 停止
2. 运行 heartbeat 检查，验证生成告警
3. 验证自动恢复逻辑（尝试重启）

### 测试 3: API 集成
1. 启动 gateway
2. curl http://localhost:8000/api/health/detailed
3. 验证返回详细健康信息

### 测试 4: 交叉检查
1. 用 claude --dangerously-skip-permissions -p "审查 ~/Desktop/nexus-ai-team/heartbeat/recovery.py，检查自动恢复逻辑是否安全（不会误杀进程、不会无限重启）"
2. 用 codex --dangerously-bypass-approvals-and-sandbox -p "审查 ~/Desktop/nexus-ai-team/heartbeat/ 所有文件，检查是否有权限提升风险"
