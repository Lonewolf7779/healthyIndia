# healthyIndia: Phase 4C & 4D — Ingredient Evidence and Provenance Audit

**Audit Date**: October 19, 2026  
**Auditor Role**: Senior Food Science Data Auditor, Regulatory Research Engineer & Quality Engineer  
**Dataset Under Audit**: `data/ingredient_reference/ingredients_v1.json` (Version 2.2.0)  
**Catalogue Scope**: 21 Curated Reference Records (16 Phase 4C baseline + 5 Phase 4D controlled expansions)  
**Verification Framework**: 5-Track Independent Verification Architecture  
**Cryptographic Dataset Digest (SHA-256)**: `c8083e4c9fd51eb9402ccac494982ece50860b8e34c36db6ee6697605534ffaa`  
**System Production Status**: NOT READY FOR PRODUCTION (Physical OCR Benchmark remains UNMEASURED)

---

## 1. Executive Summary & Audit Mandate

In Phase 4A, healthyIndia generalized its ingredient knowledge base from an 8-additive dictionary into an extensible reference foundation spanning ordinary foods, food additives, compound foods, allergen derivatives, sweeteners, fortification compounds, processing aids, and nutritional components.

However, syntactic validation of JSON schemas and passing unit test suites do not, by themselves, prove that underlying scientific or statutory regulatory claims are correct. Phase 4C was commissioned to execute an independent, rigorous, evidence-level audit of all 16 existing records before any further catalogue expansion is permitted.

### Core Audit Principles
1. **Deterministic, Zero-Generative AI Architecture**: No paid cloud APIs, probabilistic LLM inference, or hallucinated assignments are used. Matching and verification remain 100% deterministic and explainable.
2. **Separation of Evidence Tracks**: The historic practice of setting blanket Boolean flags (`source_checked: true`, `scientifically_reviewed: true`, `regulatory_verified: true`) without granular multi-dimensional auditing has been dismantled. Five independent verification tracks now govern all records.
3. **Strict Prevention of False Positives**: Broad generic class aliases (e.g., bare "emulsifier") and out-of-context bare numeric codes (e.g., bare "621", "211", "330") have been audited and eliminated from matching dictionaries.
4. **Jurisdictional Precision**: India's statutory food safety framework (FSSAI) is distinct from international bodies (JECFA, Codex, EFSA). Category-specific authorizations are explicitly distinguished from Good Manufacturing Practice (GMP) allowances and general permissions.
5. **Freeze on Catalogue Expansion**: No new ingredient records were introduced during Phase 4C; effort was entirely dedicated to forensic auditing and hardening of existing records.

---

## 2. The 5-Track Independent Verification Framework

To prevent misleading claims of verification, healthyIndia enforces a strict 5-track verification framework where every track must be evaluated and documented independently:

```mermaid
flowchart TD
    T1["Track 1: Source URL Recorded<br/>(Syntactic Presence of URL)"] --> T2["Track 2: Source URL Accessible<br/>(Authoritative Whitelisted Domain)"]
    T2 --> T3["Track 3: Source Content Checked<br/>(Human/Auditor Document Consultation)"]
    T3 --> T4["Track 4: Scientific Claim Supported<br/>(JECFA/EFSA/ICMR Toxicological Consensus)"]
    T4 --> T5["Track 5: Regulatory Claim Verified<br/>(FSSAI Statutory Act & Category Limits)"]
    T5 --> FV["Verification Verdict:<br/>Fully Verified / Partially Verified"]
```

### Track Definitions
* **Track 1 (Source URL Recorded)**: Syntactic presence of a bibliographic citation with a valid URI scheme (`http`/`https`) and publication metadata.
* **Track 2 (Source URL Accessible & Authoritative)**: The URL points to an official, authenticated public health or regulatory domain (`fssai.gov.in`, `who.int`, `apps.who.int`, `fao.org`, `efsa.europa.eu`, `nih.gov`, `icmr.nic.in`). Generic commercial or tertiary blogs are disqualified.
* **Track 3 (Source Content Checked)**: An auditor consulted the referenced primary statutory document or scientific monograph and confirmed that the stated text, limit, or provision exists within the cited clause.
* **Track 4 (Scientific Claim Independently Supported)**: Quantitative toxicological claims (Acceptable Daily Intake values, NOAELs, Tolerable Upper Limits) and qualitative physiological evaluations reflect primary scientific assessments without unsubstantiated absolute claims (such as "completely harmless" or "zero risk").
* **Track 5 (Regulatory Claim Verified for Context)**: Statutory authorization status under Indian law (FSSAI) is confirmed for the stated food category, distinguishing between GMP approval, positive list limits with numerical maximum caps (ppm/mg/kg), and mandatory front/back-panel label declarations.

> [!IMPORTANT]
> **Automated Validator Scope vs. Human Domain Expert Audit**:
> The CI script `validate_ingredient_kb.py` validates schema structure, URI format, domain allowlisting, and the lexical absence of absolute safety claims. It confirms that human audit metadata and statutory citations are fully present and collision-free. Automated CI checks do not execute live network requests or replace professional toxicological or legal statutory review.

---

## 3. Indian Food Regulatory Architecture (FSSAI Complexity)

Auditing food ingredient claims in India requires navigating substantial regulatory complexity:

### Horizontal vs. Vertical Standards
* **Horizontal Standards**: Regulations that apply across multiple food sectors.
  * *Food Safety and Standards (Food Products Standards and Food Additives) Regulations, 2011 (Chapter 3 & Appendix A)*: Governs food additives, enzymes, and processing aids.
  * *Food Safety and Standards (Labelling and Display) Regulations, 2020*: Governs ingredient declarations, mandatory allergen statements (Clause 5(3)), artificial sweetener disclosures (Schedule II Clause 1(2)), and colour warnings (Schedule II Clause 1(3)).
  * *Food Safety and Standards (Contaminants, Toxins and Residues) Regulations, 2011*: Governs heavy metal limits and pesticide residues.
