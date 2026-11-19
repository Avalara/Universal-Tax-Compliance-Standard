# Conformance and certification

**Status:** Experimental

This directory is the conformance suite for the artifacts in `spec/`. It is Experimental: passing it is necessary for a change to this repository, and it is not a certification of tax rates.

## What the suite checks

`npm run validate` (from `spec/`) does all of the following:

- Validates every worked example in `examples/` against its JSON Schema.
- Rejects the fixtures in `negative/`. A fixture that starts to pass is a failure of the suite.
- Lints `openapi/utcs-v1.yaml` with Redocly, using `redocly.yaml`. Unresolved `$ref`s fail the run. Embedded request and response examples are validated against their schemas.
- Compiles every MCP `inputSchema`, and rejects `negative/mcp-bad-tool.json`.
- Checks that `registries/rest-operations.json`, the OpenAPI paths, and `examples/discovery-manifest.example.json` name the same operations. A manifest that advertises `/classify` or `/tax/void` fails here even though the manifest schema allows any path string. `negative/manifest-stale-paths.json` is that case.
- Checks that the error-code enumeration, `registries/error-codes.json`, and [SPECIFICATION.md](../SPECIFICATION.md) list the same codes.
- Checks that the four webhook schemas are the schemas the OpenAPI webhooks reference.
- Checks that worked examples and the OpenAPI description stay provider-neutral, and that the UCP binding does not point at a private source host or claim an A2A binding.

## Certification

Three trust levels are defined in [SPECIFICATION.md](../SPECIFICATION.md) section 6. Certification is the third, and it is optional.

A **badge** in a discovery manifest is a claim that the provider has passed a described set of checks for one tier:

| Badge | Capabilities the claim covers | Prerequisite claim |
|-------|-------------------------------|--------------------|
| `core_compliance` | `tax-determination`, `jurisdiction-resolution` | none |
| `product_classification` | `product-classification` | `core_compliance` |
| `exemption_management` | `exemption-validation` | `core_compliance` |
| `compliance_documents` | `compliance-documents` | `core_compliance` |
| `cross_border_commerce` | `cross-border` | `core_compliance` and `product_classification` |
| `filing_obligations` | `filing-obligations` | `core_compliance` |

No registry is operated for this version. Therefore:

- A provider MAY put a badge in its manifest as a self-declaration.
- A provider MUST NOT describe that badge as issued by a UTCS registry.
- A consumer MUST treat `certification.badges` as a claim, not as evidence, while `certification.registry_url` does not resolve to a registry that publishes supervised results.
- The badges in `examples/discovery-manifest.example.json` illustrate the schema. They are not a certification record. The registry URL is on `example.com`.

A future registry, if the maintainers operate one, would record a supervised run of this suite plus any calculation fixtures added under roadmap item 14. Until that exists, passing `npm run validate` certifies the specification artifacts only.
