from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VideoProviderCapabilities:
    workflow_supported: bool = True
    visual_effect_simulated: bool = True
    live_provider_supported: bool = False
    operations: tuple[str, ...] = (
        "video_generation",
        "image_to_video",
        "slideshow",
        "video_resize",
        "video_trim",
        "video_thumbnail",
        "subtitle_generation",
    )


class DeterministicLocalVideoProvider:
    key = "deterministic_video_local"
    name = "Deterministic Local Video Workflow"
    model = "local-slideshow-v1"
    capabilities = VideoProviderCapabilities()

    def generate(
        self, *, seed: str, width: int, height: int, duration: int, scenario: str = "success"
    ) -> tuple[bytes, dict[str, object]]:
        if scenario == "provider_unavailable":
            raise RuntimeError("Local video provider is unavailable.")
        if scenario == "unsupported_operation":
            raise ValueError("Video operation is unsupported.")
        if scenario == "policy_rejection":
            raise PermissionError("Video request was rejected by policy.")
        if scenario == "invalid_video":
            return b"not-a-video", {"mime_type": "video/mp4"}
        fixture = Path(__file__).with_name("fixture.mp4").read_bytes()
        if scenario == "truncated_output":
            truncated = fixture[: max(12, len(fixture) // 3)]
            return b"\x00\x00\x00\x18" + truncated[4:], {"mime_type": "video/mp4"}
        if scenario == "oversized_video":
            return fixture + (b"x" * 9_000_000), {"mime_type": "video/mp4"}
        digest = hashlib.sha256(f"{seed}:{width}:{height}:{duration}".encode()).hexdigest()[:24]
        payload = bytes.fromhex(
            hashlib.sha256(f"{seed}:{width}:{height}:{duration}".encode()).hexdigest()
        )
        free_atom = struct.pack(">I4s", 8 + len(payload), b"free") + payload
        return fixture + free_atom, {
            "mime_type": "video/mp4",
            "provider_request_id": f"local:{digest}",
        }

    def health(self) -> dict[str, object]:
        return {
            "provider": self.key,
            "available": True,
            "local": True,
            "workflow_supported": True,
            "visual_effect_simulated": True,
            "live_provider_supported": False,
            "capabilities": list(self.capabilities.operations),
            "safe_message": "Local deterministic video workflow provider is healthy.",
        }


video_provider = DeterministicLocalVideoProvider()
