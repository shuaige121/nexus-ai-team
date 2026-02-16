"""Prompt builder — assembles system prompt with context isolation per level.

CEO: jd + resume + memory + org summary (departments & managers only)
Manager: jd + resume + memory + worker roster (skills, tools, strengths/weaknesses)
Worker: jd + resume + memory + tool definitions
QA Worker: same as Worker
"""

from __future__ import annotations

import logging

import yaml

from agentoffice.config import (
    AGENTS_DIR,
    JD_FILE,
    LEVEL_CEO,
    LEVEL_MANAGER,
    LEVEL_QA_WORKER,
    LEVEL_WORKER,
    MEMORY_FILE,
    RESUME_FILE,
)
from agentoffice.engine.choice_handlers import format_choices_prompt, get_choices_for_agent
from agentoffice.tools.org_utils import load_org

logger = logging.getLogger(__name__)


def build_prompt(
    agent_id: str,
    level: str,
    contract: dict,
) -> tuple[str, str]:
    """Build (system_prompt, user_message) for an agent activation.

    Applies context isolation based on agent level.

    Returns:
        Tuple of (system_prompt, user_message).
    """
    # Load agent's own files
    jd = _read_agent_file(agent_id, JD_FILE)
    resume = _read_agent_file(agent_id, RESUME_FILE)
    memory = _read_agent_file(agent_id, MEMORY_FILE)

    # Build level-specific context
    if level == LEVEL_CEO:
        context = _build_ceo_context(agent_id)
    elif level == LEVEL_MANAGER:
        context = _build_manager_context(agent_id)
    elif level in (LEVEL_WORKER, LEVEL_QA_WORKER):
        context = _build_worker_context(agent_id)
    else:
        context = ""

    # Get choices for this agent
    contract_type = contract.get("type")
    choices = get_choices_for_agent(agent_id, level, contract_type)
    choices_prompt = format_choices_prompt(choices, agent_id)

    # Assemble system prompt
    system_prompt = _assemble_system_prompt(jd, resume, memory, context, level)

    # Assemble user message (contract + response format + choices)
    user_message = _assemble_user_message(contract, choices_prompt)

    return system_prompt, user_message


def _read_agent_file(agent_id: str, filename: str) -> str:
    """Read an agent's configuration file."""
    file_path = AGENTS_DIR / agent_id / filename
    if file_path.exists():
        return file_path.read_text(encoding="utf-8")
    logger.warning("Agent file not found: %s", file_path)
    return ""


def _build_ceo_context(agent_id: str) -> str:
    """CEO context: org summary with departments and their managers."""
    org = load_org()
    departments = org.get("departments", [])
    chain = org.get("chain_of_command", {})

    lines = ["# 公司组织架构概览\n"]
    for dept in departments:
        dept_name = dept.get("name", dept["id"])
        positions = dept.get("positions", [])
        head = positions[0] if positions else "（空缺）"

        # Get head's title from jd.md if available
        head_title = _get_agent_title(head) if head != "（空缺）" else ""
        head_desc = f"{head}" + (f" ({head_title})" if head_title else "")

        # Get what the department head can command
        head_chain = chain.get(head, {})
        subordinates = head_chain.get("can_command", [])
        sub_desc = f"，管理: {', '.join(subordinates)}" if subordinates else ""

        lines.append(f"- **{dept_name}** ({dept['id']}): 负责人 {head_desc}{sub_desc}")

    lines.append(f"\n共 {len(departments)} 个部门。")
    return "\n".join(lines)


