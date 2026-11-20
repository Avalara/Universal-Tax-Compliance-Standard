# UTCS Specification Artifacts

Machine-readable specification for the **Universal Tax Compliance Standard (UTCS)**, envelope version **1.0**, status **Draft**. Normative prose is [SPECIFICATION.md](SPECIFICATION.md). Maturity of each artifact is [STATUS.md](STATUS.md). Open work is [ROADMAP.md](ROADMAP.md).

An implementation of this specification does not depend on any document outside `spec/`.

## Directory Structure

```
spec/
├── README.md                          ← This file
├── SPECIFICATION.md                   ← Normative prose
├── STATUS.md                          ← Stable / Draft / Experimental per artifact
├── ROADMAP.md                         ← Open questions and unpublished bindings
├── IMPLEMENTATIONS.md                 ← Informative reference implementation
├── registries/
│   ├── error-codes.json               ← UTCS-1001 through UTCS-8002
│   └── rest-operations.json           ← REST method and path registry
├── schemas/
│   ├── common/
│   │   ├── address.schema.json        ← Address structure (street or geocoordinate)
│   │   ├── line-item.schema.json      ← Transaction line item
│   │   ├── jurisdiction-breakdown.schema.json ← Single taxing-authority levy
│   │   ├── attestation.schema.json    ← Provider attestation / audit seal
│   │   └── error-response.schema.json ← Three-layer error model
│   ├── discovery-manifest.schema.json ← /.well-known/tax-compliance manifest
│   ├── transaction-context.schema.json← Canonical input envelope
│   ├── tax-result.schema.json         ← Canonical output envelope
│   ├── jurisdiction-resolution-request.schema.json
│   ├── jurisdiction-resolution-result.schema.json
│   ├── classification-request.schema.json
│   ├── classification-result.schema.json
│   ├── exemption-validation-request.schema.json
│   ├── exemption-validation-result.schema.json
│   └── webhooks/                      ← Four experimental webhook payload schemas
├── later/                             ← VAT/GST sketches, not part of envelope 1.0
│   └── examples/                      ← US-to-Germany determination
├── profiles/
│   └── us-sst.md                      ← US Streamlined Sales Tax conformance profile
├── mappings/
│   ├── ubl.md                         ← UTCS to OASIS UBL document mapping
│   └── examples/
│       └── utcs-to-ubl-invoice.md     ← Worked Tax Result to UBL Invoice tax block
├── bindings/
│   └── ucp.md                         ← UTCS binding for Universal Commerce Protocol
├── openapi/
│   └── utcs-v1.yaml                   ← OpenAPI 3.1, REST transport binding
├── mcp/
│   └── utcs-mcp-tools.json            ← MCP tool definitions (5 v1.0, 2 experimental)
├── examples/                          ← Validated sample request/response payloads
│   ├── determine-basic.request.json
│   ├── determine-basic.response.json
│   ├── determine-multijurisdiction.request.json
│   ├── determine-multijurisdiction.response.json
│   ├── determine-exempt.request.json
│   ├── determine-exempt.response.json
│   ├── determine-discount.request.json
│   ├── determine-discount.response.json
│   ├── determine-retail-delivery-fee.request.json
│   ├── determine-retail-delivery-fee.response.json
│   ├── error-insufficient-address.response.json
│   ├── discovery-manifest.example.json
│   ├── resolve-seattle.request.json
│   ├── resolve-seattle.response.json
│   ├── classify-products.request.json
│   ├── classify-products.response.json
│   ├── exemption-resale.request.json
│   ├── exemption-resale.response.json
│   ├── webhook-tax-committed.json
│   ├── webhook-document-generated.json
│   ├── webhook-obligation-warning.json
│   └── webhook-obligation-crossed.json
├── conformance/
│   ├── CERTIFICATION.md               ← Certification process (Experimental)
│   └── negative/                      ← Fixtures the validator must reject
├── scripts/
│   └── validate.mjs                   ← Conformance validator
├── redocly.yaml                       ← OpenAPI lint rules
└── package.json                       ← Validator deps and `npm run validate`
```

## Schemas (`schemas/`)

