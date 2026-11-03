# Measurement from Text with Model-Based Annotators

Methodological guidance for turning open-ended text (survey responses, documents, comments, transcripts) into analysis variables (categorical codes, ordinal ratings, or yes/no features) with a *model-based annotator*. That covers a generative large language model (LLM) prompted to code text, a typed-judgment API that returns probabilities over a fixed option set (e.g., Typesafe's Jev), and a supervised classifier trained on hand-coded examples. This file covers the *measurement* and *inference* questions, which are the same whichever annotator you use: what you are measuring, how to validate it against human coders, what goes wrong when the codes become variables, how to keep the result reproducible, and what may and may not be sent to a third party. It is vendor-neutral and code-agnostic. When a specific tool enters the discussion, in advice or in code, load its skill (§ 10).

**When to read this file:** Any task that codes, classifies, rates, or screens free text with a model so the result can be counted, compared, or used in a regression. Typical requests: "code these open-ended responses", "classify these documents", "use an LLM to label", "rate each comment for X", "use Typesafe/Jev to tag". Read it *before* designing the instrument, because most of the decisions below (gold-set sampling, dev/test separation, what to persist) cannot be repaired after the run.

**Relationship to other references:**
- For training and evaluating a supervised text classifier (cross-validation, baselines, metric choice, calibration tooling), see `./supervised-ml.md`. That file covers the *classifier*; this one covers the classifier's output used *as a measurement*.
- For the classify-analyze problem with cluster and latent-class labels, see `./exploratory-unsupervised.md` > "The Classify-Analyze Problem". § 6 below extends it to model-produced labels.
- For coefficient interpretation, standard errors, and robustness checks once the variable exists, see `./statistical-modeling.md`.
- For DAAF's AI-use disclosure conventions (GUIDE-LLM mapping), see `agent_reference/AI_DISCLOSURE_REFERENCE.md`.

**Evidence convention.** An author–year citation means the specialists who compiled this file's evidence base confirmed the claim in that source's text or abstract. Exceptions: Cohen (1960, 1968), Fleiss (1971), and Brier (1950) are cited as the originating sources of named coefficients and were not read; Neuendorf (2017) is cited from its table of contents. Sentences phrased as reasoning ("this suggests", "a reasonable check is", or marked *Reasoning:*) are the authors' synthesis and carry no citation. This file deliberately gives no accuracy figures, cost figures, or benchmark results. Performance is task- and data-dependent (§ 1), so any number borrowed from another study would mislead. The only numbers quoted are methodological conventions, attributed to their sources.

## Contents

- [Quick Task Lookup](#quick-task-lookup)
- [1. Scope: When Model-Based Annotation Fits](#1-scope-when-model-based-annotation-fits)
- [2. Annotation Is Measurement](#2-annotation-is-measurement)
- [3. Human-Coded Validation Sets](#3-human-coded-validation-sets)
- [4. Agreement and Accuracy Metrics](#4-agreement-and-accuracy-metrics)
- [5. LLM-Specific Validation Checks](#5-llm-specific-validation-checks)
- [6. Using Annotations as Variables Downstream](#6-using-annotations-as-variables-downstream)
- [7. Reproducibility with Hosted Models](#7-reproducibility-with-hosted-models)
- [8. Data Governance](#8-data-governance)
- [9. What to Report](#9-what-to-report)
- [10. Tools in DAAF](#10-tools-in-daaf)
- [11. Open Questions in the Literature](#11-open-questions-in-the-literature)
- [References](#references)

## Quick Task Lookup

| If the plan says... | Read this section |
|---------------------|-------------------|
| "should we use an LLM / API / classifier / hand coding?" | § 1 Scope |
| "write a codebook," "define the categories," "prompt design" | § 2 Annotation Is Measurement |
| "gold standard," "validation set," "how many to hand-code" | § 3 Human-Coded Validation Sets |
| "inter-rater reliability," "kappa," "alpha," "F1" | § 4 Agreement and Accuracy Metrics |
| "prompt sensitivity," "option order," "model version" | § 5 LLM-Specific Validation Checks |
| "use the codes in a regression," "estimate prevalence," "correct for misclassification" | § 6 Using Annotations as Variables |
| "use the probabilities," "calibration" | § 6.4–6.5 |
| "pin the model," "rerun later," "archive the outputs" | § 7 Reproducibility |
| "is it OK to send this text to the API?" "FERPA," "IRB," "PII" | § 8 Data Governance |
| "methods section," "disclosure," "what to report" | § 9 What to Report |

---

## 1. Scope: When Model-Based Annotation Fits

### Three ways to get codes from text

| Approach | What it needs | Main strength | Main cost or risk |
|----------|---------------|---------------|-------------------|
| **Human coding only** | Codebook, trained coders, reliability sample | The reference against which automated coding is validated (§ 3) | Labor; impractical for large corpora |
| **Trained supervised classifier** (e.g., regularized logistic regression on text features, fine-tuned model) | A hand-coded *training* set plus a separate test set | Fully under your control; versionable; runs locally | Needs enough labeled examples per class; see `./supervised-ml.md` |
| **Model-based annotator without task-specific training** (zero/few-shot LLM; typed-judgment API) | A codebook written as model instructions, plus a hand-coded *validation* set | Little or no training data; fast to iterate | Hosted models change and can be retired (§ 7); sends text to a third party (§ 8); systematic errors that accuracy metrics can hide (§ 6) |

Every row needs human-coded text. What changes is what the human labels are *for*: training, validation, or (§ 6) bias correction. Grimmer and Stewart (2013) put it plainly: automated methods "are no substitute for careful thought and close reading and require extensive and problem-specific validation."

### No blanket claims of superiority

The literature does not support a general ranking of model-based annotators against human coders or trained classifiers:

- Favorable findings exist. Gilardi et al. (2023) report ChatGPT outperforming crowd workers on several annotation tasks. Mellon et al. (2024), coding open-text survey responses, report that the best-performing LLM neared human performance when no training data were available. Ornstein et al. (2025) report performance comparable to expert and crowd coding.
- So do mixed and unfavorable ones. Ziems et al. (2024) find LLMs "fail to outperform the best fine-tuned models but still achieve fair levels of agreement with humans" and recommend them as members "on human annotation teams". Halterman and Keith (2025) find open-weight models limited in following codebooks zero-shot. Reiss (2023) concludes that "unsupervised application … is not recommended."
- Pangakis et al. (2023) find performance "highly contingent on both the dataset and the type of annotation task", varying even across tasks within one dataset. They argue that because these challenges "will persist even as LLM technology improves," validation is always required, and that, given rapid LLM development, binary judgments of LLM competence "will be quickly outdated."

**The shared conclusion:** a favorable result from someone else's task, dataset, model version, or vendor evaluation does not substitute for validating your own task (Pangakis et al., 2023; Törnberg, 2024). Present the three approaches to the user as options with trade-offs, not as a ranking.

### Choosing among them (reasoning, not a sourced rule)

```
How should the codes be produced?
├─ Small corpus, or a construct that needs expert judgment and close reading
│   └─ Human coding (the validation machinery in §§ 2–4 still applies)
├─ Large corpus, labeled examples available or affordable for every class
│   └─ Trained classifier is a strong candidate — locally versionable,
│       no third-party disclosure → ./supervised-ml.md
├─ Large corpus, few labels, construct expressible as explicit instructions
│   └─ Model-based annotator is a candidate — but it still needs a
│       human-coded validation set (§ 3), and § 7–8 constraints apply
└─ Text is sensitive or governed (PII, student records, health data)
    └─ Resolve § 8 FIRST: the governance answer can rule out hosted
        annotators entirely, whatever their accuracy
```

Running two approaches and comparing them on the same held-out human codes is often the most informative design. A simple trained baseline gives the model-based annotator something concrete to beat.

---

## 2. Annotation Is Measurement

### The label is an operationalization of a construct

A model-assigned code is a measurement of a concept, so it needs construct validation, not only an accuracy score. Adcock and Collier (2001) stress "the need to draw a clear distinction between measurement issues and disputes about concepts" and "the contextual specificity of measurement claims." Jacobs and Wallach (2021) note that operationalization "introduces the potential for mismatches between the theoretical understanding of the construct purported to be measured and its operationalization," and frame the evaluation in terms of construct reliability and construct validity. Grimmer et al. (2022) organize text-as-data research around representation, discovery, measurement, prediction, and causal inference. Annotation for analysis variables sits under *measurement*.

### The codebook is the instrument

For a model-based annotator, the codebook *is* the model's instructions, and the option definitions are its criteria.

- Pangakis et al. (2023): "both the human coders and the LLM should use the same codebook for annotation, where the codebook serves as the LLM's prompt instructions."
- Törnberg (2024) recommends a "prompt codebook" with "clear definitions of the coding categories, examples of text corresponding to each category, and instructions on how to handle ambiguous cases." He also notes that "it is usually beneficial to provide separate instructions" for humans and the model. The two sources differ in emphasis here (§ 11). At minimum, develop the human and model versions together and keep them consistent.
- Halterman and Keith (2025) propose a framework that begins with "preparing a codebook for both humans and LLMs." Its components include class definitions, "Clarification & Negative Clarification" (what does *not* belong), and positive and negative examples. In their ablations, removing components lowered zero-shot performance.

### Category design

| Requirement | Why (reasoning) | Source |
|-------------|-----|--------|
| **Exhaustive** categories | Every unit must have a valid code | Operationalization requirements listed in Neuendorf (2017) |
| **Mutually exclusive** categories (for single-label codes) | A unit should fit exactly one code | Neuendorf (2017) |
| **Appropriate level of measurement** (nominal vs ordinal vs yes/no) | Determines which agreement metric and downstream model are valid (§ 4) | Neuendorf (2017) |
| **An explicit "I don't know" / abstention option** | Reduces "the risk of stochastic answers" | Törnberg (2024) |

**Residual "other" vs. abstention, which are different things.** *Reasoning:* a substantive residual option ("other: the response is about something not in this list") is a code; an abstention option ("uncertain / cannot tell from the text") is a non-code. They mean different things downstream: "other" is a category whose prevalence you may report, while abstentions are missing data whose pattern you must characterize. Define each in the codebook, and report how often each is used in validation and in the full run. This distinction is the compilers' reasoning, not a rule found in the sources.

### Define the concept before you see model output

Törnberg (2024) advises coming "in with an explicitly articulated idea of the concept … to avoid being overly influenced by the interpretations of the LLM." Halterman and Keith (2025) caution that if codebook constructs "deviate too far from the background concepts an LLM has learned during pretraining, the zero-shot results may have systematic errors." Write and freeze the definitions first, then look at what the model does with them.

**Codebook checklist**
- [ ] Construct stated in one or two sentences, independent of any model
- [ ] Each category defined, with what does *not* belong (negative clarification) and boundary cases
- [ ] Positive and negative examples, drawn from the development set only (§ 3)
- [ ] Categories exhaustive and mutually exclusive; level of measurement stated
- [ ] "Other" and abstention options defined separately (if used)
- [ ] Human and model versions developed together and versioned (§ 7)

---

## 3. Human-Coded Validation Sets

### Validation is required, per task

"Any automated annotation process using an LLM must validate the LLM's performance against labels generated by humans," on "a task-by-task basis" (Pangakis et al., 2023). "Validation is, in short, a basic requirement for all publications using LLMs" (Törnberg, 2024). Reiss (2023) likewise stresses "the need for thorough validation, such as comparison against human-annotated data."

### The gold set's own quality must be established

- Song et al. (2020) show "a substantially greater risk of a researcher reaching an incorrect conclusion regarding the performance of automated procedures when the quality of manual annotations used for validation is not properly ensured."
- Pangakis et al. (2023) call for "at least two subject matter experts."
- Reliability data must come from coders who "follow explicit and communicable instructions … and work independently of each other" (Krippendorff, 2004).

### Code blind to the model

Krippendorff (2004) notes that "many methodological problems in testing reliability stem from violating the requirement for coders to be truly independent." In a pre-registered experiment on subjective annotation tasks, Schroeder et al. (2025) found that "annotators strongly took the LLM suggestions, significantly changing the label distribution", and that when LLM-assisted labels are used to evaluate the LLM, "reported model performance significantly increases." Human coders who see model suggestions are no longer an independent check on the model.

### Separate development from test, and never tune on the test set

- Refine the codebook on a subset, then judge on "held-out data … not the text samples used in the codebook update process" (Pangakis et al., 2023).
- "It is not acceptable to use the validation data to improve the prompts, as this may lead to falsely reporting higher precision" (Törnberg, 2024).
- The human-coding parallel: use a separate pilot sample, and fold pilot units into the final reliability sample "only if the reliability levels obtained in the pilot test were adequate" (Lombard et al., 2010).

| Split | Used for | Never used for |
|-------|----------|----------------|
| **Development set** | Writing and revising the codebook, choosing examples, comparing prompt or option wordings | Reporting final performance |
| **Test (validation) set** | One final evaluation of the frozen instrument | Any further revision |
| **Correction sample** (if § 6 corrections are planned) | Design-based bias correction | Prompt development (*Reasoning:* see § 6.3) |

### Sample from the data you will actually code

- Reliability data "must be representative of the data whose reliability is in question" (Krippendorff, 2004), drawn by "a random or other justifiable procedure" (Lombard et al., 2010).
- Rare classes are where errors hide. Bennett and Carvalho (2010) show that disproportionate stratified sampling can estimate classifier precision with less labeling effort than simple random sampling.
- *Reasoning:* an oversampled or stratified gold set needs inverse-probability weights when you estimate *population-level* accuracy or prevalence, and the sampling probabilities must be recorded at draw time. § 6.3's design-based corrections require them too.

### Size by the precision you need

The literature offers conflicting rules of thumb and one principled approach. Present them as such.

| Guidance | Context | Source |
|----------|---------|--------|
| "Practical minimum is … 20-30 samples of each category"; the number depends on "the number of categories and the balance of categories"; "for a precise determination, consider performing a power analysis" | LLM annotation validation | Törnberg (2024) |
| Not "less than 50 units or 10%", "rarely … greater than 300"; larger samples "when the expected reliability level is low" | Human intercoder reliability samples | Lombard et al. (2010) |
| Treat "intercoder reliability as a sampling problem" and size the sample so results carry "a known degree of confidence" | Human intercoder reliability | Lacy and Riffe (1996) |
| "Underpowered experiments are common" when comparing NLP models | Comparing two prompts, models, or annotators | Card et al. (2020) |

Power- or precision-based sizing is the principled answer (Lacy and Riffe, 1996; Card et al., 2020; Törnberg, 2024). None of these sources gives a standard specifically for multi-class LLM validation. *Reasoning:* if the gold set must show that two prompts or two annotators differ, size it for that paired comparison, not just for estimating one accuracy. Report per-class counts next to per-class rates, because rare-class estimates from small counts are noisy.

### Human coders are fallible; validate subgroups; avoid contamination

- "The human coders should not be considered ground truth" (Törnberg, 2024). Report human–human agreement (§ 4) so readers can see the ceiling.
- Subsets "for instance different languages or cultural contexts … need to be separately validated" (Törnberg, 2024). *Reasoning:* the same applies to any subgroup the analysis will compare (schools, demographic groups, time periods), because § 6 shows that error differing by group biases group comparisons.
- Contamination: avoid public labeled datasets as validation data, because "the LLM has likely already seen this database" (Törnberg, 2024). Pangakis et al. (2023) used only non-public datasets for this reason. Törnberg also calls the risk "often overstated" but puts "the burden of evidence … on the validator."

**Validation-set checklist**
- [ ] Drawn from the analysis corpus by a recorded random or stratified procedure, with inclusion probabilities saved
- [ ] At least two independent coders, blind to model output and to each other
- [ ] Development / test (/ correction) splits fixed *before* prompt iteration begins
- [ ] Size justified by the precision or comparison needed, per class
- [ ] Subgroups the analysis will compare are represented well enough to validate separately
- [ ] Not drawn from a public labeled benchmark

---

## 4. Agreement and Accuracy Metrics

Two framings coexist (§ 11). Treat the model as a **coder**, and the question is reliability: is it interchangeable with a human coder? (Krippendorff, 2004). Treat it as a **classifier**, and the question is accuracy against gold: precision, recall, F1. Report both.

### Never report accuracy or percent agreement alone

- Accuracy "can be highly misleading, in particular for imbalanced datasets"; use "a combination of these metrics", e.g., precision, recall, F1, and Cohen's kappa (Törnberg, 2024).
- Pangakis et al. (2023) criticize studies reporting "minimal performance metrics (i.e., only accuracy or intercoder agreement)."
- "Do NOT use only percent agreement"; there is "consensus … that percent agreement is a misleading and inappropriately liberal measure" (Lombard et al., 2010).
- *Reasoning:* report the full confusion matrix. It is standard practice, and it shows *which* categories are confused with which. That is the input to codebook revision and to § 6's question of whether the error is systematic. The sources consulted do not prescribe it explicitly.

### Metric menu

| Metric | Answers | Notes |
|--------|---------|-------|
| Per-class precision, recall, F1 | How good is the annotator on each code? | Report per class, with counts; macro averages hide weak classes |
| Confusion matrix | Which codes are confused with which? | Diagnostic for codebook revision and for systematic error |
| Krippendorff's alpha | Chance-corrected agreement, any number of coders, any level of measurement, with missing data | Proposed as "the standard reliability measure" (Hayes and Krippendorff, 2007) |
| Cohen's kappa (two coders; Cohen, 1960) / Fleiss's kappa (many; Fleiss, 1971) | Chance-corrected agreement | Contested as a reliability index (see below) |
| Weighted kappa (Cohen, 1968) / ordinal alpha | Agreement on ordered codes, with partial credit for near misses | Use for ordinal ratings |
| Correlation, MAE, MSE | Agreement on numeric outputs | Törnberg (2024) suggests these; Krippendorff (2004) rejects correlation as a reliability index |

**Alpha vs. kappa, a live disagreement.** Krippendorff (2004) rejects Cohen's kappa as a reliability index because its expected agreement depends on "individual coder preferences", calling it "just about worthless as a reliability index." Artstein and Poesio (2008) review alpha, Scott's pi, and kappa, and argue that "weighted, alpha-like coefficients … may be more appropriate for many corpus annotation tasks." Törnberg (2024) lists kappa as appropriate, and Lombard et al. (2010) recommend reporting multiple indices. A defensible default is to report alpha and name the coefficient used. Add kappa if the audience expects it.

**Ordinal codes.** When data are ordered, select "a coefficient that responds to the information in their metric … but assumes not more than warranted" (Krippendorff, 2004). Alpha supports nominal, ordinal, interval, and ratio data.

### Test the smallest distinction, not the average

"The reliability of each distinction should be tested and the smallest one should be taken as the reliability of the whole variable"; averaging "can easily mislead" (Krippendorff, 2004). This applies when category frequencies drive the conclusions (differences, changes, proportions); Krippendorff notes this may not be required for analyses of correlations or associations. The same logic applies across the variables that enter one index or one regression.

### Benchmark against human–human agreement

"Ideally, the LLM should approach the reliability achieved among the human coders" (Törnberg, 2024). Mellon et al. (2024) compare models against "a second human coder"; Gilardi et al. (2023) compare against "crowd workers and trained annotators." A model–human agreement figure means little without the human–human figure next to it.

### Thresholds are conventions tied to the stakes

Krippendorff (2004) suggests α ≥ .800, or ≥ .667 "where tentative conclusions are still acceptable," and adds that "there are no magical numbers": the threshold should depend on "the costs of drawing invalid conclusions." Lombard et al. (2010): ".80 or greater is acceptable in most situations," with higher bars for liberal indices. Choose and state the threshold *before* evaluating the test set, and justify it by what the variable will be used for.

---

## 5. LLM-Specific Validation Checks

Generative LLMs bring sensitivities that hand coding and conventional classifiers do not. Each row is a check to run on the **development set** (or on a held-out slice when the check itself is the finding).

| Concern | Evidence | Check |
|---------|----------|-------|
| **Prompt wording and format** | "LLM compliance and accuracy are prompt-dependent," and "minor prompt changes like asking for an explanation can cause large changes in the distribution of LLM-generated labels" (Atreja et al., 2025). Minor wording changes "or repeating the identical input can lead to varying outputs" (Reiss, 2023). Prompt format, examples, and their order "can cause accuracy to vary from near chance to near state-of-the-art" (Zhao et al., 2021) | Paraphrase the instructions and compare outputs with Krippendorff's alpha (Törnberg, 2024), or a "Prompt Stability Score" adapting intra- and inter-coder reliability (Barrie, Palaiologou, and Törnberg, 2024) |
| **Option order and position** | "All models are sensitive to the order that categories are described in the codebook" (of the open-weight models tested; Halterman and Keith, 2025). Sensitivity to option order in multiple-choice questions (Pezeshkpour and Hruschka, 2024). A token-level "selection bias" toward specific option IDs (Zheng et al., 2023). Bias toward answers "placed near the end of the prompt or … common in the pre-training data" (Zhao et al., 2021) | Run several option permutations and measure agreement across them. No single order is neutral; Törnberg (2024) lists options alphabetically for output parsing, not as a guard against order effects |
| **Label-name bias** | With generic labels ("LABEL 1") or labels swapped across definitions, models perform worse: "LLMs are indeed relying on the semantic content of the labels themselves" (Halterman and Keith, 2025) | Check that label names match their definitions closely; a swapped- or generic-label run shows how much the names carry |
| **Version drift** | "The performance and behavior of both GPT-3.5 and GPT-4 can vary greatly over time," and updates are "opaque" (Chen et al., 2024). A prompt is "tailored to the model used for its development"; use "a fixed version of the LLM" (Törnberg, 2024) | Pin and record the answering version (§ 7). *Reasoning:* re-validate whenever the model, instructions, or option set changes, because a validation applies only to what was validated |
| **Run-to-run consistency** | Repeat classification at temperature > 0; a "consistency score is correlated with accuracy" and flags edge cases (Pangakis et al., 2023) | Use repeat-run agreement to flag hard items. It is a **diagnostic, not a substitute for validation against human codes** |

**Typed-judgment APIs.** These services answer a fixed set of typed questions with probabilities instead of free text. The evidence above comes from generative LLMs. *Reasoning:* the mechanisms (option ordering, label semantics, version changes, sensitivity to instruction wording) plausibly apply to any annotator that chooses from a fixed option set, so it is a reasonable expectation to test them on a typed-judgment API. That they apply is **not established**: the sources tested no such product. The checks in the table cost little, so run them rather than assume either way.

**How much prompt wording matters is itself contested** (§ 11). Pangakis et al. (2023) found one round of codebook revision gave modest gains and that "the subtleties of prompt construction do not appear to be a significant lever on performance," while Atreja et al. (2025), Reiss (2023), and Zhao et al. (2021) report large effects. Measure it on your task.

---

## 6. Using Annotations as Variables Downstream

Once model codes become a variable, *measurement error* becomes *estimation bias*. This section covers the direction of that bias, why good validation metrics do not rule it out, and the corrections that use a human-coded subsample.

### 6.1 The direction of misclassification bias depends on the setting

Misclassification does **not** reliably push estimates toward zero.

| Setting | Consequence | Source |
|---------|-------------|--------|
| Bivariate least squares, nonsystematic (nondifferential) misclassification | Attenuation toward zero: the textbook case behind the familiar intuition | TeBlunthuis et al. (2024) |
| A binary *predicted covariate* | Predictions "will generally lead to attenuation biases" | Zhang (2021) |
| More than one predictor, or nonlinear models | "Even nonsystematic misclassification can cause bias away from 0" | TeBlunthuis et al. (2024) |
| Systematic (differential) misclassification | "Can bias inference in any direction"; in their simulation "the naïve estimator is opposite in sign to the true parameter" | TeBlunthuis et al. (2024) |
| A multi-category (polytomous) code with nondifferential error | Bias "away from null for some of the exposure categories and towards null for others" | van Smeden et al. (2020) |
| Interactions, effect modification, mediation | Measurement error creates "bias away or towards null" | van Smeden et al. (2020) |
| A misclassified *binary outcome* | "Necessarily non-classical measurement error, and thus leads to bias." If misclassification is conditionally random, linear-probability coefficients are attenuated proportionally, by a factor set by the false-positive and false-negative rates. If it relates to covariates, only "a tendency" toward attenuation remains, which covariate correlation can "partly offset" | Meyer and Mittag (2017) |

**Definitions.** Error in an exposure is nondifferential "if error in the measurement error is independent of the true value of the outcome … and differential otherwise." Outcome error is nondifferential only if independent of the true exposure (van Smeden et al., 2020).

**Blind is not the same as nondifferential.** Error "can be differential even if the measurement is taken without knowledge of the outcome" (van Smeden et al., 2020). *Reasoning:* a model that never sees the outcome or the covariates can still make errors that track them, for example by mis-coding text written in a dialect or register common in one group. TeBlunthuis et al. (2024) document such a case: an automated classifier whose errors correlated with identity disclosure.

### 6.2 High accuracy does not certify unbiased estimates

- Regressing on a predicted *outcome* is unbiased only if the prediction error is mean-zero given the covariates. That condition "implies much stronger assumptions": errors "not affected by the independent variable, the outcome variable, or any unobserved confounder" (Egami et al., 2024). Their simulations show material bias and undercoverage even when annotation accuracy is high.
- Making error rates "transparent via metrics such as the F1 score … provide[s] little safeguard against misclassification bias" (TeBlunthuis et al., 2024).
- For category *proportions*, "even a method with a high percent of individual documents correctly classified can be hugely biased" (Hopkins and King, 2010).
- A large N "does not resolve the most serious consequences of measurement error" (van Smeden et al., 2020).
- Plugging ML predictions in as regression covariates "renders regression analyses biased, inconsistent, and overconfident" (Fong and Tyler, 2021).

*Reasoning:* §§ 3–5 tell you whether the codes are *good measurements*; this section is about whether an *estimate built from them* is unbiased. Those are separate questions, and passing the first does not settle the second.

### 6.3 Corrections that use a human-coded subsample

The design-based methods share one bargain: if a human-coded subsample is drawn from the analysis corpus by a **known sampling design**, you can get valid inference **without assuming anything about how the annotator errs**. Better annotations then buy precision, not validity.

| Method | Requirement | What it does not assume | Coverage and notes | Source |
|--------|-------------|------------------------|--------------------|--------|
| **DSL** (design-based supervised learning) | "The probability of sampling documents for expert coding πᵢ is known to researchers, and πᵢ is larger than zero for every document." Stratified and oversampled designs are allowed, including sampling that depends on the model annotation, covariates, or outcome, "as long as πᵢ is known." Externally coded subsets with unknown selection are ruled out, as is real-time analysis | "We make no assumptions about prediction errors." A doubly robust, AIPW-like bias-correction term | Outcomes and independent variables; linear, logistic, multinomial, Poisson, and fixed-effects regression; proportions; IV. Includes a power analysis for the number of expert labels and a quasi-Bayesian treatment of imperfect expert labels. Its Step 3 fits a model of the expert label given the annotator output on the expert-coded data | Egami et al. (2024); method introduced in Egami et al. (2023) |
| **PPI** (prediction-powered inference) | Labeled and unlabeled data are i.i.d. samples from a common distribution (with extensions for distribution shift and finite populations); the prediction rule is "independent of the observed data" | Valid CIs for means, quantiles, and linear/logistic coefficients "without making any assumptions on the machine-learning algorithm"; "more accurate predictions translate to smaller confidence intervals" | | Angelopoulos et al. (2023) |
| **PPI++** | As PPI | As PPI | Adapts to prediction quality; intervals "that always improve on classical intervals using only the labeled data" | Angelopoulos et al. (2026) |
| **Confidence-guided selection of items to hand-code** | Human labels collected on the items the procedure selects | — | Uses annotator confidence to decide which items get human labels while keeping valid CIs, with results "no less accurate than if we only relied on human annotations" | Gligorić et al. (2025) |

**A caution on postpi.** An independent assessment found that PPI "successfully controls the type 1 error rate … regardless of the quality of the pre-trained machine learning model," whereas postpi (Wang et al., 2020) "provides valid inference only under very strong conditions that rarely hold in practice" (Motwani and Witten, 2023). Do not present postpi as a default.

**Model-based alternatives** rest on assumptions about the error rather than on the sampling design:
- A GMM correction for ML-predicted covariates (Fong and Tyler, 2021). According to TeBlunthuis et al. (2024), this approach relies on an exclusion restriction and "is unable to correct differential error."
- Maximum-likelihood error modeling (TeBlunthuis et al., 2024), which can handle differential error by including the outcome in the error model but is "sensitive to parametric assumptions."
- Consistent estimators for predicted covariates that "require the existence of validation" data (Zhang, 2021).

**Practical implications (reasoning).**
- Draw the correction sample randomly, or with recorded known probabilities, *from the analysis corpus*. Convenience-coded items and items used for prompt development do not qualify.
- PPI's requirement that the prediction rule be independent of the observed data suggests that items used to tune instructions or choose a model should not double as the correction sample. Plan a separate split (§ 3 table). Whether one human-coded sample can serve validation, recalibration, and correction at once is an open question (§ 11).
- Decide on correction *before* hand-coding begins, because it determines how the human-coded sample must be drawn.

```
Will the annotations enter an estimate (prevalence, regression, group comparison)?
├─ No (e.g., codes only route items to human review) → validation (§§ 3–5) and reporting suffice
└─ Yes
    ├─ Can a human-coded subsample be drawn from the analysis corpus with known probabilities?
    │   ├─ Yes → design-based correction (DSL; PPI / PPI++): validity does not depend
    │   │         on the annotator's error structure
    │   └─ No  → only model-based corrections remain (they assume an error model), or none;
    │             report the naive estimate with § 6.1's direction caveats and sensitivity
    │             analyses, and say so plainly
    └─ Want to use probabilities instead of hard labels? → § 6.4–6.5 first
(Decision tree is the compilers' synthesis of the sources above.)
```

### 6.4 Probabilities vs. hard labels

Many annotators return a probability or a distribution over codes. Using it is not a free fix.

- **Role matters.** In the factor-score analogue, consistent estimates are obtained by using "regression factor scores for the explanatory latent variables and Bartlett scores for the response latent variables" (Skrondal and Laake, 2001). *Reasoning, by analogy:* a calibrated P(code | text) used as a **covariate** resembles regression calibration (substituting the conditional expectation for the true value). For an **outcome**, what matters is that the prediction error is mean-zero given the covariates (§ 6.2), not whether you take the argmax. No source was found that treats annotator-reported probabilities directly as regression-calibration inputs, so treat this as an analogy.
- **Probabilities do not remove differential error.** In latent class analysis, both maximum-probability assignment and pseudo-class draws from posterior probabilities were biased, "particularly when the association … is strong," because all classify-analyze approaches "impute the latent variable under a model that is not sufficiently general" (Lanza et al., 2013). *Reasoning:* an annotator's probability conditions only on the text, not on the analysis variables, so feeding it in does not repair error that tracks those variables.
- **Thresholding can create differential error.** Discretizing a variable measured with nondifferential error "can create differential exposure measurement error within the discrete categories" (van Smeden et al., 2020). *Reasoning:* taking the argmax of a probability is that kind of discretization.
- **Where probabilities are a safe win (reasoning).** In DSL and PPI the surrogate can be any prediction, so a *calibrated* probability or expected score can serve there. That can improve efficiency without putting validity at risk. Whether it beats hard labels in practice is an efficiency question with no head-to-head evidence (§ 11).

### 6.5 Calibration is a prerequisite for using probabilities

Calibration means "predicting probability estimates representative of the true correctness likelihood" (Guo et al., 2017). Modern neural networks are "poorly calibrated," and "temperature scaling – a single-parameter variant of Platt Scaling" is effective (Guo et al., 2017). Larger models are "well-calibrated on diverse multiple choice and true/false questions when they are provided in the right format," though a trained predictor of whether the model knows the answer (P(IK)) struggles "with calibration … on new tasks" (Kadavath et al., 2022). *Reasoning:* a vendor's calibration claim describes the vendor's own evaluation; check it on your task, instrument, and corpus against your human codes. TeBlunthuis et al. (2024) likewise suggest calibrating a classifier's predictions "to one's dataset."

| Step | How | Source |
|------|-----|--------|
| **Assess** | Reliability diagram and expected calibration error; Brier score (Brier, 1950) | Guo et al. (2017) for calibration; reliability diagrams and ECE are standard practice (not confirmed in the abstract); see `./supervised-ml.md` > "Calibration" for mechanics |
| **Know the failure directions** | Different learners distort probabilities in characteristic directions | Niculescu-Mizil and Caruana (2005) |
| **Recalibrate** | Platt (sigmoid) scaling (Platt, 1999); isotonic regression and multiclass recalibration (Zadrozny and Elkan, 2002). Isotonic is more flexible and needs more calibration data (`./supervised-ml.md`) | as cited |
| **Hold out** | Fit the recalibration map on held-out human-coded data; never evaluate calibration on the data used to fit it | Standard practice (reasoning) |
| **Score the right event** | Calibrate for the event your analysis acts on (e.g., "chosen code equals the gold code") and say which event | Reasoning |

**Prevalence inherits miscalibration.**
- "Imperfect classification accuracy can cause substantial bias in estimating class prevalence," especially when the test distribution differs from training (Forman, 2008).
- Classify-and-count "typically yields bad quantifiers"; probability-based quantifiers are the alternative (Bella et al., 2010).
- A label-proportion method for annotations "emphasizes the importance of calibration" (Card and Smith, 2018).
- *Reasoning:* summed probabilities estimate prevalence correctly only if the probabilities are calibrated *in the target corpus and subgroup*. Calibration can break when prevalence shifts across groups or time, which is exactly the variation a downstream comparison studies. Check calibration within the subgroups you compare.

### 6.6 Correction packages and DAAF's environment

| Package | Language | Where it is published | Status in the DAAF image |
|---------|----------|----------------------|--------------------------|
| `dsl` | R | GitHub only (`naoki-egami/dsl`); not on CRAN as of 2026-10-06 | **Not installed** |
| `ppi-python` (import name `ppi_py`) | Python | PyPI | **Not installed** |
| `ipd` | R | CRAN; its documentation lists PostPI, PPI, PPI++, PSPA, and other estimators, outcome-focused | **Not installed** |

None of these is installed in the DAAF image (container probe, 2026-10-06). Adding one means a **Dockerfile change and a rebuild**, never a runtime install (CLAUDE.md § Runtime Package Installation; runtime installs are blocked). If a correction is needed, raise it with the user early, because the rebuild has to happen before the analysis stage. The estimators' logic is documented in the papers above, but hand-rolling a doubly robust or prediction-powered estimator is a substantial validation burden in its own right. Treat it as a methods decision for the user, not an implementation detail.

---

## 7. Reproducibility with Hosted Models

### Hosted models change and disappear

- "Proprietors of closed LLMs can alter their product or its training data — which can change its outputs — at any time" (Spirling, 2023).
- "In many cases the LM findings cannot be re-run, let alone replicated"; whole versions were "suddenly retired," and models "may simply cease to exist overnight" (Barrie, Palmer, and Spirling, 2024).
- Providers "can update and re-train their models at any time, making previous versions suddenly unavailable" (Nature Computational Science, 2026).
- "Model deprecation should be treated as a core reporting and preservation issue" (Wolfrath et al., 2026).

### Pin the version, and record the version that actually answered

- "Use a fixed version of the LLM throughout the project, document the version, and ensure that the model will be available for future use." Stable API models also "tend to be deprecated after a relatively short time, making reproducibility nearly impossible" (Törnberg, 2024).
- "Studies should document the model version date and whether the model was frozen or remained dynamic during the data collection phase" (Gallifant et al., 2025).
- *Reasoning:* request a versioned model identifier rather than a moving alias, and persist the identifier the *response* reports, on every row. An alias can move mid-run.

### Outputs are not deterministic, so measure the variance

- "Setting the temperature to 0 does not guarantee determinism" (Ouyang et al., 2024). Atil et al. (2024) document accuracy varying across runs of models configured to be deterministic.
- Hardware and software differences and "floating-point arithmetic approximations" can "compound into different word choices" (Nature Computational Science, 2026). Even with temperature 0 and a fixed seed, "a small degree of nondeterminism may remain" (Fang et al., 2026).
- Run routines "multiple times, preferably over multiple days or weeks or months" and "report the variance they observe." It is "not enough — and may be actively misleading — to just report what prompt was used for one particular run" (Barrie, Palmer, and Spirling, 2024).
- *Reasoning:* for probability-returning APIs, the same logic plausibly applies to the returned distributions. No source tested this, so measure it.

### Persist everything needed to audit a run you may not be able to repeat

Document "the full prompt text, model identifiers and version numbers… hyperparameter settings, and timestamps of API calls"; deposit tagged releases; when correcting disputed labels, keep "both the original and revised versions in a transparent audit trail"; and keep an iteration log with "date, prompt version, and agreement statistics" (Fang et al., 2026). Parameters "must always be explicitly specified -even if they are the default parameters" (Törnberg, 2024). Log "system (hardware and software) specifications, parsing scripts, and LLM configurations" (Nature Computational Science, 2026). Palmer et al. (2024) want data "produced by the LM [to be] available for others to inspect, even if they cannot produce it themselves". That is the rationale for archiving raw outputs.

**Persistence checklist (per run, in DAAF's file-first audit trail)**
- [ ] Exact instrument text (instructions, option or level definitions, examples), versioned
- [ ] Requested model identifier *and* the identifier reported in each response
- [ ] All parameters, defaults included
- [ ] Full raw response per item, including full probability distributions where returned, not just the winning code. Saved as parquet per DAAF convention
- [ ] Timestamp, retry count, and final status per item; refusals, errors, and exclusions recorded
- [ ] Repeat-run results on a stability subsample
- [ ] Usage and cost per run
- [ ] An archived, dated copy of the provider's terms (§ 8)

### Justify closed models

Scientists should "explicitly justify their use of proprietary models." Palmer et al. (2024) list six justifications, including "Technical state of the art" and "Downstream use only", and note that justification also helps "informally 'version' closed models by documenting what they were capable of on a given task at a given time." Barrie, Palmer, and Spirling (2024) likewise advise: "Justify closed models if they must be used" and "Consider open models that allow off-line versioning." McLoughlin et al. (2026) call for "Prioritizing open models and standardizing reporting practices."

---

## 8. Data Governance

**Always confirm with the user before sending any research text to an external API.** Sending text to a third-party service is a disclosure of that data, and may also be a paid action on the user's account. The user, not the agent, decides whether the data's consent terms, IRB approval, and data agreements permit it. This gate applies even when the text looks innocuous. The agent usually cannot see the consent forms or data-use agreements that govern it.

### A third-party API call is a disclosure

- "Do not submit personally identifiable or sensitive information to third-party or public AI tools. Such data may only be used with AI tools that are approved for the applicable data classification level and have appropriate data protection agreements in place." Consent materials should state "Whether participant data will be used to train or improve AI systems" and "Whether data will be shared with third-party or external AI tools" (University of Michigan HRPP, 2026).
- "Any use of AI in a research study must be described in the IRB application and/or study protocol and receive IRB approval before implementation"; investigators must classify their data first (UW–Madison HRPP, 2026).
- "Annotating personal data using cloud APIs requires explicit consent from study participants and must be covered by an approved data management protocol" (Fang et al., 2026).
- These IRB pages are institution-specific examples, not federal rules. The user's own IRB governs.

### FERPA (U.S. student records)

- Studies-exception agreements must "use PII from education records only to meet the purpose or purposes of the study," must be conducted so as not to permit identification "by anyone other than representatives of the organization with legitimate interests," and must provide "Agree to not redisclose" (U.S. Department of Education PTAC, 2015).
- Properly de-identified data "is not protected by FERPA." For click-wrap terms of service, be cautious where a provider can amend terms "without notice," and "save a copy of the TOS that you have agreed to" (U.S. Department of Education PTAC, 2014).
- *Inference, not stated by the Department of Education:* routing student-record PII to an outside API provider not named in the data agreement would likely conflict with these purpose and redisclosure terms. No Student Privacy Policy Office guidance specific to generative AI was found.

### Free text is hard to de-identify

- The HIPAA de-identification standard "makes no distinction between data entered into standardized fields and information entered as free text," and "clinical narratives… are information rich and may provide context that readily allows for patient identification" (HHS Office for Civil Rights, n.d.).
- Current LLMs can infer a wide range of personal attributes from text supplied at inference time (Staab et al., 2023). AI systems can "re-identify data previously considered de-identified" (University of Michigan HRPP, 2026).
- *Reasoning:* scrubbing names from open-ended responses does not make them de-identified. When text cannot be reliably de-identified and no agreement covers the provider, do not send it.

### Provider terms, copyright, and jurisdiction

- Web interfaces "do not provide sufficient privacy… the data you provide is often kept and used for training models." "Never send proprietary, secret, or confidential data to an API… without careful consideration." Sending licensed text "to an API can be considered an infringement" (Törnberg, 2024).
- **Read and archive the provider's data-retention and training-use terms** before the first call, and re-review them periodically (adapted from U.S. Department of Education PTAC, 2014, on click-wrap terms of service). Record the archived copy's date in the project.
- **GDPR differs from U.S. frameworks:** data processing agreements; transfers outside the EU/EEA "subject to adequate protections"; and data minimization, "only use and send the minimum amount of data necessary" (Törnberg, 2024). Local models are a "GDPR-compliant, privacy-friendly alternative" (Fang et al., 2026).
- Common Rule secondary-use specifics and HIPAA Business Associate Agreements are not covered by the sources behind this file. Route those questions to the user's IRB and privacy office.

### DAAF routing

```
Is the text sensitive, PII-bearing, or governed (FERPA, HIPAA, IRB-restricted, proprietary)?
├─ Yes, or unsure
│   └─ Do NOT send it to a hosted annotator. Raise it with the user, and route the data
│      question to the `synthetic-data-workflow` skill (Data Onboarding's DI-1 sensitivity
│      gate), which keeps raw data out of the container. Synthetic data from that path is
│      a code-development scaffold, not an analytic substitute: the real annotation must
│      run where the data is governed (human coders, or a locally run model inside the
│      approved environment)
└─ No (public or properly de-identified text, permitted by the governing terms)
    └─ Confirm with the user before any call; archive the provider's terms; minimize
       what is sent (only the fields the judgment needs)
```

---

## 9. What to Report

Adapted from the published reporting checklists. GUIDE-LLM (Feuerriegel et al., 2026) is a consensus-based reporting checklist for behavioral and social science. TRIPOD-LLM (Gallifant et al., 2025) is a health-domain extension of TRIPOD+AI; use it when the annotated text is clinical, and cite the version used, since it is a "living document". DAAF's own AI-disclosure conventions and GUIDE-LLM mapping live in `agent_reference/AI_DISCLOSURE_REFERENCE.md`. Use that file for the project's AI-use disclosure; the list below covers the *annotation instrument* specifically.

| # | Report | Basis |
|---|--------|-------|
| 1 | **Purpose and role**: what the annotator measured; human-in-the-loop vs. fully automated | GUIDE-LLM A.1–A.2 |
| 2 | **Model identity**: provider, model name, the exact version ID the responses reported (not an alias), date(s) of access, and whether the model was frozen during collection | GUIDE-LLM B.1; Gallifant et al. (2025); Törnberg (2024) |
| 3 | **Justification** for a closed or hosted model, and any open-model or trained-classifier comparison | Palmer et al. (2024); GUIDE-LLM optional item |
| 4 | **Access mode and parameters**: API, web, or local; temperature, seed, max tokens, number of runs; defaults stated explicitly | GUIDE-LLM B.2–B.3; Törnberg (2024) |
| 5 | **Exact instrument text**: instructions, system text, option sets or score levels, examples, in a versioned codebook | GUIDE-LLM C.1–C.2; Törnberg (2024); Fang et al. (2026) |
| 6 | **Development history**: versions tried, and confirmation that the test set was not used to tune them | Törnberg (2024); Fang et al. (2026) |
| 7 | **Validation design and results**: gold-set sampling and size, coder independence, human–human and model–human agreement, per-class performance, confusion matrix, subgroup results | GUIDE-LLM E.1; §§ 3–4 |
| 8 | **Stability**: repeat-run variance over time; sensitivity to wording and option order | Barrie, Palmer, and Spirling (2024); Törnberg (2024); § 5 |
| 9 | **Failure handling and post-processing**: refusals, errors, retries, parsing, exclusions; how abstentions and "other" were treated | GUIDE-LLM E.2 |
| 10 | **Downstream use**: how codes entered estimates; any correction (DSL/PPI) with its sampling design; calibration checks if probabilities were used | § 6 |
| 11 | **Data governance**: personal or sensitive data handling, de-identification method, consent and IRB coverage, data agreement, and the archived provider terms with their date | GUIDE-LLM D.1; § 8 |
| 12 | **Archive and cost**: raw responses with timestamps, scripts, and metadata deposited; what cannot be re-run if the model is retired; total spend, tokens, time; funding or provider relationships | Fang et al. (2026); Nature Computational Science (2026); GUIDE-LLM G.1 and optional items |

Cost belongs in the report because it shapes design and whether others can afford to replicate. Annotation cost was a headline result of Gilardi et al. (2023). Fang et al. (2026) also flag the "hidden costs" of prompt engineering and iteration and recommend separate API keys per project to track spend. Prompt-stability experiments "can be expensive" (Barrie, Palmer, and Spirling, 2024).

---

## 10. Tools in DAAF

This file is the methodology. The tool skills below carry syntax, environment constraints, and curated caveats. Load the relevant one before giving tool-specific advice or writing code.

| Annotator | DAAF skill | Notes |
|-----------|-----------|-------|
| **Trained supervised classifier** | `scikit-learn` (Python) or `tidymodels` (R), with `./supervised-ml.md` for methodology | Runs locally; no third-party disclosure. Deep-learning frameworks are not in the image (`./supervised-ml.md` > "Current DAAF Support Status") |
| **Typed-judgment API** (Typesafe's Jev / System One) | `typesafe-ai` | An optional, on-demand skill; its request templates are Python (`requests`). For R scripts following the same patterns, `httr2` (1.2.2) and `jsonlite` (2.0.0) are installed in the image; `httr2` arrives as a dependency of another R package (`osmdata` imports it) rather than being listed explicitly in the Dockerfile. The skill's own "Evaluating fit for your task" section applies the checks in §§ 3–6 at the API level |
| **General-purpose generative LLM APIs** | No DAAF skill currently covers them | Escalate to the orchestrator; the methodology here still applies in full |
| **Bias-correction estimators** (DSL, PPI, PPI++) | None installed | See § 6.6: Dockerfile change and rebuild required |

Both hosted options are subject to § 8's gate. Both are **options to present to the user**, not defaults. Per § 1, which annotator serves a task best is an empirical question for that task.

---

## 11. Open Questions in the Literature

These are unsettled. Do not present any side as settled practice.

1. **Coder or classifier?** The reliability framing (coders as interchangeable; Krippendorff, 2004) and the accuracy-against-gold framing answer different questions. No source resolves which comes first.
2. **Alpha vs. kappa.** Krippendorff (2004) rejects kappa; Törnberg (2024) lists it as appropriate; Lombard et al. (2010) recommend reporting multiple indices.
3. **How much prompt wording matters.** Large effects (Atreja et al., 2025; Reiss, 2023; Zhao et al., 2021) vs. modest gains from codebook revision (Pangakis et al., 2023). Törnberg (2024) suggests prompt-stability checks as a "shortcut … without the need for a validation procedure," while also insisting validation is mandatory.
4. **Option order.** Törnberg (2024) lists options alphabetically for output parsing, not as a guard against order effects; the order-sensitivity evidence (Halterman and Keith, 2025; Pezeshkpour and Hruschka, 2024; Zheng et al., 2023) points to testing permutations.
5. **One codebook or two?** Pangakis et al. (2023) use one codebook for humans and model; Törnberg (2024) keeps both in one codebook, saying the two "should generally be similar," but finds separate instructions "usually beneficial."
6. **Is human gold the ground truth?** Song et al. (2020) treat gold quality as decisive; Törnberg (2024) says human coders "should not be considered ground truth." How to correct when human coders disagree substantially remains open; DSL's quasi-Bayesian extension is one answer (Egami et al., 2024).
7. **Contamination.** Treated as a real risk by Pangakis et al. (2023); "often overstated" per Törnberg (2024), who nonetheless puts the burden of evidence on the validator.
8. **Gold-set size.** Rules of thumb conflict (§ 3). Power-based sizing is principled, but there is no agreed standard for multi-class LLM validation.
9. **Reusing the human-coded sample.** Whether one sample can serve validation, recalibration, and DSL/PPI correction at once is not resolved. DSL builds model fitting into its procedure; PPI requires a prediction rule independent of the observed data.
10. **Probabilities inside DSL/PPI.** Whether calibrated probabilities outperform hard labels as the surrogate is an efficiency question without head-to-head evidence. Treating annotator probabilities as regression-calibration inputs is an analogy (§ 6.4), not an established result.
11. **Stability evidence.** How many repeat runs, over what time span, count as adequate stability evidence is open. Barrie, Palmer, and Spirling (2024) leave "what constitutes a 'sufficiently' stable prompt" open. No source tests the run-to-run stability of typed-probability APIs.

---

## References

Indexed citations were verified against bibliographic indexes (OpenAlex, Crossref, Semantic Scholar) on 2026-10-06, and every DOI checked for retractions returned no retraction or correction notice. Items that are not indexed (working papers, a book without a DOI, web guidance) are labeled as such, with access dates, as are preprints.

### Measurement and validation of text annotation

Adcock, R. and Collier, D. (2001). "Measurement Validity: A Shared Standard for Qualitative and Quantitative Research." *American Political Science Review*, 95(3). https://doi.org/10.1017/S0003055401003100

Grimmer, J. and Stewart, B.M. (2013). "Text as Data: The Promise and Pitfalls of Automatic Content Analysis Methods for Political Texts." *Political Analysis*, 21(3). https://doi.org/10.1093/pan/mps028

Grimmer, J., Roberts, M.E., and Stewart, B.M. (2022). *Text as Data: A New Framework for Machine Learning and the Social Sciences*. Princeton University Press. ISBN 9780691207544. No DOI located; the book is not indexed as a book record in OpenAlex. Existence confirmed via the Princeton research portal: https://collaborate.princeton.edu/en/publications/text-as-data-a-new-framework-for-machine-learning-and-the-social-/ (accessed 2026-10-06). Cited here only for its organizing framework (publisher abstract).

Halterman, A. and Keith, K.A. (2025). "Codebook LLMs: Evaluating LLMs as Measurement Tools for Political Science Concepts." *Political Analysis*. https://doi.org/10.1017/pan.2025.10017 (claims confirmed in arXiv v2, 2407.10747)

Jacobs, A.Z. and Wallach, H. (2021). "Measurement and Fairness." *Proceedings of ACM FAccT*. https://doi.org/10.1145/3442188.3445901

Neuendorf, K.A. (2017). *The Content Analysis Guidebook* (2nd ed.). Sage. https://doi.org/10.4135/9781071802878 (cited for its operationalization and sampling section structure, confirmed from the table of contents)

Pangakis, N., Wolken, S., and Fasching, N. (2023). "Automated Annotation with Generative AI Requires Validation." arXiv preprint. https://doi.org/10.48550/arXiv.2306.00176

Song, H., Tolochko, P., et al. (2020). "In Validations We Trust? The Impact of Imperfect Human Annotations as a Gold Standard on the Quality of Validation of Automated Content Analysis." *Political Communication*, 37(4). https://doi.org/10.1080/10584609.2020.1723752

Schroeder, H., Roy, D., and Kabbara, J. (2025). "Just Put a Human in the Loop? Investigating LLM-Assisted Annotation for Subjective Tasks." *Findings of ACL 2025*. https://doi.org/10.18653/v1/2025.findings-acl.1323

Törnberg, P. (2024). "Best Practices for Text Annotation with Large Language Models." *Sociologica*, 18(2). https://doi.org/10.6092/issn.1971-8853/19461 (also arXiv: https://doi.org/10.48550/arXiv.2402.05129)

### Reliability, agreement, and sampling

Artstein, R. and Poesio, M. (2008). "Inter-Coder Agreement for Computational Linguistics." *Computational Linguistics*, 34(4). https://doi.org/10.1162/coli.07-034-R2

Bennett, P.N. and Carvalho, V.R. (2010). "Online Stratified Sampling." *Proceedings of CIKM*. https://doi.org/10.1145/1871437.1871677

Card, D., Henderson, P., et al. (2020). "With Little Power Comes Great Responsibility." *Proceedings of EMNLP*. https://doi.org/10.18653/v1/2020.emnlp-main.745

Cohen, J. (1960). "A Coefficient of Agreement for Nominal Scales." *Educational and Psychological Measurement*, 20(1). https://doi.org/10.1177/001316446002000104

Cohen, J. (1968). "Weighted Kappa: Nominal Scale Agreement Provision for Scaled Disagreement or Partial Credit." *Psychological Bulletin*, 70(4). https://doi.org/10.1037/h0026256

Fleiss, J.L. (1971). "Measuring Nominal Scale Agreement Among Many Raters." *Psychological Bulletin*, 76(5). https://doi.org/10.1037/h0031619

Hayes, A.F. and Krippendorff, K. (2007). "Answering the Call for a Standard Reliability Measure for Coding Data." *Communication Methods and Measures*, 1(1). https://doi.org/10.1080/19312450709336664

Krippendorff, K. (2004). "Reliability in Content Analysis: Some Common Misconceptions and Recommendations." *Human Communication Research*, 30(3). https://doi.org/10.1093/hcr/30.3.411

Lacy, S. and Riffe, D. (1996). "Sampling Error and Selecting Intercoder Reliability Samples for Nominal Content Categories." *Journalism & Mass Communication Quarterly*, 73(4). https://doi.org/10.1177/107769909607300414

Lombard, M., Snyder-Duch, J., and Bracken, C.C. (2010). "Practical Resources for Assessing and Reporting Intercoder Reliability in Content Analysis Research Projects." Web resource, last updated 2010. http://matthewlombard.com/reliability/ (accessed 2026-10-06). Companion to Lombard, M., Snyder-Duch, J., and Bracken, C.C. (2002), "Content Analysis in Mass Communication: Assessment and Reporting of Intercoder Reliability," *Human Communication Research*, 28(4), https://doi.org/10.1111/j.1468-2958.2002.tb00826.x. Quotations in this file are from the web resource.

### LLM annotation evidence and sensitivities

Atreja, S., Ashkinaze, J., Li, L., Mendelsohn, J., and Hemphill, L. (2025). "What's in a Prompt?: A Large-Scale Experiment to Assess the Impact of Prompt Design on the Compliance and Accuracy of LLM-Generated Text Annotations." *Proceedings of ICWSM*, 19. https://doi.org/10.1609/icwsm.v19i1.35807

Barrie, C., Palaiologou, E., and Törnberg, P. (2024). "Prompt Stability Scoring for Text Annotation with Large Language Models." arXiv preprint. https://doi.org/10.48550/arXiv.2407.02039

Chen, L., Zaharia, M., and Zou, J. (2024). "How Is ChatGPT's Behavior Changing over Time?" *Harvard Data Science Review*. https://doi.org/10.1162/99608f92.5317da47

Gilardi, F., Alizadeh, M., and Kubli, M. (2023). "ChatGPT Outperforms Crowd Workers for Text-Annotation Tasks." *PNAS*, 120(30). https://doi.org/10.1073/pnas.2305016120

Mellon, J., Bailey, J., et al. (2024). "Do AIs Know What the Most Important Issue Is? Using Language Models to Code Open-Text Social Survey Responses at Scale." *Research & Politics*, 11(1). https://doi.org/10.1177/20531680241231468

Ornstein, J.T., Blasingame, E.N., et al. (2025). "How to Train Your Stochastic Parrot: Large Language Models for Political Texts." *Political Science Research and Methods*. https://doi.org/10.1017/psrm.2024.64

Pezeshkpour, P. and Hruschka, E. (2024). "Large Language Models Sensitivity to the Order of Options in Multiple-Choice Questions." *Findings of NAACL 2024*. https://doi.org/10.18653/v1/2024.findings-naacl.130

Reiss, M.V. (2023). "Testing the Reliability of ChatGPT for Text Annotation and Classification: A Cautionary Remark." OSF preprint. https://doi.org/10.31219/osf.io/rvy5p

Zhao, T.Z., Wallace, E., et al. (2021). "Calibrate Before Use: Improving Few-Shot Performance of Language Models." arXiv:2102.09690 (ICML 2021 version not consulted). https://doi.org/10.48550/arXiv.2102.09690

Zheng, C., Zhou, H., et al. (2023). "Large Language Models Are Not Robust Multiple Choice Selectors." arXiv preprint (ICLR 2024 version not consulted). https://doi.org/10.48550/arXiv.2309.03882

Ziems, C., Held, W., Shaikh, O., Chen, J., Zhang, Z., and Yang, D. (2024). "Can Large Language Models Transform Computational Social Science?" *Computational Linguistics*, 50(1), 237-291. https://doi.org/10.1162/coli_a_00502

### Misclassification and downstream inference

Angelopoulos, A.N., Bates, S., Fannjiang, C., Jordan, M.I., and Zrnic, T. (2023). "Prediction-Powered Inference." *Science*, 382(6671), 669-674. https://doi.org/10.1126/science.adi6000

Angelopoulos, A.N., Duchi, J.C., and Zrnic, T. (2026). "PPI++: Efficient Prediction-Powered Inference." *Annals of Applied Statistics*. https://doi.org/10.1214/26-aoas2215

Egami, N., Hinck, M., Stewart, B.M., and Wei, H. (2023). "Using Imperfect Surrogates for Downstream Inference: Design-Based Supervised Learning for Social Science Applications of Large Language Models." *NeurIPS 2023*. https://doi.org/10.48550/arXiv.2306.04746

Egami, N., Hinck, M., Stewart, B.M., and Wei, H. (2024). "Using Large Language Model Annotations for the Social Sciences: A General Framework of Using Predicted Variables in Downstream Analyses." Working paper, version of November 17, 2024. https://naokiegami.com/paper/dsl_ss.pdf (accessed 2026-10-06; not indexed)

Fong, C. and Tyler, M. (2021). "Machine Learning Predictions as Regression Covariates." *Political Analysis*, 29(4), 467-484. https://doi.org/10.1017/pan.2020.38

Gligorić, K., Zrnic, T., Lee, C., Candès, E., and Jurafsky, D. (2025). "Can Unconfident LLM Annotations Be Used for Confident Conclusions?" *Proceedings of NAACL 2025*. https://doi.org/10.48550/arXiv.2408.15204 (arXiv version; ACL Anthology DOI not resolved)

Hopkins, D.J. and King, G. (2010). "A Method of Automated Nonparametric Content Analysis for Social Science." *American Journal of Political Science*, 54(1), 229-247. https://doi.org/10.1111/j.1540-5907.2009.00428.x

Lanza, S.T., Tan, X., and Bray, B.C. (2013). "Latent Class Analysis with Distal Outcomes: A Flexible Model-Based Approach." *Structural Equation Modeling: A Multidisciplinary Journal*, 20(1), 1-26. https://doi.org/10.1080/10705511.2013.742377

Meyer, B.D. and Mittag, N. (2017). "Misclassification in Binary Choice Models." *Journal of Econometrics*, 200(2), 295-311. https://doi.org/10.1016/j.jeconom.2017.06.012

Motwani, K. and Witten, D. (2023). "Revisiting Inference after Prediction." *Journal of Machine Learning Research*, 24(394), 1-18. https://jmlr.org/papers/v24/23-0896.html

Skrondal, A. and Laake, P. (2001). "Regression Among Factor Scores." *Psychometrika*, 66(4), 563-575. https://doi.org/10.1007/BF02296196

TeBlunthuis, N., Hase, V., and Chan, C.-h. (2024). "Misclassification in Automated Content Analysis Causes Bias in Regression. Can We Fix It? Yes We Can!" *Communication Methods and Measures*, 18(3), 278-299. https://doi.org/10.1080/19312458.2023.2293713

van Smeden, M., Lash, T.L., and Groenwold, R.H.H. (2020). "Reflection on Modern Methods: Five Myths About Measurement Error in Epidemiological Research." *International Journal of Epidemiology*, 49(1), 338-347. https://doi.org/10.1093/ije/dyz251

Wang, S., McCormick, T.H., and Leek, J.T. (2020). "Methods for Correcting Inference Based on Outcomes Predicted by Machine Learning." *PNAS*, 117(48), 30266-30275. https://doi.org/10.1073/pnas.2001238117

Zhang, H. (2021). "How Using Machine Learning Classification as a Variable in Regression Leads to Attenuation Bias and What to Do About It." SocArXiv preprint. https://doi.org/10.31235/osf.io/453jk

### Calibration and prevalence estimation

Bella, A., Ferri, C., Hernández-Orallo, J., and Ramírez-Quintana, M.J. (2010). "Quantification via Probability Estimators." *Proceedings of IEEE ICDM*. https://doi.org/10.1109/icdm.2010.75

Brier, G.W. (1950). "Verification of Forecasts Expressed in Terms of Probability." *Monthly Weather Review*, 78(1), 1-3. https://doi.org/10.1175/1520-0493(1950)078%3C0001:VOFEIT%3E2.0.CO;2

Card, D. and Smith, N.A. (2018). "The Importance of Calibration for Estimating Proportions from Annotations." *Proceedings of NAACL-HLT 2018*, 1636-1646. https://doi.org/10.18653/v1/N18-1148

Forman, G. (2008). "Quantifying Counts and Costs via Classification." *Data Mining and Knowledge Discovery*, 17(2), 164-206. https://doi.org/10.1007/s10618-008-0097-y

Guo, C., Pleiss, G., Sun, Y., and Weinberger, K.Q. (2017). "On Calibration of Modern Neural Networks." *Proceedings of ICML*, PMLR 70, 1321-1330. https://proceedings.mlr.press/v70/guo17a.html

Kadavath, S., et al. (2022). "Language Models (Mostly) Know What They Know." arXiv preprint arXiv:2207.05221. https://arxiv.org/abs/2207.05221

Niculescu-Mizil, A. and Caruana, R. (2005). "Predicting Good Probabilities with Supervised Learning." *Proceedings of ICML*. https://doi.org/10.1145/1102351.1102430

Platt, J.C. (1999). "Probabilistic Outputs for Support Vector Machines and Comparisons to Regularized Likelihood Methods." In *Advances in Large Margin Classifiers*. MIT Press.

Zadrozny, B. and Elkan, C. (2002). "Transforming Classifier Scores into Accurate Multiclass Probability Estimates." *Proceedings of ACM SIGKDD*. https://doi.org/10.1145/775047.775151

### Reproducibility and reporting

Atil, B., et al. (2024). "Non-Determinism of 'Deterministic' LLM Settings." arXiv preprint. https://doi.org/10.48550/arXiv.2408.04667

Barrie, C., Palmer, A., and Spirling, A. (2024). "Replication for Language Models: Problems, Principles, and Best Practice for Political Science." Working paper, draft of December 17, 2024. https://arthurspirling.org/documents/BarriePalmerSpirling_TrustMeBro.pdf (accessed 2026-10-06; not indexed; a later version may differ)

Fang, Q., Garcia Bernardo, J., and van Kesteren, E.-J. (2026). "A Methodological Guide on Using Large Language Models for Reproducible Text Annotation in the Social Sciences and Humanities with Python and R." arXiv preprint. https://doi.org/10.48550/arXiv.2604.09638

Feuerriegel, S., Barrie, C., Crockett, M.J., …, and Ribeiro, M.H. (2026). "A Reporting Checklist for Large Language Models in Behavioural Science." *Nature Human Behaviour*, 10(7), 1182-1186. https://doi.org/10.1038/s41562-026-02492-7 (checklist items read from https://llm-checklist.com/, accessed 2026-10-06)

Gallifant, J., et al. (2025). "The TRIPOD-LLM Reporting Guideline for Studies Using Large Language Models." *Nature Medicine*. https://doi.org/10.1038/s41591-024-03425-5

McLoughlin, K.L., Palmer, A., Matias, J.N., Crockett, M.J., et al. (2026). "Proprietary LLMs Impede Scientific Transparency and Reproducibility." *Nature Reviews Psychology*, 5(8), 513-514. https://doi.org/10.1038/s44159-026-00593-8

Nature Computational Science (2026). "Reproducibility in the Era of Large Language Models" [Editorial]. *Nature Computational Science*, 6, 907. https://doi.org/10.1038/s43588-026-01061-2

Ouyang, S., Zhang, J.M., Harman, M., et al. (2024). "An Empirical Study of the Non-Determinism of ChatGPT in Code Generation." *ACM Transactions on Software Engineering and Methodology*. https://doi.org/10.1145/3697010

Palmer, A., Smith, N.A., and Spirling, A. (2024). "Using Proprietary Language Models in Academic Research Requires Explicit Justification." *Nature Computational Science*, 4, 2-3. https://doi.org/10.1038/s43588-023-00585-1

Spirling, A. (2023). "Why Open-Source Generative AI Models Are an Ethical Way Forward for Science." *Nature*. https://doi.org/10.1038/d41586-023-01295-4

Wolfrath, N., Conroy, M., Kosten, T., et al. (2026). "Model Retirement Creates Reproducibility Risk in Biomedical AI Publications." arXiv preprint. https://doi.org/10.48550/arXiv.2609.04699

### Privacy and data governance

HHS Office for Civil Rights (n.d.). *Guidance Regarding Methods for De-identification of Protected Health Information in Accordance with the HIPAA Privacy Rule*. Archived 2026-10-01: https://web.archive.org/web/20261001135346id_/https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html

Staab, R., Vero, M., Balunović, M., and Vechev, M. (2023). "Beyond Memorization: Violating Privacy via Inference with Large Language Models." arXiv preprint. https://doi.org/10.48550/arXiv.2310.07298

U.S. Department of Education, Privacy Technical Assistance Center (PTAC) (2014, February). *Protecting Student Privacy While Using Online Educational Services: Requirements and Best Practices*. https://studentprivacy.ed.gov/sites/default/files/resource_document/file/Student%20Privacy%20and%20Online%20Educational%20Services%20(February%202014)_0.pdf (accessed 2026-10-06)

U.S. Department of Education, Privacy Technical Assistance Center (PTAC) (2015, rev. June). *Guidance for Reasonable Methods and Written Agreements* (PTAC-FAQ-5). https://studentprivacy.ed.gov/sites/default/files/resource_document/file/Guidance_for_Reasonable_Methods%20final_0_0.pdf (accessed 2026-10-06)

University of Michigan Human Research Protection Program (HRPP) (2026). *AI Use in Human Research Studies*. Institutional guidance, archived 2026-07-22: https://web.archive.org/web/20260722202943id_/https://hrpp.umich.edu/aiinhumanresearch/

UW–Madison Human Research Protection Program (HRPP) (2026). *Using AI as a Tool*. Institutional guidance, posted 2026-07-22. https://irb.wisc.edu/2026/07/22/using-ai-as-a-tool/ (accessed 2026-10-06)
