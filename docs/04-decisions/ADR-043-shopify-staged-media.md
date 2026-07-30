# ADR-043: Use validated staged media uploads

Status: Accepted

Media bytes go only to HTTPS Shopify/documented storage targets returned by a predefined mutation.
The Admin token is never forwarded. Redirects, oversized files, unsupported MIME types, arbitrary
URLs, and caller-provided paths are rejected.
