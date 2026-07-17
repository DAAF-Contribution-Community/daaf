# Fairness Assessment with fairmodels

fairmodels (v1.2.2, installed) assesses group fairness of classification models through DALEX explainers: compute the standard confusion-matrix-based fairness metrics per protected-attribute subgroup, compare them to a privileged group, and apply basic mitigation. For the conceptual framework — impossibility theorems, fairness criteria definitions, and when fairness assessment is required — see `supervised-ml.md` in the `data-scientist` skill. Python equivalent: `fairness.md` in the `scikit-learn` skill (fairlearn).

**Scope difference from fairlearn (honest asymmetry):** fairmodels covers assessment plus lightweight mitigation (`reweight`, `roc_pivot`, `resample`). It has no equivalent of fairlearn's in-processing `ExponentiatedGradient` reductions approach. If constrained retraining is a hard requirement, Python/fairlearn is the routed path.

## Setup: Explainer with type = "classification"

fairmodels consumes a DALEX explainer. Two requirements verified against the installed versions:

1. `y` must be numeric 0/1 (not a factor)
2. `type = "classification"` must be set explicitly — DALEX cannot infer the task from a workflow object, defaults to "regression", and `fairness_check()` then errors with "All models must be binary classification type"

```r
library(tidymodels)
library(DALEX)
library(fairmodels)

# fit is a fitted workflow(); outcome factor `hired` has levels c("yes", "no")
explainer <- DALEX::explain(
  model = fit,
  data = dplyr::select(test_data, -hired),          # predictors only
  y = as.numeric(test_data$hired == "yes"),          # numeric 0/1
  predict_function = function(m, newdata)
    predict(m, new_data = newdata, type = "prob")$.pred_yes,
  label = "rf_hiring",
  type = "classification",                           # REQUIRED for fairness_check
  verbose = FALSE
)
```

The protected attribute (`group` below) may be a model feature or held out of the model — fairness_check only needs it as a vector aligned with the test rows.

## fairness_check()

```r
fc <- fairness_check(
  explainer,
  protected = test_data$group,   # factor of subgroup labels, aligned with explainer data
  privileged = "A",              # reference level ratios are computed against
  verbose = FALSE
)
print(fc)
# "rf_hiring passes 1/5 metrics; Total loss: 2.41"

p <- plot(fc)   # ggplot: five metric ratios with the 0.8-1.25 four-fifths band
ggsave(file.path(FIGURES_DIR, "fairness_check.png"), p, width = 8, height = 5, dpi = 150)
```

`fairness_check` evaluates five ratio metrics (unprivileged / privileged), passing when the ratio falls in [epsilon, 1/epsilon] with epsilon = 0.8 by default (the "four-fifths rule"):

| Printed metric | Confusion-matrix definition | Fairness criterion |
|----------------|----------------------------|--------------------|
| Accuracy equality ratio | (TP + TN)/(TP + FP + TN + FN) | Equal accuracy |
| Predictive parity ratio | TP/(TP + FP) | Equal precision (PPV) |
| Predictive equality ratio | FP/(FP + TN) | Equal FPR |
| Equal opportunity ratio | TP/(TP + FN) | Equal TPR (recall) |
| Statistical parity ratio | (TP + FP)/(TP + FP + TN + FN) | Demographic parity |

### Inspecting the Numbers

```r
fc$fairness_check_data       # the five ratios per subgroup (score, subgroup, metric)
fc$parity_loss_metric_data   # parity loss for the full 12-metric set (TPR, FPR, PPV, STP, ACC, ...)

# raw per-group metric values (not ratios):
ms <- metric_scores(fc, fairness_metrics = c("TPR", "FPR", "STP", "ACC", "PPV"))
print(ms$metric_scores_data)   # score per subgroup per metric
```

## Group-Wise Metrics with yardstick

Independent of fairmodels, disaggregate any yardstick metric by group — useful for reporting and for metrics fairmodels does not cover:

```r
results <- augment(fit, new_data = test_data)   # adds .pred_class, .pred_yes, ...

# any yardstick metric respects dplyr grouping
results |>
  dplyr::group_by(group) |>
  yardstick::accuracy(truth = hired, estimate = .pred_class)

# selection rate + demographic parity ratio by hand
sel_rate <- results |>
  dplyr::group_by(group) |>
  dplyr::summarize(selection_rate = mean(.pred_class == "yes"), n = dplyr::n())
print(sel_rate)
```

Report group sizes (`n`) alongside metrics — small subgroups make every fairness metric unstable.

## Mitigation

fairmodels provides pre- and post-processing mitigation (both verified against 1.2.2):

```r
# --- Pre-processing: reweight() computes case weights that equalize
#     the protected-attribute / outcome distribution; refit the model with them
w <- reweight(protected = train_data$group, y = as.numeric(train_data$hired == "yes"))
# length(w) == nrow(train_data); pass as case weights when refitting

# --- Post-processing: roc_pivot() flips predictions near the decision
#     boundary (within theta) for the disadvantaged group, returning a new explainer
exp_fixed <- roc_pivot(explainer, protected = test_data$group,
                       privileged = "A", theta = 0.05)
fc2 <- fairness_check(exp_fixed, protected = test_data$group, privileged = "A",
                      label = "rf_roc_pivot", verbose = FALSE)
# compare: fc2$parity_loss_metric_data$STP vs fc$parity_loss_metric_data$STP
```

Always report metrics before AND after mitigation — mitigation trades overall performance for parity, and the trade must be visible to the reader.

## DAAF Reporting Integration

1. **Present fairness metrics alongside overall performance** — a model is not fully evaluated until both are reported
2. **State which fairness criterion was chosen and why** — a normative decision, not a purely technical one (see `supervised-ml.md`)
3. **Report per-group metrics, not just ratios** — use `metric_scores()` or the yardstick group pattern
4. **Document the protected-attribute definition** — how groups were constructed and the limitations of the categorization

## Operational Caveats

1. **Fairness metrics conflict** — the impossibility theorems mean you cannot pass all criteria simultaneously; choose deliberately.
2. **Binary classification only** — `fairness_check()` rejects regression explainers (use `fairness_check_regression()` for regression, with caution; it is experimental).
3. **Small groups are unstable** — under ~50 observations per group, ratios swing widely; report `n`.
4. **The four-fifths band is a heuristic**, not a legal or scientific threshold; justify the epsilon you use.
5. **Mitigation is not certification** — passing ratios after `roc_pivot` does not make the underlying model fair; document what was changed.

## Quick Reference

| Task | Code |
|------|------|
| Explainer for fairness | `DALEX::explain(fit, ..., type = "classification", y = <numeric 0/1>)` |
| Run fairness check | `fairness_check(explainer, protected = g, privileged = "A")` |
| Plot ratios | `plot(fc)` (ggplot; save via `ggsave()`) |
| Ratio table | `fc$fairness_check_data` |
| Per-group raw metrics | `metric_scores(fc, fairness_metrics = c("TPR", "FPR", "STP"))` |
| Group-wise yardstick metric | `results \|> group_by(group) \|> accuracy(truth, estimate)` |
| Pre-processing weights | `reweight(protected, y)` |
| Post-processing pivot | `roc_pivot(explainer, protected, privileged, theta = 0.05)` |
