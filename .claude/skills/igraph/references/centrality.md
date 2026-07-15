# igraph Centrality: Degree, Betweenness, Closeness, Eigenvector, PageRank

This reference covers the five centrality families in scope, the directed-graph
`mode` argument, explicit weight handling, and the **connectivity guardrail** —
the single most important correctness check before running closeness or
betweenness.

## The Connectivity Guardrail (Read First)

Closeness and betweenness are defined in terms of shortest paths between pairs of
nodes. **On a disconnected graph, paths between nodes in different components do
not exist**, so these measures are ill-defined or misleading: closeness for a
node can only "see" its own component, and cross-component pairs contribute
nothing to betweenness. Always check components before interpreting these
measures, and decide deliberately whether to restrict to the giant component.

```python
# --- Config ---
import igraph as ig

# --- Validate connectivity BEFORE centrality ---
# INTENT: refuse to interpret closeness/betweenness on a silently disconnected
#   graph; report component structure so the choice is explicit and auditable.
# REASONING: closeness "is not well-defined for disconnected graphs" — a node's
#   value reflects only its own component. Reporting the component count forces a
#   conscious decision rather than a silently wrong number.
# ASSUMES: weak components are the right notion for an undirected analysis; for
#   directed reachability use mode="strong".
comp = g.connected_components(mode="weak")
print(f"components: {len(comp)}  sizes: {sorted((len(c) for c in comp), reverse=True)}")
if len(comp) > 1:
    print("WARNING: graph is disconnected — closeness/betweenness are per-component.")
    print("Decide: restrict to the giant component, or interpret within-component.")
```

Restricting to the giant component when that is the intended scope:

```python
# INTENT: analyze the largest connected component only.
# REASONING: many network questions concern the connected core; documenting the
#   restriction (and how many nodes it drops) keeps the analysis honest.
giant = g.connected_components(mode="weak").giant()
print(f"giant component: {giant.vcount()} of {g.vcount()} nodes "
      f"({giant.vcount()/g.vcount():.1%})")
```

## Weights Are Distances, Not Strengths

A recurring trap: igraph treats edge `weight` in **path-based** measures
(betweenness, closeness) as **distance** — a higher weight means a *longer*, more
costly path. If your weights encode connection *strength* (bigger = closer),
they are backwards for these measures and must be inverted first.

```python
# INTENT: convert strength weights to distance weights for path-based centrality.
# REASONING: betweenness/closeness read weight as distance; a strength of 5
#   should shorten, not lengthen, a path. Inverting maps strength→distance.
# ASSUMES: all strengths are strictly positive (guard against divide-by-zero).
assert all(w > 0 for w in g.es["strength"]), "strengths must be positive to invert"
g.es["distance"] = [1.0 / w for w in g.es["strength"]]
```

**Practice adopted throughout this skill:** always pass `weights=` explicitly.
The auto-use of a `weight` attribute is verified for the R binding; the
equivalent auto-use behavior in python-igraph was **not verified**, so relying on
it is a portability and clarity hazard. Passing `weights=` (or `weights=None` for
an explicitly unweighted call) makes every example unambiguous.

## Directed Mode

Degree and the directed centralities take a `mode` argument:

| `mode=` | Meaning |
|---------|---------|
| `"in"` | Incoming edges (indegree / inbound importance) |
| `"out"` | Outgoing edges (outdegree / outbound importance) |
| `"all"` | Both directions combined (undirected-equivalent) |

## Degree Centrality

Degree is the count of incident edges — the simplest centrality, well-defined
even on disconnected graphs.

```python
# INTENT: compute in/out/all degree on a directed graph.
# REASONING: on directed data the three modes answer different questions
#   (received ties vs. sent ties vs. total involvement); reporting all three
#   avoids conflating them.
# ASSUMES: g is directed; on an undirected graph the three modes coincide.
indeg = g.degree(mode="in")
outdeg = g.degree(mode="out")
alldeg = g.degree(mode="all")
for name, i, o, a in zip(g.vs["name"], indeg, outdeg, alldeg):
    print(f"{name:>6}  in={i}  out={o}  all={a}")

# Weighted degree (strength) — sum of incident edge weights, NOT a path measure,
# so weights here mean strength and are used directly.
strength = g.strength(mode="all", weights=g.es["weight"])
print(f"weighted degree (strength): {dict(zip(g.vs['name'], strength))}")
```

