# Run the forked flower-shop merchant against the UTCS tax binding

The mock determination provider is in [`mock`](mock). It mounts the UCP binding in `src/bindings/ucp` and keeps an in-memory compliance record.

The merchant is forked into [`merchant`](merchant). The matching happy-path client is [`client`](client). Neither process edits the official UCP repositories. The changes a merchant must make are written up in [`merchant/TAX_HOOK.md`](merchant/TAX_HOOK.md) so the same hook can be applied to another example or another implementation.

The binding speaks `dev.ucp.shopping.tax`. Preview (`POST /checkout-sessions/{id}/$previewTax`) does not record anything. Completion (`POST /checkout-sessions/{id}/$determineTax`) forces commit and stores the `TaxResult`. `utcs_determine_tax` is the UTCS MCP tool on the same determine function. The flower-shop client calls only the merchant, and the merchant calls the HTTP binding.

The merchant and the client install `ucp-sdk` 0.4.6 from PyPI.

## What this example shows

A flower-shop buyer walks the ordinary UCP path: create a cart, add a second item, apply `10OFF`, open a checkout, pick a US shipping destination and the standard shipping option, then pay. The client talks only to the merchant. Tax appears only when the merchant calls the UTCS binding.

The same merchant demonstrates both outcomes. `--checkout_tax_extension_url` is the switch. An empty value means the merchant never calls the binding. `http://127.0.0.1:8080` means it does.

On the happy path the cart is a rose and a ceramic pot, **6500** minor units (65.00 USD). The 10% discount is an order-level discount, so the line subtotals stay 6500 and the amount due before tax is **5850**. The mock rate is 8.75% of those line subtotals: 6500 × 0.0875 = 568.75, which rounds half-up to **569**. The checkout total becomes 5850 + 569 = **6419**.

| | Without the tax extension | With UTCS (`dev.ucp.shopping.tax`) |
|---|---|---|
| How to run the merchant | Leave `--checkout_tax_extension_url` empty. The mock server can be stopped. | Point the flag at `http://127.0.0.1:8080` and run `utcs-ucp-mock`. |
| Discovery | `/.well-known/ucp` lists checkout, order, fulfillment, and payment. | The same profile also lists `dev.ucp.shopping.tax` extending checkout, with UTCS `config`: tier `core`, input profile `utcs-standard`, half-up rounding per line per jurisdiction, conformance `us-sst` `2025.1`. |
| Cart and discount | Unchanged. Totals are subtotal, discount, and total. | Unchanged. Tax is not known yet, because there is no ship-to. |
| After a shipping destination is selected | The merchant prices shipping and returns the checkout. No tax total. | The merchant `POST`s `$previewTax`. The binding turns minor units and `postal_address` into a UTCS `TransactionContext` (`commit: false`) and the mock returns a `TaxResult` with `status: calculated`. Nothing is stored. The checkout gains `tax.result` and a totals line `type: "tax"`, `amount: 569`. |
| Buyer-visible total | **5850** | **6419** |
| Completion | Payment, then the order is stored. | The merchant `POST`s `$determineTax` after payment is accepted and before the order is stored. The same calculation is stored in memory, keyed by the checkout id, with `status: committed` and an attestation (`provider_id` `utcs-mock`). |
| If tax cannot be determined | Nothing to fail. The order completes. | The merchant copies the error onto `checkout.messages`, leaves the tax total off, and does not invent a rate. A failed determine aborts completion, so no order is stored. |

`$previewTax` can run more than once. Selecting the destination and then the shipping option are both checkout updates, and each update previews again. Only `$determineTax` writes the compliance record.

The client flag `--tax_extension_url` only fetches the binding's discovery document and logs the tax total the merchant already put on the checkout. The client does not calculate tax.

## How it is built

Three processes, and only the merchant bridges the two protocols.

```text
flower-shop client          UCP checkout REST           flower-shop merchant
client                      ---------------------->        merchant
                                                             |
                                                             |  dev.ucp.shopping.tax
                                                             |  minor units, postal_address
                                                             v
                                                       src/bindings/ucp
                                                             |
                                                             |  TransactionContext / TaxResult
                                                             |  decimal strings
                                                             v
                                                       src/examples/ucp/mock
                                                       mock 8.75% engine
                                                       in-memory compliance record
```

UCP remains the commerce protocol: cart, checkout, fulfillment, payment, and order. UTCS is the calculation contract behind the binding. The mock stands in the provider port where AvaTax would sit later. It splits 8.75% into a state portion and a local portion, both half-up, and returns per-line and per-jurisdiction amounts. Preview (`commit: false`) returns `status: calculated` and writes nothing. Determine (`commit: true`) stores that `TaxResult` and returns `status: committed`.

`utcs_determine_tax` is a second door to that same function, over MCP, with decimal strings in and out. The flower-shop walk never calls it. It is there to show that the UCP binding and the UTCS core transport share one determination.

The merchant hook, and how to apply it to a different implementation, is [`merchant/TAX_HOOK.md`](merchant/TAX_HOOK.md).

## Upstream

| Upstream | What was forked |
|---|---|
| [samples](https://github.com/Universal-Commerce-Protocol/samples) `rest/python/server` | [`merchant`](merchant) |
| [samples](https://github.com/Universal-Commerce-Protocol/samples) `rest/python/client/flower_shop` | [`client`](client) |
| [python-sdk](https://github.com/Universal-Commerce-Protocol/python-sdk) | PyPI dependency `ucp-sdk` |
| [ucp](https://github.com/Universal-Commerce-Protocol/ucp) | Protocol specification, for reference while reading the binding |

## Setup

From the root of this repository:

```bash
uv sync --group dev
```

Prepare the flower-shop databases once:

```bash
cd src/examples/ucp/merchant
uv sync
mkdir -p /tmp/ucp_test
uv run import_csv.py \
  --products_db_path=/tmp/ucp_test/products.db \
  --transactions_db_path=/tmp/ucp_test/transactions.db \
  --data_dir=test_data/flower_shop
```

Install the client when you want the third terminal:

```bash
cd src/examples/ucp/client
uv sync
```

## Run

Terminal 1, from this repository:

```bash
uv run utcs-ucp-mock
```

The server listens on `127.0.0.1:8080` (`UTCS_REST_HOST` and `UTCS_REST_PORT` override that). Discovery is `GET /.well-known/ucp`.

Terminal 2, the forked merchant:

```bash
cd src/examples/ucp/merchant
uv run server.py \
  --products_db_path=/tmp/ucp_test/products.db \
  --transactions_db_path=/tmp/ucp_test/transactions.db \
  --port=8182 \
  --checkout_tax_extension_url=http://127.0.0.1:8080
```

Terminal 3, the forked happy-path client:

```bash
cd src/examples/ucp/client
uv run simple_happy_path_client.py \
  --server_url=http://127.0.0.1:8182 \
  --tax_extension_url=http://127.0.0.1:8080
```

A preview adds a `tax` total in minor units after a shipping destination is selected. Completion records the same result with `status: committed` on `checkout.tax.result`. The MCP tool is separate:

```bash
uv run utcs-ucp-mcp
```

It takes a UTCS `TransactionContext` (decimal strings) and returns a `TaxResult`.
