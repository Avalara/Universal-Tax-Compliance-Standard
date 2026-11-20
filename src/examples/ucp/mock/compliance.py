# Copyright 2026 Avalara, Inc.
# SPDX-License-Identifier: Apache-2.0

"""In-memory compliance state. A later ledger would hash these records."""

from __future__ import annotations

from bindings.ucp.models import TaxResult


class ComplianceStore:
    """Committed TaxResult records keyed by document_code. Not a CLT ledger."""

    def __init__(self) -> None:
        self._records: dict[str, TaxResult] = {}

    def put(self, result: TaxResult) -> None:
        self._records[result.document_code] = result

    def get(self, document_code: str) -> TaxResult | None:
        return self._records.get(document_code)

    def __contains__(self, document_code: str) -> bool:
        return document_code in self._records
