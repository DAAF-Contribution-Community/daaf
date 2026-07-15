# scripts/smoke_tests/smoke_igraph.py
# Functional smoke test for the Python `igraph` (python-igraph) network-analysis
# library, grounding the `igraph` skill's factual claims in observed behavior.
#
#   Expected version (post-rebuild target):
#     igraph == 1.0.0   (python-igraph; PyPI package `igraph`, import `igraph`)
#
# What this validates (synthetic-data tests, in order):
#   1. Version gate + graph construction from a Polars edge list (vertices/edges/names)
#   2. Degree centrality on a directed graph (in/out/all modes distinct)
#   3. Betweenness on the giant component with explicit distance weights (bridge node ranks top)
#   4. Seeded Louvain + Leiden community detection (reproducible; recovers planted blocks)
#   5. Bipartite construction + weighted one-mode projection (shared-affiliation counts)
#   6. Connected components + giant-component extraction (planted disconnected fragment)
#   7. Shortest path + distance (known path length on a constructed graph)
#   8. Polars round-trip of per-node measures (name-keyed, one row per vertex)
#
# WHY THIS SCRIPT EXISTS: it is the evidence-generating instrument for the igraph
# skill. It will be read as an audit artifact when the skill cites observed behavior,
# so every non-obvious construction carries INTENT/REASONING/ASSUMES comments.
#
# Sequential inline script (DAAF code style): no functions, no classes, no type
# annotations, section separators, print + assert for validation. Polars for all
# tabular data (never pandas, except at the igraph construction boundary which
# requires a pandas frame). Synthetic data; stochastic steps seeded for reproducibility.
#
# DO NOT execute against the currently-installed environment: igraph 1.0.0 is pinned
# in the Dockerfile but the container has NOT been rebuilt, so `import igraph` will
# raise ModuleNotFoundError. Run this only AFTER the rebuild that installs igraph 1.0.0.
# Do NOT pip-install igraph at runtime (blocked by DAAF safety hooks; creates drift).

# --- Config ---
import random
import sys

import igraph as ig
import polars as pl

print("=== igraph (python-igraph) Smoke Test ===\n")
print(f"  igraph version: {ig.__version__}")
print(f"  polars version: {pl.__version__}")

# INTENT: assert the installed igraph is at least the skill's target major.minor.
# REASONING: this script encodes behavior verified against 1.0.0; running it on a
#   different build could record misleading pass/fail against the wrong version.
#   Parse major/minor as integers to avoid lexical version-compare pitfalls.
# ASSUMES: __version__ is a dotted numeric string like "1.0.0".
_ver_parts = ig.__version__.split(".")
_major = int(_ver_parts[0])
_minor = int(_ver_parts[1]) if len(_ver_parts) > 1 else 0
assert (_major, _minor) >= (1, 0), (
    f"smoke_igraph.py targets igraph>=1.0.0 but found {ig.__version__}; "
    "run only after the container rebuild that installs python-igraph 1.0.0"
)
print(f"  version gate OK: igraph {ig.__version__} >= 1.0\n")

# Test accounting: every test increments total; passes increment pass.
n_pass = 0
n_total = 0

# =============================================================================
# Test 1: graph construction from a Polars edge list
# =============================================================================
# INTENT: build an undirected graph from a Polars edge list and confirm vertex
#   count, edge count, vertex names, and the weight edge attribute all round-trip.
# REASONING: Graph.DataFrame(use_vids=False) treats the first two columns as vertex
#   NAMES (the research-standard case); the pandas conversion happens only at the
#   igraph boundary because DAAF standardizes on Polars everywhere else.
# ASSUMES: string vertex names become g.vs["name"]; the third column becomes an
#   edge attribute named "weight".
n_total += 1
print("Test 1: graph construction from a Polars edge list")

edges_pl = pl.DataFrame({
    "source": ["Ana", "Ana", "Bo", "Cy", "Dee", "Bo"],
    "target": ["Bo", "Cy", "Cy", "Dee", "Ana", "Dee"],
    "weight": [3.0, 1.0, 2.0, 5.0, 1.0, 4.0],
})
g = ig.Graph.DataFrame(edges_pl.to_pandas(), directed=False, use_vids=False)

