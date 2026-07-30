import struct

import pytest
from fastapi import HTTPException

from vayujit_api.media.service import image_dimensions, safe_name, validate_upload


def png(width: int = 2, height: int = 3) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + struct.pack(">II", width, height)
        + b"\x08\x06\x00\x00\x00"
        + b"\x00\x00\x00\x00"
        + b"\x00\x00\x00\x00IEND\x00\x00\x00\x00"
    )


def jpeg(width: int = 2, height: int = 3) -> bytes:
    return (
        b"\xff\xd8"
        + b"\xff\xc0\x00\x0b\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x01\x01\x11"
        + b"\xff\xd9"
    )


def webp(width: int = 2, height: int = 3) -> bytes:
    body = (
        b"WEBPVP8X"
        + b"\x0a\x00\x00\x00"
        + b"\x00\x00\x00\x00"
        + (width - 1).to_bytes(3, "little")
        + (height - 1).to_bytes(3, "little")
    )
    return b"RIFF" + len(body).to_bytes(4, "little") + body


@pytest.mark.parametrize(
    ("mime", "filename", "data", "dimensions"),
    [
        ("image/png", "image.png", png(), (2, 3)),
        ("image/jpeg", "image.jpg", jpeg(), (2, 3)),
        ("image/webp", "image.webp", webp(), (2, 3)),
    ],
)
def test_supported_media_validation(
    mime: str, filename: str, data: bytes, dimensions: tuple[int, int]
) -> None:
    result = validate_upload(filename, mime, data)
    assert result[2:4] == dimensions
    assert len(result[4]) == 64


def test_media_rejects_mime_extension_signature_corruption_and_traversal() -> None:
    for filename, mime, data in [
        ("image.svg", "image/svg+xml", b"<svg/>"),
        ("image.jpg", "image/png", png()),
        ("image.png", "image/png", b"not-an-image"),
        ("../image.png", "image/png", png()),
    ]:
        with pytest.raises(HTTPException):
            validate_upload(filename, mime, data)
    with pytest.raises(HTTPException):
        image_dimensions(png()[:-12], "image/png")
    with pytest.raises(HTTPException):
        safe_name("..\\image.png")


def test_media_rejects_oversized_and_excessive_dimensions() -> None:
    with pytest.raises(HTTPException) as oversized:
        validate_upload("large.png", "image/png", b"x" * (10 * 1024 * 1024 + 1))
    assert oversized.value.status_code == 413
    with pytest.raises(HTTPException):
        validate_upload("wide.png", "image/png", png(10001, 1))
