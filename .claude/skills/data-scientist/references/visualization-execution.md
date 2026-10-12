# Visualization Execution Standards

Practical standards for producing clean, accessible, publication-ready figures. This guide is tool-agnostic. Whenever plotting tools enter the discussion — in advice or in code — load the routed skill: Python, `plotnine` (static) or `plotly` (interactive); R, `ggplot2` (static) or `plotly-r` (interactive). The library skills carry the syntax plus environment constraints and curated caveats that general knowledge lacks.

## Color Palette Selection

Color is one of the most powerful — and most abused — visual channels. Use it deliberately.

### Palette Type Decision Tree

```
What kind of data are you coloring?
├─ Ordered / continuous (e.g., income, temperature)
│   ├─ Values go low → high
│   │   └─ Sequential palette (single hue, light → dark)
│   └─ Values diverge from a meaningful center (e.g., above/below average)
│       └─ Diverging palette (two hues from neutral midpoint)
├─ Categorical / unordered (e.g., regions, school types)
│   └─ Qualitative palette (distinct hues, similar lightness)
└─ Only one thing matters (highlight vs. context)
    └─ Gray + one accent color
```

### Recommended Palettes

| Use Case | Palette | Why |
|----------|---------|-----|
| Sequential continuous | **viridis** | Perceptually uniform; "the current gold standard colormap" (Nuñez et al. 2018); usually readable in grayscale (DAAF heuristic) |
| Sequential, CVD-optimized | **cividis** | Blue-yellow range avoids red-green entirely |
| Sequential, high contrast | **inferno** | Wide luminance range; strong visual punch (DAAF heuristic) |
| Diverging (general) | **BrBG** (ColorBrewer) | Brown-teal avoids red-green; clear midpoint |
| Diverging (familiar) | **RdBu** (ColorBrewer) | Red-blue is intuitive for hot/cold, +/-; ColorBrewer flags RdBu colorblind-friendly, like BrBG |
| Categorical (≤8 groups) | **Okabe-Ito** | Purpose-built for color vision deficiency |
| Categorical (alternative) | **ColorBrewer Set2 / Dark2** | ColorBrewer flags Set2/Dark2 colorblind-friendly only at small class counts; check colorbrewer2.org for your number of classes, or use Okabe-Ito |
| Highlight one thing | **gray + one saturated color** | Instant attention focus; no legend needed |

