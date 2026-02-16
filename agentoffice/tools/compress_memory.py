"""Tool: Compress memory.md to stay within the character limit."""

from __future__ import annotations

import logging

from agentoffice.config import AGENTS_DIR, MEMORY_CHAR_LIMIT

logger = logging.getLogger(__name__)


def compress_memory(agent_id: str, limit: int = MEMORY_CHAR_LIMIT) -> dict:
    """Force-compress memory.md to stay within the character limit.

    Strategy: keep the structure headers and truncate content sections
    proportionally, prioritizing TODO list and recent context over
    long-term notes.

    Returns dict with status and details.
    """
    memory_path = AGENTS_DIR / agent_id / "memory.md"

    if not memory_path.exists():
        msg = f"Memory file not found for agent '{agent_id}'"
        logger.warning(msg)
        return {"status": "error", "message": msg}

    content = memory_path.read_text(encoding="utf-8")
    original_len = len(content)

    if original_len <= limit:
        return {
            "status": "ok",
            "agent_id": agent_id,
            "original_len": original_len,
            "compressed_len": original_len,
            "action": "no_compression_needed",
        }

    # Parse sections
    sections = _parse_memory_sections(content)

    # Allocation: TODO 40%, Recent Context 40%, Long-term Notes 20%
    header_budget = 100  # rough budget for section headers
    available = limit - header_budget
    allocations = {
        "待办清单": int(available * 0.4),
        "近期上下文": int(available * 0.4),
        "长期备忘": int(available * 0.2),
    }

    # Truncate each section
    compressed_sections = {}
    for section_name, section_content in sections.items():
        budget = allocations.get(section_name, int(available * 0.1))
        if len(section_content) > budget:
            truncated = section_content[:budget].rsplit("\n", 1)[0]
            compressed_sections[section_name] = truncated + "\n…（已压缩）"
        else:
            compressed_sections[section_name] = section_content

    # Rebuild memory
    compressed = "# 工作记忆 (Working Memory)\n\n"
    for section_name in ["待办清单", "近期上下文", "长期备忘"]:
        body = compressed_sections.get(section_name, "（无内容）")
        compressed += f"## {section_name}\n\n{body}\n\n"

    # Final safety truncation
    if len(compressed) > limit:
        compressed = compressed[:limit - 20] + "\n\n…（已截断）"

    memory_path.write_text(compressed, encoding="utf-8")
    compressed_len = len(compressed)
    logger.info(
        "Compressed memory for '%s': %d → %d chars",
        agent_id, original_len, compressed_len,
    )
    return {
        "status": "ok",
        "agent_id": agent_id,
        "original_len": original_len,
        "compressed_len": compressed_len,
        "action": "compressed",
    }


def _parse_memory_sections(content: str) -> dict[str, str]:
    """Parse memory.md into sections by ## headers."""
    sections: dict[str, str] = {}
    current_section = ""
    current_body: list[str] = []

    for line in content.split("\n"):
        if line.startswith("## "):
            if current_section:
                sections[current_section] = "\n".join(current_body).strip()
            current_section = line[3:].strip()
            current_body = []
        elif current_section:
            current_body.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_body).strip()

    return sections
