# Task 08: 端到端集成测试

## PROMPT（复制粘贴到新的 Claude Code 会话）

```
你是一个 QA 工程师，负责对 AgentOffice 多 Agent 系统进行端到端集成测试。

## 项目背景

AgentOffice 用文件系统组织多个 Claude Code 实例，模拟公司组织结构。你需要验证
整个系统能跑通一个完整的任务流程：

用户提需求 → CEO 拆解 → Manager 分配 → Worker 执行 → QA 验收 → 汇报

前面 7 个任务已经产出了：
- agents/ 目录结构（Task 01）
- 核心脚本：send_mail / check_inbox / read_mail / write_memory（Task 02）
- 角色模板：JD.md / TOOL.md（Task 03）
- HR 脚本：create_agent / delete_agent（Task 04）
- IT 脚本：install_tool / remove_tool / search_tool（Task 05）
- Contract 管理：create_contract / update_contract / list_contracts（Task 06）
- 启动器：start_agent / stop_agent / orchestrator（Task 07）

## 你的任务

编写并执行一个端到端测试场景，验证所有组件协同工作。

### 测试场景：CEO 要求开发一个 "Hello World" API

这是最简单的真实场景，但覆盖了完整的流程。

### 测试步骤

#### Phase 1: 环境准备

```bash
# 1. 确认基础结构存在
ls agents/ceo/ agents/hr/ agents/it-support/

