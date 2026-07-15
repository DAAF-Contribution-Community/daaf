# igraph Bipartite Networks: Construction and Projection

This reference covers two-mode (bipartite/affiliation) networks: building them
from a two-column membership table, verifying the bipartite structure, and
projecting to one-mode networks — including weighted projections that count
shared affiliations.

## What Is a Bipartite Network?

A bipartite graph has two disjoint vertex sets ("modes") with edges *only*
between the sets, never within. These model **affiliation data**: people
belonging to organizations, authors writing papers, students enrolled in courses,
customers buying products. The two modes here are, e.g., `person` and `group`.

A `type` boolean vertex attribute encodes the mode: `False` for one side,
`True` for the other. igraph uses this attribute to know the partition.

## Building a Bipartite Graph from a Membership Table

Research affiliation data is typically a two-column Polars table: one row per
(entity, affiliation) membership. Build the vertex set from the union of both
columns, assign `type`, then add the edges.

```python
# --- Config ---
import igraph as ig
import polars as pl

# --- Load: membership edge list (person -- group) ---
# INTENT: represent a two-mode affiliation network as a tidy membership table.
# REASONING: one row per (person, group) tie is the natural affiliation format;
#   the two columns become the two vertex modes.
# ASSUMES: `person` and `group` name spaces are disjoint (no name appears as both
#   a person and a group). If they can collide, prefix them (see gotchas).
memb = pl.DataFrame({
    "person": ["Ana", "Ana", "Bo", "Cy", "Cy", "Dee"],
    "group":  ["G1",  "G2",  "G1", "G2", "G3", "G3"],
})

# --- Transform: assemble vertices with a type flag, then edges ---
# INTENT: build an explicit vertex list carrying the bipartite `type` attribute.
# REASONING: bipartite algorithms need `type` (False=person, True=group). Building
#   the vertex table first guarantees every node exists and is typed before edges
#   reference it by name.
# ASSUMES: persons are type=False, groups are type=True (the convention below).
persons = memb.get_column("person").unique().sort().to_list()
groups = memb.get_column("group").unique().sort().to_list()
name_to_idx = {nm: i for i, nm in enumerate(persons + groups)}
types = [False] * len(persons) + [True] * len(groups)

edges_idx = [
    (name_to_idx[p], name_to_idx[grp])
    for p, grp in zip(memb.get_column("person"), memb.get_column("group"))
]

g_bip = ig.Graph(n=len(name_to_idx), edges=edges_idx, directed=False)
g_bip.vs["name"] = persons + groups
g_bip.vs["type"] = types

# --- Validate ---
print(f"bipartite: {g_bip.is_bipartite()}  "
      f"persons={sum(1 for t in types if not t)}  groups={sum(types)}")
assert g_bip.is_bipartite(), "graph must be bipartite (no within-mode edges)"
```

### Convenience constructor

igraph also offers `Graph.Bipartite(types, edges)` which builds directly from a
`type` list and an edge list — equivalent to the above once you have the typed
vertex indices:

```python
# INTENT: build the same bipartite graph via the dedicated constructor.
# REASONING: Graph.Bipartite takes the type vector + edges directly, skipping the
#   manual Graph(...) + vs["type"] assignment; use whichever is clearer.
# ASSUMES: edges_idx endpoints are consistent with the types vector ordering.
g_bip2 = ig.Graph.Bipartite(types, edges_idx)
g_bip2.vs["name"] = persons + groups
assert g_bip2.is_bipartite()
```

## Verifying Bipartite Structure

Before projecting, confirm the graph really is bipartite — a single within-mode
edge (e.g., a person-to-person tie that slipped into the table) breaks the
two-mode assumption and corrupts projections.

```python
# INTENT: detect any within-mode edges that would violate bipartiteness.
# REASONING: is_bipartite() returns False if any edge joins two same-type nodes;
#   catching this early prevents a silently wrong projection.
# ASSUMES: `type` is set on every vertex.
ok, detected_types = g_bip.is_bipartite(return_types=True)
print(f"is_bipartite: {ok}")
assert ok, "found within-mode edges — check the membership table for stray ties"
```

## One-Mode Projection

Projection collapses the bipartite graph into a one-mode network on each side:
two persons are connected if they share at least one group; two groups are
connected if they share at least one person. `bipartite_projection` returns both
projections as a tuple, ordered by `type` (False side first, True side second).

```python
# INTENT: project to person-person and group-group one-mode networks.
# REASONING: bipartite_projection returns (type-False projection, type-True
#   projection); with multiplicity=True the projected edges carry a `weight` equal
#   to the number of shared affiliations — the standard co-membership strength.
# ASSUMES: type=False are persons (returned first), type=True are groups.
proj_persons, proj_groups = g_bip.bipartite_projection(multiplicity=True)

print(f"person-person: {proj_persons.vcount()} nodes, {proj_persons.ecount()} edges")
print(f"group-group:   {proj_groups.vcount()} nodes, {proj_groups.ecount()} edges")

# Inspect the weighted person-person ties (shared-group counts).
for e in proj_persons.es:
    a = proj_persons.vs[e.source]["name"]
    b = proj_persons.vs[e.target]["name"]
    print(f"  {a} -- {b}  shared groups: {e['weight']}")
```

> **Weighted projection semantics:** with `multiplicity=True`, each projected
> edge's `weight` is the count of common affiliations (e.g., two people who share
> 3 groups get weight 3). This is a **strength** weight — for downstream
> path-based measures on the projection, remember it must be inverted to a
> distance (see `centrality.md`).

## Extracting a Single Projection

If you only need one side, project and take the relevant element. You can also
project only the type you want with `which=`:

```python
# INTENT: get just the person-person projection.
# REASONING: which=0 (or which=False) returns only the type-False projection,
#   avoiding building the group-group graph you don't need.
proj_persons_only = g_bip.bipartite_projection(multiplicity=True, which=0)
print(f"persons only: {proj_persons_only.summary()}")
```

## Common Bipartite Pitfalls

- **Name collisions across modes:** if a person and a group could share a name,
  the union-of-names vertex construction silently merges them. Prefix names
  (`p:Ana`, `g:G1`) when the two namespaces might overlap.
- **Projection density explosion:** a popular hub (a group everyone belongs to)
  makes *every* pair of its members adjacent in the projection, producing a
  near-complete subgraph. Check projected density and consider whether to drop or
  down-weight ubiquitous affiliations before interpreting.
- **Forgetting `multiplicity=True`:** without it, projected edges are unweighted,
  discarding the shared-affiliation counts you usually want.

See `gotchas.md` for more, and `dataframe-interop.md` for moving projected edge
lists and weights back into Polars.
