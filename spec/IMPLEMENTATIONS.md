# Reference implementations

The specification is provider-neutral. Worked examples use the provider id `example-tax` and hosts under `example.com`, which is reserved by RFC 2606. Those examples are not a live service.

Avalara maintains an informative implementation of the UCP binding. It is not part of the published specification:

- `src/bindings/ucp/` maps checkout tax calls onto a UTCS Transaction Context and back.
- `src/examples/ucp/` is a mock determiner.
- `examples/merchant/TAX_HOOK.md` is the hook another merchant would copy.

That code speaks the extension name `dev.ucp.shopping.tax`. It is not part of the normative specification, and the normative examples do not name it.
