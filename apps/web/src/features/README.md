# healthyIndia Features Directory

This directory will organize feature modules in subsequent development phases.

## Planned Feature Modules (Phase 2 & 3):
- `scan/`: Label image capture, cropping, and adapter-based OCR extraction review.
- `manual-entry/`: Unit-aware manual nutrient and ingredient input form.
- `results/`: Nutrition calculation summaries, ingredient explanations, and transparent source citations.

## Architectural Constraints:
- Business logic calculations are performed by the backend Python service.
- Features do not invent nutritional data or claim unsupported health effects.
- Missing values must never be silently converted to zero.
