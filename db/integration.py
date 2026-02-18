"""Integration layer for database logging in gateway and pipeline."""

from __future__ import annotations

import logging
from typing import Any

from db.client import AgentMetric, AuditLog, DatabaseClient, SessionLog, WorkOrderLog, get_db_client

logger = logging.getLogger(__name__)


class LoggingMixin:
    """Mixin to add database logging capabilities to existing classes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._log_client: DatabaseClient | None = None
        self._logging_enabled = True

    def _get_log_client(self) -> DatabaseClient | None:
        """Get database logging client (lazily initialized)."""
        if not self._logging_enabled:
            return None

        if self._log_client is None:
            try:
                self._log_client = get_db_client()
            except Exception as exc:
                logger.warning(f"Failed to initialize logging client: {exc}")
                self._logging_enabled = False
                return None

        return self._log_client

    def _log_work_order_safe(self, work_order: WorkOrderLog) -> None:
        """Safely log work order (no-op if logging unavailable)."""
        client = self._get_log_client()
        if client:
            try:
                client.log_work_order(work_order)
            except Exception as exc:
                logger.warning(f"Failed to log work order: {exc}")

    def _log_agent_metric_safe(self, metric: AgentMetric) -> None:
        """Safely log agent metric (no-op if logging unavailable)."""
        client = self._get_log_client()
        if client:
            try:
                client.log_agent_metric(metric)
            except Exception as exc:
                logger.warning(f"Failed to log agent metric: {exc}")

    def _log_audit_safe(self, audit: AuditLog) -> None:
        """Safely log audit entry (no-op if logging unavailable)."""
        client = self._get_log_client()
        if client:
            try:
                client.log_audit(audit)
            except Exception as exc:
                logger.warning(f"Failed to log audit entry: {exc}")

    def _log_session_safe(self, session: SessionLog) -> None:
        """Safely log session (no-op if logging unavailable)."""
        client = self._get_log_client()
        if client:
            try:
                client.log_session(session)
            except Exception as exc:
                logger.warning(f"Failed to log session: {exc}")


def log_work_order_from_dict(wo_data: dict[str, Any]) -> None:
    """Helper to log work order from dictionary (for easy integration)."""
    try:
        work_order = WorkOrderLog(
            id=wo_data["id"],
            intent=wo_data["intent"],
            difficulty=wo_data["difficulty"],
            owner=wo_data["owner"],
            compressed_context=wo_data.get("compressed_context", ""),
            relevant_files=wo_data.get("relevant_files", []),
            qa_requirements=wo_data.get("qa_requirements", ""),
            status=wo_data.get("status", "queued"),
            retry_count=wo_data.get("retry_count", 0),
            deadline=wo_data.get("deadline"),
            completed_at=wo_data.get("completed_at"),
            last_error=wo_data.get("last_error"),
        )
        client = get_db_client()
        client.log_work_order(work_order)
    except Exception as exc:
        logger.warning(f"Failed to log work order from dict: {exc}")


def log_agent_execution(
    work_order_id: str | None,
    session_id: str | None,
    agent_name: str,
    role: str,
    model: str,
    provider: str | None,
    success: bool,
    latency_ms: int,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost_usd: float = 0.0,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Helper to log agent execution metrics."""
    try:
        metric = AgentMetric(
            work_order_id=work_order_id,
            session_id=session_id,
            agent_name=agent_name,
            role=role,
            model=model,
            provider=provider,
            success=success,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            metadata=metadata,
        )
        client = get_db_client()
        client.log_agent_metric(metric)
    except Exception as exc:
        logger.warning(f"Failed to log agent execution: {exc}")


def log_audit_event(
    actor: str,
    action: str,
    status: str,
    work_order_id: str | None = None,
    session_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Helper to log audit event."""
    try:
        audit = AuditLog(
            work_order_id=work_order_id,
            session_id=session_id,
            actor=actor,
            action=action,
            status=status,
            details=details,
        )
        client = get_db_client()
        client.log_audit(audit)
    except Exception as exc:
        logger.warning(f"Failed to log audit event: {exc}")


def log_session_activity(
    session_id: str,
    user_id: str,
    channel: str,
    status: str = "active",
    title: str | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    """Helper to log session activity."""
    try:
        session = SessionLog(
            id=session_id,
            user_id=user_id,
            channel=channel,
            status=status,
            title=title,
            context=context,
        )
        client = get_db_client()
        client.log_session(session)
    except Exception as exc:
        logger.warning(f"Failed to log session activity: {exc}")
