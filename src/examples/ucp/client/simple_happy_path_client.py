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

"""Simple Happy Path Client Script for UCP SDK.

This script demonstrates a basic "happy path" user journey:
0. Discovery: Querying the merchant to see what they support.
1. Creating a new checkout session (cart).
2. Adding items to the checkout session.
3. Applying a discount code.
4. Triggering fulfillment option generation.
5. Selecting a fulfillment destination.
6. Selecting a fulfillment option.
7. Completing the checkout by processing a payment.

Usage:
  uv run simple_happy_path_client.py --server_url=http://localhost:8182

  For UTCS tax (dev.ucp.shopping.tax), run the merchant with
  --checkout_tax_extension_url=http://127.0.0.1:8080. This script logs the
  negotiated tax capability and any tax totals on the checkout.
"""

import argparse
from dataclasses import dataclass
import functools
import http.server
import json
import logging
import socketserver
import ssl
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any
import uuid
import httpx
import signing
from ucp_sdk.models.schemas.shopping import cart_create_request
from ucp_sdk.models.schemas.shopping import cart_update_request
from ucp_sdk.models.schemas.shopping import checkout_update_request
from ucp_sdk.models.schemas.shopping.types import buyer_create_request
from ucp_sdk.models.schemas.shopping.types import item_create_request
from ucp_sdk.models.schemas.shopping.types import item_update_request
from ucp_sdk.models.schemas.shopping.types import line_item_create_request
from ucp_sdk.models.schemas.shopping.types import line_item_update_request


# Set by main() when request signing is enabled; the profile URL published by
# the local key server, referenced by the UCP-Agent header so the merchant can
# discover the signing key.
_SIGNING_PROFILE_URL: str | None = None
_PLATFORM_PROFILE_URL: str | None = None
_interaction_sink: list[dict[str, Any]] | None = None


def get_headers() -> dict[str, str]:
  """Generate necessary headers for UCP requests.

  When signing is enabled the UCP-Agent header points at the demo's local key
  server (the signature itself is added by the httpx auth flow). The web demo
  passes a platform profile instead. Otherwise the header falls back to the
  historical placeholder and the legacy request-signature header.
  """
  headers = {
    "idempotency-key": str(uuid.uuid4()),
    "request-id": str(uuid.uuid4()),
  }
  if _SIGNING_PROFILE_URL:
    headers["UCP-Agent"] = f'profile="{_SIGNING_PROFILE_URL}"'
  elif _PLATFORM_PROFILE_URL:
    headers["UCP-Agent"] = f'profile="{_PLATFORM_PROFILE_URL}"'
  else:
    headers["UCP-Agent"] = 'profile="https://agent.example/profile"'
    headers["request-signature"] = "test"
  return headers


def _openssl_localhost_cert_pem() -> tuple[str, str]:
  """Create a short-lived self-signed cert for 127.0.0.1."""
  tmp = Path(tempfile.mkdtemp(prefix="ucp_platform_profile_tls_"))
  key = str(tmp / "key.pem")
  cert = str(tmp / "cert.pem")
  subprocess.run(
    [
      "openssl",
      "req",
      "-x509",
      "-newkey",
      "rsa:2048",
      "-nodes",
      "-keyout",
      key,
      "-out",
      cert,
      "-days",
      "1",
      "-subj",
      "/CN=127.0.0.1",
    ],
    check=True,
    capture_output=True,
    timeout=30,
  )
  return cert, key


def _start_local_platform_profile_server(
  profile_dir: Path,
) -> tuple[socketserver.ThreadingTCPServer, str]:
  """Serve ``profile_dir`` on 127.0.0.1 and return the server and profile URL.

  Uses HTTPS so UCP-Agent profile URIs can use the https scheme. Falls back
  to HTTP if ``openssl`` is unavailable.
  """
  handler_cls = functools.partial(
    http.server.SimpleHTTPRequestHandler,
    directory=str(profile_dir),
  )
  httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler_cls)
  httpd.daemon_threads = True
  httpd.allow_reuse_address = True
  scheme = "http"
  try:
    cert_pem, key_pem = _openssl_localhost_cert_pem()
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=cert_pem, keyfile=key_pem)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    scheme = "https"
  except (FileNotFoundError, subprocess.CalledProcessError, OSError) as exc:
    logging.warning(
      "HTTPS platform profile server unavailable (%s); using HTTP.",
      exc,
    )
  threading.Thread(target=httpd.serve_forever, daemon=True).start()
  _host, port = httpd.server_address
  uri = f"{scheme}://127.0.0.1:{port}/platform_profile.json"
  return httpd, uri


