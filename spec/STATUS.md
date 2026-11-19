# Artifact status

Envelope version **1.0** is **Draft**. A Draft artifact is normative for implementers and may still change in a compatible or incompatible way before it is marked Stable. An Experimental artifact is published so it can be tried; conforming to the envelope does not require implementing it. Nothing is Stable while the open questions in [ROADMAP.md](ROADMAP.md) are unresolved.

Date of this table: 19 November 2026.

| Artifact | Status | Notes |
|----------|--------|-------|
| [SPECIFICATION.md](SPECIFICATION.md) | Draft | Normative prose: conformance, data model, errors, security, governance, versioning. |
| `schemas/transaction-context.schema.json`, `schemas/tax-result.schema.json`, `schemas/discovery-manifest.schema.json`, `schemas/common/` | Draft | Core envelope schemas. |
| `schemas/jurisdiction-resolution-*.schema.json`, `schemas/classification-*.schema.json`, `schemas/exemption-validation-*.schema.json` | Draft | Request and response bodies for resolve, classify, and exemption validation. |
| `schemas/webhooks/` | Draft | Four webhook payloads. |
| `openapi/utcs-v1.yaml` | Draft | REST binding. Nine operations. No `/tax/void`. |
| `mcp/utcs-mcp-tools.json` | Draft | Seven tools. |
| `registries/` | Draft | Error codes and REST operations. Checked against the schemas and the OpenAPI document. |
| `profiles/us-sst.md` | Draft | US Streamlined Sales Tax profile. |
| `mappings/ubl.md` | Draft | UBL mapping. Normative only for a document that claims the mapping. |
| `bindings/ucp.md` | Draft | UCP binding, v0.1. Extension name `dev.ucp.shopping.tax`. |
| `examples/` | Draft | Informative. Validated on every `npm run validate`. |
| `conformance/` validator and negative fixtures | Experimental | Schema, lint, and cross-artifact checks. Does not score tax amounts. |
| Certification program | Experimental | Process defined. No registry is operated. See [conformance/CERTIFICATION.md](conformance/CERTIFICATION.md). |
| A2A binding | Not published | Manifest value `a2a` is reserved and MUST NOT be advertised. |
| ACP binding | Not published | Scope undecided. |
| AP2 binding | Not published | Not in this version. |
| `elr-reporting` | Not published | `UTCS-8001` and `UTCS-8002` are reserved. |

The reference implementation listed in [IMPLEMENTATIONS.md](IMPLEMENTATIONS.md) is informative. It is not an artifact of the specification.
