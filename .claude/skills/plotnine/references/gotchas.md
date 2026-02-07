# Gotchas & Best Practices

## Common Errors

### Column Name Issues

**Error**: `KeyError` or "column not found"

**Cause**: Column names must be strings in `aes()`.

```python
# WRONG
aes(x=column_name, y=other)

# CORRECT
aes(x="column_name", y="other")
```

### Literal vs. Mapped Color

**Problem**: All points same color when expecting variation.

```python
# WRONG: looks for column named "blue"
aes(color="blue")

# CORRECT: fixed color (outside aes)
geom_point(color="blue")

# CORRECT: mapped to column
aes(color="species")
```

### Missing Required Aesthetic

**Error**: `PlotnineError: geom_*() requires the following missing aesthetics: ...`

**Fix**: Add required aesthetics to `aes()`.

```python
# geom_point needs x and y
ggplot(df, aes(x="col1", y="col2")) + geom_point()
```

### Plus at End of Line

**Error**: `SyntaxError`

**Cause**: Python doesn't allow `+` at line end without continuation.

```python
# WRONG
ggplot(df, aes("x", "y")) +
geom_point()

# CORRECT: use parentheses
(
    ggplot(df, aes("x", "y"))
    + geom_point()
)
```

### Data Type Mismatch

**Problem**: Unexpected plot behavior or errors.

```python
# If "year" is numeric but should be categorical
aes(x="factor(year)")

# Or convert in pandas first
df["year"] = df["year"].astype(str)
```

### Grouped Data Not Connecting

**Problem**: `geom_line()` draws separate segments.

**Fix**: Add `group` aesthetic.

```python
# Multiple lines by group
aes(x="x", y="y", group="id")

# Or use color (implicitly groups)
aes(x="x", y="y", color="id")
```

## ggplot2 Differences

### String Column Names

R uses bare names; Python uses strings:

```r
# R
aes(x = column, y = other)
```

```python
# Python
aes(x="column", y="other")
```

### Formula Syntax in Facets

```python
# plotnine uses string formula
facet_grid("row ~ col")

# Not R's bare formula
# facet_grid(row ~ col)  # WRONG
```

### factor() Syntax

```python
# In aes string
aes(color="factor(cyl)")
```

### Some Functions Missing

Not all ggplot2 functions exist. Check API reference for alternatives.

## Performance Tips

### Large Datasets

1. **Sample data** for exploration:
   ```python
   ggplot(df.sample(1000), aes(...))
   ```

2. **Use `geom_bin_2d()`** instead of `geom_point()` for millions of points.

3. **Reduce DPI** during development:
   ```python
   theme(dpi=72)
   ```

### Memory

Save plots explicitly and close:

```python
p = ggplot(...) + geom_point()
p.save("plot.png")
del p
```

## Best Practices

### Choosing Geoms

| Data | Geom |
|------|------|
| x: continuous, y: continuous | `geom_point()`, `geom_smooth()` |
| x: discrete, y: continuous | `geom_boxplot()`, `geom_violin()` |
| x: continuous (distribution) | `geom_histogram()`, `geom_density()` |
| x: discrete (counts) | `geom_bar()` |
| x: continuous, y: continuous (time) | `geom_line()` |

### Color vs. Fill

- **Points, lines**: use `color`
- **Bars, areas, polygons**: use `fill` (and `color` for outline)

```python
# Points
geom_point(aes(color="group"))

# Bars
geom_bar(aes(fill="group"))
```

### Layer Order

Later layers draw on top:

```python
(
    ggplot(df, aes("x", "y"))
    + geom_point(color="gray")     # Bottom
    + geom_smooth(color="red")     # Top
)
```

### Consistent Styling

Create reusable theme:

```python
my_theme = (
    theme_minimal()
    + theme(
        axis_text=element_text(size=12),
        plot_title=element_text(size=16, weight="bold")
    )
)

# Apply to plots
ggplot(...) + geom_point() + my_theme
```

### Readable Code

```python
# Good: clear structure
(
    ggplot(df, aes("x", "y", color="group"))
    + geom_point(size=2)
    + geom_smooth(method="lm")
    + scale_color_brewer(palette="Set1")
    + labs(title="My Plot", x="X Label", y="Y Label")
    + theme_minimal()
)
```

## Debugging

### Check Data

```python
print(df.head())
print(df.dtypes)
print(df["column"].unique())
```

### Simplify Plot

Start minimal, add layers one at a time:

```python
# Start here
ggplot(df, aes("x", "y")) + geom_point()

# Then add
+ geom_smooth()

# Then add
+ facet_wrap("group")
```

### Print Intermediate

```python
p = ggplot(df, aes("x", "y"))
print(p)  # Shows structure
p + geom_point()
```

## Quick Fixes

| Problem | Fix |
|---------|-----|
| Plot not showing | Add `.draw()` or ensure last expression |
| Legend unwanted | `+ guides(color=False)` |
| Axis labels overlapping | `+ theme(axis_text_x=element_text(angle=45))` |
| Too many legend items | Filter data or use `scale_*_manual()` |
| Bars not stacking | Check `position="stack"` |
| Points hidden | Add `alpha=0.5` or `position_jitter()` |
| Wrong colors | Check `color` vs `fill` |
| Facets same scale | Use `scales="free"` |
