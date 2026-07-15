# Community Detection

Partitioning a graph into groups of densely connected nodes: Louvain, Leiden, and
walktrap. Two disciplines are mandatory here: **seed setting** (these algorithms
are stochastic) and the **undirected requirement** (Leiden and Louvain require an
undirected graph). The weight auto-use trap from `centrality.md` applies here too.

---

## Seed Discipline (mandatory)

Louvain, Leiden, and walktrap make randomized choices — they "visit vertices in
random order," so results "depend on non-deterministic scheduling decisions."
Without a fixed seed, two runs on the same graph can return different partitions,
breaking reproducibility.

**Set `set.seed()` immediately before every community-detection call.** igraph's
old C-level `srand()` is deprecated and ignored at the R interface — the official
doc lists its `seed` parameter as "Ignored." R's own RNG via `set.seed()` is the
correct and only mechanism.

```r
library(igraph)
library(tidygraph)

SEED <- 20260715
set.seed(SEED)                        # REQUIRED before the stochastic call
comm <- cluster_louvain(g, weights = NA)
```

Record the seed in the script and, ideally, in the report — a partition is only
reproducible if the seed that produced it is documented.

---

## The Undirected Requirement (Leiden & Louvain)

The official `cluster_leiden()` and `cluster_louvain()` docs both state:

> "The input graph. **It must be undirected.**"

A directed graph will error or silently mishandle. Convert first with
`as.undirected()`, and document the collapse strategy as a modeling choice:

```r
# INTENT: Louvain requires undirected input; collapse directed edges
# REASONING: for community structure we treat A->B and B->A as one mutual tie
# ASSUMES: direction is not analytically meaningful for the grouping question
g_undir <- as.undirected(g, mode = "collapse")   # merge reciprocal edges into one
set.seed(SEED)
comm <- cluster_louvain(g_undir, weights = NA)
```

`as.undirected()` modes:

| Mode | Behavior | When |
|------|----------|------|
| `"collapse"` | A→B and B→A become a single undirected edge | Default; treat reciprocal ties as one |
| `"each"` | Every directed edge becomes an undirected edge (keeps multiplicity) | When edge count/multiplicity matters |
| `"mutual"` | Keep only edges that are reciprocated | When only mutual ties count as ties |

The collapse choice is substantive — `"collapse"` vs `"mutual"` can change which
nodes end up grouped. State the choice and its rationale in an IAT comment.

---

## The Weight Auto-Use Trap (again)

As with centrality, `cluster_leiden()`, `cluster_louvain()`, and
`cluster_edge_betweenness()` **auto-consume a `weight` edge attribute** and treat
it as a distance. From `cluster_leiden()`:

> "If it is NULL and the input graph has a 'weight' edge attribute, then that
> attribute will be used."

Pass `weights = NA` for unweighted community detection; pass an explicit weight
vector (documenting distance semantics) for weighted.

---

## Louvain

Fast modularity maximization — the standard first choice for undirected graphs.

```r
set.seed(SEED)
comm_louvain <- cluster_louvain(g_undir, weights = NA)

membership(comm_louvain)          # integer community id per node
length(comm_louvain)              # number of communities
sizes(comm_louvain)               # nodes per community
modularity(comm_louvain)          # partition quality (see below)

# Attach membership as a node attribute
g_undir <- g_undir |>
  activate(nodes) |>
  mutate(community = as.factor(membership(comm_louvain)))
```

---

## Leiden

An improvement on Louvain that guarantees well-connected communities. The R
`cluster_leiden()` defaults to the CPM objective; for modularity-comparable
results set `objective_function = "modularity"`.

```r
set.seed(SEED)
comm_leiden <- cluster_leiden(
  g_undir,
  objective_function = "modularity",   # match Louvain's objective for comparability
  weights = NA                         # unweighted; suppress auto-use
)
cat("Leiden communities:", length(comm_leiden),
    " Modularity:", round(modularity(g_undir, membership(comm_leiden), weights = NA), 3), "\n")
```

> **Note:** with the CPM objective (`cluster_leiden()`'s default), the
> `resolution_parameter` strongly controls the number of communities, and
> `modularity()` is not the objective being optimized. Use
> `objective_function = "modularity"` when you want a modularity-based partition
> comparable to Louvain, and vary `resolution_parameter` deliberately.

---

## Walktrap

Community detection via short random walks — walks tend to stay within dense
regions. Works on undirected graphs; more computationally intensive on large graphs.

```r
set.seed(SEED)
comm_wt <- cluster_walktrap(g_undir, weights = NA, steps = 4)
cat("Walktrap communities:", length(comm_wt),
    " Modularity:", round(modularity(comm_wt), 3), "\n")
```

`steps` controls walk length (default 4); longer walks tend to find larger
communities.

---

## Modularity: Evaluating a Partition

Modularity measures how much more densely nodes connect within communities than
expected at random. Range roughly −0.5 to 1; higher is stronger community
structure. Use it to compare partitions **on the same graph** (not across graphs).

```r
# From a communities object
modularity(comm_louvain)

# From a raw membership vector (must pass the same weights argument used to detect)
modularity(g_undir, membership(comm_louvain), weights = NA)

# Compare algorithms on the same graph
set.seed(SEED); m_louvain <- modularity(cluster_louvain(g_undir, weights = NA))
set.seed(SEED); m_walktrap <- modularity(cluster_walktrap(g_undir, weights = NA))
cat("Louvain:", round(m_louvain, 3), " Walktrap:", round(m_walktrap, 3), "\n")
```

> **Interpretation caution:** modularity has a known *resolution limit* — it can fail
> to detect communities smaller than a scale set by the total graph size, merging
> genuinely separate small groups. High modularity is evidence of structure, not
> proof that the partition is "correct." Corroborate with domain knowledge and, where
> relevant, resolution-parameter sweeps (Leiden CPM).

---

## End-to-End Pattern

```r
# --- Config ---
library(igraph)
library(tidygraph)
SEED <- 20260715

# --- Transform ---
# INTENT: detect communities on an undirected, unweighted collaboration graph
# REASONING: Louvain requires undirected; collapse reciprocal ties
# ASSUMES: no 'weight' attribute (verified); direction not meaningful for grouping
stopifnot(!("weight" %in% edge_attr_names(g)))
g_undir <- if (is_directed(g)) as.undirected(g, mode = "collapse") else g

set.seed(SEED)   # stochastic — seed for reproducibility
comm <- cluster_louvain(g_undir, weights = NA)

g_undir <- g_undir |> activate(nodes) |> mutate(community = as.factor(membership(comm)))

# --- Validate ---
stopifnot(length(membership(comm)) == gorder(g_undir))
cat("Communities:", length(comm), " Modularity:", round(modularity(comm), 3),
    " (seed =", SEED, ")\n")

# --- Summary ---
node_tbl <- g_undir |> activate(nodes) |> as_tibble()
print(dplyr::count(node_tbl, community))
```