print(f"  vertices={g.vcount()} edges={g.ecount()} directed={g.is_directed()}")
print(f"  names={sorted(g.vs['name'])}")
assert g.vcount() == 4, f"expected 4 vertices, got {g.vcount()}"
assert g.ecount() == 6, f"expected 6 edges, got {g.ecount()}"
assert set(g.vs["name"]) == {"Ana", "Bo", "Cy", "Dee"}, "vertex names must round-trip"
assert "weight" in g.es.attributes(), "weight column must become an edge attribute"
print("  PASS\n")
n_pass += 1

# =============================================================================
# Test 2: degree centrality on a directed graph (in/out/all modes)
# =============================================================================
# INTENT: confirm the directed degree modes are distinct and correct on a small
#   directed graph with a known in/out structure.
# REASONING: mode="in"/"out"/"all" must answer different questions on directed
#   data; a hand-checkable star (all edges point INTO a hub) makes the expected
#   in/out degrees exact.
# ASSUMES: edges are directed source->target; the hub is vertex "H".
n_total += 1
print("Test 2: degree centrality on a directed graph (in/out/all)")

dedges = pl.DataFrame({
    "source": ["A", "B", "C", "D"],
    "target": ["H", "H", "H", "H"],   # all point into hub H
})
dg = ig.Graph.DataFrame(dedges.to_pandas(), directed=True, use_vids=False)
_hub = dg.vs.find(name="H").index

indeg = dg.degree(_hub, mode="in")
outdeg = dg.degree(_hub, mode="out")
alldeg = dg.degree(_hub, mode="all")
print(f"  hub H: in={indeg} out={outdeg} all={alldeg}")
assert indeg == 4, f"hub indegree should be 4, got {indeg}"
assert outdeg == 0, f"hub outdegree should be 0, got {outdeg}"
assert alldeg == 4, f"hub total degree should be 4, got {alldeg}"

# A leaf (A) has the mirror structure: one outgoing edge to H, none incoming.
_leaf = dg.vs.find(name="A").index
assert dg.degree(_leaf, mode="out") == 1, "leaf A outdegree should be 1"
assert dg.degree(_leaf, mode="in") == 0, "leaf A indegree should be 0"
print("  in/out/all degree modes are distinct and correct")
print("  PASS\n")
n_pass += 1

# =============================================================================
# Test 3: betweenness on the giant component with explicit distance weights
# =============================================================================
# INTENT: verify betweenness identifies a bridge node, using explicit distance
#   weights and the connectivity guardrail.
# REASONING: build two triangles joined by a single bridge node; that node lies on
#   every cross-cluster shortest path, so it must have the strictly-highest
#   betweenness. Weights are passed explicitly (as distances) per skill convention.
# ASSUMES: the constructed graph is connected (one component), so betweenness is
#   well-defined without restricting to a subcomponent.
n_total += 1
print("Test 3: betweenness identifies the bridge node (distance weights)")

bedges = pl.DataFrame({
    "source": ["x1", "x2", "x1", "BR", "y1", "y2", "y1"],
    "target": ["x2", "x3", "x3", "x1", "y2", "y3", "y3"],
    "weight": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
})
# Add the bridge edges connecting BR to both clusters.
bridge = pl.DataFrame({"source": ["BR", "BR"], "target": ["y1", "x2"], "weight": [1.0, 1.0]})
bedges = pl.concat([bedges, bridge])
bg = ig.Graph.DataFrame(bedges.to_pandas(), directed=False, use_vids=False)

# Connectivity guardrail: betweenness is only interpretable on a connected graph.
_ncomp = len(bg.connected_components(mode="weak"))
print(f"  components={_ncomp}")
assert _ncomp == 1, f"betweenness test graph must be connected, found {_ncomp} components"

# Weights are distances here; all edges are unit distance in this fixture.
bet = bg.betweenness(weights=bg.es["weight"])
_ranked = sorted(zip(bg.vs["name"], bet), key=lambda t: t[1], reverse=True)
print(f"  betweenness ranking (top 3): {[(n, round(b, 1)) for n, b in _ranked[:3]]}")
_top_name = _ranked[0][0]
assert _top_name == "BR", f"bridge node BR should rank highest in betweenness, got {_top_name}"
assert _ranked[0][1] > _ranked[1][1], "bridge betweenness must strictly exceed the runner-up"
print("  bridge node BR has strictly-highest betweenness")
print("  PASS\n")
n_pass += 1

