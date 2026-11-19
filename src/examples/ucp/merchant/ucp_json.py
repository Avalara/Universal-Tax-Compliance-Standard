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

"""JSON helpers for UCP payloads."""

from __future__ import annotations

from typing import Any


def _reverse_domain_dict_key(key: str) -> str:
  """Turn ``root='a.b'`` style keys into ``a.b``."""
  if not isinstance(key, str):
    return str(key)
  if key.startswith("root='") and key.endswith("'"):
    return key[len("root='") : -1]
  if key.startswith('root="') and key.endswith('"'):
    return key[len('root="') : -1]
  return key


def normalize_ucp_registry_keys(data: dict[str, Any]) -> dict[str, Any]:
  """Fix ``ucp.capabilities`` / ``order.ucp`` keys after ``model_dump``.

  ``ReverseDomainName`` map keys become ``root='…'`` strings in JSON; normalize
  them to plain reverse-domain names.
  """
  out = dict(data)
  ucp = out.get("ucp")
  if isinstance(ucp, dict):
    ucp = dict(ucp)
    caps = ucp.get("capabilities")
    if isinstance(caps, dict):
      ucp["capabilities"] = {
        _reverse_domain_dict_key(k): v for k, v in caps.items()
      }
    out["ucp"] = ucp
  order = out.get("order")
  if isinstance(order, dict):
    order = dict(order)
    o_ucp = order.get("ucp")
    if isinstance(o_ucp, dict):
      o_ucp = dict(o_ucp)
      caps = o_ucp.get("capabilities")
      if isinstance(caps, dict):
        o_ucp["capabilities"] = {
          _reverse_domain_dict_key(k): v for k, v in caps.items()
        }
      order["ucp"] = o_ucp
    out["order"] = order
  return out
