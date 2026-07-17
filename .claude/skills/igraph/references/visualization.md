# igraph Visualization: matplotlib Backend with Seeded Layouts

This reference covers static network figures via python-igraph's **matplotlib
backend** (the DAAF-supported path), reproducible force-directed layouts with
seed discipline, and styling nodes/edges by attribute. The Cairo backend
(`cairocffi`) is deliberately **not installed** — do not use it.

## Backend: matplotlib Only

python-igraph can render through Cairo (default) or matplotlib. DAAF's container
has matplotlib but **not** `cairocffi`, so all plotting goes through matplotlib
by passing a matplotlib `Axes` as the `target=`:

```python
import igraph as ig
import matplotlib
matplotlib.use("Agg")   # non-interactive backend for file-first script execution
import matplotlib.pyplot as plt
```

> `matplotlib.use("Agg")` selects the file-writing backend — correct for DAAF's
> file-first execution where figures are saved, not displayed interactively. Set
> it before importing `pyplot`.

## Layouts Are Stochastic — Seed Them

Force-directed layouts (Fruchterman-Reingold `"fr"`, Kamada-Kawai `"kk"`,
Davidson-Harel `"dh"`, large-graph `"lgl"`) randomize node initialization, so the
same graph produces a *different-looking* figure each run. For reproducible
figures, **seed before computing the layout** — the same discipline as community
detection:

```python
import random
random.seed(0)          # BEFORE g.layout(...) for a reproducible figure
layout = g.layout("fr")
```

Non-stochastic layouts (`"circle"`, `"grid"`, `"star"`, `"tree"`) are
deterministic and need no seed, but seeding anyway is harmless and keeps the
pattern uniform.

## Minimal Reproducible Figure

```python
# --- Config ---
import igraph as ig
import random
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# --- Layout (seeded) ---
# INTENT: compute a reproducible force-directed layout.
# REASONING: Fruchterman-Reingold randomizes initial positions; seeding fixes them
#   so the saved figure is identical across runs — essential for an auditable
#   research artifact.
# ASSUMES: g is already constructed; "fr" is a good general-purpose layout.
random.seed(0)
layout = g.layout("fr")

# --- Plot onto a matplotlib Axes ---
# INTENT: render the network to a matplotlib Axes and save to PNG.
# REASONING: target=ax routes igraph through the matplotlib backend (Cairo is not
#   installed); saving via fig.savefig keeps it in the file-first workflow.
# ASSUMES: vertex names exist for labels; adjust vertex_size for graph density.
fig, ax = plt.subplots(figsize=(8, 8))
ig.plot(
    g,
    target=ax,
    layout=layout,
    vertex_size=30,
    vertex_label=g.vs["name"],
    vertex_color="lightblue",
    edge_width=1.0,
)
ax.set_title("Collaboration network")
fig.savefig("network.png", dpi=200, bbox_inches="tight")
plt.close(fig)
```

## Styling by Attribute

The power of the visualization is encoding data — color nodes by community, size
them by centrality, weight edges by strength.

### Color nodes by community membership

```python
# INTENT: color nodes by their detected community.
# REASONING: mapping each community id to a distinct color makes the partition
#   visible; a categorical palette (tab10/tab20) keeps communities distinguishable.
# ASSUMES: g.vs["community"] was set from a community-detection membership vector.
import matplotlib

communities = g.vs["community"]
n_comm = max(communities) + 1
# NOTE: matplotlib.cm.get_cmap() was deprecated in 3.7 and is removed in 3.11;
#   the colormaps registry + resampled() is the stable replacement.
palette = matplotlib.colormaps["tab10"].resampled(max(n_comm, 1))
vertex_colors = [palette(c) for c in communities]

random.seed(0)
layout = g.layout("fr")
fig, ax = plt.subplots(figsize=(8, 8))
ig.plot(g, target=ax, layout=layout, vertex_size=25, vertex_color=vertex_colors)
ax.set_title("Communities (Louvain)")
fig.savefig("communities.png", dpi=200, bbox_inches="tight")
plt.close(fig)
```

### Size nodes by centrality, width edges by weight

```python
# INTENT: encode a centrality vector as node size and edge weight as line width.
# REASONING: scaling node size by degree/centrality draws the eye to important
#   nodes; scaling edge width by weight shows tie strength. Both are rescaled to a
#   readable pixel range so extreme values don't dominate.
# ASSUMES: `deg` aligns with g.vs order; weights are positive strengths.
deg = g.degree()
_dmax = max(deg) or 1
vertex_sizes = [10 + 40 * (d / _dmax) for d in deg]

w = g.es["weight"]
_wmax = max(w) or 1
edge_widths = [0.5 + 3.0 * (x / _wmax) for x in w]

random.seed(0)
layout = g.layout("kk")   # Kamada-Kawai — often cleaner for small weighted graphs
fig, ax = plt.subplots(figsize=(8, 8))
ig.plot(
    g, target=ax, layout=layout,
    vertex_size=vertex_sizes,
    vertex_color="salmon",
    edge_width=edge_widths,
)
ax.set_title("Node size = degree, edge width = weight")
fig.savefig("styled.png", dpi=200, bbox_inches="tight")
plt.close(fig)
```

## Common Plotting Options

| Option | Purpose |
|--------|---------|
| `layout=` | Precomputed layout (seed first if stochastic) |
| `vertex_size=` | Scalar or per-vertex list |
| `vertex_color=` | Scalar or per-vertex list of colors |
| `vertex_label=` | Per-vertex labels (e.g., `g.vs["name"]`) |
| `vertex_label_size=` | Label font size |
| `edge_width=` | Scalar or per-edge list |
| `edge_color=` | Scalar or per-edge list |
| `edge_arrow_size=` | Arrowhead size (directed graphs) |

## Layout Selection

| Layout | Good for |
|--------|----------|
| `"fr"` (Fruchterman-Reingold) | General-purpose force-directed; the default choice |
| `"kk"` (Kamada-Kawai) | Small-to-medium weighted graphs; often cleaner |
| `"drl"` / `"lgl"` | Large graphs (thousands of nodes) |
| `"circle"` | Deterministic ring; small graphs, comparison figures |
| `"grid"` | Deterministic grid; debugging/inspection |
| `"tree"` (Reingold-Tilford) | Hierarchies / DAGs |

## Reproducibility Note

A network figure is a research artifact. To make it reproducible:

- [ ] `matplotlib.use("Agg")` set before `pyplot` import (file-first execution).
- [ ] `random.seed(N)` called before any stochastic `g.layout(...)`, with `N` recorded.
- [ ] The exact layout name recorded (figures differ across layout algorithms).
- [ ] Figure saved via `fig.savefig(...)` (not shown interactively).

For non-network figures of graph-derived quantities (degree distributions,
centrality histograms, modularity-vs-resolution curves), use `plotnine` or
`plotly` — not this backend.
