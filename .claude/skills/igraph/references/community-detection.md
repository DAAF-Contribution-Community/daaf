# igraph Community Detection: Leiden, Louvain, Walktrap

This reference covers the three community-detection algorithms in scope, the
**mandatory seed discipline** that makes results reproducible, the
**directed-graph handling** rule (convert to undirected — the safe path), and
weighted community detection.

## Why Seed Discipline Is Mandatory

Community-detection algorithms make **stochastic** choices: local-moving methods
(Louvain, Leiden) visit vertices in a randomized order, so the partition they
return "depends on non-deterministic scheduling decisions." Two runs on the same
graph can yield different communities. The remedy is a **fixed, recorded seed**
before every community-detection call.

python-igraph's official tutorial pattern seeds Python's standard `random`
module:

```python
import random
random.seed(0)   # BEFORE any community-detection (or stochastic-layout) call
```

- Use `random.seed(N)` immediately before the community-detection call. This is
  the official, documented path.
- The advanced alternative `igraph.set_random_number_generator(rng)` injects a
  fully custom RNG object; use it only when you need a specific generator.
  `random.seed()` is sufficient and preferred for reproducibility.
- **Record the seed** in the script and report — an unrecorded seed defeats the
  purpose. Treat the seed as part of the method, not an incidental detail.

## Directed-Graph Handling: Convert to Undirected

Leiden and Louvain are formulated for **undirected** graphs. The R igraph
documentation states plainly that the input "must be undirected" for both
`cluster_leiden` and `cluster_louvain`. On the Python side, the directed
behavior of `community_leiden` / `community_multilevel` was **not verified** for
1.0.0 (the API page did not yield a definitive answer). Therefore:

- **Safe, portable path:** convert directed graphs to undirected with
  `Graph.as_undirected()` before community detection, and document the collapse
  semantics.
- **Do not assume** python-igraph silently handles directed input correctly for
  these algorithms. If you have a specific reason to run community detection
  directly on a directed graph, treat it as **verify-at-runtime**: test on a
  small known case and confirm the behavior before trusting it.

```python
# INTENT: guarantee undirected input for community detection.
# REASONING: Leiden/Louvain are undirected algorithms; the R docs require
#   undirected input and the Python directed behavior is unverified for 1.0.0.
#   Converting explicitly is the safe, portable path.
# ASSUMES: summing reciprocal-edge weights is the right collapse for this network.
if g.is_directed():
    g_u = g.as_undirected(mode="collapse", combine_edges={"weight": "sum"})
    print(f"converted directed -> undirected: {g_u.ecount()} edges")
else:
    g_u = g
```

## Louvain (Multilevel)

Louvain optimizes modularity by greedy local moves and hierarchical
agglomeration. In python-igraph it is `community_multilevel`.

```python
# --- Config ---
import igraph as ig
import random

# --- Detect ---
# INTENT: run Louvain reproducibly on the undirected graph with strength weights.
# REASONING: seeding before the call fixes the randomized vertex-visit order;
#   passing weights explicitly (strength — stronger ties pull nodes together)
#   avoids relying on unverified auto-use of the weight attribute.
# ASSUMES: g_u is undirected; weights are non-negative connection strengths.
random.seed(0)
louvain = g_u.community_multilevel(weights=g_u.es["weight"])
print(f"Louvain: {len(louvain)} communities, modularity={louvain.modularity:.4f}")
print(f"membership: {louvain.membership}")
```

## Leiden

The Leiden algorithm refines Louvain, guaranteeing well-connected communities.
Choose the objective function explicitly: `"modularity"` for the familiar
modularity objective (comparable to Louvain), or `"CPM"` (constant Potts model)
when you want a resolution-controlled partition.

```python
# INTENT: run Leiden reproducibly with the modularity objective.
# REASONING: Leiden fixes Louvain's badly-connected-community defect; using the
#   modularity objective makes its result directly comparable to the Louvain run.
#   Seeding fixes the stochastic vertex ordering.
# ASSUMES: objective_function="modularity" is desired; for CPM set a resolution.
random.seed(0)
leiden = g_u.community_leiden(
    objective_function="modularity",
    weights=g_u.es["weight"],
)
print(f"Leiden: {len(leiden)} communities, modularity={leiden.modularity:.4f}")
```

> **CPM note:** with `objective_function="CPM"`, also pass a
> `resolution=` value — higher resolution yields more, smaller communities. CPM
> modularity is not directly comparable to the modularity-objective value, so
> compare CPM partitions to each other, not to Louvain.

## Walktrap

Walktrap finds communities via short random walks (walks tend to stay within
dense regions). It returns a dendrogram; cut it to a flat clustering with
`.as_clustering()`.

```python
# INTENT: run Walktrap and cut the dendrogram to a flat partition.
# REASONING: walktrap uses random walks (steps=4 default); seeding keeps the
#   result reproducible, and as_clustering() cuts the hierarchy at the modularity-
#   maximizing level unless a specific cut is requested.
# ASSUMES: steps=4 is a reasonable default walk length for this graph size.
random.seed(0)
wt_dendro = g_u.community_walktrap(weights=g_u.es["weight"], steps=4)
walktrap = wt_dendro.as_clustering()
print(f"Walktrap: {len(walktrap)} communities, modularity={walktrap.modularity:.4f}")
```

## Comparing Partitions

To compare two partitions of the same graph (e.g., Louvain vs. Leiden), use an
external clustering-agreement index:

```python
# INTENT: quantify agreement between two partitions.
# REASONING: NMI/ARI summarize how similar two community assignments are,
#   independent of label permutation; useful for method-robustness reporting.
# ASSUMES: both memberships cover the same vertex set in the same order.
nmi = ig.compare_communities(louvain.membership, leiden.membership, method="nmi")
print(f"Louvain vs Leiden NMI: {nmi:.3f}")
```

## Attaching Community Membership Back to Data

Membership is a list aligned with `g_u.vs` order — attach it as a node attribute
or a Polars column for downstream analysis (e.g., testing whether communities
predict an outcome). See `dataframe-interop.md`.

```python
g_u.vs["community"] = louvain.membership
```

## Reproducibility Checklist for Community Detection

- [ ] `random.seed(N)` called immediately before the detection call, with `N` recorded.
- [ ] Directed graphs converted to undirected via `as_undirected()` (collapse semantics documented).
- [ ] Weights passed explicitly (`weights=...`), not relied upon by auto-use.
- [ ] Objective function / walk length recorded (Leiden objective, Walktrap steps).
- [ ] Modularity and community count reported for auditability.

## Method-Specific Citation

The Leiden algorithm has its own methods paper; cite it when Leiden results are
central to the analysis, in addition to the igraph software citation:

> Traag, V. A., Waltman, L., & van Eck, N. J. (2019). From Louvain to Leiden: guaranteeing well-connected communities. *Scientific Reports*, 9, 5233.

See the SKILL.md Citation section and `agent_reference/CITATION_REFERENCE.md` for
software attribution propagation.
