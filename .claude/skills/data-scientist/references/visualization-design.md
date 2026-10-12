# Visualization Design Principles

How to *think* about data visualization — choosing the right chart, encoding data effectively, and directing attention. This guide is tool-agnostic. Whenever plotting tools enter the discussion — in advice or in code — load the routed skill: Python, `plotnine` (static) or `plotly` (interactive); R, `ggplot2` (static) or `plotly-r` (interactive). The library skills carry the syntax plus environment constraints and curated caveats that general knowledge lacks.

## Exploratory vs. Explanatory

Every visualization serves one of two purposes. Know which one you're making.

**Exploratory:** You're investigating — "turning over 100 rocks to find perhaps 1 or 2 precious gemstones" (Knaflic 2014, "exploratory vs explanatory analysis" blog post). Show comprehensive data across multiple dimensions. Keep it neutral. Enable the viewer to draw conclusions.

**Explanatory:** You've found the gemstone. Now communicate it. Use selective highlighting, strategic annotation, and a declarative title to guide the audience to a specific insight.

| Aspect | Exploratory | Explanatory |
|--------|-------------|-------------|
| Audience | You (the analyst) | Stakeholders |
| Title style | Descriptive ("Enrollment by State") | Declarative ("Rural States Lost Students Fastest") |
| Color use | Functional, all series visible | Gray + highlight the signal |
| Annotation | Minimal | Strategic — explain what happened |
| Interactivity | Filters, drill-downs useful | Usually static, guided |

**Rule of thumb:** Do exploratory work first, thoroughly. Only move to explanatory when you know what the story is. The same data structure can serve both — the difference is emphasis and annotation.

## The One-Chart-One-Message Principle

Each visualization should communicate a single clear takeaway. If you need two messages, make two charts.

**Test:** Can you state the chart's message in one sentence? If not, the chart is trying to do too much.

**Common violations:**
- Dual-axis charts implying a relationship between unrelated series
- Overloaded charts with many (say 8+) colored series and a large legend
- Charts that require a paragraph of explanation to interpret

## Visual Encoding Hierarchy

Not all visual encodings are equally effective. Cleveland & McGill (1984) hypothesized, and partly tested by experiment, an ordering of elementary perceptual tasks by how accurately people judge quantitative values. Mackinlay (1986) extended it to ordinal and nominal data without empirical verification, and Munzner (2014) separates magnitude channels (for ordered data) from identity channels (for categories):

```
Most accurate (Cleveland & McGill 1984, p. 536)
  1. Position along a common scale (scatter plot, dot plot)
  2. Position along nonaligned scales (separate panels, small multiples)
  3. Length, direction (slope), angle (tied)
  4. Area (bubble size, treemap)
  5. Volume, curvature
  6. Shading, color saturation (heatmap intensity)
Least accurate
```

Ranks 3, 5, and 6 each contain tied tasks (p. 537). Color hue is not on this scale: Cleveland & McGill excluded it because hue has no single small-to-large ordering (p. 532). Use hue for categorical distinctions (an identity channel in Munzner 2014).

**Practical implications:**
- Bars beat pies for the same data: a bar chart lets readers compare positions on a common scale (rank 1) where a pie needs angle judgments (rank 3). In Cleveland & McGill's experiment the pie chart was more accurate on average in only 3 of 40 cases (p. 540).
- Scatter plots are powerful: both axes use position (rank 1).
- Bubble charts sacrifice precision: size uses area (rank 4).
- Heatmaps show patterns, not precise values: use them for "where are the hot spots?"

**Encoding depends on data type** (DAAF summary; see Munzner 2014, Ch. 5, on magnitude vs. identity channels):
- Quantitative → position, length, area, saturation
- Ordinal → position, saturation, size
- Categorical → position, hue, shape

## Chart Selection by Relationship

Start with the relationship you want to show, not the chart type you like. This framework draws from the Financial Times Visual Vocabulary (9 categories) distilled to the 6 most common in policy/research work. Numeric thresholds in these tables (category counts, series counts, sample sizes) are rules of thumb, not sourced cutoffs.