# 2. 确认脚本可执行
ls -la agents/scripts/*.sh

# 3. CEO 已存在，HR 已存在，IT Support 已存在
cat agents/registry.yaml
```

#### Phase 2: CEO 发起项目

```bash
# 4. CEO 给 HR 发招聘邮件：需要一个网关部门
echo "需要创建网关部门（dept-gateway），包含：
- 1个部门经理
- 1个开发工程师
- 1个QA" | agents/scripts/send_mail.sh ceo hr hire create-gateway-dept

# 5. HR 收到邮件
agents/scripts/check_inbox.sh hr

# 6. HR 读取邮件
agents/scripts/read_mail.sh hr <最新邮件文件名>

# 7. HR 创建部门 Manager
agents/scripts/create_agent.sh dept-gw-manager manager dept-gateway ceo

# 8. HR 创建 Worker
agents/scripts/create_agent.sh dept-gw-dev-01 worker dept-gateway dept-gw-manager

# 9. HR 创建 QA
agents/scripts/create_agent.sh dept-gw-qa qa dept-gateway dept-gw-manager

# 10. 验证：registry 更新了
cat agents/registry.yaml

# 11. 验证：目录结构正确
ls -la agents/dept-gw-manager/
ls -la agents/dept-gw-dev-01/
ls -la agents/dept-gw-qa/
```

#### Phase 3: CEO 分发任务

```bash
# 12. CEO 创建 Contract
echo '{
  "background": "需要一个简单的 Hello World HTTP API 用于验证系统流程",
  "objective": "交付一个能返回 Hello World 的 HTTP 服务",
  "requirements": ["GET / 返回 {\"message\": \"Hello World\"}", "有单元测试"],
  "restrictions": ["不要添加额外功能", "不要使用数据库"],
  "input": "无上游依赖",
  "output": "WORKSPACE 里的 Python 文件 + 测试文件",
  "acceptance_criteria": ["GET / 返回正确 JSON", "测试通过"],
  "context_budget": "小型任务"
}' | agents/scripts/create_contract.sh ceo dept-gw-manager

# 13. CEO 通知 Manager
echo "已创建 Contract CTR-xxx，请查收并安排执行。" | \
  agents/scripts/send_mail.sh ceo dept-gw-manager contract new-task

# 14. Manager 收到通知
agents/scripts/check_inbox.sh dept-gw-manager
```

#### Phase 4: Manager 拆解并分配

```bash
# 15. Manager 创建子 Contract 给 Worker
echo '{
  "background": "网关部门收到 CEO 任务：Hello World API",
  "objective": "编写 HTTP 服务和测试",
  "requirements": ["用 Python http.server 或 Flask", "GET / 返回 JSON", "写 pytest 测试"],
  "restrictions": ["不要添加鉴权", "代码不超过 50 行"],
  "input": "空的 WORKSPACE",
  "output": "app.py + test_app.py",
  "acceptance_criteria": ["python app.py 能启动", "pytest test_app.py 全通过"],
  "context_budget": "小型任务"
}' | agents/scripts/create_contract.sh dept-gw-manager dept-gw-dev-01 --parent CTR-xxx

# 16. Worker 收到
agents/scripts/check_inbox.sh dept-gw-dev-01
```

#### Phase 5: Worker 执行（模拟）

```bash
# 17. 模拟 Worker 在 WORKSPACE 写代码
cat > agents/dept-gw-dev-01/WORKSPACE/app.py << 'PYEOF'
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"message": "Hello World"}).encode())

if __name__ == "__main__":
    HTTPServer(("", 8080), Handler).serve_forever()
PYEOF

cat > agents/dept-gw-dev-01/WORKSPACE/test_app.py << 'PYEOF'
import json
import threading
import urllib.request
from app import HTTPServer, Handler

def test_hello():
    server = HTTPServer(("", 18080), Handler)
    t = threading.Thread(target=server.handle_request)
    t.start()
    resp = urllib.request.urlopen("http://localhost:18080/")
    data = json.loads(resp.read())
    assert data == {"message": "Hello World"}
    t.join()
PYEOF

# 18. Worker 发完成报告给 Manager
echo "任务完成。产出：
- app.py: HTTP 服务，GET / 返回 {\"message\": \"Hello World\"}
- test_app.py: 单元测试
所有文件在 WORKSPACE/ 下。" | \
  agents/scripts/send_mail.sh dept-gw-dev-01 dept-gw-manager report task-complete

# 19. 更新 Contract 状态
agents/scripts/update_contract.sh CTR-xxx-A review
```

#### Phase 6: QA 验收（模拟）

```bash
# 20. Manager 发验收请求给 QA
echo "请验收 Worker dept-gw-dev-01 的产出。
Contract: CTR-xxx-A
交付物位置: agents/dept-gw-dev-01/WORKSPACE/
验收标准:
1. python app.py 能启动
2. pytest test_app.py 全通过" | \
  agents/scripts/send_mail.sh dept-gw-manager dept-gw-qa review verify-output

# 21. QA 检查（模拟）
cd agents/dept-gw-dev-01/WORKSPACE/
python3 -c "import app; print('import OK')"
python3 -m pytest test_app.py -v

# 22. QA 发验收结果
echo "验收结果: 通过 ✓

逐条检查:
- [x] GET / 返回正确 JSON: 通过
- [x] 测试通过: 1/1 passed

无问题。" | \
  agents/scripts/send_mail.sh dept-gw-qa dept-gw-manager result review-passed

# 23. 更新 Contract 状态
agents/scripts/update_contract.sh CTR-xxx-A passed
```

#### Phase 7: Manager 汇报 CEO

```bash
# 24. Manager 发汇报给 CEO
echo "部门任务完成报告:

Contract: CTR-xxx
状态: 所有子任务已通过验收

产出摘要:
- Hello World API 已完成
- GET / 返回 {\"message\": \"Hello World\"}
- 单元测试通过

交付物位置: agents/dept-gw-dev-01/WORKSPACE/" | \
  agents/scripts/send_mail.sh dept-gw-manager ceo report dept-task-complete

# 25. 更新主 Contract 状态
agents/scripts/update_contract.sh CTR-xxx passed

# 26. CEO 查看最终状态
agents/scripts/check_inbox.sh ceo
agents/scripts/list_contracts.sh --status passed
```

### 验证检查清单

在每个 Phase 完成后，检查：

1. **邮件送达**：目标 INBOX 里有文件
2. **邮件格式**：打开邮件文件确认格式正确
3. **Agent 创建**：目录结构完整、JD.md 正确、registry 更新
4. **Contract 流转**：ID 正确、状态转换合法、变更记录追加
5. **文件不越界**：Worker 的文件只在 WORKSPACE 里

### 测试结果模板

测试完成后，输出测试报告到 agents/test-report.md：

```markdown
# AgentOffice 端到端测试报告

日期: {date}
测试人: QA Agent

## 测试结果总览

| Phase | 描述 | 结果 |
|-------|------|------|
| 1     | 环境准备 | ✓/✗ |
| 2     | CEO 发起 | ✓/✗ |
| 3     | CEO 分发 | ✓/✗ |
| 4     | Manager 拆解 | ✓/✗ |
| 5     | Worker 执行 | ✓/✗ |
| 6     | QA 验收 | ✓/✗ |
| 7     | Manager 汇报 | ✓/✗ |

## 发现的问题

（逐条列出）

## 建议

（改进建议）
```

## 约束

- 你是 QA，只测试不改实现代码
- 如果某个脚本有 bug，记录在报告中，不要自己修
- 测试报告放在 agents/test-report.md
- 用真实脚本执行（不要 mock），如果脚本不存在则记录为"未实现"
- 如果某个 Phase 失败，继续测试后面的 Phase（尽量多覆盖）

## 验收标准

- [ ] 7 个 Phase 都执行了（或标记为因依赖未满足而跳过）
- [ ] 测试报告生成且格式正确
- [ ] 每个 Phase 的结果都有记录
- [ ] 发现的问题都有清楚描述
- [ ] 没有修改任何实现代码
```

---

## CONTRACT

```
ID: CTR-20260216-008
FROM: ceo
TO: qa-worker-01
STATUS: pending
CREATED: 2026-02-16
PRIORITY: medium

任务目标: 执行端到端集成测试，验证全流程可行，输出测试报告
依赖: 01, 02, 03, 04, 05, 06, 07（全部）
被依赖: 无（终点）
预估上下文: 中型任务，单个 QA Worker 可完成
```
