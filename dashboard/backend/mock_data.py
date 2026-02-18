"""Mock data layer for the dashboard. Simulates AgentOffice data."""

import random
from datetime import UTC, datetime, timedelta

# --- Organization ---

MOCK_ORG = {
    "company_name": "NexusAI Corp",
    "departments": [
        {
            "name": "executive",
            "display_name": "高管层",
            "agents": ["ceo"]
        },
        {
            "name": "hr",
            "display_name": "人力资源部",
            "agents": ["hr_lead"]
        },
        {
            "name": "engineering",
            "display_name": "工程部",
            "agents": ["eng_director", "backend_dev", "frontend_dev", "qa_engineer"]
        },
        {
            "name": "research",
            "display_name": "研究部",
            "agents": ["research_lead", "web_researcher", "data_analyst"]
        },
        {
            "name": "marketing",
            "display_name": "市场部",
            "agents": ["marketing_lead", "content_writer"]
        }
    ]
}

MOCK_AGENTS = {
    "ceo": {
        "id": "ceo",
        "name": "CEO",
        "display_name": "首席执行官",
        "department": "executive",
        "level": "c-suite",
        "reports_to": None,
        "model": "claude-opus-4-20250514",
        "model_short": "Opus",
        "provider": "anthropic",
        "temperature": 0.7,
        "max_tokens": 8192,
        "status": "idle",
        "jd": "# 首席执行官 (CEO)\n\n## 核心职责\n- 接收用户指令，理解全局目标\n- 将复杂任务拆解为可执行的子任务\n- 通过Contract分配给各部门负责人\n- 审批关键决策和升级请求\n\n## 决策边界\n- 只与Director级别直接沟通\n- 不直接管理Worker级别员工\n- 预算超过阈值需要用户审批\n\n## 可用工具\n- create_department\n- create_agent\n- update_chain",
        "resume": "# CEO 人格档案\n\n## 性格特征\n- 战略思维，善于全局规划\n- 决策果断，但会考虑多方面因素\n- 沟通简洁明了\n\n## 工作习惯\n- 优先处理高优先级任务\n- 定期检查各部门进度\n- 对质量要求严格\n\n## 协作备注\n- 通过Contract与下属沟通\n- 期望收到结构化的汇报",
        "memory": "## 近期记忆\n- 刚完成组织架构初始化\n- 招聘了工程部和研究部团队\n- 正在推进市场调研项目\n\n## 关键决策\n- 选择Claude Opus作为CEO模型\n- 工程部采用三人小组结构",
        "race": "model: claude-opus-4-20250514\nprovider: anthropic\ntemperature: 0.7\nmax_tokens: 8192\nreasoning_level: high\ncost_per_1k_input: 0.015\ncost_per_1k_output: 0.075"
    },
    "hr_lead": {
        "id": "hr_lead",
        "name": "HR Lead",
        "display_name": "人力资源总监",
        "department": "hr",
        "level": "director",
        "reports_to": "ceo",
        "model": "claude-sonnet-4-20250514",
        "model_short": "Sonnet",
        "provider": "anthropic",
        "temperature": 0.5,
        "max_tokens": 4096,
        "status": "idle",
        "jd": "# 人力资源总监 (HR Lead)\n\n## 核心职责\n- 根据CEO指令创建新部门和岗位\n- 生成JD和Resume文件\n- 管理组织架构变更\n- 处理调岗和解雇流程\n\n## 可用工具\n- create_agent\n- create_department\n- remove_agent\n- remove_department\n- update_chain",
        "resume": "# HR Lead 人格档案\n\n## 性格特征\n- 细致周到，注重流程\n- 善于评估人员匹配度\n- 沟通温和但高效",
        "memory": "## 近期记忆\n- 完成了初始团队搭建\n- 处理了3次招聘请求",
        "race": "model: claude-sonnet-4-20250514\nprovider: anthropic\ntemperature: 0.5\nmax_tokens: 4096\ncost_per_1k_input: 0.003\ncost_per_1k_output: 0.015"
    },
    "eng_director": {
        "id": "eng_director",
        "name": "Engineering Director",
        "display_name": "工程总监",
        "department": "engineering",
        "level": "director",
        "reports_to": "ceo",
        "model": "claude-sonnet-4-20250514",
        "model_short": "Sonnet",
        "provider": "anthropic",
        "temperature": 0.5,
        "max_tokens": 4096,
        "status": "busy",
        "jd": "# 工程总监\n\n## 核心职责\n- 接收CEO的技术任务\n- 拆解为具体开发任务分配给工程师\n- 代码质量审核\n- 技术方案评审",
        "resume": "# Engineering Director 人格档案\n\n## 性格特征\n- 技术导向，追求代码质量\n- 善于分解复杂问题",
        "memory": "## 近期记忆\n- 正在处理后端API重构任务\n- 分配了前端优化给frontend_dev",
        "race": "model: claude-sonnet-4-20250514\nprovider: anthropic\ntemperature: 0.5\nmax_tokens: 4096\ncost_per_1k_input: 0.003\ncost_per_1k_output: 0.015"
    },
    "backend_dev": {
        "id": "backend_dev",
        "name": "Backend Developer",
        "display_name": "后端开发工程师",
        "department": "engineering",
        "level": "worker",
        "reports_to": "eng_director",
        "model": "claude-haiku-3-5-20241022",
        "model_short": "Haiku",
        "provider": "anthropic",
        "temperature": 0.3,
        "max_tokens": 4096,
        "status": "busy",
        "jd": "# 后端开发工程师\n\n## 核心职责\n- 编写Python后端代码\n- API接口开发\n- 数据库操作\n- 单元测试\n\n## 可用工具\n- code_exec\n- web_search",
        "resume": "# Backend Dev 人格档案\n\n## 性格特征\n- 专注、高效\n- 代码风格规范",
        "memory": "## 近期记忆\n- 正在开发用户认证模块\n- 完成了数据库schema设计",
        "race": "model: claude-haiku-3-5-20241022\nprovider: anthropic\ntemperature: 0.3\nmax_tokens: 4096\ncost_per_1k_input: 0.001\ncost_per_1k_output: 0.005"
    },
    "frontend_dev": {
        "id": "frontend_dev",
        "name": "Frontend Developer",
        "display_name": "前端开发工程师",
        "department": "engineering",
        "level": "worker",
        "reports_to": "eng_director",
        "model": "claude-haiku-3-5-20241022",
        "model_short": "Haiku",
        "provider": "anthropic",
        "temperature": 0.3,
        "max_tokens": 4096,
        "status": "idle",
        "jd": "# 前端开发工程师\n\n## 核心职责\n- React前端开发\n- UI/UX实现\n- 组件库维护\n- 性能优化",
        "resume": "# Frontend Dev 人格档案\n\n## 性格特征\n- 注重用户体验\n- 追求像素级还原",
        "memory": "## 近期记忆\n- 完成了仪表盘首页布局\n- 正在优化组件性能",
        "race": "model: claude-haiku-3-5-20241022\nprovider: anthropic\ntemperature: 0.3\nmax_tokens: 4096\ncost_per_1k_input: 0.001\ncost_per_1k_output: 0.005"
    },
    "qa_engineer": {
        "id": "qa_engineer",
        "name": "QA Engineer",
        "display_name": "质量保证工程师",
        "department": "engineering",
        "level": "worker",
        "reports_to": "eng_director",
        "model": "claude-haiku-3-5-20241022",
        "model_short": "Haiku",
        "provider": "anthropic",
        "temperature": 0.2,
        "max_tokens": 4096,
        "status": "idle",
        "jd": "# QA工程师\n\n## 核心职责\n- 代码质量检查\n- 测试用例编写\n- Bug追踪\n- 质检报告编写",
        "resume": "# QA Engineer 人格档案\n\n## 性格特征\n- 严谨细致\n- 对质量零容忍",
        "memory": "## 近期记忆\n- 审查了最近3个PR\n- 发现了2个关键Bug",
        "race": "model: claude-haiku-3-5-20241022\nprovider: anthropic\ntemperature: 0.2\nmax_tokens: 4096\ncost_per_1k_input: 0.001\ncost_per_1k_output: 0.005"
    },
    "research_lead": {
        "id": "research_lead",
        "name": "Research Lead",
        "display_name": "研究部主管",
        "department": "research",
        "level": "manager",
        "reports_to": "ceo",
        "model": "claude-sonnet-4-20250514",
        "model_short": "Sonnet",
        "provider": "anthropic",
        "temperature": 0.6,
        "max_tokens": 4096,
        "status": "idle",
        "jd": "# 研究部主管\n\n## 核心职责\n- 管理研究团队\n- 制定调研方案\n- 整合研究成果\n- 向CEO汇报",
        "resume": "# Research Lead 人格档案\n\n## 性格特征\n- 好奇心强\n- 善于归纳总结",
        "memory": "## 近期记忆\n- 完成了市场竞品分析\n- 正在进行技术趋势调研",
        "race": "model: claude-sonnet-4-20250514\nprovider: anthropic\ntemperature: 0.6\nmax_tokens: 4096\ncost_per_1k_input: 0.003\ncost_per_1k_output: 0.015"
    },
    "web_researcher": {
        "id": "web_researcher",
        "name": "Web Researcher",
        "display_name": "网络调研员",
        "department": "research",
        "level": "worker",
        "reports_to": "research_lead",
        "model": "claude-haiku-3-5-20241022",
        "model_short": "Haiku",
        "provider": "anthropic",
        "temperature": 0.3,
        "max_tokens": 4096,
        "status": "idle",
        "jd": "# 网络调研员\n\n## 核心职责\n- 网络信息搜索\n- 数据收集\n- 竞品分析\n- 趋势追踪\n\n## 可用工具\n- web_search",
        "resume": "# Web Researcher 人格档案\n\n## 性格特征\n- 信息敏感度高\n- 善于筛选有效信息",
        "memory": "## 近期记忆\n- 完成了3篇竞品报告",
        "race": "model: claude-haiku-3-5-20241022\nprovider: anthropic\ntemperature: 0.3\nmax_tokens: 4096\ncost_per_1k_input: 0.001\ncost_per_1k_output: 0.005"
    },
    "data_analyst": {
        "id": "data_analyst",
        "name": "Data Analyst",
        "display_name": "数据分析师",
        "department": "research",
        "level": "worker",
        "reports_to": "research_lead",
        "model": "claude-haiku-3-5-20241022",
        "model_short": "Haiku",
        "provider": "anthropic",
        "temperature": 0.2,
        "max_tokens": 4096,
        "status": "idle",
        "jd": "# 数据分析师\n\n## 核心职责\n- 数据清洗和分析\n- 报表生成\n- 趋势预测\n- 数据可视化\n\n## 可用工具\n- code_exec\n- canvas",
        "resume": "# Data Analyst 人格档案\n\n## 性格特征\n- 数字敏感\n- 逻辑严密",
        "memory": "## 近期记忆\n- 完成了月度数据报告",
        "race": "model: claude-haiku-3-5-20241022\nprovider: anthropic\ntemperature: 0.2\nmax_tokens: 4096\ncost_per_1k_input: 0.001\ncost_per_1k_output: 0.005"
    },
    "marketing_lead": {
        "id": "marketing_lead",
        "name": "Marketing Lead",
        "display_name": "市场部主管",
        "department": "marketing",
        "level": "manager",
        "reports_to": "ceo",
        "model": "claude-sonnet-4-20250514",
        "model_short": "Sonnet",
        "provider": "anthropic",
        "temperature": 0.7,
        "max_tokens": 4096,
        "status": "idle",
        "jd": "# 市场部主管\n\n## 核心职责\n- 市场策略制定\n- 内容规划\n- 品牌管理\n- 向CEO汇报市场动态",
        "resume": "# Marketing Lead 人格档案\n\n## 性格特征\n- 创意丰富\n- 善于洞察市场趋势",
        "memory": "## 近期记忆\n- 制定了Q1市场推广计划",
        "race": "model: claude-sonnet-4-20250514\nprovider: anthropic\ntemperature: 0.7\nmax_tokens: 4096\ncost_per_1k_input: 0.003\ncost_per_1k_output: 0.015"
    },
    "content_writer": {
        "id": "content_writer",
        "name": "Content Writer",
        "display_name": "内容创作者",
        "department": "marketing",
        "level": "worker",
        "reports_to": "marketing_lead",
        "model": "claude-haiku-3-5-20241022",
        "model_short": "Haiku",
        "provider": "anthropic",
        "temperature": 0.8,
        "max_tokens": 4096,
        "status": "idle",
        "jd": "# 内容创作者\n\n## 核心职责\n- 文案撰写\n- 博客文章\n- 社交媒体内容\n- SEO优化\n\n## 可用工具\n- web_search\n- canvas",
        "resume": "# Content Writer 人格档案\n\n## 性格特征\n- 文笔流畅\n- 创意十足",
        "memory": "## 近期记忆\n- 完成了产品介绍文案\n- 发布了2篇博客文章",
        "race": "model: claude-haiku-3-5-20241022\nprovider: anthropic\ntemperature: 0.8\nmax_tokens: 4096\ncost_per_1k_input: 0.001\ncost_per_1k_output: 0.005"
    }
}