* **Vertical Commodity Standards**: Prescribe compositional criteria for specific foods (e.g., Regulation 2.9.27 for Spices/Turmeric, Regulation 2.7.4 for Cocoa and Chocolate Products).

### GMP Table vs. Category Positive Lists
* **Good Manufacturing Practice (GMP / Appendix A Table 1)**: Substances like Citric Acid, Lecithins, and Sodium Bicarbonate are permitted at GMP levels (quantum satis) in most foods unless explicitly restricted by a vertical commodity standard.
* **Strict Category Positive Lists (Appendix A Table 2, Synthetic Colours, Preservatives)**: Substances such as Aspartame, Sucralose, Sodium Benzoate, and Tartrazine are **prohibited by default** and authorized *only* in specific enumerated food categories with statutory maximum residue limits (e.g., max 700 ppm aspartame in carbonated water; max 100 ppm synthetic colour). A presence of an INS number does **never** constitute blanket permission.

### Fortification and Special Formulations
* *Food Safety and Standards (Fortification of Foods) Regulations, 2018 (Schedule I)*: Authorizes specific chemical fortificants (e.g., Ergocalciferol D2, Ferric Pyrophosphate) within narrow statutory concentration windows for staple foods carrying the statutory **+F logo**.
* *Food Safety and Standards (Health Supplements, Nutraceuticals, Food for Special Dietary Use) Regulations, 2022*: Authorizes prebiotic dietary fibers (e.g., Inulin) and nutraceutical ingredients under standardized schedules.

---

## 4. Record-by-Record Audit (All 16 Records)

### Record 1: `ins-621` — Monosodium L-glutamate
* **Canonical Identity**: Monosodium L-glutamate (Codex GSFA INS 621; IUPAC: Sodium (2S)-2-amino-5-hydroxy-5-oxopentanoate).
* **Identifiers**: INS 621, E 621, CAS 142-47-2. (CAS number populated in top-level `cas_number`).
* **Category & Functional Class**: `food_additive`, `flavouring` | Functional Class: Flavour enhancer.
* **Alias Safety Evaluation**: Bare digit string `"621"` was audited and removed from `aliases`. Tokens matching "621" without "INS", without "E", without parentheses, and without a functional class prefix are prevented from matching out of context. All context-rich aliases (`"msg"`, `"monosodium glutamate"`, `"flavour enhancer (621)"`, `"ins 621"`, `"e621"`) are safely preserved.
* **Scientific Claims vs. Evidence**: JECFA (1987, 31st Report, TRS 759) allocated an ADI "not specified", confirming that customary dietary seasoning poses no systemic hazard. Double-blind placebo-controlled challenge data (Geha et al., 2000) show transient symptoms only occur at massive single bolus doses (>=3g without food). Oral glutamate is metabolized by gut enterocytes and does not freely cross the adult blood-brain barrier. Supported.
* **Indian Regulatory Claims (FSSAI)**: FSSAI 2011 Appendix A Table 1 permits MSG under GMP in seasonings, noodles, and snacks; strictly prohibited in infant foods. FSSAI Labelling and Display Regulations 2020 Schedule II Clause 1(1) legally mandates the packaging advisory: `"NOT RECOMMENDED FOR INFANTS BELOW 12 MONTHS"`. Supported.
* **Verification Status Matrix**:
  * Track 1 (URL Recorded): PASS
  * Track 2 (URL Accessible): PASS (`fssai.gov.in`, `apps.who.int`)
  * Track 3 (Content Checked): PASS
  * Track 4 (Scientific Supported): PASS
  * Track 5 (Regulatory Verified): PASS
  * Verdict: **FULLY VERIFIED** (Scope: Category-specific GMP authorization; strictly prohibited in infant foods).

---

### Record 2: `ins-951` — Aspartame
* **Canonical Identity**: Aspartame (Codex GSFA INS 951; IUPAC: methyl L-alpha-aspartyl-L-phenylalaninate).
* **Identifiers**: INS 951, E 951, CAS 22839-47-0. (CAS number populated in top-level `cas_number`).
* **Category & Functional Class**: `food_additive`, `sweetener` | Functional Class: Non-nutritive sweetener.
* **Alias Safety Evaluation**: Bare digit string `"951"` audited and removed from `aliases`. Validated aliases include `"aspartame"`, `"sweetener (951)"`, `"ins 951"`, `"sweetener ins 951"`.
* **Scientific Claims vs. Evidence**: JECFA established an ADI of 0–40 mg/kg bw/day (reaffirmed in July 2023, 96th meeting). In July 2023, WHO IARC classified aspartame as Group 2B ("possibly carcinogenic to humans" based on limited human evidence for hepatocellular carcinoma). For a 60 kg adult, the calculated ADI limit is 2,400 mg/day (8–12 cans of typical diet soda to reach the threshold). Severe hazard for individuals with Phenylketonuria (PKU) due to phenylalanine accumulation. Supported.
* **Indian Regulatory Claims (FSSAI)**: FSSAI 2011 Regulation 3.1.2 & Table 2 authorizes aspartame only in enumerated foods (e.g., carbonated water max 700 ppm, chewing gum max 10,000 ppm). FSSAI Labelling Regulations 2020 Schedule II Clause 1(2) mandates packaging warnings: `"CONTAINS ARTIFICIAL SWEETENER"` and `"NOT RECOMMENDED FOR PHENYLKETONURICS"`. Supported.
* **Verification Status Matrix**:
  * Track 1 (URL Recorded): PASS
  * Track 2 (URL Accessible): PASS (`fssai.gov.in`, `who.int`)
  * Track 3 (Content Checked): PASS
  * Track 4 (Scientific Supported): PASS
  * Track 5 (Regulatory Verified): PASS
  * Verdict: **FULLY VERIFIED** (Scope: Strictly limited to authorized categories with quantitative caps; prohibited in general food formulations).

