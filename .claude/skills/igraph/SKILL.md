---
name: igraph
description: >-
  Network/graph analysis with python-igraph: graph construction from edge-list DataFrames (Polars round-trip), centrality (degree, betweenness, closeness, eigenvector, PageRank), community detection (Leiden, Louvain, walktrap) with seed discipline, paths/components, bipartite construction and projection, static visualization (matplotlib backend). Use for relational data — collaboration, friendship, organizational, or co-occurrence networks. For geographic road-network routing use geopandas (OSMnx); for non-graph clustering use scikit-learn. R equivalent: igraph-r (use when execution language is R).
metadata:
  audience: research-coders
  domain: python-library
  library-version: "1.0.0 (python-igraph)"
  skill-last-updated: "2026-07-15"
---

# igraph Skill

python-igraph network analysis library for Python: constructing, analyzing, and visualizing graphs and networks. Covers graph construction from edge-list DataFrames with Polars round-trips, centrality measures (degree, betweenness, closeness, eigenvector, PageRank), community detection (Leiden, Louvain, walktrap) with mandatory seed discipline, shortest paths and connected components, bipartite graph construction and one-mode projection, node/edge attribute interop with tidy tables for downstream statistics, and static visualization via the matplotlib backend. Use when working with relational data — collaboration networks, friendship/social ties, organizational hierarchies, co-occurrence or co-authorship structures. For geographic road-network routing, use geopandas (OSMnx). For non-graph clustering or dimensionality reduction, use scikit-learn. ERGM and statistical/generative network models are out of scope (see Version Notes).

Comprehensive skill for network analysis with python-igraph. Use the decision trees below to find the right guidance, then load detailed reference files as needed.

## Version Notes

This skill targets **python-igraph 1.0.0** (released 2025-10-23).

- **Package vs. import name:** the PyPI package is `igraph` (`pip install igraph`), imported as `import igraph`. Historically the package was distributed as `python-igraph`; that name is now an alias. Do not confuse it with the unrelated `igraph` typo-squat or with `jgraph`.
- **Installation in DAAF:** `igraph==1.0.0` is pinned in the Dockerfile framework install block and is **pre-installed in the current image** (import verified against the live container 2026-07-16) — no installation needed. Runtime installs are blocked in DAAF (see CLAUDE.md § Runtime Package Installation); for any related extra, escalate to the user for a Dockerfile addition (user additions block) and rebuild.
- **Shared C core with R:** python-igraph and the R `igraph` package wrap the *same* C library, so algorithms and coded-value semantics match across the language pair. This is why the DAAF pair is `igraph` (Python) ↔ `igraph-r` (R) rather than pairing two unrelated engines — it eliminates cross-language semantic drift.
- **Plotting backend:** this skill uses the **matplotlib backend** (`igraph.plot(g, target=ax)`), which is already in the container. The default Cairo backend (`cairocffi`) is deliberately **not** installed — do not call plotting code paths that require it.
- **NetworkX relationship:** NetworkX is the documentation and teaching touchstone of the Python network-analysis ecosystem (broadest docs, near-universal course adoption) but is substantially slower at research scale. This skill uses python-igraph, not NetworkX; NetworkX is mentioned only as the ecosystem reference point.
- **Out of scope — deferred:** ERGM and other statistical/generative network models (exponential random graph models, stochastic block model *inference*, TERGM) are a distinct inferential method family with MCMC cost and model-degeneracy hazards. They are a **deferred future extension**, not part of this skill.

## What is python-igraph?

python-igraph provides a graph data structure and a large library of graph algorithms:

- **Graph object:** a `Graph` holds vertices (nodes) and edges, each optionally carrying named attributes. Directedness is a property of the whole graph (`directed=True/False`), set at construction.
- **Edge-list construction:** graphs are most naturally built from an edge list — a two-column table of (source, target) pairs — which maps cleanly to a Polars DataFrame. Vertex and edge attributes ride alongside as additional columns.
- **Algorithm coverage:** centrality (degree, betweenness, closeness, eigenvector, PageRank), community detection (Leiden, Louvain/multilevel, walktrap), shortest paths, connected components, and bipartite projection.
- **Attribute interop:** vertex/edge attributes round-trip to tidy tables, so graph-derived measures (e.g., per-node centrality) flow back into Polars for downstream regression or joins.
- **Static visualization:** `igraph.plot()` renders onto a matplotlib `Axes` with a chosen layout; force-directed layouts require a seed for reproducible figures.

## How to Use This Skill

### Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `quickstart.md` | Graph construction, edge-list ↔ Polars round-trip, I/O, inspection | Starting with igraph |
| `centrality.md` | Degree, betweenness, closeness, eigenvector, PageRank; directed modes; connectivity guardrail | Computing node importance |
| `community-detection.md` | Leiden, Louvain, walktrap; seed discipline; directed-graph handling | Finding clusters/communities |
| `paths-components.md` | Shortest paths, distances, diameter, connected components, reachability | Path and connectivity analysis |
| `bipartite.md` | Bipartite construction from two-column tables, one-mode projection | Two-mode (affiliation) networks |
| `visualization.md` | matplotlib-backend plotting, seeded layouts, styling | Making network figures |
| `dataframe-interop.md` | Node/edge attributes ↔ tidy tables for downstream stats | Moving results in/out of Polars |
| `gotchas.md` | Directed/weighted traps, seed omissions, disconnected-graph pitfalls | Debugging or reviewing |

### Reading Order

1. **New to igraph?** Start with `quickstart.md`, then `centrality.md`.
2. **Detecting communities?** Read `community-detection.md` (seed discipline is mandatory).
3. **Making figures?** Read `visualization.md` (relies on `quickstart.md` for construction).
4. **Feeding results into analysis?** Read `dataframe-interop.md`.
5. **Having issues?** Check `gotchas.md` first.

**The reference-file routing in this skill applies to advisory and brainstorming turns as much as implementation.** Recommending an approach, reviewing a plan, or answering a question that touches a routed topic calls for reading the routed reference file just as much as writing code does — the reference files carry curated caveats (directed-vs-undirected semantics, weight interpretation, seed discipline) that this overview and general knowledge lack.

## Related Skills

| Skill | Relationship |
|-------|-------------|
| **polars** | Edge lists, node/edge attribute tables, and graph-derived measures live in Polars DataFrames. Use polars for all tabular transformation before building a graph and after extracting results. |
| **data-scientist** | Methodology routing — when a network representation is appropriate, how to interpret centrality/community results, and the pitfalls (betweenness ≠ resilience; centrality ill-defined across components). Load alongside for research workflows. |
| **scikit-learn** | For clustering/dimensionality reduction on feature matrices *without* graph structure (k-means, PCA, UMAP), use scikit-learn — not community detection. |
| **geopandas** | For geographic road-network routing (OSMnx) and spatial contiguity graphs, use geopandas — not igraph. |
| **plotnine / plotly** | For non-network figures of graph-derived measures (centrality distributions, degree histograms), use plotnine or plotly. |

**Routing guidance:** igraph is for *relational* structure — entities connected by ties. If the data is a feature matrix and the goal is clustering by similarity, that is scikit-learn, not igraph. If the "network" is a road or spatial-adjacency graph tied to geography, that is geopandas (OSMnx). Community detection here means graph-topology community detection (Leiden/Louvain), not feature-space clustering.

## Quick Decision Trees

### "I need to build or inspect a graph"

```
Constructing / inspecting a graph?
├─ From a Polars edge-list DataFrame → ./references/quickstart.md
├─ With node and edge attributes → ./references/quickstart.md
├─ Directed vs. undirected choice → ./references/quickstart.md
├─ Read/write graph file (GraphML, edgelist) → ./references/quickstart.md
├─ Inspect vcount / ecount / degree summary → ./references/quickstart.md
└─ Convert directed → undirected → ./references/quickstart.md
```

### "I need to measure node importance (centrality)"

```
Centrality?
├─ Degree (in / out / all) → ./references/centrality.md
├─ Betweenness → ./references/centrality.md
├─ Closeness → ./references/centrality.md
├─ Eigenvector centrality → ./references/centrality.md
├─ PageRank → ./references/centrality.md
├─ Weighted centrality (explicit weights=) → ./references/centrality.md
└─ Check connectivity BEFORE closeness/betweenness → ./references/centrality.md
```

### "I need to find communities or clusters"

```
Community detection?
├─ Leiden → ./references/community-detection.md
├─ Louvain (multilevel) → ./references/community-detection.md
├─ Walktrap → ./references/community-detection.md
├─ Set a seed for reproducibility → ./references/community-detection.md
├─ Directed graph (convert to undirected) → ./references/community-detection.md
└─ Weighted community detection → ./references/community-detection.md
```

### "I need paths, distances, or components"

```
Paths / connectivity?
├─ Shortest path between two nodes → ./references/paths-components.md
├─ All-pairs distances → ./references/paths-components.md
├─ Diameter → ./references/paths-components.md
├─ Connected components (weak / strong) → ./references/paths-components.md
├─ Largest connected component (giant) → ./references/paths-components.md
└─ Reachability check → ./references/paths-components.md
```

