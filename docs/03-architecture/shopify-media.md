# Shopify media

Shopify media selection reuses the owner-scoped Media Library. JPEG, PNG, and WebP remain the only
supported types; SVG and arbitrary remote image fetching remain prohibited. Connector-specific
remote mappings are checksum-bound to a Shopify store and do not alter WordPress media mappings.

Destination media failure policies are fail safely, create a draft without media, or create a
degraded execution requiring recovery. Local paths and raw bytes never appear in API responses.