# =============================================================================
# Test 4: seeded Louvain + Leiden community detection (reproducible)
# =============================================================================
# INTENT: confirm seeded community detection is reproducible AND recovers a planted
#   two-block structure, for both Louvain and Leiden.
# REASONING: two dense cliques joined by a single sparse edge have an obvious 2-
#   community structure. Seeding before each call fixes the stochastic vertex order,
#   so a repeat run must give an identical partition. Weights passed explicitly.
# ASSUMES: the planted structure is separable enough that both algorithms find
#   exactly 2 communities; membership is compared up to label permutation via the
#   count of communities and reproducibility across two seeded runs.
n_total += 1
print("Test 4: seeded Louvain + Leiden community detection")

# Block A: clique over a1,a2,a3 ; Block B: clique over b1,b2,b3 ; one bridge a1-b1.
block_edges = []
for clique in (["a1", "a2", "a3"], ["b1", "b2", "b3"]):
    for i in range(len(clique)):
        for j in range(i + 1, len(clique)):
            block_edges.append((clique[i], clique[j]))
block_edges.append(("a1", "b1"))   # single sparse bridge between blocks
cedges = pl.DataFrame({
    "source": [e[0] for e in block_edges],
    "target": [e[1] for e in block_edges],
    "weight": [1.0] * len(block_edges),
})
cg = ig.Graph.DataFrame(cedges.to_pandas(), directed=False, use_vids=False)

# Louvain (community_multilevel): seed, detect, then repeat and require identical.
random.seed(0)
louv1 = cg.community_multilevel(weights=cg.es["weight"])
random.seed(0)
louv2 = cg.community_multilevel(weights=cg.es["weight"])
print(f"  Louvain: {len(louv1)} communities, modularity={louv1.modularity:.4f}")
assert len(louv1) == 2, f"Louvain should recover 2 planted blocks, got {len(louv1)}"
assert louv1.membership == louv2.membership, "seeded Louvain must be reproducible"

# Leiden (community_leiden, modularity objective): seed, detect, repeat.
random.seed(0)
leid1 = cg.community_leiden(objective_function="modularity", weights=cg.es["weight"])
random.seed(0)
leid2 = cg.community_leiden(objective_function="modularity", weights=cg.es["weight"])
print(f"  Leiden:  {len(leid1)} communities, modularity={leid1.modularity:.4f}")
assert len(leid1) == 2, f"Leiden should recover 2 planted blocks, got {len(leid1)}"
assert leid1.membership == leid2.membership, "seeded Leiden must be reproducible"
print("  both algorithms recover 2 blocks and are reproducible under a fixed seed")
print("  PASS\n")
n_pass += 1

# =============================================================================
# Test 5: bipartite construction + weighted one-mode projection
# =============================================================================
# INTENT: build a bipartite person--group graph and confirm the weighted projection
#   counts shared affiliations correctly.
# REASONING: with Ana and Bo both in G1, the person-projection must contain an
#   Ana--Bo edge of weight 1 (one shared group). multiplicity=True is required to
#   get the shared-affiliation counts as edge weights.
# ASSUMES: type=False are persons, type=True are groups; person/group namespaces
#   are disjoint (no shared names).
n_total += 1
print("Test 5: bipartite construction + weighted one-mode projection")

memb = pl.DataFrame({
    "person": ["Ana", "Ana", "Bo", "Cy", "Cy", "Dee"],
    "group":  ["G1",  "G2",  "G1", "G2", "G3", "G3"],
})
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

print(f"  is_bipartite={g_bip.is_bipartite()} persons={len(persons)} groups={len(groups)}")
assert g_bip.is_bipartite(), "constructed graph must be bipartite"

proj_persons, proj_groups = g_bip.bipartite_projection(multiplicity=True)
# Ana and Bo share exactly G1 -> expect an Ana--Bo edge of weight 1.
_pnames = proj_persons.vs["name"]
_ab = [
    proj_persons.es[e.index]["weight"]
    for e in proj_persons.es
    if {_pnames[e.source], _pnames[e.target]} == {"Ana", "Bo"}
]
print(f"  person-projection: {proj_persons.vcount()} nodes, {proj_persons.ecount()} edges")
print(f"  Ana--Bo shared-group weight: {_ab}")
assert _ab == [1.0], f"Ana--Bo should share exactly 1 group (weight 1.0), got {_ab}"
print("  weighted projection counts shared affiliations correctly")
print("  PASS\n")
n_pass += 1