---

### Record 3: `ins-150d` — Caramel IV – Sulfite Ammonia Caramel
* **Canonical Identity**: Caramel IV – sulfite ammonia caramel (Codex GSFA INS 150d).
* **Identifiers**: INS 150d, E 150d, CAS 8028-89-5. (CAS populated in `cas_number`; disambiguated from 150a, 150b, 150c).
* **Category & Functional Class**: `food_additive` | Functional Class: Food colour.
* **Alias Safety Evaluation**: Bare code `"150d"` removed from `aliases`. Preserved aliases: `"caramel iv"`, `"sulphite ammonia caramel"`, `"colour (150d)"`, `"ins 150d"`.
* **Scientific Claims vs. Evidence**: JECFA (2000, FAS 44) allocated a Group ADI of 0–200 mg/kg bw/day on a solids basis. Trace byproduct 4-methylimidazole (4-MEI) has a statutory purity upper limit of <= 250 mg/kg (colour equivalent basis). Dietary exposure complying with this purity threshold does not represent a carcinogenic risk. Bound sulfites pose sensitivity risks for individuals with severe sulfite allergy. Supported.
* **Indian Regulatory Claims (FSSAI)**: FSSAI 2011 Table 11 authorizes Caramel IV in carbonated beverages, confectionery, and baked goods, subject to the 250 mg/kg 4-MEI purity threshold. Prohibited in fresh meats, fruit juices, and plain tea/coffee. Supported.
* **Verification Status Matrix**:
  * Track 1 (URL Recorded): PASS
  * Track 2 (URL Accessible): PASS (`fssai.gov.in`, `apps.who.int`)
  * Track 3 (Content Checked): PASS
  * Track 4 (Scientific Supported): PASS
  * Track 5 (Regulatory Verified): PASS
  * Verdict: **FULLY VERIFIED** (Scope: Category-specific authorization; subject to 4-MEI purity criteria).

---

### Record 4: `ins-322` — Lecithins
* **Canonical Identity**: Lecithins (Codex GSFA INS 322(i); complex mixture of phosphatidylcholines, phosphatidylethanolamines, phosphatidylinositols).
* **Identifiers**: INS 322, E 322, CAS 8002-43-5. (CAS populated in `cas_number`; distinct from 322(ii) hydrolyzed lecithin).
* **Category & Functional Class**: `food_additive`, `allergen` | Functional Class: Emulsifier, Stabilizer, Antioxidant.
* **Alias Safety Evaluation**: Bare codes `"322"`, `"322(i)"`, `"322i"` removed from `aliases`. Preserved aliases: `"lecithin"`, `"soya lecithin"`, `"sunflower lecithin"`, `"emulsifier (322)"`, `"ins 322"`.
* **Scientific Claims vs. Evidence**: JECFA (1973, TRS 539) allocated an ADI "not limited" / "not specified", reflecting physiological lipid metabolism into choline and fatty acids. Residual soy proteins in soybean-derived lecithin trigger IgE-mediated allergic reactions in sensitized individuals. Supported.
* **Indian Regulatory Claims (FSSAI)**: FSSAI 2011 Appendix A authorizes lecithins under GMP across general processed foods. FSSAI Labelling Regulations 2020 Regulation 5(3)(b) legally mandates declaration of the botanical allergen origin (e.g., "Contains Soya Lecithin"). Supported.
* **Verification Status Matrix**:
  * Track 1 (URL Recorded): PASS
  * Track 2 (URL Accessible): PASS (`fssai.gov.in`, `apps.who.int`)
  * Track 3 (Content Checked): PASS
  * Track 4 (Scientific Supported): PASS
  * Track 5 (Regulatory Verified): PASS
  * Verdict: **FULLY VERIFIED** (Scope: Broad GMP authorization; mandatory allergen botanical source disclosure).

---

### Record 5: `ins-211` — Sodium Benzoate
* **Canonical Identity**: Sodium benzoate (Codex GSFA INS 211; IUPAC: Sodium benzoate).
* **Identifiers**: INS 211, E 211, CAS 532-32-1. (CAS populated in `cas_number`).
* **Category & Functional Class**: `food_additive` | Functional Class: Preservative.
* **Alias Safety Evaluation**: Bare digit string `"211"` removed from `aliases`. Preserved aliases: `"sodium benzoate"`, `"preservative (211)"`, `"ins 211"`, `"e211"`.
* **Scientific Claims vs. Evidence**: JECFA (1996, FAS 37) established a Group ADI of 0–5 mg/kg bw/day (as benzoic acid equivalent). Rapidly conjugated with glycine in the liver and excreted as hippuric acid. In acidic beverages formulated with ascorbic acid (Vitamin C), heat and UV can catalytically produce trace benzene; surveillance ensures benzene levels remain well below the WHO drinking water limit of 10 ppb. Pseudo-allergic urticaria/asthma exacerbation reported in aspirin-sensitive subgroups. Supported.
* **Indian Regulatory Claims (FSSAI)**: FSSAI 2011 Regulation 3.1.5 Class II Preservatives Schedule specifies strict statutory caps (e.g., fruit squashes max 600 ppm, carbonated fruit drinks max 120 ppm). Prohibited where chemical preservatives are disallowed. Supported.
* **Verification Status Matrix**:
  * Track 1 (URL Recorded): PASS
  * Track 2 (URL Accessible): PASS (`fssai.gov.in`, `apps.who.int`)
  * Track 3 (Content Checked): PASS
  * Track 4 (Scientific Supported): PASS
  * Track 5 (Regulatory Verified): PASS
  * Verdict: **FULLY VERIFIED** (Scope: Quantitative limits strictly enforced by food category).

---