Schemas use **JSON Schema draft 2020-12**. Most identify themselves with an `$id` under `https://utcs.tax/schemas/`. The resolve request and result schemas are referenced from the OpenAPI document and use a file-relative `$ref` without an `$id`, so a bundler resolves the file instead of the identifier host. The normative rules are the schemas and [SPECIFICATION.md](SPECIFICATION.md). A third column, where present, is only a historical section number. It is not a link and not a dependency.

### Common Schemas

| File | Description | Origin |
|------|-------------|---------------|
| `address.schema.json` | Address with oneOf: text path (line1 + city + postal_code + country) or geocoordinate path (latitude + longitude + country). ISO 3166-1 alpha-2 country codes. Optional `location_code` is the seller's outlet code for local reporting. When several addresses carry one, the seller origin governs. | §4, §5 |
| `line-item.schema.json` | Line item with line_number, quantity, amount (decimal string). A negative quantity is allowed only on a return, and a return line's amount MUST be negative. Optional: item_code, description, tax_code (standard or custom value), tax_included, `discounted`, revenue_account, `entity_use_code` (per-line use-based exemption), per-line `exemption_certificate_id` (applied or the request fails `UTCS-5xxx`), per-line `addresses` (ship_from/ship_to override for drop-ship or split origin), per-line `tax_override`, parameters. | §6.2.3 |
| `jurisdiction-breakdown.schema.json` | Single jurisdiction levy: jurisdiction_type, jurisdiction_code, jurisdiction_code_system (fips/iso/provider-defined), tax_type (incl. sellers_use/consumer_use), tax_category (UBL UNCL 5305), `fee_basis` (ad_valorem / flat / per_unit) with `rate` required only for ad_valorem and `unit_rate`/`units` carrying per_unit levies, amounts, rate_rule_id, exemption_applied (with controlled exemption_reason). | §6.3.3 |
| `attestation.schema.json` | Provider attestation: provider_id, provider_name, content_version, calculation_timestamp, engine_version, optional signature. | §6 |
| `error-response.schema.json` | Three-layer error model: structured UTCS-XXXX code, human message, machine-actionable recovery hints. All error codes from UTCS-1001 through UTCS-8002. | §7 |

### Top-Level Schemas