### Comparison — How do values differ across categories?

| Chart | Best For | Key Rule |
|-------|----------|----------|
| Vertical bar | Few categories (<12), short labels | Must start at zero (widely held convention) |
| Horizontal bar | Many categories or long labels | Sort by value (don't alphabetize) |
| Dot plot | Many categories, emphasis on position | Less ink than bars; avoids zero-baseline issue |
| Grouped bar | Sub-groups within categories | Limit to 2-3 sub-groups |
| Slope chart | Change between exactly 2 time points | Shows direction + magnitude of change |

### Distribution — How are values spread?

| Chart | Best For | Key Rule |
|-------|----------|----------|
| Histogram | Single distribution, shape + frequency | Bin width changes the story — try multiple |
| Box plot | Comparing distributions compactly | Hides shape: a bimodal and a unimodal distribution with the same quartiles produce identical boxes |
| Violin plot | Distribution shape matters | Reveals bimodality that box plots hide |
| Strip/jitter | Moderate datasets (n < ~500/group) | Shows individual data points; use transparency for larger n |
| ECDF plot | Percentile comparisons, no binning | Shows every point's rank; great for "what % fall below X?" questions |
| Ridgeline | Comparing many distributions (5-20+) | Compact vertical stacking of densities |

### Trend Over Time — How do values change?

| Chart | Best For | Key Rule |
|-------|----------|----------|
| Line chart | Continuous time series, 1-5 series | Lines imply continuity — don't use for discrete events |
| Area chart | Emphasizing volume over time | Stacked areas: only bottom layer and total are readable; middle layers lack a common baseline |
| Small multiples | 5+ series that would overlap | Each gets its own panel — avoids spaghetti |
| Bar chart | Discrete time periods (annual totals) | When each period is independent |
| Sparklines | Inline trend context in tables/text | Data-intense, design-simple, word-sized graphics (Tufte 2006, *Beautiful Evidence*) |

### Correlation — How do variables relate?

| Chart | Best For | Key Rule |
|-------|----------|----------|
| Scatter plot | Two continuous variables, n < ~5K | The gold standard — both axes use position |
| Hexbin / 2D density | Scatter with n > 5K (overplotting) | Shows density where scatter becomes a blob |
| Heatmap | Two categorical variables, showing intensity | Pattern detection, not precise reading |
| Connected scatter | Two variables changing over time | Path shows temporal trajectory |

### Composition — How do parts make a whole?

| Chart | Best For | Key Rule |
|-------|----------|----------|
| Stacked bar | Parts + total magnitude | Bottom segment is easiest to compare |
| 100% stacked bar | Comparing proportions across groups | Normalizes totals; focus on share |
| Treemap | Hierarchical, many categories | Space-efficient but hard to compare precisely |
| Waffle chart | Simple proportion ("7 out of 10") | Intuitive for general audiences |
| Stacked area | Composition change over time | Bottom layer + total are reliable; middle layers are hard to read precisely |

**Why pie charts are usually poor:** They encode values as angle (rank 3), whereas a bar chart supports position judgments on a common scale (rank 1). Comparing slices across pies is nearly impossible. As a rule of thumb, beyond 3-4 slices they become unreadable. A bar chart almost always communicates the same data more accurately. The one defensible use: showing that one category overwhelmingly dominates.

### Ranking — What is the order?

| Chart | Best For | Key Rule |
|-------|----------|----------|
| Horizontal bar (sorted) | Ranked list of categories | **Sort the data** — the chart should do the cognitive work |
| Lollipop | Ranked list, cleaner aesthetic | Dot + stem; less ink than full bars |
| Bump chart | How rankings change over time | Shows rank trajectories and crossovers |

## Small Multiples

When you have more than 5 series, small multiples almost always beat an overloaded single chart.

**Why they work:** The eye learns the chart structure once, then compares across panels. Structure is O(1), comparison is O(n) (a DAAF heuristic) — far less cognitive load than decoding a legend for each data point.

**When to use** (thresholds are rules of thumb):
- Too many series for one chart (>5 lines, >4 groups)
- Comparing pattern/shape across a categorical variable
- The legend would need more than ~5 entries

**Design rules:**
- **Shared axes** — all panels must use the same scales (this is the whole point)
- **Meaningful ordering** — sort by the variable of interest, not alphabetically
- **Label panels directly** — put the category name on each panel
- **Minimal per-panel decoration** — the structure does the work

**Limitations:** Weaker for precise cross-panel value comparison; consume more space.

## Common Pitfalls

| Pitfall | Why It's Bad | Better Alternative |
|---------|-------------|-------------------|
| Pie charts (>3 slices, rule of thumb) | Angle encoding is weak; cross-pie comparison is impossible | Horizontal bar, stacked bar |
| Dual-axis charts | Scale choices create false implied correlations; deeply misleading | Two separate panels; index to common baseline |
| 3D effects | Add no information; distort perception via perspective | Standard 2D charts |
| Spaghetti plots (>5 lines) | Colors become indistinguishable; tracking is impossible | Small multiples; gray + highlight one series |
| Truncated bar chart axes | Bars encode *length* — not starting at zero breaks that mapping | Start at zero, or switch to dot plot |
| Rainbow color scales | Perceptually non-uniform; bright yellows can read as false peaks (Nuñez et al. 2018, on jet); colorblind-hostile | viridis, cividis, or single-hue sequential |

## Integrity Checklist

Before finalizing any visualization:

- [ ] Bar charts start at zero (widely held convention)
- [ ] Scales are consistent across all panels/small multiples
- [ ] No dual axes implying false relationships
- [ ] Area/volume encodings are proportional (no distorted bubbles)
- [ ] Uncertainty is shown where relevant (confidence intervals, error bars)
- [ ] Data is not cherry-picked — full context is visible
- [ ] Source is cited
- [ ] The chart's message is stated (title) or immediately obvious
- [ ] Sample sizes (N) are disclosed for all groups shown
- [ ] Suppressed or missing values are noted (not silently excluded)
- [ ] Axis labels include units of measurement
- [ ] **Visual inspection performed via the Read tool on the generated PNG** — programmatic checks alone cannot verify layout, readability, color rendering, or overall visual coherence; every figure must be viewed directly before declaring it complete

## Key References

- Cleveland & McGill (1984). "Graphical Perception: Theory, Experimentation, and Application to the Development of Graphical Methods." *Journal of the American Statistical Association* 79(387):531–554. doi:10.1080/01621459.1984.10478080
- Mackinlay, J.D. (1986). "Automating the design of graphical presentations of relational information." *ACM Transactions on Graphics* 5(2):110–141. doi:10.1145/22949.22950
- Munzner, T. *Visualization Analysis and Design* (2014). A K Peters/CRC Press. doi:10.1201/b17511
- Tufte, E. *The Visual Display of Quantitative Information* (1983, 2nd ed. 2001)
- Tufte, E.R. *Beautiful Evidence* (2006)
- Knaflic, C.N. (2014). "exploratory vs explanatory analysis." storytellingwithdata.com blog. https://www.storytellingwithdata.com/blog/2014/04/exploratory-vs-explanatory-analysis
- Knaflic, C.N. *Storytelling with Data* (2015)
- Nuñez, J.R., Anderton, C.R., & Renslow, R.S. (2018). "Optimizing colormaps with consideration for color vision deficiency to enable accurate interpretation of scientific data." *PLOS ONE* 13(7):e0199239. doi:10.1371/journal.pone.0199239
- Schwabish, J. *Better Data Visualizations* (2021)
- Wilke, C. *Fundamentals of Data Visualization* (2019) — freely available at clauswilke.com/dataviz
- [FT Visual Vocabulary](https://ft-interactive.github.io/visual-vocabulary/) — 9-category chart selection framework
- [From Data to Viz](https://data-to-viz.com) — interactive decision tree by data type