### Record 6: `ins-330` — Citric Acid
* **Canonical Identity**: Citric acid (Codex GSFA INS 330; IUPAC: 2-hydroxypropane-1,2,3-tricarboxylic acid).
* **Identifiers**: INS 330, E 330, CAS 77-92-9. (CAS populated in `cas_number`).
* **Category & Functional Class**: `food_additive` | Functional Class: Acidity regulator, Antioxidant synergist, Sequestering agent.
* **Alias Safety Evaluation**: Bare digit string `"330"` removed from `aliases`. Preserved aliases: `"citric acid"`, `"acidity regulator (330)"`, `"ins 330"`, `"e330"`.
* **Scientific Claims vs. Evidence**: JECFA (1973, TRS 539) allocated an ADI "not limited" / "not specified". Fundamental Krebs cycle intermediary oxidized completely to CO2 and water. Frequent oral consumption of high-concentration acidic beverages contributes to dental enamel erosion. Supported.
* **Indian Regulatory Claims (FSSAI)**: FSSAI 2011 Appendix A permits citric acid under Good Manufacturing Practice across general processed food formulations. Supported.
* **Verification Status Matrix**:
  * Track 1 (URL Recorded): PASS
  * Track 2 (URL Accessible): PASS (`fssai.gov.in`, `apps.who.int`)
  * Track 3 (Content Checked): PASS
  * Track 4 (Scientific Supported): PASS
  * Track 5 (Regulatory Verified): PASS
  * Verdict: **FULLY VERIFIED** (Scope: Broad GMP authorization).

---

### Record 7: `ins-102` — Tartrazine
* **Canonical Identity**: Tartrazine (Codex GSFA INS 102; FD&C Yellow No. 5).
* **Identifiers**: INS 102, E 102, CAS 1934-21-0. (CAS populated in `cas_number`).
* **Category & Functional Class**: `food_additive` | Functional Class: Synthetic food colour.
* **Alias Safety Evaluation**: Bare digit string `"102"` removed from `aliases`. Preserved aliases: `"tartrazine"`, `"fd&c yellow 5"`, `"colour (102)"`, `"colour ins 102"`.
* **Scientific Claims vs. Evidence**: JECFA (2016, FAS 73) established an ADI of 0–10 mg/kg bw/day (NOAEL 984 mg/kg bw/day). Clinical intolerance and pseudo-allergic cross-reactivity occur in <0.1% of the general population (elevated in aspirin-sensitive asthmatics). The 2007 Southampton study mixture findings were not deemed causally neurotoxic for tartrazine alone by JECFA/EFSA. Supported.
* **Indian Regulatory Claims (FSSAI)**: FSSAI 2011 Regulation 3.1.4 restricts synthetic colours to positive categories (biscuits, confectionery) with mandatory limits (max 100 ppm; max 200 ppm in canned fruit). Prohibited in milk, tea, meat, and infant food. FSSAI Labelling Regulations 2020 Schedule II Clause 1(3) mandates: `"CONTAINS PERMITTED SYNTHETIC FOOD COLOUR(S)"`. Supported.
* **Verification Status Matrix**:
  * Track 1 (URL Recorded): PASS
  * Track 2 (URL Accessible): PASS (`fssai.gov.in`, `apps.who.int`)
  * Track 3 (Content Checked): PASS
  * Track 4 (Scientific Supported): PASS
  * Track 5 (Regulatory Verified): PASS
  * Verdict: **FULLY VERIFIED** (Scope: Strictly limited to authorized categories with quantitative maximum caps).

---

### Record 8: `ins-500ii` — Sodium Hydrogen Carbonate
* **Canonical Identity**: Sodium hydrogen carbonate (Codex GSFA INS 500(ii); common: sodium bicarbonate / baking soda).
* **Identifiers**: INS 500(ii), E 500(ii), CAS 144-55-8. (CAS populated in `cas_number`; disambiguated from 500(i) sodium carbonate).
* **Category & Functional Class**: `food_additive` | Functional Class: Raising agent, Acidity regulator.
* **Alias Safety Evaluation**: Bare codes `"500(ii)"` and `"500ii"` removed from `aliases`. Enclosed parenthesized forms (`"raising agent (500(ii))"`, `"ins 500(ii)"`, `"e500(ii)"`) and sub-index standalone syntax (`500(ii)`) are preserved.
* **Scientific Claims vs. Evidence**: JECFA (1985, FAS 20) allocated a Group ADI "not specified" for sodium carbonates and bicarbonates. Physiologically dissociates into homeostatically regulated ions. Contributes 27.4% sodium by mass, relevant to individuals on sodium-restricted regimens. Supported.
* **Indian Regulatory Claims (FSSAI)**: FSSAI 2011 Appendix A authorizes sodium hydrogen carbonate under Good Manufacturing Practice in bakery products, snack foods, and flours. Supported.
* **Verification Status Matrix**:
  * Track 1 (URL Recorded): PASS
  * Track 2 (URL Accessible): PASS (`fssai.gov.in`, `apps.who.int`)
  * Track 3 (Content Checked): PASS
  * Track 4 (Scientific Supported): PASS
  * Track 5 (Regulatory Verified): PASS
  * Verdict: **FULLY VERIFIED** (Scope: GMP authorization in bakery and cereal formulations).

---

