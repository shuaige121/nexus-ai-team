from __future__ import annotations

import itertools
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .config import AgentRole, Difficulty, owner_for_difficulty
from .model_router import ModelRouter

ALLOWED_DIFFICULTY: set[str] = {"trivial", "normal", "complex", "unclear"}
_ORDER_COUNTER = itertools.count(1)


@dataclass
class RouteResult:
    intent: str
    difficulty: Difficulty
    owner: AgentRole
    relevant_files: list[str]
    qa_requirements: str
    clarification_question: str | None = None
    equipment_name: str | None = None  # If request can be handled by equipment


@dataclass
class WorkOrder:
    id: str
    intent: str
    difficulty: Difficulty
    owner: AgentRole
    compressed_context: str
    relevant_files: list[str]
    qa_requirements: str
    deadline: str | None = None
    clarification_question: str | None = None
    equipment_name: str | None = None  # If request can be handled by equipment

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "intent": self.intent,
            "difficulty": self.difficulty,
            "owner": self.owner,
            "compressed_context": self.compressed_context,
            "relevant_files": self.relevant_files,
            "qa_requirements": self.qa_requirements,
            "deadline": self.deadline,
            "clarification_question": self.clarification_question,
            "equipment_name": self.equipment_name,
        }


class AdminAgent:
    """
    Admin agent:
    1) Compress incoming context to a concise work order brief.
    2) Classify request as trivial / normal / complex / unclear.
    """

    def __init__(self, router: ModelRouter | None = None, use_llm: bool = True) -> None:
        self.router = router or ModelRouter()
        self.use_llm = use_llm

    def create_work_order(
        self,
        user_message: str,
        conversation: Sequence[Mapping[str, Any]] | None = None,
        *,
        deadline: str | None = None,
    ) -> WorkOrder:
        compressed_context = self.compress_message(user_message, conversation)
        route = self.classify_request(user_message, compressed_context=compressed_context)
        return WorkOrder(
            id=self._new_work_order_id(),
            intent=route.intent,
            difficulty=route.difficulty,
            owner=route.owner,
            compressed_context=compressed_context,
            relevant_files=route.relevant_files,
            qa_requirements=route.qa_requirements,
            deadline=deadline,
            clarification_question=route.clarification_question,
            equipment_name=route.equipment_name,
        )

    def compress_message(
        self,
        user_message: str,
        conversation: Sequence[Mapping[str, Any]] | None = None,
        *,
        max_chars: int = 4000,
    ) -> str:
        context = self._build_context_block(user_message, conversation)
        if not self.use_llm:
            return self._fallback_compress(context, max_chars=max_chars)

        prompt = (
            "You are the NEXUS Admin agent.\n"
            "Compress the request into a compact work brief under ~1000 tokens.\n"
            "Keep: objective, constraints, expected outputs, and file references.\n"
            "Do not add facts not present in the request."
        )
        try:
            response = self.router.chat(
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": context},
                ],
                role="admin",
                max_tokens=900,
                temperature=0.1,
            )
            compressed = response.content.strip()
            if compressed:
                return compressed[:max_chars]
        except Exception:
            pass

        return self._fallback_compress(context, max_chars=max_chars)

    def classify_request(
        self,
        user_message: str,
        *,
        compressed_context: str | None = None,
    ) -> RouteResult:
        text = (compressed_context or user_message).strip()

        # Check if request can be handled by equipment (deterministic scripts)
        equipment_name = self._detect_equipment(user_message)

        if self.use_llm:
            try:
                result = self._classify_with_llm(user_message=user_message, compressed_context=text)
                result.equipment_name = equipment_name
                return result
            except Exception:
                pass
        result = self._classify_with_heuristic(user_message=user_message, compressed_context=text)
        result.equipment_name = equipment_name
        return result

    def _classify_with_llm(self, *, user_message: str, compressed_context: str) -> RouteResult:
        schema = (
            "Return strict JSON with keys: "
            "intent, difficulty, relevant_files, qa_requirements, clarification_question.\n"
            "difficulty must be one of: trivial, normal, complex, unclear."
        )
        response = self.router.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You are NEXUS Admin router. "
                        "Classify requests and output only valid JSON."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"{schema}\n\n"
                        f"Original request:\n{user_message}\n\n"
                        f"Compressed context:\n{compressed_context}"
                    ),
                },
            ],
            role="admin",
            temperature=0.0,
            max_tokens=350,
        )
        payload = self._parse_json_object(response.content)

        difficulty_raw = str(payload.get("difficulty", "")).strip().lower()
        if difficulty_raw not in ALLOWED_DIFFICULTY:
            raise ValueError(f"Invalid difficulty from LLM: {difficulty_raw}")
        difficulty: Difficulty = difficulty_raw  # type: ignore[assignment]

        intent = str(payload.get("intent") or self._infer_intent(user_message)).strip()
        relevant_files = self._normalize_files(payload.get("relevant_files"), compressed_context)
        qa_requirements = str(payload.get("qa_requirements") or self._default_qa(intent)).strip()

        clarification_question_raw = payload.get("clarification_question")
        clarification_question = (
            str(clarification_question_raw).strip()
            if clarification_question_raw not in (None, "")
            else None
        )
        if difficulty == "unclear" and not clarification_question:
            clarification_question = self._default_clarification_question()

        owner = owner_for_difficulty(difficulty)
        return RouteResult(
            intent=intent,
            difficulty=difficulty,
            owner=owner,
            relevant_files=relevant_files,
            qa_requirements=qa_requirements,
            clarification_question=clarification_question,
        )

    def _classify_with_heuristic(
        self, *, user_message: str, compressed_context: str,
    ) -> RouteResult:
        lowered = user_message.lower()
        intent = self._infer_intent(user_message)
        difficulty = self._infer_difficulty(lowered, user_message)
        owner = owner_for_difficulty(difficulty)
        relevant_files = self._extract_files(compressed_context)
        qa_requirements = self._default_qa(intent)
        clarification_question = (
            self._default_clarification_question() if difficulty == "unclear" else None
        )

        return RouteResult(
            intent=intent,
            difficulty=difficulty,
            owner=owner,
            relevant_files=relevant_files,
            qa_requirements=qa_requirements,
            clarification_question=clarification_question,
        )

    @staticmethod
    def _build_context_block(
        user_message: str,
        conversation: Sequence[Mapping[str, Any]] | None,
    ) -> str:
        lines: list[str] = []
        if conversation:
            lines.append("Conversation excerpts:")
            for msg in conversation[-8:]:
                role = str(msg.get("role", "user")).strip() or "user"
                content = str(msg.get("content", "")).strip()
                if content:
                    lines.append(f"- {role}: {content}")
        lines.append("Latest request:")
        lines.append(user_message.strip())
        return "\n".join(lines).strip()

    @staticmethod
    def _fallback_compress(text: str, *, max_chars: int) -> str:
        collapsed = re.sub(r"\s+", " ", text).strip()
        if len(collapsed) <= max_chars:
            return collapsed
        head = max(0, (max_chars // 2) - 24)
        tail = max(0, max_chars - head - 24)
        return f"{collapsed[:head]} ... [truncated] ... {collapsed[-tail:]}"

    @staticmethod
    def _parse_json_object(text: str) -> dict[str, Any]:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in model response.")
        return json.loads(match.group(0))

    @staticmethod
    def _normalize_files(raw: Any, backup_text: str) -> list[str]:
        if isinstance(raw, list):
            cleaned = [str(item).strip() for item in raw if str(item).strip()]
            if cleaned:
                return cleaned[:10]
        return AdminAgent._extract_files(backup_text)

    @staticmethod
    def _extract_files(text: str) -> list[str]:
        pattern = re.compile(r"(?:[\w.-]+/)*[\w.-]+\.[A-Za-z0-9]+")
        found = pattern.findall(text)
        unique: list[str] = []
        for item in found:
            if item not in unique:
                unique.append(item)
        return unique[:10]

    @staticmethod
    def _infer_intent(text: str) -> str:
        lowered = text.lower()
        if any(k in lowered for k in ["bug", "debug", "error", "fix", "报错", "修复"]):
            return "debug"
        if any(k in lowered for k in ["deploy", "docker", "k8s", "ops", "上线", "部署"]):
            return "ops"
        if any(k in lowered for k in ["doc", "readme", "文档", "说明"]):
            return "documentation"
        if any(k in lowered for k in ["build", "implement", "create", "新增", "实现", "搭建"]):
            return "build_feature"
        return "general_request"

    @staticmethod
    def _infer_difficulty(lowered: str, raw_text: str) -> Difficulty:
        if len(raw_text.strip()) < 8:
            return "unclear"

        unclear_signals = [
            "不知道",
            "随便",
            "你看着办",
            "unclear",
            "not sure",
            "whatever",
        ]
        if any(token in lowered for token in unclear_signals):
            return "unclear"

        complex_signals = [
            "architecture",
            "refactor",
            "migration",
            "database",
            "security",
            "performance",
            "langgraph",
            "redis",
            "postgres",
            "docker",
            "kubernetes",
            "架构",
            "重构",
            "迁移",
            "数据库",
            "性能",
            "安全",
        ]
        complex_hits = sum(1 for token in complex_signals if token in lowered)
        if complex_hits >= 2 or len(raw_text) > 900:
            return "complex"

        trivial_signals = [
            "typo",
            "format",
            "translate",
            "rename",
            "small",
            "quick",
            "改个字",
            "翻译",
            "润色",
            "一句话",
        ]
        if len(raw_text) < 140 and any(token in lowered for token in trivial_signals):
            return "trivial"

        return "normal"

    @staticmethod
    def _default_qa(intent: str) -> str:
        if intent == "debug":
            return "Reproduce the issue, apply fix, and verify the failure no longer occurs."
        if intent == "build_feature":
            return "Feature must run without errors and include a local verification step."
        if intent == "ops":
            return "Changes must include rollback notes and a post-change health check."
        return "Must run without errors."

    @staticmethod
    def _default_clarification_question() -> str:
        return "Please clarify your expected output, constraints, and preferred deliverable format."

    @staticmethod
    def _detect_equipment(user_message: str) -> str | None:
        """
        Detect if user request can be handled by equipment (deterministic scripts).
        Returns equipment name if detected, None otherwise.
        """
        lowered = user_message.lower()

        # Health check patterns
        health_patterns = [
            "health check",
            "system health",
            "check system",
            "cpu usage",
            "memory usage",
            "disk usage",
            "gpu usage",
            "系统健康",
            "健康检查",
        ]
        if any(pattern in lowered for pattern in health_patterns):
            return "health_check"

        # Log rotation patterns
        log_patterns = [
            "rotate log",
            "clean log",
            "compress log",
            "log cleanup",
            "日志清理",
            "日志轮转",
        ]
        if any(pattern in lowered for pattern in log_patterns):
            return "log_rotate"

        # Backup patterns
        backup_patterns = [
            "backup",
            "create backup",
            "backup project",
            "备份",
            "备份项目",
        ]
        if any(pattern in lowered for pattern in backup_patterns):
            return "backup"

        # Cost report patterns
        cost_patterns = [
            "cost report",
            "token cost",
            "usage report",
            "token usage",
            "成本报告",
            "token 成本",
        ]
        if any(pattern in lowered for pattern in cost_patterns):
            return "cost_report"

        return None

    @staticmethod
    def _new_work_order_id() -> str:
        utc_day = datetime.now(UTC).strftime("%Y%m%d")
        serial = next(_ORDER_COUNTER)
        return f"WO-{utc_day}-{serial:04d}"

