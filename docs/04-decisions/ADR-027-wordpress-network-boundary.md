# ADR-027: WordPress network boundary

Status: Accepted

Remote WordPress URLs require HTTPS outside development, pass DNS/IP safety checks, cannot contain
credentials, query strings, or fragments, and may use only a bounded base path. Connector requests
use fixed REST endpoint patterns, reject redirects, and bound time and response size.
