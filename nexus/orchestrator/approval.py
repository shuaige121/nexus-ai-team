"""
NEXUS 审批引擎 — 强规则

规则：
1. 只有两个动作：APPROVED / REJECTED，没有其他状态
2. REJECTED 必须有 notes（备注/原因），不能为空
3. CC 列表的人只收通知，不能操作
4. 审批人可以是 AI 或 human
5. 每个合同只能有一个 pending 审批，不能重复发起
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApproverType(str, Enum):
    AI = "ai"
    HUMAN = "human"


@dataclass
class ApprovalRequest:
    """一个审批请求"""
    request_id: str
    contract_id: str
    title: str                          # 审批标题（简短描述）
    summary: str                        # 审批内容摘要
    approver_type: ApproverType         # ai 或 human
    approver_id: str                    # human: telegram user ID / ai: "ai_ceo"
    cc_list: list[str] = field(default_factory=list)  # CC 的 telegram user IDs
    status: ApprovalStatus = ApprovalStatus.PENDING
    rejection_notes: str = ""           # REJECTED 时必填
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    resolved_by: str = ""               # 实际操作人

    def approve(self, by: str) -> None:
        """批准。一键，没有废话。"""
        if self.status != ApprovalStatus.PENDING:
            raise ValueError(
                f"审批 {self.request_id} 已经是 {self.status.value}，不能重复操作"
            )
        self.status = ApprovalStatus.APPROVED
        self.resolved_at = time.time()
        self.resolved_by = by
        logger.info("[APPROVAL] APPROVED: %s by %s", self.request_id, by)

    def reject(self, by: str, notes: str) -> None:
        """不批准。必须写备注。"""
        if self.status != ApprovalStatus.PENDING:
            raise ValueError(
                f"审批 {self.request_id} 已经是 {self.status.value}，不能重复操作"
            )
        notes = notes.strip()
        if not notes:
            raise ValueError("REJECTED 必须写备注（rejection_notes 不能为空）")
        self.status = ApprovalStatus.REJECTED
        self.rejection_notes = notes
        self.resolved_at = time.time()
        self.resolved_by = by
        logger.info(
            "[APPROVAL] REJECTED: %s by %s, notes: %s",
            self.request_id,
            by,
            notes[:100],
        )

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "contract_id": self.contract_id,
            "title": self.title,
            "summary": self.summary,
            "approver_type": self.approver_type.value,
            "approver_id": self.approver_id,
            "cc_list": self.cc_list,
            "status": self.status.value,
            "rejection_notes": self.rejection_notes,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "resolved_by": self.resolved_by,
        }


class ApprovalStore:
    """审批请求存储（MVP 用内存，后续可换 DB）"""

    def __init__(self) -> None:
        self._store: dict[str, ApprovalRequest] = {}  # request_id -> ApprovalRequest
        self._by_contract: dict[str, str] = {}         # contract_id -> request_id (最新的)

    def create(
        self,
        contract_id: str,
        title: str,
        summary: str,
        approver_type: ApproverType,
        approver_id: str,
        cc_list: list[str] | None = None,
    ) -> ApprovalRequest:
        """创建审批请求。每个合同同时只能有一个 pending。"""
        # 检查是否已有 pending
        existing_id = self._by_contract.get(contract_id)
        if existing_id:
            existing = self._store.get(existing_id)
            if existing and existing.status == ApprovalStatus.PENDING:
                raise ValueError(
                    f"合同 {contract_id} 已有 pending 审批 {existing_id}，不能重复发起"
                )

        request = ApprovalRequest(
            request_id=f"APR-{uuid.uuid4().hex[:8].upper()}",
            contract_id=contract_id,
            title=title,
            summary=summary,
            approver_type=approver_type,
            approver_id=approver_id,
            cc_list=cc_list or [],
        )
        self._store[request.request_id] = request
        self._by_contract[contract_id] = request.request_id
        logger.info(
            "[APPROVAL_STORE] created: %s for contract %s",
            request.request_id,
            contract_id,
        )
        return request

    def get(self, request_id: str) -> ApprovalRequest | None:
        return self._store.get(request_id)

    def get_by_contract(self, contract_id: str) -> ApprovalRequest | None:
        rid = self._by_contract.get(contract_id)
        return self._store.get(rid) if rid else None

    def get_pending(self) -> list[ApprovalRequest]:
        return [r for r in self._store.values() if r.status == ApprovalStatus.PENDING]


# 全局单例
approval_store = ApprovalStore()
