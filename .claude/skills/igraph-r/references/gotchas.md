# Gotchas

The traps that silently corrupt igraph results in R. Every item here is a
*silent* failure mode — the code runs, returns numbers, and the numbers are wrong.
Read this before trusting any centrality, community, or figure output.

---

## 1. Silent Weight Auto-Use (the flagship trap)

**Symptom:** centrality or community results look off, or your explicit `weights`
argument seems ignored, or unweighted analysis gives weighted numbers.

**Cause:** igraph functions **automatically consume an edge attribute named
`weight`** when the graph has one. This is documented behavior, not a bug. From the
official `betweenness()` reference:

> "If the graph has a `weight` edge attribute, then this is used by default."

The same holds for `closeness()`, `cluster_edge_betweenness()`, `cluster_leiden()`,
`cluster_louvain()`, `shortest_paths()`, and `distances()`.

**Worse:** for path-based measures (betweenness, closeness, shortest paths)
`weight` is treated as a **DISTANCE** — higher = longer path. If your `weight`
column encodes connection *strength* (higher = closer), the auto-use inverts the
meaning of every path-based result.

**Fix:**

```r
# Unweighted: pass weights = NA (NOT NULL — NULL triggers the auto-use fallback)
betweenness(g, weights = NA)
cluster_louvain(g, weights = NA)

# Weighted with strength semantics feeding a distance-based measure: convert first
E(g)$dist <- 1 / E(g)$weight          # strength -> distance
betweenness(g, weights = E(g)$dist)   # now correct

# Defensive check to run early:
if ("weight" %in% edge_attr_names(g))
  cat("Graph has 'weight' — it will be auto-used as a DISTANCE. Confirm intent.\n")
```

**`NA` vs `NULL`:** `weights = NULL` means "use the `weight` attribute if present"
(auto-use). `weights = NA` means "ignore weights entirely." For unweighted intent
always use `NA`.

---

## 2. Unseeded Stochastic Steps (irreproducible results)

**Symptom:** community partitions or figure layouts change every time you run the
script.

**Cause:** community detection (Louvain, Leiden, walktrap) and force-directed
layouts (`fr`, `kk`, `dh`, `lgl`) make randomized choices. Without a fixed seed the
result varies run to run.

**Fix:** `set.seed()` immediately before each stochastic call. Two stochastic steps
(e.g., detection then layout) need two seed calls.

```r
set.seed(20260715); comm <- cluster_louvain(g, weights = NA)   # seed detection
set.seed(20260715); p <- ggraph(g, layout = "fr") + geom_node_point()  # seed layout
```

> **`srand()` is dead.** igraph's old C-level `srand()` is deprecated — its `seed`
> parameter is documented as "Ignored." Do not use it. R's `set.seed()` is the only
> working mechanism at the R interface, because R igraph draws from R's RNG.

---

## 3. Leiden / Louvain on a Directed Graph

**Symptom:** `cluster_leiden()` or `cluster_louvain()` errors, or returns a
nonsensical partition, on a directed graph.

**Cause:** both functions require undirected input. The official docs state
plainly: *"The input graph. It must be undirected."*

**Fix:** convert with `as.undirected()` and document the collapse choice as a
modeling decision:

```r
# INTENT: Louvain requires undirected; collapse reciprocal directed edges to one
g_undir <- as.undirected(g, mode = "collapse")   # or "each" / "mutual"
set.seed(20260715); comm <- cluster_louvain(g_undir, weights = NA)
```

The mode (`"collapse"` / `"each"` / `"mutual"`) changes the result — see
`community-detection.md`. Never silently feed a directed graph to these functions.

---

## 4. Closeness / Betweenness on a Disconnected Graph

**Symptom:** closeness returns warnings, `Inf`/`NaN`, or values that aren't
comparable across nodes; diameter looks implausibly small.

**Cause:** closeness and betweenness are defined via shortest paths; across
disconnected components paths don't exist. Closeness "is not well-defined for
disconnected graphs." igraph computes over reachable nodes only and the numbers
stop being comparable.

