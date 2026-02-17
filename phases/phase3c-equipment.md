# Phase 3C Contract: Equipment Framework

## 工作目录
cd ~/Desktop/nexus-ai-team

## 准备
1. git checkout -b phase3c-equipment main

## 任务
实现 Equipment 框架 — 确定性的自动化脚本，不需要 LLM 就能完成的重复任务。

### 框架 (equipment/)
1. 实现 equipment/manager.py — 设备管理器：
   - register_equipment() — 注册新设备（脚本）
   - run_equipment() — 执行设备
   - schedule_equipment() — 定时任务（cron 表达式）
   - list_equipment() — 列出所有设备和状态
2. 设备配置格式 (equipment/registry.yaml)
3. 实现示例设备：
   - equipment/scripts/health_check.py — 检查系统健康（CPU/RAM/Disk/GPU）
   - equipment/scripts/log_rotate.py — 日志轮转和清理
   - equipment/scripts/backup.py — 项目备份到指定目录
   - equipment/scripts/cost_report.py — 每日 token 成本报告

### Gateway 集成
1. 在 gateway 添加 /api/equipment 端点
2. Admin agent 判断请求是否可以用设备处理（省钱）

### 文档更新
1. 更新 README.md：添加 Equipment 使用说明
2. 更新 PROGRESS.md

## 完成后
1. git add -A && git commit -m "feat: Phase 3C — Equipment automation framework"
2. git push origin phase3c-equipment
