# Artifact status

Envelope version **1.0** is **Draft**. It covers US sales and use tax at checkout, for B2C and B2B alike, as the specification stands today. VAT, GST, and other non-US tax, including VAT reverse charge and buyer VAT identifiers, are a later version, as is e-invoicing. Cross-border duties, filing obligations, and webhooks are Experimental. A Draft artifact is normative for implementers and may still change in a compatible or incompatible way before it is marked Stable. An Experimental artifact is published so it can be tried; conforming to the envelope does not require implementing it. Nothing is Stable while the open questions in [ROADMAP.md](ROADMAP.md) are unresolved.

Date of this table: 19 November 2026.

| Artifact | Status | Notes |
|----------|--------|-------|
| [SPECIFICATION.md](SPECIFICATION.md) | Draft | Normative prose: conformance, data model, errors, security, governance, versioning. Section 1 states the v1.0 scope. |
| `schemas/transaction-context.schema.json`, `schemas/tax-result.schema.json`, `schemas/discovery-manifest.schema.json`, `schemas/common/` | Draft | Core envelope schemas. US sales and use tax at checkout. |
| `schemas/jurisdiction-resolution-*.schema.json`, `schemas/classification-*.schema.json`, `schemas/exemption-validation-*.schema.json` | Draft | Request and response bodies for resolve, classify, and exemption validation. |
| `openapi/utcs-v1.yaml` | Draft | REST binding. Seven v1.0 operations. `POST /cross-border/calculate` and `GET /obligations` are Experimental and stay out of the v1.0 registry. |
| `schemas/webhooks/` | Experimental | Four webhook payloads. Checkout still receives the tax result on the determination response. |
| `mcp/utcs-mcp-tools.json` | Draft | Five v1.0 tools. `utcs_calculate_duties` and `utcs_check_obligations` are Experimental. |
| `registries/` | Draft | Error codes and REST operations. Checked against the schemas and the OpenAPI document. `UTCS-7xxx` and `UTCS-8xxx` are reserved. |
| `profiles/us-sst.md` | Draft | US Streamlined Sales Tax profile. |
| `bindings/ucp.md` | Draft | UCP binding, v0.1. Extension name `dev.ucp.shopping.tax`. |
| `examples/` | Draft | Informative examples of this version. Validated on every `npm run validate`. |
| `conformance/` validator and negative fixtures | Experimental | Schema, lint, and cross-artifact checks. Does not score tax amounts. |
| Certification program | Experimental | Process defined. No registry is operated. See [conformance/CERTIFICATION.md](conformance/CERTIFICATION.md). |
| `later/` | Not in this version | VAT/GST field names and the US-to-Germany example. See [ROADMAP.md](ROADMAP.md). |
| Webhook binding | Experimental | Four events and the HMAC `signature` scheme. Manifest value `webhook` MUST NOT be advertised. |
| `cross-border` | Experimental | `POST /cross-border/calculate` and `utcs_calculate_duties`. Not in the v1.0 registry. `UTCS-7001` through `UTCS-7003` are reserved. |
| `filing-obligations` | Experimental | `GET /obligations` and `utcs_check_obligations`. Not in the v1.0 registry. |
| `mappings/ubl.md` | Not in this version | UBL and e-invoicing sketch. Normative only if a later version adopts it. |
| A2A binding | Not published | Manifest value `a2a` is reserved and MUST NOT be advertised. |
| ACP binding | Not published | Scope undecided. |
| AP2 binding | Not published | Not in this version. |
| `elr-reporting` | Not published | E-invoicing and live reporting. `UTCS-8001` and `UTCS-8002` are reserved. |

The reference implementation listed in [IMPLEMENTATIONS.md](IMPLEMENTATIONS.md) is informative. It is not an artifact of the specification.
