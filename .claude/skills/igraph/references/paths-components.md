# igraph Paths and Components: Shortest Paths, Distances, Diameter, Connectivity

This reference covers shortest paths, all-pairs distances, diameter, connected
components (weak and strong), the giant component, and reachability. These are
the connectivity primitives that centrality and community-detection results
depend on.

## Weights Are Distances Here

As in centrality, path functions read edge `weight` as **distance** — higher
weight = longer path. If weights encode strength, invert them first (see
`centrality.md`). Pass `weights=` explicitly; do not rely on unverified
auto-use.

## Shortest Paths

`get_shortest_paths` returns the vertex sequence(s) of a shortest path;
`distances` returns the numeric path length(s).

```python
# --- Config ---
import igraph as ig

# --- Shortest path (vertex sequence) ---
# INTENT: find the actual node sequence of a shortest path between two named nodes.
# REASONING: get_shortest_paths returns vertex-index lists; mapping through
#   g.vs["name"] recovers the human-readable route. Passing weights=distance makes
#   "shortest" mean lowest total distance, not fewest hops.
# ASSUMES: src and dst are vertex names present in g.vs["name"]; distances are
#   distance-scaled weights.
src, dst = "Ana", "Dee"
paths = g.get_shortest_paths(src, to=dst, weights=g.es["distance"], output="vpath")
route = [g.vs[i]["name"] for i in paths[0]] if paths and paths[0] else []
print(f"shortest path {src} -> {dst}: {route}")
```

Numeric distance between two nodes (or a distance matrix):

```python
# INTENT: get the shortest-path DISTANCE (not the route) between two nodes, and
#   demonstrate a full distance matrix.
# REASONING: `distances` is the efficient way to get lengths; inf marks
#   unreachable pairs (different components), which is itself diagnostic.
# ASSUMES: distance weights; inf in the result signals disconnection.
d = g.distances(source=[src], target=[dst], weights=g.es["distance"])[0][0]
print(f"distance {src} -> {dst}: {d}")

dmat = g.distances(weights=g.es["distance"])   # full V x V matrix (list of lists)
n_unreachable = sum(1 for row in dmat for v in row if v == float("inf"))
print(f"unreachable ordered pairs (inf entries): {n_unreachable}")
```

> **`inf` in a distance matrix is a connectivity signal.** Any `inf` entry means
> the two nodes are in different components (or, on a directed graph, not
> reachable following edge direction). This is the same condition that makes
> closeness/betweenness ill-defined — see the connectivity guardrail in
> `centrality.md`.

## Diameter

The diameter is the longest shortest-path distance in the graph — the "width" of
the network. On a disconnected graph it is `inf` unless you restrict to a
component.

```python
# INTENT: report the diameter of the connected core.
# REASONING: diameter on a disconnected graph is infinite; computing it on the
#   giant component gives an interpretable spread of the connected structure.
# ASSUMES: analyzing the giant component is the intended scope.
giant = g.connected_components(mode="weak").giant()
diam = giant.diameter(weights=giant.es["distance"])
print(f"giant-component diameter: {diam:.3f}")
```

## Connected Components

Components partition the graph into maximal connected subgraphs. On directed
graphs, distinguish:

- **Weak components** (`mode="weak"`): treat edges as undirected — nodes are in
  the same component if connected ignoring direction.
- **Strong components** (`mode="strong"`): nodes are in the same component only
  if mutually reachable *following* edge direction.

```python
# INTENT: characterize component structure for both weak and strong notions.
# REASONING: on directed data weak vs. strong components answer different
#   questions (any-connection vs. mutual-reachability); reporting both prevents
#   conflating them. On undirected graphs the two coincide.
# ASSUMES: g may be directed; sizes are reported largest-first.
weak = g.connected_components(mode="weak")
print(f"weak components: {len(weak)}  sizes: {sorted(map(len, weak), reverse=True)}")

if g.is_directed():
    strong = g.connected_components(mode="strong")
    print(f"strong components: {len(strong)}  "
          f"sizes: {sorted(map(len, strong), reverse=True)}")
```

## The Giant Component

The giant (largest) component is the usual analysis scope when a network has a
dominant connected core plus scattered isolates or small fragments.

```python
# INTENT: extract the giant component and report how much of the graph it covers.
# REASONING: documenting the fraction of nodes retained makes the scope decision
#   auditable — dropping half the nodes to a "giant component" is a substantive
#   analytic choice, not a technicality.
giant = g.connected_components(mode="weak").giant()
print(f"giant component: {giant.vcount()}/{g.vcount()} nodes "
      f"({giant.vcount()/g.vcount():.1%}), {giant.ecount()} edges")
```

> The subgraph re-indexes vertices 0..giant.vcount()-1. If you need to map giant
> results back to original labels, carry `g.vs["name"]` through — `.giant()`
> preserves the `name` attribute, so `giant.vs["name"]` still works.

## Reachability

To test whether one node can reach another (respecting direction on a directed
graph), check for a finite distance:

```python
# INTENT: boolean reachability test between two nodes.
# REASONING: a finite distance means a path exists; on a directed graph this
#   honors edge direction, answering "can A reach B?" rather than "are A and B in
#   the same undirected component?".
# ASSUMES: distance weights; None/inf handling covers the unreachable case.
d = g.distances(source=[src], target=[dst], weights=g.es["distance"])[0][0]
reachable = d != float("inf")
print(f"{src} can reach {dst}: {reachable}")
```

## Neighborhoods (Ego Structure)

The immediate neighborhood of a node — useful for local structure without a full
ego-network analysis:

```python
# INTENT: list a node's neighbors (order-1 neighborhood).
# REASONING: neighbors() returns adjacent vertex indices; mode controls direction
#   on directed graphs (in/out/all), mirroring the degree modes.
# ASSUMES: node given by name; resolve to index via g.vs.find.
idx = g.vs.find(name="Cy").index
nbrs = [g.vs[i]["name"] for i in g.neighbors(idx, mode="all")]
print(f"neighbors of Cy: {nbrs}")
```

## Feeding Results into Analysis

Distances, component membership, and reachability flags are all vertex- or
pair-aligned vectors that attach back to Polars tables for downstream modeling —
see `dataframe-interop.md`. Component membership in particular is often used to
subset or as a fixed effect.

```python
# Component membership as a per-node label (aligned with g.vs order):
g.vs["component"] = g.connected_components(mode="weak").membership
```
