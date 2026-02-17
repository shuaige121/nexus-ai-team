## UAT 测试场景 — Phase 3B QA + Logging

### 测试 1: QA Pipeline
1. cd ~/Desktop/nexus-ai-team
2. 创建一个测试工作单 mock（JSON 文件），运行 QA runner 验证
3. 验证 QA 对完整工作单返回 PASS
4. 验证 QA 对有缺陷的工作单返回 FAIL + 具体原因

### 测试 2: 数据库降级
1. 不配置 DATABASE_URL，验证系统优雅降级到 SQLite 或 JSON 文件
2. 调用 log_work_order() 和 query_metrics()，验证数据持久化

### 测试 3: 交叉检查
1. 用 claude --dangerously-skip-permissions -p "审查 ~/Desktop/nexus-ai-team/db/client.py 的 SQL 查询，检查是否有 SQL 注入风险。只输出发现的问题，没有问题就说 SAFE"
2. 用 codex --dangerously-bypass-approvals-and-sandbox -p "审查 ~/Desktop/nexus-ai-team/qa/runner.py，检查验证逻辑是否可被绕过。只输出问题"
