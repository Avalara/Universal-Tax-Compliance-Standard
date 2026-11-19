<!--
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
-->

<!-- disableFinding(LINK_RELATIVE_G3DOC) -->

# Simple Happy Path Client Script for UCP SDK.

This copy lives next to the forked merchant in the UTCS repo. Its platform profile lists `dev.ucp.shopping.tax` at `2026-04-08`. That is the only tax-specific change; see [TAX_HOOK.md](../merchant/TAX_HOOK.md).

## Scope

This script demonstrates a complete "happy path" user journey: 0. **Discovery**:
Querying the merchant to see what they support. 1. **Create Checkout**: Creating
a new checkout session (cart). 2. **Add Items**: Adding items to the checkout
session. 3. **Fulfillment**: Triggering fulfillment option generation, selecting
a destination, and choosing a shipping option. 4. **Complete**: Completing the
checkout by processing a payment.

## Prerequisites

1.  **Install Dependencies**: `uv sync`

    `uv sync` installs `ucp-sdk` from PyPI.

2.  **Start the Merchant Server**: You need a running UCP Merchant Server to
    execute this client against. Follow the instructions in the
    [merchant README](../merchant/README.md). The tax hook is
    [TAX_HOOK.md](../merchant/TAX_HOOK.md).

    _Quick start (from `../merchant/`):_

    ```shell
    uv run server.py \
      --products_db_path=/tmp/ucp_test/products.db \
      --transactions_db_path=/tmp/ucp_test/transactions.db \
      --port=8182 \
      --checkout_tax_extension_url=http://127.0.0.1:8080
    ```

## Web UI (happy path demo)

With the merchant server running (same as above), start the local demo app.
It runs the same happy path as the CLI in-process and lists every HTTP request
and response in the browser (default: [http://127.0.0.1:8765](http://127.0.0.1:8765)).

```bash
uv run happy_path_demo_app.py
```

Open the URL, optionally adjust the merchant or tax-extension URLs, then click
**Run happy path**.

## Running the Client

Once the server is running, you can execute the client script:

```bash
uv run simple_happy_path_client.py --server_url=http://localhost:8182
```

### Options

- `--server_url`: The base URL of the UCP Merchant Server (default:
  `http://localhost:8182`).
- `--export_requests_to`: Path to a markdown file where the request/response
  dialog will be logged.

  ```bash
  uv run simple_happy_path_client.py --export_requests_to=interaction_log.md
  ```

- `--disable_signatures`: Do not sign requests. By default the client signs
  every request per RFC 9421 with an ephemeral `ES256` key and publishes the
  matching public key from a small local profile server, so the merchant can
  discover the key (via the `UCP-Agent` header) and verify the signature. Pass
  this flag to send unsigned requests instead — useful when exporting a
  replayable dialog, since a real signature is bound to the request body and
  host.

## Automated Demo (extract_json_dialog.sh)

For a fully automated demonstration that sets up the database, starts the
server, runs the client, and generates a transaction log, use the included shell
script:

```bash
./extract_json_dialog.sh
```

This will output the interaction log to `/tmp/ucp_test/happy_path_dialog.md`.
