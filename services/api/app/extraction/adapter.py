"""
Pluggable OCR Adapter interfaces and implementations.
Implements the Replaceable Adapter pattern with multi-pass OCR and discrepancy detection.
"""

import io
import os
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageEnhance, ImageOps

from app.extraction.quality import _estimate_skew_angle

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


@dataclass
class OcrEngineOutput:
    """
    Richer outcome of local OCR engine execution with dual-pass discrepancy tracking.
    Supports backward-compatible 2-tuple unpacking via __iter__ (raw_text, confidence).
    """

    raw_text: str
    confidence: float | None
    pass_a_text: str | None = None
    pass_b_text: str | None = None
    pass_discrepancy: bool = False
    discrepancy_details: list[str] = field(default_factory=list)

    def __iter__(self):
        """Allows unpacking directly as (raw_text, confidence) for backwards compatibility."""
        return iter((self.raw_text, self.confidence))


class BaseOcrAdapter(ABC):
    """
    Abstract adapter for local OCR engines.
    Allows transparent replacement of Tesseract with alternative engines.
    """

    @abstractmethod
    def extract_text(self, image_bytes: bytes) -> OcrEngineOutput:
        """
        Executes local OCR on verified image bytes in memory.
        """
        ...


class TesseractOcrAdapter(BaseOcrAdapter):
    """
    Adapter implementing offline OCR using Tesseract, OpenCV, and Pillow.
    Features dual-pass preprocessing (normalized grayscale vs deskewed binary)
    and deterministic discrepancy auditing between passes.
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

    def _preprocess_pass_a(self, img_bytes: bytes) -> Image.Image:
        """
        Pass A: Normalized grayscale with CLAHE and mild sharpening.
        Optimal for clear, high-contrast packaging prints.
        """
        np_arr = np.frombuffer(img_bytes, np.uint8)
        cv_img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if cv_img is None:
            # Fallback to Pillow
            stream = io.BytesIO(img_bytes)
            with Image.open(stream) as img:
                gray = img.convert("L")
                contrasted = ImageOps.autocontrast(gray, cutoff=2)
                return ImageEnhance.Sharpness(contrasted).enhance(1.5)

        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        equalized = clahe.apply(gray)
        blurred = cv2.GaussianBlur(equalized, (3, 3), 0)
        sharpened = cv2.addWeighted(equalized, 1.5, blurred, -0.5, 0)
        return Image.fromarray(sharpened)

    def _preprocess_pass_b(self, img_bytes: bytes) -> Image.Image:
        """
        Pass B: Deskewed Otsu adaptive thresholding.
        Optimal for rotated, shaded, or low-contrast packaging.
        """
        np_arr = np.frombuffer(img_bytes, np.uint8)
        cv_img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if cv_img is None:
            stream = io.BytesIO(img_bytes)
            with Image.open(stream) as img:
                return img.convert("L").point(lambda p: 255 if p > 128 else 0)

        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        skew_angle = _estimate_skew_angle(gray)

        # Deskew if angle is notable
        if 1.0 < abs(skew_angle) < 45.0:
            h, w = gray.shape[:2]
            center = (w // 2, h // 2)
            rot_mat = cv2.getRotationMatrix2D(center, -skew_angle, 1.0)
            gray = cv2.warpAffine(
                gray, rot_mat, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
            )

        # Otsu thresholding
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return Image.fromarray(binary)

    def _run_tesseract(self, img: Image.Image, psm: int = 6) -> tuple[str, float | None]:
        config = f"--psm {psm}"
        raw_text = pytesseract.image_to_string(
            img,
            lang="eng",
            config=config,
            timeout=int(self.timeout_seconds),
        )
        data = pytesseract.image_to_data(
            img,
            lang="eng",
            config=config,
            output_type=pytesseract.Output.DICT,
            timeout=int(self.timeout_seconds),
        )
        confidences = [
            float(c) for c in data.get("conf", []) if isinstance(c, (int, float)) and c > 0
        ]
        avg_conf = round(sum(confidences) / len(confidences), 1) if confidences else None
        return raw_text.strip(), avg_conf

    def extract_text(self, image_bytes: bytes) -> OcrEngineOutput:
        if not self.is_available():
            raise OcrEngineUnavailableError(
                "Tesseract OCR is not installed or configured on the server. "
                "Please configure TESSERACT_CMD or install Tesseract-OCR."
            )

        try:
            # Pass A: Normalized CLAHE
            img_a = self._preprocess_pass_a(image_bytes)
            text_a, conf_a = self._run_tesseract(img_a, psm=6)

            # Pass B: Deskewed Binarization
            img_b = self._preprocess_pass_b(image_bytes)
            text_b, conf_b = self._run_tesseract(img_b, psm=4)

            # Compare Pass A and Pass B
            words_a = set(text_a.lower().split())
            words_b = set(text_b.lower().split())

            discrepancy = False
            details: list[str] = []

            # Check word overlap
            if words_a or words_b:
                intersection = words_a.intersection(words_b)
                union = words_a.union(words_b)
                jaccard = len(intersection) / len(union) if union else 1.0
                if jaccard < 0.40 and len(words_a) > 5 and len(words_b) > 5:
                    discrepancy = True
                    details.append(
                        "Dual OCR preprocessing passes produced divergent word sets "
                        f"(overlap: {jaccard * 100:.0f}%)."
                    )

            # Choose primary text: the richer extraction
            if len(text_b) > len(text_a) * 1.3:
                primary_text = text_b
                primary_conf = conf_b
            else:
                primary_text = text_a
                primary_conf = conf_a

            return OcrEngineOutput(
                raw_text=primary_text,
                confidence=primary_conf,
                pass_a_text=text_a,
                pass_b_text=text_b,
                pass_discrepancy=discrepancy,
                discrepancy_details=details,
            )

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
        pass_a_text: str | None = None,
        pass_b_text: str | None = None,
        pass_discrepancy: bool = False,
    ) -> None:
        self.mock_text = mock_text
        self.mock_confidence = mock_confidence
        self.should_timeout = should_timeout
        self.should_fail = should_fail
        self.pass_a_text = pass_a_text or mock_text
        self.pass_b_text = pass_b_text or mock_text
        self.pass_discrepancy = pass_discrepancy

    def extract_text(self, image_bytes: bytes) -> OcrEngineOutput:
        if self.should_timeout:
            raise OcrTimeoutError(15.0)
        if self.should_fail:
            raise OcrEngineError("OCR_MOCK_FAILURE", "Simulated OCR failure.")
        return OcrEngineOutput(
            raw_text=self.mock_text,
            confidence=self.mock_confidence,
            pass_a_text=self.pass_a_text,
            pass_b_text=self.pass_b_text,
            pass_discrepancy=self.pass_discrepancy,
            discrepancy_details=["Simulated dual-pass discrepancy"]
            if self.pass_discrepancy
            else [],
        )
