# IPEDS Financial Aid Data

Understanding student financial aid data, net price calculations, and their limitations.

## Contents

- [Financial Aid Survey Overview](#financial-aid-survey-overview)
- [Student Populations](#student-populations)
- [Aid Types](#aid-types)
- [Net Price](#net-price)
- [Cost of Attendance](#cost-of-attendance)
- [Military Benefits](#military-benefits)
- [Common Analysis Issues](#common-analysis-issues)
- [Variable Reference](#variable-reference)

## Financial Aid Survey Overview

The Student Financial Aid (SFA) survey collects:
- Counts of students receiving different types of aid
- Total amounts awarded by aid type
- Average amounts calculated from these data

### Collection Period

Winter collection (December-February) for the prior academic year.

### Reporting Requirements

All Title IV institutions must report SFA data.

### Key Data Elements

1. Number of students receiving aid (by type)
2. Total amount of aid awarded (by type)
3. Average award = Total amount / Number receiving

## Student Populations

**Critical**: Different data elements use different student populations.

### Population Definitions

| Population | Definition | Primary Use |
|------------|------------|-------------|
| All undergraduates | All enrolled undergrads | Total aid picture |
| Full-time first-time (FTFT) | First-time, full-time, degree-seeking | Net price calculation |
| Full-time undergraduates | Full-time, degree-seeking | Comparative analysis |
| Part-time undergraduates | Part-time, degree-seeking | Limited reporting |
| Graduate students | Master's and doctoral | Separate from undergrad |

### Why Different Populations Matter

| Population | Pros | Cons |
|------------|------|------|
| All undergrads | Most comprehensive | Heterogeneous mix |
| FTFT only | Comparable across institutions | Small, selective group |
| Full-time only | More comparable | Misses PT students |

### First-Time Full-Time Limitation

Net price and many aid statistics use only FTFT students who:
- Never attended college before
- Started full-time
- Are degree/certificate-seeking

**At community colleges**, this may be <25% of students.

## Aid Types

### Grant Aid (Gift Aid)

Does not need to be repaid.

| Type | Source | Description |
|------|--------|-------------|
| Pell Grant | Federal | Need-based, up to ~$7,400/year |
| FSEOG | Federal | Supplemental grant, need-based |
| Other federal grants | Federal | Various programs |
| State grants | State | Varies by state |
| Local grants | Local | Varies by locality |
| Institutional grants | Institution | School-funded aid |

### Federal Loans

Must be repaid.

| Type | Description | Interest |
|------|-------------|----------|
| Direct Subsidized | Need-based, no interest while enrolled | Government pays |
| Direct Unsubsidized | Not need-based | Student pays |
| Direct PLUS | Parent loans for undergrads | Higher rate |
| Perkins | Campus-based (discontinued) | Low rate |

### Work-Study

Federal Work-Study program:
- Part-time employment
- Usually need-based
- Institution administers

### Aid Award Statistics

```python
# Average award calculation
avg_grant = total_grant_amount / number_receiving_grants

# Percent receiving aid
pct_receiving = students_with_aid / total_students * 100
```

## Net Price

### Definition

**Net Price = Cost of Attendance - Grant Aid Received**

This represents what students actually pay after grants (but before loans).

### Calculation Population

Net price is calculated ONLY for:
- First-time, full-time degree/certificate-seeking undergraduates
- Who were awarded any Title IV aid

**Excludes**:
- Part-time students
- Transfer students
- Students receiving no Title IV aid (full-pay students)
- Non-degree students

### Net Price by Income Level

IPEDS reports net price by family income quintile:

| Income Level | Income Range |
|--------------|--------------|
| $0 - $30,000 | Lowest income |
| $30,001 - $48,000 | Low-middle income |
| $48,001 - $75,000 | Middle income |
| $75,001 - $110,000 | Upper-middle income |
| $110,001 and above | Highest income |

### Why Net Price by Income Matters

```python
# Example showing why average net price is misleading
avg_net_price = 15000  # Overall average

# But by income level:
net_price_low_income = 8000    # After Pell, institutional aid
net_price_high_income = 22000  # Little grant aid

# Average masks important variation
```

### Net Price Limitations

| Limitation | Implication |
|------------|-------------|
| FTFT only | Not representative of all students |
| Title IV recipients only | Excludes full-pay students |
| Published vs actual | Individual packages vary widely |
| Excludes loans | Not total cost |
| Prior year data | May not reflect current prices |

### Interpreting Net Price

```python
# What net price tells you
net_price = sticker_price - grants

# What it doesn't tell you
# - Whether students can afford it
# - Loan amounts needed
# - Out-of-pocket costs
# - Impact of room and board choices
```

## Cost of Attendance

### Components

| Component | Description |
|-----------|-------------|
| Tuition and fees | Published tuition + required fees |
| Room and board | On-campus or estimated off-campus |
| Books and supplies | Estimated annual cost |
| Other expenses | Transportation, personal, etc. |

### Variations

| Student Type | Room/Board |
|--------------|------------|
| On-campus | On-campus rates |
| Off-campus (not with family) | Estimated local costs |
| Off-campus (with family) | Usually lower estimate |

### COA in Net Price Calculation

```python
# Net price components
coa = tuition_fees + room_board + books_supplies + other
net_price = coa - total_grant_aid
```

### Published vs Actual

| Measure | Description | Use |
|---------|-------------|-----|
| Published tuition | Sticker price | Comparison |
| Net tuition | After institutional discounts | Closer to reality |
| Net price | After all grants | What families pay |
| Out-of-pocket | After grants and loans | True cash needed |

## Military Benefits

### Types Tracked

| Benefit | Description |
|---------|-------------|
| Post-9/11 GI Bill | Veterans, service members |
| Yellow Ribbon | Institutional supplements |
| DoD Tuition Assistance | Active duty |
| Other military | Various programs |

### Data Collection

- Count of students receiving benefits
- Separate from other aid categories
- Graduate and undergraduate

### Limitation

Military benefits recipients may also receive other aid; avoid double-counting.

## Common Analysis Issues

### Issue 1: Comparing Net Price Across Institution Types

**Problem**: Different student populations make comparison misleading.

| Institution Type | Net Price Population |
|------------------|---------------------|
| Selective 4-year | FTFT is most students |
| Community college | FTFT is minority |
| For-profit | Variable enrollment patterns |

**Solution**: Note population differences; compare within peer groups.

### Issue 2: Average vs Distribution

**Problem**: Average net price hides important variation.

```python
# Hypothetical examples
# Institution A: Everyone pays $15,000
avg_a = 15000

# Institution B: Half pay $5,000, half pay $25,000
avg_b = 15000  # Same average, very different experience
```

**Solution**: Look at net price by income level.

### Issue 3: Full-Pay Students Not Included

**Problem**: Students not receiving Title IV aid are excluded.

| Group | Excluded Because |
|-------|-----------------|
| Wealthy families | Don't file FAFSA |
| International students | Not Title IV eligible |
| Undocumented students | Not Title IV eligible |

**Impact**: At wealthy institutions, net price may overstate what the full student body pays.

### Issue 4: Institutional Aid Variation

**Problem**: Institutional aid varies widely by student characteristics.

| Factor | Impact on Institutional Aid |
|--------|----------------------------|
| Academic merit | May get more aid |
| Athletic recruitment | May get more aid |
| Income level | Need-based aid varies |
| State residency | May affect aid |

**Solution**: Net price by income shows some of this variation.

### Issue 5: Debt vs Net Price

**Problem**: Low net price doesn't mean no debt.

```python
# Example
net_price = 12000  # After grants
pell_grant = 6000
institutional_grant = 4000
# Student needs $12,000 more
# Options: loans, work, family contribution

loans_taken = 8000  # Typical
out_of_pocket = 4000
```

**Solution**: Consider loan data alongside net price.

### Issue 6: Part-Time Students

**Problem**: Part-time students excluded from net price but:
- Are majority at many schools
- Have different aid patterns
- Face different cost structures

**Solution**: Note this limitation; use total aid data for broader picture.

## Data Interpretation Examples

### Comparing Two Institutions

```python
# Institution A (selective private)
net_price_a = 25000
pct_ftft = 80  # FTFT is 80% of students
interpretation: net_price reflects most students

# Institution B (community college)
net_price_b = 8000
pct_ftft = 20  # FTFT is 20% of students
interpretation: net_price reflects minority of students
```

### Analyzing Aid Effectiveness

```python
# Equity analysis
gap = net_price_high_income - net_price_low_income

# Positive gap = higher income pays more (progressive)
# Negative gap = lower income pays more (regressive)
# Zero = same net price regardless of income
```

### Grant Aid Coverage

```python
# What share of costs are covered by grants?
grant_coverage = total_grants / cost_of_attendance * 100

# High coverage = more affordable
# Low coverage = more loans/family contribution needed
```

## Variable Reference

### Student Counts

| Variable | Description |
|----------|-------------|
| `scugffn` | FTFT undergrads in net price cohort |
| `scugrad` | Undergrads receiving any aid |
| `scugran` | Undergrads receiving grants |
| `scugpel` | Undergrads receiving Pell |
| `scugfsl` | Undergrads receiving federal loans |
| `scugsta` | Undergrads receiving state grants |
| `scugist` | Undergrads receiving institutional grants |

### Aid Amounts

| Variable | Description |
|----------|-------------|
| `upgrnta` | Average undergraduate grant amount |
| `upgrnt` | Total undergraduate grants |
| `uppell` | Total Pell grant amount |
| `upfloan` | Total federal loan amount |
| `uagrnta` | Average grant to FTFT |
| `uagrntt` | Total grants to FTFT |

### Net Price Variables

| Variable | Description |
|----------|-------------|
| `npist1` | Net price, income $0-$30,000 |
| `npist2` | Net price, income $30,001-$48,000 |
| `npist3` | Net price, income $48,001-$75,000 |
| `npist4` | Net price, income $75,001-$110,000 |
| `npist5` | Net price, income $110,001+ |
| `npgrn1` | Number in net price, lowest income |
| `npgrn2` | Number in net price, second income |
| `npgrn3` | Number in net price, third income |
| `npgrn4` | Number in net price, fourth income |
| `npgrn5` | Number in net price, highest income |

### Cost Variables (from IC)

| Variable | Description |
|----------|-------------|
| `tuition2` | In-state tuition and fees |
| `tuition3` | Out-of-state tuition and fees |
| `roomamt` | Room charges |
| `boardamt` | Board charges |
| `bksupply` | Books and supplies estimate |
| `rmbrdamt` | Room and board combined |
