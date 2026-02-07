# Title IV Federal Student Aid Programs

Comprehensive reference for federal student aid programs authorized under Title IV of the Higher Education Act (HEA) of 1965, as amended.

## Contents

- [Overview](#overview)
- [Federal Pell Grant Program](#federal-pell-grant-program)
- [William D. Ford Federal Direct Loan Program](#william-d-ford-federal-direct-loan-program)
- [Campus-Based Programs](#campus-based-programs)
- [Program Comparison](#program-comparison)
- [Eligibility Requirements](#eligibility-requirements)

## Overview

Title IV programs are the largest source of federal student aid, providing grants, loans, and work-study funds to eligible students attending participating postsecondary institutions. The Department of Education's Office of Federal Student Aid (FSA) administers these programs.

### Title IV Program Categories

| Category | Programs | Funding Mechanism |
|----------|----------|-------------------|
| Grant Programs | Pell Grant, FSEOG, TEACH Grant, Iraq/Afghanistan Service Grant | Direct appropriation |
| Loan Programs | Direct Subsidized, Direct Unsubsidized, Parent PLUS, Grad PLUS | Federal lending |
| Campus-Based | Federal Work-Study, FSEOG, Perkins (discontinued) | Institutional allocation |

### Key Legislative Authority

- Higher Education Act of 1965 (HEA), Title IV
- FAFSA Simplification Act (part of Consolidated Appropriations Act, 2021)
- Student Aid Index (SAI) replaced Expected Family Contribution (EFC) in 2024-25

## Federal Pell Grant Program

The largest federal grant program providing need-based aid to undergraduate students.

### Program Characteristics

| Attribute | Description |
|-----------|-------------|
| **Type** | Need-based grant (does not require repayment) |
| **Eligibility** | Undergraduate students with demonstrated financial need |
| **Maximum Award (2025-26)** | $7,395 |
| **Minimum Award (2025-26)** | 10% of maximum (~$739) |
| **Lifetime Eligibility** | 12 full-time semesters (600% Lifetime Eligibility Used) |
| **Portability** | Follows student to any Title IV institution |

### Pell Grant Calculation

The Pell Grant Scheduled Award depends on:

1. **Student Aid Index (SAI)**: Measure of family financial strength
2. **Cost of Attendance (COA)**: Institutional cost for full academic year
3. **Enrollment Intensity**: Full-time, 3/4-time, half-time, or less-than-half-time
4. **Academic Year Structure**: Semesters, quarters, clock hours

**Maximum SAI for Pell eligibility (2025-26)**: $6,655 for full-time students

### Pell Grant Award Calculation Table

| Enrollment Status | Percentage of Scheduled Award |
|-------------------|-------------------------------|
| Full-time (12+ credits) | 100% |
| Three-quarter time (9-11 credits) | 75% |
| Half-time (6-8 credits) | 50% |
| Less than half-time (<6 credits) | 25-50% (varies) |

### Special Pell Provisions

- **Year-Round Pell**: Students may receive up to 150% of scheduled award in one award year
- **Automatic Zero SAI**: Students meeting federal poverty thresholds receive maximum Pell
- **Minimum Pell eligibility**: Students with SAI at or below threshold qualify regardless of COA

### FSA Data Variables for Pell Grants

In the Education Data Portal `/fsa/grants/` endpoint:

| Variable | Description |
|----------|-------------|
| `pell_recipients` | Number of Pell Grant recipients |
| `pell_disbursements` | Total Pell Grant disbursements ($) |
| `pell_avg_amount` | Average Pell Grant per recipient ($) |

## William D. Ford Federal Direct Loan Program

The federal government is the direct lender for all loans in this program.

### Direct Subsidized Loans

| Attribute | Description |
|-----------|-------------|
| **Type** | Need-based loan with interest subsidy |
| **Eligibility** | Undergraduate students with financial need |
| **Interest Subsidy** | Government pays interest while in school, grace period, and deferment |
| **Interest Rate (2025-26)** | 6.53% (fixed) |
| **Origination Fee** | 1.057% |

**Annual Limits by Grade Level:**

| Grade Level | Annual Limit |
|-------------|--------------|
| Freshman (0-29 credits) | $3,500 |
| Sophomore (30-59 credits) | $4,500 |
| Junior/Senior (60+ credits) | $5,500 |

**Aggregate Limit**: $23,000 (subsidized only)

### Direct Unsubsidized Loans

| Attribute | Description |
|-----------|-------------|
| **Type** | Non-need-based loan |
| **Eligibility** | All enrolled students (undergrad, grad, professional) |
| **Interest Subsidy** | None - interest accrues from disbursement |
| **Interest Rate - Undergrad (2025-26)** | 6.53% (fixed) |
| **Interest Rate - Graduate (2025-26)** | 8.08% (fixed) |
| **Origination Fee** | 1.057% |

**Annual Limits (Dependent Undergraduates):**

| Grade Level | Subsidized | Unsubsidized | Total |
|-------------|------------|--------------|-------|
| Freshman | $3,500 | $2,000 | $5,500 |
| Sophomore | $4,500 | $2,000 | $6,500 |
| Junior/Senior | $5,500 | $2,000 | $7,500 |

**Annual Limits (Independent Undergraduates):**

| Grade Level | Subsidized | Additional Unsub | Total |
|-------------|------------|------------------|-------|
| Freshman | $3,500 | $6,000 | $9,500 |
| Sophomore | $4,500 | $6,000 | $10,500 |
| Junior/Senior | $5,500 | $7,000 | $12,500 |

**Graduate/Professional Student Limits:**

- Annual: $20,500 (all unsubsidized)
- Aggregate: $138,500 (includes undergraduate borrowing)

### Direct PLUS Loans

| Attribute | Parent PLUS | Graduate/Professional PLUS |
|-----------|-------------|---------------------------|
| **Borrower** | Parent of dependent undergraduate | Graduate/professional student |
| **Credit Check** | Required | Required |
| **Interest Rate (2025-26)** | 9.08% (fixed) | 9.08% (fixed) |
| **Origination Fee** | 4.228% | 4.228% |
| **Annual Limit** | Cost of attendance minus other aid | Cost of attendance minus other aid |
| **Aggregate Limit** | None | None |

**Credit Requirements:**
- No adverse credit history (90+ day delinquency, bankruptcy, foreclosure, etc.)
- Endorser option if borrower has adverse credit
- Credit counseling required if approved despite adverse credit

### FSA Data Variables for Loans

In the Education Data Portal `/fsa/loans/` endpoint:

| Variable | Description |
|----------|-------------|
| `dl_sub_recipients` | Direct Subsidized Loan recipients |
| `dl_sub_disbursements` | Direct Subsidized Loan disbursements ($) |
| `dl_unsub_recipients` | Direct Unsubsidized Loan recipients |
| `dl_unsub_disbursements` | Direct Unsubsidized Loan disbursements ($) |
| `dl_parent_plus_recipients` | Parent PLUS Loan recipients |
| `dl_parent_plus_disbursements` | Parent PLUS disbursements ($) |
| `dl_grad_plus_recipients` | Grad PLUS Loan recipients |
| `dl_grad_plus_disbursements` | Grad PLUS disbursements ($) |

## Campus-Based Programs

These programs provide funds directly to institutions, which then award aid to eligible students.

### Federal Supplemental Educational Opportunity Grant (FSEOG)

| Attribute | Description |
|-----------|-------------|
| **Type** | Need-based grant |
| **Eligibility** | Undergraduates with exceptional financial need (Pell-first priority) |
| **Award Range** | $100 to $4,000 per year |
| **Funding** | Limited institutional allocation |
| **Matching** | 25% institutional match required |

**Priority**: Schools must award FSEOG first to students with lowest SAI who are Pell-eligible.

### Federal Work-Study (FWS)

| Attribute | Description |
|-----------|-------------|
| **Type** | Employment program |
| **Eligibility** | Students with financial need |
| **Earnings** | At least federal minimum wage |
| **Hours** | Vary; cannot exceed student's financial need |
| **Matching** | 25% employer match (some exceptions) |

**Employment Types:**
- On-campus employment
- Off-campus community service positions
- Off-campus employment with federal, state, or local agencies
- Literacy tutoring
- America Reads/America Counts

**Special Requirements:**
- 7% of allocation for community service
- 7% of allocation for literacy activities (if offering reading tutors)

### Federal Perkins Loan (Discontinued)

| Attribute | Description |
|-----------|-------------|
| **Type** | Need-based, campus-based loan |
| **Status** | No new loans after September 30, 2017 |
| **Interest Rate** | 5% (fixed) |
| **Annual Limit (was)** | $5,500 undergrad / $8,000 grad |
| **Current Status** | Wind-down and servicing only |

**Note**: While no new Perkins Loans can be made, institutions continue to collect on outstanding loans and FSA data may include historical Perkins data.

### FSA Data Variables for Campus-Based Programs

In the Education Data Portal `/fsa/campus-based-volume/` endpoint:

| Variable | Description |
|----------|-------------|
| `fws_allocation` | Federal Work-Study federal allocation ($) |
| `fws_recipients` | FWS recipients |
| `fws_disbursements` | FWS disbursements ($) |
| `fseog_allocation` | FSEOG federal allocation ($) |
| `fseog_recipients` | FSEOG recipients |
| `fseog_disbursements` | FSEOG disbursements ($) |
| `perkins_allocation` | Perkins Loan allocation ($) |
| `perkins_recipients` | Perkins Loan recipients |
| `perkins_disbursements` | Perkins Loan disbursements ($) |

## Program Comparison

### Grant Programs

| Program | Need-Based | Max Amount | Repayment |
|---------|------------|------------|-----------|
| Federal Pell Grant | Yes | $7,395 | No |
| FSEOG | Yes (exceptional) | $4,000 | No |
| TEACH Grant | Service-based | $4,000 | Converts to loan if service not completed |

### Loan Programs

| Program | Need-Based | Interest Rate (2025-26) | Interest Subsidy |
|---------|------------|------------------------|------------------|
| Direct Subsidized | Yes | 6.53% | Yes (in school/grace/deferment) |
| Direct Unsubsidized | No | 6.53% (UG) / 8.08% (Grad) | No |
| Parent PLUS | No (credit-based) | 9.08% | No |
| Grad PLUS | No (credit-based) | 9.08% | No |

### Historical Loan Interest Rates

| Loan Type | 2020-21 | 2021-22 | 2022-23 | 2023-24 | 2024-25 |
|-----------|---------|---------|---------|---------|---------|
| Direct Subsidized/Unsub (UG) | 2.75% | 3.73% | 4.99% | 5.50% | 6.53% |
| Direct Unsubsidized (Grad) | 4.30% | 5.28% | 6.54% | 7.05% | 8.08% |
| PLUS (Parent/Grad) | 5.30% | 6.28% | 7.54% | 8.05% | 9.08% |

## Eligibility Requirements

### General Title IV Eligibility (Students)

All Title IV programs require students to:

1. Be a U.S. citizen, national, or eligible noncitizen
2. Have a valid Social Security number
3. Be registered with Selective Service (if male, 18-25)
4. Be enrolled in an eligible program at a participating school
5. Maintain satisfactory academic progress (SAP)
6. Not be in default on federal student loans
7. Not owe a refund on federal grants
8. Complete the FAFSA annually

### Institutional Participation Requirements

To participate in Title IV programs, institutions must:

1. Be accredited by a recognized accrediting agency
2. Be authorized to operate by the state
3. Sign a Program Participation Agreement (PPA) with ED
4. Demonstrate administrative capability
5. Demonstrate financial responsibility
6. Meet program-specific requirements

### Program-Specific Eligibility

| Program | Additional Requirements |
|---------|------------------------|
| Pell Grant | Undergraduate only; no prior bachelor's degree; SAI within threshold |
| Direct Subsidized | Undergraduate only; demonstrated financial need |
| Direct Unsubsidized | No additional need requirement |
| Parent PLUS | Parent of dependent undergrad; no adverse credit history |
| Grad PLUS | Graduate/professional student; no adverse credit history |
| FSEOG | Exceptional financial need; Pell-eligible priority |
| FWS | Demonstrated financial need; U.S. citizen/eligible noncitizen |