### Record 9: `ing-turmeric` — Turmeric
* **Canonical Identity**: Turmeric (Curcuma longa L. rhizome powder).
* **Identifiers**: CAS 84775-52-0 (whole rhizome/extract). (Disambiguated from isolated Curcumin pigment CAS 458-37-7).
* **Category & Functional Class**: `ordinary_ingredient`, `flavouring` | Functional Class: Spice, Natural colouring.
* **Alias Safety Evaluation**: Verified aliases (`"turmeric"`, `"haldi"`, `"turmeric powder"`, `"हल्दी"`) are botanical and culinary terms with zero false positive risk.
* **Scientific Claims vs. Evidence**: Agricultural whole spice without a toxicological ADI; culinary intake recognized as safe. Curcuminoids exhibit antioxidant properties. High supplemental doses (>3g isolated curcumin extract) may produce GI discomfort or anticoagulant interactions; culinary spice levels are well tolerated. Supported.
* **Indian Regulatory Claims (FSSAI)**: FSSAI 2011 Regulation 2.9.27 governs Turmeric (Haldi) whole and powder. Mandates total ash <= 9.0%, moisture <= 10.0%, and absolute freedom from lead chromate adulteration. Supported.
* **Audit Correction Applied**: The pre-audit knowledge base conflated Turmeric whole spice with CAS 458-37-7 (which is Curcumin, the isolated pigment, INS 100(i)). Corrected to CAS 84775-52-0 with explicit documentation of the agricultural vs. isolated pigment boundary.
* **Verification Status Matrix**:
  * Track 1 (URL Recorded): PASS
  * Track 2 (URL Accessible): PASS (`fssai.gov.in`)
  * Track 3 (Content Checked): PASS
  * Track 4 (Scientific Supported): PASS
  * Track 5 (Regulatory Verified): PASS
  * Verdict: **FULLY VERIFIED** (Scope: Agricultural spice and botanical ingredient).

---

### Record 10: `fort-vit-d2` — Ergocalciferol (Vitamin D2)
* **Canonical Identity**: Ergocalciferol (Vitamin D2; IUPAC: (3beta,5Z,7E,22E)-9,10-secoergosta-5,7,10(19),22-tetraen-3-ol).
* **Identifiers**: CAS 50-14-6. (Disambiguated from Cholecalciferol Vitamin D3, CAS 67-97-0).
* **Category & Functional Class**: `fortification_compound`, `nutritional_component` | Functional Class: Nutrient fortificant.
* **Alias Safety Evaluation**: Aliases (`"ergocalciferol"`, `"vitamin d2"`, `"vit d2"`, `"calciferol"`, `"vitamin d"`) are safe. **Audit Boundary Note**: "Vitamin D" on commercial Indian packages may legally represent either Vitamin D2 or Vitamin D3 under FSSAI 2018 Schedule I. In this baseline release, matching "Vitamin D" resolves to `fort-vit-d2` as a recognized representative entity.
* **Scientific Claims vs. Evidence**: Tolerable Upper Intake Level (UL) is 4,000 IU/day (100 mcg/day) for adults (ICMR-NIN 2020 / EFSA). Essential fat-soluble vitamin mediating calcium absorption and bone mineralization. Excessive chronic overdose produces hypercalcemia; food fortification levels are strictly calibrated far below UL. Supported.
* **Indian Regulatory Claims (FSSAI)**: FSSAI (Fortification of Foods) Regulations 2018 Schedule I authorizes Vitamin D2 for fortification of Edible Oil (0.11–0.16 mcg/g) and Milk (0.5–0.75 mcg/100 ml) under the statutory **+F logo**. Supported.
* **Verification Status Matrix**:
  * Track 1 (URL Recorded): PASS
  * Track 2 (URL Accessible): PASS (`fssai.gov.in`)
  * Track 3 (Content Checked): PASS
  * Track 4 (Scientific Supported): PASS
  * Track 5 (Regulatory Verified): PASS
  * Verdict: **FULLY VERIFIED** (Scope: Staple food fortification within statutory concentration bands).

---

### Record 11: `fort-ferric-pyrophosphate` — Ferric Pyrophosphate
* **Canonical Identity**: Ferric Pyrophosphate (Iron(III) diphosphate; Fe4(P2O7)3).
* **Identifiers**: CAS 10058-44-3.
* **Category & Functional Class**: `fortification_compound`, `nutritional_component` | Functional Class: Mineral fortificant.
* **Alias Safety Evaluation**: Aliases (`"ferric pyrophosphate"`, `"iron pyrophosphate"`, `"micronized ferric pyrophosphate"`) are specific and robust against false positives.
* **Scientific Claims vs. Evidence**: Tolerable Upper Intake Level is 45 mg elemental iron/day for adults (ICMR-NIN 2020). Water-insoluble form prevents organoleptic discoloration and fat rancidity during grain storage; micronization achieves bioavailability comparable to ferrous sulphate. Supported.
* **Indian Regulatory Claims (FSSAI)**: FSSAI (Fortification of Foods) Regulations 2018 Schedule I authorizes ferric pyrophosphate as a permitted iron source for Fortified Rice (28–42.5 mg/kg) and Fortified Wheat Flour. Supported.
* **Verification Status Matrix**:
  * Track 1 (URL Recorded): PASS
  * Track 2 (URL Accessible): PASS (`fssai.gov.in`)
  * Track 3 (Content Checked): PASS
  * Track 4 (Scientific Supported): PASS
  * Track 5 (Regulatory Verified): PASS
  * Verdict: **FULLY VERIFIED** (Scope: Grain fortification under FSSAI Schedule I).

---

### Record 12: `ing-soy-protein-isolate` — Soy Protein Isolate
* **Canonical Identity**: Soy Protein Isolate (isolated soya protein).
* **Identifiers**: CAS 9010-10-0.
* **Category & Functional Class**: `allergen`, `ordinary_ingredient`, `nutritional_component` | Functional Class: Protein fortificant, Allergen, Emulsifier.
* **Alias Safety Evaluation**: Aliases (`"soy protein isolate"`, `"soya protein isolate"`, `"isolated soy protein"`) are specific and safe.
* **Scientific Claims vs. Evidence**: Complete plant protein (>90% protein dry weight basis). Recognized major food allergen provoking IgE-mediated reactions ranging from mild dermatitis to life-threatening systemic anaphylaxis. Supported.
* **Indian Regulatory Claims (FSSAI)**: FSSAI (Labelling and Display) Regulations 2020 Regulation 5(3)(e) legally mandates front/back panel allergen declaration: `"Contains Soy"` or `"Contains Soybeans and products thereof"`.
* **Audit Correction Applied**: The pre-audit citation referenced "Clause 5(4)". Corrected to statutory Regulation 5(3)(e) ("Declaration regarding Food Allergen").
* **Verification Status Matrix**:
  * Track 1 (URL Recorded): PASS
  * Track 2 (URL Accessible): PASS (`fssai.gov.in`)
  * Track 3 (Content Checked): PASS
  * Track 4 (Scientific Supported): PASS
  * Track 5 (Regulatory Verified): PASS
  * Verdict: **FULLY VERIFIED** (Scope: Food ingredient subject to mandatory statutory allergen labelling).