_TAX_CAPABILITY = "dev.ucp.shopping.tax"


def log_checkout_tax_section(
  logger: logging.Logger,
  checkout_json: dict[str, object],
  step_label: str,
) -> None:
  """Log negotiated tax capability and advisory tax totals for a checkout."""
  logger.info("--- Tax (advisory preview) · %s ---", step_label)
  ucp = checkout_json.get("ucp")
  caps = ucp.get("capabilities") if isinstance(ucp, dict) else None
  if isinstance(caps, dict) and _TAX_CAPABILITY in caps:
    logger.info(
      "  Negotiated %s → version %s",
      _TAX_CAPABILITY,
      caps[_TAX_CAPABILITY],
    )
  else:
    logger.info(
      "  %s not present on checkout.ucp.capabilities (pruned or N/A).",
      _TAX_CAPABILITY,
    )
  totals_raw = checkout_json.get("totals")
  if not isinstance(totals_raw, list):
    logger.info("  (No totals list in response.)")
    return
  tax_amounts = [
    str(row.get("amount"))
    for row in totals_raw
    if isinstance(row, dict) and row.get("type") == "tax"
  ]
  if tax_amounts:
    logger.info(
      "  Advisory tax in totals: %s minor unit(s) [%s]",
      len(tax_amounts),
      ", ".join(tax_amounts),
    )
  else:
    logger.info(
      "  No `tax` line in totals yet (often appears after a ship-to address "
      "and with --checkout_tax_extension_url on the merchant)."
    )


def log_tax_extension_well_known_ucp(
  logger: logging.Logger,
  tax_extension_base_url: str,
) -> None:
  """GET ``{base}/.well-known/ucp`` on the tax extension and log a summary."""
  base = tax_extension_base_url.strip().rstrip("/")
  if not base:
    return
  url = f"{base}/.well-known/ucp"
  try:
    response = httpx.get(url, timeout=5.0)
  except httpx.RequestError as exc:
    logger.warning("Could not GET tax extension discovery %s (%s)", url, exc)
    return
  if response.status_code != 200:
    logger.warning(
      "Tax extension discovery %s returned HTTP %s",
      url,
      response.status_code,
    )
    return
  try:
    doc = response.json()
  except json.JSONDecodeError:
    logger.warning("Tax extension discovery at %s is not JSON", url)
    return
  logger.info("--- Tax extension /.well-known/ucp (%s) ---", base)
  ucp = doc.get("ucp") if isinstance(doc, dict) else None
  if not isinstance(ucp, dict):
    return
  caps = ucp.get("capabilities")
  if isinstance(caps, dict) and _TAX_CAPABILITY in caps:
    rows = caps[_TAX_CAPABILITY]
    if rows:
      logger.info("  ucp.capabilities[%s]: %s", _TAX_CAPABILITY, rows[0])
  elif isinstance(caps, list):
    for item in caps:
      if isinstance(item, dict) and item.get("name") == _TAX_CAPABILITY:
        logger.info("  ucp.capabilities entry: %s", item)
        break


def log_order_tax_section(
  logger: logging.Logger,
  order_json: dict[str, object],
) -> None:
  """Log tax capability on a completed order, if present."""
  ucp = order_json.get("ucp")
  caps = ucp.get("capabilities") if isinstance(ucp, dict) else None
  if isinstance(caps, dict) and _TAX_CAPABILITY in caps:
    logger.info(
      "--- Tax on completed order · negotiated %s → %s ---",
      _TAX_CAPABILITY,
      caps[_TAX_CAPABILITY],
    )


def remove_none_values(obj):
  """Recursively remove keys with None values from a dictionary or list."""
  if isinstance(obj, dict):
    return {k: remove_none_values(v) for k, v in obj.items() if v is not None}
  elif isinstance(obj, list):
    return [remove_none_values(v) for v in obj]
  else:
    return obj


