"""
Deterministic computer vision image quality gates using OpenCV.

Assesses food label photographs for:
1. Blur and sharpness (Laplacian variance).
2. Resolution boundaries.
3. Glare, overexposure, and underexposure.
4. Low contrast and poor text visibility.
5. Rotation and skew angle estimation.
6. Table cropping and border proximity.

Provides advisory warnings and quality metrics.
Does NOT claim that passing checks guarantees 100% OCR accuracy.
"""

from dataclasses import dataclass, field

import cv2
import numpy as np

from app.extraction.models import ExtractionWarning

QUALITY_DISCLAIMER = (
    "Computer vision quality gates evaluate physical image properties (sharpness, lighting, "
    "contrast, resolution, and skew). These checks provide advisory warnings but cannot "
    "guarantee text legibility or numerical accuracy. Unreadable or missing values must be "
    "verified or entered manually."
)

# Threshold constants for quality evaluation
MIN_RECOMMENDED_WIDTH = 600
MIN_RECOMMENDED_HEIGHT = 400
MIN_RECOMMENDED_PIXELS = 300_000  # ~0.3 MP

BLUR_THRESHOLD_POOR = 50.0
BLUR_THRESHOLD_FAIR = 100.0

GLARE_THRESHOLD_POOR = 0.15  # 15% saturated pixels
GLARE_THRESHOLD_FAIR = 0.08  # 8% saturated pixels

UNDEREXPOSED_THRESHOLD = 40.0  # Mean intensity < 40 (out of 255)
OVEREXPOSED_THRESHOLD = 220.0  # Mean intensity > 220

LOW_CONTRAST_THRESHOLD = 30.0  # Standard deviation of intensity < 30
SKEW_WARNING_THRESHOLD_DEG = 5.0
BORDER_MARGIN_THRESHOLD_PX = 8


@dataclass(frozen=True)
class QualityMetrics:
    """Calculated numerical metrics from conventional CV analysis."""

    width: int
    height: int
    total_pixels: int
    sharpness_score: float
    glare_ratio: float
    mean_luminance: float
    contrast_std: float
    estimated_skew_degrees: float
    min_content_margin_px: int


@dataclass
class ImageQualityAssessment:
    """
    Structured outcome of pre-OCR image quality gates.
    """

    is_acceptable: bool
    grade: str  # "good", "fair", "poor"
    metrics: QualityMetrics
    warnings: list[ExtractionWarning] = field(default_factory=list)
    disclaimer: str = QUALITY_DISCLAIMER

    def to_dict(self) -> dict:
        return {
            "is_acceptable": self.is_acceptable,
            "grade": self.grade,
            "metrics": {
                "width": self.metrics.width,
                "height": self.metrics.height,
                "total_pixels": self.metrics.total_pixels,
                "sharpness_score": round(self.metrics.sharpness_score, 1),
                "glare_ratio": round(self.metrics.glare_ratio, 3),
                "mean_luminance": round(self.metrics.mean_luminance, 1),
                "contrast_std": round(self.metrics.contrast_std, 1),
                "estimated_skew_degrees": round(self.metrics.estimated_skew_degrees, 1),
                "min_content_margin_px": self.metrics.min_content_margin_px,
            },
            "warnings": [{"code": w.code, "message": w.message} for w in self.warnings],
            "disclaimer": self.disclaimer,
        }


def _estimate_skew_angle(gray: np.ndarray) -> float:
    """
    Estimates dominant text skew angle in degrees using edge detection and Hough lines.
    Returns angle in range [-45.0, 45.0].
    """
    try:
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, threshold=80, minLineLength=50, maxLineGap=10
        )
        if lines is None or len(lines) == 0:
            return 0.0

        angles: list[float] = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            dx = x2 - x1
            dy = y2 - y1
            if dx == 0:
                continue
            angle_rad = np.arctan2(dy, dx)
            angle_deg = np.degrees(angle_rad)
            # Only consider near-horizontal text lines (-45 to 45 deg)
            if -45.0 <= angle_deg <= 45.0:
                angles.append(angle_deg)

        if not angles:
            return 0.0

        median_angle = float(np.median(angles))
        return median_angle
    except Exception:
        return 0.0


def _detect_min_content_margin(gray: np.ndarray) -> int:
    """
    Detects distance from high-contrast text contours to the image perimeter.
    Used to detect potentially cropped tables.
    """
    h, w = gray.shape
    try:
        # Edge detection
        edges = cv2.Canny(gray, 75, 200)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return min(h, w) // 2

        min_margin = min(h, w)
        for c in contours:
            area = cv2.contourArea(c)
            if area < 50:  # Ignore tiny noise specks
                continue
            x, y, cw, ch = cv2.boundingRect(c)
            # Calculate distance from this bounding box to edges
            dist_left = x
            dist_top = y
            dist_right = w - (x + cw)
            dist_bottom = h - (y + ch)
            box_min = min(dist_left, dist_top, dist_right, dist_bottom)
            if box_min < min_margin:
                min_margin = box_min

        return max(0, min_margin)
    except Exception:
        return 20


