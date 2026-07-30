# Publishing preview and sanitization

`POST /api/v1/publishing/preview` uses the backend WordPress mapping functions also used by
publishing. It returns title, slug, excerpt, safe paragraph markup, status, taxonomy IDs, author,
featured media, immutable Artifact version, Product, Brand, and update target.

Generated content is treated as plain text. HTML-looking content is escaped; paragraphs and line
breaks receive deterministic markup. The UI renders original and mapped output as text and never
uses sanitizer bypass or unsafe HTML insertion.
