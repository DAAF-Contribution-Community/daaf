# igraph Quickstart: Construction, Polars Round-Trip, I/O, Inspection

This reference covers building a `Graph` from edge-list data, moving edge/node
tables between Polars and igraph, reading/writing graph files, and inspecting a
graph's basic structure. It is the foundation for every other reference file.

## Installation Status in DAAF

`igraph==1.0.0` is pinned in the Dockerfile framework install block but **the
container has not been rebuilt**, so `import igraph` currently raises
`ModuleNotFoundError`. Rebuild by exiting the container and running
`bash rebuild_daaf.sh` (`.\rebuild_daaf.ps1` on Windows) from the `daaf-docker`
folder. Verify after rebuild:

```python
import igraph as ig
print(ig.__version__)   # expect "1.0.0"
```

The PyPI package is `igraph` (`pip install igraph`), imported as `import igraph`.
The historical name `python-igraph` is now an alias for the same package.

## Core Concepts

- A `Graph` holds **vertices** (nodes, integer-indexed 0..vcount-1) and
  **edges** (pairs of vertex indices).
- **Directedness is graph-level**, fixed at construction: `directed=True` or
  `directed=False`. You cannot mix directed and undirected edges in one graph.
- Vertices and edges carry **named attributes** accessed via `g.vs["attr"]`
  (vertex sequence) and `g.es["attr"]` (edge sequence).
- Vertices can have a **`name` attribute** so you can refer to them by label
  instead of integer index. This is the single most common source of confusion —
  see `gotchas.md` on names vs. indices.

## Building a Graph

### From explicit edge tuples

The most direct construction — a list of `(source_index, target_index)` tuples:

```python
# --- Build ---
import igraph as ig

# INTENT: build a small undirected graph from integer-indexed edge tuples.
# REASONING: Graph(n, edges, directed) is the lowest-level constructor; vertex
#   count must be given explicitly so isolated (edgeless) vertices are retained.
# ASSUMES: vertex indices in `edges` are 0-based and < n_vertices.
edges = [(0, 1), (0, 2), (1, 2), (2, 3), (3, 4)]
g = ig.Graph(n=5, edges=edges, directed=False)

print(f"vertices: {g.vcount()}  edges: {g.ecount()}  directed: {g.is_directed()}")
assert g.vcount() == 5, "isolated vertices must be retained"
```

### From a Polars edge-list DataFrame (the DAAF-standard path)

Research edge lists live in Polars. igraph's `Graph.DataFrame()` constructor
consumes a **pandas** DataFrame whose first two columns are the edge endpoints
(by vertex *name*, not index), with any further columns becoming edge
attributes. Because DAAF standardizes on Polars, convert with `.to_pandas()` at
the igraph boundary only.

```python
# --- Config ---
import igraph as ig
import polars as pl

# --- Load ---
# INTENT: represent a collaboration network as a Polars edge list with a weight.
# REASONING: Polars is DAAF's DataFrame standard; the pandas conversion happens
#   only at the igraph boundary because Graph.DataFrame requires a pandas frame.
# ASSUMES: the first two columns are source/target vertex names; `weight` is an
#   edge attribute. String vertex names become the vertices' `name` attribute.
edges_pl = pl.DataFrame({
    "source": ["Ana", "Ana", "Bo", "Cy", "Dee"],
    "target": ["Bo", "Cy", "Cy", "Dee", "Ana"],
    "weight": [3.0, 1.0, 2.0, 5.0, 1.0],
})

# --- Transform ---
# INTENT: hand igraph a pandas view of the edge list.
# REASONING: Graph.DataFrame(use_vids=False) treats the first two columns as
#   vertex NAMES and auto-creates the vertex set; the resulting graph exposes
#   g.vs["name"] so results can be mapped back to labels.
g = ig.Graph.DataFrame(edges_pl.to_pandas(), directed=False, use_vids=False)

# --- Validate ---
print(f"vertices: {g.vcount()}  edges: {g.ecount()}")
print(f"vertex names: {g.vs['name']}")
print(f"edge weights: {g.es['weight']}")
assert set(g.vs["name"]) == {"Ana", "Bo", "Cy", "Dee"}, "vertex names must round-trip"
assert "weight" in g.es.attributes(), "weight column must become an edge attribute"
```

