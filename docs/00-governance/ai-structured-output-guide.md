# AI structured-output guide

The provider receives a JSON Schema matching the backend Product-content
contract. Responses are bounded, parsed as JSON, reject extra fields and markup,
and enforce all field/list limits. One additional provider attempt is permitted
after schema validation fails. A second invalid response ends the request safely
without an artifact.
