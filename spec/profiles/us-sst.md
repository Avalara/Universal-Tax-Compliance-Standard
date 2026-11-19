# UTCS Conformance Profile: US-SST

**Profile ID:** `us-sst`
**Status:** Draft v0.1
**Applies to:** UTCS v1.0 core (`../schemas/`)
**Scope:** United States sales and use tax under the Streamlined Sales and Use Tax Agreement (SSUTA)

This profile defines how a UTCS provider conforms to the Streamlined Sales and Use Tax Agreement while serving the protocol-agnostic UTCS core. It constrains and annotates the core; it does not fork it. A provider that implements this profile produces ordinary UTCS Tax Results that any UTCS consumer can read, plus the additional guarantees described here.

Requirement levels (MUST, SHOULD, MAY) follow RFC 2119.

---

## 1. What a conformance profile is

A conformance profile is a named rule set that a provider conforms to: sourcing rules, jurisdiction code systems, classification vocabularies, exemption handling, rounding, and return formats. Three properties define how it travels through UTCS:

- The provider **declares** the profile in its discovery manifest under `conformance_profiles` (see [`../schemas/discovery-manifest.schema.json`](../schemas/discovery-manifest.schema.json)).
- The provider **derives** whether the profile applies to a given transaction from the facts in the request (addresses, entity type, date). The caller never selects a profile.
- The provider **annotates** the applied profile on the Tax Result under the result-level `conformance` field (see [`../schemas/tax-result.schema.json`](../schemas/tax-result.schema.json)).

A caller sending a US domestic transaction to an SST-conformant provider gets `us-sst` back as an annotation. The caller did not ask for it and could not have; the provider determined it.

## 2. SST roles and the UTCS provider

SSTUTA distinguishes service models. A UTCS provider maps onto them through its attestation and certification, not through any change to the calculation contract.

| SST role | Description | UTCS expression |
|----------|-------------|-----------------|
| CSP (Certified Service Provider) | Certified to perform all of a seller's sales and use tax functions | Provider holds the `core_compliance` certification badge and identifies as a CSP in `attestation.provider_name` / registry entry |
| CAS (Certified Automated System) | Certified software that calculates tax | Provider's calculation engine, identified by `attestation.engine_version` and `attestation.content_version` |
| Model 1 | Seller uses a CSP | The agent or merchant calls a CSP-operated UTCS provider |
| Model 2 | Seller uses a CAS | The merchant runs a CAS and exposes it as a UTCS provider |
| Model 3 | Seller uses a certified proprietary system | A large seller exposes its own certified engine as a UTCS provider |

The attestation block ([`../schemas/common/attestation.schema.json`](../schemas/common/attestation.schema.json)) carries the identity and content version that an SST audit requires. When a provider signs the result, the signature gives the CLT audit layer a cryptographic anchor.

## 3. Jurisdiction codes

Under `us-sst`, every jurisdiction reported in a Tax Result MUST set `jurisdiction_code_system` to `fips` and populate `jurisdiction_code` with the corresponding FIPS code used by the SST Rate and Boundary databases:

- State levies use the two-digit state FIPS code.
- County, city, and special-district levies use the FIPS place or county codes published in the destination state's boundary database.

UTCS ships no FIPS codes and no boundary data. The provider supplies both from its SST Rate and Boundary database. The profile only fixes which code system the `jurisdiction_code` field speaks.

## 4. Sourcing

Sourcing is the provider's determination. UTCS neither defines sourcing rules nor decides which jurisdiction's tax applies; it only exposes the address roles on the Transaction Context that a provider's sourcing logic reads:

| Address role | UTCS field |
|--------------|------------|
| Location where the order is received | `addresses.ship_from` or `addresses.point_of_order_acceptance` |
| Location where the product is received by the purchaser | `addresses.ship_to` |
| Origin for origin-sourced intrastate sales | `addresses.point_of_order_origin` |

A provider claiming `us-sst` conformance is asserting that its own sourcing follows the SSUTA hierarchy. UTCS carries the address facts; the provider owns the rules.

## 5. Classification

SST member states share a Library of Definitions in the Taxability Matrix. Under `us-sst`, a provider that echoes a classification SHOULD carry the SST library term in the line `tax_code`:

```json
{
  "tax_code": "clothing"
}
```

A caller MAY send `tax_code` as an input hint on a line item, using an SST library term, a provider tax code, or a custom value. The provider owns the final classification and returns the applied `tax_code` on the Tax Result line.

## 6. Taxability treatment

The provider expresses the taxability treatment it applied through the `tax_category` field on each jurisdiction breakdown, using UNCL5305 codes. For US sales and use tax, three values carry the common cases:

