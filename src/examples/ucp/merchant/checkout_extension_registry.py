#   Copyright 2026 UCP Authors
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""Pluggable checkout extensions for discovery and capability negotiation.

Registered entries are merged into the business capability list advertised at
``/.well-known/ucp`` and used as the business side of platform intersection.
Duplicate capability ``name`` values are resolved in favor of the **registry**
(registered declarations override ``discovery_profile.json``).

This module is **data-only**: it does not add checkout JSON fields. New
extension payloads still require SDK models, mixing into ``UnifiedCheckout``,
or ``model_config = ConfigDict(extra="allow")`` on your checkout types.
"""

from __future__ import annotations

from typing import Any

_CHECKOUT_ROOT = "dev.ucp.shopping.checkout"

_REGISTRY: list[dict[str, Any]] = []


def register_checkout_extension(capability: dict[str, Any]) -> None:
  """Register a checkout extension capability (vendor or internal).

  Args:
      capability: Discovery-style declaration with ``name``, ``version``,
        ``spec``, ``schema``, and ``extends`` (string or list) that includes
        ``dev.ucp.shopping.checkout``.

  Raises:
      ValueError: If required keys are missing or ``extends`` is invalid.

  """
  required = ("name", "version", "spec", "schema")
  for key in required:
    if key not in capability:
      msg = f"Capability must include {key!r}"
      raise ValueError(msg)
  ext = capability.get("extends")
  if ext is None:
    msg = "Checkout extensions must declare extends"
    raise ValueError(msg)
  parents = [ext] if isinstance(ext, str) else list(ext)
  if _CHECKOUT_ROOT not in parents:
    msg = f"extends must include {_CHECKOUT_ROOT!r}"
    raise ValueError(msg)
  _REGISTRY.append(dict(capability))


def iter_registered_checkout_extensions() -> tuple[dict[str, Any], ...]:
  """Return a snapshot of registered extensions (immutable tuples of dicts)."""
  return tuple(dict(x) for x in _REGISTRY)


def clear_registered_checkout_extensions() -> None:
  """Remove all registered extensions (for tests)."""
  _REGISTRY.clear()


def merge_discovery_capabilities_list(
  discovery_caps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
  """Merge discovery list with registry; registry overrides same ``name``."""
  by_name: dict[str, dict[str, Any]] = {
    c["name"]: dict(c) for c in discovery_caps if "name" in c
  }
  for reg in _REGISTRY:
    by_name[reg["name"]] = dict(reg)
  return list(by_name.values())


def merge_discovery_capabilities(
  discovery_caps: dict[str, Any],
) -> dict[str, Any]:
  """Merge a name-keyed capability map; registry overrides the same name."""
  out: dict[str, Any] = {
    str(name): list(items) if isinstance(items, list) else items
    for name, items in discovery_caps.items()
  }
  for reg in _REGISTRY:
    entry = {key: value for key, value in reg.items() if key != "name"}
    out[str(reg["name"])] = [entry]
  return out


def load_default_extensions() -> None:
  """Register built-in extensions at startup.

  Registers the checkout tax preview extension when running the
  companion service (see ``--checkout_tax_extension_url``). ``spec`` points at
  the extension's UCP discovery document (``/.well-known/ucp``); ``schema``
  references its OpenAPI definition.
  """
  if any(x.get("name") == "dev.ucp.shopping.tax" for x in _REGISTRY):
    return
  _tax_base = "http://127.0.0.1:8080"
  register_checkout_extension(
    {
      "name": "dev.ucp.shopping.tax",
      "version": "2026-04-08",
      "spec": f"{_tax_base}/.well-known/ucp",
      "schema": f"{_tax_base}/openapi.json",
      "extends": _CHECKOUT_ROOT,
      "config": {
        "tier": "core",
        "input_profiles": ["utcs-standard"],
        "rounding": {
          "default_method": "half_up",
          "granularity": "per_line_per_jurisdiction",
        },
        "conformance_profiles": [{"id": "us-sst", "version": "2025.1"}],
      },
    }
  )