## Betweenness Centrality

Fraction of shortest paths passing through each node — captures brokerage/bridge
roles. **Guardrail:** only meaningful after the connectivity check above. Also
note that betweenness is *not* a valid measure of network resilience — do not
present it as one.

```python
# INTENT: rank nodes by weighted betweenness within the connected component.
# REASONING: betweenness identifies brokers; passing weights=distance makes the
#   shortest-path definition explicit. Directed graphs honor edge direction.
# ASSUMES: `distance` is a distance-scaled weight (strength already inverted).
bet = giant.betweenness(weights=giant.es["distance"], directed=giant.is_directed())
ranked = sorted(zip(giant.vs["name"], bet), key=lambda t: t[1], reverse=True)
print("top betweenness:", ranked[:5])
```

## Closeness Centrality

Inverse of the mean shortest-path distance to all reachable nodes — captures how
efficiently a node reaches the rest. **Guardrail:** ill-defined across
components; compute on the giant component (or interpret strictly
within-component) and pass weights as distances.

```python
# INTENT: closeness on the giant component with distance weights.
# REASONING: closeness on a disconnected graph only "sees" a node's own
#   component; restricting to the giant component makes the value interpretable.
# ASSUMES: giant is a single connected component (guaranteed by .giant()).
clo = giant.closeness(weights=giant.es["distance"], mode="all")
print("closeness (giant):", dict(zip(giant.vs["name"], (round(c, 3) for c in clo))))
```

## Eigenvector Centrality

Importance defined recursively — a node is central if connected to central
nodes. Here weights mean **strength** (a stronger tie transmits more importance),
so pass the raw strength weights, not the inverted distances.

```python
# INTENT: eigenvector centrality with strength weights.
# REASONING: unlike path measures, eigenvector centrality treats weight as
#   connection strength; higher weight = more transmitted importance.
# ASSUMES: the graph is connected enough for a meaningful leading eigenvector;
#   on directed graphs consider PageRank instead (below).
eig = giant.eigenvector_centrality(weights=giant.es["weight"])
print("eigenvector:", dict(zip(giant.vs["name"], (round(e, 3) for e in eig))))
```

## PageRank

A random-walk importance measure that is well-behaved on **directed** graphs
(where eigenvector centrality can be problematic). Weights mean transition
strength. The damping factor defaults to 0.85.

```python
# INTENT: PageRank on the (possibly directed) graph with strength weights.
# REASONING: PageRank handles directed graphs and dangling nodes gracefully via
#   damping, making it the go-to recursive-importance measure for directed data.
# ASSUMES: weights are non-negative strengths; damping=0.85 is the conventional
#   default unless there is a reason to change it.
pr = g.pagerank(weights=g.es["weight"], damping=0.85, directed=g.is_directed())
print("PageRank:", dict(zip(g.vs["name"], (round(p, 4) for p in pr))))
assert abs(sum(pr) - 1.0) < 1e-6, "PageRank scores should sum to ~1"
```

## Choosing a Centrality

| Question | Measure |
|----------|---------|
| Who has the most direct ties? | Degree (in/out/all) |
| Who bridges otherwise-separate groups? | Betweenness |
| Who can reach everyone fastest? | Closeness |
| Who is connected to well-connected others? | Eigenvector (undirected) / PageRank (directed) |
| Who accumulates the most tie-strength? | Weighted degree (strength) |

For interpretation caveats (e.g., betweenness ≠ resilience, centrality under the
Modifiable Areal Unit / boundary-specification problem), load the `data-scientist`
skill's methodology guidance alongside this one.

## Moving Results into Analysis

Centrality vectors align with `g.vs` order — attach them back as a Polars column
for downstream regression or joins. See `dataframe-interop.md`.
