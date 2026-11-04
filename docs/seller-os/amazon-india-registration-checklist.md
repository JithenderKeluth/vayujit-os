# Amazon India registration and API-readiness checklist

Status: account not registered; no Amazon credentials or provider calls were
used. Provider-specific requirements change and must be confirmed by the owner
in Amazon's current Seller Central and Selling Partner API (SP-API) portals.
Anything not confirmed there is **UNVERIFIED - HUMAN FOLLOW-UP REQUIRED**.

## Verified provider distinctions

Amazon's current SP-API documentation distinguishes seller registration from
developer/application registration and authorization. It also distinguishes
private applications from public applications, requires approved roles for
operations, and uses Login with Amazon (LWA) authorization for applicable
flows. Review the official sources before implementation:

- [SP-API registration overview](https://developer-docs.amazon.com/sp-api/lang-en_EN/docs/sp-api-registration-overview)
- [SP-API onboarding overview](https://developer-docs.amazon.com/sp-api/docs/onboarding-overview)
- [SP-API roles](https://developer-docs.amazon.com/sp-api/docs/roles-in-the-selling-partner-api)
- [Connect to SP-API](https://developer-docs.amazon.com/sp-api/docs/connecting-to-the-selling-partner-api)
- [SP-API endpoints](https://developer-docs.amazon.com/sp-api/lang-es_ES/docs/sp-api-endpoints)

These links do not constitute approval, credentials, or certification for
VAYUJIT.

## Registration stages

### 1. Seller-account registration

- [ ] Owner confirms the official Amazon India Seller Central entry point and
      creates the seller account personally.
- [ ] Legal business identity, contact, address, tax and settlement details
      are supplied truthfully in Seller Central.
- [ ] Account type, selling plan, fees, and payout terms are reviewed by the
      owner.
- [ ] Registration outcome and seller ID are recorded in a HUMAN-controlled
      document; credentials never enter Git or screenshots.
- Status: **UNVERIFIED - HUMAN FOLLOW-UP REQUIRED**.

### 2. Identity, tax, and verification

- [ ] Owner completes every verification task shown by Seller Central.
- [ ] GST/PAN/bank/address documents and category-related declarations are
      supplied only through the official portal where requested.
- [ ] Any category, brand, trademark, or restricted-product approval is
      recorded with its exact Amazon status and expiry.
- Status: **UNVERIFIED - HUMAN FOLLOW-UP REQUIRED**. Do not infer requirements
  from a third-party guide.

### 3. Product/category eligibility

- [ ] For each product, the owner confirms the exact Amazon category,
      attributes, compliance documents, images, brand/GTIN/SKU requirements,
      pricing, and fulfilment model in Seller Central.
- [ ] VAYUJIT canonical product and listing records contain only evidence the
      owner has supplied; missing values remain `UNKNOWN`.
- [ ] Category approval is verified for the selected product before any draft
      is considered ready.
- Status: **UNVERIFIED - HUMAN FOLLOW-UP REQUIRED**.

### 4. Marketplace API access eligibility

- [ ] Owner confirms whether the account/application type is eligible for the
      required SP-API operations and marketplace.
- [ ] Developer registration, application type, data-access description,
      security controls, and requested roles are reviewed in the official
      portal.
- [ ] A seller account is not treated as API access; eligibility must be
      demonstrated by the portal and provider response.
- Status: **UNVERIFIED - HUMAN FOLLOW-UP REQUIRED**.

### 5. Application authorization and credential issuance

- [ ] Decide private self-authorization versus another officially supported
      authorization model.
- [ ] Owner approves the exact roles/scopes and redirect/authorization flow.
- [ ] Store LWA/client/refresh credentials only in the approved secret manager;
      never in VAYUJIT rows, logs, fixtures, or browser evidence.
- [ ] Record credential owner, expiry/rotation policy, revocation process, and
      correlation ID without recording secret values.
- Status: **UNVERIFIED - HUMAN FOLLOW-UP REQUIRED**.

### 6. Official API contract verification

- [ ] Confirm the current official model, operation, region endpoint, rate
      limits, error semantics, restricted-data requirements, and role mappings.
- [ ] Review official deprecations and terms before adapter work.
- [ ] Do not infer operation paths, permissions, ASIN/merchant identifiers, or
      write behavior from VAYUJIT's fake transport.
- Status: **UNVERIFIED - HUMAN FOLLOW-UP REQUIRED**.

### 7. Sandbox certification, if supported

- [ ] Confirm the current Amazon sandbox availability for the selected use
      case and account/application type.
- [ ] Run only provider-approved, non-production sandbox tests with separate
      credentials and no real catalog/order data.
- [ ] Preserve request/response correlation without storing secrets or raw
      restricted payloads.
- Status: **UNVERIFIED - HUMAN FOLLOW-UP REQUIRED**.

### 8. Authorized live read-only certification

- [ ] Owner explicitly authorizes a bounded `LIVE_READ_ONLY` test.
- [ ] Confirm the exact seller/marketplace scope, request budget, kill switch,
      timeout, domain allowlist, and evidence retention.
- [ ] Reconcile read-only results against canonical VAYUJIT records; do not
      create external listings or mutate prices/inventory.
- Status: **BLOCKED** until stages 1-7 and separate authorization are complete.

### 9. External-write approval

- [ ] Product/listing readiness, commercial review, backup, and HUMAN approval
      are complete.
- [ ] A separate, single-use, auditable execution authorization names the
      exact artifact, seller account, operation, expiry, and emergency-stop
      state.
- [ ] Owner approves publication only after reviewing the final payload in the
      official marketplace context.
- Status: **DENIED BY DEFAULT**.

## VAYUJIT handoff data

Required from the owner: Seller Central status and seller ID, account type,
verification status, category approvals, application type, approved roles,
marketplace/region, credential custody and expiry metadata, sandbox/read-only
authorization, and explicit HUMAN decisions for each next stage. No token,
client secret, or refresh token should be sent in chat or committed.

