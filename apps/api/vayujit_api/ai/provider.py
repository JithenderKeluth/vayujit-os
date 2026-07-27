import hashlib
import json
from dataclasses import dataclass
from typing import Protocol


class ProviderError(Exception):
    def __init__(self, code: str, safe_message: str) -> None:
        self.code = code
        self.safe_message = safe_message
        super().__init__(safe_message)


@dataclass(frozen=True)
class GenerationInput:
    brand_name: str
    product_name: str
    product_type: str
    short_description: str | None
    description: str | None
    category: str | None
    tags: list[str]
    additional_instructions: str | None
    template_key: str
    template_version: int

    def normalized(self) -> str:
        return json.dumps(
            {
                "brand_name": self.brand_name.strip(),
                "product_name": self.product_name.strip(),
                "product_type": self.product_type,
                "short_description": (self.short_description or "").strip(),
                "description": (self.description or "").strip(),
                "category": (self.category or "").strip(),
                "tags": sorted(tag.strip().casefold() for tag in self.tags),
                "additional_instructions": (self.additional_instructions or "").strip(),
                "template_key": self.template_key,
                "template_version": self.template_version,
            },
            sort_keys=True,
            separators=(",", ":"),
        )


@dataclass(frozen=True)
class ProviderResult:
    content: dict[str, object]
    metadata: dict[str, object]


class AIProvider(Protocol):
    key: str
    name: str
    provider_type: str

    def available(self) -> bool: ...
    def generate(self, value: GenerationInput) -> ProviderResult: ...


class DeterministicMockAIProvider:
    key = "deterministic_mock_v1"
    name = "Deterministic Local Mock"
    provider_type = "mock"

    def available(self) -> bool:
        return True

    def generate(self, value: GenerationInput) -> ProviderResult:
        instructions = (value.additional_instructions or "").casefold()
        if "[mock:fail]" in instructions:
            raise ProviderError("mock_generation_failed", "The local mock generation failed.")
        if "[mock:invalid]" in instructions:
            return ProviderResult(
                {"product_title": "<script>invalid</script>"}, {"mode": "invalid"}
            )
        digest = hashlib.sha256(value.normalized().encode()).hexdigest()
        base = (
            value.short_description
            or value.description
            or f"{value.product_name} by {value.brand_name}"
        )
        category = value.category or value.product_type
        content: dict[str, object] = {
            "product_title": f"{value.brand_name} {value.product_name}",
            "short_description": f"{base[:360]} — crafted for dependable everyday use.",
            "long_description": (
                f"{value.product_name} combines {base.lower()} with the trusted identity "
                f"of {value.brand_name}. Designed for customers seeking a clear, practical "
                f"{category} option, it balances useful details with an approachable "
                f"presentation. Reference {digest[:8]}."
            ),
            "key_features": [
                f"Designed for {category}",
                f"Presented by {value.brand_name}",
                f"Consistent product reference {digest[8:14]}",
            ],
            "seo_title": f"{value.product_name} | {value.brand_name}"[:70],
            "seo_description": f"Discover {value.product_name} from {value.brand_name}. {base}"[
                :170
            ],
            "social_caption": (
                f"Meet {value.product_name} from {value.brand_name}. {base} #{digest[:6]}"
            ),
            "keywords": [value.product_name.lower(), value.brand_name.lower(), category.lower()],
            "generation_summary": (
                "Deterministic product content generated from template "
                f"{value.template_key} v{value.template_version}."
            ),
        }
        return ProviderResult(
            content, {"provider": self.key, "deterministic": True, "input_fingerprint": digest[:16]}
        )
