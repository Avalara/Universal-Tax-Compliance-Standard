# Merchant hook for `dev.ucp.shopping.tax`

This flower-shop server is the official Python merchant sample with one hook added: while a checkout is open it asks the UTCS UCP binding for tax, and on completion it commits that result before the order is stored. The binding itself stays in [`src/bindings/ucp`](../../../bindings/ucp) and [`src/examples/ucp/mock`](../mock). Copy this behavior into another merchant. The flower-shop store, catalog, and payment handlers are not part of the hook.

Upstream of the unmodified sample: [Universal-Commerce-Protocol/samples](https://github.com/Universal-Commerce-Protocol/samples) `rest/python/server`. This tree also carries the capability-negotiation code from the local `schema-update` checkout (`d0ecb28`). `ucp-sdk` 0.4.6 is installed from PyPI by `uv sync`.

## What any merchant does

1. **Advertise the capability** on `GET /.well-known/ucp`. Name `dev.ucp.shopping.tax`, extending `dev.ucp.shopping.checkout`, version `2026-04-08`. `spec` is the binding's `/.well-known/ucp`. `schema` is its OpenAPI document. `config` carries UTCS discovery: `tier` `core`, `input_profiles` `["utcs-standard"]`, `rounding` half-up per line per jurisdiction, `conformance_profiles` `us-sst` `2025.1`.

2. **Negotiate it** with the platform. Keep the negotiated version and the `UCP-Agent` header on the checkout until preview has run. A platform profile that lists capabilities must include `dev.ucp.shopping.tax` at `2026-04-08` or the capability is pruned. This merchant treats a profile with no capability list as "every capability the merchant advertises."

3. **Preview** with `POST {tax_base}/checkout-sessions/{checkout_id}/$previewTax` after the buyer has selected a shipping destination, and again whenever that checkout is updated. Skip the call when the tax base URL is empty, the capability was not negotiated, there is no selected ship-to, or there is no `UCP-Agent`.

4. **Apply the preview.** On HTTP 200 and an empty `messages` list, store the returned `tax` object on the checkout and add a totals entry `type: "tax"` whose `amount` is `tax.result.total_tax` (minor units, including `0`). On a transport failure, a non-200, or any `messages[]` entry with `type: "error"`, add those messages to the checkout and leave the tax total off. Do not invent an amount.

5. **Commit** with `POST {tax_base}/checkout-sessions/{checkout_id}/$determineTax` during completion, after payment and fulfillment are valid and before the order is stored. The same failure cases abort completion. A successful response replaces `checkout.tax` with the committed object (`tax.result.status` is `committed`).

6. **Send this body** for both calls. Amounts in `line_items` stay minor units. `tax.commit` is `false` for preview and `true` for determine; the binding forces that flag from the route, and sending it keeps the body honest.

```json
{
  "currency": "USD",
  "line_items": [],
  "fulfillment": {},
  "tax": {
    "document_code": "<checkout id>",
    "effective_at": "2026-11-18T12:00:00Z",
    "entity_type": "b2c",
    "commit": false,
    "ship_from": {
      "street_address": "9 Warehouse Way",
      "address_locality": "Seattle",
      "address_region": "WA",
      "postal_code": "98101",
      "address_country": "US"
    },
    "lines": [
      {"id": "<line_items[].id>", "tax_classification": {"code": "<item id or merchant tax code>"}}
    ]
  }
}
```

`ship_to` is not a separate field. The binding reads the selected fulfillment destination, which uses the same `postal_address` names. `UCP-Agent` must use an `https` profile URL. This sample rewrites a loopback `http://127.0.0.1` or `http://localhost` profile to `https` before the call. When completion no longer has the original header, send `profile="https://agent.example/profile"`.

An order-level discount that is not allocated onto line subtotals is not subtracted by the binding. Taxable amount is the line `totals` subtotal unless `tax.lines[].taxable_amount` overrides it.

## Where this fork implements it

| Step | Location |
|---|---|
| Capability advertisement | `checkout_extension_registry.py` `load_default_extensions` |
| Base URL and ship-from | `config.py` flags `checkout_tax_extension_url`, `checkout_tax_ship_from_json` |
| Negotiated versions and `UCP-Agent` kept until preview | `routes/ucp_implementation.py` `resolve_platform_config`; `models.py` `CheckoutPlatform` |
| Public checkout drops that request-time state | `services/checkout_service.py` `_publish_platform` |
| Preview call site | `services/checkout_service.py` `_enrich_and_recalculate` calls `_preview_checkout_tax` |
| Commit call site | `services/checkout_service.py` `complete_checkout` calls `_commit_checkout_tax` before inventory reservation |
| Body, HTTP, totals, messages | `_tax_request_body`, `_post_tax`, `_attach_tax`, `_append_tax_messages` in the same file |

`CheckoutPlatform` is not part of the tax protocol. The SDK `PlatformSchema` requires `webhook_url`, and a signing profile often has none. The subclass makes that field optional so checkout creation still succeeds. Another merchant can keep its own platform object, as long as negotiated versions and `UCP-Agent` are still available when preview runs.

## Platform side

The happy-path client in [`src/examples/ucp/client`](../client) lists the capability in `platform_profile.json`:

```json
"dev.ucp.shopping.tax": [{"version": "2026-04-08"}]
```

A client that already accepts extra fields on the checkout does not need a new model. The tax object rides on the checkout response. The client should tolerate a missing tax total until a ship-to exists.
