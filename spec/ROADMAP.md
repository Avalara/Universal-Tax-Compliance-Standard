# Roadmap

This list is the work that keeps envelope 1.0 at Draft, and the work that waits for a later version. An item moves to done only when the artifact it names has changed and `npm run validate` passes. Program tracking that lives outside this repository is not restated here.

## Later than envelope 1.0

Envelope 1.0 is US sales and use tax at checkout, B2C and B2B alike. The names below are reserved. Sketches live in [later/](later/) and are not validated as part of this version.

### VAT, GST, and other non-US tax

A later version covers VAT, GST, and other non-US tax, including VAT reverse charge and buyer VAT identifiers. These names are reserved and are not members of the envelope 1.0 schemas:

- `business_identification_no`, the seller's VAT or GST registration
- `tax_registration_ids`, the buyer's VAT or GST identifiers
- document types `reverse_charge` and `customs`
- `intra_community_supply` on `entity_use_code` and `exemption_reason`
- address roles `import` and `goods_place_or_service_rendered`. `addresses.bill_to` stays in envelope 1.0: California SB 122, effective 1 January 2027, sources SaaS and prewritten software by the billing address first, and [SPECIFICATION.md](SPECIFICATION.md#31-transaction-context) section 3.1 states that rule.
- `delivery_terms`, `is_seller_importer_of_record`, and line-item `hs_code` on the envelope 1.0 transaction schema. The experimental cross-border request carries them.
- tax types `vat`, `gst`, and `duty` on an envelope 1.0 tax result. The experimental cross-border result may use them.

`later/examples/determine-crossborder.request.json` and `determine-crossborder.response.json` are a US-to-Germany sale under DDP, with German VAT on the result. The Canadian HST sample is the experimental `POST /cross-border/calculate` example: a US shipment to Ontario, HST at 13 percent reported as `tax_type` `gst`, duties at zero under CUSMA, and a landed cost that adds shipping.

Open: which non-US regimes the next envelope covers, and whether reverse charge is a document type or a flag on the result.

### E-invoicing

`elr-reporting` is reserved. `UTCS-8001` and `UTCS-8002` are reserved codes. `mappings/ubl.md` is a UBL sketch for that later work. How a synchronous government acknowledgement would interact with checkout is undecided (item 4).

### Cross-border

The name `cross-border` is reserved. `POST /cross-border/calculate` and `utcs_calculate_duties` are published as Experimental. They are not in the v1.0 registry, and a provider MUST NOT advertise them. `UTCS-7001`, `UTCS-7002`, and `UTCS-7003` are reserved codes.

The published design covers duties, landed cost, a de minimis threshold, country of origin, HS classification, Incoterms, and importer of record. The Canadian HST sample is that shape for one US-to-Ontario shipment.

Open: whether cross-border is its own capability or an extension of tax determination; which party is liable when delivery terms and importer of record disagree; how a US sales-tax result and an import levy share one response.

### Filing obligations

The name `filing-obligations` is reserved. `GET /obligations` and `utcs_check_obligations` are published as Experimental. They are not in the v1.0 registry, and a provider MUST NOT advertise them.

The design to pick up is nexus accumulation, an economic-nexus threshold, filing frequency, and the next filing date.

Open: whether threshold monitoring is a provider report or a merchant-side aggregate of committed determinations.

### Webhooks

The webhook binding is Experimental. Checkout receives the tax result on the determination response. The manifest value `webhook` is reserved, and a provider MUST NOT advertise it.

Four payload schemas are in `schemas/webhooks/`, each marked experimental on the REST binding. The signing scheme is an HMAC over the raw body, carried in `signature`. A consumer rejects a payload that fails verification. `conformance/negative/webhook-missing-signature.json` is a body that fails that check.

| Event | Schema | Belongs with |
|-------|--------|--------------|
| `utcs.tax.committed` | `schemas/webhooks/tax-committed.schema.json` | a push of a committed result |
| `utcs.document.generated` | `schemas/webhooks/document-generated.schema.json` | compliance documents |
| `utcs.obligation.threshold_warning` | `schemas/webhooks/obligation-threshold-warning.schema.json` | `filing-obligations` |
| `utcs.obligation.threshold_crossed` | `schemas/webhooks/obligation-threshold-crossed.schema.json` | `filing-obligations` |

Open: which HMAC algorithm and which key the consumer uses, and whether delivery is at-least-once.

### Other deferred items

- **Entity use codes.** Whether `government` splits into federal, state and local.
- **Jurisdiction resolution.** Whether Core requires a jurisdiction tree with `tax_types`. The v1.0 contract stands.
- **Classification.** A categorical or optional `confidence`, a `tax_code_system` field, and namespaced `parameters`.
- **Compliance documents.** What `POST /documents` adds over the committed record, and audit actions.
- **Exemption validation.** Lookup by `customer_code` and jurisdiction, a verified or pending-review status, and `invalid_product`.
- **Per-line fields and addresses.** Marketplace and address roles per line, including a line-level `bill_to`; partial returns by line; and fallback addresses for bill-to sourcing (payment instrument, purchaser profile).
- **Invoice text.** Legally required invoice messages, with e-invoicing.
- **Attestation signature.** Optional in v1.0. A later version defines how it is produced and verified.
- **Transaction date.** Which local date governs `transaction_date`, since rates change at local midnight.

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
