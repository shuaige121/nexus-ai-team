# Phase 3A Contract: LAN Web GUI

## 工作目录
cd ~/Desktop/nexus-ai-team

## 准备
1. git checkout -b phase3a-webgui main

## 任务
实现 LAN Web GUI，让用户可以通过浏览器管理和使用 NEXUS。

### 后端 API (gateway/ 扩展)
1. 在 gateway/main.py 中添加以下 REST 端点:
   - GET /api/agents — 列出所有 agent 和状态
   - GET /api/work-orders — 查询工作单（支持 status/agent 过滤）
   - GET /api/metrics — 系统指标（token 用量、请求数、成本）
   - POST /api/chat — 已有，确保返回格式与前端兼容
2. 所有端点返回 JSON，有错误处理

### 前端 (dashboard/)
1. 检查是否已有 dashboard/ 目录（之前 merge 了 dashboard 分支），在此基础上完善
2. 使用 React + Vite + Tailwind CSS
3. 实现页面：
   - **Chat** — 与 NEXUS 对话，实时显示回复（WebSocket）
   - **Agents** — 查看组织架构和 agent 状态
   - **Work Orders** — 工作单列表和详情
   - **Metrics** — token 用量和成本图表
4. 响应式设计，支持手机和桌面

### 文档更新
1. 更新 README.md：添加 Web GUI 使用说明
2. 更新 PROGRESS.md：记录 Phase 3A 完成状态
3. 更新 WORK_CALENDAR.md：记录本次工作

## 完成后
1. git add -A && git commit -m "feat: Phase 3A — LAN Web GUI with React dashboard"
2. git push origin phase3a-webgui
