## UAT 测试场景 — Phase 3A Web GUI

### 测试 1: API 端点
1. 启动 gateway: cd ~/Desktop/nexus-ai-team && python3 -m uvicorn gateway.main:app --host 0.0.0.0 --port 8000 &
2. 等待 3 秒
3. curl http://localhost:8000/api/agents — 验证返回 JSON 列表
4. curl http://localhost:8000/api/work-orders — 验证返回 JSON
5. curl http://localhost:8000/api/metrics — 验证返回 JSON
6. curl http://localhost:8000/docs — 验证返回 Swagger UI (200)

### 测试 2: 模拟用户对话
1. 用 claude --dangerously-skip-permissions -p "发送一个 curl POST 请求到 http://localhost:8000/api/chat，body 为 {\"message\": \"你好，请问今天天气怎么样？\"} 并返回响应内容" 获取回复
2. 验证响应格式正确（有 response 字段）

### 测试 3: 前端构建
1. cd dashboard/frontend && npm install && npm run build — 验证无报错
2. 检查 dist/ 目录生成了 index.html

### 测试 4: 交叉检查
1. 用 codex --dangerously-bypass-approvals-and-sandbox -p "审查 ~/Desktop/nexus-ai-team/gateway/main.py 的安全性，检查是否有注入漏洞、未验证输入、CORS 配置问题。只输出发现的问题，没有问题就说 SAFE" 做安全交叉检查

### 清理
- kill 掉后台 uvicorn 进程
