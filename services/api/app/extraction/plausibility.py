"""
Deterministic physical plausibility and consistency checks for nutrition values.

Identifies:
1. Physical impossibilities (e.g. macronutrients > total weight, sub-nutrients > total).
2. Transposed or misread decimal points (e.g. 25g instead of 2.5g).
3. Atwater calorie discrepancies.
4. Contradictions between salt and sodium.

Does NOT modify or invent values. Emits clear advisory warnings and flags.
"""

from typing import Final

from app.extraction.models import ExtractionWarning

ATWATER_PROTEIN_KCAL_PER_G: Final[float] = 4.0
ATWATER_CARB_KCAL_PER_G: Final[float] = 4.0
ATWATER_FAT_KCAL_PER_G: Final[float] = 9.0


class PlausibilityAuditResult:
    """Outcome of physical consistency checks on extracted nutrient values."""

    def __init__(self) -> None:
        self.warnings: list[ExtractionWarning] = []
        self.field_plausibility: dict[
            str, str
        ] = {}  # field_name -> "plausible" | "suspicious" | "contradictory"
        self.field_warnings: dict[str, str] = {}


def audit_table_plausibility(
    nutrient_values: dict[str, float | None],
    serving_size: float | None = None,
    basis: str = "per_100g",
) -> PlausibilityAuditResult:
    """
    Evaluates physical consistency of nutrition values.
    Returns per-field plausibility states and global warnings.
    """
    result = PlausibilityAuditResult()

    # Initialize all present fields as plausible
    for k in nutrient_values:
        result.field_plausibility[k] = "plausible"

    # Helper to get numeric float
    def get_val(key: str) -> float | None:
        v = nutrient_values.get(key)
        return float(v) if v is not None else None

    energy = get_val("energy_kcal")
    protein = get_val("protein_g")
    carbs = get_val("carbohydrates_g")
    total_sugar = get_val("total_sugar_g")
    added_sugar = get_val("added_sugar_g")
    total_fat = get_val("total_fat_g")
    sat_fat = get_val("saturated_fat_g")
    trans_fat = get_val("trans_fat_g")
    sodium = get_val("sodium_mg")

    # 1. Negative numbers check
    for k, v in nutrient_values.items():
        if v is not None and v < 0:
            result.field_plausibility[k] = "contradictory"
            msg = f"Nutrient {k} has a negative value ({v}), which is physically impossible."
            result.field_warnings[k] = msg
            result.warnings.append(
                ExtractionWarning(code="PLAUSIBILITY_NEGATIVE_VALUE", message=msg)
            )

    # 2. Sub-nutrient checks: Added Sugars vs Total Sugars
    # Scientific basis: Added sugars are chemically a subset of total mono- and disaccharides.
    # Applicable units: grams (g).
    # Tolerance: 0.2g allowance for independent regulatory rounding (FSSAI Schedule II).
    # Known exceptions: Slight rounding inversion (true values 1.04g vs 1.06g rounded).
    # Disposition: Contradictory if excess > 0.2g; suspicious advisory if 0.0 < excess <= 0.2g.
    if added_sugar is not None and total_sugar is not None:
        diff_sugar = added_sugar - total_sugar
        if diff_sugar > 0.2:
            result.field_plausibility["added_sugar_g"] = "contradictory"
            result.field_plausibility["total_sugar_g"] = "contradictory"
            msg = (
                f"Added sugars ({added_sugar}g) cannot exceed total sugars ({total_sugar}g). "
                "Values may be transposed or a decimal point was misread."
            )
            result.field_warnings["added_sugar_g"] = msg
            result.warnings.append(
                ExtractionWarning(code="PLAUSIBILITY_ADDED_SUGAR_EXCEEDS_TOTAL", message=msg)
            )
        elif diff_sugar > 0.05:
            result.field_plausibility["added_sugar_g"] = "suspicious"
            msg = (
                f"Added sugars ({added_sugar}g) slightly exceeds total sugars ({total_sugar}g), "
                "likely due to independent rounding. Please verify against physical label."
            )
            result.field_warnings["added_sugar_g"] = msg
            result.warnings.append(
                ExtractionWarning(code="PLAUSIBILITY_ADDED_SUGAR_ROUNDING_DISCREPANCY", message=msg)
            )

    # 3. Sub-nutrient checks: Saturated Fat and Trans Fat vs Total Fat
    # Scientific basis: Saturated and trans fatty acids are chemical subclasses of total lipids.
    # Applicable units: grams (g).
    # Tolerance: 0.2g individual, 0.5g combined for independent analytical rounding.
    # Known exceptions: Regulatory rounding of low-fat formulations.
    # Disposition: Contradictory if individual excess > 0.2g; suspicious if combined excess > 0.5g.
    if total_fat is not None:
        if sat_fat is not None and (sat_fat - total_fat) > 0.2:
            result.field_plausibility["saturated_fat_g"] = "contradictory"
            msg = (
                f"Saturated fat ({sat_fat}g) cannot exceed total fat ({total_fat}g). "
                "Please verify values against the physical label."
            )
            result.field_warnings["saturated_fat_g"] = msg
            result.warnings.append(
                ExtractionWarning(code="PLAUSIBILITY_SAT_FAT_EXCEEDS_TOTAL", message=msg)
            )

        if trans_fat is not None and (trans_fat - total_fat) > 0.2:
            result.field_plausibility["trans_fat_g"] = "contradictory"
            msg = (
                f"Trans fat ({trans_fat}g) cannot exceed total fat ({total_fat}g). "
                "Please verify values against the physical label."
            )
            result.field_warnings["trans_fat_g"] = msg
            result.warnings.append(
                ExtractionWarning(code="PLAUSIBILITY_TRANS_FAT_EXCEEDS_TOTAL", message=msg)
            )

        if sat_fat is not None and trans_fat is not None:
            if (sat_fat + trans_fat) > (total_fat + 0.5):
                msg = (
                    f"Sum of saturated fat ({sat_fat}g) and trans fat ({trans_fat}g) exceeds "
                    f"total fat ({total_fat}g). Please verify against physical label."
                )
                result.field_plausibility["saturated_fat_g"] = "suspicious"
                result.field_plausibility["trans_fat_g"] = "suspicious"
                result.warnings.append(
                    ExtractionWarning(code="PLAUSIBILITY_FAT_COMPONENTS_EXCEED_TOTAL", message=msg)
                )

    # 4. Total Mass Bound Check
    # Scientific basis: Conservation of Mass (Protein + Carbs + Fat + Fiber + Ash + Water = Total).
    # Applicable units & serving basis:
    # - Solid foods per 100g (basis == 'per_100g'): Limit is 105.0g (5.0g tolerance).
    # - Liquid foods per 100ml (basis == 'per_100ml'): Density rho can exceed 1.0 g/ml.
    #   For heavy liquids (honey rho~1.42, syrups rho~1.35), 100ml weighs up to ~145g.
    #   Limit is 150.0g.
    # Known exceptions: High-density syrups/honey per 100ml, polyols, component rounding.
    # Disposition: Contradictory if individual macro > mass limit; suspicious if sum > mass limit.
    if basis in ("per_100g", "per_100ml"):
        macro_sum = 0.0
        counted_macros = []
        if protein is not None:
            macro_sum += protein
            counted_macros.append(f"protein={protein}g")
        if carbs is not None:
            macro_sum += carbs
            counted_macros.append(f"carbs={carbs}g")
        if total_fat is not None:
            macro_sum += total_fat
            counted_macros.append(f"fat={total_fat}g")

        mass_limit = 105.0 if basis == "per_100g" else 150.0
        if macro_sum > mass_limit:
            basis_label = "100g" if basis == "per_100g" else "100ml"
            msg = (
                f"Sum of macronutrients ({macro_sum:.1f}g: {', '.join(counted_macros)}) exceeds "
                f"maximum plausible mass for {basis_label}. A decimal separator may be missing."
            )
            if protein is not None and protein > 50:
                result.field_plausibility["protein_g"] = "suspicious"
            if carbs is not None and carbs > mass_limit:
                result.field_plausibility["carbohydrates_g"] = "contradictory"
            if total_fat is not None and total_fat > 100:
                result.field_plausibility["total_fat_g"] = "contradictory"
            result.warnings.append(
                ExtractionWarning(code="PLAUSIBILITY_MACRO_SUM_EXCEEDS_100G", message=msg)
            )

    # If basis is per_serving and serving size is known:
    if basis == "per_serving" and serving_size is not None and serving_size > 0:
        for k in (
            "protein_g",
            "carbohydrates_g",
            "total_sugar_g",
            "added_sugar_g",
            "total_fat_g",
            "saturated_fat_g",
        ):
            v = get_val(k)
            if v is not None and v > (serving_size + 0.5):
                msg = (
                    f"Nutrient {k} ({v}g) exceeds the stated serving size ({serving_size}g). "
                    "This value likely belongs to the Per 100g column."
                )
                result.field_plausibility[k] = "contradictory"
                result.field_warnings[k] = msg
                result.warnings.append(
                    ExtractionWarning(code="PLAUSIBILITY_EXCEEDS_SERVING_SIZE", message=msg)
                )

    # 5. Atwater Calorie Consistency Check
    # Scientific basis: General Atwater energy factors:
    # 4 kcal/g protein, 4 kcal/g carbs, 9 kcal/g fat.
    # Applicable units: kcal.
    # Tolerance: Max(35 kcal, 0.35 * atwater_expected) to accommodate analytical variance.
    # Known scientific exceptions:
    # - Dietary fiber: 2 kcal/g (Codex/FSSAI) or 0 kcal/g (insoluble).
    # - Polyols / sugar alcohols: 0.2 to 2.4 kcal/g (e.g. erythritol, maltitol).
    # - Organic acids: 3 kcal/g (e.g. citric acid in fruit drinks).
    # - Specific Atwater factors differ by food matrix.
    # Disposition: Suspicious advisory warning; prompts user to check for polyols/fiber.
    if energy is not None and protein is not None and carbs is not None and total_fat is not None:
        atwater_expected = (
            protein * ATWATER_PROTEIN_KCAL_PER_G
            + carbs * ATWATER_CARB_KCAL_PER_G
            + total_fat * ATWATER_FAT_KCAL_PER_G
        )
        # Check relative and absolute difference
        diff = abs(energy - atwater_expected)
        # If difference exceeds 35% and at least 35 kcal
        if atwater_expected > 20 and diff > max(35.0, 0.35 * atwater_expected):
            msg = (
                f"Declared energy ({energy} kcal) differs noticeably from expected macronutrient "
                f"calories ({atwater_expected:.0f} kcal: 4x{protein} + 4x{carbs} + 9x{total_fat}). "
                "Known exceptions include polyols, dietary fiber (2 kcal/g), and organic acids. "
                "Please verify energy and macronutrient digits."
            )
            result.field_plausibility["energy_kcal"] = "suspicious"
            result.warnings.append(
                ExtractionWarning(code="PLAUSIBILITY_ATWATER_CALORIE_DISCREPANCY", message=msg)
            )

    # 6. Sodium / Salt scale sanity
    # Scientific basis: Stoichiometric conversion: 1g NaCl = 393.4 mg Na (Na=22.99, Cl=35.45).
    # Tolerance: Values above 10,000 mg (10g Na ~ 25g Salt) per serving are physically extreme.
    # Known exceptions: Brines, pure seasonings/sauces before dilution.
    # Disposition: Suspicious warning flagging probable omitted decimal point (e.g. 15000 vs 150.0).
    if sodium is not None and sodium > 10_000.0:
        msg = f"Sodium ({sodium}mg) is unusually high. A decimal point may have been omitted."
        result.field_plausibility["sodium_mg"] = "suspicious"
        result.warnings.append(ExtractionWarning(code="PLAUSIBILITY_EXTREME_SODIUM", message=msg))

    return result
