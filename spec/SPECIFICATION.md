# Universal Tax Compliance Standard (UTCS)

**Envelope version:** 1.0
**Status:** Draft
**Date:** 18 November 2026
**Maintainers:** UTCS maintainers
**License:** Apache License 2.0

This document is the normative prose for UTCS. The JSON Schemas under `schemas/`, the REST binding in `openapi/utcs-v1.yaml`, the MCP tools in `mcp/utcs-mcp-tools.json`, and the registries under `registries/` are normative machine-readable parts of the same specification. Worked examples are informative. A profile, mapping, or protocol binding is normative only for an implementation that claims that profile, mapping, or binding, and only at the maturity recorded in [STATUS.md](STATUS.md).

Strategy material that may sit beside this tree is not part of the specification. An implementation does not need it.

The key words MUST, MUST NOT, REQUIRED, SHOULD, SHOULD NOT, RECOMMENDED, MAY, and OPTIONAL in this document are to be interpreted as described in RFC 2119 and RFC 8174.

---

## 1. What conforming means

UTCS defines how tax compliance is requested and returned for a transaction. It does not define which commerce protocol started the transaction, and it does not define tax rates, boundaries, or product taxonomies. A provider supplies those. The specification supplies the envelope.

A **conforming provider** implements every Core capability it is required to implement, publishes a discovery manifest, and follows the error, security, and versioning rules in this document. Capabilities are grouped into tiers:

| Tier | Requirement | Capabilities |
|------|-------------|--------------|
| Core | MUST implement | `tax-determination`, `jurisdiction-resolution` |
| Standard | SHOULD implement | `product-classification`, `exemption-validation`, `compliance-documents` |
| Advanced | MAY implement | `cross-border`, `filing-obligations` |

A provider MUST NOT advertise a capability it does not implement. A consumer that requires a capability the provider does not advertise MUST NOT silently drop that requirement. The gap MUST be surfaced to the caller.

`elr-reporting` (e-invoicing and live reporting) is not a capability in this version. The `UTCS-8xxx` codes are reserved for it.

### 1.1 Capability identity and dependencies

A capability is named `name@major.minor`. The dependencies below are normative. A provider MUST NOT advertise a capability whose dependency it does not also advertise at a compatible version.

| Capability | Depends on |
|------------|------------|
| `tax-determination` | none |
| `jurisdiction-resolution` | none |
| `product-classification` | none |
| `exemption-validation` | `tax-determination` |
| `compliance-documents` | `tax-determination` |
| `cross-border` | `tax-determination`, `product-classification` |
| `filing-obligations` | `tax-determination`, `jurisdiction-resolution` |

### 1.2 Input and output

Input is flexible. A provider accepts one or more named input profiles and MUST accept `utcs-standard`. Output is strict. Every conforming provider returns a Tax Result in the shape defined by `schemas/tax-result.schema.json`. A consumer MUST be able to read that result without knowing which provider produced it.

A profile name in the manifest, including a name such as `utcs-ucp` or `utcs-acp`, identifies an input shape. It does not by itself publish a protocol binding. Bindings that exist are listed in [STATUS.md](STATUS.md).

---

## 2. Versioning

Two version spaces are independent.

**Envelope version** (`utcs_version` in the discovery manifest, and the `/utcs/v1` prefix on the REST base URL) covers discovery, the manifest, the error model, and the transport rules in this document. The envelope version of this text is `1.0`.

**Capability version** (`major.minor` on each capability) covers that capability's request and response.

- A major increment is a breaking change to that capability's schema. A consumer MUST NOT assume compatibility across majors.
- A minor increment is backward compatible: new optional fields, or a wider enumeration that older consumers can ignore. A consumer SHOULD ignore object members it does not recognize.
- Adding a capability does not force a provider to change capabilities it already implements.

The envelope version of a REST call is the `/utcs/v1` prefix on the provider base URL. A request body does not carry `utcs_version`. A provider MUST serve envelope 1.0 only under that prefix, MUST NOT treat a call to any other prefix as an envelope 1.0 request, and MUST NOT answer a call it cannot serve with a guessed tax amount. When the caller requires a capability the provider does not implement, the provider MUST reject the request with `UTCS-1002`.

