"""UCP discovery document for dev.ucp.shopping.tax."""

from __future__ import annotations

from typing import Any

CAPABILITY = "dev.ucp.shopping.tax"
CHECKOUT = "dev.ucp.shopping.checkout"
PROTOCOL_VERSION = "2026-04-08"


def capability_config() -> dict[str, Any]:
    return {
        "tier": "core",
        "input_profiles": ["utcs-standard"],
        "rounding": {
            "default_method": "half_up",
            "granularity": "per_line_per_jurisdiction",
        },
        "conformance_profiles": [{"id": "us-sst", "version": "2025.1"}],
    }


def well_known_ucp(*, public_base: str) -> dict[str, Any]:
    base = public_base.rstrip("/")
    spec = f"{base}/.well-known/ucp"
    schema = f"{base}/openapi.json"
    return {
        "ucp": {
            "version": PROTOCOL_VERSION,
            "services": {
                CAPABILITY: [
                    {
                        "version": PROTOCOL_VERSION,
                        "transport": "rest",
                        "endpoint": base,
                        "spec": spec,
                        "schema": schema,
                    }
                ]
            },
            "capabilities": {
                CAPABILITY: [
                    {
                        "version": PROTOCOL_VERSION,
                        "extends": CHECKOUT,
                        "spec": spec,
                        "schema": schema,
                        "config": capability_config(),
                    }
                ]
            },
        }
    }
