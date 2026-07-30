# Shopify product mapping

Approved Artifact title and description map to the Shopify title and sanitized description HTML.
Brand or destination defaults map to vendor; Product category or a destination default maps to
product type; keywords and configured tags are deduplicated. SEO title and description are bounded
and contain no markup.

The initial variant policy creates one default variant from existing Product commerce data. The
connector does not invent price, SKU, barcode, weight, options, or inventory. Structured variants
are accepted only when Product data already provides a valid bounded structure.
