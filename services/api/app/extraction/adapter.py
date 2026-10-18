"""
Pluggable OCR Adapter interfaces and implementations.
Implements the Replaceable Adapter pattern.
"""

import io
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Final

import pytesseract
from PIL import Image, ImageEnhance, ImageOps

DEFAULT_TIMEOUT_SECONDS: Final[float] = 15.0


class OcrEngineError(Exception):
    """Base exception for OCR engine execution failures."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class OcrEngineUnavailableError(OcrEngineError):
    """Raised when the OCR binary or engine runtime is not installed or available."""

    def __init__(self, message: str = "OCR engine is unavailable on the host system.") -> None:
        super().__init__(code="OCR_ENGINE_UNAVAILABLE", message=message)


class OcrTimeoutError(OcrEngineError):
    """Raised when the OCR extraction exceeds configured time limits."""

    def __init__(self, timeout_seconds: float) -> None:
        super().__init__(
            code="OCR_TIMEOUT_ERROR",
            message=f"OCR processing timed out after {timeout_seconds} seconds.",
        )


class BaseOcrAdapter(ABC):
    """
    Abstract adapter for local OCR engines.
    Allows transparent replacement of Tesseract with alternative engines.
    """

    @abstractmethod
    def extract_text(self, image_bytes: bytes) -> tuple[str, float | None]:
        """
        Executes local OCR on verified image bytes in memory.

        Returns:
            tuple[str, float | None]: (extracted_raw_text, confidence_score_0_to_100)
        """
        ...


class TesseractOcrAdapter(BaseOcrAdapter):
    """
    Adapter implementing offline OCR using Tesseract and Pillow.
    """

    def __init__(
        self,
        tesseract_cmd: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.resolved_cmd = self._resolve_tesseract_cmd(tesseract_cmd)
        if self.resolved_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.resolved_cmd

    @staticmethod
    def _resolve_tesseract_cmd(explicit_cmd: str | None) -> str | None:
        if explicit_cmd and Path(explicit_cmd).is_file():
            return explicit_cmd

        # Check standard PATH
        on_path = shutil.which("tesseract")
        if on_path:
            return on_path

        # Check common Windows installation locations
        if os.name == "nt":
            candidate_paths = [
                Path(os.environ.get("LOCALAPPDATA", ""))
                / "Programs"
                / "Tesseract-OCR"
                / "tesseract.exe",
                Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
                Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
            ]
            for candidate in candidate_paths:
                if candidate.is_file():
                    return str(candidate)

        return None

    def is_available(self) -> bool:
        """Verifies whether the Tesseract executable is present and callable."""
        return self.resolved_cmd is not None and Path(self.resolved_cmd).is_file()

    def _preprocess_image(self, img: Image.Image) -> Image.Image:
        """
        Applies non-destructive in-memory preprocessing to improve OCR accuracy
        on packaged food labels (lighting correction, contrast enhancement).
        """
        # Convert to grayscale
        gray = img.convert("L")

        # Auto-contrast normalization
        contrasted = ImageOps.autocontrast(gray, cutoff=2)

        # Mild sharpness enhancement
        enhancer = ImageEnhance.Sharpness(contrasted)
        sharpened = enhancer.enhance(1.5)

        return sharpened

    def extract_text(self, image_bytes: bytes) -> tuple[str, float | None]:
        if not self.is_available():
            raise OcrEngineUnavailableError(
                "Tesseract OCR is not installed or configured on the server. "
                "Please configure TESSERACT_CMD or install Tesseract-OCR."
            )

        try:
            stream = io.BytesIO(image_bytes)
            with Image.open(stream) as img:
                processed = self._preprocess_image(img)

                # 1. Extract full text structure
                raw_text = pytesseract.image_to_string(
                    processed,
                    lang="eng",
                    timeout=int(self.timeout_seconds),
                )

                # 2. Extract confidence metrics
                data = pytesseract.image_to_data(
                    processed,
                    lang="eng",
                    output_type=pytesseract.Output.DICT,
                    timeout=int(self.timeout_seconds),
                )

                # Compute average confidence over recognized words
                confidences: list[float] = [
                    float(c) for c in data.get("conf", []) if isinstance(c, (int, float)) and c > 0
                ]
                avg_confidence = (
                    round(sum(confidences) / len(confidences), 1) if confidences else None
                )

                return raw_text.strip(), avg_confidence

        except pytesseract.TesseractTimeoutError:
            raise OcrTimeoutError(self.timeout_seconds) from None
        except pytesseract.TesseractNotFoundError:
            raise OcrEngineUnavailableError(
                "Tesseract executable was not found at configured path."
            ) from None
        except Exception as exc:
            raise OcrEngineError(
                code="OCR_EXECUTION_FAILED",
                message="Local OCR execution encountered an error processing the image.",
            ) from exc


class MockOcrAdapter(BaseOcrAdapter):
    """
    Mock adapter for fast, deterministic unit and integration testing.
    """

    def __init__(
        self,
        mock_text: str = "",
        mock_confidence: float | None = 90.0,
        should_timeout: bool = False,
        should_fail: bool = False,
    ) -> None:
        self.mock_text = mock_text
        self.mock_confidence = mock_confidence
        self.should_timeout = should_timeout
        self.should_fail = should_fail

    def extract_text(self, image_bytes: bytes) -> tuple[str, float | None]:
        if self.should_timeout:
            raise OcrTimeoutError(15.0)
        if self.should_fail:
            raise OcrEngineError("OCR_MOCK_FAILURE", "Simulated OCR failure.")
        return self.mock_text, self.mock_confidence