| File | Description | Origin |
|------|-------------|---------------|
| `discovery-manifest.schema.json` | Provider discovery manifest served at `/.well-known/tax-compliance`. Declares capabilities, transports, authentication, input profiles, rounding configuration (SSUTA §324-aligned default), conformance_profiles, certification badges. | §4, §6.6, §6.8, §8, §9, §10 |
| `transaction-context.schema.json` | Canonical input for US sales and use tax at checkout. Required fields: document_type (incl. `void` and `return`), transaction_date, currency_code, commit, entity_type, addresses, lines. Optional: `document_code` (caller's key; the provider MAY generate one when it is omitted; a caller SHOULD send it when `commit` is true so `UTCS-6001` can reject a repeated commit), `company_code` (routes to the selling entity), customer (with `entity_use_code` for use-based exemption and `exemption_certificate_id`, which is applied or fails `UTCS-5xxx`), `discount`, `marketplace` (facilitator liability context), `reference_code` (on a return, reverses the original tax), `purchase_order_number`, `addresses.bill_to` (billing address for bill-to sourcing, including California SB 122), tax_override, parameters. | §6.2 |
| `tax-result.schema.json` | Canonical output. Strict structure: result_id (the provider's key, which MAY equal document_code), document_code (the caller's key when they sent one, otherwise provider-generated; not an echo of an omitted field), status, totals (decimal strings, incl. `total_non_taxable` and optional `total_discount`), currency_code, per-line amounts (taxable_amount, exempt_amount, `non_taxable_amount`, optional discount_amount), line-level jurisdictions (with tax_category, jurisdiction_code_system), an optional order-level `jurisdictions[]` rollup, and attestation. Optional line-level `tax_calculated` and result-level `total_tax_calculated` (engine amount before any tax_override), result-level `conformance[]` annotation, `messages[]` (info/warning/error notices; nexus-not-established is a warning, an estimated rate is not), and `adjustment` (set when status is `adjusted`). `document_id` is not a member; it exists only on a compliance document. | §6.3 |

## OpenAPI Specification (`openapi/`)

**`utcs-v1.yaml`** — Full OpenAPI 3.1.0 specification for the UTCS REST transport binding.

Covers:
- **7 v1.0 endpoints** across Core and Standard. Envelope 1.0 is US sales and use tax at checkout.
- **2 Experimental endpoints**: `POST /cross-border/calculate` and `GET /obligations`, marked `x-utcs-status: experimental` and kept out of the v1.0 registry
- **4 experimental webhooks**: tax committed, document generated, obligation threshold warning and crossed
- **3 security schemes**: Bearer token, OAuth 2.0 client credentials, API key
- **10 design principles**: protocol-agnostic through low barrier to entry
- **Worked examples**: request and response payloads on every endpoint — determination, jurisdiction resolution, classification, exemption validation, and compliance documents
- **X-UTCS-Input-Profile** header for input profile negotiation

### Endpoint Summary

| Method | Path | Capability | Tier |
|--------|------|------------|------|
| GET | `/.well-known/tax-compliance` | Discovery | — |
| POST | `/tax/determine` | tax-determination | Core |
| POST | `/jurisdictions/resolve` | jurisdiction-resolution | Core |
| POST | `/tax-codes/classify` | product-classification | Standard |
| POST | `/exemptions/validate` | exemption-validation | Standard |
| GET | `/documents/{document_id}` | compliance-documents | Standard |
| POST | `/documents` | compliance-documents | Standard |
| POST | `/cross-border/calculate` | cross-border | Experimental |
| GET | `/obligations` | filing-obligations | Experimental |

Paths are relative to the server URL, `https://{provider}/utcs/v1`. A void is `document_type: void` on `POST /tax/determine`. There is no `/tax/void` operation. `POST /tax-codes/classify` is the classification operation. There is no `/classify` operation.

## MCP Tool Definitions (`mcp/`)

**`utcs-mcp-tools.json`** — 5 v1.0 MCP tools, plus 2 Experimental tools that stay out of the v1.0 registry.

Tool names use the `utcs_` prefix (configurable via `tools_prefix` in the discovery manifest).

| Tool Name | Capability | Tier |
|-----------|------------|------|
| `utcs_determine_tax` | tax-determination@1.0 | Core |
| `utcs_resolve_jurisdictions` | jurisdiction-resolution@1.0 | Core |
| `utcs_classify_product` | product-classification@1.0 | Standard |
| `utcs_validate_exemption` | exemption-validation@1.0 | Standard |
| `utcs_get_document` | compliance-documents@1.0 | Standard |
| `utcs_calculate_duties` | cross-border@1.0 | Experimental |
| `utcs_check_obligations` | filing-obligations@1.0 | Experimental |

## Conformance Profiles (`profiles/`)

A conformance profile names the external tax standard a provider conforms to for a result. The provider declares supported profiles in its manifest (`conformance_profiles`), derives the governing profile during determination, and annotates the applied profile on the Tax Result `conformance` field. A profile carries no rate or boundary data; it maps an external standard onto the UTCS core. See [SPECIFICATION.md](SPECIFICATION.md) and [profiles/us-sst.md](profiles/us-sst.md).

| File | Profile | Scope |
|------|---------|-------|
| `us-sst.md` | `us-sst` | US Streamlined Sales Tax (SSUTA): CSP/CAS roles, FIPS jurisdiction codes, sourcing, SST library classification, F0003 exemptions, SSUTA §324 rounding, SSTRS registration. |

## Mappings (`mappings/`)

Mappings render a UTCS Tax Result into an external document or reporting format.

| File | Target | Notes |
|------|--------|-------|
| `ubl.md` | OASIS UBL 2.x | Later-version sketch for e-invoicing. Not part of envelope 1.0. |
| `examples/utcs-to-ubl-invoice.md` | UBL Invoice | Later-version sketch of a Tax Result as a UBL `cac:TaxTotal` (EU VAT). |

## Protocol Bindings (`bindings/`)

A binding carries UTCS into a specific commerce protocol, keeping UTCS semantics while adopting the host protocol's conventions.

| File | Protocol | Notes |
|------|----------|-------|
| `ucp.md` | Universal Commerce Protocol | Draft binding onto the UCP checkout lifecycle. Extension name `dev.ucp.shopping.tax`. The extension repository is not published at a public URL; this file is the public UTCS-side binding. |

## Examples (`examples/`)

Worked request and response payloads that validate against the schemas. The validator in `scripts/` checks every one on each run.

| File | Schema | Scenario |
|------|--------|----------|
| `determine-basic.request.json` / `.response.json` | transaction-context / tax-result | Single-line B2C sale into Austin, TX. Estimate (`commit: false`), three jurisdictions, order-level rollup. |
| `determine-multijurisdiction.request.json` / `.response.json` | transaction-context / tax-result | Two-line committed B2C sale into Los Angeles, CA, routed through a `marketplace` facilitator. State, county, district, and special levies per line, with the order-level `jurisdictions[]` rollup summed across both lines. |
| `determine-exempt.request.json` / `.response.json` | transaction-context / tax-result | B2B resale into Columbus, OH with an exemption certificate and a resale `entity_use_code`. Zero tax, `tax_category` E, `exemption_applied`, and a `us-sst` conformance annotation. |
| `determine-discount.request.json` / `.response.json` | transaction-context / tax-result | Two-line B2C sale into Austin, TX with an 80.00 document `discount` allocated across both `discounted` lines. Per-line `discount_amount` (20.00 / 60.00), taxable basis reduced before tax, `total_discount`, and `total_amount` held at the gross line sum. |
| `determine-retail-delivery-fee.request.json` / `.response.json` | transaction-context / tax-result | Two-line B2C sale delivered into Denver, CO. Line 1 carries ad_valorem sales tax (state + Denver + RTD + SCFD, 8.81%); line 2 is the Colorado retail delivery fee as a `fee_basis` `flat` levy (0.31 flat, no `rate`), exercising both branches of the fee-basis rule. |
| `determine-return.request.json` | transaction-context | Return of the basic sale (`reference_code` `SO-100432`): the one widget at 100.00, quantity -1, amount -100.00. The referenced original's tax is reversed, not recalculated. |
| `error-insufficient-address.response.json` | common/error-response | UTCS-3001 input error: destination address missing, with recovery hints. |
| `discovery-manifest.example.json` | discovery-manifest | Illustrative provider manifest. Hosts are under `example.com`. Certification badges show the schema; they are not a certification record. |

The order-level rollup and conformance annotations are deliberate: the rollup gives a per-jurisdiction total across all lines while the line-level breakdown is preserved, and only the Ohio example claims `us-sst` because it is the only example in a Streamlined Sales Tax member state.

The US-to-Germany determination is `later/examples/determine-crossborder.request.json` and `determine-crossborder.response.json`. It is not part of this validated set. The Canadian HST sample is the Experimental example on `POST /cross-border/calculate` in `openapi/utcs-v1.yaml`.

## Usage

### Validate the bundled examples

The conformance validator registers every schema, validates the worked examples, rejects the negative fixtures, lints the OpenAPI document with Redocly (including `$ref` resolution and embedded examples), compiles each MCP `inputSchema`, and checks the manifest, registries, and prose against each other.

```bash
cd spec
npm install
npm run validate
```

A passing run prints a check mark for each check and exits 0. Any failure prints the reason and exits 1. The pipeline that runs this on every merge request is `.gitlab-ci.yml` at the repository root. Node.js 24 is the pinned runtime (`.nvmrc`).

### Validate your own input/output against schemas

```bash
# Using ajv-cli (npm install -g ajv-cli)
ajv validate -s spec/schemas/transaction-context.schema.json -d my-request.json
ajv validate -s spec/schemas/tax-result.schema.json -d my-response.json
```

### Generate client/server stubs from OpenAPI

```bash
# Using openapi-generator
openapi-generator generate -i spec/openapi/utcs-v1.yaml -g python -o clients/python
openapi-generator generate -i spec/openapi/utcs-v1.yaml -g typescript-axios -o clients/typescript
```

### Register MCP tools

Load `spec/mcp/utcs-mcp-tools.json` into any MCP-compatible AI runtime. Each tool's `inputSchema` follows JSON Schema draft 2020-12 and can be validated independently.

## Versioning

These artifacts are envelope **1.0**, status **Draft**. The `utcs_version` field and the `/utcs/v1` base-URL prefix both name that envelope. Versioning rules are in [SPECIFICATION.md](SPECIFICATION.md). Per-artifact maturity is in [STATUS.md](STATUS.md).

## License

Apache License 2.0 — Copyright 2026 Avalara, Inc. The license text is
[LICENSE](../LICENSE). Attribution is in [NOTICE](../NOTICE).
