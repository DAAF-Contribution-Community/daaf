# MEPS vs FRPL: Why MEPS is Superior for Cross-State Analysis

Detailed comparison of Model Estimates of Poverty in Schools (MEPS) and Free/Reduced-Price Lunch (FRPL) eligibility as school poverty measures.

## The FRPL Problem

### What is FRPL?

Free and Reduced-Price Lunch (FRPL) eligibility has traditionally been used to measure school poverty:
- **Free lunch**: Family income ≤130% FPL
- **Reduced-price lunch**: Family income 131-185% FPL
- **Combined FRPL**: Income ≤185% FPL

### Why FRPL Was Once Useful

Before 2010, FRPL was a reasonable poverty proxy because:
- Schools collected income verification forms from families
- The data was available at the school level
- It captured a meaningful economic threshold

### The Community Eligibility Provision (CEP) Problem

**CEP**, introduced in the Healthy, Hunger-Free Kids Act of 2010, allows schools to provide **free meals to ALL students** if they meet certain thresholds.

#### CEP Mechanics

1. The school, group of schools, or district computes its **Identified Student Percentage (ISP)**. ISP = identified students ÷ enrollment as of April 1 of the prior school year. Identified students are those certified for free meals *without an application*: directly certified via SNAP, TANF, FDPIR or (in USDA-approved states) Medicaid, plus homeless, migrant, runaway, Head Start and non-application foster children. ISP is not identical to CCD's direct-certification count.
2. If ISP ≥ 25%, it may elect CEP (≥ 40% before USDA's final rule, 88 FR 65778, effective 2023-10-26). Groups may average.
3. CEP schools *may* report all students as free-lunch eligible (NCES). Since SY 2016-17, states may report FRPL and/or direct-certification counts instead.
4. CEP schools can no longer use USDA funds to collect FRPL forms (Gutierrez & Blagg 2025)

#### Impact on FRPL Data

| Metric | Pre-CEP | Post-CEP |
|--------|---------|----------|
| Data collection | Income forms from families | USDA funds cannot be used to collect FRPL forms |
| FRPL reported | Actual eligible students | May be all students; some states report direct certification instead |
| Poverty signal | Reasonable proxy | Inflated where all students are reported as eligible |

### CEP Adoption Rates

| School year | CEP schools (FRAC) |
|-------------|--------------------|
| 2014-15 | 14,184 |
| 2016-17 | 20,678 |
| 2018-19 | 28,809 |
| 2020-21 | 33,407 |
| 2022-23 | 40,235 |
| 2024-25 | 54,234 |
| 2025-26 | 55,362 |

**Key insight**: FRAC counts 40,235 CEP schools in SY 2022-23 and 55,362 in SY 2025-26 (74.9% of eligible schools). That is roughly 41% and 56% of the ~98,600 U.S. public schools (DAAF calculation; FRAC and NCES school universes differ). USDA pandemic waivers also let every school serve free meals in SY 2020-21 and 2021-22.

## State-Level FRPL Variation

### Different States, Different Rules

Even before CEP, FRPL varied by state due to:

1. **Direct certification scope**
   - Some states auto-certify SNAP participants only
   - Others include TANF, Medicaid, foster care
   - Coverage varies significantly

2. **Form collection policies**
   - Some states require forms from all families
   - Others only collect from those seeking eligibility
   - Affects non-response rates

3. **Verification requirements**
   - Some states verify more applications
   - Affects who remains "eligible" after verification

4. **Categorical eligibility**
   - Some states have broader categorical eligibility
   - Certain populations auto-qualify regardless of income

### Illustrative Point: Similar FRPL Rates, Different Policies

*Illustrative; no state figures are given because none were sourced.* Two states can report similar FRPL rates while differing in which benefit programs feed direct certification, in CEP uptake, and in actual poverty. The similar FRPL rates then mask different underlying policies and poverty levels. One documented source of variation: as of SY 2025-26, FRAC reports that 44 states use Medicaid and household income data to directly certify children for free or reduced-price school meals.

## Comparing FRPL and MEPS

### Fundamental Differences

| Dimension | FRPL | MEPS |
|-----------|------|------|
| **Source** | Administrative program data | Statistical model |
| **Poverty threshold** | 130-185% FPL | 100% FPL |
| **Consistency** | Varies by state/year | Standardized nationwide |
| **CEP impact** | Distorted where CEP schools report all students | Accounts for CEP |
| **What it measures** | Program participation | Estimated true poverty |
| **Comparability** | Poor across states | Designed for comparison |

### Poverty Threshold Comparison

```
HHS poverty guideline (2024, family of 4, 48 states + DC): $31,200

FRPL Free Lunch (130% of guideline):     $40,560
FRPL Reduced Lunch (185% of guideline):  $57,720
100% of guideline:                       $31,200
```

These are HHS poverty guidelines (FRPL basis). MEPS targets SAIPE/Census poverty thresholds, so the 100% line above is only an approximation of the MEPS threshold.

**MEPS measures deeper poverty** - families at or below the official poverty line, not near-poverty.

### Relationship Between FRPL and MEPS

*Illustrative; no FRPL-MEPS correlation figures are given because none were sourced.* Urban reports that the FRPL measure "became increasingly unreliable with the introduction of the federal universal free school meal program CEP" (Gutierrez & Blagg 2025), so FRPL should be expected to track poverty less closely as CEP spreads.

## When to Use Each Measure

### Use MEPS When:

1. **Comparing schools across different states**
   - MEPS is standardized; FRPL is not

2. **Analyzing trends over time (2010+)**
   - CEP adoption makes FRPL inconsistent over time

3. **Research requiring consistent poverty measurement**
   - MEPS provides comparability for statistical analysis

4. **Studying where high-poverty schools are (research, not allocation)**
   - MEPS is comparable across states and time; Urban says it should not be used to allocate resources within a state or district

5. **Controlling for socioeconomic status in regressions**
   - MEPS is a better control variable due to consistency

### Use FRPL When:

1. **Studying school meal program participation itself**
   - FRPL directly measures program participation

2. **Replicating historical studies using FRPL**
   - May need FRPL for comparability with prior research

3. **Federal formula compliance**
   - Some federal programs mandate FRPL-based calculations

4. **Understanding meal program operations**
   - FRPL data relevant for food service planning

### Use Both When:

1. **Studying CEP impact**
   - Compare MEPS (true poverty) vs FRPL (program measure)

2. **Examining state policy effects**
   - Differences reveal policy impacts

3. **Validating poverty measures**
   - Cross-validation between measures

## State-by-State FRPL Reliability

*The earlier most/least reliable state lists were removed because they were unsourced.*

### Recommendation

Even in "reliable" states, **MEPS is preferred** for cross-state comparison because:
1. Consistent methodology nationwide
2. Model fit to adjusted Census SAIPE district poverty
3. Accounts for known FRPL biases

## The Direct Certification Problem

### What is Direct Certification?

Direct certification identifies students eligible for free meals based on participation in other programs:
- SNAP (Supplemental Nutrition Assistance Program)
- TANF (Temporary Assistance for Needy Families)
- Medicaid (in some states)
- Foster care
- Homeless status
- Migrant status

### Direct Certification Variation

*Illustrative; the earlier state-by-state program table was removed because it was unsourced.* Direct certification identifies students whose households participate in SNAP, TANF, or Medicaid, "depending on the state", and "the income eligibility thresholds and work requirements for these programs also vary by state" (Gutierrez & Blagg 2025). As of SY 2025-26, FRAC reports that 44 states use Medicaid and household income data for direct certification.

### Impact on FRPL Comparability

*Illustrative:* a school with 50% directly certified students can mean different things in different states. Where Medicaid data are matched, the certified group can include families from a different income range than in a state that matches only SNAP and TANF.

## Practical Guidance

### For Researchers

1. **Default to MEPS** for school poverty analysis
2. **Document your choice** and rationale
3. **Consider sensitivity analysis** using both measures
4. **Note the 100% vs 185% FPL threshold difference**

### For Policymakers

1. **Recognize FRPL limitations** in funding formulas
2. **Do not use MEPS to allocate resources** within a state or district (Urban). Use it for cross-state and longitudinal research. For allocation, Urban points to measures linked to enrolled students, such as direct-certification counts or counts of students in foster care or experiencing homelessness
3. **Understand CEP schools** are not necessarily 100% poor

### For Practitioners

1. **Use student-linked measures for school needs assessment** (e.g., direct-certification counts); use MEPS for cross-state or trend context
2. **Use FRPL for meal program operations**
3. **Don't assume high FRPL = high poverty** in CEP schools

## Summary

| Criterion | FRPL | MEPS |
|-----------|------|------|
| Cross-state comparison | Poor | Excellent |
| Temporal consistency | Declining | Good |
| Measures actual poverty | Increasingly poor | Yes |
| Data availability | All schools | Most public schools |
| Official metric status | Yes (federal programs) | No (research measure) |
| Recommended for research | Only pre-2010 | Yes (2009-10+) |

**Bottom line**: For any analysis requiring consistent, comparable school poverty measurement, MEPS is the superior choice. FRPL should only be used when program participation itself is the focus or when mandated by specific requirements.
