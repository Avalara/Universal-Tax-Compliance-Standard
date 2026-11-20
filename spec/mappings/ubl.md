# UTCS to UBL Mapping

**Status:** Not part of envelope 1.0
**Applies to:** a later version that covers e-invoicing
**Target:** OASIS Universal Business Language (UBL) 2.x, with notes for EN 16931 and Peppol BIS Billing 3.0

This document is a sketch of how a later version could map a Tax Result onto the UBL tax model. Envelope 1.0 does not include e-invoicing. The sketch is not normative for a v1.0 implementation. See [../ROADMAP.md](../ROADMAP.md).

Requirement levels (MUST, SHOULD, MAY) follow RFC 2119.

---

## 1. Why UBL

UBL is the document model underneath EN 16931, Peppol BIS Billing, and a growing set of national e-invoicing mandates. UTCS keeps a JSON-native calculation model and emits UBL XML when a transaction must become a compliance document. The tax semantics line up closely, so the mapping is mechanical rather than interpretive.

## 2. The UBL tax model

UBL nests its tax representation:

```text
cac:TaxTotal
  cbc:TaxAmount                      (total tax for the document or line)
  cac:TaxSubtotal                    (one per category + scheme + rate)
    cbc:TaxableAmount
    cbc:TaxAmount
    cac:TaxCategory
      cbc:ID                         (UNCL5305 category code)
      cbc:Percent
      cbc:TaxExemptionReasonCode     (when exempt)
      cbc:TaxExemptionReason         (when exempt)
      cac:TaxScheme
        cbc:ID                       (UNCL5153 scheme code, e.g. VAT, GST)
```

UTCS breaks tax down by jurisdiction. UBL groups it by category, scheme, and rate. The mapping aggregates UTCS jurisdiction breakdowns into UBL subtotals.

## 3. Field mapping

| UTCS Tax Result | UBL element | Notes |
|-----------------|-------------|-------|
| `total_tax` | `cac:TaxTotal/cbc:TaxAmount` | Document-level total. `currencyID` from `currency_code`. |
| `currency_code` | `@currencyID` on every amount | ISO 4217. |
| `lines[].jurisdictions[]` | `cac:TaxSubtotal` | Aggregate breakdowns that share `tax_category`, `tax_type`, and `rate` into one subtotal. |
| `jurisdiction_breakdown.taxable_amount` | `cac:TaxSubtotal/cbc:TaxableAmount` | Summed across the aggregated breakdowns. |
| `jurisdiction_breakdown.tax_amount` | `cac:TaxSubtotal/cbc:TaxAmount` | Summed across the aggregated breakdowns. |
| `jurisdiction_breakdown.tax_category` | `cac:TaxCategory/cbc:ID` | UNCL5305 code. Set `listID="UNCL5305"`. |
| `jurisdiction_breakdown.rate` | `cac:TaxCategory/cbc:Percent` | Multiply the decimal rate by 100 (`0.065` becomes `6.5`). |
| `jurisdiction_breakdown.tax_type` | `cac:TaxScheme/cbc:ID` | Map to UNCL5153 (see §4). |
| `exemption_applied.exemption_reason` | `cac:TaxCategory/cbc:TaxExemptionReason` | Present when `tax_category` is `E`. |
| `exemption_applied.exemption_reason` | `cac:TaxCategory/cbc:TaxExemptionReasonCode` | Provider maps the controlled reason to the mandate's code list where one is required. |
| `lines[].tax_code` / `lines[].hs_code` | `cac:Item/cac:CommodityClassification` | When the applied tax code or HS code should travel on the invoice line. |
| `attestation` | document-level note or extension | Carries provider identity and content version for audit. |

## 4. Tax type to UBL scheme

UTCS `tax_type` carries the tax-scheme semantics that UBL puts in `cac:TaxScheme/cbc:ID` (UNCL5153):

| UTCS `tax_type` | UBL TaxScheme ID |
|-----------------|------------------|
| `vat` | `VAT` |
| `gst` | `GST` |
| `sales_tax`, `sellers_use`, `consumer_use`, `use_tax` | `LAC` (local/sales tax) or a provider-declared scheme |
| `excise` | `EXC` |
| `duty` | `CUD` (customs duty) |
| `environmental_fee` | `ENV` or a provider-declared scheme |

US sales and use tax has no single UNCL5153 code in common use across mandates. A provider rendering UBL for a US transaction declares the scheme it uses and keeps it stable.

## 5. Tax category to UBL category

UTCS `tax_category` is already a UNCL5305 value, so it maps one to one onto `cac:TaxCategory/cbc:ID`. The codes in the UTCS core enum match the EN 16931 and Peppol BIS Billing category set: `S`, `Z`, `E`, `AE`, `K`, `G`, `O`, `L`, `M`, `B`. No translation table is needed.

## 6. Documents: Invoice and Credit Note

When the `compliance-documents` capability produces a UBL document, the UTCS `document_type` selects the UBL document type:

| UTCS `document_type` | UBL document |
|----------------------|--------------|
| `sale` | `Invoice` |
| `return` | `CreditNote` |
| `purchase_order` | `Order` (where a buyer-side document is needed) |

The tax block is built from the Tax Result as mapped above. Header parties, line descriptions, and amounts come from the originating Transaction Context and the merchant's commercial data.

## 7. EN 16931 and Peppol notes

EN 16931 constrains UBL (cardinalities, business rules, code lists). Peppol BIS Billing 3.0 constrains it further and adds transport. A UTCS-emitted UBL document targeting either profile MUST satisfy that profile's rules in addition to this mapping. The UTCS tax block is compatible by construction because the category and scheme codes are drawn from the same lists those profiles require.

## 8. Decimal handling

UTCS amounts are decimal strings. UBL amounts are decimals with a `currencyID` attribute. The value transfers unchanged; the mapping only adds the currency attribute. No minor-unit conversion happens here. Minor-unit integers belong to the UCP binding ([`../bindings/ucp.md`](../bindings/ucp.md)), not to UBL.

## 9. Worked example

A worked UTCS-result-to-UBL-Invoice tax block is in [`examples/utcs-to-ubl-invoice.md`](examples/utcs-to-ubl-invoice.md).

## 10. Scope

This mapping covers the tax block and the document-type selection. A full conformant Peppol BIS Billing or national-mandate binding (complete document schema, validation artifacts, transport) is future work that builds on this foundation.
