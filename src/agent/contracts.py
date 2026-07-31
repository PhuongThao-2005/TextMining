"""Typed, serialization-safe contracts for bounded agent execution."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence


AGENT_VERSION = "agent-ablation-v1"
TRACE_SCHEMA_VERSION = "agent-trace-v1"
TOOL_CONTRACT_VERSION = "retrieval-tool-v1"


class AgentMode(str, Enum):
    NONE = "none"
    SIMPLE_PLANNER = "simple_planner"
    MULTI_TOOL = "multi_tool"


class AgentAction(str, Enum):
    RETRIEVE = "retrieve"
    ABSTAIN = "abstain"


class AgentStatus(str, Enum):
    COMPLETED = "completed"
    ABSTAINED = "abstained"
    FAILED = "failed"


@dataclass(frozen=True)
class ToolRequest:
    query: str
    top_k: int
    filter_profile: str = "broad"


@dataclass(frozen=True)
class ToolResult:
    status: str
    items: tuple[Any, ...] = ()
    latency_ms: float | None = None
    stage_latencies_ms: dict[str, float | None] = field(default_factory=dict)
    error_type: str | None = None
    error_message: str | None = None

    @property
    def result_count(self) -> int:
        return len(self.items)


@dataclass(frozen=True)
class PlannerDecision:
    action: AgentAction
    query: str | None
    reason_code: str


@dataclass(frozen=True)
class AgentTraceEvent:
    step: int
    event: str
    action: str | None = None
    reason_code: str | None = None
    tool: str | None = None
    status: str | None = None
    latency_ms: float | None = None
    result_count: int | None = None
    error_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in vars(self).items() if value is not None}


@dataclass(frozen=True)
class AgentExecutionResult:
    status: AgentStatus
    final_answer: str = ""
    retrieved_items: tuple[Any, ...] = ()
    trace: tuple[AgentTraceEvent, ...] = ()
    latency_ms: dict[str, float | None] = field(default_factory=dict)
    reason_code: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    retrieval_invoked: bool = False
    tool_call_count: int = 0
    successful_tool_calls: int = 0

    def trace_dicts(self, *, limit: int = 8) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.trace[: max(0, limit)]]


def coerce_agent_mode(value: object) -> AgentMode:
    try:
        return AgentMode(str(value or "none"))
    except ValueError as exc:
        raise ValueError(f"Unknown agent mode {value!r}; expected one of {[mode.value for mode in AgentMode]}.") from exc

