"""Tool: Create a new agent with all configuration files."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from agentoffice.config import AGENTS_DIR, MEMORY_CHAR_LIMIT
from agentoffice.tools.org_utils import load_org, save_org

logger = logging.getLogger(__name__)

_DEFAULT_WORK_HABITS = "- 严格按照指令执行任务\n- 完成后及时汇报"


def create_agent(
    agent_id: str,
    department: str,
    level: str,
    title: str,
    reports_to: str,
    manages: list[str] | None = None,
    responsibilities: list[str] | None = None,
    boundaries: list[str] | None = None,
    authority: list[str] | None = None,
    tools: list[str] | None = None,
    hiring_requirements: str = "",
    employee_name: str = "",
    personality: str = "",
    work_habits: str = "",
    strengths: list[str] | None = None,
    weaknesses: list[str] | None = None,
    collaboration_notes: str = "",
    model: str = "claude-haiku-4-5-20251001",
    provider: str = "anthropic",
    endpoint: str = "https://api.anthropic.com/v1/messages",
    api_key_env: str = "ANTHROPIC_API_KEY",
    species: str = "Claude Haiku",
    temperature: float = 0.2,
    max_tokens: int = 4096,
    input_cost: float = 0.001,
    output_cost: float = 0.005,
    reasoning: str = "basic",
    speed: str = "fast",
    tool_use: bool = True,
    languages: list[str] | None = None,
) -> dict:
    """Create a new agent: directory + jd.md + resume.md + memory.md + race.yaml + org.yaml update.

    All file operations are deterministic — zero LLM calls.

    Returns dict with status and details.
    """
    manages = manages or []
    responsibilities = responsibilities or []
    boundaries = boundaries or []
    authority = authority or []
    tools = tools or []
    strengths = strengths or []
    weaknesses = weaknesses or []
    languages = languages or ["en", "zh"]

    agent_dir = AGENTS_DIR / agent_id

    # Check if agent already exists
    if agent_dir.exists():
        msg = f"Agent '{agent_id}' already exists at {agent_dir}"
        logger.warning(msg)
        return {"status": "error", "message": msg}

    # 1. Create directory
    agent_dir.mkdir(parents=True, exist_ok=True)

    # 2. Generate jd.md
    _write_jd(agent_dir, agent_id=agent_id, department=department, level=level,
              title=title, reports_to=reports_to, manages=manages,
              responsibilities=responsibilities, boundaries=boundaries,
              authority=authority, tools=tools,
              hiring_requirements=hiring_requirements)

    # 3. Generate resume.md
    _write_resume(agent_dir, agent_id=agent_id, title=title,
                  employee_name=employee_name, personality=personality,
                  work_habits=work_habits, strengths=strengths,
                  weaknesses=weaknesses, collaboration_notes=collaboration_notes)

    # 4. Generate memory.md
    _write_memory(agent_dir, title=title, department=department)

    # 5. Generate race.yaml
    _write_race(agent_dir, species=species, provider=provider, endpoint=endpoint,
                api_key_env=api_key_env, model=model, temperature=temperature,
                max_tokens=max_tokens, input_cost=input_cost, output_cost=output_cost,
                reasoning=reasoning, speed=speed, tool_use=tool_use, languages=languages)

    # 6. Update org.yaml
    _update_org(agent_id=agent_id, department=department, level=level,
                reports_to=reports_to, manages=manages, authority=authority)

    logger.info("Created agent '%s' (%s) in department '%s'", agent_id, title, department)
    return {
        "status": "ok",
        "agent_id": agent_id,
        "title": title,
        "department": department,
        "level": level,
        "model": model,
    }


def _write_jd(agent_dir: Path, **kwargs: object) -> None:
    responsibilities_text = "\n".join(f"- {r}" for r in kwargs["responsibilities"]) or "（待定义）"
    authority_text = "\n".join(f"- {a}" for a in kwargs["authority"]) or "（无特殊权限）"
    boundaries_text = "\n".join(f"- {b}" for b in kwargs["boundaries"]) or "（无特殊约束）"
    manages_text = ", ".join(kwargs["manages"]) if kwargs["manages"] else "无"
    tools_text = "\n".join(f"- {t}" for t in kwargs["tools"]) or "无"

    content = f"""# 岗位说明书 (Job Description)

## 基本信息