# =============================================================================
# Test 6: connected components + giant-component extraction
# =============================================================================
# INTENT: confirm component detection finds a planted disconnected fragment and
#   .giant() returns the larger component.
# REASONING: a 4-node path plus a separate 2-node edge yields exactly 2 weak
#   components of sizes 4 and 2; the giant must be the size-4 one.
# ASSUMES: weak components are the right notion for this undirected fixture.
n_total += 1
print("Test 6: connected components + giant-component extraction")

comp_edges = pl.DataFrame({
    "source": ["p1", "p2", "p3", "q1"],
    "target": ["p2", "p3", "p4", "q2"],   # p-path (4 nodes) + disjoint q-edge (2 nodes)
})
comp_g = ig.Graph.DataFrame(comp_edges.to_pandas(), directed=False, use_vids=False)
comps = comp_g.connected_components(mode="weak")
_sizes = sorted((len(c) for c in comps), reverse=True)
print(f"  components={len(comps)} sizes={_sizes}")
assert len(comps) == 2, f"expected 2 components, got {len(comps)}"
assert _sizes == [4, 2], f"expected component sizes [4, 2], got {_sizes}"

giant = comps.giant()
print(f"  giant component: {giant.vcount()} nodes")
assert giant.vcount() == 4, f"giant component should have 4 nodes, got {giant.vcount()}"
print("  PASS\n")
n_pass += 1

# =============================================================================
# Test 7: shortest path + distance on a constructed graph
# =============================================================================
# INTENT: verify shortest-path route and numeric distance on a graph with a known
#   answer, using explicit distance weights.
# REASONING: a simple path s-m-t of unit-distance edges has shortest distance 2 and
#   the route [s, m, t]; a direct s-t edge of distance 5 must NOT be chosen. This
#   confirms weights are read as distances (lower = shorter).
# ASSUMES: weights are distances; get_shortest_paths returns vertex-index paths.
n_total += 1
print("Test 7: shortest path + distance (distance weights)")

sp_edges = pl.DataFrame({
    "source": ["s", "m", "s"],
    "target": ["m", "t", "t"],
    "weight": [1.0, 1.0, 5.0],   # s-m-t = 2 (via middle) vs. direct s-t = 5
})
sp_g = ig.Graph.DataFrame(sp_edges.to_pandas(), directed=False, use_vids=False)

_path = sp_g.get_shortest_paths("s", to="t", weights=sp_g.es["weight"], output="vpath")[0]
_route = [sp_g.vs[i]["name"] for i in _path]
_dist = sp_g.distances(source=["s"], target=["t"], weights=sp_g.es["weight"])[0][0]
print(f"  shortest route s->t: {_route}  distance={_dist}")
assert _route == ["s", "m", "t"], f"shortest route should go via m, got {_route}"
assert abs(_dist - 2.0) < 1e-9, f"shortest distance should be 2.0, got {_dist}"
print("  weights read as distances; lower-distance route chosen over direct edge")
print("  PASS\n")
n_pass += 1

# =============================================================================
# Test 8: Polars round-trip of per-node measures
# =============================================================================
# INTENT: extract per-node measures into a name-keyed Polars frame and confirm one
#   row per vertex with unique keys and finite values.
# REASONING: this is the interop pattern the skill teaches — measures are lists in
#   g.vs order, paired with g.vs["name"] so the frame joins safely by name. Using
#   the Test-1 graph `g` keeps the fixture connected and small.
# ASSUMES: pagerank returns one value per vertex summing to ~1; degree returns one
#   integer per vertex.
n_total += 1
print("Test 8: Polars round-trip of per-node measures")

deg = g.degree(mode="all")
pr = g.pagerank(weights=g.es["weight"], directed=g.is_directed())
node_measures = pl.DataFrame({
    "name": g.vs["name"],
    "degree": deg,
    "pagerank": pr,
})
print(node_measures)
assert node_measures.height == g.vcount(), "one row per vertex"
assert node_measures.get_column("name").n_unique() == g.vcount(), "names must be unique keys"
assert abs(sum(pr) - 1.0) < 1e-6, "PageRank scores should sum to ~1"
assert all(d >= 0 for d in deg), "degrees must be non-negative"
print("  per-node measures round-trip to a name-keyed Polars frame")
print("  PASS\n")
n_pass += 1

# --- Summary ---
print("=== smoke_igraph.py summary ===")
print(f"  PASS {n_pass}/{n_total}")
print(f"  Tested against: igraph {ig.__version__}, polars {pl.__version__}")
assert n_pass == n_total, f"{n_total - n_pass} test(s) failed"
print("=== All igraph smoke tests PASSED ===")
sys.exit(0)