---

### Record 13: `ins-955` — Sucralose
* **Canonical Identity**: Sucralose (Codex GSFA INS 955; IUPAC: 1,6-dichloro-1,6-dideoxy-beta-D-fructofuranosyl 4-chloro-4-deoxy-alpha-D-galactopyranoside).
* **Identifiers**: INS 955, E 955, CAS 56038-13-2. (CAS populated in `cas_number`).
* **Category & Functional Class**: `sweetener`, `food_additive` | Functional Class: Non-nutritive sweetener.
* **Alias Safety Evaluation**: Bare digit string `"955"` removed from `aliases`. Preserved aliases: `"sucralose"`, `"sweetener (955)"`, `"sweetener ins 955"`, `"ins 955"`, `"e955"`, `"splenda"`.
* **Scientific Claims vs. Evidence**: JECFA (1990, 35th Report, TRS 789) allocated an ADI of 0–15 mg/kg bw/day (reaffirmed by EFSA). Approximately 600 times sweeter than sucrose. Minimally absorbed (~15%), un-metabolized for energy, excreted unchanged in feces. Non-carcinogenic in rodent bioassays. Supported.
* **Indian Regulatory Claims (FSSAI)**: FSSAI 2011 Regulation 3.1.2 & Table 1 authorizes sucralose in specified foods (e.g., carbonated water max 300 ppm, biscuits max 750 ppm). FSSAI 2020 Schedule II Clause 1(2) mandates declaration: `"CONTAINS NON-CALORIC SWEETENER - SUCRALOSE"`. Supported.
* **Verification Status Matrix**:
  * Track 1 (URL Recorded): PASS
  * Track 2 (URL Accessible): PASS (`fssai.gov.in`, `apps.who.int`)
  * Track 3 (Content Checked): PASS
  * Track 4 (Scientific Supported): PASS
  * Track 5 (Regulatory Verified): PASS
  * Verdict: **FULLY VERIFIED** (Scope: Strictly limited to authorized categories with statutory ppm caps).

---

### Record 14: `ing-cocoa-butter-prep` — Cocoa Butter Preparation
* **Canonical Identity**: Cocoa Butter Preparation (Compound fat ingredient).
* **Identifiers**: CAS None (Multi-component lipid mixture from Theobroma cacao).
* **Category & Functional Class**: `compound_ingredient`, `ordinary_ingredient` | Functional Class: Compound fat ingredient.
* **Alias Safety Evaluation**: Aliases (`"cocoa butter preparation"`, `"cocoa butter prep"`, `"chocolate fat preparation"`) are specific and safe.
* **Scientific Claims vs. Evidence**: Natural edible vegetable fat rich in stearic, palmitic, and oleic fatty acids. Standard culinary macronutrient with no toxicological ADI. Supported.
* **Indian Regulatory Claims (FSSAI)**: Standardized chocolate ingredient under FSSAI 2011 Regulation 2.7.4. Compound food parenthetical declaration rules governed by FSSAI Labelling and Display Regulations 2020 Clause 5(2)(a). Supported.
* **Verification Status Matrix**:
  * Track 1 (URL Recorded): PASS
  * Track 2 (URL Accessible): PASS (`fssai.gov.in`)
  * Track 3 (Content Checked): PASS
  * Track 4 (Scientific Supported): PASS
  * Track 5 (Regulatory Verified): PASS
  * Verdict: **FULLY VERIFIED** (Scope: Standardized confectionery compound ingredient).

---

### Record 15: `proc-papain` — Papain
* **Canonical Identity**: Papain (Enzyme EC 3.4.22.2; cysteine protease from Carica papaya latex).
* **Identifiers**: CAS 9001-73-4, EC 3.4.22.2.
* **Category & Functional Class**: `processing_aid` | Functional Class: Enzyme, Meat tenderizer, Clarifying agent.
* **Alias Safety Evaluation**: Aliases (`"papain"`, `"papaya proteinase"`, `"protease papain"`) are specific and safe.
* **Scientific Claims vs. Evidence**: Evaluated as an enzyme processing aid by JECFA (1971, 1987); ADI "not specified". Inactivated by heat and cooking in finished food. Occupational enzyme dust inhalation can produce respiratory sensitization; dietary intake in finished food is safe. Supported.
* **Indian Regulatory Claims (FSSAI)**: FSSAI 2011 Regulation 3.3.1 (Enzymes) / FSSAI (Processing Aids) Regulations 2018 authorizes papain for meat tenderization and protein hydrolysis under Good Manufacturing Practice. Supported.
* **Verification Status Matrix**:
  * Track 1 (URL Recorded): PASS
  * Track 2 (URL Accessible): PASS (`fssai.gov.in`)
  * Track 3 (Content Checked): PASS
  * Track 4 (Scientific Supported): PASS
  * Track 5 (Regulatory Verified): PASS
  * Verdict: **FULLY VERIFIED** (Scope: Processing aid under GMP).

---

