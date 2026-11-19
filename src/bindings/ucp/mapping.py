"""Translate a UCP checkout tax call into a UTCS TransactionContext and back."""

from __future__ import annotations

from typing import Any

from bindings.ucp.errors import BindingError
from bindings.ucp.money import decimal_to_minor, minor_to_decimal
from bindings.ucp.models import (
    CheckoutTaxRequest,
    PostalAddress,
    TaxInput,
    TaxLineInput,
    TaxResult,
    TransactionContext,
    UtcsAddress,
    UtcsCustomer,
    UtcsLine,
)

_ENTITY_TYPES = frozenset({"b2c", "b2b", "b2g"})


def _require(value: str | None, *, content: str, path: str, code: str = "tax_insufficient_data") -> str:
    if value is None or not str(value).strip():
        severity = "requires_buyer_input" if code == "tax_invalid_location" else "recoverable"
        raise BindingError(code, content, severity=severity, path=path)
    return str(value).strip()


def _country(raw: str | None, *, path: str) -> str:
    country = _require(raw, content="Address country is required", path=path, code="tax_invalid_location")
    if len(country) != 2 or not country.isalpha():
        raise BindingError(
            "tax_invalid_location",
            f"Country {country!r} is not an ISO 3166-1 alpha-2 code",
            severity="requires_buyer_input",
            path=path,
        )
    return country.upper()


def postal_to_utcs(address: PostalAddress, *, path: str) -> UtcsAddress:
    country = _country(address.address_country, path=f"{path}.address_country")
    has_geo = address.latitude is not None and address.longitude is not None
    line1 = (address.street_address or "").strip()
    city = (address.address_locality or "").strip()
    postal = (address.postal_code or "").strip()
    has_text = bool(line1 and city and postal)
    if not has_text and not has_geo:
        raise BindingError(
            "tax_insufficient_data",
            "Address needs a street, locality, and postal code, or latitude and longitude",
            path=path,
        )
    return UtcsAddress(
        line1=line1 or None,
        line2=(address.extended_address or "").strip() or None,
        city=city or None,
        region=(address.address_region or "").strip() or None,
        postal_code=postal or None,
        country=country,
        latitude=address.latitude,
        longitude=address.longitude,
    )


