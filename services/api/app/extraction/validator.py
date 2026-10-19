"""
Defensive image validation module for local OCR.
Guards against decompression bombs, spoofed extensions, and malformed files.
"""

import io
from typing import Final

from PIL import Image, UnidentifiedImageError

# Global defense against decompression bombs (16 Megapixels limit)
Image.MAX_IMAGE_PIXELS = 16_000_000

SUPPORTED_IMAGE_FORMATS: Final[set[str]] = {"JPEG", "PNG", "WEBP"}
MIN_IMAGE_BYTES: Final[int] = 64


class ImageValidationError(Exception):
    """Raised when an uploaded image fails security or format validation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def validate_image_payload(
    image_bytes: bytes,
    max_bytes: int = 10_485_760,
    max_dimension: int = 4096,
    max_pixels: int = 16_000_000,
) -> tuple[int, int, str]:
    """
    Validates image bytes in memory against strict security and format criteria.

    Returns:
        tuple[int, int, str]: (width, height, format_name)

    Raises:
        ImageValidationError: If the payload is empty, corrupted, oversized, or unauthorized.
    """
    # 1. Payload size boundaries
    payload_len = len(image_bytes)
    if payload_len < MIN_IMAGE_BYTES:
        raise ImageValidationError(
            code="EMPTY_OR_TRUNCATED_IMAGE",
            message="Uploaded file is empty or too small to be a valid image.",
        )

    if payload_len > max_bytes:
        raise ImageValidationError(
            code="IMAGE_TOO_LARGE",
            message=(
                f"Image file size ({payload_len} bytes) exceeds maximum limit of {max_bytes} bytes."
            ),
        )

    # 2. Decompression bomb protection in Pillow
    Image.MAX_IMAGE_PIXELS = max_pixels

    # 3. Verify container structure
    try:
        stream = io.BytesIO(image_bytes)
        with Image.open(stream) as img:
            img.verify()
    except Image.DecompressionBombError:
        raise ImageValidationError(
            code="DECOMPRESSION_BOMB_DETECTED",
            message="Image exceeds safe pixel density limits and was rejected for security.",
        ) from None
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ImageValidationError(
            code="INVALID_IMAGE_FORMAT",
            message="File content is corrupted or not a recognized image.",
        ) from exc

    # 4. Re-open to inspect metadata and dimensions
    try:
        stream.seek(0)
        with Image.open(stream) as img:
            format_name = (img.format or "").upper()
            if format_name not in SUPPORTED_IMAGE_FORMATS:
                raise ImageValidationError(
                    code="UNSUPPORTED_IMAGE_FORMAT",
                    message=(
                        f"Image format '{format_name}' is not supported. "
                        f"Allowed formats: {', '.join(sorted(SUPPORTED_IMAGE_FORMATS))}."
                    ),
                )

            width, height = img.size
            if width <= 0 or height <= 0:
                raise ImageValidationError(
                    code="INVALID_IMAGE_DIMENSIONS",
                    message="Image has invalid zero or negative dimensions.",
                )

            if width > max_dimension or height > max_dimension:
                raise ImageValidationError(
                    code="IMAGE_DIMENSION_EXCEEDED",
                    message=(
                        f"Image dimensions ({width}x{height}) exceed maximum allowed dimension "
                        f"of {max_dimension}px."
                    ),
                )

            if width * height > max_pixels:
                raise ImageValidationError(
                    code="IMAGE_PIXEL_LIMIT_EXCEEDED",
                    message=(
                        f"Total pixel count ({width * height}) exceeds limit "
                        f"of {max_pixels} pixels."
                    ),
                )

            return width, height, format_name

    except ImageValidationError:
        raise
    except Exception as exc:
        raise ImageValidationError(
            code="IMAGE_INSPECTION_FAILED",
            message="Failed to inspect image properties.",
        ) from exc
