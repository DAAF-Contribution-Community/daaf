# igraph Gotchas: Traps, Pitfalls, and Debugging

Curated failure modes for python-igraph in DAAF research workflows. Several of
these are *silent* — they produce a plausible-looking wrong answer rather than an
error — so they warrant explicit guardrails.

## 1. Directed Input to Community Detection (Leiden / Louvain)

**Symptom:** an error, or (worse) a silently questionable partition when running
`community_leiden` / `community_multilevel` on a directed graph.

**Cause:** these algorithms are formulated for **undirected** graphs. The R
igraph docs state the input "must be undirected." The Python-side directed
behavior for 1.0.0 was **not verified** — do not assume it is handled correctly.

**Fix:** convert explicitly before detecting communities, and document the
collapse semantics:

```python
if g.is_directed():
    g_u = g.as_undirected(mode="collapse", combine_edges={"weight": "sum"})
else:
    g_u = g
```

If you have a specific need to run community detection on directed structure,
treat it as **verify-at-runtime**: test on a small known example and confirm the
behavior before trusting it. See `community-detection.md`.

## 2. Non-Reproducible Results (Missing Seed)

**Symptom:** community assignments or figure layouts change between runs of the
same script.

**Cause:** community detection (Louvain, Leiden, walktrap) and force-directed
layouts (`"fr"`, `"kk"`, `"dh"`, `"lgl"`) are **stochastic**.

**Fix:** call `random.seed(N)` immediately before the stochastic call, and
**record `N`**. This is the official python-igraph tutorial pattern.

```python
import random
random.seed(0)
part = g_u.community_multilevel(weights=g_u.es["weight"])
```

The advanced path `igraph.set_random_number_generator(rng)` exists for injecting
a custom RNG, but `random.seed()` is sufficient and preferred. An unrecorded seed
is as bad as no seed — the result is reproducible only if the seed is part of the
saved script.

## 3. Closeness / Betweenness Returns inf or nan on a Disconnected Graph

**Symptom:** closeness values that look wrong, `inf` entries in a distance
matrix, or betweenness that ignores obvious bridges.

**Cause:** these path-based measures are **ill-defined across components** —
unreachable pairs contribute nothing, and closeness "is not well-defined for
disconnected graphs." A node's closeness reflects only its own component.

**Fix:** check components first; restrict to the giant component (or interpret
strictly within-component) as a deliberate, documented choice:

```python
comp = g.connected_components(mode="weak")
if len(comp) > 1:
    print(f"WARNING: {len(comp)} components — restricting to giant component")
    g = comp.giant()
```

See the connectivity guardrail in `centrality.md`.

## 4. Weights Read as Distances, Not Strengths

**Symptom:** shortest paths route through *strong* ties as if they were long
detours; central "hubs" look peripheral.

**Cause:** in path-based measures (betweenness, closeness, shortest paths),
igraph treats `weight` as **distance** — higher weight = longer path. If your
weights encode connection *strength* (bigger = closer), they are backwards.

**Fix:** invert strength to distance before path-based measures:

```python
assert all(w > 0 for w in g.es["strength"]), "positive strengths required"
g.es["distance"] = [1.0 / w for w in g.es["strength"]]
bet = g.betweenness(weights=g.es["distance"])
```

Note the asymmetry: **eigenvector centrality, PageRank, and weighted degree
(strength)** treat weight as *strength* (use it directly), while **betweenness,
closeness, and shortest paths** treat it as *distance* (invert first). Keep two
attributes (`weight`/`strength` and `distance`) to stay unambiguous.

## 5. Relying on Unverified Weight Auto-Use

**Symptom:** a weighted call gives different results across environments, or an
"unweighted" call unexpectedly uses weights.

**Cause:** the R binding auto-uses a `weight` edge attribute when `weights` is
`NULL`. The equivalent auto-use in **python-igraph was not verified**. Relying on
it is a portability and clarity hazard.

**Fix:** always pass `weights=` explicitly — `weights=g.es["weight"]` (or
`weights=g.es["distance"]`) for weighted, `weights=None` for explicitly
unweighted. Never leave it to the default.

## 6. Vertex Names vs. Integer Indices

**Symptom:** `KeyError`, or a function silently operating on the wrong node.

**Cause:** igraph vertices are fundamentally **integer-indexed** (0..vcount-1).
The `name` attribute is a convenience layer. Many functions accept a name *only*
if a `name` attribute exists; otherwise they expect an index. Mixing them causes
subtle errors.

