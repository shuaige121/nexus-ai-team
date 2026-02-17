## UAT 测试场景 — Phase 3C Equipment

### 测试 1: 设备注册和执行
1. cd ~/Desktop/nexus-ai-team
2. 调用 register_equipment() 注册 health_check 设备
3. 调用 run_equipment("health_check") 执行健康检查
4. 验证返回 CPU/RAM/Disk 信息

### 测试 2: 设备列表 API
1. 启动 gateway
2. curl http://localhost:8000/api/equipment — 验证返回设备列表

### 测试 3: 模拟 Admin 判断
1. 用 claude --dangerously-skip-permissions -p "模拟一个用户请求: '检查服务器磁盘空间'。这个请求应该被路由到 equipment 而不是 LLM。验证 admin agent 的路由逻辑是否能正确识别这类请求"

### 测试 4: 交叉检查
1. 用 codex --dangerously-bypass-approvals-and-sandbox -p "审查 ~/Desktop/nexus-ai-team/equipment/ 的所有脚本，检查是否有命令注入、路径遍历等安全问题。只输出问题"
