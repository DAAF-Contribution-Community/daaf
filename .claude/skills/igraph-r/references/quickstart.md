# Quickstart: Building and Inspecting Graphs

Constructing graphs from edge-list tibbles, the tidyverse round-trip, graph I/O,
and basic inspection. This is the entry point — most network work starts by
turning a pair of tables (edges, optionally nodes) into a graph.

---

## The Data Model

A graph is two tables:

- **Edge table**: one row per edge. The first two columns name the endpoints
  (conventionally `from` and `to`); further columns are edge attributes (e.g.,
  `weight`, `year`).
- **Node table** (optional): one row per node, keyed by the node name. Columns are
  node attributes (e.g., `department`, `type`). If omitted, nodes are inferred from
  the endpoints that appear in the edge table.

tidygraph's `tbl_graph` holds both tables and lets dplyr verbs operate on each.
Any igraph function that expects a graph also accepts a `tbl_graph` — there is no
conversion cost.

---

## Constructing a Graph from an Edge-List Tibble

```r
# --- Config ---
library(igraph)
library(tidygraph)
library(dplyr)

# --- Load ---
# INTENT: Build an undirected co-occurrence graph from an edge tibble
# ASSUMES: 'edges' has columns 'from' and 'to' (first two cols name endpoints)
edges <- tibble(
  from = c("A", "A", "B", "C", "C"),
  to   = c("B", "C", "C", "D", "E")
)

# tidygraph route (preferred in DAAF's R house style)
g <- as_tbl_graph(edges, directed = FALSE)

# Raw igraph route (identical result; use when you need igraph-only options)
g_ig <- graph_from_data_frame(edges, directed = FALSE)

cat("Nodes:", gorder(g), " Edges:", gsize(g), "\n")   # gorder = vertex count, gsize = edge count
```

`directed = FALSE` vs `TRUE` is a modeling decision, not a formatting one — it
changes what centrality and community algorithms compute. Choose it deliberately
and document the choice in an IAT comment. See `gotchas.md` for the traps.

---

## Edge List + Separate Node Table

When nodes carry attributes (or some nodes have no edges and would otherwise be
dropped), supply an explicit node table. With `graph_from_data_frame()` the node
table's **first column is the node key**; remaining columns become node attributes.

```r
nodes <- tibble(
  name = c("A", "B", "C", "D", "E", "F"),  # F is isolated — kept only via explicit node table
  dept = c("x", "x", "y", "y", "z", "z")
)

# INTENT: Keep isolated node F and attach the 'dept' attribute to every node
g_ig <- graph_from_data_frame(edges, directed = FALSE, vertices = nodes)
stopifnot(gorder(g_ig) == 6)  # F retained

# tidygraph equivalent: pass both tables
g <- tbl_graph(nodes = nodes, edges = edges, directed = FALSE, node_key = "name")
```

> **Why the explicit node table matters:** without it, node F (which appears in no
> edge) does not exist in the graph, and any per-node summary silently undercounts.

---

## The Round-Trip: Graph Back to Tidy Tables

The defining feature of tidygraph — pull either table back out as a plain tibble
for downstream statistics (see `dataframe-interop.md` for the full treatment):

```r
node_tbl <- g |> activate(nodes) |> as_tibble()
edge_tbl <- g |> activate(edges) |> as_tibble()

# Round-trip identity check: reconstruct the same graph from the extracted tables
g2 <- tbl_graph(nodes = node_tbl, edges = edge_tbl, directed = FALSE)
stopifnot(gorder(g2) == gorder(g))
stopifnot(gsize(g2) == gsize(g))
cat("Round-trip preserved:", gorder(g2), "nodes,", gsize(g2), "edges\n")
```

> **Note on edge endpoints after round-trip:** when you `activate(edges) |>
> as_tibble()`, the `from`/`to` columns are **integer node indices**, not the
> original names. To recover names, join back to the node table on the index, or
> use `igraph::as_data_frame(g, what = "edges")` which returns name-based endpoints.

---

## Inspecting a Graph

```r
gorder(g)                 # number of nodes (vertices)
gsize(g)                  # number of edges
is_directed(g)            # TRUE/FALSE
is_connected(g)           # single connected component?
vertex_attr_names(g)      # node attribute names
edge_attr_names(g)        # edge attribute names — CHECK for "weight" (see below)
V(g)$name                 # node names
head(igraph::as_data_frame(g, what = "edges"))  # edge table with named endpoints
```

**Always check `edge_attr_names(g)` early.** If it includes `"weight"`, then
centrality and community functions will auto-consume it as a **distance** unless
you pass `weights = NA` (see `centrality.md` and `gotchas.md`). This one check
prevents the most common silent error in igraph.

```r
# INTENT: Confirm whether a 'weight' attribute is present before running centrality
if ("weight" %in% edge_attr_names(g)) {
  cat("WARNING: graph has a 'weight' attribute — it will be auto-used as a distance.\n")
} else {
  cat("No 'weight' attribute — unweighted analysis is the default.\n")
}
```

---

## Graph I/O

DAAF stores tabular data as parquet, so the durable, reproducible pattern is to
**persist the edge and node tibbles as parquet** and reconstruct the graph in each
script — not to serialize the graph object. This keeps the audit trail readable.

```r
library(arrow)

# Save (the reproducible pattern — tables, not the graph object)
write_parquet(edge_tbl, file.path(PROJECT_DIR, "data", "edges.parquet"))
write_parquet(node_tbl, file.path(PROJECT_DIR, "data", "nodes.parquet"))

# Reload and rebuild
edges2 <- read_parquet(file.path(PROJECT_DIR, "data", "edges.parquet"))
nodes2 <- read_parquet(file.path(PROJECT_DIR, "data", "nodes.parquet"))
g <- tbl_graph(nodes = nodes2, edges = edges2, directed = FALSE, node_key = "name")
```

For interchange with other graph tools, igraph can read/write GraphML, GML, and
edgelist formats via `read_graph()` / `write_graph()` — but for DAAF pipelines the
parquet-tables pattern above is preferred (it stays inside the parquet-only
convention and is directly auditable).

---

## Minimal End-to-End Example

```r
# --- Config ---
library(igraph)
library(tidygraph)
library(dplyr)

# --- Load ---
edges <- tibble(from = c("A","A","B","C","C","D"), to = c("B","C","C","D","E","E"))
g <- as_tbl_graph(edges, directed = FALSE)

# --- Transform ---
# INTENT: attach degree as a node attribute; unweighted so weights = NA is implicit
#         (no 'weight' attribute present — verified below)
stopifnot(!("weight" %in% edge_attr_names(g)))
g <- g |> activate(nodes) |> mutate(deg = centrality_degree(mode = "all"))

# --- Validate ---
deg_tbl <- g |> activate(nodes) |> as_tibble()
stopifnot(nrow(deg_tbl) == gorder(g))
stopifnot(sum(deg_tbl$deg) == 2 * gsize(g))  # handshake lemma: sum of degrees = 2E

# --- Summary ---
cat("Nodes:", gorder(g), " Edges:", gsize(g), "\n")
print(deg_tbl)
```
