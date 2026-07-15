# igraph ↔ Polars Interop: Attributes, Measures, and Edge Lists as Tidy Tables

This reference covers moving data between igraph and Polars: extracting per-node
measures (centrality, community, component) into a tidy Polars frame for
downstream statistics, attaching a Polars column as a node attribute, and
exporting the graph's edge list back to a Polars DataFrame. This is the glue that
lets graph structure feed regression, joins, and reporting.

## The Interop Principle

Keep the **Parquet edge list (and node-attribute table) as the source of truth**,
per DAAF conventions. Build the graph from those tables, compute graph measures,
then bring the measures *back* into Polars as columns keyed by node name. The
graph is a transient computation; the tidy tables are the auditable artifacts.

Alignment rule: igraph returns per-node measures as **lists in `g.vs` order**
(vertex index 0..vcount-1). To join safely to other data, pair each measure with
`g.vs["name"]` so the key travels with the value — never assume the vertex order
matches an external table's row order.

## Extracting Per-Node Measures into a Polars Frame

```python
# --- Config ---
import igraph as ig
import polars as pl
import random

# --- Compute several node-level measures ---
# INTENT: assemble a tidy per-node table of graph measures for downstream stats.
# REASONING: each measure is a list aligned with g.vs order; zipping with
#   g.vs["name"] makes name the join key so the frame can merge with external
#   attributes safely, regardless of row order.
# ASSUMES: g is connected enough for the path measures, or they are computed on
#   the giant component; weights passed explicitly per skill convention.
deg = g.degree(mode="all")
pr = g.pagerank(weights=g.es["weight"], directed=g.is_directed())

random.seed(0)
membership = g.as_undirected().community_multilevel(
    weights=g.as_undirected().es["weight"]
).membership

node_measures = pl.DataFrame({
    "name": g.vs["name"],
    "degree": deg,
    "pagerank": pr,
    "community": membership,
})

# --- Validate ---
print(node_measures)
assert node_measures.height == g.vcount(), "one row per vertex"
assert node_measures.get_column("name").n_unique() == g.vcount(), "names unique"
```

This `node_measures` frame is now an ordinary Polars table: join it to a
node-attribute table, use `community` as a grouping variable, or feed `pagerank`
into a regression as a predictor.

```python
# INTENT: join graph measures to external node attributes for modeling.
# REASONING: joining on `name` (not position) is robust to ordering differences
#   between the graph's vertex sequence and the attribute table.
# ASSUMES: nodes_pl has a `name` column matching g.vs["name"].
analysis_frame = node_measures.join(nodes_pl, on="name", how="left")
print(analysis_frame.columns)
```

## Attaching a Polars Column as a Node Attribute

The reverse direction — push a computed column (e.g., an external covariate) onto
the graph so it can drive coloring, weighting, or per-community summaries.

```python
# INTENT: attach an external attribute to the graph in the correct vertex order.
# REASONING: g.vs["attr"] = list assigns BY VERTEX INDEX, so the list must be
#   ordered to match g.vs. Reindexing the Polars frame to g.vs["name"] guarantees
#   alignment rather than trusting the frame's native order.
# ASSUMES: nodes_pl contains every vertex name exactly once.
name_order = pl.DataFrame({"name": g.vs["name"]})
aligned = name_order.join(nodes_pl, on="name", how="left")
g.vs["dept"] = aligned.get_column("dept").to_list()
assert len(g.vs["dept"]) == g.vcount(), "attribute length must equal vertex count"
```

> **The alignment trap:** `g.vs["x"] = some_list` assigns by position. If
> `some_list` came from a Polars frame in a different row order than `g.vs`, every
> value lands on the wrong node — silently. Always reindex to `g.vs["name"]`
> first (as above). This is the most common interop bug; see `gotchas.md`.

## Exporting the Edge List Back to Polars

To persist the graph (or a projection/subgraph) as an auditable Parquet artifact,
convert its edges — with names and attributes — back to a Polars frame.

```python
# INTENT: export the graph's edges (by name, with weight) to a Polars edge list.
# REASONING: reconstructing name-keyed source/target columns produces the same
#   tidy edge-list format the graph was built from, closing the round-trip and
#   yielding a Parquet-persistable artifact.
# ASSUMES: g.vs["name"] is set; `weight` is an edge attribute.
edge_rows = {
    "source": [g.vs[e.source]["name"] for e in g.es],
    "target": [g.vs[e.target]["name"] for e in g.es],
    "weight": g.es["weight"],
}
edges_out = pl.DataFrame(edge_rows)
print(edges_out)

# Persist as the auditable artifact (Parquet, per DAAF conventions).
edges_out.write_parquet("network_edges.parquet")
```

For a projected bipartite graph, the same pattern exports the projection's
shared-affiliation-weighted edges:

```python
# INTENT: export a one-mode projection's weighted edges to Polars.
# REASONING: identical name-keyed export; the projection's `weight` carries the
#   shared-affiliation count (a strength weight).
proj_edges = pl.DataFrame({
    "a": [proj_persons.vs[e.source]["name"] for e in proj_persons.es],
    "b": [proj_persons.vs[e.target]["name"] for e in proj_persons.es],
    "shared": proj_persons.es["weight"],
})
proj_edges.write_parquet("person_projection_edges.parquet")
```

## Per-Community Summaries

A frequent downstream task: summarize node attributes within detected
communities. Once measures are in Polars, this is a plain group-by.

```python
# INTENT: summarize an outcome by detected community.
# REASONING: with community membership as a Polars column, community-level
#   aggregates are a standard group_by — no graph API needed downstream.
# ASSUMES: analysis_frame has `community` and a numeric `outcome` column.
summary = (
    analysis_frame
    .group_by("community")
    .agg(
        pl.len().alias("n_nodes"),
        pl.col("pagerank").mean().alias("mean_pagerank"),
    )
    .sort("community")
)
print(summary)
```

## Round-Trip Checklist

- [ ] Graph built from a Parquet edge list (the source of truth), not the reverse.
- [ ] Per-node measures paired with `g.vs["name"]` before leaving igraph.
- [ ] Attributes pushed onto the graph reindexed to `g.vs["name"]` order first.
- [ ] Exported edge lists / measures written to Parquet as the auditable artifact.
- [ ] Joins keyed on `name`, never on positional row order.
