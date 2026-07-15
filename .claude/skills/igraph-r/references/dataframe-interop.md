# DataFrame Interop: Graphs and Tibbles

Moving between graphs and tidy tables via tidygraph's `activate()` and
`as_tibble()`, attaching computed attributes back to nodes/edges, and running
dplyr verbs on graph tables. This is the bridge between network computation and
DAAF's tidyverse downstream statistics.

---

## The Active Table Concept

A `tbl_graph` contains two tables — nodes and edges. `activate()` selects which
one dplyr verbs (and `as_tibble()`) operate on. The active table is a piece of
graph state; verbs after `activate(nodes)` touch nodes, verbs after
`activate(edges)` touch edges.

```r
library(igraph)
library(tidygraph)
library(dplyr)

g <- as_tbl_graph(
  tibble(from = c("A","A","B","C"), to = c("B","C","C","D")),
  directed = FALSE
)

# Extract node table
node_tbl <- g |> activate(nodes) |> as_tibble()
#> # A tibble: 4 x 1 : name

# Extract edge table
edge_tbl <- g |> activate(edges) |> as_tibble()
#> # A tibble: 4 x 2 : from, to  (from/to are INTEGER node indices, not names)
```

> **Endpoint columns are indices, not names.** In the extracted edge table `from`
> and `to` are 1-based integer positions into the node table. To get names back,
> either join to the node table on the index or use
> `igraph::as_data_frame(g, what = "edges")`, which returns name-based endpoints.

---

## Attaching Computed Attributes Back to Nodes

The core downstream-stats pattern: compute a graph-level quantity (centrality,
community membership), attach it as a node attribute, extract the enriched node
table for regression/plotting.

```r
# INTENT: attach degree and betweenness as node columns for downstream modeling
# ASSUMES: unweighted graph — betweenness with weights = NA (no 'weight' attr)
stopifnot(!("weight" %in% edge_attr_names(g)))

g <- g |>
  activate(nodes) |>
  mutate(
    degree      = centrality_degree(mode = "all"),
    betweenness = centrality_betweenness(weights = NA)  # tidygraph wrapper; passes to igraph
  )

# Extract for downstream stats
model_data <- g |> activate(nodes) |> as_tibble()
stopifnot(all(c("degree", "betweenness") %in% names(model_data)))
```

The tidygraph wrappers (`centrality_degree()`, `centrality_betweenness()`,
`centrality_closeness()`, `centrality_eigen()`, `centrality_pagerank()`) call the
same igraph routines and inherit the same weight/seed behavior — pass `weights =
NA` for unweighted graphs exactly as with the raw igraph functions. See
`centrality.md`.

---

## Raw igraph Attribute Assignment (Escape Hatch)

When a computation is easier with raw igraph, assign the result to `V(g)$attr` or
`E(g)$attr` directly. A `tbl_graph` is an igraph object, so this works:

```r
# Raw-igraph assignment: compute with igraph, store as a node attribute
V(g)$pagerank <- page_rank(g)$vector

# Then continue in tidygraph
model_data <- g |> activate(nodes) |> as_tibble()
stopifnot("pagerank" %in% names(model_data))
```

Both styles interoperate freely on the same object — use whichever is clearer for
the step at hand.

---

## dplyr Verbs on Graph Tables

Standard dplyr verbs work on the active table. This is powerful for filtering
subgraphs, recoding attributes, or joining external metadata.

```r
# Filter nodes by an attribute (creates a subgraph; incident edges follow)
core <- g |>
  activate(nodes) |>
  filter(degree >= 2)

# Join external node metadata (e.g., department lookup)
dept_lookup <- tibble(name = c("A","B","C","D"), dept = c("x","x","y","y"))
g <- g |>
  activate(nodes) |>
  left_join(dept_lookup, by = "name")

# Recode / mutate edge attributes
g <- g |>
  activate(edges) |>
  mutate(is_cross_dept = .N()$dept[from] != .N()$dept[to])  # .N() accesses the node table
```

> **`.N()` and `.E()` accessors:** inside an edge-context `mutate()`, `.N()` returns
> the node table so you can look up endpoint attributes by index (`.N()$dept[from]`).
> Symmetrically, `.E()` accesses the edge table from a node context. These make
> edge-level features that depend on node attributes expressible in one pipe.

---

## Filtering a Subgraph and Round-Tripping

```r
# INTENT: extract the largest connected component as a tibble pair for archiving
comp <- components(g)
giant_id <- which.max(comp$csize)

g_giant <- g |>
  activate(nodes) |>
  mutate(.comp = comp$membership) |>
  filter(.comp == giant_id) |>
  activate(nodes) |>
  select(-.comp)

# Persist as parquet tables (DAAF convention)
library(arrow)
write_parquet(g_giant |> activate(nodes) |> as_tibble(),
              file.path(PROJECT_DIR, "data", "giant_nodes.parquet"))
write_parquet(igraph::as_data_frame(g_giant, what = "edges"),
              file.path(PROJECT_DIR, "data", "giant_edges.parquet"))
```

Using `igraph::as_data_frame(g, what = "edges")` for the edge export gives
**name-based** `from`/`to` columns, which reconstruct correctly without an index
join — the preferred form for archived edge tables.

---

## Validation Patterns

```r
# Node table row count equals graph order
stopifnot(nrow(g |> activate(nodes) |> as_tibble()) == gorder(g))

# Edge table row count equals graph size
stopifnot(nrow(g |> activate(edges) |> as_tibble()) == gsize(g))

# No node attribute silently dropped after a join
before <- vertex_attr_names(g)
g <- g |> activate(nodes) |> left_join(dept_lookup, by = "name")
stopifnot("dept" %in% vertex_attr_names(g))
cat("Attributes after join:", paste(vertex_attr_names(g), collapse = ", "), "\n")
```
