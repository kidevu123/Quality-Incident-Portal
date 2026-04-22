# Security review checklist (pre-production)

## Identity & access

- [ ] Enforce strong password policy; consider SSO (SAML/OIDC) for enterprise tenants
- [ ] Map `Role` to Django permissions / groups per tenant; periodic access reviews
- [ ] Separate distributor users from staff; optional IP allowlists for admin
- [ ] MFA for admin and finance approvers

## Application

- [ ] `DEBUG=false`, secure cookies, HSTS when on HTTPS
- [ ] CSRF on all state-changing browser views; tighten CORS to known origins
- [ ] Rate limit portal claim submission and login (`django-ratelimit` wired; expand coverage)
- [ ] Validate uploads: size, MIME sniffing, malware scan, store outside web root with authz
- [ ] Secrets only via env / vault — never in repo (Zoho refresh token rotation procedure)

## API & integrations

- [ ] Zoho: least-scope OAuth; store tokens encrypted; monitor refresh failures
- [ ] Idempotency keys for financial pushes; human approval over threshold
- [ ] Audit every Zoho push with request/response hashes (PII redacted)

## Data & infra

- [ ] PostgreSQL: TLS, role separation, `pg_dump` encryption, PITR where available
- [ ] Redis: password, bind to private network, persistence policy documented
- [ ] Nginx: TLS 1.2+, modern ciphers, `client_max_body_size` aligned with upload policy
- [ ] Backups tested quarterly; restore runbook exercised

## Compliance & abuse

- [ ] Data retention policy for tickets, attachments, and logs
- [ ] Distributor abuse detection (velocity, duplicate claims) — tune `abuse_risk_score`
- [ ] GDPR/CCPA: export/delete hooks for customer data (Phase 2)
