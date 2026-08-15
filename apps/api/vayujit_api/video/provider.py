from __future__ import annotations

import hashlib
import struct
from collections.abc import Iterator
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

    @staticmethod
    def _deterministic_variant(data: bytes, *, width: int, height: int, duration: int) -> bytes:
        """Adapt the checked-in MP4 fixture without adding a second renderer."""
        if width <= 0 or height <= 0 or duration <= 0:
            return data
        output = bytearray(data)

        def children(start: int, end: int) -> Iterator[tuple[bytes, int, int]]:
            offset = start
            while offset + 8 <= end:
                size = struct.unpack(">I", output[offset : offset + 4])[0]
                header = 8
                if size == 1:
                    size = struct.unpack(">Q", output[offset + 8 : offset + 16])[0]
                    header = 16
                if size < header or offset + size > end:
                    return
                yield bytes(output[offset + 4 : offset + 8]), offset + header, offset + size
                offset += size

        def visit(start: int, end: int) -> None:
            for kind, content_start, content_end in children(start, end):
                if kind in {b"mvhd", b"mdhd"} and content_end - content_start >= 20:
                    output[content_start + 12 : content_start + 16] = struct.pack(">I", 1000)
                    output[content_start + 16 : content_start + 20] = struct.pack(
                        ">I", duration * 1000
                    )
                elif kind == b"tkhd" and content_end - content_start >= 84:
                    output[content_end - 8 : content_end - 4] = struct.pack(">I", width << 16)
                    output[content_end - 4 : content_end] = struct.pack(">I", height << 16)
                elif kind == b"avc1" and content_end - content_start >= 28:
                    output[content_start + 24 : content_start + 26] = struct.pack(">H", width)
                    output[content_start + 26 : content_start + 28] = struct.pack(">H", height)
                if kind in {b"moov", b"trak", b"mdia", b"minf", b"stbl", b"stsd"}:
                    visit(content_start, content_end)

        visit(0, len(output))
        return bytes(output)

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
        fixture = self._deterministic_variant(
            fixture, width=width, height=height, duration=duration
        )
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
