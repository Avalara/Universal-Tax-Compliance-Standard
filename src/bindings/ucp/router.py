# Copyright 2026 Avalara, Inc.
# SPDX-License-Identifier: Apache-2.0

"""UCP routes for the tax binding. Storage stays with the injected determine function."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from bindings.ucp.discovery import PROTOCOL_VERSION, well_known_ucp
from bindings.ucp.errors import BindingError
from bindings.ucp.mapping import to_transaction_context, to_ucp_tax
from bindings.ucp.models import CheckoutTaxRequest, TaxResult, TransactionContext

Determine = Callable[[TransactionContext], TaxResult]

_PROFILE = re.compile(r'profile\s*=\s*"([^"]+)"', re.IGNORECASE)


def _ucp_agent_profile(raw: str | None) -> str:
    if raw is None or not raw.strip():
        raise BindingError(
            "invalid_ucp_agent",
            'UCP-Agent must include profile="https://..."',
            path="UCP-Agent",
        )
    match = _PROFILE.search(raw.strip())
    if not match:
        raise BindingError(
            "invalid_ucp_agent",
            'UCP-Agent must include profile="https://..."',
            path="UCP-Agent",
        )
    url = match.group(1).strip()
    if not url.startswith("https://"):
        raise BindingError(
            "invalid_ucp_agent",
            "profile URL in UCP-Agent must use https",
            path="UCP-Agent",
        )
    return url


def _envelope(public_base: str) -> dict[str, Any]:
    document = well_known_ucp(public_base=public_base)
    return {
        "version": PROTOCOL_VERSION,
        "capabilities": document["ucp"]["capabilities"],
    }


def create_router(determine: Determine) -> APIRouter:
    router = APIRouter()

    def _public_base(request: Request) -> str:
        return str(request.base_url).rstrip("/")

    @router.get("/.well-known/ucp")
    async def discovery(request: Request) -> JSONResponse:
        return JSONResponse(well_known_ucp(public_base=_public_base(request)))

    def _handle(checkout_id: str, body: CheckoutTaxRequest, *, commit: bool, request: Request) -> JSONResponse:
        base = _public_base(request)
        try:
            _ucp_agent_profile(request.headers.get("UCP-Agent"))
            context = to_transaction_context(body, commit=commit, checkout_id=checkout_id)
            result = determine(context)
        except BindingError as exc:
            status = 400 if exc.code == "invalid_ucp_agent" else 200
            payload: dict[str, Any] = {"ucp": _envelope(base), "messages": [exc.message()]}
            return JSONResponse(status_code=status, content=payload)
        return JSONResponse(
            {
                "ucp": _envelope(base),
                "tax": to_ucp_tax(context, result),
                "messages": [],
            }
        )

    @router.post("/checkout-sessions/{checkout_id}/$previewTax")
    async def preview_tax(checkout_id: str, body: CheckoutTaxRequest, request: Request) -> JSONResponse:
        return _handle(checkout_id, body, commit=False, request=request)

    @router.post("/checkout-sessions/{checkout_id}/$determineTax")
    async def determine_tax(checkout_id: str, body: CheckoutTaxRequest, request: Request) -> JSONResponse:
        return _handle(checkout_id, body, commit=True, request=request)

    return router