Protocol bindings version independently. A binding MUST state the minimum envelope version it targets. No compatibility matrix beyond that statement is defined in this version; that is an open question recorded in [ROADMAP.md](ROADMAP.md).

This envelope is Draft. Artifact maturity is in [STATUS.md](STATUS.md). Nothing in this version is Stable while the open questions in the roadmap are unresolved.

---

## 3. Data model

The schemas are the field-level contract. This section states the rules that apply across them.

### 3.1 Transaction Context

`schemas/transaction-context.schema.json` is the canonical input to tax determination.

A provider MUST enforce these constraints:

- `lines` MUST contain at least one line. An empty array MUST be rejected with `UTCS-3001`.
- `addresses` MUST include `ship_from` and `ship_to`, or `single_location` for a point-of-sale transaction. Otherwise the provider MUST reject the request with `UTCS-3001`.
- `document_type` and `entity_type` MUST be members of the enumerations in the schema. Any other value MUST be rejected with `UTCS-3002`. A provider MUST NOT substitute a default.
- `transaction_date` MUST be a valid RFC 3339 datetime. A date outside the provider's supported range MUST be rejected with `UTCS-4004`.
- `currency_code` MUST be an ISO 4217 code the provider supports.
- Every monetary amount MUST be a decimal string. A provider MUST NOT require or return a binary floating-point amount.

`document_type` includes `void`. A void is a tax-determination request with `document_type` of `void`, sent to `POST /tax/determine`. There is no `/tax/void` operation. When the document to void cannot be found, the provider MUST return `UTCS-6002`.

### 3.2 Tax Result

`schemas/tax-result.schema.json` is the canonical output. A provider MUST return this structure for a successful determination. Jurisdiction, tax type, tax category, and `fee_basis` are provider outputs. The caller does not select them.

`fee_basis` has three values:

| Value | Meaning | Required members |
|-------|---------|------------------|
| `ad_valorem` | `tax_amount` equals `taxable_amount` multiplied by `rate`. This is the default when `fee_basis` is omitted. | `rate` |
| `flat` | A fixed statutory amount. `rate` does not apply. | none beyond the common required members |
| `per_unit` | `tax_amount` equals `unit_rate` multiplied by `units`. | `unit_rate`, `units` |

### 3.3 Other request and response bodies

These schemas are normative for their operations:

| Operation | Request | Response |
|-----------|---------|----------|
| `POST /jurisdictions/resolve` | `schemas/jurisdiction-resolution-request.schema.json` | `schemas/jurisdiction-resolution-result.schema.json` |
| `POST /tax-codes/classify` | `schemas/classification-request.schema.json` | `schemas/classification-result.schema.json` |
| `POST /exemptions/validate` | `schemas/exemption-validation-request.schema.json` | `schemas/exemption-validation-result.schema.json` |

### 3.4 Accuracy over availability

If a provider cannot determine tax accurately, it MUST return an error from the registry in section 4. It MUST NOT return an approximate rate, a default rate, or a guessed amount in place of that error.

### 3.5 Attestation

Every successful Tax Result MUST include the attestation block defined by `schemas/common/attestation.schema.json`. The attestation identifies the provider, the content version, the engine version, and the calculation time. A signature MAY be present. Trust levels are defined in section 6.

---

## 4. Error model

An error response MUST contain three layers, as defined by `schemas/common/error-response.schema.json`:

1. A `code` from the registry below.
2. A human-readable `message`.
3. A `recovery` object whose `action` is one of `provide_additional_data`, `retry`, `retry_or_block`, `use_alternative_capability`, `contact_provider`, or `not_recoverable`.

`category` MUST match the registry row for that code. A service-unavailability error (`UTCS-1001`) MUST include `recovery.compliance_warning` describing the risk of completing the transaction without a determination, and SHOULD include `retry_after_seconds`.