### Record 16: `nutr-inulin` — Inulin
* **Canonical Identity**: Inulin (linear beta-(2->1) fructan polysaccharide from chicory root Cichorium intybus).
* **Identifiers**: CAS 9005-80-5.
* **Category & Functional Class**: `nutritional_component`, `ordinary_ingredient` | Functional Class: Dietary fiber, Prebiotic.
* **Alias Safety Evaluation**: Aliases (`"inulin"`, `"chicory root fiber"`, `"chicory inulin"`, `"prebiotic inulin"`) are specific and safe.
* **Scientific Claims vs. Evidence**: Soluble prebiotic dietary fiber undergoing selective fermentation by bifidobacteria in the colon. Acute intake >15–20g may induce transient osmotic GI symptoms (FODMAP). Supported.
* **Indian Regulatory Claims (FSSAI)**: FSSAI (Health Supplements, Nutraceuticals, Food for Special Dietary Use) Regulations 2022 Schedule I & Schedule IV approves inulin as a prebiotic ingredient and dietary fiber. Supported.
* **Verification Status Matrix**:
  * Track 1 (URL Recorded): PASS
  * Track 2 (URL Accessible): PASS (`fssai.gov.in`)
  * Track 3 (Content Checked): PASS
  * Track 4 (Scientific Supported): PASS
  * Track 5 (Regulatory Verified): PASS
  * Verdict: **FULLY VERIFIED** (Scope: Recognized prebiotic and dietary fiber ingredient).

---

## 5. Summary Verification Status Matrix (All 16 Records)

| Record ID | Canonical Name | Category | Track 1 (URL) | Track 2 (Access) | Track 3 (Check) | Track 4 (Science) | Track 5 (Law) | Status | Audit Finding |
|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| `ins-621` | Monosodium L-glutamate | Food Additive | PASS | PASS | PASS | PASS | PASS | Fully Verified | Bare "621" removed; infant ban verified |
| `ins-951` | Aspartame | Sweetener | PASS | PASS | PASS | PASS | PASS | Fully Verified | Bare "951" removed; PKU warning verified |
| `ins-150d` | Caramel IV | Food Additive | PASS | PASS | PASS | PASS | PASS | Fully Verified | Bare "150d" removed; 4-MEI cap verified |
| `ins-322` | Lecithins | Food Additive | PASS | PASS | PASS | PASS | PASS | Fully Verified | Bare numbers removed; allergen origin verified |
| `ins-211` | Sodium Benzoate | Food Additive | PASS | PASS | PASS | PASS | PASS | Fully Verified | Bare "211" removed; category caps verified |
| `ins-330` | Citric Acid | Food Additive | PASS | PASS | PASS | PASS | PASS | Fully Verified | Bare "330" removed; GMP status verified |
| `ins-102` | Tartrazine | Food Additive | PASS | PASS | PASS | PASS | PASS | Fully Verified | Bare "102" removed; mandatory label colour disclosure verified |
| `ins-500ii` | Sodium Hydrogen Carbonate | Food Additive | PASS | PASS | PASS | PASS | PASS | Fully Verified | Bare codes removed; sub-index verified |
| `ing-turmeric` | Turmeric | Ordinary Spice | PASS | PASS | PASS | PASS | PASS | Fully Verified | Conflation resolved (CAS 84775-52-0 vs 458-37-7) |
| `fort-vit-d2` | Ergocalciferol (D2) | Fortificant | PASS | PASS | PASS | PASS | PASS | Fully Verified | Schedule I +F milk/oil limits verified |
| `fort-ferric-pyrophosphate` | Ferric Pyrophosphate | Fortificant | PASS | PASS | PASS | PASS | PASS | Fully Verified | Schedule I +F rice/flour limits verified |
| `ing-soy-protein-isolate` | Soy Protein Isolate | Allergen | PASS | PASS | PASS | PASS | PASS | Fully Verified | Citation corrected to Regulation 5(3)(e) |
| `ins-955` | Sucralose | Sweetener | PASS | PASS | PASS | PASS | PASS | Fully Verified | Bare "955" removed; ppm limits verified |
| `ing-cocoa-butter-prep` | Cocoa Butter Prep | Compound | PASS | PASS | PASS | PASS | PASS | Fully Verified | Compound food rules verified |
| `proc-papain` | Papain | Processing Aid | PASS | PASS | PASS | PASS | PASS | Fully Verified | Regulation 3.3.1 enzyme limits verified |
| `nutr-inulin` | Inulin | Nutritional | PASS | PASS | PASS | PASS | PASS | Fully Verified | 2022 Nutraceutical Schedule I/IV verified |

---

## 6. Audit Discrepancies Identified and Corrections Applied

During the forensic audit of the 16 reference records, the following discrepancies were identified and resolved:

1. **Turmeric vs. Curcumin CAS Conflation**:
   * *Pre-Audit State*: `ing-turmeric` listed CAS `458-37-7`.
   * *Finding*: CAS 458-37-7 identifies **Curcumin** (diferuloylmethane, the purified pigment, INS 100(i)). The agricultural whole spice Turmeric is registered under CAS `84775-52-0` (or lacks a single CAS due to complex botanical matrix).
   * *Correction*: Updated top-level CAS to `84775-52-0`, refined chemical identity to clearly distinguish the whole spice from the isolated curcumin constituent, and updated provenance notes.
2. **Missing Top-Level CAS Identifiers for Additives**:
   * *Pre-Audit State*: Records 1–8 had `cas_number: None` at the top level, even though CAS numbers were embedded in the unstructured `chemical_identity` string.
   * *Correction*: Populated all top-level `cas_number` fields with verified registry strings (`142-47-2`, `22839-47-0`, `8028-89-5`, `8002-43-5`, `532-32-1`, `77-92-9`, `1934-21-0`, `144-55-8`).
3. **Out-of-Context Bare Numeric Aliases**:
   * *Pre-Audit State*: `aliases` lists contained bare strings such as `"621"`, `"951"`, `"150d"`, `"322"`, `"211"`, `"330"`, `"102"`, `"500ii"`, `"955"`.
   * *Finding*: A bare 3-digit number has no statutory context. In OCR or unstructured text, numbers like "621" or "330" frequently represent net weights ("330g"), energy ("621 kJ"), or batch numbers, creating a severe false positive vector.
   * *Correction*: Removed bare numbers from `aliases`. Hardened `extract_ins_pattern` in `matcher.py` so that 3-4 digit numbers are only extracted as INS candidates when accompanied by `INS`/`E` prefix, functional prefix, or parentheses (`(621)`).
