"""
Extraction and OCR adapter interfaces.

Architectural Rule:
- OCR must be implemented as a replaceable adapter in a later phase.
- All extracted data is treated as untrusted input.
- Extracted fields must preserve raw text, normalized value, unit, and confidence.
- No OCR or generative AI dependencies are permitted in Phase 1.
"""
