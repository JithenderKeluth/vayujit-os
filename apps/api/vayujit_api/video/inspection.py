from __future__ import annotations

import struct
from collections.abc import Iterator
from dataclasses import dataclass


class VideoInspectionError(ValueError):
    pass


@dataclass(frozen=True)
class VideoInspection:
    container: str
    mime_type: str
    video_stream_count: int
    audio_stream_count: int
    duration_seconds: float
    width: int
    height: int
    frame_rate: float | None
    size_bytes: int
    checksum_sha256: str


def _children(data: bytes, start: int, end: int) -> Iterator[tuple[bytes, int, int]]:
    offset = start
    while offset + 8 <= end:
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        header = 8
        if size == 1:
            if offset + 16 > end:
                raise VideoInspectionError("Video container is malformed.")
            size = struct.unpack(">Q", data[offset + 8 : offset + 16])[0]
            header = 16
        if size < header or offset + size > end:
            raise VideoInspectionError("Video container is truncated.")
        yield kind, offset + header, offset + size
        offset += size
    if offset != end:
        raise VideoInspectionError("Video container is malformed.")


def inspect_video(data: bytes) -> VideoInspection:
    import hashlib

    if len(data) < 16:
        raise VideoInspectionError("Video container is too small.")
    atoms = list(_children(data, 0, len(data)))
    if not any(kind == b"ftyp" for kind, _, _ in atoms):
        raise VideoInspectionError("Unsupported or malformed video container.")
    moov = next((bounds for kind, *bounds in atoms if kind == b"moov"), None)
    if moov is None:
        raise VideoInspectionError("Video container has no metadata.")
    moov_start, moov_end = moov
    mvhd = next((b for k, *b in _children(data, moov_start, moov_end) if k == b"mvhd"), None)
    if mvhd is None or mvhd[1] - mvhd[0] < 20:
        raise VideoInspectionError("Video duration metadata is missing.")
    mvhd_data = data[mvhd[0] : mvhd[1]]
    if mvhd_data[0] != 0:
        raise VideoInspectionError("Unsupported video metadata version.")
    timescale = struct.unpack(">I", mvhd_data[12:16])[0]
    duration = struct.unpack(">I", mvhd_data[16:20])[0]
    if not timescale or not duration:
        raise VideoInspectionError("Video duration is invalid.")
    video_streams = 0
    audio_streams = 0
    width = height = 0
    frame_rate: float | None = None
    for kind, trak_start, trak_end in _children(data, moov_start, moov_end):
        if kind != b"trak":
            continue
        mdia = next((b for k, *b in _children(data, trak_start, trak_end) if k == b"mdia"), None)
        tkhd = next((b for k, *b in _children(data, trak_start, trak_end) if k == b"tkhd"), None)
        if mdia is None:
            continue
        mdia_atoms = list(_children(data, mdia[0], mdia[1]))
        hdlr = next((b for k, *b in mdia_atoms if k == b"hdlr"), None)
        if hdlr is None:
            continue
        handler = data[hdlr[0] + 8 : hdlr[0] + 12]
        if handler == b"vide":
            video_streams += 1
            if tkhd is None or tkhd[1] - tkhd[0] < 84:
                raise VideoInspectionError("Video dimensions are missing.")
            tkhd_data = data[tkhd[0] : tkhd[1]]
            width = struct.unpack(">I", tkhd_data[-8:-4])[0] >> 16
            height = struct.unpack(">I", tkhd_data[-4:])[0] >> 16
            stbl = next(
                (
                    b
                    for k, *b in _children(
                        data,
                        next(b for k, *b in mdia_atoms if k == b"minf")[0],
                        next(b for k, *b in mdia_atoms if k == b"minf")[1],
                    )
                    if k == b"stbl"
                ),
                None,
            )
            if stbl:
                stts = next(
                    (b for k, *b in _children(data, stbl[0], stbl[1]) if k == b"stts"), None
                )
                if stts and stts[1] - stts[0] >= 16:
                    values = data[stts[0] : stts[1]]
                    count, sample_count, delta = struct.unpack(">III", values[4:16])
                    if count and sample_count and delta:
                        frame_rate = sample_count * timescale / duration
        elif handler == b"soun":
            audio_streams += 1
    if video_streams != 1 or width <= 0 or height <= 0:
        raise VideoInspectionError("Video must contain one valid video stream.")
    return VideoInspection(
        container="mp4",
        mime_type="video/mp4",
        video_stream_count=video_streams,
        audio_stream_count=audio_streams,
        duration_seconds=duration / timescale,
        width=width,
        height=height,
        frame_rate=frame_rate,
        size_bytes=len(data),
        checksum_sha256=hashlib.sha256(data).hexdigest(),
    )
