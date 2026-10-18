# Real-World Packaged Food Label Photo Collection Guide

This guide establishes the standardized physical acquisition and ground-truth transcription protocol for assembling real packaging photographs for the `healthyIndia` optical character recognition (OCR) and deterministic parsing benchmark.

---

## 1. Objectives and Scientific Integrity

The purpose of this protocol is to assemble a rigorous, reproducible, and unbiased physical dataset.
To maintain evidential integrity:
- **Never fabricate photos or ground-truth entries**: Synthetic images, web scrapes of digital graphics, and mock values are prohibited.
- **Fail-closed unmeasured status**: If physical image files are not bundled on disk, benchmark evaluations remain strictly `UNMEASURED` with 0 evaluated samples.
- **Double-blind provenance**: The personnel capturing photographs and transcribing ground truth must follow independent verification before inclusion.

---

## 2. Photographic Capture Protocol

### 2.1 Camera Hardware and Optical Settings
- **Hardware**: Standard smartphone cameras (e.g. 12 MP–48 MP primary sensor). High-end professional DSLR setups are discouraged unless matching typical consumer mobile capabilities.
- **Flash / Illumination**: Turn off camera LED flash (flash creates localized whiteout hotspots on metallized pouches). Use ambient room lighting or diffuse window daylight.
- **Focus**: Tap-to-focus directly on the numerical nutrition table. Ensure micro-text (<6 pt font) is optically sharp with no motion blur or depth-of-field falloff.
- **Resolution**: Capture at native sensor resolution (minimum 1920x1080, recommended 3000x4000 or 4000x3000). Save as high-quality JPEG (`.jpg`/`.jpeg`) or PNG. Do not downscale or apply heavy beauty filters/HDR smoothing that distorts character strokes.

### 2.2 Framing and Composition
- **Framing F1 (Optimal Crop)**: Center the nutrition facts panel and ingredient statement so they occupy 70%–85% of the frame. Include a small border of surrounding packaging for context.
- **Framing F2 (Consumer Context)**: Frame the package so the nutrition panel occupies 30%–50% of the frame, capturing surrounding graphics, brand markings, or seals.
- **Aspect Ratio**: Native 4:3 or 16:9 vertical/horizontal depending on packaging geometry.

### 2.3 Lighting Environments
- **Condition L1 (Natural Diffuse Daylight)**:
  - 500–1000 lux indirect daylight near a window.
  - Zero direct sunbeams hitting the packaging.
  - Color temperature ~5000 K–6500 K.
- **Condition L2 (Domestic Artificial Ambient)**:
  - Standard domestic or office warm/cool LED/CFL ceiling lighting (150–350 lux).
  - No harsh point reflections directly over numerical cells.
- **Condition L3 (Specular Reflection / Glare Stress Test)**:
  - Direct directional lamp or un-diffused light source striking the glossy/metallized film at an angle that creates glare across at least one nutrient row.
  - Used specifically to stress-test OCR glare robustness.

### 2.4 Perspective and Presentation Angles
- **Angle A1 (Orthogonal / Planar)**:
  - Camera lens plane parallel to the label surface (tilt angle ≤ 10°).
  - Minimizes keystoning and trapezoidal distortion.
- **Angle A2 (Handheld Skew)**:
  - Realistic handheld angle (15°–35° pitch or yaw tilt).
  - Evaluates OCR perspective tolerance and de-skewing algorithms.

### 2.5 Packaging Physical States
- **State S1 (Pristine / Planar)**:
  - Unopened, flat package supported against a flat surface (e.g., cereal carton panel, chocolate bar face).
- **State S2 (Cylindrical / Curved)**:
  - Bottles, cans, yogurt cups, spice jars photographed in their natural curved state without mechanical flattening.
- **State S3 (Creased / Wrinkled / Puffed)**:
  - Pillow namkeen pouches, crumpled snack bags, or flow-wrapped biscuit sleeves with natural fold lines, seam ridges, or puff inflation.

---

## 3. Data Leakage Prevention (Brand & SKU Splitting)

