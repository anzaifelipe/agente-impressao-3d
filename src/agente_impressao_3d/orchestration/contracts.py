"""Immutable, serializable contracts for one deterministic orchestration step."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class OrchestrationRequest:
    """One structured intent and the arguments to forward to its selected tool."""

    action: str
    arguments: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "arguments": dict(self.arguments)}


@dataclass(frozen=True, slots=True)
class OrchestrationResult:
    """The observation from one selected tool, associated with its intent."""

    ok: bool
    action: str
    tool: str | None = None
    result: Mapping[str, Any] | None = None
    error: Mapping[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"ok": self.ok, "action": self.action}
        if self.tool is not None:
            payload["tool"] = self.tool
        if self.ok:
            payload["result"] = dict(self.result or {})
        else:
            payload["error"] = dict(self.error or {})
        return payload
