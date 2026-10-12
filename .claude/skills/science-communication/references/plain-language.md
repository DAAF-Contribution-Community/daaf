# Plain-Language Translation

How to communicate statistical and analytical findings in language your audience can understand. Plain language is not dumbing down — it is precise communication calibrated to the reader's vocabulary. As NIH's *Clear & Simple* guide puts it: "People with average or good reading skills appreciate messages that are conveyed simply and clearly."

This reference covers four areas: translating statistical jargon, calibrating reading level, expressing uncertainty through hedging, and choosing appropriate causal language.

## Statistical Jargon Translation Table

When writing for non-technical audiences, replace statistical terminology with accessible equivalents. The goal is to preserve meaning while removing the barrier of unfamiliar vocabulary.

| Technical Term | Plain-Language Equivalent | Notes |
|----------------|--------------------------|-------|
| Statistically significant | The difference is unlikely to be due to chance alone | Never say "significant" without context — readers assume "important" |
| p-value | How likely we'd see this result if there were really no difference | Avoid reporting exact p-values to non-technical audiences |
| p < 0.05 | We can be fairly confident this pattern is real, not just random noise | Frame as confidence, not probability |
| Confidence interval | A range of plausible values; we're [X]% confident the true value falls within this range | "Between X and Y" is often sufficient |
| 95% confidence interval | If we repeated this study 100 times, about 95 of those ranges would contain the true value | Only use this precise definition for technical audiences |
| Standard deviation | How spread out the values are; a measure of variation | "Typical spread" works for most audiences |
| Standard error | How precisely we've estimated the average | Usually omit entirely for non-technical audiences |
| Variance | How much the values differ from each other | Usually use "variation" or "spread" instead |
| Mean / average | Average (arithmetic mean); the typical value | "Average" is universally understood |
| Median | The middle value — half are above, half below | More intuitive than mean for skewed data; explain the concept |
| Percentile | Ranking relative to others; "at the 75th percentile" means scoring higher than 75% of the group | Use concrete framing: "higher than 3 out of 4" |
| Correlation | Two things tend to move together | Emphasize: "move together" does not mean one causes the other |
| Regression | A statistical method for measuring the relationship between factors while holding other factors constant | "Our analysis accounts for differences in X, Y, and Z" |
| Coefficient | The estimated relationship between two factors | "For each additional X, we see Y more/fewer Z" |
| Effect size | How big the difference actually is (not just whether it exists) | "The gap is equivalent to roughly..." with concrete comparison |
| Odds ratio | How much more (or less) likely something is in one group compared to another | "People in group A were X times as likely to..." |
| Relative risk | How much higher (or lower) the risk is in one group vs. another | Same as odds ratio for non-technical audiences |
| Hazard ratio | How much faster (or slower) one group experiences an event compared to another | "Group A experienced the event X times as fast" |
| Regression to the mean | Extreme values tend to move back toward average over time | "Unusually high (or low) results tend to bounce back" |
| Confounding variable | Another factor that could explain the apparent relationship | "There might be a hidden factor driving both patterns" |
| Omitted variable bias | Our estimate may be off because we couldn't account for an important factor | "We couldn't measure everything that matters" |
| Selection bias | The people in our study may not represent the full population | "Our sample may not reflect everyone" |
| Endogeneity | The thing we're studying and the outcome may influence each other | "The cause and effect may run in both directions" |
| Heterogeneity | The pattern differs across subgroups | "The effect isn't the same for everyone" |
| Interaction effect | The relationship between A and B changes depending on C | "The impact of A depends on C" |
| Fixed effects | Accounting for unchanging differences between groups | "After controlling for stable characteristics of each group" |
| Instrumental variable | A technique for isolating the causal effect when direct measurement is contaminated | "We used a natural experiment to separate cause from correlation" |
| Difference-in-differences | Comparing trends before and after a change, between affected and unaffected groups | "We compared how things changed for the affected group vs. a similar unaffected group" |
| Regression discontinuity | Comparing outcomes just above and below a threshold | "We compared students just above and just below the cutoff" |
| Propensity score matching | Comparing similar individuals who received different treatments | "We compared people who were similar in every measurable way except the one factor we're studying" |
| Robustness check | Testing whether our findings hold up under different assumptions | "We checked our results multiple ways and they held up" |
| Sensitivity analysis | Testing how much our conclusions depend on our assumptions | "We tested what would happen if our assumptions were wrong" |
| Power (statistical) | The ability of a study to detect a real effect if one exists | "Whether our study was large enough to detect a meaningful difference" |
| Sample size | The number of observations in the study | "We studied N people/schools/districts" |
| Weighting | Adjusting the analysis so that the sample better represents the population | "We adjusted so that our results reflect the full population" |
| Bootstrapping | A technique for estimating uncertainty by resampling the data | Usually omit entirely; say "we estimated the uncertainty" |
| Cross-validation | Testing a model on data it wasn't trained on | "We verified the model works on new data" |
| Overfitting | A model that learns noise instead of signal | "The model memorized the specific data rather than learning the general pattern" |
| Null hypothesis | The assumption that there is no real effect or difference | "The possibility that the pattern is just random noise" |
| Type I error | Concluding there's an effect when there isn't one (false positive) | "A false alarm — seeing a pattern that isn't really there" |
| Type II error | Missing a real effect (false negative) | "Missing a pattern that is actually there" |
| Multicollinearity | Predictors in the model are too closely related to each other | "Some of our factors are so closely related that we can't separate their individual effects" |