To prevent data contamination between algorithm development (e.g. prompt engineering, regex tuning, preprocessing heuristics) and final evaluation:

1. **Split by Brand and Category, Not Just Framing**:
   - Never place photograph A of a specific product (e.g., *Brand X Salted Peanuts 50g*) in the training/tuning set and photograph B of the same SKU in the evaluation set.
   - Entire brands or distinct SKU product lines must be isolated:
     - **Evaluation Split (Benchmark)**: Held-out SKUs that the parser rules or regex patterns were never tuned against.
     - **Development / Tuning Split**: Used for prototyping regular expressions, unit normalization, and OCR pre-filters.
2. **Exclusion of Evaluation SKUs from Regex Whitelists**:
   - Parser code must not contain hardcoded product names, proprietary serving sizes, or custom nutrient values tailored to benchmark samples.

---

## 4. Double-Blind Ground Truth Transcription Protocol

To guarantee error-free ground truth:

1. **Primary Transcription (Transcriber A)**:
   - Reads the physical packaging under strong light with a magnifying glass if necessary.
   - Transcribes every numerical value verbatim as declared on the packaging (e.g., energy, protein, total fat, saturated fat, trans fat, carbohydrates, total sugars, added sugars, sodium).
   - Records the exact declaration basis: `"per_100g"`, `"per_100ml"`, or `"per_serving"`.
   - Records serving size and unit if specified.
   - Transcribes the full ingredient list verbatim including parenthetical sub-ingredients and additives.
2. **Secondary Independent Verification (Reviewer B)**:
   - An independent reviewer examines the pristine photograph and verifies character-for-character every transcribed field.
   - Cross-checks:
     - Energy unit (`kcal` vs `kJ`).
     - Trans fat declared value (`<0.2` vs `0.1` vs `0` vs `0.0`).
     - Added sugars vs Total sugars.
     - Sodium unit (`mg` vs `g`).
     - Serving size and servings per container.
3. **Discrepancy Resolution**:
   - Any difference between Transcriber A and Reviewer B triggers physical reinspection of the package.
   - If a number is smudged, torn, or illegible on the physical package, set that field to `null` with `"readability": "unreadable_due_to_smudge"` rather than guessing.

---

## 5. Image Integrity & SHA-256 Digest Calculation

Every image file added to `data/real_food_labels/images/` must have its cryptographic SHA-256 digest recorded in `samples.json`.

### 5.1 Computing SHA-256 Digest
Run the standard CLI or script on the pristine image file:

#### Linux / macOS:
```bash
sha256sum data/real_food_labels/images/RFL-001.jpg
```

#### Windows PowerShell:
```powershell
Get-FileHash -Algorithm SHA256 data\real_food_labels\images\RFL-001.jpg
```

#### Python:
```python
import hashlib
from pathlib import Path

img_path = Path("data/real_food_labels/images/RFL-001.jpg")
digest = hashlib.sha256(img_path.read_bytes()).hexdigest()
print(digest)
```

### 5.2 Verification Rule
The benchmark runner will verify that:
1. The image exists in `data/real_food_labels/images/{image_filename}`.
2. The SHA-256 hash of the file on disk matches `image_sha256` declared in `samples.json`. If a mismatch occurs, the sample fails verification.

---

## 6. Annotation Workflow Summary

1. **Acquire packaging**: Purchase representative consumer packaged food item in Indian retail.
2. **Capture photograph**: Follow camera settings, lighting, angle, and state guidelines in Section 2.
3. **Save image**: Store in `data/real_food_labels/images/RFL-XXX.<ext>`.
4. **Compute SHA-256**: Calculate cryptographic hash using Section 5.
5. **Transcribe Ground Truth**: Complete double-blind transcription following Section 4.
6. **Populate `samples.json`**: Add JSON entry matching `data/real_food_labels/annotation_template.json`.
7. **Run Validation Script**:
   ```bash
   python services/api/scripts/validate_dataset.py
   ```
8. **Run Benchmark Script**:
   ```bash
   python services/api/scripts/run_real_photo_benchmark.py
   ```