# --- Contracts ---

CONTRACT_TYPES = ["task", "report", "revision", "escalation", "assistance"]
PRIORITIES = ["high", "medium", "low"]
STATUSES = ["pending", "executing", "completed", "failed", "archived"]

def _ts(days_ago: int = 0, hours_ago: int = 0) -> str:
    dt = datetime.now(UTC) - timedelta(days=days_ago, hours=hours_ago)
    return dt.isoformat()

MOCK_CONTRACTS = [
    {
        "id": "CTR-001",
        "type": "task",
        "from_agent": "ceo",
        "to_agent": "eng_director",
        "priority": "high",
        "status": "executing",
        "objective": "重构后端API接口，提升响应速度和代码可维护性，确保向后兼容",
        "payload": {"objective": "重构后端API接口，提升响应速度和代码可维护性，确保向后兼容", "deadline": "2026-02-20", "constraints": ["保持API向后兼容", "添加单元测试"]},
        "parent_id": None,
        "created_at": _ts(1, 3),
        "updated_at": _ts(0, 2)
    },
    {
        "id": "CTR-002",
        "type": "task",
        "from_agent": "eng_director",
        "to_agent": "backend_dev",
        "priority": "high",
        "status": "executing",
        "objective": "实现用户认证模块的JWT token刷新机制",
        "payload": {"objective": "实现用户认证模块的JWT token刷新机制", "parent_task": "CTR-001"},
        "parent_id": "CTR-001",
        "created_at": _ts(1, 2),
        "updated_at": _ts(0, 1)
    },
    {
        "id": "CTR-003",
        "type": "task",
        "from_agent": "eng_director",
        "to_agent": "frontend_dev",
        "priority": "medium",
        "status": "completed",
        "objective": "优化前端组件渲染性能，减少不必要的re-render",
        "payload": {"objective": "优化前端组件渲染性能，减少不必要的re-render"},
        "parent_id": "CTR-001",
        "created_at": _ts(2, 0),
        "updated_at": _ts(0, 5)
    },
    {
        "id": "CTR-004",
        "type": "report",
        "from_agent": "frontend_dev",
        "to_agent": "eng_director",
        "priority": "medium",
        "status": "completed",
        "objective": "前端优化完成报告：React.memo和useMemo优化了12个组件",
        "payload": {"objective": "前端优化完成报告", "result": "优化了12个组件，FCP降低40%"},
        "parent_id": "CTR-003",
        "created_at": _ts(0, 5),
        "updated_at": _ts(0, 5)
    },
    {
        "id": "CTR-005",
        "type": "task",
        "from_agent": "ceo",
        "to_agent": "research_lead",
        "priority": "medium",
        "status": "executing",
        "objective": "调研当前AI Agent框架市场，分析竞品优劣势",
        "payload": {"objective": "调研当前AI Agent框架市场，分析竞品优劣势", "scope": ["AutoGPT", "CrewAI", "MetaGPT", "LangGraph"]},
        "parent_id": None,
        "created_at": _ts(0, 8),
        "updated_at": _ts(0, 3)
    },
    {
        "id": "CTR-006",
        "type": "task",
        "from_agent": "research_lead",
        "to_agent": "web_researcher",
        "priority": "medium",
        "status": "pending",
        "objective": "搜集AutoGPT和CrewAI最新版本特性和用户反馈",
        "payload": {"objective": "搜集AutoGPT和CrewAI最新版本特性和用户反馈"},
        "parent_id": "CTR-005",
        "created_at": _ts(0, 7),
        "updated_at": _ts(0, 7)
    },
    {
        "id": "CTR-007",
        "type": "task",
        "from_agent": "research_lead",
        "to_agent": "data_analyst",
        "priority": "low",
        "status": "pending",
        "objective": "整理历史调研数据，生成竞品对比矩阵",
        "payload": {"objective": "整理历史调研数据，生成竞品对比矩阵"},
        "parent_id": "CTR-005",
        "created_at": _ts(0, 6),
        "updated_at": _ts(0, 6)
    },
    {
        "id": "CTR-008",
        "type": "revision",
        "from_agent": "qa_engineer",
        "to_agent": "backend_dev",
        "priority": "high",
        "status": "pending",
        "objective": "认证模块代码质检未通过：缺少边界条件测试",
        "payload": {"objective": "认证模块代码质检未通过", "issues": ["缺少token过期边界测试", "错误码不统一"]},
        "parent_id": "CTR-002",
        "created_at": _ts(0, 1),
        "updated_at": _ts(0, 1)
    },
    {
        "id": "CTR-009",
        "type": "task",
        "from_agent": "ceo",
        "to_agent": "marketing_lead",
        "priority": "low",
        "status": "completed",
        "objective": "制定Q1市场推广计划，包括内容策略和渠道规划",
        "payload": {"objective": "制定Q1市场推广计划"},
        "parent_id": None,
        "created_at": _ts(3, 0),
        "updated_at": _ts(1, 0)
    },
    {
        "id": "CTR-010",
        "type": "task",
        "from_agent": "marketing_lead",
        "to_agent": "content_writer",
        "priority": "low",
        "status": "completed",
        "objective": "撰写产品介绍文案和首篇技术博客",
        "payload": {"objective": "撰写产品介绍文案和首篇技术博客"},
        "parent_id": "CTR-009",
        "created_at": _ts(2, 5),
        "updated_at": _ts(1, 2)
    },
    {
        "id": "CTR-011",
        "type": "escalation",
        "from_agent": "backend_dev",
        "to_agent": "eng_director",
        "priority": "high",
        "status": "pending",
        "objective": "数据库连接池配置需要架构决策，超出Worker权限",
        "payload": {"objective": "数据库连接池配置需要架构决策", "reason": "涉及基础架构变更，需要Director审批"},
        "parent_id": "CTR-002",
        "created_at": _ts(0, 0),
        "updated_at": _ts(0, 0)
    },
    {
        "id": "CTR-012",
        "type": "report",
        "from_agent": "eng_director",
        "to_agent": "ceo",
        "priority": "medium",
        "status": "completed",
        "objective": "工程部周报：API重构进度60%，前端优化已完成",
        "payload": {"objective": "工程部周报", "progress": "60%", "blockers": ["数据库连接池配置待定"]},
        "parent_id": None,
        "created_at": _ts(0, 4),
        "updated_at": _ts(0, 4)
    }
]


