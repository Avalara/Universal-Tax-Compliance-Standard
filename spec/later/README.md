# Later than envelope 1.0

These files are design sketches for VAT, GST, and other non-US tax. They are not part of envelope 1.0, and `npm run validate` does not check them.

`POST /cross-border/calculate`, `GET /obligations`, and the webhook binding are Experimental. They live in the REST binding with `x-utcs-status: experimental`, and they stay out of the v1.0 registry. See [ROADMAP.md](../ROADMAP.md).

## Examples

| File | What it sketches |
|------|------------------|
| `examples/determine-crossborder.request.json` | US-to-Germany sale, DDP, seller as importer of record |
| `examples/determine-crossborder.response.json` | German VAT on that sale |

The Canadian HST sample (Ontario, 13 percent, reported as `tax_type` `gst`) is the Experimental example on `POST /cross-border/calculate` in `openapi/utcs-v1.yaml`.