## Reading Level Guidance

NIH's *Clear & Simple* guide tells writers to "Decide on the reading level for the material" and, above all, to "make sure you write for your audience." Match complexity to the reader:

| Audience | Target Reading Level | Guidance |
|----------|---------------------|----------|
| General public (health literacy context) | 6th-8th grade | Common health-literacy target (DAAF convention) |
| General public (educated) | 9th-11th grade | Appropriate for most public-facing research communication |
| Policy audiences | 10th-12th grade | Can handle more complex sentences but not jargon |
| Academic audiences | Graduate level | Full technical vocabulary appropriate |

### Practical Reading Level Tips

Based on NIH's plain-language tips, which say sentence length "should average 15-20 words" and "each paragraph should contain only one topic" (Plain Language at NIH, archived 2012-10-14), with DAAF additions:

1. **Sentence length:** Average 15-20 words per sentence. One idea per sentence.
2. **Paragraph length:** Short paragraphs, one topic each (DAAF practice: 2-3 sentences maximum).
3. **Word choice:** Pick the familiar word over the unusual one. "Use" not "utilize." "Before" not "prior to." "About" not "pertaining to."
4. **Active voice:** "We found that X causes Y" not "It was found that Y is caused by X." Active voice clarifies who did what.
5. **Concrete over abstract:** "1 in 5 students" not "20% of the student population." Concrete examples stick; abstract percentages slide off.
6. **Define once, use consistently:** If you must introduce a technical term, define it clearly the first time, then use it consistently. Don't alternate between synonyms.

### Common Word Replacements

A DAAF list of common substitutions, selected for research communication. NIH's plain-language tips say to "Use common, everyday words" (Plain Language at NIH, archived 2012-10-14):

| Avoid | Use Instead |
|-------|-------------|
| additional | more |
| assist, assistance | help |
| commence | begin, start |
| currently | now (or omit) |
| demonstrate | show |
| determine | find, decide |
| disseminate | share, send |
| due to the fact that | because |
| endeavor | try |
| facilitate | help, ease |
| finalize | finish, complete |
| implement | carry out, start |
| in accordance with | under, per |
| in order to | to |
| in the event of | if |
| methodology | method |
| modify | change |
| necessitate | need, require |
| numerous | many |
| parameters | limits |
| pertaining to | about |
| prior to | before |
| provide | give |
| regarding | about |
| subsequent | later, next |
| sufficient | enough |
| terminate | end, stop |
| utilize | use |
| validate | confirm |
| whereas | because, since |

## Hedging Language Scale

Hedging communicates your confidence level to the reader. The challenge: too little hedging overstates your evidence; too much hedging buries the finding. Match your hedge to your inferential strength.

### Five-Level Hedging Scale

| Level | Confidence | Example Phrases | When to Use |
|-------|-----------|-----------------|-------------|
| **Very high** | Near-certain | "The evidence clearly shows..." / "We can confidently state..." / "The data demonstrate..." | Well-established findings with robust evidence from multiple independent sources or RCTs |
| **High** | Strong evidence | "The evidence strongly suggests..." / "Our analysis provides strong support for..." / "The data consistently show..." | Strong observational evidence with appropriate controls and robustness checks |
| **Moderate** | Substantial evidence | "The evidence suggests..." / "Our findings indicate..." / "The data point toward..." | Solid evidence with some limitations or caveats |
| **Low** | Preliminary evidence | "The evidence is suggestive of..." / "Preliminary findings point to..." / "There are indications that..." | Limited data, early-stage research, or important caveats that weaken conclusions |
| **Very low** | Speculative | "It is possible that..." / "One interpretation is..." / "The data are consistent with, but do not confirm..." | Exploratory findings, small samples, many competing explanations |

