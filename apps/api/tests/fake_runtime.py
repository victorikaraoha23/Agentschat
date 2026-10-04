"""In-memory runtime doubles for contract tests (Task 7.1).

These fakes implement the application-facing ``AgentRuntime`` protocol with
no external calls — no Hermes, no model, no subprocess, no network. They
exist only so tests can prove application code handles both runtime
outcomes without importing anything Hermes-specific.
"""

from __future__ import annotations

from app.runtime import (
    RuntimeFailureReason,
    RuntimeRequest,
    RuntimeResult,
)


class FakeSuccessRuntime:
    """Always answers successfully with fixed, caller-independent text."""

    def __init__(self, output: str = "fake assistant reply") -> None:
        self.output = output
        self.requests: list[RuntimeRequest] = []

    async def execute(self, request: RuntimeRequest) -> RuntimeResult:
        self.requests.append(request)
        return RuntimeResult(ok=True, output=self.output)


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
