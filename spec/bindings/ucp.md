# UTCS Binding: Universal Commerce Protocol (UCP)

**Status:** Draft v0.1
**Applies to:** UTCS v1.0 core (`../schemas/`), which is itself Draft. See [../STATUS.md](../STATUS.md).
**UCP-side reference:** extension `dev.ucp.shopping.tax`

This binding carries UTCS into the Universal Commerce Protocol. It sits beside the REST and MCP transport bindings. The calculation contract is unchanged, and the same canonical Tax Result comes back. What changes is how the request rides UCP's checkout lifecycle and how amounts and identifiers follow UCP conventions. No Agent-to-Agent binding is published in this version.

The UCP-native expression is the extension `dev.ucp.shopping.tax`. Its repository is not published at a public URL. This document is the public UTCS-side binding. Where the two differ in detail, the extension governs UCP wire format and this document governs UTCS semantics. The only extension name used here is `dev.ucp.shopping.tax`.

Requirement levels (MUST, SHOULD, MAY) follow RFC 2119.

---

## 1. Principle

Keep UTCS semantics, adopt UCP conventions. A determination still takes facts (addresses, entity type, lines, exemption claims) and returns a provider-derived result (tax type, category, jurisdiction breakdown). UCP decides the casing, the money representation, and the moment in checkout when tax is determined.

## 2. Conventions

| Concern | UTCS core | UCP binding |
|---------|-----------|-------------|
| JSON casing | `snake_case` | `snake_case` (unchanged) |
| Currency amounts | decimal strings (`"49.99"`) | integer minor units (`4999`) per ISO 4217 |
| Tax rates | decimal strings | decimal strings (unchanged; ratios, not currency) |
| Dates | RFC 3339 | RFC 3339 (unchanged) |
| Line identity | `line_number` | checkout `line_items[].id` |
| Addresses | UTCS `Address` (text/geo `oneOf`) | UCP `postal_address` plus optional lat/long |

Minor-unit conversion is the one substantive transform. A provider converts decimal-string amounts to minor units on the way out and back on the way in, using the ISO 4217 minor-unit exponent for the transaction currency.

## 3. Discovery

| UTCS core | UCP binding |
|-----------|-------------|
| `/.well-known/tax-compliance` manifest | `/.well-known/ucp` capability declaration plus `config` |
| `capabilities[].tier` | `config.tier` on the capability entry |
| `input_profiles` | `config.input_profiles` |
| `rounding` | `config.rounding` |
| `conformance_profiles` | `config.conformance_profiles` |
| `certification` | `config` (optional, provider-defined) |

## 4. Lifecycle

UTCS uses a `commit` flag to separate an estimate from a recorded transaction. UCP expresses the same split through its checkout operations.

| UTCS | UCP binding |
|------|-------------|
| Determine with `commit: false` | Rides on `update_checkout`, or an explicit `POST /checkout-sessions/{id}/$previewTax` |
| Determine with `commit: true` | Rides on `complete_checkout`; completion forces commit |

A preview never records a transaction. Completion records one.

## 5. Request mapping

| UTCS `TransactionContext` | UCP `tax` input |
|---------------------------|-----------------|
| `document_type` | implied by the operation (preview versus complete) |
| `document_code` | `tax.document_code` |
| `transaction_date` | `tax.effective_at` |
| `currency_code` | read from the checkout `currency` |
| `commit` | `tax.commit` (completion forces it true) |
| `entity_type` | `tax.entity_type` |
| `customer.exemption_certificate_id` | `tax.exemptions[].certificate_id` |
| `addresses.ship_from` | `tax.ship_from` |
| `addresses.ship_to` | read from the checkout fulfillment destination |
| `lines[].line_number` | `tax.lines[].id` (= `line_items[].id`) |
| `lines[].amount` | read from `line_items[].totals`, or `tax.lines[].taxable_amount` override |
| `lines[].tax_code` | `tax.lines[].tax_classification.code` |

