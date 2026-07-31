"""Deterministic one-tool planner used by the agent ablation."""
from __future__ import annotations

import re
import time
from typing import Any, Callable, Sequence

from .contracts import (
    AgentAction, AgentExecutionResult, AgentStatus, AgentTraceEvent, PlannerDecision, ToolRequest,
)
from .tools import RetrievalTool


PLANNER_POLICY = "deterministic-retrieve-or-abstain"
PLANNER_POLICY_VERSION = "v1"


class SimplePlanner:
    allowed_actions = frozenset({AgentAction.RETRIEVE, AgentAction.ABSTAIN})

    def __init__(
        self, *, retrieval_tool: RetrievalTool, generator: Callable[[dict[str, Any], str, Sequence[Any]], str],
        top_k: int, filter_profile: str, max_steps: int = 3, max_tool_calls: int = 1,
        max_retries: int = 0, deadline_seconds: float = 60.0,
        decision_policy: Callable[[object], PlannerDecision] | None = None,
    ) -> None:
        if (
            not 1 <= max_steps <= 3 or not 0 <= max_tool_calls <= 1 or max_retries != 0
            or top_k <= 0 or not 0 < deadline_seconds <= 300
        ):
            raise ValueError("Planner steps, calls, retries, top_k, and deadline must satisfy the bounded contract.")
        self.tool = retrieval_tool
        self.generator = generator
        self.top_k = top_k
        self.filter_profile = filter_profile
        self.max_steps = max_steps
        self.max_tool_calls = max_tool_calls
        self.max_retries = max_retries
        self.deadline_seconds = deadline_seconds
        self.decision_policy = decision_policy or self.decide

    @staticmethod
    def decide(question: object) -> PlannerDecision:
        if not isinstance(question, str):
            return PlannerDecision(AgentAction.ABSTAIN, None, "unsupported_request")
        normalized = " ".join(question.split())
        if not normalized:
            return PlannerDecision(AgentAction.ABSTAIN, None, "insufficient_question")
        return PlannerDecision(AgentAction.RETRIEVE, normalized, "retrieval_required")

    def execute(self, row: dict[str, Any]) -> AgentExecutionResult:
        started = time.perf_counter()
        trace: list[AgentTraceEvent] = []
        decision_started = time.perf_counter()
        decision = self.decision_policy(row.get("question"))
        decision_ms = _elapsed_ms(decision_started)
        if decision.action not in self.allowed_actions:
            return self._failure(started, trace, "unsupported_request", "UnapprovedAction", decision_ms)
        trace.append(AgentTraceEvent(1, "planner_decision", action=decision.action.value, reason_code=decision.reason_code, latency_ms=decision_ms))
        if decision.action is AgentAction.ABSTAIN:
            return AgentExecutionResult(
                status=AgentStatus.ABSTAINED, trace=tuple(trace), reason_code=decision.reason_code,
                latency_ms={"planner_decision": decision_ms, "agent_total": _elapsed_ms(started)},
            )
        if self.max_steps < 3:
            trace.append(AgentTraceEvent(2, "termination", status="failed", reason_code="step_limit_reached"))
            return self._failure(started, trace, "step_limit_reached", "StepLimitExceeded", decision_ms)
        if self.max_tool_calls < 1:
            return self._failure(started, trace, "step_limit_reached", "ToolCallLimitExceeded", decision_ms)
        if self._expired(started):
            return self._failure(started, trace, "step_limit_reached", "AgentDeadlineExceeded", decision_ms)

        tool_result = self.tool.execute(ToolRequest(decision.query or "", self.top_k, self.filter_profile))
        trace.append(AgentTraceEvent(
            2, "tool_call", action="retrieve", tool=self.tool.name, status=tool_result.status,
            latency_ms=tool_result.latency_ms, result_count=tool_result.result_count,
            error_type=tool_result.error_type,
        ))
        latencies = {**tool_result.stage_latencies_ms, "planner_decision": decision_ms, "tool_retrieval": tool_result.latency_ms}
        if tool_result.status == "failed":
            return self._failure(started, trace, "tool_failure", tool_result.error_type or "ToolFailure", decision_ms,
                                 tool_result.error_message, latencies, tool_calls=1)
        if tool_result.status == "empty":
            return AgentExecutionResult(
                status=AgentStatus.ABSTAINED, retrieved_items=(), trace=tuple(trace), reason_code="empty_context",
                latency_ms={**latencies, "agent_total": _elapsed_ms(started)}, retrieval_invoked=True,
                tool_call_count=1, successful_tool_calls=1,
            )
        if self._expired(started):
            return self._failure(started, trace, "step_limit_reached", "AgentDeadlineExceeded", decision_ms,
                                 latencies=latencies, tool_calls=1)
        generation_started = time.perf_counter()
        try:
            context = _format_context(tool_result.items)
            answer = self.generator(row, context, tool_result.items)
            generation_ms = _elapsed_ms(generation_started)
        except Exception as exc:
            generation_ms = _elapsed_ms(generation_started)
            trace.append(AgentTraceEvent(3, "generation", status="failed", latency_ms=generation_ms, error_type=type(exc).__name__))
            return self._failure(started, trace, "tool_failure", type(exc).__name__, decision_ms, str(exc),
                                 {**latencies, "generation": generation_ms}, tool_calls=1)
        trace.append(AgentTraceEvent(3, "generation", status="completed", latency_ms=generation_ms))
        return AgentExecutionResult(
            status=AgentStatus.COMPLETED, final_answer=str(answer), retrieved_items=tool_result.items,
            trace=tuple(trace), latency_ms={**latencies, "generation": generation_ms, "agent_total": _elapsed_ms(started)},
            retrieval_invoked=True, tool_call_count=1, successful_tool_calls=1,
        )

    def _expired(self, started: float) -> bool:
        return time.perf_counter() - started >= self.deadline_seconds

    @staticmethod
    def _failure(started: float, trace: list[AgentTraceEvent], reason: str, error_type: str, decision_ms: float,
                 message: str | None = None, latencies: dict[str, float | None] | None = None,
                 tool_calls: int = 0) -> AgentExecutionResult:
        return AgentExecutionResult(
            status=AgentStatus.FAILED, trace=tuple(trace), reason_code=reason, error_type=error_type,
            error_message=_sanitize_error(message or error_type),
            latency_ms={**(latencies or {"planner_decision": decision_ms}), "agent_total": _elapsed_ms(started)},
            retrieval_invoked=bool(tool_calls), tool_call_count=tool_calls,
        )


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000.0, 6)


def _sanitize_error(message: str) -> str:
    value = re.sub(
        r"(?i)(api[_-]?key|authorization|token|secret)(\s*[:=]\s*)([^\s,;]+)",
        r"\1\2***",
        str(message),
    )
    return re.sub(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+", "Bearer ***", value)[:500]


def _format_context(chunks: Sequence[Any]) -> str:
    blocks = []
    for rank, chunk in enumerate(chunks, 1):
        citation = getattr(chunk, "citation_anchor", None) or getattr(chunk, "citation_label", None) or getattr(chunk, "chunk_id", None)
        blocks.append(f"[{rank}] chunk_id={getattr(chunk, 'chunk_id', '')}; citation={citation}\n{getattr(chunk, 'chunk_text', '')}")
    return "\n\n".join(blocks)
