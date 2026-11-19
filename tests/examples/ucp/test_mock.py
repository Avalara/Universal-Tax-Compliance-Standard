"""Mock provider: preview does not record, commit does."""

from bindings.ucp.models import (
    TransactionContext,
    UtcsAddress,
    UtcsLine,
)
from examples.ucp.mock.determine import MockDeterminer


def _context(*, commit: bool) -> TransactionContext:
    address = UtcsAddress(
        line1="98 San Jacinto Blvd",
        city="Austin",
        region="TX",
        postal_code="78701",
        country="US",
    )
    origin = UtcsAddress(
        line1="512 S Mangum St",
        city="Durham",
        region="NC",
        postal_code="27701",
        country="US",
    )
    return TransactionContext(
        document_type="sale",
        document_code="SO-1",
        transaction_date="2026-03-14T16:20:00Z",
        currency_code="USD",
        commit=commit,
        entity_type="b2c",
        addresses={"ship_from": origin, "ship_to": address},
        lines=[UtcsLine(line_number="1", quantity=1, amount="100.00", tax_code="P0000000")],
    )


def test_preview_does_not_store_and_commit_does() -> None:
    engine = MockDeterminer()
    preview = engine(_context(commit=False))
    assert preview.status == "calculated"
    assert preview.total_tax == "8.75"
    assert preview.attestation.provider_id == "utcs-mock"
    assert "SO-1" not in engine.store

    committed = engine(_context(commit=True))
    assert committed.status == "committed"
    assert engine.store.get("SO-1") is not None
    assert engine.store.get("SO-1").status == "committed"
    assert committed.attestation.calculation_timestamp.endswith("Z")
