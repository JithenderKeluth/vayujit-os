"""Network-free deterministic image provider used for local workflow certification."""

from __future__ import annotations

import binascii
import hashlib
import struct
import zlib

from vayujit_api.ai.failures import StudioProviderFailure

IMAGE_CAPABILITIES = {
    "image_generation",
    "image_editing",
    "background_removal",
    "inpainting",
    "outpainting",
    "transparent_background",
    "image_variations",
}


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)
    )


def deterministic_png(width: int, height: int, seed: str) -> bytes:
    digest = hashlib.sha256(seed.encode()).digest()
    row = bytearray([0])
    for x in range(width):
        row.extend(
            (
                digest[x % len(digest)],
                digest[(x + 7) % len(digest)],
                digest[(x + 13) % len(digest)],
                255,
            )
        )
    raw = bytes(row) * height
    header = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        header
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(raw, 6))
        + _chunk(b"IEND", b"")
    )


class DeterministicImageProvider:
    key = "deterministic_mock_v1"
    name = "Local deterministic image provider"
    provider_type = "mock"
    capabilities = IMAGE_CAPABILITIES

    def available(self) -> bool:
        return True

    def discover_models(self) -> list[str]:
        return ["image-deterministic-v1"]

    def validate_operation(self, operation: str) -> None:
        if operation not in {
            "generate_product_image",
            "remove_background",
            "replace_background",
            "white_background",
            "lifestyle_scene",
            "enhance_image",
            "resize",
            "crop",
            "extend_canvas",
            "promotional_creative",
            "marketplace_main_image",
            "marketplace_gallery_image",
            "thumbnail",
            "banner",
        }:
            raise StudioProviderFailure("unsupported_provider")

    def generate(
        self, *, operation: str, width: int, height: int, seed: str, scenario: str
    ) -> tuple[bytes, dict[str, object]]:
        self.validate_operation(operation)
        if scenario == "throttle":
            raise StudioProviderFailure("provider_throttled", retry_after=1)
        if scenario == "timeout":
            raise StudioProviderFailure("provider_timeout")
        if scenario == "provider_error":
            raise StudioProviderFailure("provider_unavailable")
        if scenario == "unsupported_operation":
            raise StudioProviderFailure("unsupported_provider")
        if scenario == "policy_refusal":
            raise StudioProviderFailure("policy_refusal")
        if scenario == "oversized_output":
            raise StudioProviderFailure("output_too_large")
        if scenario == "invalid_image":
            return b"not-an-image", {"deterministic": True, "scenario": scenario}
        value = deterministic_png(width, height, f"{seed}:{operation}")
        return value, {
            "deterministic": True,
            "scenario": scenario,
            "capabilities": sorted(self.capabilities),
            "mime_type": "image/png",
            "width": width,
            "height": height,
            "size_bytes": len(value),
            "checksum_sha256": hashlib.sha256(value).hexdigest(),
        }


image_provider = DeterministicImageProvider()
