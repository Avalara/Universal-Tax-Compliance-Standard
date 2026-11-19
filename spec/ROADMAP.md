# Roadmap

This list is the work that keeps envelope 1.0 at Draft. An item moves to done only when the artifact it names has changed and `npm run validate` passes. Program tracking that lives outside this repository is not restated here.

## Blocks Stable

These questions are unresolved. The specification does not pick an answer for any of them.

1. **Capability extensions.** Whether a provider may publish a capability outside the registry, and under what namespace, is undecided.
2. **Idempotency.** Whether `document_code` plus `commit: true` MUST return the original result instead of committing twice is undecided. `UTCS-6001` covers a document code that is already committed; it does not by itself define a replay rule.
3. **Bulk operations.** No batch operation is specified. Whether one is required is undecided.
4. **Synchronous e-invoicing.** `elr-reporting` is not a capability in this version. How a synchronous government acknowledgement would interact with checkout is undecided. `UTCS-8001` and `UTCS-8002` are reserved codes only.
5. **Multiple providers.** Whether one merchant may split capabilities across providers, and how a consumer would discover that split, is undecided.
6. **Binding compatibility.** A binding states the envelope version it targets. A matrix policy beyond that is undecided.

## Alignment with other repositories

7. **`fee_basis` on the UCP extension.** Core UTCS has `ad_valorem`, `flat`, and `per_unit`. The `dev.ucp.shopping.tax` extension does not yet carry `fee_basis`. Until it does, a UCP mapping can drop a flat or per-unit levy. `bindings/ucp.md` states the requirement. The extension repository is separate and is not updated by this tree.
8. **Composed UCP validation.** The extension's composed check against a Universal Commerce Protocol checkout has not been run. The UCP binding stays Draft until that run is recorded.
9. **Public URL for the UCP extension.** The extension repository is not published at a public URL. `bindings/ucp.md` is the public UTCS-side binding. The extension name on this side is `dev.ucp.shopping.tax` and no other name.
10. **ACP scope.** Whether ACP is in scope for the first Stable envelope is undecided. No ACP binding will be added until that decision is made. AP2 is likewise unspecified.

## Transport and certification gaps

11. **A2A.** No binding document exists. The manifest value is reserved. Publish `bindings/a2a.md` or remove the reserved value in a later envelope.
12. **MCP generate-document.** `POST /documents` has no MCP tool. Add one or state explicitly that generation is REST-only.
13. **Certification registry.** The process in `conformance/CERTIFICATION.md` is Experimental. Badges in a manifest are claims until a registry records a supervised run. This repository does not operate that registry.
14. **Calculation fixtures.** The conformance suite checks structure and cross-artifact consistency. It does not yet include rate or boundary cases. Those cases require content that this specification deliberately does not ship.
15. **Public contact.** No monitored mailbox is designated. A contact email will be added only after one is confirmed to exist and to be monitored.