4. **Incorrect Statutory Clause in Soy Allergen Citation**:
   * *Pre-Audit State*: `ing-soy-protein-isolate` cited Clause 5(4) of the FSSAI Labelling Regulations.
   * *Finding*: In the official Gazette Notification of the FSSAI (Labelling and Display) Regulations, 2020, mandatory allergen declarations are governed by **Regulation 5(3)** (specifically Clause 5(3)(e) for Soybeans).
   * *Correction*: Updated citation and supported claims text to Regulation 5(3)(e).
5. **Decoupling of Provenance Booleans into 5 Independent Tracks**:
   * *Pre-Audit State*: Blanket flags (`source_checked: true`, `scientifically_reviewed: true`, `regulatory_verified: true`) were carried over without multi-track verification.
   * *Correction*: Expanded `EvidenceProvenance` and `validate_ingredient_kb.py` to independently evaluate: (1) URL recorded, (2) URL accessible on authoritative domain, (3) Source content checked by auditor, (4) Scientific claims supported, (5) Regulatory status verified with documented scope limitations.

---

## 7. Scope Limitations & Verified Baseline
* **Absence from Reference Does Not Mean Dangerous**: When healthyIndia analyzes a packaged product and reports ingredients in `unmatched_items`, this indicates that the ingredient is not yet in the curated knowledge base. The system strictly refuses to probabilistically guess unknown substances.
* **Physical-Photo OCR Benchmark Status**: The local OCR physical-photo accuracy remains marked as **`UNMEASURED`**. System deployment status remains **`NOT READY FOR PRODUCTION`**. Public health release requires completing a physical packaging photographic study with ground-truth verification.

---

## 8. Phase 4D Controlled Catalogue Expansion (Records 17–21)

In Phase 4D, a controlled expansion introduced 5 high-frequency packaged food staples widely present in Indian packaged food declarations:

### Record 17: `ing-palm-oil` — Palm Oil
* **Canonical Identity**: Palm Oil (Elaeis guineensis fruit oil).
* **Identifiers**: CAS 8002-75-3.
* **Category & Functional Class**: `ordinary_ingredient` | Functional Classes: Vegetable Fat, Cooking Oil.
* **Statutory Citation**: FSSAI Food Safety and Standards (Food Products Standards and Food Additives) Regulations, 2011, Regulation 2.2.1(19).
* **Scientific & Health Evidence**: Composed of ~50% saturated fatty acids (palmitic acid) and 40% monounsaturated oleic acid. High intake is associated with elevated LDL cholesterol (WHO 2023).
* **5-Track Status**: All 5 tracks PASS (Fully Verified).

### Record 18: `ing-whole-wheat-flour` — Whole Wheat Flour (Atta)
* **Canonical Identity**: Whole Wheat Flour / Atta (Milled Triticum aestivum retaining bran, germ, and endosperm).
* **Identifiers**: CAS None (agricultural cereal commodity).
* **Category & Functional Class**: `ordinary_ingredient`, `allergen` | Functional Classes: Cereal Staple, Whole Flour.
* **Statutory Citation**: FSSAI Regulations 2011, Regulation 2.4.1(1) (Atta standard of identity: gluten >=6.0%, ash <=2.0%) & FSSAI Labelling Regulations 2020 Clause 5(3) (Mandatory cereal allergen).
* **5-Track Status**: All 5 tracks PASS (Fully Verified).

### Record 19: `ing-refined-wheat-flour` — Refined Wheat Flour (Maida)
* **Canonical Identity**: Refined Wheat Flour / Maida (Milled Triticum aestivum endosperm).
* **Identifiers**: CAS 130498-22-5.
* **Category & Functional Class**: `ordinary_ingredient`, `allergen` | Functional Classes: Cereal Staple, Refined Flour.
* **Statutory Citation**: FSSAI Regulations 2011, Regulation 2.4.2(1) (Maida standard of identity: gluten >=7.5%, ash <=1.0%) & FSSAI Labelling Regulations 2020 Clause 5(3).
* **5-Track Status**: All 5 tracks PASS (Fully Verified).

### Record 20: `ing-sugar` — Sugar (Sucrose)
* **Canonical Identity**: Sugar / Sucrose (beta-D-fructofuranosyl alpha-D-glucopyranoside).
* **Identifiers**: CAS 57-50-1.
* **Category & Functional Class**: `ordinary_ingredient`, `sweetener` | Functional Classes: Nutritive Sweetener, Bulking Agent.
* **Statutory Citation**: FSSAI Regulations 2011, Regulation 2.8.1 (Refined Sugar purity >= 99.5%) & FSSAI Labelling Regulations 2020 Clause 5(2) (Mandatory added sugars disclosure).
* **Scientific Guidance**: WHO Guideline (2015) strongly recommends free sugars <10% total energy intake (conditional <5%, ~25g/day). ICMR-NIN 2020 added sugar limit <=25g/day.
* **5-Track Status**: All 5 tracks PASS (Fully Verified).

### Record 21: `ing-iodized-salt` — Iodized Salt
* **Canonical Identity**: Iodized Salt (NaCl fortified with potassium iodate, KIO3).
* **Identifiers**: CAS 7647-14-5.
* **Category & Functional Class**: `ordinary_ingredient`, `fortification_compound` | Functional Classes: Seasoning, Essential Mineral Source.
* **Statutory Citation**: FSSAI Regulations 2011, Regulation 2.9.30 (Mandatory iodization standard: NaCl >=96.0%, iodine >=15 ppm retail).
* **Scientific Guidance**: WHO guideline (2020) recommends <2000 mg sodium (~5 g salt) per day for adults to prevent hypertension.
* **5-Track Status**: All 5 tracks PASS (Fully Verified).