**Okabe-Ito hex values (R's `palette.colors()` order, with black moved last and gray `#999999` omitted):** `#E69F00` (orange), `#56B4E9` (sky blue), `#009E73` (bluish green), `#F0E442` (yellow), `#0072B2` (blue), `#D55E00` (vermilion), `#CC79A7` (reddish purple), `#000000` (black). Use via `scale_color_manual()` in plotnine or `color_discrete_sequence` in plotly.

### Color Restraint

- **Maximum useful categories: 5-7 (rule of thumb).** Beyond that, viewers can't reliably distinguish colors. Group small categories into "Other," use faceting, or label directly.
- **Gray is your best friend.** Set everything to gray by default, then add color only where it encodes information or draws attention. This is the single most effective technique for directing focus.
- **Never use rainbow/jet.** It's perceptually non-uniform (bright yellows can read as false peaks; Nuñez et al. 2018), colorblind-hostile, and doesn't convert to grayscale meaningfully.
- **Muted fills, vivid accents.** Use desaturated colors for large areas (bars, choropleth). Reserve saturated colors for small elements that need to stand out.

## Colorblind Accessibility

Red-green color vision deficiency affects about 8% of men and 0.4% of women of European ancestry, and 4-6.5% of Chinese and Japanese men (Birch 2012). In a room of 50 people of European ancestry, half of them men, expect about 2 who struggle to tell a red-green scheme apart.

### The Golden Rule: Redundant Encoding

**Never rely on color alone.** Always pair color with at least one other visual channel:
- **Shape** — circles, squares, triangles in scatter plots (limit to 3-4, rule of thumb)
- **Line style** — solid, dashed, dotted for line charts
- **Direct labels** — text on chart elements eliminates color lookup entirely
- **Pattern/texture** — hatching in bar fills (use sparingly)
- **Position** — facet into small multiples instead of overlaying colored series

### The Quick Test: "Get It Right in Black & White"

Convert your chart to grayscale. If you lose information, your design relies too heavily on hue. Fix by:
1. Ensuring lightness varies across your palette (not just hue)
2. Adding redundant encoding
3. Switching to a perceptually uniform palette (viridis family)

### What to Avoid

- Red vs. green (the most common problem by far)
- Any palette where two colors differ only in hue at similar lightness
- More than 3-4 colors without redundant encoding as backup (rule of thumb)

### Testing Tools

- **Coblis** (color-blindness.com) — upload an image, simulate CVD types
- **Color Oracle** (colororacle.org) — desktop full-screen CVD filter
- **ColorBrewer** (colorbrewer2.org) — interactive picker with "colorblind safe" filter
- **Grayscale print test** — the simplest and often most revealing check

## Labeling Philosophy

### Direct Labeling vs. Legends

**Prefer direct labeling.** Legends force the reader into a lookup loop: see a color → travel to legend → decode → travel back → repeat. Each round-trip costs cognitive effort.

| Situation | Recommendation |
|-----------|---------------|
| Line chart, 2-4 series | Label at end of each line (right side) — no legend needed |
| Bar chart, few categories | Label bars directly with values or category names |
| Scatter, highlighted points | Annotate the points |
| Many categories (>5) | Legend may be necessary, but consider faceting first |
| Small multiples | Shared legend is fine — panel labels do the main work |

**Legend placement when needed:** Inside the plot area (corner with no data) is better than outside. Top-of-chart horizontal legends work for 2-4 items. Avoid bottom-of-chart placement (DAAF convention).

### Titles

| Style | Example | When to Use |
|-------|---------|-------------|
| **Descriptive** | "Per-Pupil Expenditure by State, 2022" | Exploratory analysis, technical reports |
| **Declarative** | "Spending Gaps Widened After 2019" | Presentations, policy briefs, stakeholder reports |

**Subtitles** provide methodology context: "Source: CCD 2015-2022, public schools only. N = 13,194 districts."

**Source notes** go at the bottom-left, in smaller gray text. Always include them.

### Axis Labels

- **Always include units.** "$K per pupil" is better than leaving it ambiguous.
- **Abbreviate large numbers.** 1K, 10K, 1M, 1B — readers process these faster than full numbers.
- **If you rotate labels, rotate the chart.** Angled tick labels on the x-axis are almost always a sign you should switch to a horizontal bar chart. This single change often transforms a cluttered chart into a clean one.
- **Axis breaks are risky.** Truncating the y-axis on a bar chart misrepresents magnitude. For line/dot charts, non-zero baselines are acceptable if clearly labeled.

### Annotation

Annotations are where the analyst adds value beyond what the data alone shows. Use them sparingly but strategically:

- **Reference lines** — horizontal lines for averages, targets, benchmarks. Label directly: "National avg: 42%"
- **Event annotations** — on time series, mark inflection points: "Policy X enacted," "COVID-19 closures"
- **Callouts** — brief text pointing to a specific data element. One short sentence max.
- **Strategic highlighting** — bold or saturate the focal element; gray out everything else

**Default limit (DAAF convention):** 1-2 annotations per chart. Time series with multiple relevant events may warrant 3-4, but each must earn its place. If you need more than 4, consider splitting into panels.

## Typography & Layout

### Font Selection

**Sans-serif for all chart text (DAAF convention).** Recommended: Inter, Source Sans Pro, Roboto, Lato, Helvetica/Arial.

### Size Hierarchy

These sizes are a DAAF convention; the Urban Institute guide, for example, uses 8.5pt axis labels in PDF figures.

| Element | Print Size | Screen Size | Weight |
|---------|-----------|-------------|--------|
| Title | 14-18 pt | 16-20 px | Bold |
| Subtitle | 11-14 pt | 13-16 px | Italic or regular |
| Axis labels | 10-12 pt | 11-13 px | Regular |
| Tick labels | 8-10 pt | 9-11 px | Regular |
| Annotations | 8-10 pt | 9-11 px | Regular |
| Source note | 7-8 pt | 10-11 px | Regular, gray |

**Minimum readable size:** Nothing below ~7 pt in print or ~9 px on screen.

### Aspect Ratios

| Chart Type | Recommended Ratio (rule of thumb) | Why |
|------------|-------------------|-----|
| Time series | ~16:9 or wider | Spreads temporal data; slopes are easier to perceive |
| Scatter plot | ~4:3 or 1:1 | Equal perception in both dimensions |
| Bar chart | Driven by category count | Horizontal bars can be taller; vertical bars wider |

### Whitespace

Leave adequate margins. Don't crowd labels against edges. Internal padding between data and axes prevents points from sitting on the axis line. Whitespace is not wasted — it aids comprehension.

## Export Standards

These are DAAF conventions; journals and publishers set their own requirements.

| Context | DPI | Format | Notes |
|---------|-----|--------|-------|
| Screen / web | 72-150 | PNG | Retina displays benefit from 2x (144-192) |
| Presentations | 150 | PNG | Balance quality and file size |
| Print / publication | 300+ | PNG or PDF | 300 DPI is a common minimum |
| Scalable / archival | N/A | SVG or PDF | Vector; scales without quality loss |

**Never use JPEG for charts.** Lossy compression creates visible artifacts around sharp lines and text.

**Recommended defaults for reports:** PNG at 300 DPI, dimensions ~2100 × 1400 px for full-width figures.

## Project Consistency

Define visual standards once and apply them to every figure. Inconsistency across figures in a report is one of the most visible markers of amateur work.

### What to Standardize

| Element | Define Once (DAAF convention) |
|---------|-------------|
| Color palette | 5-8 named colors (primary, secondary, accent, sequential, diverging) |
| Font family | Single sans-serif family for all text |
| Font sizes | Mapping of element roles to sizes |
| Background | White (#FFFFFF) or very light gray (#F5F5F5) |
| Gridlines | Light gray, horizontal only (or none) |
| Axis lines | Left + bottom only; remove top and right borders |
| Source note format | Consistent placement, font, wording |
| DPI and dimensions | Single export resolution and figure size |

### The Theme Approach

Build a reusable theme or configuration that encodes these standards. Apply it to every figure. Both plotnine (via `theme()`) and plotly (via `layout(template=)`) support this pattern. Define once, apply everywhere.

### Consistency Checklist

- [ ] Same color means the same thing across all figures in the report
- [ ] Same font family and size hierarchy throughout
- [ ] Source notes in the same position and format
- [ ] Sequential/diverging palettes are consistent (same blue gradient = same meaning)
- [ ] Figure numbering follows a single sequence
- [ ] All figures exported at the same DPI and dimensions

## Figure Captions

**Caption placement:** Below the figure (standard in policy research).

**Self-contained:** A reader should understand the figure without reading surrounding text. Include: what is shown, units, time period, geographic scope, sample size.

**Example:**
> **Figure 3.** Distribution of per-pupil expenditure across U.S. school districts, 2022-23. Districts weighted by enrollment. Median = $14,200. Source: CCD. N = 13,194.

**Cross-referencing:** Refer to figures by number ("As shown in Figure 3"), never by position ("the chart below"). Position changes during editing.

## Key References

- Wilke, C. *Fundamentals of Data Visualization* (2019) — clauswilke.com/dataviz
- Knaflic, C.N. *Storytelling with Data* (2015)
- [Urban Institute Style Guide](https://urbaninstitute.github.io/graphics-styleguide/) — practical model for project consistency
- [Datawrapper Blog: Colorblindness](https://www.datawrapper.de/blog/colorblindness-part2) — practical accessibility guidance
- [ColorBrewer](https://colorbrewer2.org) — palette selection with CVD/print filters
- WCAG 2.1: 4.5:1 for normal text (3:1 for large text; SC 1.4.3) and 3:1 for graphical objects needed to understand the content (SC 1.4.11)
- Birch, J. (2012). "Worldwide prevalence of red-green color deficiency." *Journal of the Optical Society of America A* 29(3):313. doi:10.1364/JOSAA.29.000313
- Nuñez, J.R., Anderton, C.R., & Renslow, R.S. (2018). "Optimizing colormaps with consideration for color vision deficiency to enable accurate interpretation of scientific data." *PLOS ONE* 13(7):e0199239. doi:10.1371/journal.pone.0199239
- Okabe, M. & Ito, K. (2002, modified 2008). [Color Universal Design (CUD): How to make figures and presentations that are friendly to Colorblind people](https://jfly.uni-koeln.de/color/)
