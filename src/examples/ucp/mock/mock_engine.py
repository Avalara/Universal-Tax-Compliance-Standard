# Copyright 2026 Avalara, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Flat-rate determination provider. Checkout and UCP stay outside this module."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

from bindings.ucp.errors import BindingError
from bindings.ucp.money import decimal_to_minor, minor_to_decimal
from bindings.ucp.models import (
    Attestation,
    ConformanceProfile,
    JurisdictionBreakdown,
    OrderJurisdiction,
    ResultLine,
    TaxResult,
    TransactionContext,
)

_TOTAL_RATE = Decimal("0.0875")
_STATE_RATE = Decimal("0.056875")


def _minor_tax(amount_minor: int, rate: Decimal) -> int:
    return int((Decimal(amount_minor) * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def calculate(context: TransactionContext) -> TaxResult:
    """Return a calculated TaxResult. The caller decides whether to record it."""
    if context.entity_type not in {"b2c", "b2b", "b2g"}:
        raise BindingError(
            "tax_invalid_classification",
            f"entity_type {context.entity_type!r} is not recognized",
            path="entity_type",
        )
    if context.commit and not context.document_code.strip():
        raise BindingError(
            "tax_insufficient_data",
            "A committed determination needs document_code",
            path="document_code",
        )
    currency = context.currency_code
    if not context.lines:
        raise BindingError("tax_insufficient_data", "At least one line is required", path="lines")

    lines: list[ResultLine] = []
    total_tax_minor = 0
    total_amount_minor = 0
    state_amount_minor = 0
    state_tax_minor = 0
    local_amount_minor = 0
    local_tax_minor = 0

    for line in context.lines:
        amount_minor = decimal_to_minor(line.amount, currency)
        tax_minor = _minor_tax(amount_minor, _TOTAL_RATE)
        state_minor = _minor_tax(amount_minor, _STATE_RATE)
        local_minor = tax_minor - state_minor
        total_tax_minor += tax_minor
        total_amount_minor += amount_minor
        state_amount_minor += amount_minor
        state_tax_minor += state_minor
        local_amount_minor += amount_minor
        local_tax_minor += local_minor
        region = context.addresses["ship_to"].region or "LOCAL"
        lines.append(
            ResultLine(
                line_number=line.line_number,
                tax_amount=minor_to_decimal(tax_minor, currency),
                taxable_amount=line.amount,
                exempt_amount=minor_to_decimal(0, currency),
                non_taxable_amount=minor_to_decimal(0, currency),
                tax_code=line.tax_code,
                jurisdictions=[
                    JurisdictionBreakdown(
                        jurisdiction_type="state",
                        jurisdiction_code="ST",
                        jurisdiction_name=region,
                        tax_type="sales_tax",
                        rate=format(_STATE_RATE, "f"),
                        taxable_amount=line.amount,
                        tax_amount=minor_to_decimal(state_minor, currency),
                        rate_rule_id="mock-state",
                    ),
                    JurisdictionBreakdown(
                        jurisdiction_type="city",
                        jurisdiction_code="LOC",
                        jurisdiction_name=region,
                        tax_type="sales_tax",
                        rate=format(_TOTAL_RATE - _STATE_RATE, "f"),
                        taxable_amount=line.amount,
                        tax_amount=minor_to_decimal(local_minor, currency),
                        rate_rule_id="mock-local",
                    ),
                ],
            )
        )

    region = context.addresses["ship_to"].region or "LOCAL"
    ruleset = os.environ.get("UTCS_MOCK_RULESET_VERSION", "mock-0.1")
    zero = minor_to_decimal(0, currency)
    return TaxResult(
        result_id=f"res_{uuid.uuid4().hex[:12]}",
        document_code=context.document_code,
        status="calculated",
        total_tax=minor_to_decimal(total_tax_minor, currency),
        total_taxable=minor_to_decimal(total_amount_minor, currency),
        total_exempt=zero,
        total_non_taxable=zero,
        total_amount=minor_to_decimal(total_amount_minor, currency),
        currency_code=currency,
        lines=lines,
        jurisdictions=[
            OrderJurisdiction(
                jurisdiction_type="state",
                jurisdiction_code="ST",
                jurisdiction_name=region,
                tax_type="sales_tax",
                taxable_amount=minor_to_decimal(state_amount_minor, currency),
                tax_amount=minor_to_decimal(state_tax_minor, currency),
            ),
            OrderJurisdiction(
                jurisdiction_type="city",
                jurisdiction_code="LOC",
                jurisdiction_name=region,
                tax_type="sales_tax",
                taxable_amount=minor_to_decimal(local_amount_minor, currency),
                tax_amount=minor_to_decimal(local_tax_minor, currency),
            ),
        ],
        attestation=Attestation(
            provider_id="utcs-mock",
            provider_name="UTCS Mock",
            content_version=ruleset,
            calculation_timestamp=_now(),
            engine_version="mock-0.1",
        ),
        conformance=[ConformanceProfile(id="us-sst", version="2025.1")],
    )
