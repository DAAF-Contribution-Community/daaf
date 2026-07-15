# Visualization with ggraph

Static, publication-quality network figures using ggraph — ggplot2 grammar of
graphics applied to networks. The dominant discipline here is **seeding the layout**:
force-directed layouts randomize initialization, so an unseeded figure is
irreproducible.

> **Container-rebuild reminder:** `ggraph` (and `tidygraph`) are added to the
> Dockerfile but not loadable until the container is rebuilt. Code in this file will
> error with "there is no package called 'ggraph'" until then. See the skill's
> Version Notes.

---

## Seed Discipline (mandatory)

Force-directed layouts (`fr` = Fruchterman-Reingold, `kk` = Kamada-Kawai, `dh`,
`lgl`) start from random node positions and iterate. Two runs without a fixed seed
produce different — sometimes very different — figures. **Call `set.seed()`
immediately before building any ggraph object that uses a stochastic layout.**

```r
library(igraph)
library(tidygraph)
library(ggraph)
library(ggplot2)

SEED <- 20260715
set.seed(SEED)                       # REQUIRED before a stochastic layout
p <- ggraph(g, layout = "fr") +
  geom_edge_link(alpha = 0.4) +
  geom_node_point(size = 3) +
  theme_void()
```

Deterministic layouts (`layout = "circle"`, `"grid"`, `"star"`, `"tree"`) do not
need a seed, but seeding before every layout is a harmless, consistent habit.

---

## The ggraph Grammar

A ggraph plot is three layered concepts:

1. **Layout** — the node positions: `ggraph(g, layout = "fr")`. Layout is chosen
   once at the top and is analogous to a coordinate system.
2. **Edge geoms** — `geom_edge_link()`, `geom_edge_arc()`, `geom_edge_fan()` draw
   edges; aesthetics map edge attributes (`aes(width = weight, alpha = weight)`).
3. **Node geoms** — `geom_node_point()`, `geom_node_text()` draw nodes; aesthetics
   map node attributes (`aes(color = community, size = degree)`).

```r
set.seed(SEED)
ggraph(g, layout = "fr") +
  geom_edge_link(aes(width = weight), alpha = 0.3, color = "grey60") +
  geom_node_point(aes(color = community, size = degree)) +
  geom_node_text(aes(label = name), repel = TRUE, size = 3) +
  scale_edge_width(range = c(0.2, 2)) +
  labs(title = "Collaboration Network") +
  theme_void()
```

---

## Common Layouts

| Layout | Character | Seed needed | Good for |
|--------|-----------|-------------|----------|
| `"fr"` | Force-directed (Fruchterman-Reingold) | **Yes** | General-purpose; the default choice |
| `"kk"` | Force-directed (Kamada-Kawai) | **Yes** | Smaller graphs, smoother spacing |
| `"stress"` | Stress-majorization (graphlayouts) | No (deterministic) | Stable, reproducible force-like layout |
| `"circle"` | Nodes on a circle | No | Small graphs, showing all-to-all structure |
| `"tree"` / `"dendrogram"` | Hierarchical | No | Trees, taxonomies |
| `"grid"` | Regular grid | No | Lattice-like data |

> **Reproducibility tip:** the `"stress"` layout (from the graphlayouts dependency)
> is deterministic and force-directed-like — a strong default when you want a
> nice layout *without* depending on a seed. Prefer it when figure stability across
> machines matters more than the specific FR aesthetic.

---

## Coloring by Community

A frequent pattern: detect communities (see `community-detection.md`), attach
membership as a node attribute, color by it.

```r
# INTENT: color nodes by Louvain community on a seeded layout
set.seed(SEED)
comm <- cluster_louvain(g, weights = NA)
g <- g |> activate(nodes) |> mutate(community = as.factor(membership(comm)))

set.seed(SEED)   # seed the LAYOUT too (distinct stochastic step from detection)
ggraph(g, layout = "fr") +
  geom_edge_link(alpha = 0.3) +
  geom_node_point(aes(color = community), size = 4) +
  scale_color_brewer(palette = "Set2", name = "Community") +
  theme_void()
```

> **Two stochastic steps, two seeds.** Community detection *and* the force layout
> are each stochastic. Seed before the detection call and again before the ggraph
> build; otherwise one of the two can still vary between runs.

---

## Sizing Nodes by Centrality

```r
set.seed(SEED)
g <- g |> activate(nodes) |> mutate(btw = centrality_betweenness(weights = NA))

set.seed(SEED)
ggraph(g, layout = "fr") +
  geom_edge_link(alpha = 0.25) +
  geom_node_point(aes(size = btw), color = "steelblue") +
  scale_size(range = c(1, 8), name = "Betweenness") +
  theme_void()
```

---

## Directed Graphs: Arrows

```r
set.seed(SEED)
ggraph(g, layout = "fr") +
  geom_edge_link(
    arrow = arrow(length = unit(2, "mm"), type = "closed"),
    end_cap = circle(3, "mm"),          # stop the arrow short of the node
    alpha = 0.5
  ) +
  geom_node_point(size = 3) +
  theme_void()
```

---

## Building the Plot Object vs. Rendering

In DAAF pipelines, build the plot object and save it deliberately with `ggsave()`
following the figure-naming convention. A ggraph object is a ggplot object, so all
ggplot2 export machinery applies. Load the `ggplot2` skill for theme/scale/export
detail.

```r
# INTENT: build then save a reproducible network figure
set.seed(SEED)
p <- ggraph(g, layout = "fr") +
  geom_edge_link(alpha = 0.3) +
  geom_node_point(aes(color = community), size = 3) +
  theme_void()

ggsave(
  file.path(PROJECT_DIR, "output", "2026-07-15_collaboration_network.png"),
  p, width = 8, height = 6, dpi = 300
)
```

---

## End-to-End Pattern

```r
# --- Config ---
library(igraph); library(tidygraph); library(ggraph); library(ggplot2)
SEED <- 20260715

# --- Transform: community + centrality as node attributes ---
stopifnot(!("weight" %in% edge_attr_names(g)))   # unweighted; weights = NA below
set.seed(SEED); comm <- cluster_louvain(g, weights = NA)
g <- g |>
  activate(nodes) |>
  mutate(community = as.factor(membership(comm)),
         degree    = centrality_degree(mode = "all"))

# --- Visualize (seed the layout) ---
set.seed(SEED)
p <- ggraph(g, layout = "fr") +
  geom_edge_link(alpha = 0.3, color = "grey60") +
  geom_node_point(aes(color = community, size = degree)) +
  scale_color_brewer(palette = "Set2") +
  labs(title = "Network (Louvain communities, FR layout)") +
  theme_void()

# --- Validate the object built ---
stopifnot(inherits(p, "ggraph") || inherits(p, "ggplot"))
cat("Plot object built for", gorder(g), "nodes (seed =", SEED, ")\n")
```