@dataclass
class HappyPathResult:
  """Outcome of :func:`run_happy_path`."""

  ok: bool
  error_message: str | None = None
  order_id: str | None = None
  order_permalink: str | None = None


def log_interaction(
  filename: str | None,
  method: str,
  url: str,
  headers: dict[str, str],
  json_body: dict[str, object] | None,
  response: httpx.Response,
  step_description: str,
  replacements: dict[str, str] | None = None,
  extractions: dict[str, str] | None = None,
):
  """Log one request for markdown export and the web demo."""
  replacements = replacements or {}
  extractions = extractions or {}
  if _interaction_sink is not None:
    try:
      response_body: object = response.json()
    except json.JSONDecodeError:
      response_body = response.text
    _interaction_sink.append(
      {
        "step": step_description,
        "method": method,
        "url": url,
        "request_headers": dict(headers),
        "request_body": json_body,
        "status_code": response.status_code,
        "response_body": response_body,
      }
    )
  if not filename:
    return

  with Path(filename).open("a", encoding="utf-8") as f:
    f.write(f"## {step_description}\n\n")

    # --- Request (Curl) ---
    # Apply replacements to URL
    display_url = url
    for val, var_name in replacements.items():
      if val in display_url:
        display_url = display_url.replace(val, f"${var_name}")

    curl_cmd = f"export RESPONSE=$(curl -s -X {method} {display_url} \\\n"

    # Headers
    # We generally don't tokenize headers in this simple script,
    # but could if needed.
    for k, v in headers.items():
      curl_cmd += f"  -H '{k}: {v}' \\\n"

    # Body
    if json_body:
      curl_cmd += "  -H 'Content-Type: application/json' \\\n"
      clean_body = remove_none_values(json_body)
      json_str = json.dumps(clean_body, indent=2)

      # Apply replacements to body
      for val, var_name in replacements.items():
        # Simple string replacement - safer to do on the JSON string
        # than traversing the dict for this doc-gen purpose.
        if val in json_str:
          json_str = json_str.replace(val, f"${var_name}")

      curl_cmd += f"  -d '{json_str}')\n"
    else:
      curl_cmd = curl_cmd.rstrip(" \\\n") + ")\n"

    f.write("### Request\n\n```bash\n" + curl_cmd + "```\n\n")

    # --- Response ---

    f.write("### Response\n\n")

    try:
      resp_json = response.json()
      clean_resp = remove_none_values(resp_json)
      f.write("```json\n" + json.dumps(clean_resp, indent=2) + "\n```\n\n")
    except json.JSONDecodeError:
      f.write(f"```\n{response.text}\n```\n\n")

    # --- Extract Variables ---
    if extractions:
      f.write("### Extract Variables\n\n```bash\n")
      for var_name, jq_expr in extractions.items():
        # We assume the user has the response in a variable or pipe.
        # For the snippet, we'll assume they pipe the previous curl output.
        f.write(f"export {var_name}=$(echo $RESPONSE | jq -r '{jq_expr}')\n")
      f.write("```\n\n")


def main() -> int:
  """Run the happy path client."""
  parser = argparse.ArgumentParser()

  parser.add_argument(
    "--server_url",
    default="http://localhost:8182",
    help="Base URL of the UCP Server",
  )

  parser.add_argument(
    "--export_requests_to",
    default=None,
    help="Path to export requests and responses as markdown.",
  )

  parser.add_argument(
    "--tax_extension_url",
    default="",
    help=(
      "Base URL of the checkout tax extension. After merchant discovery, "
      "GET /.well-known/ucp on this host is logged. Empty skips the call."
    ),
  )

  parser.add_argument(
    "--disable_signatures",
    action="store_true",
    help=(
      "Do not sign requests. By default the client signs every request with "
      "an ephemeral ES256 key and publishes the public key from a local "
      "profile server for the merchant to verify."
    ),
  )

  args = parser.parse_args()

  # Configure Logging

  logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
  )

  logger = logging.getLogger(__name__)

  signer = None
  if not args.disable_signatures:
    global _SIGNING_PROFILE_URL
    signer, profile_server = signing.build_signer()
    profile_server.start()
    _SIGNING_PROFILE_URL = profile_server.profile_url
    logger.info(
      "Signing requests with an ephemeral ES256 key; publishing it at %s",
      _SIGNING_PROFILE_URL,
    )

  client = httpx.Client(base_url=args.server_url, auth=signer)

  # Clear the export file if it exists
  if args.export_requests_to:
    with Path(args.export_requests_to).open("w", encoding="utf-8") as f:
      f.write("""<!--
   Copyright 2026 UCP Authors

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

Note:
   This file is automatically generated by running simple_happy_path_client.py.
   Do not modify manually.
-->
""")
      f.write("# UCP Happy Path Interaction Log\n\n")
      f.write("### Configuration\n\n")
      f.write(f"```bash\nexport SERVER_URL={args.server_url}\n```\n\n")
      f.write(
        "> **Note:** In the bash snippets below, `jq` is used to extract"
        " values from the JSON response.\n"
      )
      f.write(
        "> It is assumed that the response body of the previous `curl`"
        " command is captured in a variable named `$RESPONSE`.\n\n"
      )

  try:
    result = run_happy_path(
      logger=logger,
      client=client,
      server_url=args.server_url,
      platform_profile_uri="",
      tax_extension_url=args.tax_extension_url or "",
      export_requests_to=args.export_requests_to,
      interactions_out=None,
    )
    return 0 if result.ok else 1
  finally:
    client.close()


