"""
NEXUS 权限矩阵 — 硬编码角色能力与约束

每个角色的工具权限、通信权限和文件访问范围在此处集中定义。
所有节点在调用工具前必须通过 check_permission() 校验。
"""
from __future__ import annotations

# --------------------------------------------------------------------------
# 权限矩阵：角色 → 能力集合
# --------------------------------------------------------------------------
ROLE_PERMISSIONS: dict[str, dict] = {
    "ceo": {
        "tools": ["generate_contract", "send_mail", "write_note", "read_reports"],
        # CEO 只能联系各部门经理，不能直接联系 worker 或 qa
        "allowed_contacts": ["it_manager", "hr_manager", "product_manager", "manager"],
        "file_scope": ["company/", "docs/"],
        "constraints": ["NO_CLI", "NO_CODE", "NO_DIRECT_EXECUTION"],
    },
    "manager": {
        "tools": ["break_down_task", "assign_worker", "review_report", "send_mail", "escalate"],
        # Manager 可以联系 CEO（上报）以及本部门 worker/qa
        "allowed_contacts": ["ceo", "worker", "qa", "own_department_workers"],
        "file_scope": ["department_specific/"],
        "constraints": ["NO_CROSS_DEPARTMENT", "NO_DIRECT_CODE_EXECUTION"],
    },
    "worker": {
        "tools": ["write_code", "run_tests", "git_commit", "read_file", "send_mail"],
        # Worker 只能联系自己的 manager，禁止越级
        "allowed_contacts": ["manager", "own_manager"],
        "file_scope": ["task_branch_only/"],
        "constraints": ["NO_MAIN_BRANCH", "NO_CROSS_DEPARTMENT", "NO_UPWARD_COMMAND"],
    },
    "qa": {
        "tools": ["review_code", "run_linter", "run_tests", "write_verdict", "send_mail"],
        # QA 只能联系自己的 manager，只读权限
        "allowed_contacts": ["manager", "own_manager"],
        "file_scope": ["read_only_all/"],
        "constraints": ["NO_CODE_MODIFICATION", "NO_DIRECT_DEPLOY"],
    },
}

# --------------------------------------------------------------------------
# Chain of Command 规则：合法的通信路径
# 格式：(from_role, to_role) → True 表示允许
# --------------------------------------------------------------------------
ALLOWED_MAIL_ROUTES: set[tuple[str, str]] = {
    ("ceo", "manager"),
    ("manager", "ceo"),    # 上报路径
    ("manager", "worker"),
    ("manager", "qa"),
    ("worker", "manager"),  # worker 只能回报给 manager
    ("qa", "manager"),      # qa 只能回报给 manager
}


class PermissionError(Exception):
    """权限校验失败时抛出此异常。"""

    def __init__(self, role: str, action: str, detail: str = "") -> None:
        self.role = role
        self.action = action
        msg = f"[PERMISSION DENIED] role={role!r} action={action!r}"
        if detail:
            msg += f" — {detail}"
        super().__init__(msg)


def check_tool_permission(role: str, tool_name: str) -> None:
    """
    校验某角色是否有权调用指定工具。

    Args:
        role: 调用方角色，例如 "ceo" / "worker"
        tool_name: 工具名称，例如 "write_code"

    Raises:
        PermissionError: 如果该角色无权调用该工具
    """
    perms = ROLE_PERMISSIONS.get(role)
    if perms is None:
        raise PermissionError(role, tool_name, f"未知角色 {role!r}")
    if tool_name not in perms["tools"]:
        raise PermissionError(
            role,
            tool_name,
            f"工具 {tool_name!r} 不在角色 {role!r} 的允许列表 {perms['tools']} 中",
        )


def check_mail_permission(from_role: str, to_role: str) -> str | None:
    """
    校验邮件路由是否符合 Chain of Command。

    返回拒绝原因字符串（违规时），或 None（通过时）。
    调用方可根据返回值决定是否记录审计日志或抛出异常。

    Args:
        from_role: 发件人角色
        to_role: 收件人角色

    Returns:
        None 表示校验通过；非 None 字符串表示被拒绝的具体原因
    """
    if (from_role, to_role) not in ALLOWED_MAIL_ROUTES:
        return (
            f"不允许的通信路径 {from_role!r} → {to_role!r}，"
            f"合法路径：{sorted(ALLOWED_MAIL_ROUTES)}"
        )
    return None


def check_constraint(role: str, constraint: str) -> bool:
    """
    查询某角色是否有某项约束。

    Args:
        role: 角色名
        constraint: 约束名，例如 "NO_CLI"

    Returns:
        True 表示该角色存在此约束
    """
    perms = ROLE_PERMISSIONS.get(role, {})
    return constraint in perms.get("constraints", [])


def get_role_tools(role: str) -> list[str]:
    """返回某角色的全部允许工具列表。"""
    return ROLE_PERMISSIONS.get(role, {}).get("tools", [])
