---
name: igraph-r
description: >-
  R network analysis with igraph fronted by tidygraph + ggraph: graph
  construction from edge-list tibbles (tidyverse round-trip), centrality
  (degree, betweenness, closeness, eigenvector, PageRank), community detection
  (Leiden, Louvain, walktrap) with seed discipline, shortest paths, components,
  bipartite construction + projection, and static grammar-of-graphics figures via
  ggraph with seeded layouts. Use for relational/graph data. For road-network
  routing use sf-terra (sfnetworks); for non-graph clustering use tidymodels.
  Use when execution language is R. Python equivalent: igraph.
metadata:
  audience: research-coders
  domain: r-library
  library-version: "igraph 2.2.3, tidygraph 1.3.1, ggraph 2.2.2"
  skill-last-updated: "2026-07-15"
---

# igraph-r Skill

R network analysis with igraph (the C-core graph engine), fronted by tidygraph
(a tidy `tbl_graph` API that wraps igraph's full functionality with dplyr verbs)
and ggraph (grammar-of-graphics static network figures built on the tidygraph
data structure). Covers graph construction from edge-list tibbles with a
round-trip back to tidy node/edge tables, centrality (degree, betweenness,
closeness, eigenvector, PageRank), community detection (Leiden, Louvain,
walktrap) with mandatory seed discipline, shortest paths and connected
components, bipartite graph construction and one-mode projection, and static
visualization via ggraph with seeded layouts. Use when the execution language is
R and the task involves relational/network data. For road-network routing use
sf-terra (sfnetworks); for community detection framed as feature clustering
without an explicit graph, use tidymodels. ERGM/statnet inferential modeling is
deliberately out of scope (see Version Notes). Python equivalent: the igraph skill.

## What is igraph?

igraph is a single C library with R and Python bindings that run the same
algorithms — the R and Python skills share identical semantics because they wrap
the same core:

- **Graph objects**: An igraph object holds vertices and edges plus arbitrary
  vertex/edge/graph attributes. Directedness is a graph-level property set at
  construction (`directed = TRUE/FALSE`).
- **Attribute-driven**: Vertices and edges carry named attributes (`weight`,
  `name`, `type`, etc.). Some attribute names are semantically special — most
  importantly `weight`, which many functions consume automatically (see Gotchas).
- **Computational substrate**: igraph is the algorithmic engine. tidygraph and
  ggraph front it for manipulation and plotting; raw igraph remains the escape
  hatch for algorithms not surfaced tidily.

## What are tidygraph and ggraph?

tidygraph and ggraph give igraph a tidyverse face, matching DAAF's R house style:

- **tbl_graph**: tidygraph's `tbl_graph` is a graph whose node and edge tables are
  manipulable with dplyr verbs. Any function that expects an igraph object also
  accepts a `tbl_graph` — there is zero interop cost between the two.
- **activate()**: `activate(nodes)` / `activate(edges)` selects which table dplyr
  verbs operate on. `as_tibble()` extracts the active table back to a plain tibble
  for downstream statistics.
- **Grammar of graphics**: ggraph applies ggplot2 grammar to networks —
  `ggraph(g, layout = ...) + geom_edge_link() + geom_node_point()`. Layouts are
  a scale-like concept; force-directed layouts are stochastic and need a seed.
- **igraph underneath**: tidygraph re-exports centrality and community-detection
  wrappers (`centrality_degree()`, `group_louvain()`, etc.), but they call the
  same igraph routines and inherit the same gotchas (weight auto-use, seed
  sensitivity). This skill shows both the raw igraph call and the tidygraph verb
  where useful.

## Version Notes

Versions targeted in the DAAF container (R 4.5.3):

| Package | Version | Role | Status |
|---------|---------|------|--------|
| igraph | 2.2.3 | C-core graph engine | **Installed** (P3M snapshot 2026-04-15; CRAN latest is newer) |
| tidygraph | 1.3.1 | Tidy `tbl_graph` API over igraph | **Added to Dockerfile; NOT loadable until container rebuild** |
| ggraph | 2.2.2 | Grammar-of-graphics network figures | **Added to Dockerfile; NOT loadable until container rebuild** |
| graphlayouts | (P3M snapshot) | Layout algorithms; arrives as a ggraph dependency | **Added transitively with ggraph; exact snapshot version unresolved** |

**Installation state (read before running any tidygraph/ggraph code):**
- **igraph 2.2.3** is already installed — it was previously a transitive dependency
  and is now promoted to a first-class framework package. Raw-igraph code runs today.
- **tidygraph 1.3.1** and **ggraph 2.2.2** were added to the Dockerfile's framework
  R block but are **not loadable until the container is rebuilt**. Any script that
  `library(tidygraph)` / `library(ggraph)` will error until then. To rebuild: exit
  the container, then run `bash rebuild_daaf.sh` (`.\rebuild_daaf.ps1` on Windows)
  from the `daaf-docker` folder.
- **graphlayouts** arrives as a ggraph dependency. At the P3M 2026-04-15 snapshot
  it resolves to the release current on that date; the exact version is
  **deliberately not pinned here** (the current CRAN 1.2.4 postdates the snapshot,
  so the snapshot supplies an earlier release). Let the P3M snapshot resolve it at
  build time rather than pinning a version that may not exist in the snapshot.

**igraph 2.x note:** The 2.0 release (May 2024) realigned R igraph to the 0.10 C
core, matching the Python side; the R and Python igraph skills therefore describe
the same algorithms with the same semantics.

**Out of scope — ERGM/statnet (deferred extension):** Exponential random graph
models (the `statnet` stack: `network`, `sna`, `ergm`) are a distinct inferential
method with MCMC cost, model-degeneracy hazards, and network-size limits. They are
**not covered by this skill** and belong to a separate, deferred advanced-inference
extension. This skill covers descriptive network analysis, community detection, and
visualization only.

## How to Use This Skill

### Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `quickstart.md` | tbl_graph construction, edge-list tibble ↔ graph round-trip, I/O, inspection | Starting out or a quick reminder |
| `centrality.md` | Degree, betweenness, closeness, eigenvector, PageRank; `weights = NA` discipline; component/mode guardrails | Computing node importance |
| `community-detection.md` | Leiden, Louvain, walktrap; seed discipline; undirected requirement; modularity | Finding groups/clusters in a graph |
| `paths-components.md` | Shortest paths, distances, diameter, connected components, reachability | Path/reachability/component questions |
| `bipartite.md` | Two-mode graph construction (`type` attribute), one-mode projection | Two-mode (actor–event) data |
| `visualization.md` | ggraph grammar, seeded layouts, edge/node geoms, faceting | Making static network figures |
| `dataframe-interop.md` | `activate()`/`as_tibble()`, node/edge attributes ↔ tibbles for downstream stats | Moving between graph and tidy tables |
| `gotchas.md` | Silent weight auto-use, seed sensitivity, directed/undirected traps, disconnected-graph pitfalls | Debugging or before trusting a result |

### Reading Order

1. **New to igraph in R?** Start with `quickstart.md` then `dataframe-interop.md`
2. **Computing centrality?** Read `centrality.md` (and `gotchas.md` on weight auto-use)
3. **Detecting communities?** Read `community-detection.md` (seed discipline is mandatory)
4. **Paths / reachability?** Read `paths-components.md`
5. **Two-mode data?** Read `bipartite.md`
6. **Making figures?** Read `visualization.md`
7. **Something surprising?** Check `gotchas.md` first — most surprises are weight
   auto-use or an unseeded stochastic step

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `igraph` | Python equivalent — same C core, same algorithms, same semantics for Python pipelines |
| `data-scientist` | Method selection — when/why to use network methods vs. clustering; interpretation guidance |
| `tidyverse` | Data preparation — edge-list and node tables are tibbles; dplyr prepares them and `tbl_graph` round-trips back |
| `ggplot2` | Visualization — ggraph is built on ggplot2; load ggplot2 for themes, scales, and styling |
| `tidymodels` | Non-graph clustering / dimensionality reduction (k-means, PCA, UMAP) when there is no explicit graph structure |
| `sf-terra` | Spatial / road-network routing (sfnetworks, spdep contiguity graphs) — geographic graphs, not general relational graphs |
| `r-python-translation` | Cross-language translation of network code |

**Routing guidance:** Use this skill for general relational/graph data (social
networks, citation graphs, co-occurrence, actor–event structures). For
**road-network routing** (shortest path along a street network) use `sf-terra`
(sfnetworks). For **community detection framed as feature clustering** without an
explicit node/edge graph — e.g., clustering observations by numeric features — use
`tidymodels`, not this skill. For **spatial contiguity weights** (queen/rook
neighbors, distance bands) use `sf-terra` + spdep.

## Quick Decision Trees

### "I need to build a graph from data"

```
Constructing a graph?
+-- From an edge-list tibble -> ./references/quickstart.md
+-- From edge list + separate node table -> ./references/quickstart.md
+-- Directed vs undirected (which to choose) -> ./references/quickstart.md + ./references/gotchas.md
+-- Two-mode (actor-event / bipartite) data -> ./references/bipartite.md
+-- Round-trip graph back to tidy tables -> ./references/dataframe-interop.md
+-- Read/write a graph to file -> ./references/quickstart.md
```

### "I need to measure node importance"

```
Centrality?
+-- Degree (in/out/all) -> ./references/centrality.md
+-- Betweenness / closeness -> ./references/centrality.md (check components first!)
+-- Eigenvector / PageRank -> ./references/centrality.md
+-- Unweighted result but graph has a 'weight' attribute -> ./references/gotchas.md (pass weights = NA)
+-- Weighted centrality (weights = distances) -> ./references/centrality.md
```

### "I need to find groups / communities"

```
Community detection?
+-- Louvain / Leiden (fast modularity) -> ./references/community-detection.md (set.seed first!)
+-- Walktrap (random-walk based) -> ./references/community-detection.md
+-- Directed graph -> convert with as.undirected() first -> ./references/community-detection.md
+-- Reproducible results across runs -> ./references/community-detection.md (seed discipline)
+-- Modularity / evaluating a partition -> ./references/community-detection.md
```

### "I need paths, distances, or components"

```
Paths / reachability?
+-- Shortest path between two nodes -> ./references/paths-components.md
+-- All-pairs distances / diameter -> ./references/paths-components.md
+-- Connected components -> ./references/paths-components.md
+-- Is the graph connected? (before centrality) -> ./references/paths-components.md
```

### "I need to make a network figure"

```
Visualization?
+-- Force-directed layout (FR / KK) -> ./references/visualization.md (set.seed first!)
+-- Color nodes by community / attribute -> ./references/visualization.md
+-- Size nodes by centrality -> ./references/visualization.md
+-- Edge weights / directed arrows -> ./references/visualization.md
+-- Reproducible figure across runs -> ./references/visualization.md (seed discipline)
```

### "I need to move between graphs and tibbles"

```
Graph <-> tidy tables?
+-- Extract node table for downstream stats -> ./references/dataframe-interop.md
+-- Extract edge table -> ./references/dataframe-interop.md
+-- Attach a computed attribute back to nodes -> ./references/dataframe-interop.md
+-- dplyr verbs on nodes/edges (activate) -> ./references/dataframe-interop.md
```

### "Something isn't working"

```
Having issues?
+-- Centrality "ignored" my weights argument / unexpected weighting -> ./references/gotchas.md
+-- Community/layout results differ every run -> ./references/gotchas.md (seed)
+-- cluster_leiden / cluster_louvain error on directed graph -> ./references/gotchas.md
+-- closeness/betweenness gives Inf/NaN or warnings -> ./references/gotchas.md (disconnected)
+-- Directed vs undirected giving surprising numbers -> ./references/gotchas.md
```

## File-First Execution in Research Workflows

In DAAF research pipelines, R network operations follow the **file-first execution
protocol** — code is written to `.R` script files and executed via the
`run_with_capture.sh` wrapper, never run interactively.

**The pattern:**
1. Write network analysis code to `scripts/stage{N}_{type}/{step}_{task-name}.R`
2. Execute via Bash: `bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/{script_name}.R`
3. `run_with_capture.sh` detects the `.R` extension and uses `Rscript` automatically
4. stdout/stderr are appended to the script file as comments
5. If a script fails, create a versioned copy (`_a.R`, `_b.R`, etc.) for fixes

Read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the complete protocol.

**R network script structure follows DAAF conventions:**

```r
# --- Config ---
library(igraph)
library(tidygraph)
library(dplyr)

PROJECT_DIR <- "/daaf/research/YYYY-MM-DD_Project"
SEED <- 20260715  # fixed seed for reproducible community detection

# --- Load ---
# INTENT: Build a co-authorship graph from an edge-list tibble
# ASSUMES: edges tibble has columns 'from' and 'to' naming authors
edges <- arrow::read_parquet(file.path(PROJECT_DIR, "data", "coauthor_edges.parquet"))
g <- as_tbl_graph(edges, directed = FALSE)
cat("Nodes:", igraph::gorder(g), " Edges:", igraph::gsize(g), "\n")

# --- Transform ---
# INTENT: Detect communities; graph is unweighted so suppress weight auto-use
# REASONING: cluster_louvain requires an undirected graph (already undirected here)
# ASSUMES: no 'weight' edge attribute; weights = NA makes that explicit
set.seed(SEED)  # community detection is stochastic — seed for reproducibility
comm <- cluster_louvain(g, weights = NA)
g <- g |> activate(nodes) |> mutate(community = as.factor(membership(comm)))

# --- Validate ---
stopifnot(igraph::gorder(g) == length(membership(comm)))
cat("Communities found:", length(comm), " Modularity:", round(modularity(comm), 3), "\n")

# --- Save ---
node_tbl <- g |> activate(nodes) |> as_tibble()
arrow::write_parquet(node_tbl, file.path(PROJECT_DIR, "data", "nodes_with_community.parquet"))
cat("Saved: nodes_with_community.parquet\n")
```

## Quick Reference

### Essential Setup

```r
library(igraph)      # graph engine (centrality, community, paths)
library(tidygraph)   # tbl_graph, activate(), dplyr verbs on graphs
library(ggraph)      # grammar-of-graphics network figures (needs container rebuild)
library(dplyr)       # data manipulation for node/edge tables
library(ggplot2)     # themes/scales for ggraph
```

### Core Operations

| Operation | Code | Package |
|-----------|------|---------|
| Graph from edge tibble | `as_tbl_graph(edges, directed = FALSE)` | tidygraph |
| Graph from igraph directly | `graph_from_data_frame(edges, directed = FALSE, vertices = nodes)` | igraph |
| Node count / edge count | `gorder(g)` / `gsize(g)` | igraph |
| Activate node table | `g \|> activate(nodes)` | tidygraph |
| Node table to tibble | `g \|> activate(nodes) \|> as_tibble()` | tidygraph |
| Degree (in/out/all) | `degree(g, mode = "all")` | igraph |
| Betweenness (unweighted) | `betweenness(g, weights = NA)` | igraph |
| Closeness (check components!) | `closeness(g, weights = NA)` | igraph |
| Eigenvector centrality | `eigen_centrality(g, weights = NA)$vector` | igraph |
| PageRank | `page_rank(g)$vector` | igraph |
| Community (Louvain) | `set.seed(s); cluster_louvain(g, weights = NA)` | igraph |
| Community (Leiden) | `set.seed(s); cluster_leiden(g, objective_function = "modularity")` | igraph |
| Membership vector | `membership(comm)` | igraph |
| Modularity of a partition | `modularity(comm)` | igraph |
| Connected components | `components(g)` | igraph |
| Is connected? | `is_connected(g)` | igraph |
| Shortest path | `shortest_paths(g, from, to)` | igraph |
| Convert to undirected | `as.undirected(g, mode = "collapse")` | igraph |
| Bipartite projection | `bipartite_projection(g)` | igraph |
| Static plot | `set.seed(s); ggraph(g, layout = "fr") + geom_edge_link() + geom_node_point()` | ggraph |

### The Two Non-Negotiables

| Rule | Why | Reference |
|------|-----|-----------|
| **Pass `weights = NA` for unweighted centrality/community** | igraph silently auto-uses a `weight` edge attribute and treats it as **distance** (higher = longer path), not strength | `gotchas.md`, `centrality.md` |
| **`set.seed()` before any stochastic step** | Force-directed layouts and community detection are non-deterministic; unseeded results are irreproducible. igraph's old `srand()` is deprecated/ignored — use `set.seed()` | `gotchas.md`, `community-detection.md`, `visualization.md` |

## Topic Index

| Topic | Reference File |
|-------|---------------|
| tbl_graph construction | `./references/quickstart.md` |
| Edge-list tibble to graph | `./references/quickstart.md` |
| Directed vs undirected choice | `./references/quickstart.md` |
| Graph I/O (read/write) | `./references/quickstart.md` |
| Graph inspection (order, size, attributes) | `./references/quickstart.md` |
| Degree centrality (in/out/all) | `./references/centrality.md` |
| Betweenness centrality | `./references/centrality.md` |
| Closeness centrality | `./references/centrality.md` |
| Eigenvector centrality | `./references/centrality.md` |
| PageRank | `./references/centrality.md` |
| weights = NA discipline | `./references/centrality.md` |
| Component check before centrality | `./references/centrality.md` |
| Louvain community detection | `./references/community-detection.md` |
| Leiden community detection | `./references/community-detection.md` |
| Walktrap community detection | `./references/community-detection.md` |
| Seed discipline (community) | `./references/community-detection.md` |
| Undirected requirement for Leiden/Louvain | `./references/community-detection.md` |
| Modularity | `./references/community-detection.md` |
| Shortest paths | `./references/paths-components.md` |
| Distances / diameter | `./references/paths-components.md` |
| Connected components | `./references/paths-components.md` |
| Reachability | `./references/paths-components.md` |
| Bipartite graph construction | `./references/bipartite.md` |
| One-mode projection | `./references/bipartite.md` |
| ggraph layouts | `./references/visualization.md` |
| Seeded layouts | `./references/visualization.md` |
| Node/edge geoms | `./references/visualization.md` |
| Color by community | `./references/visualization.md` |
| activate() / as_tibble() | `./references/dataframe-interop.md` |
| Node/edge attributes to tibbles | `./references/dataframe-interop.md` |
| dplyr verbs on graphs | `./references/dataframe-interop.md` |
| Silent weight auto-use | `./references/gotchas.md` |
| Seed sensitivity | `./references/gotchas.md` |
| Directed/undirected traps | `./references/gotchas.md` |
| Disconnected-graph centrality | `./references/gotchas.md` |

## Citation

igraph, tidygraph, and ggraph are software; when they are used as primary
analytical tools, include software citations in the report's Software & Tools
references. Pipeline agents should propagate these citations into report
deliverables per `agent_reference/CITATION_REFERENCE.md` (a registry entry for the
igraph ecosystem is maintained there — reference it rather than duplicating).

**igraph (R) requires all three references together.** The installed `citation("igraph")`
CITATION file states verbatim: *"To cite igraph please use these three references."*
The 2006 paper is **not** superseded by the newer ones — the citation is cumulative:

> Csárdi, G. and Nepusz, T. (2006). "The igraph software package for complex network
> research." *InterJournal, Complex Systems*, 1695. https://igraph.org
>
> Antonov, M., Csárdi, G., Horvát, S., Müller, K., Nepusz, T., Noom, D., Salmon, M.,
> Traag, V., Foucault Welles, B., and Zanini, F. (2023). "igraph enables fast and
> robust network analysis across programming languages." *arXiv preprint
> arXiv:2311.10260.* https://doi.org/10.48550/arXiv.2311.10260
>
> Csárdi, G., Nepusz, T., Traag, V., Horvát, S., Zanini, F., Noom, D., Müller, K.,
> Schoch, D., and Salmon, M. (2026). *igraph: Network Analysis and Visualization in R.*
> R package version 2.2.3. https://doi.org/10.5281/zenodo.7682609

> **Note on the 2023 reference:** As of the installed CITATION file (igraph 2.2.3) it
> is an arXiv preprint; cite it as such. The DOI `10.48550/arXiv.2311.10260` is stable
> regardless of eventual journal publication.

BibTeX (reproduce all three):

```bibtex
@Article{,
  title = {The igraph software package for complex network research},
  author = {G\'abor Cs\'ardi and Tam\'as Nepusz},
  journal = {InterJournal},
  volume = {Complex Systems},
  pages = {1695},
  year = {2006},
  url = {https://igraph.org},
}

@Article{,
  title = {igraph enables fast and robust network analysis across programming languages},
  author = {Michael Antonov and G\'abor Cs\'ardi and Szabolcs Horv\'at and Kirill M\"uller
            and Tam\'as Nepusz and Daniel Noom and Ma\"elle Salmon and Vincent Traag
            and Brooke Foucault Welles and Fabio Zanini},
  journal = {arXiv preprint arXiv:2311.10260},
  year = {2023},
  doi = {10.48550/arXiv.2311.10260},
}

@Manual{,
  title = {{igraph}: Network Analysis and Visualization in R},
  author = {G\'abor Cs\'ardi and Tam\'as Nepusz and Vincent Traag and Szabolcs Horv\'at
            and Fabio Zanini and Daniel Noom and Kirill M\"uller and David Schoch
            and Ma\"elle Salmon},
  year = {2026},
  note = {R package version 2.2.3},
  doi = {10.5281/zenodo.7682609},
  url = {https://CRAN.R-project.org/package=igraph},
}
```

If tidygraph is used for graph manipulation, additionally cite:

> Pedersen, T.L. (2024). *tidygraph: A Tidy API for Graph Manipulation.* R package
> version 1.3.1. https://CRAN.R-project.org/package=tidygraph

If ggraph is used for network figures, additionally cite:

> Pedersen, T.L. (2025). *ggraph: An Implementation of Grammar of Graphics for Graphs
> and Networks.* R package version 2.2.2. https://CRAN.R-project.org/package=ggraph

**Licenses:** igraph is **GPL-2 (or later)**; tidygraph and ggraph are **MIT**
(`MIT + file LICENSE`). Acknowledge these in the report's software/licensing notes
when the packages are central to the analysis.

**Cite when:** igraph/tidygraph/ggraph are used for centrality, community
detection, path analysis, or network figures central to the analysis.
**Do not cite when:** only used incidentally (e.g., a single degree count as a
descriptive aside).
