"""Wire the mock provider and compliance record to the UCP binding."""

from __future__ import annotations

from bindings.ucp.models import TaxResult, TransactionContext
from examples.ucp.mock.compliance import ComplianceStore
from examples.ucp.mock.mock_engine import calculate


class MockDeterminer:
    """Determination for this phase: preview is advisory, commit writes compliance state."""

    def __init__(self, store: ComplianceStore | None = None) -> None:
        self.store = store or ComplianceStore()

    def __call__(self, context: TransactionContext) -> TaxResult:
        result = calculate(context)
        if not context.commit:
            return result
        committed = result.model_copy(update={"status": "committed"})
        self.store.put(committed)
        return committed
