# R Stats Time Series Reference

Time series analysis with base R `stats`: `ts()` objects, `arima()`, `acf()`/
`pacf()`, decomposition, stationarity tests, and Durbin-Watson. Covers the base
R time series toolkit. R 4.5.3.

---

## Contents

- [ts Objects](#ts-objects)
- [ACF and PACF](#acf-and-pacf)
- [ARIMA Models](#arima-models)
- [Decomposition](#decomposition)
- [Stationarity Tests](#stationarity-tests)
- [Forecasting](#forecasting)
- [Durbin-Watson and Serial Correlation](#durbin-watson-and-serial-correlation)
- [Comparison to Python](#comparison-to-python)

---

## ts Objects

R's `ts()` creates a time series object with built-in frequency and start/end
metadata:

```r
# Monthly data starting January 2020
y <- ts(data_vector, start = c(2020, 1), frequency = 12)

# Quarterly data starting Q1 2015
y <- ts(data_vector, start = c(2015, 1), frequency = 4)

# Annual data
y <- ts(data_vector, start = 2000, frequency = 1)

# Inspect ts properties
frequency(y)    # 12 for monthly, 4 for quarterly
start(y)        # c(2020, 1)
end(y)          # last period
time(y)         # time index as decimal
cycle(y)        # season number (1-12 for monthly)
```

### Subsetting

```r
# Subset by time window
window(y, start = c(2021, 1), end = c(2022, 12))

# Lag and difference operators
lag(y, k = -1)    # lag-1 (note: R's lag uses negative for standard lag)
diff(y)           # first difference
diff(y, lag = 12) # seasonal difference (12-month)
diff(diff(y))     # second difference
```

Note: R's `lag()` convention is the opposite of many other languages.
`lag(y, k = -1)` shifts the series backward by 1 period (the standard "lag-1").
`lag(y, k = 1)` is a lead.

---

## ACF and PACF

### Autocorrelation Function

```r
# ACF plot
acf(y)

# ACF values (suppress plot)
acf_vals <- acf(y, plot = FALSE)
acf_vals$acf    # autocorrelation values
acf_vals$lag    # lag numbers

# Custom max lag
acf(y, lag.max = 36)
```

### Partial Autocorrelation Function

```r
# PACF plot
pacf(y)

# PACF values
pacf_vals <- pacf(y, plot = FALSE)
pacf_vals$acf   # partial autocorrelation values
```

### Cross-Correlation

```r
# Cross-correlation between two series
ccf(x, y)
```

### Reading ACF/PACF for ARIMA Order Selection

| ACF Pattern | PACF Pattern | Suggested Model |
|-------------|--------------|-----------------|
| Tails off (gradual decay) | Cuts off after lag p | AR(p) |
| Cuts off after lag q | Tails off | MA(q) |
| Tails off | Tails off | ARMA(p,q) |
| Significant at seasonal lags | Significant at seasonal lags | Seasonal component |

---

## ARIMA Models

### arima() (Base R)

```r
# ARIMA(p, d, q)
fit <- arima(y, order = c(1, 1, 1))
summary(fit)

# Seasonal ARIMA(p, d, q)(P, D, Q)[s]
fit <- arima(y, order = c(1, 1, 1),
             seasonal = list(order = c(1, 1, 1), period = 12))

# Include external regressors
fit <- arima(y, order = c(1, 0, 0), xreg = cbind(x1, x2))
```

### Results Extraction

```r
fit <- arima(y, order = c(1, 1, 1))

coef(fit)           # Coefficients (ar1, ma1, intercept)
fit$sigma2          # Estimated innovation variance
AIC(fit)            # AIC
BIC(fit)            # BIC
logLik(fit)         # Log-likelihood
residuals(fit)      # Model residuals

# Standard errors
sqrt(diag(fit$var.coef))

# Confidence intervals
confint(fit)
```

### auto.arima (forecast Package)

If the `forecast` package is available, `auto.arima()` automatically selects
the best ARIMA order by information criterion:

```r
library(forecast)

# Automatic order selection
fit_auto <- auto.arima(y)
summary(fit_auto)

# With seasonal component
fit_auto <- auto.arima(y, seasonal = TRUE)

# Constrain search
fit_auto <- auto.arima(y, max.p = 3, max.q = 3, max.d = 2)

# Include regressors
fit_auto <- auto.arima(y, xreg = cbind(x1, x2))
```

### Diagnostic Checks for ARIMA

```r
# Check residuals for white noise
Box.test(residuals(fit), lag = 10, type = "Ljung-Box")
# H0: residuals are white noise

# Multiple lags at once
Box.test(residuals(fit), lag = 20, type = "Ljung-Box")

# ACF of residuals (should be within bounds)
acf(residuals(fit))

# Shapiro-Wilk on residuals
shapiro.test(residuals(fit))
```

---

## Decomposition

### Classical Decomposition

```r
# Additive decomposition: Y = Trend + Seasonal + Remainder
decomp_add <- decompose(y, type = "additive")

# Multiplicative: Y = Trend * Seasonal * Remainder
decomp_mult <- decompose(y, type = "multiplicative")

# Plot all components
plot(decomp_add)

# Extract components
decomp_add$trend
decomp_add$seasonal
decomp_add$random     # remainder
decomp_add$figure     # seasonal figure (one cycle)
```

### STL Decomposition (Loess)

More robust than classical decomposition:

```r
# STL: Seasonal and Trend decomposition using Loess
stl_fit <- stl(y, s.window = "periodic")
plot(stl_fit)

# Extract components
stl_fit$time.series[, "trend"]
stl_fit$time.series[, "seasonal"]
stl_fit$time.series[, "remainder"]

# Customized seasonal window
stl_fit <- stl(y, s.window = 13, t.window = 25)
```

`s.window = "periodic"` assumes the seasonal pattern is fixed over time.
A numeric value (e.g., 13) allows the seasonal pattern to evolve.

---

## Stationarity Tests

The `tseries` package ships pre-installed in the DAAF container image; the
`urca` package (a different, richer API for the same tests: `ur.df()`,
`ur.kpss()`, `ur.pp()`) is also installed.

### Augmented Dickey-Fuller (ADF) Test

```r
library(tseries)

# ADF test
adf.test(y)
# H0: series has a unit root (non-stationary)
# Reject (p < 0.05) -> series is stationary

# With specific lag order
adf.test(y, k = 4)
```

### KPSS Test

```r
library(tseries)

# KPSS test (level stationarity)
kpss.test(y, null = "Level")
# H0: series is level-stationary
# Reject (p < 0.05) -> series is NOT stationary

# KPSS test (trend stationarity)
kpss.test(y, null = "Trend")
# H0: series is trend-stationary
```

### Phillips-Perron Test

```r
library(tseries)

pp.test(y)
# H0: series has a unit root (non-stationary)
# Similar to ADF but uses non-parametric correction for autocorrelation
```

### Combined Interpretation

| ADF (H0: unit root) | KPSS (H0: stationary) | Conclusion |
|---------------------|----------------------|------------|
| Reject | Don't reject | Stationary |
| Don't reject | Reject | Non-stationary (difference) |
| Reject | Reject | Inconclusive (fractional?) |
| Don't reject | Don't reject | Inconclusive |

---

## Forecasting

### predict() for arima

```r
fit <- arima(y, order = c(1, 1, 1))

# Point forecasts with prediction intervals
pred <- predict(fit, n.ahead = 12)
pred$pred     # point forecasts
pred$se       # standard errors

# Compute 95% prediction intervals
upper <- pred$pred + 1.96 * pred$se
lower <- pred$pred - 1.96 * pred$se
```

### forecast() (forecast Package)

```r
library(forecast)

fit <- auto.arima(y)

# Forecast next 12 periods
fc <- forecast(fit, h = 12)
plot(fc)

# Extract components
fc$mean       # point forecasts
fc$lower      # lower bounds (80% and 95% by default)
fc$upper      # upper bounds
```

### Exponential Smoothing (HoltWinters)

```r
# Additive Holt-Winters
hw_fit <- HoltWinters(y, seasonal = "additive")

# Multiplicative
hw_fit <- HoltWinters(y, seasonal = "multiplicative")

# Forecast
predict(hw_fit, n.ahead = 12)

# With prediction intervals
predict(hw_fit, n.ahead = 12, prediction.interval = TRUE)
```

---

## Durbin-Watson and Serial Correlation

### In Regression Context

```r
library(lmtest)

fit <- lm(y ~ x1 + x2, data = df)

# Durbin-Watson test for first-order autocorrelation
dwtest(fit)
# DW ~= 2: no autocorrelation
# DW < 2: positive autocorrelation
# DW > 2: negative autocorrelation

# Breusch-Godfrey for higher-order autocorrelation
bgtest(fit, order = 4)
```

### For Time Series Residuals

```r
fit_arima <- arima(y, order = c(1, 0, 0))

# Ljung-Box test on residuals
Box.test(residuals(fit_arima), lag = 10, type = "Ljung-Box")

# Portmanteau test
Box.test(residuals(fit_arima), lag = 10, type = "Box-Pierce")
```

---

## Comparison to Python

| Task | R (base stats) | Python (statsmodels) |
|------|---------------|---------------------|
| Create time series | `ts(y, start, freq)` | `pd.Series` with DatetimeIndex |
| ACF | `acf(y)` | `sm.tsa.acf(y)` |
| PACF | `pacf(y)` | `sm.tsa.pacf(y)` |
| ARIMA | `arima(y, order = c(p,d,q))` | `sm.tsa.ARIMA(y, order=(p,d,q)).fit()` |
| Seasonal ARIMA | `arima(y, order, seasonal)` | `sm.tsa.SARIMAX(y, order, seasonal_order).fit()` |
| Auto ARIMA | `forecast::auto.arima(y)` | `pmdarima.auto_arima(y)` (external) |
| Decomposition | `decompose(y)` or `stl(y)` | `sm.tsa.seasonal_decompose(y)` |
| ADF test | `tseries::adf.test(y)` | `sm.tsa.adfuller(y)` |
| KPSS test | `tseries::kpss.test(y)` | `sm.tsa.kpss(y)` |
| Ljung-Box | `Box.test(resid, type = "Ljung-Box")` | `sm.stats.acorr_ljungbox(resid)` |
| Holt-Winters | `HoltWinters(y)` | `sm.tsa.ExponentialSmoothing(y).fit()` |

Key difference: R's `ts()` class carries frequency metadata natively, making
seasonal analysis cleaner. Python time series rely on pandas DatetimeIndex with
explicit frequency setting.

---

## References

- R Core Team (2026). R: A Language and Environment for Statistical Computing.
- Hyndman, R.J. & Athanasopoulos, G. (2021). *Forecasting: Principles and
  Practice*, 3rd ed. OTexts.
- Brockwell, P.J. & Davis, R.A. (2016). *Introduction to Time Series and
  Forecasting*, 3rd ed. Springer.
- Box, G.E.P., Jenkins, G.M., Reinsel, G.C., & Ljung, G.M. (2015). *Time
  Series Analysis: Forecasting and Control*, 5th ed. Wiley.
