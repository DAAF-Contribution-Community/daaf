# Centrality

Node-importance measures: degree, betweenness, closeness, eigenvector, and
PageRank. Two guardrails dominate this file: the **silent weight auto-use** trap
and the **disconnected-graph** trap. Read both before trusting any centrality
number.

---

## The Weight Auto-Use Guardrail (read first)

igraph functions **automatically use an edge attribute named `weight`** when the
graph has one. The official `betweenness()` reference states:

> "Optional positive weight vector for calculating weighted betweenness. **If the
> graph has a `weight` edge attribute, then this is used by default.**"

The same auto-use language holds for `closeness()`, `cluster_edge_betweenness()`,
`cluster_leiden()`, and `cluster_louvain()`.

Two consequences:

1. **Weights are treated as DISTANCES, not strengths.** A higher `weight` means a
   *longer* path. If your `weight` column encodes connection *strength* (higher =
   more connected), passing it directly inverts the meaning of betweenness and
   closeness. Convert first (e.g., `distance = 1 / strength`) and document it.
2. **To force an unweighted calculation, pass `weights = NA`** — not `NULL`.
   `NULL` triggers the auto-use fallback; `NA` explicitly disables weighting.

```r
library(igraph)
library(tidygraph)

# --- Unweighted intent: ALWAYS make it explicit ---
# INTENT: unweighted betweenness; weights = NA disables silent auto-use
# ASSUMES: even if a 'weight' attribute exists, we want topology-only betweenness
bc <- betweenness(g, weights = NA)

# --- Weighted intent: state the distance interpretation ---
# INTENT: weighted betweenness where E(g)$weight is a DISTANCE (higher = longer)
# REASONING: our weights come from travel time, which is already a distance
# ASSUMES: weights are positive and distance-semantic; no conversion needed
bc_w <- betweenness(g, weights = E(g)$weight)
```

**Defensive check to run before any centrality call:**

```r
if ("weight" %in% edge_attr_names(g)) {
  cat("Graph has 'weight' — pass weights = NA for unweighted, or confirm distance semantics.\n")
}
```

---

## Directedness and the `mode` Argument

For directed graphs, `degree()`, `closeness()`, and `betweenness()` take a `mode`
argument controlling which edge directions count:

```r
degree(g, mode = c("all", "out", "in", "total"))
```

- `"in"` — indegree (edges pointing *to* the node)
- `"out"` — outdegree (edges pointing *from* the node)
- `"all"` / `"total"` — both directions combined

On an **undirected** graph `mode` is ignored (all edges count once). On a
**directed** graph the choice is substantive — pick it deliberately and document
it. `"all"` is the common default when direction is not the analytical focus.

---

## Degree Centrality

The count of a node's edges — the simplest and most robust centrality.

```r
# Raw igraph
deg_all <- degree(g, mode = "all")
deg_in  <- degree(g, mode = "in")    # directed graphs only meaningful
deg_out <- degree(g, mode = "out")

# tidygraph (attach as node attribute)
g <- g |>
  activate(nodes) |>
  mutate(degree = centrality_degree(mode = "all"))

# Handshake-lemma sanity check (undirected): sum of degrees = 2 * edge count
stopifnot(sum(degree(g, mode = "all")) == 2 * gsize(g))
```

`normalized = TRUE` divides by the maximum possible degree (`gorder(g) - 1`),
giving a 0–1 scale comparable across graphs of different sizes.

---

## Betweenness Centrality

Fraction of shortest paths through a node — captures "brokerage" / bridging.

```r
# INTENT: unweighted betweenness; weights = NA (topology only)
bc <- betweenness(g, weights = NA, directed = is_directed(g))

# tidygraph
g <- g |> activate(nodes) |> mutate(betweenness = centrality_betweenness(weights = NA))
```

**Two cautions:**

1. **Disconnected graphs** (see below) — betweenness only counts reachable pairs.
2. **Not a resilience metric.** Betweenness is frequently misused as a proxy for
   network resilience or a node's "importance to connectivity." It is a
   shortest-path-brokerage measure, not a validated resilience measure — do not
   present high betweenness as evidence of criticality without a resilience-specific
   analysis.