def _selected_destination(fulfillment: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(fulfillment, dict):
        return None
    methods = fulfillment.get("methods")
    if not isinstance(methods, list):
        return None
    fallback: dict[str, Any] | None = None
    for method in methods:
        if not isinstance(method, dict):
            continue
        destinations = method.get("destinations")
        if not isinstance(destinations, list):
            continue
        selected = method.get("selected_destination_id")
        for dest in destinations:
            if not isinstance(dest, dict):
                continue
            if selected and dest.get("id") == selected:
                return dest
            if fallback is None and (dest.get("address_country") or dest.get("street_address")):
                fallback = dest
    return fallback


def ship_to_from_fulfillment(fulfillment: dict[str, Any] | None) -> PostalAddress:
    dest = _selected_destination(fulfillment)
    if dest is None:
        raise BindingError(
            "tax_insufficient_data",
            "Checkout fulfillment has no destination to use as ship_to",
            path="fulfillment",
        )
    return PostalAddress.model_validate(dest)


def _line_amount_minor(line: dict[str, Any], override: int | None) -> int:
    if override is not None:
        return override
    totals = line.get("totals")
    if isinstance(totals, list):
        for entry in totals:
            if isinstance(entry, dict) and entry.get("type") == "subtotal":
                return int(entry.get("amount") or 0)
        for entry in totals:
            if isinstance(entry, dict) and entry.get("type") == "total":
                return int(entry.get("amount") or 0)
    return 0


def _classification_code(line_id: str, tax_line: TaxLineInput | None, ucp_line: dict[str, Any]) -> str:
    if tax_line and tax_line.tax_classification and tax_line.tax_classification.code.strip():
        return tax_line.tax_classification.code.strip()
    item = ucp_line.get("item")
    if isinstance(item, dict):
        item_id = item.get("id")
        if isinstance(item_id, str) and item_id.strip():
            return item_id.strip()
    raise BindingError(
        "tax_invalid_classification",
        f"Line {line_id} has no tax classification code",
        path=f"tax.lines[{line_id}]",
    )


def _effective_at(raw: str) -> str:
    text = raw.strip()
    if "T" not in text:
        return f"{text}T00:00:00Z"
    return text


def to_transaction_context(
    request: CheckoutTaxRequest,
    *,
    commit: bool,
    checkout_id: str,
) -> TransactionContext:
    tax: TaxInput = request.tax
    currency = _require(request.currency, content="Checkout currency is required", path="currency").upper()
    if len(currency) != 3 or not currency.isalpha():
        raise BindingError("tax_insufficient_data", f"Currency {currency!r} is not ISO 4217", path="currency")
    effective = _require(tax.effective_at, content="tax.effective_at is required", path="tax.effective_at")
    entity = _require(tax.entity_type, content="tax.entity_type is required", path="tax.entity_type")
    if entity not in _ENTITY_TYPES:
        raise BindingError(
            "tax_invalid_classification",
            f"entity_type {entity!r} is not b2c, b2b, or b2g",
            path="tax.entity_type",
        )
    if tax.ship_from is None:
        raise BindingError("tax_insufficient_data", "tax.ship_from is required", path="tax.ship_from")
    ship_from = postal_to_utcs(tax.ship_from, path="tax.ship_from")
    ship_to = postal_to_utcs(ship_to_from_fulfillment(request.fulfillment), path="fulfillment")

    by_id = {line.id: line for line in (tax.lines or [])}
    if not request.line_items:
        raise BindingError("tax_insufficient_data", "Checkout line_items are required", path="line_items")

    utcs_lines: list[UtcsLine] = []
    for raw in request.line_items:
        if not isinstance(raw, dict):
            continue
        line_id = str(raw.get("id") or "").strip()
        if not line_id:
            raise BindingError("tax_insufficient_data", "Each line_items entry needs an id", path="line_items")
        tax_line = by_id.get(line_id)
        amount_minor = _line_amount_minor(raw, tax_line.taxable_amount if tax_line else None)
        if amount_minor < 0:
            raise BindingError(
                "tax_insufficient_data",
                f"Line {line_id} amount is negative",
                path=f"line_items[{line_id}]",
            )
        quantity = raw.get("quantity")
        utcs_lines.append(
            UtcsLine(
                line_number=line_id,
                quantity=float(quantity) if isinstance(quantity, int | float) and quantity else 1,
                amount=minor_to_decimal(amount_minor, currency),
                tax_code=_classification_code(line_id, tax_line, raw),
            )
        )
    if not utcs_lines:
        raise BindingError("tax_insufficient_data", "No line items to determine", path="line_items")

    certificate = None
    for exemption in tax.exemptions or []:
        if exemption.certificate_id and exemption.certificate_id.strip():
            certificate = exemption.certificate_id.strip()
            break
    customer = UtcsCustomer(exemption_certificate_id=certificate) if certificate else None
    document_code = (tax.document_code or "").strip() or checkout_id
    if commit and not document_code:
        raise BindingError(
            "tax_insufficient_data",
            "A committed determination needs tax.document_code",
            path="tax.document_code",
        )

    return TransactionContext(
        document_type="sale",
        document_code=document_code,
        transaction_date=_effective_at(effective),
        currency_code=currency,
        commit=commit,
        entity_type=entity,
        addresses={"ship_from": ship_from, "ship_to": ship_to},
        lines=utcs_lines,
        customer=customer,
    )


def _minor(amount: str, currency: str) -> int:
    return decimal_to_minor(amount, currency)


def to_ucp_tax(context: TransactionContext, result: TaxResult) -> dict[str, Any]:
    """UCP tax object: echoed inputs plus result amounts in minor units."""
    currency = result.currency_code
    attestation = result.attestation.model_dump()
    attestation["result_id"] = result.result_id
    lines = []
    for line in result.lines:
        lines.append(
            {
                "id": line.line_number,
                "tax_amount": _minor(line.tax_amount, currency),
                "taxable_amount": _minor(line.taxable_amount, currency),
                "exempt_amount": _minor(line.exempt_amount, currency),
                "tax_classification": {"code": line.tax_code},
                "jurisdictions": [
                    {
                        "jurisdiction_type": part.jurisdiction_type,
                        "jurisdiction_code": part.jurisdiction_code,
                        "jurisdiction_name": part.jurisdiction_name,
                        "tax_type": part.tax_type,
                        "rate": part.rate,
                        "taxable_amount": _minor(part.taxable_amount, currency),
                        "tax_amount": _minor(part.tax_amount, currency),
                    }
                    for part in line.jurisdictions
                ],
            }
        )
    return {
        "document_code": context.document_code,
        "effective_at": context.transaction_date,
        "entity_type": context.entity_type,
        "commit": context.commit,
        "result": {
            "status": result.status,
            "total_tax": _minor(result.total_tax, currency),
            "total_taxable": _minor(result.total_taxable, currency),
            "total_exempt": _minor(result.total_exempt, currency),
            "lines": lines,
            "jurisdictions": [
                {
                    "jurisdiction_type": part.jurisdiction_type,
                    "jurisdiction_code": part.jurisdiction_code,
                    "jurisdiction_name": part.jurisdiction_name,
                    "tax_type": part.tax_type,
                    "taxable_amount": _minor(part.taxable_amount, currency),
                    "tax_amount": _minor(part.tax_amount, currency),
                }
                for part in result.jurisdictions
            ],
            "attestation": attestation,
            "conformance": [item.model_dump(exclude_none=True) for item in result.conformance],
        },
    }