**Fix:** check components first; restrict to the giant component or use
`harmonic_centrality()` (which handles unreachable nodes gracefully):

```r
comp <- components(g)
if (comp$no > 1) {
  giant <- induced_subgraph(g, which(comp$membership == which.max(comp$csize)))
  cc <- closeness(giant, weights = NA)          # well-defined now
  hc <- harmonic_centrality(g, weights = NA)    # alternative: whole graph, robust
}
```

See `centrality.md` and `paths-components.md` for the connectivity-first pattern.

---

## 5. Directed vs. Undirected Chosen by Accident

**Symptom:** degree/centrality numbers are double or half what you expect; a graph
you thought was mutual behaves asymmetrically.

**Cause:** `directed = TRUE` vs `FALSE` at construction is a substantive modeling
choice, but it's easy to accept the default without thinking. `graph_from_data_frame()`
defaults to `directed = TRUE`; `as_tbl_graph()` on an edge tibble also defaults to
directed. An edge list of undirected relationships read as directed will
mis-compute everything.

**Fix:** set `directed` explicitly and document *why*:

```r
# INTENT: friendships are mutual -> undirected
g <- as_tbl_graph(edges, directed = FALSE)
stopifnot(!is_directed(g))
```

On directed graphs, always set `mode` explicitly on `degree()`, `closeness()`,
`betweenness()` (`"in"` / `"out"` / `"all"`) — the default may not be what you want.

---

## 6. Bipartite Projection Creates a Strength-Weighted, Dense Graph

**Symptom:** after `bipartite_projection()`, centrality behaves oddly, or the graph
is far denser than the original two-mode structure.

**Cause:** projection (a) creates a `weight` attribute that is a **strength** (count
of shared neighbors), which then gets auto-used as a *distance* by path measures
(trap #1 in reverse); and (b) connects every pair sharing any neighbor, producing a
dense graph.

**Fix:** pass `weights = NA` for topology-only centrality, or convert the strength
to a distance; consider thresholding weak edges. See `bipartite.md`.

```r
proj <- bipartite_projection(g)$proj1
betweenness(proj, weights = NA)                 # topology only, safe
# or: proj_strong <- delete_edges(proj, E(proj)[weight < 2])
```

---

## 7. Function Renames Between igraph Versions

**Symptom:** "could not find function" for a name you're sure exists.

**Cause:** igraph 2.x renamed several functions. Notably
`graph_from_incidence_matrix()` → `graph_from_biadjacency_matrix()`. The skill
snapshot may drift from the installed version over time.

**Fix:** check the installed help (`?graph_from_biadjacency_matrix`) and prefer the
current name. Per DAAF's skill-information-awareness principle, when a documented
function name errors unexpectedly, verify against the installed package rather than
assuming the skill text is current.

---

## 8. tidygraph Wrappers Inherit igraph Behavior

**Symptom:** using `centrality_betweenness()` or `group_louvain()` from tidygraph
doesn't escape the weight/seed traps above.

**Cause:** tidygraph's centrality/community verbs are thin wrappers over the same
igraph routines. They inherit weight auto-use and seed sensitivity exactly.

**Fix:** apply the same discipline through the wrappers — pass `weights = NA`,
`set.seed()` before stochastic verbs:

```r
set.seed(20260715)
g <- g |>
  activate(nodes) |>
  mutate(btw = centrality_betweenness(weights = NA),   # weights = NA still required
         community = as.factor(group_louvain()))        # still stochastic -> seed above
```

---

## Quick Pre-Flight Checklist

Before trusting any result, confirm:

- [ ] Checked `edge_attr_names(g)` for `"weight"`; passed `weights = NA` if unweighted
- [ ] If weighted, confirmed strength-vs-distance semantics match the measure
- [ ] `set.seed()` before every community-detection and force-layout call
- [ ] Directed/undirected set explicitly and matches the phenomenon
- [ ] For Leiden/Louvain: graph is undirected (converted if needed)
- [ ] For closeness/betweenness/diameter: checked components; handled disconnection
- [ ] For projections: handled the strength-weighted, dense result