def run_happy_path(
  *,
  logger: logging.Logger,
  client: httpx.Client,
  server_url: str,
  platform_profile_uri: str,
  tax_extension_url: str,
  export_requests_to: str | None,
  interactions_out: list[dict[str, Any]] | None,
) -> HappyPathResult:
  """Execute the cart-to-order happy path and optionally record each call."""
  global _PLATFORM_PROFILE_URL, _interaction_sink
  _PLATFORM_PROFILE_URL = platform_profile_uri or None
  _interaction_sink = interactions_out
  global_replacements: dict[str, str] = {server_url: "SERVER_URL"}

  try:
    # ==========================================================================

    # STEP 0: Discovery

    # ==========================================================================

    logger.info("STEP 0: Discovery - Asking merchant what they support...")

    url = "/.well-known/ucp"

    response = client.get(url)

    if export_requests_to or _interaction_sink is not None:
      log_interaction(
        export_requests_to,
        "GET",
        f"{server_url}{url}",
        {},
        None,
        response,
        "Step 0: Discovery",
        replacements=global_replacements,
      )

    if response.status_code != 200:
      logger.error("Discovery failed: %s", response.text)

      return HappyPathResult(ok=False, error_message="Happy path stopped")

    discovery_data = response.json()

    # Discovery profiles are wrapped in a top-level `ucp` object per the UCP
    # discovery schema; fall back to the root for flat/legacy profiles.
    ucp_data = discovery_data.get("ucp", discovery_data)

    supported_handlers = []
    for handlers in ucp_data.get("payment_handlers", {}).values():
      supported_handlers.extend(handlers)

    logger.info(
      "Merchant supports %d payment handlers:", len(supported_handlers)
    )

    for h in supported_handlers:
      logger.info(" - %s (%s)", h["id"], h["name"])

    caps = ucp_data.get("capabilities", {})
    logger.info("--- Tax (discovery) ---")
    tax_ad = None
    if isinstance(caps, dict):
      rows = caps.get(_TAX_CAPABILITY)
      if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        tax_ad = rows[0].get("version")
    elif isinstance(caps, list):
      for cap in caps:
        if isinstance(cap, dict) and cap.get("name") == _TAX_CAPABILITY:
          tax_ad = cap.get("version")
          break
    if tax_ad is not None:
      logger.info(
        "  Merchant advertises %s (version %s).", _TAX_CAPABILITY, tax_ad
      )
    else:
      logger.info(
        "  %s not listed in discovery (tax preview unavailable).",
        _TAX_CAPABILITY,
      )
    tax_ext_base = (tax_extension_url or "").strip()
    if tax_ext_base:
      log_tax_extension_well_known_ucp(logger, tax_ext_base)

    # ==========================================================================

    # ==========================================================================
    # STEP 1: Create a Cart
    # ==========================================================================

    logger.info("\nSTEP 1: Creating a new Cart...")

    # We start with one item: "Red Rose"
    item1 = item_create_request.ItemCreateRequest(id="bouquet_roses")
    line_item1 = line_item_create_request.LineItemCreateRequest(
      quantity=1, item=item1
    )

    # We include the buyer
    buyer_request = buyer_create_request.BuyerCreateRequest(
      full_name="John Doe", email="john.doe@example.com"
    )

    create_payload = cart_create_request.CartCreateRequest(
      line_items=[line_item1],
      buyer=buyer_request,
    )

    headers = get_headers()
    url = "/carts"

    json_body = create_payload.model_dump(
      mode="json", by_alias=True, exclude_none=True
    )

    response = client.post(
      url,
      json=json_body,
      headers=headers,
    )

    cart_data = response.json()
    cart_id = cart_data.get("id")

    # Extract IDs for documentation
    extractions = {}
    if cart_id:
      global_replacements[cart_id] = "CART_ID"
      extractions["CART_ID"] = ".id"

    if cart_data.get("line_items"):
      li_id = cart_data["line_items"][0]["id"]
      global_replacements[li_id] = "LINE_ITEM_1_ID"
      extractions["LINE_ITEM_1_ID"] = ".line_items[0].id"

    if export_requests_to or _interaction_sink is not None:
      log_interaction(
        export_requests_to,
        "POST",
        f"{server_url}{url}",
        headers,
        json_body,
        response,
        "Step 1: Create Cart",
        replacements=global_replacements,
        extractions=extractions,
      )

    if response.status_code not in [200, 201]:
      logger.error("Failed to create cart: %s", response.text)
      return HappyPathResult(ok=False, error_message="Happy path stopped")

    logger.info("Successfully created cart: %s", cart_id)
    logger.info("Current Total: %s cents", cart_data["totals"][-1]["amount"])

    # ==========================================================================
    # STEP 2: Add More Items (Update Cart)
    # ==========================================================================

    logger.info("\nSTEP 2: Adding a second item (Ceramic Pot)...")

    # Update Item 1 (Roses) - Keep quantity 1
    item1_update = item_update_request.ItemUpdateRequest(id="bouquet_roses")
    line_item1_update = line_item_update_request.LineItemUpdateRequest(
      id=cart_data["line_items"][0]["id"],
      quantity=1,
      item=item1_update,
    )

    # Add Item 2 (Ceramic Pot) - Quantity 2
    item2_update = item_update_request.ItemUpdateRequest(id="pot_ceramic")
    line_item2_update = line_item_update_request.LineItemUpdateRequest(
      quantity=2,
      item=item2_update,
    )

    # Construct the Update Payload
    update_payload = cart_update_request.CartUpdateRequest(
      id=cart_id,
      line_items=[line_item1_update, line_item2_update],
    )

    headers = get_headers()
    url = f"/carts/{cart_id}"

    json_body = update_payload.model_dump(
      mode="json", by_alias=True, exclude_none=True
    )

    response = client.put(
      url,
      json=json_body,
      headers=headers,
    )

    cart_data = response.json()
    extractions = {}

    if len(cart_data.get("line_items", [])) > 1:
      li_2_id = cart_data["line_items"][1]["id"]
      global_replacements[li_2_id] = "LINE_ITEM_2_ID"
      extractions["LINE_ITEM_2_ID"] = ".line_items[1].id"

    if export_requests_to or _interaction_sink is not None:
      log_interaction(
        export_requests_to,
        "PUT",
        f"{server_url}{url}",
        headers,
        json_body,
        response,
        "Step 2: Add Items (Update Cart)",
        replacements=global_replacements,
        extractions=extractions,
      )

    if response.status_code != 200:
      logger.error("Failed to add items: %s", response.text)
      return HappyPathResult(ok=False, error_message="Happy path stopped")

    logger.info("Successfully added items.")
    logger.info("New Total: %s cents", cart_data["totals"][-1]["amount"])
    logger.info("Item Count: %d", len(cart_data["line_items"]))

    # ==========================================================================
    # STEP 3: Apply Discount to Cart
    # ==========================================================================

    logger.info("\nSTEP 3: Applying Discount (10%% OFF) to Cart...")

    li_1 = next(
      li
      for li in cart_data["line_items"]
      if li["item"]["id"] == "bouquet_roses"
    )
    li_2 = next(
      li for li in cart_data["line_items"] if li["item"]["id"] == "pot_ceramic"
    )

    item1_update = item_update_request.ItemUpdateRequest(id="bouquet_roses")
    line_item1_update = line_item_update_request.LineItemUpdateRequest(
      id=li_1["id"],
      quantity=1,
      item=item1_update,
    )

    item2_update = item_update_request.ItemUpdateRequest(id="pot_ceramic")
    line_item2_update = line_item_update_request.LineItemUpdateRequest(
      id=li_2["id"],
      quantity=2,
      item=item2_update,
    )

    update_payload = cart_update_request.CartUpdateRequest(
      id=cart_id,
      line_items=[line_item1_update, line_item2_update],
    )

    update_dict = update_payload.model_dump(
      mode="json", by_alias=True, exclude_none=True
    )
    update_dict["discounts"] = {"codes": ["10OFF"]}

    headers = get_headers()
    url = f"/carts/{cart_id}"
    json_body = update_dict

    response = client.put(
      url,
      json=json_body,
      headers=headers,
    )

    if export_requests_to or _interaction_sink is not None:
      log_interaction(
        export_requests_to,
        "PUT",
        f"{server_url}{url}",
        headers,
        json_body,
        response,
        "Step 3: Apply Discount to Cart",
        replacements=global_replacements,
      )

    if response.status_code != 200:
      logger.error("Failed to apply discount: %s", response.text)
      return HappyPathResult(ok=False, error_message="Happy path stopped")

    cart_data = response.json()
    logger.info("Successfully applied discount to cart.")
    logger.info("New Total: %s cents", cart_data["totals"][-1]["amount"])

    discounts_applied = cart_data.get("discounts", {}).get("applied", [])
    if discounts_applied:
      logger.info(
        "Applied Discounts: %s", [d["code"] for d in discounts_applied]
      )
    else:
      logger.warning("No discounts applied!")

    # ==========================================================================
    # STEP 4: Convert Cart to Checkout (Create Checkout Session)
    # ==========================================================================

    logger.info("\nSTEP 4: Creating Checkout Session from Cart...")

    # We only need cart_id. The server will inherit everything else from
    # the cart as per UCP Cart-to-Checkout conversion specification.
    checkout_payload = {
      "cart_id": cart_id,
    }

    headers = get_headers()
    url = "/checkout-sessions"
    json_body = checkout_payload

    response = client.post(
      url,
      json=json_body,
      headers=headers,
    )

    checkout_data = response.json()
    checkout_id = checkout_data.get("id")

    extractions = {}
    if checkout_id:
      global_replacements[checkout_id] = "CHECKOUT_ID"
      extractions["CHECKOUT_ID"] = ".id"

    if export_requests_to or _interaction_sink is not None:
      log_interaction(
        export_requests_to,
        "POST",
        f"{server_url}{url}",
        headers,
        json_body,
        response,
        "Step 4: Create Checkout Session from Cart",
        replacements=global_replacements,
        extractions=extractions,
      )

    if response.status_code not in [200, 201]:
      logger.error("Failed to create checkout from cart: %s", response.text)
      return HappyPathResult(ok=False, error_message="Happy path stopped")

    logger.info(
      "Successfully created checkout session from cart: %s", checkout_id
    )
    logger.info(
      "Current Total: %s cents", checkout_data["totals"][-1]["amount"]
    )
    log_checkout_tax_section(logger, checkout_data, "step 4 · create checkout")

    # ==========================================================================

    # STEP 5: Select Fulfillment Option

    # ==========================================================================

    logger.info("\nSTEP 5: Selecting Fulfillment Option...")

    # Ensure fulfillment options are generated

    if not checkout_data.get("fulfillment") or not checkout_data[
      "fulfillment"
    ].get("methods"):
      logger.info("STEP 5: Triggering fulfillment option generation...")

      # Re-construct line items for update to satisfy strict validation

      # We need IDs from the current session

      li_1 = next(
        li
        for li in checkout_data["line_items"]
        if li["item"]["id"] == "bouquet_roses"
      )

      li_2 = next(
        li
        for li in checkout_data["line_items"]
        if li["item"]["id"] == "pot_ceramic"
      )

      item1_update = item_update_request.ItemUpdateRequest(id="bouquet_roses")

      line_item1_update = line_item_update_request.LineItemUpdateRequest(
        id=li_1["id"],
        quantity=1,
        item=item1_update,
      )

      item2_update = item_update_request.ItemUpdateRequest(id="pot_ceramic")

      line_item2_update = line_item_update_request.LineItemUpdateRequest(
        id=li_2["id"],
        quantity=2,
        item=item2_update,
      )

      # Construct full update payload

      trigger_request = checkout_update_request.CheckoutUpdateRequest(
        id=checkout_id,
        line_items=[line_item1_update, line_item2_update],
        currency=checkout_data["currency"],
        payment=checkout_data.get("payment"),
        fulfillment={
          "methods": [
            {
              "id": "method_1",
              "type": "shipping",
              "line_item_ids": [li_1["id"], li_2["id"]],
            }
          ]
        },
      )

      trigger_payload = trigger_request.model_dump(
        mode="json", by_alias=True, exclude_none=True
      )

      url = f"/checkout-sessions/{checkout_id}"

      headers = get_headers()

      response = client.put(url, json=trigger_payload, headers=headers)

      checkout_data = response.json()

      # Extract Fulfillment Method ID (though not always needed if we have
      # just 1)

      extractions = {}

      if checkout_data.get("fulfillment") and checkout_data["fulfillment"].get(
        "methods"
      ):
        method_id = checkout_data["fulfillment"]["methods"][0]["id"]

        global_replacements[method_id] = "FULFILLMENT_METHOD_ID"

        extractions["FULFILLMENT_METHOD_ID"] = ".fulfillment.methods[0].id"

        # Also destinations

        destinations = checkout_data["fulfillment"]["methods"][0].get(
          "destinations", []
        )

        if destinations:
          # Assuming addr_1 is first

          dest_id = destinations[0]["id"]

          global_replacements[dest_id] = "DESTINATION_ID"

          extractions["DESTINATION_ID"] = (
            ".fulfillment.methods[0].destinations[0].id"
          )

      if export_requests_to or _interaction_sink is not None:
        log_interaction(
          export_requests_to,
          "PUT",
          f"{server_url}{url}",
          headers,
          trigger_payload,
          response,
          "Step 5: Trigger Fulfillment",
          replacements=global_replacements,
          extractions=extractions,
        )

      if response.status_code == 200:
        checkout_data = response.json()

      else:
        logger.warning("Failed to trigger fulfillment: %s", response.text)

    if checkout_data.get("fulfillment") and checkout_data["fulfillment"].get(
      "methods"
    ):
      method = checkout_data["fulfillment"]["methods"][0]

      if method.get("destinations"):
        dest_id = method["destinations"][0]["id"]

        logger.info("STEP 6: Selecting destination: %s", dest_id)

        # 1. Select Destination to calculate options

        # We must send full payload again

        trigger_request.fulfillment = {
          "methods": [
            {
              "id": "method_1",
              "type": "shipping",
              "line_item_ids": [li_1["id"], li_2["id"]],
              "selected_destination_id": dest_id,
            }
          ]
        }

        payload = trigger_request.model_dump(
          mode="json", by_alias=True, exclude_none=True
        )

        url = f"/checkout-sessions/{checkout_id}"

        headers = get_headers()

        response = client.put(
          url,
          json=payload,
          headers=headers,
        )

        if export_requests_to or _interaction_sink is not None:
          log_interaction(
            export_requests_to,
            "PUT",
            f"{server_url}{url}",
            headers,
            payload,
            response,
            "Step 6: Select Destination",
            replacements=global_replacements,
          )

        if response.status_code != 200:
          logger.error("Failed to select destination: %s", response.text)

          return HappyPathResult(ok=False, error_message="Happy path stopped")

        checkout_data = response.json()

        # 2. Select Option

        method = checkout_data["fulfillment"]["methods"][0]

        if method.get("groups") and method["groups"][0].get("options"):
          option_id = method["groups"][0]["options"][0]["id"]

          logger.info("STEP 7: Selecting option: %s", option_id)

          trigger_request.fulfillment = {
            "methods": [
              {
                "id": "method_1",
                "type": "shipping",
                "line_item_ids": [li_1["id"], li_2["id"]],
                "selected_destination_id": dest_id,
                "groups": [
                  {
                    "id": "group_1",
                    "line_item_ids": [li_1["id"], li_2["id"]],
                    "selected_option_id": option_id,
                  }
                ],
              }
            ]
          }

          payload = trigger_request.model_dump(
            mode="json", by_alias=True, exclude_none=True
          )

          headers = get_headers()

          response = client.put(
            url,
            json=payload,
            headers=headers,
          )

          if export_requests_to or _interaction_sink is not None:
            log_interaction(
              export_requests_to,
              "PUT",
              f"{server_url}{url}",
              headers,
              payload,
              response,
              "Step 7: Select Option",
              replacements=global_replacements,
            )

          if response.status_code != 200:
            logger.error("Failed to select option: %s", response.text)

            return HappyPathResult(ok=False, error_message="Happy path stopped")

          checkout_data = response.json()

          logger.info("Fulfillment option selected.")

          logger.info(
            "Updated Total: %s cents", checkout_data["totals"][-1]["amount"]
          )
          log_checkout_tax_section(
            logger, checkout_data, "step 7 · fulfillment selected"
          )

    # ==========================================================================

    # STEP 8: Complete Checkout (Payment)

    # ==========================================================================

    logger.info("\nSTEP 8: Processing Payment...")

    # We use the 'mock_payment_handler' discovered in Step 0.

    # In a real app, you'd match a handler ID (e.g. 'gpay') to your client

    # logic.

    target_handler = "mock_payment_handler"

    if not any(h["id"] == target_handler for h in supported_handlers):
      logger.error("Merchant does not support %s. Aborting.", target_handler)

      return HappyPathResult(ok=False, error_message="Happy path stopped")

    # Create Payment Data (Single Instrument) using strong types

    # Matches the structure expected by the server's updated complete_checkout

    final_payload = {
      "payment": {
        "instruments": [
          {
            "id": "instr_my_card",
            "handler_id": target_handler,
            "type": "card",
            "display": {
              "brand": "Visa",
              "last_digits": "4242",
            },
            "credential": {
              "type": "token",
              "token": "success_token",
            },
            "billing_address": {
              "street_address": "123 Main St",
              "address_locality": "Anytown",
              "address_region": "CA",
              "address_country": "US",
              "postal_code": "12345",
            },
          }
        ]
      },
      "signals": {
        "com.example.ip": "127.0.0.1",
        "com.example.browser": "python-httpx",
      },
    }

    headers = get_headers()

    url = f"/checkout-sessions/{checkout_id}/complete"

    response = client.post(
      url,
      json=final_payload,
      headers=headers,
    )

    final_data = response.json()

    extractions = {}

    if final_data.get("order") and final_data["order"].get("id"):
      order_id = final_data["order"]["id"]

      global_replacements[order_id] = "ORDER_ID"

      extractions["ORDER_ID"] = ".order.id"

    if export_requests_to or _interaction_sink is not None:
      log_interaction(
        export_requests_to,
        "POST",
        f"{server_url}{url}",
        headers,
        final_payload,
        response,
        "Step 8: Complete Checkout",
        replacements=global_replacements,
        extractions=extractions,
      )

    if response.status_code != 200:
      logger.error("Payment failed: %s", response.text)

      return HappyPathResult(ok=False, error_message="Happy path stopped")

    logger.info("Payment Successful!")

    logger.info("Checkout Status: %s", final_data["status"])

    logger.info("Order ID: %s", final_data["order"]["id"])

    logger.info("Order Permalink: %s", final_data["order"]["permalink_url"])
    log_checkout_tax_section(logger, final_data, "step 8 · complete")
    order_obj = final_data.get("order")
    if isinstance(order_obj, dict):
      log_order_tax_section(logger, order_obj)

    # ==========================================================================

    # DONE

    # ==========================================================================

    logger.info("\nHappy Path completed successfully.")
    order = final_data.get("order") if isinstance(final_data, dict) else None
    return HappyPathResult(
      ok=True,
      order_id=(
        str(order["id"])
        if isinstance(order, dict) and order.get("id")
        else None
      ),
      order_permalink=(
        str(order["permalink_url"])
        if isinstance(order, dict) and order.get("permalink_url")
        else None
      ),
    )
  except Exception:  # pylint: disable=broad-exception-caught
    logger.exception("An unexpected error occurred:")
    return HappyPathResult(ok=False, error_message="Unexpected error")


if __name__ == "__main__":
  sys.exit(main())
