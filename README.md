# Universal Tax Compliance Standard (UTCS)

An open, protocol-agnostic specification for how tax compliance works for any
transaction, whichever commerce protocol initiated it.

UTCS defines the compliance envelope: the data model, the operations, the
error codes, and the transport bindings. It does not define tax rates,
boundaries, or product taxonomies. A provider supplies those.

These artifacts are envelope **1.0**, status **Draft**. Copyright 2026
Avalara, Inc. Licensed under the Apache License, Version 2.0. See
[LICENSE](LICENSE) and [NOTICE](NOTICE).

## Repository layout

| Path | Contents |
|------|----------|
| `spec/` | Normative specification: JSON Schemas, OpenAPI 3.1, MCP tool definitions, registries, conformance profiles, mappings, the UCP binding, and validated examples. |
| `src/bindings/ucp/` | UCP binding library. Maps checkout tax calls onto a UTCS `TransactionContext` and back, and serves `$previewTax` and `$determineTax`. |
| `src/examples/ucp/` | Mock determination server and `utcs_determine_tax`. See [`src/examples/ucp/README.md`](src/examples/ucp/README.md). |

An implementation of the specification does not depend on any document outside `spec/`. The file-by-file index is [`spec/README.md`](spec/README.md).

- **Prose** — [`spec/SPECIFICATION.md`](spec/SPECIFICATION.md) defines conformance, the data model, errors, security, governance, and versioning. [`spec/STATUS.md`](spec/STATUS.md) records maturity. [`spec/ROADMAP.md`](spec/ROADMAP.md) records what is still open.
- **Schemas** — JSON Schema 2020-12 for the transaction context, tax result, discovery manifest, resolve, classify, and exemption bodies, four webhook payloads, and shared types.
- **OpenAPI** — `spec/openapi/utcs-v1.yaml`, the REST transport binding. Paths are relative to `https://{provider}/utcs/v1`.
- **MCP** — `spec/mcp/utcs-mcp-tools.json`, 7 tool definitions.
- **Profiles / mappings / bindings** — US Streamlined Sales Tax profile, UBL mapping, and the Universal Commerce Protocol binding.
- **Examples** — request and response payloads. They use a neutral provider. The informative UCP implementation in this repository is listed in [`spec/IMPLEMENTATIONS.md`](spec/IMPLEMENTATIONS.md).

## Validate

```bash
cd spec
npm install
npm run validate
```

A passing run prints `OK: all conformance checks passed.` The check validates examples, rejects negative fixtures, lints the OpenAPI document, and compares the manifest, registries, and prose. Continuous integration runs the same check (`.gitlab-ci.yml`). Node.js 24 is pinned in `.nvmrc`.

## Versioning

The `utcs_version` field and the `/utcs/v1` prefix both name envelope 1.0. Versioning rules are in [`spec/SPECIFICATION.md`](spec/SPECIFICATION.md).

## License

Licensed under the Apache License, Version 2.0. Copyright 2026 Avalara, Inc.
See [LICENSE](LICENSE) and [NOTICE](NOTICE).
