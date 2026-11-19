# These files are inputs the conformance validator must reject.
# A change that makes one of them pass is a validator bug, not a spec fix.

- `empty-lines.request.json` — transaction context with an empty `lines` array.
- `return-nonnegative-amount.request.json` — a return whose line amount is not negative.
- `sale-negative-quantity.request.json` — a sale line with a negative quantity.
- `unknown-error-code.json` — error code outside the registry.
- `classify-no-products.json` — classification request with no products.
- `webhook-missing-signature.json` — committed-tax webhook without `signature`.
- `manifest-stale-paths.json` — schema-valid manifest whose paths are not REST operations, including `/classify` and `/tax/void`, plus an `a2a` transport. The schema accepts it. The cross-artifact check must not.
- `mcp-bad-tool.json` — MCP tool whose `inputSchema` does not resolve.