### "I have a two-mode (bipartite) network"

```
Bipartite / affiliation network?
├─ Build bipartite graph from two-column table → ./references/bipartite.md
├─ Project to one mode → ./references/bipartite.md
├─ Weighted projection (shared-affiliation counts) → ./references/bipartite.md
└─ Verify bipartite structure → ./references/bipartite.md
```

### "I need to make a figure or move results into analysis"

```
Visualization / interop?
├─ Plot the network (matplotlib backend) → ./references/visualization.md
├─ Seeded reproducible layout → ./references/visualization.md
├─ Style by attribute (color/size) → ./references/visualization.md
├─ Extract per-node measures to a Polars frame → ./references/dataframe-interop.md
├─ Attach a Polars column as a node attribute → ./references/dataframe-interop.md
└─ Export edge list back to Polars → ./references/dataframe-interop.md
```

### "Something isn't working"

```
Having issues?
├─ Community detection errors on a directed graph → ./references/gotchas.md
├─ Non-reproducible layout or community results → ./references/gotchas.md
├─ Closeness/betweenness returns inf or nan → ./references/gotchas.md
├─ Weighted result looks backwards → ./references/gotchas.md
├─ Vertex names vs. indices confusion → ./references/gotchas.md
└─ General troubleshooting → ./references/gotchas.md
```

## File-First Execution in Research Workflows

**Important:** In data research pipelines (see `CLAUDE.md`), graph operations are executed through **script files**, not interactively. This ensures auditability and reproducibility.

**The pattern:**
1. Write graph analysis code to `scripts/stage{N}_{type}/{step}_{task-name}.py`
2. Execute via Bash with the automatic output-capture wrapper script
3. Validation results get embedded in scripts as comments
4. If failed, create a versioned copy for fixes

Closely read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the mandatory file-first execution protocol covering complete code-file writing, output capture, and file-versioning rules.

**See:**
- `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` — Script execution protocol and format with validation

The examples in reference files show igraph syntax. In research workflows, wrap them in scripts following the file-first pattern. Every stochastic example (community detection, force-directed layout) is preceded by `random.seed()` — preserve that discipline when adapting examples.

---

## Quick Reference

### Essential Imports

```python
import igraph as ig
import polars as pl
import random  # seed BEFORE any stochastic layout or community detection
```

### Core Operations

| Operation | Code |
|-----------|------|
| Build from edge tuples | `g = ig.Graph(edges=edge_tuples, directed=False)` |
| Build from Polars edge list | `g = ig.Graph.DataFrame(edges_pdf, directed=False)` (via pandas bridge — see quickstart) |
| Node / edge counts | `g.vcount()`, `g.ecount()` |
| Degree (directed) | `g.degree(mode="in")` / `"out"` / `"all"` |
| Betweenness | `g.betweenness(weights=g.es["weight"])` |
| Closeness | `g.closeness(weights=g.es["weight"])` |
| Eigenvector | `g.eigenvector_centrality(weights=g.es["weight"])` |
| PageRank | `g.pagerank(weights=g.es["weight"])` |
| To undirected | `g_u = g.as_undirected()` |
| Louvain (undirected) | `random.seed(0); part = g_u.community_multilevel(weights=g_u.es["weight"])` |
| Leiden (undirected) | `random.seed(0); part = g_u.community_leiden(objective_function="modularity")` |
| Walktrap | `random.seed(0); part = g_u.community_walktrap().as_clustering()` |
| Connected components | `comp = g.connected_components(mode="weak")` |
| Giant component | `giant = g.connected_components().giant()` |
| Shortest path | `g.get_shortest_paths(src, to=dst, weights=g.es["weight"])` |
| Bipartite projection | `proj1, proj2 = g.bipartite_projection()` |
| Plot (matplotlib) | `ig.plot(g, target=ax, layout=g.layout("fr"))` |

> **Weights are distances, not strengths.** In path-based measures (betweenness, closeness, shortest paths), a higher `weight` means a *longer* path. If your weights encode connection *strength*, invert them before passing. Always pass `weights=` explicitly in weighted examples (see gotchas).

### Directed-Graph Mode Cheat Sheet

