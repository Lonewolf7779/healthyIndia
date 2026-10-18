# Real-World Food Packaging Photo Dataset Specification

## 1. Overview and Purpose

The `healthyIndia` real-world packaging photo dataset provides a standardized, reproducible benchmark for evaluating computer vision, optical character recognition (OCR), table layout parsing, and nutrition calculation under physical conditions representative of the Indian retail market.

Unlike synthetic text renders or digital graphics, physical food packaging exhibits severe real-world challenges:
- Surface curvature (cylindrical bottles, tapered jars, flexible pouches)
- Material specular reflections and glare spots (metallized polyester, foil wrappers, glossy OPP laminates)
- Wrinkles, folds, and seam distortions on flexible plastic packaging
- Low-contrast dot-matrix printing and ink-stamp batch/manufacturing dates
- Variable ambient lighting, shadows, and camera perspective skew

To ensure scientific integrity and eliminate synthetic bias, every ground truth entry in this dataset follows strict provenance standards and double-blind human verification.

---

## 2. Representative Packaging Categories (Indian Retail)

The dataset encompasses 10 distinct packaging categories spanning the Indian food supply:

1. **Savory Snacks & Extruded Namkeen**:
   - Formats: Metallized BOPP/polyester foil pouches, pillow packs, gusseted pouches.
   - Typical Challenges: High specular glare, puffed pouch curvature, wrinkled seam edges, multi-colored backgrounds.
2. **Biscuits & Cookies**:
   - Formats: Flow-wrapped flexible polypropylene sleeves, cylindrical roll packs.
   - Typical Challenges: Surface wrinkling along seals, curved typography, compact tables.
3. **Dairy & Cultured Products**:
   - Formats: Polypropylene curd/yogurt cups, aseptic Tetra Pak cartons, foil-lined butter wrappers.
   - Typical Challenges: Tapered conical distortion, condensation droplets, small font sizes.
4. **Ready-to-Eat (RTE) & Ready-to-Cook (RTC) Meals**:
   - Formats: Retort pouches, stand-up zipper pouches, printed SBS paperboard cartons.
   - Typical Challenges: Foil glare, dual-column (as-packaged vs as-prepared) nutritional declarations.
5. **Beverages & Juices**:
   - Formats: Cylindrical PET bottles, glass bottles, slim aluminum cans.
   - Typical Challenges: Severe cylindrical perspective warping, liquid refraction, transparent label overlays.
6. **Breakfast Cereals & Grain Pouches**:
   - Formats: Matte cardboard outer cartons, large ziplock laminated pouches.
   - Typical Challenges: Dense multi-column tables, bilingual declarations (English + Hindi), fine print.
7. **Chocolates & Confectionery**:
   - Formats: Aluminum foil inner wraps, micro-format pillow wrappers, heat-sealed flow wraps.
   - Typical Challenges: Micro-typography (<6 pt font), crushed foil creases, metallic interference.
8. **Condiments, Sauces & Pickles**:
   - Formats: Glass jars with cylindrical wrap-around labels, squeeze PET bottles, spout pouches.
   - Typical Challenges: 360-degree cylindrical curvature, oily residue, narrow text columns.
9. **Flours, Pulses & Staple Grains**:
   - Formats: Heavy LDPE poly-sacks (1 kg - 5 kg), woven HDPE bags with printed labels.
   - Typical Challenges: Bag slumping, dot-matrix overprinting, creased panels.
10. **Nutritional Supplements & Health Foods**:
    - Formats: High-density polyethylene (HDPE) tubs, blister cartons, stand-up metallic pouches.
    - Typical Challenges: High-density micro-tables, extended micronutrient listings, complex RDA percentages.

---

## 3. Capture Conditions Protocol

All photographs collected for evaluation must record physical capture parameters:

### A. Lighting Environments
- **Condition L1 (Natural Daylight)**: Diffuse indirect sunlight (500–1000 lux), color temperature ~5500 K.
- **Condition L2 (Domestic Warm/Cool Artificial)**: Ceiling or desk LED/fluorescent lighting (150–300 lux), color temperature 3000 K–4000 K.
- **Condition L3 (Challenging Glare)**: Direct directional incandescent or point-source LED producing visible specular reflection hotspots over the label area.

