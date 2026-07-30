# Media Library

The Media Library stores owner-scoped JPEG, PNG, and WebP assets outside public application
directories. Uploads are bounded, signature-checked, dimension-checked, hashed, and written
atomically under a server-generated canonical storage key. API responses never expose that key or
the local path.

Identical bytes reuse the existing owner asset by SHA-256 checksum. Archiving is reversible and
does not remove bytes. WordPress mappings are site-specific and reuse remote media only after the
remote record is verified. SVG and arbitrary remote image URLs are unsupported.
