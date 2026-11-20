# Copyright 2026 Avalara, Inc.
# SPDX-License-Identifier: Apache-2.0

"""Route tests. The determine function is injected and does not store anything itself."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from bindings.ucp.models import TransactionContext
from bindings.ucp.router import create_router
from examples.ucp.mock.mock_engine import calculate

_HEADERS = {"UCP-Agent": 'profile="https://agent.example/profile"'}
_BODY = {
    "currency": "USD",
    "line_items": [
        {
            "id": "1",
            "totals": [{"type": "subtotal", "amount": 10000}],
            "item": {"id": "WIDGET"},
        }
    ],
    "fulfillment": {
        "methods": [
            {
                "destinations": [
                    {
                        "street_address": "98 San Jacinto Blvd",
                        "address_locality": "Austin",
                        "address_region": "TX",
                        "postal_code": "78701",
                        "address_country": "US",
                    }
                ]
            }
        ]
    },
    "tax": {
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
    },
}


def _app(seen: list[bool]) -> FastAPI:
    def determine(context: TransactionContext):
        seen.append(context.commit)
        result = calculate(context)
        if context.commit:
            return result.model_copy(update={"status": "committed"})
        return result

    app = FastAPI()
    app.include_router(create_router(determine))
    return app


def test_preview_forces_commit_false_and_returns_minor_units() -> None:
    seen: list[bool] = []
    client = TestClient(_app(seen))
    response = client.post("/checkout-sessions/chk_1/$previewTax", json=_BODY, headers=_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert seen == [False]
    assert body["tax"]["commit"] is False
    assert body["tax"]["document_code"] == "chk_1"
    assert body["tax"]["result"]["status"] == "calculated"
    assert body["tax"]["result"]["total_tax"] == 875
    assert body["messages"] == []
    config = body["ucp"]["capabilities"]["dev.ucp.shopping.tax"][0]["config"]
    assert config["tier"] == "core"
    assert config["input_profiles"] == ["utcs-standard"]


def test_determine_forces_commit_true() -> None:
    seen: list[bool] = []
    client = TestClient(_app(seen))
    payload = dict(_BODY)
    payload["tax"] = dict(_BODY["tax"], commit=False, document_code="SO-9")
    response = client.post("/checkout-sessions/chk_1/$determineTax", json=payload, headers=_HEADERS)
    assert response.status_code == 200
    assert seen == [True]
    assert response.json()["tax"]["result"]["status"] == "committed"
    assert response.json()["tax"]["document_code"] == "SO-9"


def test_missing_ship_from_is_a_message_not_a_rate() -> None:
    seen: list[bool] = []
    client = TestClient(_app(seen))
    payload = dict(_BODY)
    payload["tax"] = {key: value for key, value in _BODY["tax"].items() if key != "ship_from"}
    response = client.post("/checkout-sessions/chk_1/$previewTax", json=payload, headers=_HEADERS)
    assert response.status_code == 200
    assert seen == []
    message = response.json()["messages"][0]
    assert message["code"] == "tax_insufficient_data"
    assert message["severity"] == "recoverable"
    assert "tax" not in response.json()


def test_bad_ucp_agent_is_http_400() -> None:
    client = TestClient(_app([]))
    response = client.post("/checkout-sessions/chk_1/$previewTax", json=_BODY)
    assert response.status_code == 400
    assert response.json()["messages"][0]["code"] == "invalid_ucp_agent"
