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

import json
import logging
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

_DB_PATH = os.path.expanduser("~/.nexus/approvals.db")


def _init_db(conn: sqlite3.Connection) -> None:
    """Create the approval_requests table if it does not exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS approval_requests (
            request_id TEXT PRIMARY KEY,
            contract_id TEXT NOT NULL,
            title TEXT,
            summary TEXT,
            approver_type TEXT,
            approver_id TEXT,
            cc_list TEXT,
            status TEXT DEFAULT 'pending',
            rejection_notes TEXT DEFAULT '',
            created_at TEXT,
            resolved_at TEXT
        )
    """)
    conn.commit()


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
    _db_conn: Optional[sqlite3.Connection] = field(default=None, repr=False, compare=False)

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
        self._persist_to_db()

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
        self._persist_to_db()

    def _persist_to_db(self) -> None:
        """Write current status/notes/resolved_at back to SQLite if a connection exists."""
        if self._db_conn is None:
            return
        try:
            self._db_conn.execute(
                """UPDATE approval_requests
                   SET status = ?, rejection_notes = ?, resolved_at = ?
                   WHERE request_id = ?""",
                (self.status.value, self.rejection_notes, self.resolved_at, self.request_id),
            )
            self._db_conn.commit()
        except Exception as exc:
            logger.error("[APPROVAL] Failed to persist %s to SQLite: %s", self.request_id, exc)

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
    """审批请求存储（SQLite 持久化 + 内存缓存）"""

    def __init__(self, db_path: str | None = None) -> None:
        self._store: dict[str, ApprovalRequest] = {}  # request_id -> ApprovalRequest
        self._by_contract: dict[str, str] = {}         # contract_id -> request_id (最新的)

        # SQLite persistence
        resolved_path = db_path or _DB_PATH
        os.makedirs(os.path.dirname(resolved_path), exist_ok=True)
        self._conn = sqlite3.connect(resolved_path, check_same_thread=False)
        _init_db(self._conn)
        self._load_from_db()

    def _load_from_db(self) -> None:
        """Load all existing approval requests from SQLite into memory."""
        cursor = self._conn.execute("SELECT * FROM approval_requests")
        columns = [desc[0] for desc in cursor.description]
        for row in cursor.fetchall():
            row_dict = dict(zip(columns, row))
            try:
                req = ApprovalRequest(
                    request_id=row_dict["request_id"],
                    contract_id=row_dict["contract_id"],
                    title=row_dict["title"] or "",
                    summary=row_dict["summary"] or "",
                    approver_type=ApproverType(row_dict["approver_type"]),
                    approver_id=row_dict["approver_id"] or "",
                    cc_list=json.loads(row_dict["cc_list"]) if row_dict["cc_list"] else [],
                    status=ApprovalStatus(row_dict["status"]),
                    rejection_notes=row_dict["rejection_notes"] or "",
                    created_at=float(row_dict["created_at"]) if row_dict["created_at"] else time.time(),
                    resolved_at=float(row_dict["resolved_at"]) if row_dict["resolved_at"] else None,
                )
                req._db_conn = self._conn
                self._store[req.request_id] = req
                self._by_contract[req.contract_id] = req.request_id
            except Exception as exc:
                logger.error("[APPROVAL_STORE] Failed to load row %s: %s", row_dict.get("request_id"), exc)

        logger.info("[APPROVAL_STORE] loaded %d requests from SQLite", len(self._store))

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
        request._db_conn = self._conn
        self._store[request.request_id] = request
        self._by_contract[contract_id] = request.request_id

        # Persist to SQLite
        try:
            self._conn.execute(
                """INSERT INTO approval_requests
                   (request_id, contract_id, title, summary, approver_type,
                    approver_id, cc_list, status, rejection_notes, created_at, resolved_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    request.request_id,
                    request.contract_id,
                    request.title,
                    request.summary,
                    request.approver_type.value,
                    request.approver_id,
                    json.dumps(request.cc_list),
                    request.status.value,
                    request.rejection_notes,
                    str(request.created_at),
                    None,
                ),
            )
            self._conn.commit()
        except Exception as exc:
            logger.error("[APPROVAL_STORE] Failed to INSERT %s: %s", request.request_id, exc)

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