The UTCS line `tax_code` carries the caller's classification hint and maps onto the UCP classification code. A caller passes a Library of Definitions term, an internal code, or a custom value; the provider owns the final classification.

## 6. Response mapping

| UTCS `TaxResult` | UCP `tax.result` |
|------------------|------------------|
| `result_id` | carried in `attestation` if surfaced |
| `status` | `status` |
| `total_tax` (decimal string) | `total_tax` (minor units) |
| `total_taxable` / `total_exempt` | `total_taxable` / `total_exempt` (minor units) |
| `lines[].line_number` | `lines[].id` |
| `lines[].tax_amount` | `lines[].tax_amount` (minor units) |
| `lines[].tax_code` | `lines[].tax_classification.code` |
| `lines[].jurisdictions[]` | `lines[].jurisdictions[]`, including `fee_basis`, `rate`, `unit_rate`, and `units` |
| `jurisdictions[]` (order-level rollup) | `tax.result.jurisdictions[]` (minor units) |
| `attestation` | `attestation` |
| `conformance` | `conformance` |

## 7. Conformance profiles

The conformance profile travels unchanged. The provider declares its profiles in `config.conformance_profiles`, derives which one applies, and annotates the applied profile on the result `conformance` field. The caller does not select a profile in a UCP request any more than it does in a REST request.

## 8. Error model

UTCS uses three-layer `UTCS-####` codes with recovery hints. UCP separates protocol failures (transport) from business outcomes (HTTP 200 with `messages[]`). The binding maps UTCS domain failures onto `messages[]`.

| UTCS category | `messages[]` code (suggested) | severity |
|---------------|-------------------------------|----------|
| `UTCS-3xxx` (input) | `tax_insufficient_data`, `field_required` | recoverable |
| `UTCS-3002` (unrecognized enum) | `tax_invalid_classification` | recoverable |
| `UTCS-4xxx` (tax resolution) | `tax_invalid_location`, `tax_unsupported_jurisdiction` | requires_buyer_input / unrecoverable |
| `UTCS-5xxx` (exemption) | `eligibility_invalid` | recoverable |
| `UTCS-2xxx` (auth) | UCP protocol `401` | n/a |
| `UTCS-1xxx` (service) | UCP `503` with `Retry-After` | n/a |

The accuracy-over-availability rule holds. A determination failure becomes an error message, and at checkout an escalation, never a guessed rate. A provider MAY keep the precise `UTCS-####` code in its own diagnostics for audit while `messages[]` drives platform behavior.

## 9. Deferred capabilities

The checkout-shaped binding covers tax determination, classification, and exemption validation. The following UTCS capabilities are not cart-shaped and are out of scope for the shopping extension. They are proposed as a future standalone `dev.ucp.tax.*` service:

- `compliance-documents`
- `elr-reporting`
- `filing-obligations`
- standalone `jurisdiction-resolution`, `product-classification`, and `cross-border` outside a checkout

## 10. Scope

This binding delivers the MVP surface: determine tax during checkout, classify, validate exemptions, and return the canonical result under UCP conventions. The deferred capabilities and a full `dev.ucp.tax.*` service are future work.

## 11. Alignment still open

These items are unresolved. They are why this binding stays Draft.

- **`fee_basis`.** Core UTCS has three values: `ad_valorem`, `flat`, and `per_unit`. A mapping MUST preserve `fee_basis`, and `unit_rate` and `units` when `fee_basis` is `per_unit`. The `dev.ucp.shopping.tax` extension does not yet define `fee_basis`. Until it does, a UCP payload can drop a flat or per-unit levy. Closing that gap is a change to the extension, which is a separate repository.
- **Composed validation.** The extension's composed check against a Universal Commerce Protocol checkout has not been run. This binding's wire mapping is not conformance-tested against the UCP meta-schema.
- **ACP.** No ACP binding is specified. Whether ACP is in scope is undecided. This document does not define one.
- **A2A.** No A2A binding is published. See [../ROADMAP.md](../ROADMAP.md).