def assess_image_quality(image_bytes: bytes) -> ImageQualityAssessment:
    """
    Analyzes an in-memory image buffer using OpenCV and returns deterministic quality gates.
    """
    np_arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if img is None:
        return ImageQualityAssessment(
            is_acceptable=False,
            grade="poor",
            metrics=QualityMetrics(
                width=0,
                height=0,
                total_pixels=0,
                sharpness_score=0.0,
                glare_ratio=1.0,
                mean_luminance=0.0,
                contrast_std=0.0,
                estimated_skew_degrees=0.0,
                min_content_margin_px=0,
            ),
            warnings=[
                ExtractionWarning(
                    code="IMAGE_DECODE_FAILED",
                    message="Image data could not be decoded by the computer vision processor.",
                )
            ],
        )

    h, w = img.shape[:2]
    total_pixels = h * w
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 1. Blur & Sharpness via Laplacian Variance
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    sharpness = float(laplacian.var())

    # 2. Glare & Overexposure
    glare_pixels = int(np.sum(gray >= 250))
    glare_ratio = float(glare_pixels) / float(total_pixels)
    mean_luminance = float(np.mean(gray))

    # 3. Contrast Standard Deviation
    contrast_std = float(np.std(gray))

    # 4. Skew angle estimation
    skew_angle = _estimate_skew_angle(gray)

    # 5. Table Cropping / Content Margin
    margin_px = _detect_min_content_margin(gray)

    metrics = QualityMetrics(
        width=w,
        height=h,
        total_pixels=total_pixels,
        sharpness_score=sharpness,
        glare_ratio=glare_ratio,
        mean_luminance=mean_luminance,
        contrast_std=contrast_std,
        estimated_skew_degrees=skew_angle,
        min_content_margin_px=margin_px,
    )

    warnings: list[ExtractionWarning] = []
    severe_issues = 0
    mild_issues = 0

    # Evaluate Resolution
    if w < MIN_RECOMMENDED_WIDTH or h < MIN_RECOMMENDED_HEIGHT:
        warnings.append(
            ExtractionWarning(
                code="IMAGE_LOW_RESOLUTION",
                message=(
                    f"Image resolution ({w}x{h} px) is lower than the recommended minimum "
                    f"({MIN_RECOMMENDED_WIDTH}x{MIN_RECOMMENDED_HEIGHT} px). Small text "
                    "or decimal points may fail to resolve."
                ),
            )
        )
        mild_issues += 1

    # Evaluate Sharpness
    if sharpness < BLUR_THRESHOLD_POOR:
        warnings.append(
            ExtractionWarning(
                code="IMAGE_BLUR_SEVERE",
                message=(
                    f"Image is significantly blurred (sharpness score: {sharpness:.1f}, "
                    f"recommended >= {BLUR_THRESHOLD_FAIR}). Text and numbers may be "
                    "misidentified or missed."
                ),
            )
        )
        severe_issues += 1
    elif sharpness < BLUR_THRESHOLD_FAIR:
        warnings.append(
            ExtractionWarning(
                code="IMAGE_BLUR_MILD",
                message=(
                    f"Image shows mild blur (sharpness score: {sharpness:.1f}). "
                    "Please double-check extracted numeric values carefully."
                ),
            )
        )
        mild_issues += 1

    # Evaluate Glare
    if glare_ratio > GLARE_THRESHOLD_POOR:
        warnings.append(
            ExtractionWarning(
                code="IMAGE_GLARE_SEVERE",
                message=(
                    f"Significant glare detected ({glare_ratio * 100:.1f}% saturated pixels). "
                    "Reflections from glossy packaging can obliterate text."
                ),
            )
        )
        severe_issues += 1
    elif glare_ratio > GLARE_THRESHOLD_FAIR:
        warnings.append(
            ExtractionWarning(
                code="IMAGE_GLARE_MILD",
                message=(
                    "Moderate packaging glare or reflection detected "
                    f"({glare_ratio * 100:.1f}% of image). "
                    "Ensure no nutrient values are masked by shine."
                ),
            )
        )
        mild_issues += 1

    # Evaluate Underexposure / Overexposure
    if mean_luminance < UNDEREXPOSED_THRESHOLD:
        warnings.append(
            ExtractionWarning(
                code="IMAGE_UNDEREXPOSED",
                message="Image is very dark. Low lighting reduces character contrast.",
            )
        )
        mild_issues += 1
    elif mean_luminance > OVEREXPOSED_THRESHOLD:
        warnings.append(
            ExtractionWarning(
                code="IMAGE_OVEREXPOSED",
                message=(
                    "Image is overly bright or washed out. Characters may bleed into background."
                ),
            )
        )
        mild_issues += 1

    # Evaluate Contrast
    if contrast_std < LOW_CONTRAST_THRESHOLD:
        warnings.append(
            ExtractionWarning(
                code="IMAGE_LOW_CONTRAST",
                message=(
                    "Low tonal contrast detected "
                    f"(contrast standard deviation: {contrast_std:.1f}). "
                    "Faint print or colored backgrounds may degrade OCR reliability."
                ),
            )
        )
        mild_issues += 1

    # Evaluate Skew
    if abs(skew_angle) > SKEW_WARNING_THRESHOLD_DEG:
        warnings.append(
            ExtractionWarning(
                code="IMAGE_SKEWED",
                message=(
                    f"Image appears rotated or skewed by approximately {skew_angle:.1f}°. "
                    "Tilted lines can cause multi-column text to merge incorrectly."
                ),
            )
        )
        mild_issues += 1

    # Evaluate Border Proximity (Table Cropping)
    if margin_px < BORDER_MARGIN_THRESHOLD_PX:
        warnings.append(
            ExtractionWarning(
                code="TABLE_POTENTIALLY_CROPPED",
                message=(
                    "Packaging text appears right up against the image edge. "
                    "Part of the nutrition table or serving size information may be cut off."
                ),
            )
        )
        mild_issues += 1

    # Determine overall quality grade
    if severe_issues >= 2 or (severe_issues >= 1 and mild_issues >= 2):
        grade = "poor"
        is_acceptable = False
    elif severe_issues == 1 or mild_issues >= 2:
        grade = "fair"
        is_acceptable = True
    else:
        grade = "good"
        is_acceptable = True

    return ImageQualityAssessment(
        is_acceptable=is_acceptable,
        grade=grade,
        metrics=metrics,
        warnings=warnings,
    )