**Fix:** be explicit about which you're using. Resolve a name to an index when a
function needs an index:

```python
idx = g.vs.find(name="Cy").index          # name -> index
name = g.vs[idx]["name"]                    # index -> name
```

When building from a Polars edge list, use `Graph.DataFrame(..., use_vids=False)`
so the string columns are treated as **names**, not integer ids (see
`quickstart.md`). `use_vids=True` would interpret `"Ana"` as an integer id and
fail or misbehave.

## 7. Attribute Assignment Lands on the Wrong Node

**Symptom:** node colors/sizes/covariates are shuffled — the right values on the
wrong nodes.

**Cause:** `g.vs["attr"] = some_list` assigns **by vertex index/position**. If
`some_list` came from a Polars frame in a different row order than `g.vs`, every
value is misaligned — silently.

**Fix:** reindex the source frame to `g.vs["name"]` order before assigning:

```python
name_order = pl.DataFrame({"name": g.vs["name"]})
aligned = name_order.join(nodes_pl, on="name", how="left")
g.vs["dept"] = aligned.get_column("dept").to_list()
```

See `dataframe-interop.md`.

## 8. Bipartite Name Collisions and Projection Explosions

**Symptom:** a person and a group merge into one node; or a projection is
near-complete (everyone connected to everyone).

**Cause:** (a) if a person and a group share a name, the union-of-names vertex
set silently merges them; (b) a ubiquitous affiliation (a group everyone belongs
to) makes every pair of its members adjacent in the projection.

**Fix:** prefix names across modes (`p:Ana`, `g:G1`) when namespaces might
overlap; check projected density and consider dropping/down-weighting ubiquitous
affiliations. See `bipartite.md`.

## 9. Plotting Tries to Use Cairo

**Symptom:** an error about Cairo / `cairocffi` when calling `ig.plot(...)`.

**Cause:** Cairo is python-igraph's *default* plotting backend, and it is **not
installed** in the DAAF container.

**Fix:** always route through matplotlib by passing a matplotlib `Axes` as
`target=`:

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(8, 8))
ig.plot(g, target=ax, layout=g.layout("fr"))
fig.savefig("network.png", dpi=200, bbox_inches="tight")
```

See `visualization.md`.

## 10. Import Fails Before Container Rebuild

**Symptom:** `ModuleNotFoundError: No module named 'igraph'`.

**Cause:** `igraph==1.0.0` is pinned in the Dockerfile but the container has not
yet been rebuilt.

**Fix:** exit the container and run `bash rebuild_daaf.sh` (`.\rebuild_daaf.ps1`
on Windows) from the `daaf-docker` folder. Do **not** attempt a runtime
`pip install` — runtime package installation is blocked by DAAF safety hooks and
creates unreproducible drift. Confirm with `python -c "import igraph; print(igraph.__version__)"`
(expect `1.0.0`) after rebuild.

## 11. Self-Loops and Multi-Edges Distort Measures

**Symptom:** inflated degrees, unexpected community structure, or centrality
anomalies.

**Cause:** an edge list may contain self-loops (a node tied to itself) or
duplicate edges (multi-edges) that you did not intend. Many measures count them.

**Fix:** inspect and, if unintended, simplify:

```python
print(f"self-loops: {sum(g.is_loop())}  multi-edges: {sum(g.is_multiple())}")
# Remove them only if they are genuinely artifacts (document the decision):
g_simple = g.simplify(multiple=True, loops=True, combine_edges={"weight": "sum"})
```

Simplifying is a substantive analytic choice — record why, since summing weights
of merged multi-edges changes their meaning.

## Debugging Workflow

When a network result looks wrong, check in this order:

1. **Directedness** — is the graph directed when you expected undirected (or vice versa)? `g.is_directed()`
2. **Connectivity** — how many components? `len(g.connected_components(mode="weak"))`
3. **Weights** — are you passing them explicitly, and as distance vs. strength correctly?
4. **Seed** — did you seed before the stochastic call, and record it?
5. **Names/indices** — are you addressing nodes by the right key?
6. **Self-loops/multi-edges** — are there unintended ones inflating measures?
7. **Simplification** — did an earlier `simplify()` change the graph out from under you?

Print `g.summary()` early — it reports vertex/edge counts, directedness, and
attribute names in one line, catching many construction mistakes immediately.
