"""Tests for Veyra Boundary Interceptor & Python Tool Decorator."""

import pytest
from veyra.boundary.interceptor import Veyra
from veyra.boundary.retry import SafeRetryPolicy
from veyra.boundary.taxonomy import FailureKind, VeyraBoundaryError
from veyra.boundary.trace import TraceRecorder


class TestBoundaryInterceptor:
    def setup_method(self):
        self.recorder = TraceRecorder()
        self.retry_policy = SafeRetryPolicy(max_attempts=3, base_backoff_sec=0.01, max_backoff_sec=0.05, jitter=False)
        self.veyra = Veyra(recorder=self.recorder, retry_policy=self.retry_policy)

    def test_direct_execution_success(self):
        @self.veyra.tool()
        def add(a: int, b: int) -> int:
            return a + b

        result = add(2, 3)
        assert result == 5
        assert len(self.recorder.traces) == 1
        trace = self.recorder.traces[0]
        assert trace.decision == "direct_execution"
        assert trace.outcome == "success"
        assert trace.attempt == 1

    def test_safe_argument_normalization_and_execution(self):
        @self.veyra.tool()
        def get_user_profile(user_id: int, active: bool = True) -> dict:
            return {"user_id": user_id, "active": active}

        # Proposed string arguments coerced cleanly
        result = get_user_profile(user_id="42", active="true")
        assert result == {"user_id": 42, "active": True}

        assert len(self.recorder.traces) == 1
        trace = self.recorder.traces[0]
        assert trace.decision == "corrected_and_executed"
        assert trace.outcome == "success"
        assert len(trace.corrections) == 2

    def test_safe_retry_on_idempotent_transient_error(self):
        call_count = 0

        @self.veyra.tool(retryable=True, idempotent=True)
        def fetch_weather(city: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("upstream 503 gateway timeout")
            return f"Sunny in {city}"

        result = fetch_weather("Seattle")
        assert result == "Sunny in Seattle"
        assert call_count == 2
        assert len(self.recorder.traces) == 1
        trace = self.recorder.traces[0]
        assert trace.decision == "retried_and_succeeded"
        assert trace.attempt == 2
        assert trace.outcome == "success"

    def test_unsafe_retry_strictly_forbidden_for_non_idempotent(self):
        call_count = 0

        # Destructive or write tool: idempotent=False
        @self.veyra.tool(retryable=True, idempotent=False)
        def charge_card(amount: float) -> str:
            nonlocal call_count
            call_count += 1
            raise TimeoutError("payment gateway timeout")

        with pytest.raises(VeyraBoundaryError) as exc_info:
            charge_card(amount=50.0)

        assert exc_info.value.classification.kind == FailureKind.TRANSIENT_ERROR
        assert exc_info.value.classification.safe_to_retry is False
        assert call_count == 1  # Crucial: NEVER retried!

        trace = self.recorder.traces[0]
        assert trace.decision == "failed_escalated"
        assert trace.attempt == 1
        assert trace.outcome == "failure"

    def test_precondition_error_escalation(self):
        @self.veyra.tool(retryable=True, idempotent=True)
        def cancel_order(order_id: int) -> str:
            raise ValueError(f"Order {order_id} does not exist: precondition failed")

        with pytest.raises(VeyraBoundaryError) as exc_info:
            cancel_order(order_id=999)

        assert exc_info.value.classification.kind == FailureKind.PRECONDITION_ERROR
        assert exc_info.value.classification.requires_agent is True
        assert exc_info.value.classification.safe_to_retry is False

        trace = self.recorder.traces[0]
        assert trace.decision == "failed_escalated"
        assert trace.failure["kind"] == "precondition_error"

    def test_schema_validation_error_escalation(self):
        @self.veyra.tool()
        def set_score(user_id: int, score: int) -> bool:
            return True

        # Missing required parameter 'score'
        with pytest.raises(VeyraBoundaryError) as exc_info:
            set_score(user_id=12)

        assert exc_info.value.classification.kind == FailureKind.SCHEMA_ERROR
        assert exc_info.value.classification.status_code == 400
