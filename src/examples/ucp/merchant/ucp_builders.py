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

"""Build UCP metadata for checkout and order API responses."""

from __future__ import annotations

import capability_negotiation
import config
from ucp_sdk.models.schemas.capability import ResponseSchema as CapabilityRef
from ucp_sdk.models.schemas.ucp import ResponseCheckoutSchema
from ucp_sdk.models.schemas.ucp import ResponseOrderSchema


def _capability_map(
  name_to_version: dict[str, str],
) -> dict[str, list[CapabilityRef]]:
  return {
    name: [CapabilityRef(name=name, version=ver)]
    for name, ver in sorted(name_to_version.items())
  }


def checkout_ucp_metadata(
  negotiated_capability_versions: dict[str, str],
) -> ResponseCheckoutSchema:
  """UCP block for checkout sessions (checkout root + checkout extensions)."""
  defs = capability_negotiation.merged_capability_definitions_by_name()
  filtered = capability_negotiation.filter_for_checkout_response(
    negotiated_capability_versions,
    defs,
  )
  if capability_negotiation.CHECKOUT_ROOT not in filtered:
    filtered[capability_negotiation.CHECKOUT_ROOT] = config.get_server_version()
  return ResponseCheckoutSchema(
    version=config.get_server_version(),
    capabilities=_capability_map(filtered),
    payment_handlers=config.get_payment_handlers(),
  )


def order_ucp_metadata(
  negotiated_capability_versions: dict[str, str],
) -> ResponseOrderSchema:
  """UCP block for orders (order root + order extensions)."""
  defs = capability_negotiation.merged_capability_definitions_by_name()
  filtered = capability_negotiation.filter_for_order_response(
    negotiated_capability_versions,
    defs,
  )
  if capability_negotiation.ORDER_ROOT not in filtered:
    filtered[capability_negotiation.ORDER_ROOT] = config.get_server_version()
  return ResponseOrderSchema(
    version=config.get_server_version(),
    capabilities=_capability_map(filtered),
  )
