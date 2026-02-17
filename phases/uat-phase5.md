## UAT 测试场景 — Phase 5 Docker + Release

### 测试 1: Docker 构建
1. cd ~/Desktop/nexus-ai-team
2. docker compose config — 验证配置语法正确
3. docker compose build — 验证镜像构建成功（如果有 Docker）
4. 如果没有 Docker，验证 Dockerfile 和 docker-compose.yml 语法正确

### 测试 2: 手动启动验证
1. pip install -e .
2. python3 -m uvicorn gateway.main:app --port 8000 &
3. curl http://localhost:8000/health → 200
4. curl http://localhost:8000/docs → Swagger UI

### 测试 3: 文档完整性
1. 验证 README.md 包含: 安装指南、配置说明、API 参考、使用示例
2. 验证 CHANGELOG.md 存在
3. 验证 LICENSE 存在
4. 验证 .env.example 包含所有环境变量

### 测试 4: 端到端模拟
1. 用 claude --dangerously-skip-permissions -p "作为一个全新用户，只看 ~/Desktop/nexus-ai-team/README.md，按照指南尝试安装和使用。报告遇到的任何问题。"
2. 用 codex --dangerously-bypass-approvals-and-sandbox -p "审查 ~/Desktop/nexus-ai-team 整个项目的安全性，特别是认证、输入验证、环境变量处理。给出安全评分和改进建议"

### 清理
- kill 后台进程