### B. Camera Angle and Perspective
- **Angle A1 (Normal / Orthogonal)**: Sensor parallel to label plane (0°–10° tilt).
- **Angle A2 (Hand-held Perspective Skew)**: Realistic consumer angle (15°–35° tilt along pitch or yaw axis).

### C. Framing and Distance
- **Framing F1 (Optimal Crop)**: Nutrition table occupies >70% of frame area.
- **Framing F2 (Consumer Framing)**: Nutrition table occupies 30%–50% of frame area within broader package context.

### D. Packaging State
- **State S1 (Pristine / Flat)**: Brand-new package flattened or supported against a planar surface.
- **State S2 (Curved / Cylindrical)**: Natural cylindrical curvature without flattening (e.g. bottles, cans).
- **State S3 (Deformed / Wrinkled)**: Flexible packaging exhibiting consumer creases, folds, or pillow inflation.

---

## 4. Ground Truth Annotation Schema

Each ground-truth sample is represented by a structured JSON object adhering to `annotation_template.json`:

```json
{
  "sample_id": "RFL-001",
  "product_name": "String (Verbatim product title as printed)",
  "brand": "String (Brand name)",
  "fssai_license": "String (14-digit FSSAI number if visible, or null)",
  "barcode": "String (EAN-13 / UPC barcode if visible, or null)",
  "category": "One of the 10 defined retail categories",
  "packaging_format": "pouch | bottle | wrapper | carton | jar | cup | can | sack",
  "image_filename": "Filename within images/ directory",
  "image_sha256": "64-character SHA-256 hex digest of pristine image file",
  "capture_metadata": {
    "lighting_condition": "L1 | L2 | L3",
    "camera_angle": "A1 | A2",
    "framing": "F1 | F2",
    "packaging_state": "S1 | S2 | S3",
    "device_description": "String (e.g., Samsung Galaxy S21, iPhone 13, etc.)"
  },
  "ground_truth_nutrition": {
    "declaration_basis": "per_100g | per_100ml | per_serving | dual_column",
    "serving_size": 30.0,
    "serving_unit": "g | ml | piece | portion",
    "food_form": "solid | liquid",
    "nutrients": {
      "energy_kcal": 140.0,
      "protein_g": 2.1,
      "carbohydrates_g": 21.0,
      "total_sugar_g": 9.0,
      "added_sugar_g": 7.5,
      "dietary_fiber_g": 0.8,
      "total_fat_g": 6.0,
      "saturated_fat_g": 2.8,
      "trans_fat_g": 0.05,
      "cholesterol_mg": null,
      "sodium_mg": 180.0
    },
    "dual_column_values": {
      "per_100": { "energy_kcal": 467.0, "...": "..." },
      "per_serving": { "energy_kcal": 140.0, "...": "..." }
    }
  },
  "ground_truth_ingredients_text": "Verbatim ingredients declaration string",
  "verification": {
    "annotator_1": "Identifier",
    "annotator_2": "Identifier",
    "verified_date": "YYYY-MM-DD",
    "status": "DOUBLE_VERIFIED"
  }
}
```

---

## 5. Dual Independent Human Verification Protocol

To prevent subjective annotation errors:
1. **Primary Transcription (Annotator 1)**: Transcribes verbatim text, nutrition table figures, and ingredients from the physical package under 100% zoom.
2. **Independent Cross-Audit (Annotator 2)**: Independently inspects the high-resolution photograph and validates all values without viewing Annotator 1's preliminary outputs.
3. **Reconciliation**: Any discrepancy in numeric values, units, or character sequences must be flagged for physical sample review.
4. **Plausibility Gate**: The structured ground truth must pass automated biological plausibility constraints (macronutrient mass bounds, Atwater calorie bounds, sugar/fat sub-component invariants) via `validate_dataset.py`.