> **Why `use_vids=False`:** with `use_vids=True`, igraph interprets the first two
> columns as integer vertex *ids*. Research edge lists almost always carry string
> labels (person names, institution ids), so `use_vids=False` (interpret as
> names) is the correct default. See `gotchas.md`.

### Supplying a separate vertex-attribute table

To attach node attributes (e.g., department, seniority) that exist independently
of the edges — including for isolated nodes — pass a `vertices` frame whose first
column is the vertex name:

```python
# INTENT: attach node attributes and guarantee isolated nodes appear.
# REASONING: passing `vertices=` ensures every listed node exists even if it has
#   no edges, and each extra column becomes a vertex attribute.
# ASSUMES: the first column of `vertices` holds names matching the edge endpoints.
nodes_pl = pl.DataFrame({
    "name": ["Ana", "Bo", "Cy", "Dee", "El"],   # El is isolated
    "dept": ["R&D", "R&D", "Ops", "Ops", "Ops"],
})
g = ig.Graph.DataFrame(
    edges_pl.to_pandas(),
    vertices=nodes_pl.to_pandas(),
    directed=False,
    use_vids=False,
)
print(f"depts: {g.vs['dept']}")
assert "El" in g.vs["name"], "isolated vertex from the vertices table must be present"
```

### Directed vs. undirected — choose deliberately

Directedness changes the meaning of nearly every measure (degree splits into
in/out; closeness/betweenness follow edge direction; Leiden/Louvain require
undirected input). Decide from the *substance* of the ties:

- **Directed** when ties have an inherent sender→receiver asymmetry: citations,
  follows, email-from→email-to, advice-seeking.
- **Undirected** when ties are inherently mutual: co-authorship, co-attendance,
  friendship recorded symmetrically.

If a downstream method needs undirected input but the data is directed, convert
explicitly rather than silently (see below), and record why.

## Converting Directed → Undirected

```python
# INTENT: produce an undirected copy for methods that require it (e.g., Louvain).
# REASONING: as_undirected collapses each directed edge; `combine_edges` controls
#   how duplicate edges' attributes merge (sum the weights of reciprocal edges).
# ASSUMES: summing weights is the right semantics for this network; for unweighted
#   collapse use mode="collapse" to dedupe reciprocal pairs into a single edge.
g_u = g.as_undirected(mode="collapse", combine_edges={"weight": "sum"})
print(f"undirected: {g_u.is_directed()}  edges: {g_u.ecount()}")
```

## Graph I/O

igraph reads and writes many formats. For research provenance, prefer GraphML
(preserves attributes and directedness) for graph snapshots; keep the *source of
truth* as a Parquet edge list per DAAF conventions and rebuild the graph from it.

```python
# Write / read GraphML (attributes + directedness preserved)
g.write_graphml("network.graphml")
g2 = ig.Graph.Read_GraphML("network.graphml")

# Plain edge list (indices only — attributes and names are NOT preserved)
g.write_edgelist("network.edgelist")
```

> **Provenance note:** the canonical, auditable artifact is the Parquet edge list
> (and node-attribute table), not the serialized graph. Save those with
> `.write_parquet()` and reconstruct the graph in each script — this keeps the
> pipeline reproducible and inspectable. See `dataframe-interop.md`.

## Basic Inspection

```python
g.vcount()                       # number of vertices
g.ecount()                       # number of edges
g.is_directed()                  # directedness
g.is_connected(mode="weak")      # single component?
g.density()                      # edge density
g.degree()                       # degree of every vertex (list)
max(g.degree())                  # max degree
g.vs["name"]                     # vertex names (if set)
g.es.attributes()                # list of edge-attribute names
g.vs.attributes()                # list of vertex-attribute names
g.summary()                      # one-line structural summary string
```

A quick degree-distribution sanity check:

```python
# INTENT: print a degree summary so the appended execution log records the
#   graph's shape for audit.
# REASONING: an isolated-node count and max degree catch construction mistakes
#   (e.g., a self-loop explosion or an accidental complete graph) early.
deg = g.degree()
print(f"n={g.vcount()} m={g.ecount()} "
      f"isolated={sum(1 for d in deg if d == 0)} "
      f"max_degree={max(deg)} mean_degree={sum(deg)/len(deg):.2f}")
```

## Next Steps

- Measure node importance → `centrality.md`
- Find communities → `community-detection.md`
- Paths and components → `paths-components.md`
- Move results in/out of Polars → `dataframe-interop.md`
- Common construction traps → `gotchas.md`
