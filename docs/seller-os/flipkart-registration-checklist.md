# Flipkart registration and API-readiness checklist

Status: account not registered; no Flipkart credentials or provider calls were
used. Confirm current requirements in the official Seller Hub and Seller APIs
portal. Anything not confirmed there is **UNVERIFIED - HUMAN FOLLOW-UP
REQUIRED**.

## Verified provider distinctions

The current official Flipkart Seller API documentation states that seller
registration is separate from API access: registration credentials do not
provide API access, and a seller uses the dashboard's Developer Access flow to
create self-access applications. The documentation also describes separate
authorization-code access for third-party applications, HTTPS-only API calls,
and distinct production/sandbox handling. Review:

- [Flipkart Seller registration](https://seller.flipkart.com)
- [Flipkart Seller API overview](https://seller.flipkart.com/api-docs/FMSAPI.html)
- [API documentation home](https://seller.flipkart.com/api-docs/index.html)
- [Flipkart seller platform overview](https://seller.flipkart.com/api-docs/FMPlatOverview.html)
- [API best practices](https://seller.flipkart.com/api-docs/best_practices.html)

These sources do not authorize VAYUJIT or confirm a particular account's
eligibility.

## Registration stages

### 1. Seller-account registration

- [ ] Owner creates the account only through the official Seller Hub.
- [ ] Legal business, address, tax/GST, bank, contact, and pickup/location
      information are supplied truthfully.
- [ ] Seller ID and account status are recorded outside secrets.
- Status: **UNVERIFIED - HUMAN FOLLOW-UP REQUIRED**.

### 2. Identity, tax, and verification

- [ ] Owner completes every verification and location onboarding task shown by
      Seller Hub.
- [ ] GST, bank, address, and category/product documents are submitted through
      the official workflow where required.
- [ ] Approval status, expiry, and unresolved holds are recorded.
- Status: **UNVERIFIED - HUMAN FOLLOW-UP REQUIRED**.

### 3. Product/category eligibility

- [ ] Confirm category, product attributes, compliance, images, brand/GTIN/SKU,
      packaging, fulfilment, and pricing requirements in the Seller dashboard.
- [ ] Keep any missing field as `UNKNOWN`; do not infer listing approval from a
      successful account registration.
- Status: **UNVERIFIED - HUMAN FOLLOW-UP REQUIRED**.

### 4. Marketplace API access eligibility

- [ ] Owner confirms the Seller APIs - Developer Admin portal is available for
      the registered seller.
- [ ] Decide self-access versus an approved third-party application.
- [ ] Confirm API terms, application type, scopes, token lifetime/refresh,
      environment, rate limits, and support process from the current portal.
- Status: **UNVERIFIED - HUMAN FOLLOW-UP REQUIRED**. Seller registration alone
  is not API access.

### 5. Application authorization and credential issuance

- [ ] For self-access, owner creates the application through Developer Access
      and records only non-secret metadata.
- [ ] For third-party access, owner explicitly authorizes the application and
      redirect/state flow.
- [ ] Keep app ID/secret/access/refresh tokens in the secret manager only;
      record expiry, rotation, and revocation ownership.
- Status: **UNVERIFIED - HUMAN FOLLOW-UP REQUIRED**.

### 6. Official API contract verification

- [ ] Confirm current listing, order, inventory, report, and authentication
      contracts in the official documentation.
- [ ] Verify exact production base URL, HTTPS requirement, authorization
      header, token flow, error codes, rate limits, and seller/location scope.
- [ ] Do not copy fake transport paths or permissions into production settings.
- Status: **UNVERIFIED - HUMAN FOLLOW-UP REQUIRED**.

### 7. Sandbox certification, if supported

- [ ] Confirm whether the selected seller/application has sandbox access; the
      official FAQ states registration does not automatically provide sandbox
      access.
- [ ] Obtain provider-approved sandbox tokens and run only bounded tests.
- [ ] Keep sandbox data and credentials separate from any production seller
      records.
- Status: **UNVERIFIED - HUMAN FOLLOW-UP REQUIRED**.

### 8. Authorized live read-only certification

- [ ] Owner authorizes a bounded `LIVE_READ_ONLY` test after stages 1-7.
- [ ] Confirm seller ID, location scope, allowlisted domains, request budget,
      timeout, kill switch, and evidence retention.
- [ ] Reconcile reads to VAYUJIT without creating listings, changing price or
      stock, acknowledging orders, or publishing.
- Status: **BLOCKED** until prior stages and a separate authorization exist.

### 9. External-write approval

- [ ] Readiness, backup, product/listing review, and HUMAN approval are
      complete.
- [ ] Create a separate single-use execution authorization for the exact
      artifact and operation, with expiry, revocation, and emergency-stop
      checks.
- [ ] Owner reviews the final payload in Seller Hub/official context.
- Status: **DENIED BY DEFAULT**.

## VAYUJIT handoff data

Required from the owner: Seller Hub status and seller ID, verification/location
status, GST/tax evidence, product/category approval, Developer Access status,
application type, scopes/token metadata, sandbox/read-only approval, and the
explicit HUMAN decision for each stage. Never send an app secret or token in
chat, logs, fixtures, or Git.

