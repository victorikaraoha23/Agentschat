"""In-memory runtime doubles for contract tests (Tasks 7.1 and 8.3).

These fakes implement the application-facing ``AgentRuntime`` protocol with
no external calls -- no Hermes, no model, no subprocess, no network. They
exist only so tests can prove application code handles both runtime
outcomes without importing anything Hermes-specific.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.runtime import (
    RuntimeFailureReason,
    RuntimeRequest,
    RuntimeResult,
    RuntimeStreamEvent,
    RuntimeStreamEventKind,
)


class FakeSuccessRuntime:
    """Always answers successfully with fixed, caller-independent text."""

    def __init__(self, output: str = "fake assistant reply") -> None:
        self.output = output
        self.requests: list[RuntimeRequest] = []

    async def execute(self, request: RuntimeRequest) -> RuntimeResult:
        self.requests.append(request)
        return RuntimeResult(ok=True, output=self.output)

    async def stream(
        self, request: RuntimeRequest
    ) -> AsyncIterator[RuntimeStreamEvent]:
        """Emit the answer as two deltas, then complete with the whole text.

        Two deltas rather than one so a test that only reads the first event can
        tell "arrived incrementally" from "the whole answer at once".
        """
        self.requests.append(request)
        half = len(self.output) // 2
        yield RuntimeStreamEvent(
            kind=RuntimeStreamEventKind.DELTA, content=self.output[:half]
        )
        yield RuntimeStreamEvent(
            kind=RuntimeStreamEventKind.DELTA, content=self.output[half:]
        )
        yield RuntimeStreamEvent(
            kind=RuntimeStreamEventKind.COMPLETED, content=self.output
        )


class FakeFailureRuntime:
    """Always answers with the configured application-level failure."""

    def __init__(
        self,
        reason: RuntimeFailureReason = RuntimeFailureReason.FAILED,
    ) -> None:
        self.reason = reason
        self.requests: list[RuntimeRequest] = []

    async def execute(self, request: RuntimeRequest) -> RuntimeResult:
        self.requests.append(request)
        return RuntimeResult(
            ok=False,
            reason=self.reason,
            message="Fake runtime failure.",
        )

    async def stream(
        self, request: RuntimeRequest
    ) -> AsyncIterator[RuntimeStreamEvent]:
        """Fail immediately, having produced nothing.

        The "nothing" is the point: a run that never started cannot have partial
        output, so a test that wants partial-then-failure uses
        :class:`PartialThenFailRuntime` instead.
        """
        self.requests.append(request)
        yield RuntimeStreamEvent(kind=RuntimeStreamEventKind.FAILED, reason=self.reason)


class PartialThenFailRuntime(FakeFailureRuntime):
    """Emits some text, then fails -- the partial-output case (Task 8.3)."""

    def __init__(
        self,
        reason: RuntimeFailureReason = RuntimeFailureReason.FAILED,
        partial: str = "Hello, I can hel",
    ) -> None:
        super().__init__(reason)
        self.partial = partial

    async def stream(
        self, request: RuntimeRequest
    ) -> AsyncIterator[RuntimeStreamEvent]:
        self.requests.append(request)
        yield RuntimeStreamEvent(
            kind=RuntimeStreamEventKind.DELTA, content=self.partial
        )
        yield RuntimeStreamEvent(kind=RuntimeStreamEventKind.FAILED, reason=self.reason)