### Hedging Anti-Patterns

| Anti-Pattern | Problem | Better |
|--------------|---------|--------|
| "The data prove that..." | Nothing in observational research is "proven" | "The evidence strongly suggests..." |
| "It is perhaps possible that there might be some indication of a potential..." | Over-hedging buries the finding | "The evidence suggests..." |
| "We found a significant relationship..." | "Significant" means different things to technical and lay readers | "We found a [strong/meaningful/consistent] relationship..." |
| "More research is needed." (as the conclusion) | This is always true and therefore meaningless | State what you found, then note specific open questions |

## IPCC Calibrated Uncertainty Language

The Intergovernmental Panel on Climate Change developed a formal framework for expressing uncertainty. It uses two independent scales, which this guide adapts for other fields.

### Likelihood Scale (Probability of Outcome)

These terms express quantified probability (IPCC AR5 Guidance Note, Table 1). Terms marked * are AR4 terms the note allows "in the AR5 when appropriate."

| Term | Probability Range |
|------|-------------------|
| Virtually certain | 99-100% |
| Extremely likely* | 95-100% |
| Very likely | 90-100% |
| Likely | 66-100% |
| More likely than not* | >50-100% |
| About as likely as not | 33-66% |
| Unlikely | 0-33% |
| Very unlikely | 0-10% |
| Extremely unlikely* | 0-5% |
| Exceptionally unlikely | 0-1% |

**Key design features:**
- The ranges are nested, not mutually exclusive: "very likely" (90-100%) is a subset of "likely" (66-100%), and the scale mirrors around 50% ("likely" 66-100%, "unlikely" 0-33%)
- Boundaries are "fuzzy," and "about as likely as not" (33-66%) "should not be used to express a lack of knowledge"
- Readers "may adjust their interpretation of this likelihood language according to the magnitude of perceived potential consequences," so pair calibrated terms with the number

### Confidence Scale (Epistemic Quality)

Confidence synthesizes the author team's judgment about a finding's validity from **evidence** ("limited," "medium," "robust") and **agreement** ("low," "medium," "high"), using five qualifiers: very low, low, medium, high, very high. Confidence rises with evidence and agreement, but the mapping is deliberately flexible: "for a given evidence and agreement statement, different confidence levels could be assigned." "Confidence should not be interpreted probabilistically." For low agreement and limited evidence, report the evidence and agreement terms instead of a confidence level.

### Using Both Scales Together

Confidence certifies the epistemic quality of the assessment; likelihood communicates the probability. They can be stacked: "It is *very likely* (high confidence) that X is occurring." When a likelihood is given, the IPCC does not require stating confidence if it is high or very high.

**Decision rule:** Use likelihood terms only when confidence is high or very high. Expressing a precise probability for a finding with low confidence creates false precision.

### Adapting for Non-Climate Research

While the IPCC framework was designed for climate science, its two-dimensional approach (probability + confidence) is valuable for any research communication that needs to express uncertainty clearly:

- **For policy audiences:** Use the likelihood terms directly (they're intuitive) and translate confidence as "strength of evidence"
- **For general audiences:** Map to everyday language: "very likely" → "the evidence strongly points to..."; "about as likely as not" → "the chances are roughly even." When evidence is thin or conflicting, say that instead ("the evidence is limited," "studies disagree"); that is a confidence judgment, not a likelihood
- **For academic audiences:** Use the framework as a supplement to standard statistical reporting

## Causal vs. Correlational Language

Choosing the right linking language is one of the most consequential decisions in research communication. The wrong word can either overstate your evidence (implying causation from correlation) or understate it (hedging a well-identified causal effect into meaninglessness).

This section is the lay- and policy-audience guide. It translates the same evidence ladder that the `academic-manuscript` skill applies to journal articles (claim tiers T0–T3, M, and A in `academic-manuscript/references/claims-ledger-and-coherence.md` § Language tiers; the reasoning is in `academic-manuscript/references/honest-interpretation.md` § Causal-language calibration). When you write a manuscript, use those tiers. When you write a plain-language summary or policy brief from a manuscript, keep every claim at or below the tier the manuscript assigned it.

### The Core Distinction

A causal claim answers two questions: *did X change Y*, and *for whom*. Every design that earns causal language also limits whose effect it measures (the estimand). Say that scope in plain words, because lay readers will otherwise assume the effect applies to everyone.

| Study Design | What You Can Claim | Whose Effect (Scope to State) | Appropriate Language |
|--------------|-------------------|-------------------------------|---------------------|
| Randomized controlled trial (RCT), low attrition | Causal effect (manuscript tier T3) | The trial population. Separate the effect of *offering* the program from the effect of *receiving* it | "X increased Y" / "X reduced Y" / "The program raised attendance by 3 points among participating schools" |
| Difference-in-differences / event study | Causal effect under the parallel-trends assumption (T2) | The units or cohorts that were actually treated (ATT), not all units | "Comparing changes in adopting and non-adopting districts, we estimate the policy reduced chronic absence by 2 points *in the districts that adopted it*" |
| Regression discontinuity | Causal effect under the assumption that units could not precisely sort themselves around the cutoff (T2) | Units near the cutoff only (a local effect) | "For students who scored just above versus just below the cutoff, the program raised…" |
| Instrumental variables / fuzzy RD | Causal effect under instrument validity (T2) | Only "compliers": units whose participation was changed by the instrument (LATE) | "For families whose enrollment depended on the lottery, attending the school raised…" |
| Matching / regression adjustment (selection-on-observables) | Causal effect **only if** the analysis declared a causal estimand, named the no-unmeasured-confounding assumption, and reported a sensitivity analysis for unmeasured confounding (T2). Otherwise association (T1) | Treated units (ATT) or the whole population (ATE), as declared | With all three conditions: "Assuming we have accounted for every important difference between the groups (our sensitivity analysis suggests…), X is estimated to have raised Y." Without them: "X is associated with Y" |
| Observational with controls, no declared causal estimand | Association only (T1) | The conditional association in the sample | "X is associated with Y," paired with an explicit statement that the analysis does not show X causes Y |
| Cross-sectional correlation | Association only (T1) | The sample at one point in time | "X and Y tend to occur together" / "X correlates with Y" |
| Descriptive tabulation | Description (T0) | The population and period described | "Y is higher among…" / "Y declined from … to …" |

### Linking Language Spectrum

The tiers below are a DAAF grouping informed by Haber et al. (2022), not their scale. Their 47 reviewers' ratings of linking-word roots were "highly heterogeneous"; only "cause" reached near consensus, and "correlate" and "associate" rated weaker than "impact," "effect," "affect," and "prevent." Treat the tiers as rough guidance, ordered from strongest to weakest causal implication:

| Causal Strength | Linking Words | Appropriate For |
|----------------|---------------|-----------------|
| **Strong causal** | causes, produces, leads to, results in, prevents, affects, impacts | RCTs (T3); quasi-experiments (T2) only with the design, named assumption, and scope in the same sentence or paragraph |
| **Moderate causal** | increases, reduces, improves, influences | Quasi-experimental designs and qualifying selection-on-observables analyses (T2), with explicit design disclosure and estimand scope |
| **Weak causal / ambiguous** | contributes to, is a factor in, is a determinant of, explains | Not a safe hedge: these words still give X a causal role. Use only where the design earns causal language (T2 or higher) |
| **Predictive** | predicts, forecasts, discriminates between | Prediction models and associational analyses (T1); make clear that prediction is not causation |
| **Associational** | is associated with, is related to, is linked to, correlates with | Observational studies without a declared causal estimand (T1), *paired with* an explicit non-causal statement, because over half of Haber et al.'s reviewers read "association" as at least somewhat causal |
| **Descriptive** | differs between, is higher among, varies across | Descriptive comparisons without causal intent (T0); fits any design. Context matters: "lower"/"higher" can read as causal ("X lowered Y") |

### The "Schrödinger's Causal Inference" Problem

Haber et al. (2022) found that what they call "Schrödinger's causal inference" (studies that "avoid stating (or even explicitly deny) an interest in estimating causal effects yet are otherwise embedded with causal intent, inference, implications, and recommendations") is common in observational health research. In a typical (hypothetical) case, the results say X was associated with Y and the conclusion says clinicians should consider X to reduce Y. The causal claim simultaneously exists and doesn't exist depending on which paragraph you read.

**Prevention:** Ensure that the strength of language in your recommendations does not exceed the strength of language in your findings. If you found an "association," your recommendation should say "further investigation is warranted" — not "policymakers should adopt X." Among observational studies in 18 high-profile health journals whose abstracts made an action recommendation, Haber et al. found that 44.5% made a recommendation that implied causality more strongly than the abstract's linking sentence.

### Mechanism and Recommendation Rules

**Recommendation strength never exceeds claim strength.** A recommendation is itself a causal claim: "districts should adopt X" assumes adopting X would change the outcome.

| Supporting evidence | Recommendation you can make | Example |
|---------------------|-----------------------------|---------|
| Descriptive or associational (T0/T1) | Non-causal actions only: monitor, target attention, investigate, evaluate | "These patterns warrant a rigorous evaluation of four-day weeks before further expansion" |
| Causal, at least conditional (T2/T3), on the same outcome and population | Adoption, expansion, or discontinuation, scoped to the population the estimate covers, with cost and scalability addressed | "For districts like those studied, adopting X is likely to reduce Y; at about $Z per student, it compares favorably with…" |

A recommendation also inherits the estimand's scope. A DiD estimate for early-adopting districts, or an RD estimate for students near a cutoff, does not by itself justify a recommendation for every district or every student.

**Mechanism words need a mechanism design.** "Because," "through," "driven by," and "operates via" claim to know *how* an effect happens. That requires a formal mediation analysis with stated assumptions (manuscript tier M). Without one, present the mechanism as an explicitly labeled hypothesis: "One possible explanation, which this analysis cannot test, is reduced instructional time." The same applies to "If this association is causal, it would suggest…": the frame must read as speculation.

### Practical Causal Language Rules

1. **Declare what you are estimating, then match the language to it.** Haber et al. (2022) concluded that their research "undercuts the assumption that avoiding 'causal' words leads to clarity of interpretation in medical research," and recommend that research "clearly state its target estimand … including explicitly stating when such estimands are causal." Hernán (2018) and Dahabreh and Bibbins-Domingo's 2024 *JAMA* framework for causal language in observational studies take the same position: being explicit about the causal question and its assumptions beats euphemism. So when no causal estimand is declared, use associational or descriptive language *and* say outright that the analysis does not show cause ("This analysis describes how X and Y move together; it does not show that X causes Y"). When a causal estimand is declared and the design supports it, use the causal language the Core Distinction table allows, with its scope.

2. **State the study design when using causal language.** "Our difference-in-differences analysis shows that the policy *reduced* dropout rates by 4 percentage points" is honest because it names the design. "The policy *reduced* dropout rates" without design context invites misinterpretation.

3. **Separate findings from implications.** Use causal language in findings only if the design warrants it. In the implications section, you can discuss causal *possibilities* with appropriate hedging: "If this association is causal, it would suggest..."

4. **Watch for direction-of-causation assumptions.** "Poverty affects test scores" assumes a direction. "Poverty is associated with lower test scores" is neutral about the direction. Only claim directionality if your design supports it.

5. **Avoid "weasel causality."** Words like "impact," "influence," and "affect" are verbs that imply the exposure *did something* to the outcome — they are causal in ordinary English even if the writer thinks they're being cautious. If your design does not earn causal language (see the Core Distinction table), these words overclaim.

6. **State whose effect it is.** Name the scope the design supports in plain words: "in the districts that adopted the policy," "for students near the cutoff," "for families whose enrollment depended on the lottery." Dropping the scope in a summary turns a local estimate into a universal claim.

7. **Never let a word list substitute for clear thinking.** Haber et al. (2022) found reviewers' ratings of individual linking words "highly heterogeneous." The same word can also read differently in context ("people with X had lower Y" versus "X lowered Y"). Rather than "policing which words we use," they recommend focusing on how researchers, research consumers, and reviewers "can better identify and assess causal inference study designs and assumptions." The solution is structural transparency about your design and estimand, not vocabulary restrictions.

## Number Formatting Standards

How you present numbers affects comprehension as much as how you present words. Match formatting to the audience.

### General Rules

| Guideline | Example | Rationale |
|-----------|---------|-----------|
| **Round aggressively for non-technical audiences** | "About 14 percentage points" not "13.7 percentage points" | False precision distracts; rounded numbers are easier to remember |
| **Use natural frequencies over percentages for general audiences** | "1 in 5 students" not "20% of students" | Natural frequencies are processed faster and remembered longer |
| **Use percentages for technical audiences** | "20.3% (95% CI: 18.1-22.5)" | Technical readers expect precision |
| **Abbreviate large numbers** | "$14M" or "$14 million" not "$14,000,000" | Readers process abbreviated forms faster |
| **Provide baselines for differences** | "Scores rose by 14 points, from 52% to 66%" | A difference without a baseline is uninterpretable |
| **Use absolute AND relative comparisons together** | "3x more likely (15% vs. 5%)" | Relative comparisons alone can mislead: "3x more likely" sounds dramatic but may mean 0.3% vs 0.1% |
| **Avoid decimal places for general audiences** | "About 3 in 10" not "29.7%" | Decimal places imply false precision for lay readers |
| **Use consistent formatting within a deliverable** | Don't switch between "20%", "one-fifth", and "1 in 5" for the same quantity | Inconsistency creates confusion about whether these are different numbers |

### Framing Effects to Watch

The same number can feel very different depending on how it is framed:

| Framing | Example | Perception |
|---------|---------|------------|
| Relative risk (high anchor) | "3x more likely to drop out" | Alarming — emphasizes the multiplier |
| Absolute risk | "15% vs. 5% dropout rate" | More measured — shows actual rates |
| Natural frequency | "15 out of every 100 students" | Most intuitive for general audiences |
| Inverted frame | "85% of students completed" vs. "15% dropped out" | Same data, different emotional impact — choose deliberately |

**Rule of thumb:** Present both absolute and relative comparisons when the finding is important. Lead with whichever framing is most appropriate for your audience and purpose, but always include the other for context.

## Domain-Specific Jargon

The jargon translation table above covers statistical and methodological terms. However, every research domain has its own specialized vocabulary (e.g., "Title I," "FRPL eligibility," "AYP" in education; "incidence," "comorbidity," "morbidity" in public health).

**Guidance for domain-specific translation:** When working with a specific data domain, consult the relevant domain skill (e.g., `education-data-context`, `education-data-source-ccd`) for the authoritative definitions and caveats of domain-specific terms. Then apply the same plain-language translation principles from this file: replace with familiar equivalents, define on first use, and provide concrete examples.

The jargon translation table in this file is deliberately domain-agnostic — it handles the statistical and analytical language that appears in *every* research project. Domain-specific translation is handled by domain skills to avoid duplication and ensure accuracy.

## References and Further Reading

Dahabreh, I.J. & Bibbins-Domingo, K. (2024). "Causal Inference About the Effects of Interventions From Observational Studies in Medical Journals." *JAMA*, 331(21), 1845-1853. https://doi.org/10.1001/jama.2024.7741

Haber, N.A. et al. (2022). "Causal and Associational Language in Observational Health Research: A Systematic Evaluation." *American Journal of Epidemiology*, 191(12), 2084-2097. https://doi.org/10.1093/aje/kwac137

Hernán, M.A. (2018). "The C-Word: Scientific Euphemisms Do Not Improve Causal Inference From Observational Data." *American Journal of Public Health*, 108(5), 616-619. https://doi.org/10.2105/AJPH.2018.304337

NIH. "Plain Language at NIH." https://www.nih.gov/institutes-nih/nih-office-director/office-communications-public-liaison/clear-communication/plain-language-nih (2012 version archived at https://webarchive.library.unt.edu/web/20121014050319/http://www.nih.gov/clearcommunication/plainlanguage.htm)

NIH. "Clear & Simple." https://www.nih.gov/institutes-nih/nih-office-director/office-communications-public-liaison/clear-communication/clear-simple (archived 2024-01-11)

Federal Plain Language Guidelines (now Digital.gov plain language guides). https://digital.gov/guides/plain-language

Mastrandrea, M.D., Field, C.B., Stocker, T.F., et al. (2010). "Guidance Note for Lead Authors of the IPCC Fifth Assessment Report on Consistent Treatment of Uncertainties." IPCC. https://www.ipcc.ch/site/assets/uploads/2017/08/AR5_Uncertainty_Guidance_Note.pdf

Mastrandrea, M.D. et al. (2011). "The IPCC AR5 Guidance Note on Consistent Treatment of Uncertainties: A Common Approach Across the Working Groups." *Climatic Change*, 108(4), 675-691. https://doi.org/10.1007/s10584-011-0178-6
