# R Stats Classical Tests Reference

Classical hypothesis tests in base R: t-tests, chi-squared tests, Wilcoxon/
Mann-Whitney, Fisher's exact test, proportion tests, Kolmogorov-Smirnov, and
correlation tests. All functions are in the `stats` package (base R).

---

## Contents

- [t-test](#t-test)
- [Chi-Squared Test](#chi-squared-test)
- [Fisher's Exact Test](#fishers-exact-test)
- [Wilcoxon / Mann-Whitney Test](#wilcoxon--mann-whitney-test)
- [Proportion Test](#proportion-test)
- [Kolmogorov-Smirnov Test](#kolmogorov-smirnov-test)
- [Correlation Tests](#correlation-tests)
- [Summary Table](#summary-table)

---

## t-test

### Two-Sample t-test

```r
# Independent two-sample t-test (equal variances assumed)
t.test(x, y, var.equal = TRUE)

# Welch t-test (unequal variances -- default and recommended)
t.test(x, y)

# Formula interface
t.test(value ~ group, data = df)
```

### One-Sample t-test

```r
# Test: is the mean of x equal to mu0?
t.test(x, mu = 5)
```

### Paired t-test

```r
# Paired observations (before/after)
t.test(before, after, paired = TRUE)

# Formula interface with paired data
t.test(value ~ time, data = df_long, paired = TRUE)
```

### Options

```r
# One-sided test: is x > y?
t.test(x, y, alternative = "greater")

# One-sided: is x < y?
t.test(x, y, alternative = "less")

# Custom confidence level
t.test(x, y, conf.level = 0.99)
```

### Extracting Results

```r
result <- t.test(x, y)

result$statistic   # t-statistic
result$parameter   # degrees of freedom
result$p.value     # p-value
result$conf.int    # confidence interval for difference in means
result$estimate    # group means

# Using broom
library(broom)
tidy(result)
# Returns: estimate, estimate1, estimate2, statistic, p.value,
#          parameter, conf.low, conf.high, method, alternative
```

---

## Chi-Squared Test

### Test of Independence

```r
# From a contingency table
tab <- table(df$x, df$y)
chisq.test(tab)

# Directly from two vectors
chisq.test(df$x, df$y)
```

### Goodness-of-Fit Test

```r
# Observed counts vs expected proportions
observed <- c(45, 35, 20)
expected_prop <- c(0.5, 0.3, 0.2)

chisq.test(observed, p = expected_prop)

# Equal proportions (uniform distribution)
chisq.test(observed)  # default: equal probabilities
```

### Options and Results

```r
result <- chisq.test(tab)

result$statistic    # chi-squared statistic
result$parameter    # degrees of freedom
result$p.value      # p-value
result$observed     # observed frequencies
result$expected     # expected frequencies under H0
result$residuals    # Pearson residuals: (O - E) / sqrt(E)
result$stdres       # standardized residuals

# With continuity correction (default for 2x2 tables)
chisq.test(tab, correct = TRUE)

# Without continuity correction
chisq.test(tab, correct = FALSE)

# Simulate p-value (for small expected frequencies)
chisq.test(tab, simulate.p.value = TRUE, B = 10000)
```

### When to Use Simulated P-value

If any expected cell count < 5, the chi-squared approximation may be poor.
Use `simulate.p.value = TRUE` or switch to Fisher's exact test.

---

## Fisher's Exact Test

For 2x2 tables or small samples where chi-squared approximation is unreliable:

```r
# 2x2 table
tab <- matrix(c(10, 5, 3, 12), nrow = 2)
fisher.test(tab)

# From contingency table
tab <- table(df$treatment, df$outcome)
fisher.test(tab)

# Larger tables (r x c) -- uses Monte Carlo simulation
tab_large <- table(df$category, df$outcome)
fisher.test(tab_large, simulate.p.value = TRUE, B = 10000)
```

### Options

```r
result <- fisher.test(tab)

result$p.value       # p-value
result$conf.int      # CI for odds ratio (2x2 only)
result$estimate      # odds ratio (2x2 only)

# One-sided: odds ratio > 1?
fisher.test(tab, alternative = "greater")
```

---

## Wilcoxon / Mann-Whitney Test

Non-parametric alternatives to t-tests. Use when normality assumption is
violated or data is ordinal.

### Two-Sample (Mann-Whitney U)

```r
# Independent two-sample test
wilcox.test(x, y)

# Formula interface
wilcox.test(value ~ group, data = df)

# Exact p-value (for small samples without ties)
wilcox.test(x, y, exact = TRUE)
```

### One-Sample (Signed Rank)

```r
# Test: is the median of x equal to m?
wilcox.test(x, mu = 5)
```

### Paired (Signed Rank)

```r
wilcox.test(before, after, paired = TRUE)
```

### Options and Results

```r
result <- wilcox.test(x, y)

result$statistic   # W statistic
result$p.value     # p-value

# Confidence interval for location shift
wilcox.test(x, y, conf.int = TRUE)
# Adds: $conf.int and $estimate (Hodges-Lehmann estimator)

# One-sided
wilcox.test(x, y, alternative = "greater")
```

---

## Proportion Test

### One-Sample Proportion Test

```r
# x successes out of n trials; test against p0
prop.test(x = 45, n = 100, p = 0.5)
```

### Two-Sample Proportion Test

```r
# Compare two proportions
prop.test(x = c(45, 55), n = c(100, 120))
```

### Multiple Proportions

```r
# k-sample test of equal proportions
prop.test(x = c(45, 55, 60), n = c(100, 120, 110))
```

### Options

```r
# Without continuity correction
prop.test(x = 45, n = 100, p = 0.5, correct = FALSE)

# One-sided
prop.test(x = 45, n = 100, p = 0.5, alternative = "greater")

# Custom confidence level
prop.test(x = 45, n = 100, conf.level = 0.99)
```

---

## Kolmogorov-Smirnov Test

### One-Sample (Against a Reference Distribution)

```r
# Test: does x follow a normal distribution?
ks.test(x, "pnorm", mean = mean(x), sd = sd(x))

# Against a uniform distribution
ks.test(x, "punif", min = 0, max = 1)
```

### Two-Sample (Compare Two Distributions)

```r
# Test: do x and y come from the same distribution?
ks.test(x, y)
```

### Results

```r
result <- ks.test(x, y)

result$statistic   # D statistic (max distance between CDFs)
result$p.value     # p-value

# One-sided alternatives
ks.test(x, y, alternative = "less")     # CDF of x lies below y
ks.test(x, y, alternative = "greater")  # CDF of x lies above y
```

---

## Correlation Tests

### Pearson Correlation

```r
# Test: is the Pearson correlation between x and y != 0?
cor.test(x, y, method = "pearson")
```

### Spearman Rank Correlation

```r
cor.test(x, y, method = "spearman")
```

### Kendall Tau

```r
cor.test(x, y, method = "kendall")
```

### Options and Results

```r
result <- cor.test(x, y, method = "pearson")

result$estimate    # correlation coefficient
result$statistic   # t-statistic (Pearson) or S (Spearman)
result$p.value     # p-value
result$conf.int    # CI for correlation (Pearson only)

# One-sided: positive correlation?
cor.test(x, y, alternative = "greater")

# Correlation matrix (no p-values)
cor(df[, c("x1", "x2", "x3")])
cor(df[, c("x1", "x2", "x3")], method = "spearman")
```

---

## Summary Table

| Test | Function | H0 | When to Use |
|------|----------|-----|-------------|
| t-test (two-sample) | `t.test(x, y)` | Means are equal | Compare two group means (normal data) |
| t-test (one-sample) | `t.test(x, mu = m)` | Mean = m | Test against a hypothesized mean |
| t-test (paired) | `t.test(x, y, paired = TRUE)` | Mean diff = 0 | Before/after measurements |
| Chi-squared (independence) | `chisq.test(tab)` | Variables independent | Categorical association (large n) |
| Chi-squared (GOF) | `chisq.test(x, p = probs)` | Follows distribution | Test observed vs expected proportions |
| Fisher's exact | `fisher.test(tab)` | Independence | 2x2 tables, small samples |
| Wilcoxon/Mann-Whitney | `wilcox.test(x, y)` | Same distribution | Non-parametric two-sample test |
| Wilcoxon signed rank | `wilcox.test(x, mu = m)` | Median = m | Non-parametric one-sample test |
| Proportion test | `prop.test(x, n, p)` | Proportion = p | Test proportions |
| Kolmogorov-Smirnov | `ks.test(x, y)` | Same CDF | Compare distributions |
| Pearson correlation | `cor.test(x, y)` | Correlation = 0 | Linear association |
| Spearman correlation | `cor.test(x, y, method = "spearman")` | Rank correlation = 0 | Monotonic association |
| Kendall tau | `cor.test(x, y, method = "kendall")` | Concordance = 0 | Ordinal association |

---

## References

- R Core Team (2025). R: A Language and Environment for Statistical Computing.
  R Foundation for Statistical Computing, Vienna, Austria.
- Hollander, M., Wolfe, D.A., & Chicken, E. (2014). *Nonparametric Statistical
  Methods*, 3rd ed. Wiley.
