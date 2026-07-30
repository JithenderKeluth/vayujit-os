# Shopify credentials

Create an owner-controlled Shopify custom app and grant only the Admin API scopes required for
product read/write, files/media, collections, and publications when publication discovery is
needed. Record the permanent `*.myshopify.com` domain and Admin API access token.

Credentials use authenticated encryption in PostgreSQL. The token is write-only: it is never
returned to Angular, Electron, diagnostics, logs, audit metadata, URLs, or exports. Application
credentials take precedence over deployment environment credentials. Removing the credential
also disables the connector.

Set `VAYUJIT_CREDENTIAL_ENCRYPTION_KEY` before saving application credentials. Deployment fallback
uses `SHOPIFY_SHOP_DOMAIN`, `SHOPIFY_ADMIN_API_ACCESS_TOKEN`, and `SHOPIFY_API_VERSION`.