| `mode=` | Meaning |
|---------|---------|
| `"in"` | Incoming edges only (indegree) |
| `"out"` | Outgoing edges only (outdegree) |
| `"all"` | Both directions combined |

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Graph construction from edge list | `./references/quickstart.md` |
| Edge-list ↔ Polars round-trip | `./references/quickstart.md` |
| Node / edge attributes | `./references/quickstart.md` |
| Directed vs. undirected | `./references/quickstart.md` |
| Graph I/O (GraphML, edgelist) | `./references/quickstart.md` |
| Graph inspection | `./references/quickstart.md` |
| Degree centrality | `./references/centrality.md` |
| Betweenness centrality | `./references/centrality.md` |
| Closeness centrality | `./references/centrality.md` |
| Eigenvector centrality | `./references/centrality.md` |
| PageRank | `./references/centrality.md` |
| Weighted centrality | `./references/centrality.md` |
| Connectivity check before centrality | `./references/centrality.md` |
| Leiden community detection | `./references/community-detection.md` |
| Louvain / multilevel | `./references/community-detection.md` |
| Walktrap | `./references/community-detection.md` |
| Modularity | `./references/community-detection.md` |
| Seed discipline | `./references/community-detection.md` |
| Directed-graph community handling | `./references/community-detection.md` |
| Shortest paths | `./references/paths-components.md` |
| Distances / diameter | `./references/paths-components.md` |
| Connected components | `./references/paths-components.md` |
| Giant component | `./references/paths-components.md` |
| Reachability | `./references/paths-components.md` |
| Bipartite construction | `./references/bipartite.md` |
| One-mode projection | `./references/bipartite.md` |
| Weighted projection | `./references/bipartite.md` |
| Network plotting (matplotlib) | `./references/visualization.md` |
| Seeded layouts | `./references/visualization.md` |
| Styling by attribute | `./references/visualization.md` |
| Attributes → Polars frame | `./references/dataframe-interop.md` |
| Polars column → node attribute | `./references/dataframe-interop.md` |
| Edge-list export | `./references/dataframe-interop.md` |
| Directed/weighted traps | `./references/gotchas.md` |
| Non-reproducible results | `./references/gotchas.md` |
| inf/nan centrality on disconnected graphs | `./references/gotchas.md` |
| Vertex names vs. indices | `./references/gotchas.md` |

## Citation

python-igraph carries formal software attribution. When igraph is used as a
primary analytical tool (any centrality, community-detection, path, or bipartite
analysis central to the results), include the following in the report's
**Software & Tools** references. python-igraph's own `CITATION.cff` names the
2006 Csárdi & Nepusz article as the preferred citation; cite the 2023
cross-language paper as supplemental.

**Preferred citation (required):**

> Csárdi, G., & Nepusz, T. (2006). The igraph software package for complex network research. *InterJournal, Complex Systems*, 1695. https://igraph.org

**Supplemental citation (recommended for cross-language / reproducibility work):**

> Antonov, M., Csárdi, G., Horvát, S., Müller, K., Nepusz, T., Noom, D., Salmon, M., Traag, V., Foucault Welles, B., & Zanini, F. (2023). igraph enables fast and robust network analysis across programming languages. *arXiv preprint* arXiv:2311.10260. https://doi.org/10.48550/arXiv.2311.10260

**BibTeX:**

```bibtex
@Article{igraph2006,
  title   = {The igraph software package for complex network research},
  author  = {G{\'a}bor Cs{\'a}rdi and Tam{\'a}s Nepusz},
  journal = {InterJournal},
  volume  = {Complex Systems},
  pages   = {1695},
  year    = {2006},
  url     = {https://igraph.org},
}

@Article{igraph2023,
  title   = {igraph enables fast and robust network analysis across programming languages},
  author  = {Michael Antonov and G{\'a}bor Cs{\'a}rdi and Szabolcs Horv{\'a}t and
             Kirill M{\"u}ller and Tam{\'a}s Nepusz and Daniel Noom and Ma{\"e}lle Salmon and
             Vincent Traag and Brooke Foucault Welles and Fabio Zanini},
  journal = {arXiv preprint arXiv:2311.10260},
  year    = {2023},
  doi     = {10.48550/arXiv.2311.10260},
}
```

**License:** python-igraph is distributed under **GPL-2.0-or-later** (from its
`CITATION.cff`). This is a copyleft license; acknowledge it in the report's
software attribution alongside the citation.

**Cite when:** igraph produces centrality, community structure, paths, or
bipartite projections that inform the analysis or appear in figures/tables.
**Do not cite when:** igraph is used only for a throwaway structural check with no
bearing on reported results.

Pipeline agents must propagate these citations into the report's Software & Tools
section per `agent_reference/CITATION_REFERENCE.md` — the igraph registry entry
there is the canonical source for pipeline citation propagation and verification.
For method-specific citations (e.g., the Leiden algorithm), consult
`community-detection.md` and `agent_reference/CITATION_REFERENCE.md`.
