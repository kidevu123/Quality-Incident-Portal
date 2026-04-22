# Phase 2 roadmap

1. **Barcode / batch scanning** — mobile-friendly intake; validate lot against inventory master
2. **OCR on labels** — extract lot/expiry from photos; human-in-the-loop confirmation
3. **AI defect classification** — multimodal model; confidence thresholds drive routing
4. **Manufacturer scorecards** — roll up CAPA, chargebacks, ppm, trend dashboards
5. **Vendor chargebacks** — workflow + Zoho Bills / manual credit linkage
6. **Portal chat** — async messaging or embedded widget; SLA on first response
7. **Warranty registration** — SKU + serial lifecycle; eligibility checks before replacement SO
8. **Knowledge base** — agent macros → published articles; SEO-safe portal docs
9. **Supplier portal** — constrained view for co-investigations and containment
10. **Multi-tenancy** — org-level isolation (schema or row-level), subdomain routing

Cross-cutting: full-text search (OpenSearch/PostgreSQL), event bus (outbox pattern), observability (OpenTelemetry), feature flags.