def _build_manager_context(agent_id: str) -> str:
    """Manager context: worker roster with skills and capabilities."""
    org = load_org()
    chain = org.get("chain_of_command", {})
    agent_chain = chain.get(agent_id, {})
    subordinates = agent_chain.get("can_command", [])

    if not subordinates:
        return "# 团队成员\n\n当前没有下属员工。需要通过CEO请求HR招聘。"

    lines = ["# 团队成员\n"]
    for sub_id in subordinates:
        sub_jd = _read_agent_file(sub_id, JD_FILE)
        sub_resume = _read_agent_file(sub_id, RESUME_FILE)

        title = _extract_field(sub_jd, "岗位名称") or sub_id
        level = _extract_field(sub_jd, "级别") or "unknown"

        # Extract key info from resume
        strengths = _extract_section(sub_resume, "优势")
        weaknesses = _extract_section(sub_resume, "短板")

        # Extract tools from JD
        tools = _extract_section(sub_jd, "可用工具")

        lines.append(f"## {sub_id} — {title} (级别: {level})")
        if strengths:
            lines.append(f"**优势**: {strengths}")
        if weaknesses:
            lines.append(f"**短板**: {weaknesses}")
        if tools and tools.strip() != "无":
            lines.append(f"**可用工具**: {tools}")
        lines.append("")

    return "\n".join(lines)


def _build_worker_context(agent_id: str) -> str:
    """Worker context: available tool definitions."""
    jd = _read_agent_file(agent_id, JD_FILE)
    tools_section = _extract_section(jd, "可用工具")

    if not tools_section or tools_section.strip() == "无":
        return "# 可用工具\n\n无可用工具。按指令执行文本类任务。"

    return f"# 可用工具\n\n{tools_section}"


def _assemble_system_prompt(
    jd: str, resume: str, memory: str, context: str, level: str,
) -> str:
    """Combine all pieces into the system prompt."""
    parts = [
        "你是NEXUS Corp的一名员工，严格按照你的岗位说明和工作记忆行事。",
        "",
        "# 你的岗位说明",
        jd,
        "",
        "# 你的个人简历",
        resume,
        "",
        "# 你的工作记忆",
        memory,
    ]

    if context:
        parts.extend(["", context])

    parts.extend([
        "",
        "# 回复格式要求",
        "",
        "你必须严格以JSON格式回复，包含以下字段：",
        '- "action": { "summary": "完成了什么（一句话）", "output": "具体产出内容" }',
        '- "memory_update": "更新后的工作记忆（纯文本，2000字以内，'
        '包含待办/上下文/备忘三个section）"',
        '- "choice": "从选择题中选的选项ID（必填）"',
        '- "choice_payload": { "to": "目标agent（如需）", "summary": "摘要", ... }',
    ])

    if level in (LEVEL_MANAGER,):
        parts.append(
            '- "tool_calls": [{ "tool": "工具名", "params": { ... } }]  '
            "（仅HR Lead等有工具的角色需要）"
        )

    parts.extend([
        "",
        "注意：choice字段是必填的。你必须从下面的选择题中选择一个选项。",
    ])

    return "\n".join(parts)


def _assemble_user_message(contract: dict, choices_prompt: str) -> str:
    """Build the user message from contract + choices."""
    # Format contract as readable text
    contract_text = yaml.dump(
        contract, default_flow_style=False, allow_unicode=True, sort_keys=False,
    )

    parts = [
        "# 当前Contract",
        "",
        "```yaml",
        contract_text.strip(),
        "```",
        "",
        choices_prompt,
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_agent_title(agent_id: str) -> str:
    """Extract title from an agent's jd.md."""
    jd = _read_agent_file(agent_id, JD_FILE)
    return _extract_field(jd, "岗位名称") or ""


def _extract_field(markdown: str, field_name: str) -> str | None:
    """Extract a field value from markdown like '- **岗位名称**: value'."""
    for line in markdown.split("\n"):
        if f"**{field_name}**" in line:
            parts = line.split(":", 1)
            if len(parts) == 2:
                return parts[1].strip()
    return None


def _extract_section(markdown: str, section_name: str) -> str | None:
    """Extract content under a ## section header."""
    lines = markdown.split("\n")
    capturing = False
    captured: list[str] = []

    for line in lines:
        if line.startswith("## ") and section_name in line:
            capturing = True
            continue
        if capturing:
            if line.startswith("## "):
                break
            captured.append(line)

    if captured:
        return "\n".join(captured).strip()
    return None
