# Copyright 2026 Avalara, Inc.
# SPDX-License-Identifier: Apache-2.0

"""UTCS calculation models and the UCP tax wire."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class PostalAddress(_Model):
    """UCP postal_address."""

    street_address: str | None = None
    extended_address: str | None = None
    address_locality: str | None = None
    address_region: str | None = None
    postal_code: str | None = None
    address_country: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class TaxClassification(_Model):
    code: str
    system: str | None = None


class TaxExemption(_Model):
    certificate_id: str | None = None


class TaxLineInput(_Model):
    id: str
    taxable_amount: int | None = None
    tax_classification: TaxClassification | None = None


class TaxInput(_Model):
    document_code: str | None = None
    effective_at: str | None = None
    entity_type: str | None = None
    ship_from: PostalAddress | None = None
    exemptions: list[TaxExemption] | None = None
    lines: list[TaxLineInput] | None = None
    commit: bool | None = None


class CheckoutTaxRequest(_Model):
    currency: str
    line_items: list[dict[str, Any]] = Field(default_factory=list)
    fulfillment: dict[str, Any] | None = None
    tax: TaxInput


class UtcsAddress(_Model):
    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    region: str | None = None
    postal_code: str | None = None
    country: str
    latitude: float | None = None
    longitude: float | None = None


class UtcsCustomer(_Model):
    exemption_certificate_id: str | None = None


class UtcsLine(_Model):
    line_number: str
    quantity: float = 1
    amount: str
    tax_code: str


class TransactionContext(_Model):
    document_type: str
    document_code: str
    transaction_date: str
    currency_code: str
    commit: bool
    entity_type: str
    addresses: dict[str, UtcsAddress]
    lines: list[UtcsLine]
    customer: UtcsCustomer | None = None
    profile: str = "utcs-standard"


class JurisdictionBreakdown(_Model):
    jurisdiction_type: str
    jurisdiction_code: str
    jurisdiction_code_system: str = "provider-defined"
    jurisdiction_name: str
    tax_type: str
    tax_category: str = "S"
    fee_basis: str = "ad_valorem"
    rate: str
    taxable_amount: str
    tax_amount: str
    rate_rule_id: str
    exemption_applied: None = None


class ResultLine(_Model):
    line_number: str
    tax_amount: str
    taxable_amount: str
    exempt_amount: str
    non_taxable_amount: str
    tax_code: str
    jurisdictions: list[JurisdictionBreakdown]


class OrderJurisdiction(_Model):
    jurisdiction_type: str
    jurisdiction_code: str
    jurisdiction_code_system: str = "provider-defined"
    jurisdiction_name: str
    tax_type: str
    taxable_amount: str
    tax_amount: str


class Attestation(_Model):
    provider_id: str
    provider_name: str
    content_version: str
    calculation_timestamp: str
    engine_version: str


class ConformanceProfile(_Model):
    id: str
    version: str | None = None


class TaxResult(_Model):
    result_id: str
    document_code: str
    status: str
    total_tax: str
    total_taxable: str
    total_exempt: str
    total_non_taxable: str
    total_amount: str
    currency_code: str
    lines: list[ResultLine]
    jurisdictions: list[OrderJurisdiction]
    attestation: Attestation
    conformance: list[ConformanceProfile]