| SST treatment | UTCS `tax_category` |
|---------------|---------------------|
| Taxable at the standard rate | `S` |
| Taxable at a zero rate | `Z` |
| Exempt (item or entity) | `E` |

The same `tax_category` axis maps directly to UBL `cac:TaxCategory` when the transaction is also rendered as an e-invoice, so a provider populates it once and both the SST return and any UBL document read from it.

## 7. Tax type

US sales and use tax distinguishes seller-collected and buyer-accrued obligations. The provider sets `tax_type` on each jurisdiction breakdown to the value it determined:

| Obligation | UTCS `tax_type` |
|------------|-----------------|
| Sales tax collected by the seller | `sales_tax` |
| Seller's use tax (remote seller collecting destination tax) | `sellers_use` |
| Consumer use tax (buyer self-accrues) | `consumer_use` |

`tax_type` is provider-derived output. The caller supplies the facts; the provider names the tax.

## 8. Exemptions

SST publishes the Uniform Sales and Use Tax Certificate of Exemption (SSTGB Form F0003). Under `us-sst`:

- A claimed exemption MUST carry the certificate identifier through the input (`customer.exemption_certificate_id` or a per-line exemption claim).
- An applied exemption MUST report `exemption_reason` on the jurisdiction breakdown using a value drawn from the controlled vocabulary in [`../schemas/common/jurisdiction-breakdown.schema.json`](../schemas/common/jurisdiction-breakdown.schema.json).

The controlled `exemption_reason` values align to the F0003 reason categories:

| F0003 reason category | UTCS `exemption_reason` |
|-----------------------|-------------------------|
| Resale | `resale` |
| Government (federal, state, local) | `government` |
| Charitable / nonprofit organization | `charitable_nonprofit` |
| Religious or educational organization | `religious_educational` |
| Agricultural production | `agricultural_production` |
| Industrial production / manufacturing | `industrial_production` |
| Direct pay permit | `direct_pay` |
| Direct mail | `direct_mail` |
| Foreign diplomat | `foreign_diplomat` |
| Other (provider explains via `exemption_type`) | `other` |

`export` and `intra_community_supply` exist in the core vocabulary for cross-border use and do not apply under `us-sst`.

## 9. Rounding

The UTCS core default is half-up rounding to the currency minor unit, computed per line per jurisdiction before summation. That default is consistent with SSUTA Section 324. Under `us-sst`, a provider MUST declare its rounding in the manifest `rounding` block and SHOULD cite SSUTA Section 324 as the basis. A provider that applies an invoice-level rounding election permitted by Section 324 MUST set `rounding.jurisdiction_overrides_applied` to `true`.

## 10. Returns and filing

Filing SST returns is the provider's responsibility and sits outside the UTCS calculation contract. UTCS determines per-transaction tax; the provider aggregates committed transactions and files the Simplified Electronic Return (SER) through its own systems. The `filing-obligations` advanced capability MAY report where a transaction will be filed, but UTCS does not generate, format, or transmit returns.

## 11. Registration

SST sellers register through the Streamlined Sales Tax Registration System. Registration is a provider and merchant concern, outside the per-transaction contract. A provider MAY carry a seller's registration identifier through `business_identification_no` on the Transaction Context.

## 12. What this profile does not change

The profile adds constraints and annotations. It does not ship rate data, boundary data, or tax content, and it does not alter the canonical input or output shape. A non-SST UTCS consumer reads an `us-sst` result with no special handling; the SST guarantees are additive.

## 13. Conformance checklist

A provider conforms to `us-sst` when all of the following hold:

1. The provider declares `us-sst` in `conformance_profiles` in its discovery manifest.
2. For each US domestic transaction it determines, the provider annotates `conformance` with `us-sst` on the Tax Result.
3. Every jurisdiction breakdown sets `jurisdiction_code_system` to `fips`.
4. The provider applies SSUTA sourcing using the supplied address roles.
5. Applied taxability is expressed through `tax_category`, and applied tax type through `tax_type`.
6. Applied exemptions report a controlled `exemption_reason` and the certificate identifier.
7. The manifest `rounding` block is declared and consistent with SSUTA Section 324.
8. The attestation identifies the CSP or certified engine and content version.

## 14. Manifest declaration example

```json
{
  "conformance_profiles": [
    {
      "id": "us-sst",
      "version": "0.1",
      "specification_url": "https://utcs.tax/profiles/us-sst"
    }
  ]
}
```

## 15. Result annotation example

```json
{
  "conformance": [
    { "id": "us-sst", "version": "0.1" }
  ]
}
```
