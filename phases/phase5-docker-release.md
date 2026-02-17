# Phase 5 Contract: Docker + Documentation + Release

## 工作目录
cd ~/Desktop/nexus-ai-team

## 准备
1. git checkout -b phase5-docker-release main

## 任务

### Docker Compose 全栈 (docker/)
1. 完善 docker-compose.yml:
   - gateway 服务（FastAPI + uvicorn）
   - redis 服务
   - postgresql 服务
   - dashboard 前端（nginx 静态服务或 node dev server）
2. 创建 Dockerfile（多阶段构建，最终镜像精简）
3. 创建 docker/init.sql — 数据库初始化
4. 实现 make up / make down / make logs 快捷命令 (Makefile)
5. 确保 .env.example 包含所有配置项

### 文档
1. 完善 README.md:
   - 完整的安装指南（Docker 方式 + 手动方式）
   - 配置说明（所有环境变量）
   - 架构图（ASCII 或 Mermaid）
   - API 参考
   - 使用示例（Telegram + Web GUI）
   - 贡献指南
2. 最终更新 PROGRESS.md — 标记所有 phase 完成
3. 创建 CHANGELOG.md
4. 确保 LICENSE 文件存在（MIT）

### 最终验证
1. docker compose up 能启动所有服务
2. curl localhost:8000/health 返回 200
3. curl localhost:8000/docs 返回 Swagger UI

## 完成后
1. git add -A && git commit -m "feat: Phase 5 — Docker deployment + documentation + v1.0"
2. git push origin phase5-docker-release