- **岗位ID**: {kwargs["agent_id"]}
- **部门**: {kwargs["department"]}
- **级别**: {kwargs["level"]}
- **岗位名称**: {kwargs["title"]}
- **汇报对象**: {kwargs["reports_to"]}
- **管理范围**: {manages_text}

## 职责描述

{responsibilities_text}

## 决策权限

{authority_text}

## 边界约束

{boundaries_text}

## Contract处理规则

### 收到 task 类型
- 理解任务目标和验收标准
- 按职责范围执行或分配
- 完成后选择下一步操作

### 收到 report 类型
- 审阅下属提交的报告
- 评估是否满足验收标准
- 选择通过、打回或升级

### 收到 clarification 类型
- 回答下属的疑问
- 提供必要的补充信息

### 收到 revision 类型
- 根据反馈修改产出
- 重新提交报告

## 可用工具

{tools_text}

## 招聘要求

{kwargs["hiring_requirements"] or "（通用要求）"}
"""
    (agent_dir / "jd.md").write_text(content, encoding="utf-8")


def _write_resume(agent_dir: Path, **kwargs: object) -> None:
    strengths_text = "\n".join(f"- {s}" for s in kwargs["strengths"]) or "（待评估）"
    weaknesses_text = "\n".join(f"- {w}" for w in kwargs["weaknesses"]) or "（待评估）"

    content = f"""# 员工简历 (Resume)

## 基本信息

- **员工ID**: {kwargs["agent_id"]}
- **当前岗位**: {kwargs["title"]}
- **姓名**: {kwargs["employee_name"] or kwargs["agent_id"]}

## 性格设定

{kwargs["personality"] or "认真负责，按指令执行。"}

## 工作习惯

{kwargs["work_habits"] or _DEFAULT_WORK_HABITS}

## 优势

{strengths_text}

## 短板

{weaknesses_text}

## 协作备注

{kwargs["collaboration_notes"] or "按标准流程协作。"}
"""
    (agent_dir / "resume.md").write_text(content, encoding="utf-8")


def _write_memory(agent_dir: Path, **kwargs: object) -> None:
    content = f"""# 工作记忆 (Working Memory)

## 待办清单

（暂无待办事项）

## 近期上下文

刚入职{kwargs["department"]}部门，担任{kwargs["title"]}。等待第一个任务指令。

## 长期备忘

（暂无备忘）
"""
    assert len(content) <= MEMORY_CHAR_LIMIT, f"Initial memory exceeds {MEMORY_CHAR_LIMIT} chars"
    (agent_dir / "memory.md").write_text(content, encoding="utf-8")


def _write_race(agent_dir: Path, **kwargs: object) -> None:
    race_data = {
        "species": kwargs["species"],
        "provider": kwargs["provider"],
        "endpoint": kwargs["endpoint"],
        "api_key_env": kwargs["api_key_env"],
        "model": kwargs["model"],
        "parameters": {
            "temperature": kwargs["temperature"],
            "max_tokens": kwargs["max_tokens"],
        },
        "cost": {
            "input_per_1k": kwargs["input_cost"],
            "output_per_1k": kwargs["output_cost"],
        },
        "capabilities": {
            "reasoning": kwargs["reasoning"],
            "speed": kwargs["speed"],
            "tool_use": kwargs["tool_use"],
            "languages": kwargs["languages"],
        },
    }
    with open(agent_dir / "race.yaml", "w", encoding="utf-8") as f:
        yaml.dump(race_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _update_org(
    agent_id: str,
    department: str,
    level: str,
    reports_to: str,
    manages: list[str],
    authority: list[str],
) -> None:
    """Update org.yaml with the new agent."""
    org = load_org()

    # Add position to department
    for dept in org["departments"]:
        if dept["id"] == department:
            if agent_id not in dept.get("positions", []):
                dept.setdefault("positions", []).append(agent_id)
            break

    # Add to chain_of_command
    org["chain_of_command"][agent_id] = {
        "reports_to": reports_to,
        "can_command": manages,
        "authority": authority,
    }

    # Add to superior's can_command
    if reports_to in org["chain_of_command"]:
        superior = org["chain_of_command"][reports_to]
        if agent_id not in superior.get("can_command", []):
            superior.setdefault("can_command", []).append(agent_id)

    save_org(org)