The registry is also published as `registries/error-codes.json`. The schema enumeration and that file MUST list the same codes. Codes are stable within an envelope major version. A provider MUST NOT invent a `UTCS-` code outside this registry.

| Code | Category | Meaning |
|------|----------|---------|
| `UTCS-1001` | service | Provider temporarily unavailable |
| `UTCS-1002` | service | Capability not implemented |
| `UTCS-1003` | service | Rate limit exceeded |
| `UTCS-2001` | authentication | Invalid or expired credentials |
| `UTCS-2002` | authentication | Insufficient scope for the requested capability |
| `UTCS-3001` | input | Required field missing |
| `UTCS-3002` | input | Invalid field value or unrecognized enumeration |
| `UTCS-3003` | input | Unrecognized input profile |
| `UTCS-3004` | input | Line item validation failure |
| `UTCS-4001` | tax_resolution | Jurisdiction unresolvable from the provided address |
| `UTCS-4002` | tax_resolution | Tax code not recognized |
| `UTCS-4003` | tax_resolution | Country not supported |
| `UTCS-4004` | tax_resolution | Transaction date outside the supported range |
| `UTCS-5001` | exemption | Exemption certificate not found |
| `UTCS-5002` | exemption | Exemption certificate expired |
| `UTCS-5003` | exemption | Exemption not valid for the jurisdiction |
| `UTCS-5004` | exemption | Exemption not valid for the product |
| `UTCS-6001` | document | Document code already committed |
| `UTCS-6002` | document | Document not found for void or adjustment |
| `UTCS-7001` | cross_border | HS code classification failed |
| `UTCS-7002` | cross_border | Country of origin required but not provided |
| `UTCS-7003` | cross_border | Trade agreement validation failed |
| `UTCS-8001` | elr | Reporting submission failed. Reserved. `elr-reporting` is not a capability in this version. |
| `UTCS-8002` | elr | Reporting format not supported for the jurisdiction. Reserved. `elr-reporting` is not a capability in this version. |

---

## 5. Transport bindings

The same data model applies on every transport. A provider declares the transports it implements in the discovery manifest. A consumer chooses one.

Operation paths below are relative to the REST base URL. That base URL includes the envelope prefix `/utcs/v1`. The machine-readable list is `registries/rest-operations.json`. A manifest endpoint path MUST be one of these operations for the capability it claims. The normative list:

| Method | Path | Capability |
|--------|------|------------|
| GET | `/.well-known/tax-compliance` | discovery |
| POST | `/tax/determine` | `tax-determination` |
| POST | `/jurisdictions/resolve` | `jurisdiction-resolution` |
| POST | `/tax-codes/classify` | `product-classification` |
| POST | `/exemptions/validate` | `exemption-validation` |
| GET | `/documents/{document_id}` | `compliance-documents` |
| POST | `/documents` | `compliance-documents` |
| POST | `/cross-border/calculate` | `cross-border` |
| GET | `/obligations` | `filing-obligations` |

There is no `/tax/void` path and no `/classify` path.

REST requirements:

- Endpoints MUST be served over TLS 1.2 or higher.
- Bodies MUST be `application/json`.
- The input profile MUST be carried in the `X-UTCS-Input-Profile` header or a `profile` member. If neither is present, the provider MUST assume `utcs-standard`.
- Authentication MUST use a method the manifest declares.

### 5.1 MCP

The MCP binding exposes one tool per capability that has a tool in `mcp/utcs-mcp-tools.json`. Tool names use the manifest `tools_prefix`, default `utcs_`. Each `inputSchema` is a JSON Schema and MUST compile. The tools in this version are:

| Tool | Capability |
|------|------------|
| `utcs_determine_tax` | `tax-determination` |
| `utcs_resolve_jurisdictions` | `jurisdiction-resolution` |
| `utcs_classify_product` | `product-classification` |
| `utcs_validate_exemption` | `exemption-validation` |
| `utcs_get_document` | `compliance-documents` |
| `utcs_calculate_duties` | `cross-border` |
| `utcs_check_obligations` | `filing-obligations` |

