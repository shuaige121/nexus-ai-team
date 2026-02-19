"""
Worker 工具集

Worker 负责实际代码编写、测试运行和提交。
只能在 task branch 上操作，禁止推送到 main 分支。
"""
from __future__ import annotations

import logging

from nexus.orchestrator.permissions import check_tool_permission
from nexus.orchestrator.tools._llm_helper import llm_call

logger = logging.getLogger(__name__)

_WRITE_CODE_SYSTEM = (
    "You are a senior Python developer. Write clean, well-structured, "
    "and tested code. Include docstrings and type hints. "
    "Return only the code — no prose before or after."
)


def write_code(role: str, instruction: str, attempt: int = 1) -> str:
    """
    根据 Manager 指令编写代码（调用 LLM 生成真实代码）。

    Args:
        role: 调用方角色（必须是 "worker"）
        instruction: Manager 下发的执行指令
        attempt: 当前是第几次尝试（用于重试场景）

    Returns:
        LLM 生成的代码字符串

    Raises:
        PermissionError: 非 worker 角色调用时抛出
    """
    check_tool_permission(role, "write_code")
    logger.info(
        "[WORKER_TOOL] write_code: attempt=%d, instr=%s...", attempt, instruction[:50]
    )

    user_prompt = (
        f"Attempt #{attempt}.\n\n"
        f"Task instruction:\n{instruction}"
    )
    return llm_call(role, _WRITE_CODE_SYSTEM, user_prompt)


def run_tests(role: str, code: str) -> dict:
    """
    在 Worker 提交前运行本地测试。

    Args:
        role: 调用方角色
        code: 待测试的代码字符串

    Returns:
        测试结果字典，包含通过/失败数量和覆盖率
    """
    check_tool_permission(role, "run_tests")
    logger.info("[WORKER_TOOL] run_tests: code_len=%d", len(code))

    # TODO: integrate with subprocess for real test execution
    # (e.g., write code to a temp file, run `pytest --tb=short -q`,
    # capture stdout/stderr, parse results)
    return {
        "passed": 5,
        "failed": 0,
        "coverage": "87%",
        "duration": "0.42s",
        "status": "GREEN",
    }


def git_commit(role: str, code: str, message: str, branch: str = "feature/task") -> str:
    """
    提交代码到任务专属 branch（不允许直接提交到 main）。

    Args:
        role: 调用方角色
        code: 代码内容
        message: commit message
        branch: 目标分支（默认 feature/task，禁止 main/master）

    Returns:
        模拟的 commit hash 字符串

    Raises:
        PermissionError: 尝试提交到 main/master 时抛出
        ValueError: 分支名不合法时抛出
    """
    check_tool_permission(role, "git_commit")

    # 强制执行 NO_MAIN_BRANCH 约束
    forbidden_branches = {"main", "master", "production", "prod"}
    if branch.lower() in forbidden_branches:
        from nexus.orchestrator.permissions import PermissionError as NexusPermError
        raise NexusPermError(
            role,
            "git_commit",
            f"Worker 被禁止提交到受保护分支 {branch!r}，"
            f"请使用 feature/ 或 task/ 前缀的分支",
        )

    logger.info("[WORKER_TOOL] git_commit: branch=%s, msg=%s", branch, message[:50])

    # TODO: integrate with subprocess for real git operations
    # (e.g., git add, git commit -m, git push origin <branch>)
    fake_hash = f"abc{hash(code + message) % 100000:05x}"
    return f"[{branch}] {fake_hash} — {message}"


def read_file(role: str, file_path: str) -> str:
    """
    读取任务 branch 范围内的文件。

    Args:
        role: 调用方角色
        file_path: 文件路径（限制在 task_branch_only/ 范围）

    Returns:
        文件内容字符串
    """
    check_tool_permission(role, "read_file")
    logger.info("[WORKER_TOOL] read_file: path=%s", file_path)

    # TODO: integrate with real filesystem access (os.path / pathlib)
    # with sandboxed path validation to prevent directory traversal
    return f"[FILE CONTENT] {file_path}\n# 模拟文件内容\ndata = {{'key': 'value'}}\n"
