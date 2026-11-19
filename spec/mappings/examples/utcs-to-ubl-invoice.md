# Worked Example: UTCS Tax Result to UBL Invoice Tax Block

This example renders a UTCS Tax Result as the tax block of a UBL Invoice. It follows the mapping in [`../ubl.md`](../ubl.md). The scenario is a single-line EU VAT sale, which is UBL's native territory and exercises EN 16931 cleanly.

## Scenario

A German seller invoices a German business customer for one item at 100.00 EUR. German standard-rate VAT applies at 19%.

## UTCS Tax Result (input to the mapping)

```json
{
  "result_id": "res_9f2a4c",
  "document_code": "INV-2026-00042",
  "status": "committed",
  "total_tax": "19.00",
  "total_taxable": "100.00",
  "total_exempt": "0.00",
  "total_amount": "100.00",
  "currency_code": "EUR",
  "lines": [
    {
      "line_number": "1",
      "tax_amount": "19.00",
      "taxable_amount": "100.00",
      "exempt_amount": "0.00",
      "tax_code": "P0000000",
      "jurisdictions": [
        {
          "jurisdiction_type": "country",
          "jurisdiction_code": "DE",
          "jurisdiction_code_system": "iso-3166-1",
          "jurisdiction_name": "Germany",
          "tax_type": "vat",
          "tax_category": "S",
          "rate": "0.19",
          "taxable_amount": "100.00",
          "tax_amount": "19.00",
          "rate_rule_id": "de-vat-standard-2026"
        }
      ]
    }
  ],
  "attestation": {
    "provider_id": "prov_example",
    "provider_name": "Example Tax Provider",
    "content_version": "2026.06.1",
    "calculation_timestamp": "2026-06-16T14:05:00Z",
    "engine_version": "8.2.0"
  },
  "conformance": [
    { "id": "en16931" }
  ]
}
```

## UBL Invoice tax block (output of the mapping)

```xml
<cac:TaxTotal>
  <cbc:TaxAmount currencyID="EUR">19.00</cbc:TaxAmount>
  <cac:TaxSubtotal>
    <cbc:TaxableAmount currencyID="EUR">100.00</cbc:TaxableAmount>
    <cbc:TaxAmount currencyID="EUR">19.00</cbc:TaxAmount>
    <cac:TaxCategory>
      <cbc:ID schemeID="UNCL5305">S</cbc:ID>
      <cbc:Percent>19.0</cbc:Percent>
      <cac:TaxScheme>
        <cbc:ID>VAT</cbc:ID>
      </cac:TaxScheme>
    </cac:TaxCategory>
  </cac:TaxSubtotal>
</cac:TaxTotal>
```

## How each value moved

| UBL value | Source |
|-----------|--------|
| `cac:TaxTotal/cbc:TaxAmount` = 19.00 | result `total_tax` |
| `@currencyID` = EUR | result `currency_code` |
| `cbc:TaxableAmount` = 100.00 | jurisdiction `taxable_amount` |
| `cbc:TaxAmount` = 19.00 | jurisdiction `tax_amount` |
| `cac:TaxCategory/cbc:ID` = S | jurisdiction `tax_category` |
| `cbc:Percent` = 19.0 | jurisdiction `rate` × 100 |
| `cac:TaxScheme/cbc:ID` = VAT | jurisdiction `tax_type` mapped through UNCL5153 |

## Exempt variant

When `tax_category` is `E`, the subtotal carries the exemption reason. A result whose jurisdiction reports `tax_category: "E"` with `exemption_applied.exemption_reason: "intra_community_supply"` renders as:

```xml
<cac:TaxCategory>
  <cbc:ID schemeID="UNCL5305">E</cbc:ID>
  <cbc:Percent>0.0</cbc:Percent>
  <cbc:TaxExemptionReason>Intra-community supply</cbc:TaxExemptionReason>
  <cac:TaxScheme>
    <cbc:ID>VAT</cbc:ID>
  </cac:TaxScheme>
</cac:TaxCategory>
```
