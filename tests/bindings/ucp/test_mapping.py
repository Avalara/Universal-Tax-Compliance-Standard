"""Mapping tests for the UCP tax binding."""

from bindings.ucp.mapping import to_transaction_context, to_ucp_tax
from bindings.ucp.models import CheckoutTaxRequest
from examples.ucp.mock.mock_engine import calculate

_REQUEST = {
    "currency": "USD",
    "line_items": [
        {
            "id": "1",
            "quantity": 1,
            "totals": [{"type": "subtotal", "amount": 10000}],
            "item": {"id": "WIDGET"},
        }
    ],
    "fulfillment": {
        "methods": [
            {
                "selected_destination_id": "dest-1",
                "destinations": [
                    {
                        "id": "dest-1",
                        "street_address": "98 San Jacinto Blvd",
                        "address_locality": "Austin",
                        "address_region": "TX",
                        "postal_code": "78701",
                        "address_country": "US",
                    }
                ],
            }
        ]
    },
    "tax": {
        "document_code": "SO-1",
        "effective_at": "2026-03-14T16:20:00Z",
        "entity_type": "b2c",
        "ship_from": {
            "street_address": "512 S Mangum St",
            "address_locality": "Durham",
            "address_region": "NC",
            "postal_code": "27701",
            "address_country": "US",
        },
        "lines": [{"id": "1", "tax_classification": {"code": "P0000000"}}],
        "exemptions": [{"certificate_id": "EX-100"}],
    },
}


def test_minor_units_become_decimal_strings_and_back() -> None:
    context = to_transaction_context(
        CheckoutTaxRequest.model_validate(_REQUEST),
        commit=False,
        checkout_id="chk_1",
    )
    assert context.lines[0].amount == "100.00"
    assert context.lines[0].tax_code == "P0000000"
    assert context.addresses["ship_from"].line1 == "512 S Mangum St"
    assert context.addresses["ship_to"].city == "Austin"
    assert context.customer is not None
    assert context.customer.exemption_certificate_id == "EX-100"
    assert context.commit is False

    result = calculate(context)
    wire = to_ucp_tax(context, result)
    assert wire["result"]["total_tax"] == 875
    assert wire["result"]["lines"][0]["tax_amount"] == 875
    assert wire["result"]["lines"][0]["jurisdictions"][0]["rate"] == "0.056875"


def test_taxable_amount_override_replaces_line_subtotal() -> None:
    body = dict(_REQUEST)
    body["tax"] = dict(_REQUEST["tax"])
    body["tax"]["lines"] = [{"id": "1", "taxable_amount": 5000, "tax_classification": {"code": "P0000000"}}]
    context = to_transaction_context(
        CheckoutTaxRequest.model_validate(body),
        commit=True,
        checkout_id="chk_1",
    )
    assert context.commit is True
    assert context.lines[0].amount == "50.00"