def generate_token_history(days: int = 7):
    """Generate mock token consumption data for the past N days."""
    data = []
    agents = list(MOCK_AGENTS.keys())
    for day_offset in range(days, -1, -1):
        date = (datetime.now(UTC) - timedelta(days=day_offset)).strftime("%Y-%m-%d")
        for agent_id in agents:
            agent = MOCK_AGENTS[agent_id]
            # Higher-level agents use more tokens
            base = {"c-suite": 15000, "director": 8000, "manager": 6000, "worker": 3000}
            base_tokens = base.get(agent["level"], 3000)
            noise = random.randint(-base_tokens // 3, base_tokens // 3)
            total = max(500, base_tokens + noise)
            input_t = int(total * 0.6)
            output_t = total - input_t

            cost_map = {
                "claude-opus-4-20250514": (0.015, 0.075),
                "claude-sonnet-4-20250514": (0.003, 0.015),
                "claude-haiku-3-5-20241022": (0.001, 0.005),
            }
            rates = cost_map.get(agent["model"], (0.001, 0.005))
            cost = (input_t / 1000 * rates[0]) + (output_t / 1000 * rates[1])

            calls = random.randint(2, 12)
            data.append({
                "day": date,
                "agent_name": agent_id,
                "model": agent["model"],
                "input_tokens": input_t,
                "output_tokens": output_t,
                "total": total,
                "cost": round(cost, 4),
                "calls": calls
            })
    return data


def generate_performance_data():
    """Generate mock performance data for each agent."""
    data = []
    for agent_id, agent in MOCK_AGENTS.items():
        total = random.randint(10, 50)
        completed = int(total * random.uniform(0.7, 0.98))
        reworked = random.randint(0, max(1, total - completed))
        qa_passed = int(completed * random.uniform(0.75, 1.0))
        avg_time_minutes = random.uniform(2, 30)

        completion_rate = completed / total if total > 0 else 0
        rework_rate = reworked / completed if completed > 0 else 0
        qa_rate = qa_passed / completed if completed > 0 else 0
        score = int(completion_rate * 40 + (1 - rework_rate) * 30 + qa_rate * 30)

        data.append({
            "agent_name": agent_id,
            "display_name": agent["display_name"],
            "department": agent["department"],
            "model": agent["model_short"],
            "total_tasks": total,
            "completed": completed,
            "reworked": reworked,
            "qa_passed": qa_passed,
            "completion_rate": round(completion_rate, 3),
            "rework_rate": round(rework_rate, 3),
            "qa_rate": round(qa_rate, 3),
            "avg_time_minutes": round(avg_time_minutes, 1),
            "score": min(100, max(0, score))
        })
    return data


def generate_cost_optimization():
    """Generate mock cost optimization suggestions."""
    return [
        {
            "agent": "web_researcher",
            "current_model": "Haiku",
            "current_cost_per_1k": 0.001,
            "suggested_model": "Qwen3-8B (Ollama)",
            "suggested_cost_per_1k": 0.0,
            "reason": "该岗位只需要执行网络搜索和信息整理，本地模型即可胜任",
            "estimated_monthly_savings": 2.50
        },
        {
            "agent": "content_writer",
            "current_model": "Haiku",
            "current_cost_per_1k": 0.001,
            "suggested_model": "Qwen3-8B (Ollama)",
            "suggested_cost_per_1k": 0.0,
            "reason": "文案创作任务可以用本地模型完成，质量可接受",
            "estimated_monthly_savings": 1.80
        },
        {
            "agent": "hr_lead",
            "current_model": "Sonnet",
            "current_cost_per_1k": 0.003,
            "suggested_model": "Haiku",
            "suggested_cost_per_1k": 0.001,
            "reason": "HR流程较为标准化，不需要高推理能力",
            "estimated_monthly_savings": 4.20
        }
    ]


# --- Tools ---

MOCK_TOOLS = [
    {"name": "web_search", "icon": "search", "description": "网络搜索工具，支持多搜索引擎", "agents": ["web_researcher", "content_writer"]},
    {"name": "code_exec", "icon": "terminal", "description": "代码执行环境，支持Python/JS/Shell", "agents": ["backend_dev", "data_analyst"]},
    {"name": "canvas", "icon": "edit", "description": "文档编辑画布，支持Markdown/Rich Text", "agents": ["data_analyst", "content_writer"]},
    {"name": "file_manager", "icon": "folder", "description": "文件管理工具，支持读写和目录操作", "agents": ["backend_dev", "frontend_dev"]},
    {"name": "create_agent", "icon": "user-plus", "description": "创建新Agent，生成完整四件套文件", "agents": ["ceo", "hr_lead"]},
    {"name": "create_department", "icon": "building", "description": "创建新部门，更新组织架构", "agents": ["ceo", "hr_lead"]},
    {"name": "remove_agent", "icon": "user-minus", "description": "删除Agent，归档其Memory", "agents": ["hr_lead"]},
    {"name": "remove_department", "icon": "trash", "description": "删除部门，需要先转移或删除所有成员", "agents": ["hr_lead"]},
    {"name": "update_chain", "icon": "link", "description": "更新指挥链关系", "agents": ["ceo", "hr_lead"]},
    {"name": "compress_memory", "icon": "archive", "description": "压缩Agent的Memory文件，保留关键信息", "agents": ["hr_lead"]},
]

MOCK_MODELS = [
    {"name": "Claude Opus", "id": "claude-opus-4-20250514", "provider": "anthropic", "reasoning": "极强", "speed": "慢", "cost_input": 0.015, "cost_output": 0.075, "agents": ["ceo"]},
    {"name": "Claude Sonnet", "id": "claude-sonnet-4-20250514", "provider": "anthropic", "reasoning": "强", "speed": "中", "cost_input": 0.003, "cost_output": 0.015, "agents": ["hr_lead", "eng_director", "research_lead", "marketing_lead"]},
    {"name": "Claude Haiku", "id": "claude-haiku-3-5-20241022", "provider": "anthropic", "reasoning": "中", "speed": "快", "cost_input": 0.001, "cost_output": 0.005, "agents": ["backend_dev", "frontend_dev", "qa_engineer", "web_researcher", "data_analyst", "content_writer"]},
    {"name": "Qwen3 8B", "id": "qwen3-8b", "provider": "ollama", "reasoning": "中", "speed": "中", "cost_input": 0.0, "cost_output": 0.0, "agents": []},
    {"name": "DeepSeek V3", "id": "deepseek-chat", "provider": "deepseek", "reasoning": "强", "speed": "中", "cost_input": 0.0005, "cost_output": 0.002, "agents": []},
]


def get_org_tree():
    """Build tree structure for frontend rendering."""
    nodes = []
    links = []
    for agent_id, agent in MOCK_AGENTS.items():
        nodes.append({
            "id": agent_id,
            "name": agent["display_name"],
            "level": agent["level"],
            "department": agent["department"],
            "model": agent["model_short"],
            "status": agent["status"]
        })
        if agent["reports_to"]:
            links.append({
                "source": agent["reports_to"],
                "target": agent_id
            })
    return {"nodes": nodes, "links": links}