`POST /documents` has no separate MCP tool in this version. Retrieval is `utcs_get_document`.

### 5.2 Webhooks

Four events are specified. Each payload schema lives under `schemas/webhooks/`. A provider that sends webhooks MUST sign the raw body and put the signature in `signature`. A consumer MUST reject a payload that fails verification.

| Event | Schema |
|-------|--------|
| `utcs.tax.committed` | `schemas/webhooks/tax-committed.schema.json` |
| `utcs.document.generated` | `schemas/webhooks/document-generated.schema.json` |
| `utcs.obligation.threshold_warning` | `schemas/webhooks/obligation-threshold-warning.schema.json` |
| `utcs.obligation.threshold_crossed` | `schemas/webhooks/obligation-threshold-crossed.schema.json` |

### 5.3 A2A

No Agent-to-Agent binding is published in this version. The manifest enumeration value `a2a` is reserved. A provider MUST NOT advertise `a2a` until `bindings/a2a.md` exists. Advertising it in this version is non-conformant.

### 5.4 Protocol bindings

A protocol binding maps this envelope onto a commerce protocol. It does not change the calculation contract.

| Binding | Status |
|---------|--------|
| Universal Commerce Protocol | Draft. See `bindings/ucp.md`. The extension name is `dev.ucp.shopping.tax`. |
| ACP | Not specified. Whether ACP is in scope is undecided. See [ROADMAP.md](ROADMAP.md). |
| AP2 | Not specified. |

---

## 6. Security

Tax payloads contain personal data, financial data, and compliance records.

- Every transport MUST use TLS 1.2 or higher. There is no exception for discovery.
- A provider MUST declare at least one of `bearer_token`, `oauth2_client_credentials`, `mtls`, or `api_key`, and MUST support that method on every authenticated operation.
- A provider SHOULD support OAuth 2.0 client credentials for production use. When that method is declared, `token_endpoint` MUST be present.
- A provider MUST NOT accept credentials on a non-TLS endpoint.

Authentication failures use `UTCS-2001` and `UTCS-2002`.

### 6.1 Trust

Trust is signaled, not granted by the protocol.

1. **Self-declaration.** Any party MAY publish a manifest and serve the envelope. The manifest states identity, capabilities, and endpoints.
2. **Attestation.** Every successful result carries the attestation block. A consumer MAY accept or reject a provider on that identity.
3. **Certification.** A badge in the manifest is a claim. It is an issued certification only when a registry named by the certification process records it. The process and its current limit are in [conformance/CERTIFICATION.md](conformance/CERTIFICATION.md). Certification is OPTIONAL. An uncertified provider MAY still conform to this specification.

---

## 7. Governance

The specification is maintained by the UTCS maintainers. Copyright is held by Avalara, Inc. The text is licensed under the Apache License 2.0. A move to a neutral standards body is a roadmap item, not a fact about this version. No monitored public mailbox is designated in this version; the contact recorded on the REST binding is the name "UTCS Maintainers" and nothing further.

A change to a normative artifact is proposed as follows:

1. The proposer writes the change, the motivation, the capabilities affected, and the compatibility impact.
2. The proposal is available for comment for at least 30 days.
3. The maintainers accept, amend, or reject it, and publish the reason.
4. An accepted change lands in the envelope or capability version named in the decision.

The conformance suite that guards this repository is described in [conformance/CERTIFICATION.md](conformance/CERTIFICATION.md). It checks artifacts against each other. It does not score tax rates.

---

## 8. Discovery

A provider MUST publish its manifest at `GET /.well-known/tax-compliance`. The schema is `schemas/discovery-manifest.schema.json`. The manifest MUST include `utcs_version`, provider identity, capabilities, transports, authentication, input profiles (including `utcs-standard`), and rounding.

Rounding's default is half-up to the ISO 4217 minor unit, applied per line and per jurisdiction. A provider MUST declare the method and granularity it actually uses, including when a jurisdiction requires a different rule.