---

## Closeness Centrality

Inverse of the mean shortest-path distance to all other nodes — how "central" a
node is in reachability terms.

```r
# INTENT: unweighted closeness; weights = NA
cc <- closeness(g, weights = NA, mode = "all")

# tidygraph
g <- g |> activate(nodes) |> mutate(closeness = centrality_closeness(weights = NA))
```

> **Closeness is ill-defined on disconnected graphs.** If any node is unreachable,
> its distance is infinite and the mean is undefined. igraph computes closeness over
> reachable nodes only and **warns**; the resulting numbers are not comparable
> across components. Check connectivity first (next section) and, if disconnected,
> compute closeness per component or use `harmonic_centrality()` (which is
> well-defined with unreachable nodes, contributing 0).

---

## Eigenvector Centrality

A node is important if its neighbors are important — recursive influence.

```r
# INTENT: unweighted eigenvector centrality; weights = NA
ec <- eigen_centrality(g, weights = NA, directed = is_directed(g))$vector

# tidygraph
g <- g |> activate(nodes) |> mutate(eigen = centrality_eigen(weights = NA))
```

Here weights, if used, are **connection strengths** (higher = stronger tie) —
the opposite semantics from the distance-based betweenness/closeness. This is a
subtle asymmetry: for eigenvector centrality a large `weight` increases influence;
for betweenness/closeness a large `weight` lengthens paths. Be explicit about which
semantics your `weight` column carries and which measures you feed it to.

Eigenvector centrality is best behaved on connected, undirected graphs; on directed
or disconnected graphs interpret with care (PageRank is often the better choice for
directed graphs).

---

## PageRank

A random-walk-based influence measure; robust on directed graphs (its original
domain) and does not require connectivity.

```r
pr <- page_rank(g)$vector          # returns a list; $vector is the score
g <- g |> activate(nodes) |> mutate(pagerank = centrality_pagerank())

# PageRank scores sum to 1 (a probability distribution over nodes)
stopifnot(abs(sum(page_rank(g)$vector) - 1) < 1e-8)
```

For weighted PageRank, `weight` is a **strength** (higher = more walk probability),
matching eigenvector semantics, not distance semantics.

---

## The Disconnected-Graph Guardrail

Betweenness and closeness are ill-defined across components. **Check connectivity
before computing them:**

```r
# INTENT: guard centrality against silent disconnection artifacts
comp <- components(g)
if (comp$no > 1) {
  cat("WARNING: graph has", comp$no, "components; closeness/betweenness cross-",
      "component values are not comparable.\n")
  # Option A: analyze the giant component only
  giant_id <- which.max(comp$csize)
  g_giant <- induced_subgraph(g, which(comp$membership == giant_id))
  cc <- closeness(g_giant, weights = NA)
  # Option B: use harmonic centrality (well-defined with unreachable nodes)
  hc <- harmonic_centrality(g, weights = NA)
}
stopifnot(exists("comp"))
cat("Components:", comp$no, " Giant size:", max(comp$csize), "\n")
```

---

## Choosing a Measure

| Measure | Captures | Weight semantics | Disconnected-graph safety |
|---------|----------|------------------|---------------------------|
| Degree | Local connectivity | count / strength | Safe |
| Betweenness | Shortest-path brokerage | **distance** | Only reachable pairs — check components |
| Closeness | Reachability centrality | **distance** | Ill-defined — use harmonic or per-component |
| Eigenvector | Recursive influence | **strength** | Fragile on disconnected/directed |
| PageRank | Random-walk influence | **strength** | Safe (handles directed & disconnected) |
| Harmonic | Reachability (robust) | **distance** | Safe (unreachable contribute 0) |

**Rule of thumb:** on a connected undirected graph any measure is fine; on a
directed graph prefer PageRank; on a disconnected graph prefer degree, PageRank,
or harmonic centrality, and never compare raw closeness across components.
