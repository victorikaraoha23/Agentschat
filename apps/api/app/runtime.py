"""Agent runtime contract for the FastAPI backend (Task 7.1).

Boundary owned here::

    API/domain  ->  Runtime interface (here)  ->  Hermes adapter  ->  Hermes

Application code depends only on what is defined here, never on Hermes
imports, config keys, or response shapes. The adapter lives in
``app/hermes_adapter.py`` and is selected by ``get_agent_runtime`` below;
until a run is actually requested nothing calls it, and the API starts and
serves exactly as before with no Hermes process or credentials present.

The contract is deliberately small: who is asking, in which conversation,
and what they said. A run may also be *streamed* (:meth:`AgentRuntime.stream`),
which reports the same three application values as events instead of one final
result. Tools, files, memory, model parameters, billing, retries, and streaming
of anything other than the reply text do not exist in the product yet.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from enum import Enum
from typing import Annotated, Final, Protocol
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import Settings, get_settings

#: Longest user content the runtime accepts, mirroring the message endpoint.
RUNTIME_CONTENT_MAX_LENGTH = 4000

#: The one wording for each failure reason, owned by the contract: the
#: unavailable placeholder, the Hermes adapter, and the execution endpoint's
#: HTTP details all use these, so the same outcome reads the same wherever it
#: surfaces. They are application text, never provider wording (root AGENTS.md
#: §13, §18 — one canonical definition instead of copies).
RUNTIME_UNAVAILABLE_MESSAGE: Final[str] = "The agent runtime is not available."
RUNTIME_FAILED_MESSAGE: Final[str] = "The agent run failed."
RUNTIME_TIMED_OUT_MESSAGE: Final[str] = "The agent run took too long and was stopped."
RUNTIME_INVALID_REQUEST_MESSAGE: Final[str] = "The agent runtime rejected the request."


class RuntimeRequest(BaseModel):
    """Application-level work offered to the agent runtime."""

    model_config = ConfigDict(frozen=True)

    user_id: UUID = Field(description="Verified caller; never client-supplied.")
    conversation_id: UUID = Field(description="Conversation owning the message.")
    content: str = Field(min_length=1, max_length=RUNTIME_CONTENT_MAX_LENGTH)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        """Trim the content, and refuse a message with nothing in it.

        Empty and whitespace-only content are validation errors, matching the
        message endpoint so exactly what the user typed (minus surrounding
        whitespace) is what the runtime sees.
        """
        stripped = value.strip()
        if stripped == "":
            raise ValueError("Content must not be blank.")
        return stripped


class RuntimeFailureReason(str, Enum):
    """Small application-level failure vocabulary for runtime outcomes."""

    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    TIMED_OUT = "timed-out"
    INVALID_REQUEST = "invalid-request"


class RuntimeResult(BaseModel):
    """Outcome of one runtime execution, in application terms only."""

    model_config = ConfigDict(frozen=True)

    ok: bool = Field(description="True for success, False for runtime failure.")
    output: str = Field(default="", description="Assistant text when ok.")
    reason: RuntimeFailureReason | None = Field(default=None)
    message: str = Field(default="", description="Safe short summary.")

    @model_validator(mode="after")
    def _check_success_and_failure_shapes(self) -> RuntimeResult:
        """Keep success and failure results in their distinct shapes."""
        if self.ok and self.reason is not None:
            raise ValueError("A successful result must not carry a failure reason.")
        if not self.ok and self.reason is None:
            raise ValueError("A failed result must carry a failure reason.")
        return self


class RuntimeStreamEventKind(str, Enum):
    """The three things a streamed run can report (Task 8.3).

    Deliberately tiny. A stream needs to say "here is more text", "that is the
    whole reply", or "this run failed" -- and nothing else. Tool activity, token
    counts, reasoning, and provider detail have no product meaning yet, so they
    are not modelled rather than modelled and ignored.
    """

    DELTA = "delta"
    COMPLETED = "completed"
    FAILED = "failed"


class RuntimeStreamEvent(BaseModel):
    """One event of a streamed run, in application terms only.

    ``content`` carries the new text for a ``DELTA`` and the complete reply for
    ``COMPLETED``. A ``FAILED`` event carries a reason instead of content, and the
    implementation's own error text stays on the server (root ``AGENTS.md`` §13).
    """

    model_config = ConfigDict(frozen=True)

    kind: RuntimeStreamEventKind
    content: str = Field(default="")
    reason: RuntimeFailureReason | None = Field(default=None)

    @model_validator(mode="after")
    def _check_event_shape(self) -> RuntimeStreamEvent:
        """Keep failures and non-failures in their distinct shapes."""
        if self.kind is RuntimeStreamEventKind.FAILED and self.reason is None:
            raise ValueError("A failed stream event must carry a failure reason.")
        if self.kind is not RuntimeStreamEventKind.FAILED and self.reason is not None:
            raise ValueError("Only a failed stream event carries a failure reason.")
        return self


class AgentRuntime(Protocol):
    """Application-facing runtime capability used by execution paths."""

    async def execute(self, request: RuntimeRequest) -> RuntimeResult:
        """Run one agent request and return its application-level outcome."""
        ...  # pragma: no cover - contract only

    def stream(self, request: RuntimeRequest) -> AsyncGenerator[RuntimeStreamEvent, None]:
        """Run one agent request, yielding events as they become available.

        The async generator form matters: a run may involve model calls,
        subprocesses, and network work, so the adapter must be able to yield
        between them without blocking the request. Implementations always finish
        with exactly one terminal event (``COMPLETED`` or ``FAILED``), which is
        what tells the caller whether a complete reply exists. Callers close the
        generator to release runtime resources when streaming stops. Implementations
        must shield asynchronous cleanup when a pending read is cancelled.
        """
        ...  # pragma: no cover - contract only


class _UnavailableRuntime:
    """Placeholder used whenever no runtime implementation is configured."""

    async def execute(self, request: RuntimeRequest) -> RuntimeResult:
        return RuntimeResult(
            ok=False,
            reason=RuntimeFailureReason.UNAVAILABLE,
            message=RUNTIME_UNAVAILABLE_MESSAGE,
        )

    async def stream(
        self, request: RuntimeRequest
    ) -> AsyncGenerator[RuntimeStreamEvent, None]:
        """Fail immediately rather than pretending to stream an answer.

        A stream that opened and never produced anything would leave the caller
        waiting with no way to tell what happened; one failed event says it at
        once, in the same wording `execute` uses.
        """
        yield RuntimeStreamEvent(
            kind=RuntimeStreamEventKind.FAILED,
            reason=RuntimeFailureReason.UNAVAILABLE,
        )


_UNAVAILABLE = _UnavailableRuntime()


def get_agent_runtime(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AgentRuntime:
    """FastAPI dependency returning the configured runtime implementation.

    Configuration decides between the Hermes adapter and the unavailable
    placeholder; nothing else does, and neither is touched at import time.
    ``dependency_overrides`` substitutes a fake in tests without reaching into
    either implementation.
    """
    executable = settings.hermes_executable
    if executable is None:
        return _UNAVAILABLE
    # Imported here, not at module level: the adapter implements the contract
    # above, so a top-level import would make the contract depend on its own
    # implementation (root AGENTS.md §3).
    from app.hermes_adapter import HermesRuntimeAdapter

    return HermesRuntimeAdapter(
        executable=executable,
        timeout_seconds=settings.hermes_timeout_seconds,
    )


AgentRuntimeDep = Annotated[AgentRuntime, Depends(get_agent_runtime)]
