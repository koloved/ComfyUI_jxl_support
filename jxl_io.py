"""JPEG XL container format utilities with Brotli-compressed metadata support."""

import io
import json
import math
import struct
import numpy as np

try:
    import brotli
    _BROTLI_AVAILABLE = True
except ImportError:
    _BROTLI_AVAILABLE = False

try:
    import imagecodecs
    _JXL_AVAILABLE = True
except ImportError:
    _JXL_AVAILABLE = False


# -- Constants -----------------------------------------------------------

_JXL_SIG = struct.pack(">I", 12) + b"JXL " + bytes([0x0d, 0x0a, 0x87, 0x0a])

_FTYP_BOX = (
    struct.pack(">I", 20)
    + b"ftyp"
    + b"jxl "
    + struct.pack(">I", 0)
    + b"jxl "
)


# -- Container building / parsing -----------------------------------------


def _make_box(box_type: bytes, data: bytes) -> bytes:
    return struct.pack(">I", 8 + len(data)) + box_type + data


def _parse_boxes(data: bytes) -> list[dict]:
    boxes = []
    offset = 0
    while offset + 8 <= len(data):
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        box_type = data[offset + 4 : offset + 8]
        if size == 0:
            break
        if size < 8 or offset + size > len(data):
            break
        box_data = data[offset + 8 : offset + size]
        boxes.append({"type": box_type, "data": box_data, "size": size})
        offset += size
    return boxes


def _find_box(boxes: list[dict], box_type: bytes):
    for box in boxes:
        if box["type"] == box_type:
            return box
    return None


# -- Metadata helpers ----------------------------------------------------


def _compress_metadata(data: bytes):
    if not _BROTLI_AVAILABLE:
        return None
    return brotli.compress(data)


def _decompress_metadata(data: bytes):
    if not _BROTLI_AVAILABLE:
        return None
    try:
        return brotli.decompress(data)
    except brotli.error:
        return None


def _clean_nan(obj):
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean_nan(v) for v in obj]
    return obj


def _build_metadata_blob(prompt: dict | None, extra_pnginfo: dict | None) -> bytes:
    metadata = {}
    if prompt is not None:
        metadata["prompt"] = _clean_nan(prompt)
    if extra_pnginfo is not None:
        for key, value in extra_pnginfo.items():
            metadata[key] = _clean_nan(value)
    return json.dumps(metadata, allow_nan=False).encode("utf-8")


def _parse_metadata_blob(raw: bytes) -> dict:
    try:
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


# -- Core encode / decode ------------------------------------------------


def encode_jxl(
    image: np.ndarray,
    quality: int = 100,
    compress_metadata: bool = True,
    prompt: dict | None = None,
    extra_pnginfo: dict | None = None,
) -> bytes:
    """Encode a numpy image (HxWxC, uint8) to a JXL container with optional metadata.

    Quality 100 = lossless. Lower values = more compression.
    """
    if not _JXL_AVAILABLE:
        raise RuntimeError(
            "imagecodecs is not available. Install it with: pip install imagecodecs"
        )

    if quality >= 100:
        codestream = imagecodecs.jpegxl_encode(image, lossless=True)
    else:
        distance = (100 - quality) * 0.15
        codestream = imagecodecs.jpegxl_encode(image, lossless=False, distance=distance)

    container = _JXL_SIG + _FTYP_BOX
    container += _make_box(b"jxlc", codestream)

    if prompt is not None or extra_pnginfo is not None:
        raw_meta = _build_metadata_blob(prompt, extra_pnginfo)
        if compress_metadata and _BROTLI_AVAILABLE:
            compressed = _compress_metadata(raw_meta)
            if compressed is not None:
                brob_content = b"comf" + compressed
                container += _make_box(b"brob", brob_content)
        else:
            container += _make_box(b"brob", b"comf" + raw_meta)

    return container


def decode_jxl(data: bytes):
    """Decode a JXL file to (image_array, metadata_dict)."""
    if not _JXL_AVAILABLE:
        raise RuntimeError(
            "imagecodecs is not available. Install it with: pip install imagecodecs"
        )

    metadata = {}

    if _is_container(data):
        boxes = _parse_boxes(data)
        brob = _find_box(boxes, b"brob")
        if brob is not None:
            raw_type = brob["data"][:4]
            compressed = brob["data"][4:]
            if raw_type == b"comf":
                decompressed = _decompress_metadata(compressed)
                if decompressed is not None:
                    metadata = _parse_metadata_blob(decompressed)
        codestream = _extract_codestream_from_boxes(boxes)
        if codestream is None:
            raise ValueError("No JXL codestream found in container")
    else:
        codestream = data

    image = imagecodecs.jpegxl_decode(codestream)
    return image, metadata


def _is_container(data: bytes) -> bool:
    if len(data) < 32:
        return False
    return (
        struct.unpack(">I", data[:4])[0] == 12
        and data[4:8] == b"JXL "
        and data[8:12] == bytes([0x0d, 0x0a, 0x87, 0x0a])
        and struct.unpack(">I", data[12:16])[0] == 20
        and data[16:20] == b"ftyp"
        and data[20:24] == b"jxl "
    )


def extract_jxl_metadata(data: bytes) -> dict:
    """Extract metadata from a JXL container without decoding the image."""
    metadata = {}
    if not _is_container(data):
        return metadata
    boxes = _parse_boxes(data)
    brob = _find_box(boxes, b"brob")
    if brob is not None:
        raw_type = brob["data"][:4]
        compressed = brob["data"][4:]
        if raw_type == b"comf":
            decompressed = _decompress_metadata(compressed)
            if decompressed is not None:
                metadata = _parse_metadata_blob(decompressed)
    return metadata


def _find_box_by_type(boxes: list[dict], box_type: bytes):
    for box in boxes:
        if box["type"] == box_type:
            return box
    return None


def _extract_codestream_from_boxes(boxes: list[dict]):
    jxlc = _find_box_by_type(boxes, b"jxlc")
    if jxlc is not None:
        return jxlc["data"]
    for box in boxes:
        if box["type"] == b"jxlp" and len(box["data"]) > 1:
            return box["data"][1:]
    return None
