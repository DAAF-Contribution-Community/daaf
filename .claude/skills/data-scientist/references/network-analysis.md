# Network Analysis Methodology

Conceptual foundations for network (graph) analysis — when a network frame is the right frame, how to conceptualize nodes and edges, how to choose a centrality measure for a research question, and how to interpret community-detection and bipartite results without over-reading them. This guide is code-agnostic. Whenever graphs or network operations enter the discussion — in advice or in code — load the `igraph` skill (Python — python-igraph, matplotlib rendering) or the `igraph-r` skill (R — igraph fronted by tidygraph/ggraph): they carry the syntax plus the environment constraints and curated caveats (auto-weighting behavior, directed/undirected requirements, seed mechanics) that general knowledge lacks or gets wrong.

## When a Network Frame Is Appropriate

Not every dataset with relationships needs graph methods. The decision hinges on whether the *relationships themselves* — connectivity, position, brokerage, reachability — are the object of study, or whether the relationships are just one more attribute of individual units.

```
Does my research question depend on relational structure?
├─ Question is about attributes of individual units
│   └─ How much? How many? What predicts an outcome for a unit?
│      → A network frame is NOT needed. Analyze as ordinary tabular data
│        (descriptive stats, regression, ML). Even relational data (e.g., a
│        "number of collaborators" column) can be a plain feature.
├─ Question is about a unit's POSITION in a web of ties
│   └─ Who is central? Who bridges otherwise-separate groups? Who is peripheral?
│      → Network frame fits. Centrality analysis.
├─ Question is about GROUP structure emergent from ties
│   └─ Are there cohesive subgroups / communities? Who clusters with whom?
│      → Network frame fits. Community detection.
├─ Question is about REACHABILITY or flow
│   └─ How far apart are units? Is the network connected? What paths exist?
│      → Network frame fits. Paths, components, diameter.
└─ Question is about the DYADS themselves (why ties form)
    └─ What predicts the presence of a tie? Is there reciprocity, transitivity?
       → This is statistical network modeling (ERGM/SAOM) — NOT currently
         covered by DAAF skills (see "Out of Current Scope" below).
```

**The core test:** if you could answer the question after collapsing the network to a table of node-level summary statistics without losing what you care about, you probably do not need graph machinery. If the answer requires knowing *who is connected to whom*, you do.

> **Relationship to spatial networks:** Road-network routing, service areas, and network-constrained point patterns are a spatial specialization covered by the geospatial stack (Python: OSMnx/PySAL `spaghetti`; R: `sfnetworks`), not by the general graph skills here. The `geospatial-analysis.md` reference's "Three Ways to Represent Spatial Reality" note points here for *general* graphs; route spatially-embedded routing problems back to `geopandas`/`sf-terra`.

---

## Conceptualizing the Graph: Nodes, Edges, Directedness, Weights

Before any computation, four modeling decisions determine what every downstream metric means. Getting these wrong produces numbers that compute cleanly but answer the wrong question.

### Nodes and Edges

- **Nodes (vertices)** are the units whose relationships you study — people, institutions, papers, genes, places.
- **Edges (ties)** are the relationships. The single most important question is *what does an edge mean?* A co-authorship edge, a "sent-an-email" edge, and a "reports-to" edge have completely different semantics and support completely different inferences. Document the edge definition explicitly, the way you would document a variable.
- **Edge-list construction:** In DAAF workflows, graphs are typically built from an edge-list DataFrame (Polars/tidyverse) — two columns naming the endpoints of each tie, plus optional attribute columns (weight, type, timestamp). The graph → tidy-table round-trip (edge list → graph → node/edge tables back out) keeps the analysis inside the auditable file-first pipeline.

### Directedness

| Choice | Edge means | Consequence |
|--------|-----------|-------------|
| **Undirected** | A symmetric relationship (co-authorship, friendship-if-mutual, co-occurrence) | Degree = count of neighbors; one path notion |
| **Directed** | An asymmetric relationship (citation, following, money flow) | Separate in-degree vs. out-degree; paths respect direction; reachability is asymmetric |

Directedness is not cosmetic. In-degree (who is pointed *to*) and out-degree (who points *out*) answer different questions — a highly-cited paper has high in-degree, a review paper high out-degree. When in doubt about a metric under directedness, confirm the `mode` argument (`"in"`, `"out"`, `"all"`) the library applies.

**Community detection is undirected-only in the common igraph algorithms.** In R, `cluster_leiden()` and `cluster_louvain()` require an undirected graph and will error or mishandle directed input — convert explicitly (`as.undirected()`) and decide *how* to collapse reciprocal/asymmetric ties before doing so. In Python, treat Leiden/Louvain as undirected by default and convert unless you have verified directed support at runtime.

### Weights — and the Distance/Strength Trap

Edge weights can mean opposite things, and the library's default is a common source of silent error.

> **The weights-as-distances trap:** igraph treats a `weight` edge attribute as a **distance** (higher = farther apart / longer path), not as a connection strength. If your weights encode *strength* (higher = closer / stronger tie), passing them raw inverts every distance-based metric (closeness, betweenness, shortest paths). And critically: **if the graph carries a `weight` attribute, igraph uses it automatically** in `betweenness()`, `closeness()`, `cluster_leiden()`, and related functions — you do not have to ask for it. To force an unweighted computation, pass `weights = NA` (R) / the equivalent explicit override (Python), not `NULL` (which triggers the auto-use). Before running any distance-based metric on a weighted graph, decide deliberately: use the weights as distances, invert strength-to-distance, or suppress with `weights = NA`.

---

## Centrality Selection

There is no single "importance" — each centrality measure operationalizes a *different* theory of what makes a node matter. Choose the measure whose definition matches the research question, not the one that is most familiar.

| Measure | Node is central if it… | Research question it answers | Key caveats |
|---------|------------------------|------------------------------|-------------|
| **Degree** | Has many direct ties | "Who is most active / most connected locally?" | Purely local; ignores position in the wider structure. Under directedness, split into in-degree vs. out-degree |
| **Betweenness** | Lies on many shortest paths between other pairs | "Who brokers / bridges between otherwise-separate parts?" | Expensive on large graphs; **NOT a resilience or robustness metric** (see below); ill-defined pairs across disconnected components contribute nothing |
| **Closeness** | Is a short average distance from all others | "Who can reach the whole network fastest?" | **Requires a connected component** — undefined when some nodes are unreachable; compute within components or use harmonic closeness |
| **Eigenvector** | Is connected to other well-connected nodes | "Who is influential by keeping powerful company?" | Can concentrate on one dense region; convergence issues on some directed/disconnected graphs |
| **PageRank** | Receives many links from nodes that themselves receive many links (with damping) | "Who is important in a directed flow / endorsement sense?" | Directed-graph-native; damping factor is a modeling choice; more robust than raw eigenvector on directed graphs |

### Two Load-Bearing Caveats

- **Betweenness is not a resilience metric.** It is common — and wrong — to read high betweenness as "this node's removal would fragment the network" or "this node is a robustness bottleneck." Betweenness measures shortest-path brokerage, which is not a theoretically valid measure of network resilience. If the question is about robustness to node removal, model that directly (e.g., recompute connectivity/component structure under node deletion), do not substitute betweenness.
- **Closeness and betweenness assume reachability.** Both are defined in terms of shortest paths. When the graph has multiple components (see the guardrail below), pairs in different components have no finite path, and these measures become ill-defined or silently restricted to within-component pairs. Always establish the component structure first.

---

## Community Detection

Community detection partitions nodes into cohesive subgroups (more ties within than between). It is exploratory and inherently under-determined — different algorithms, resolutions, and random seeds yield different partitions of the same graph.

### Algorithm Selection

| Algorithm | Approach | Notes |
|-----------|----------|-------|
| **Leiden** | Refinement of Louvain that guarantees well-connected communities | **Preferred default.** Fixes a known Louvain flaw where communities could be internally disconnected |
| **Louvain** | Greedy modularity optimization via local moving | Fast and widely used, but can return **internally disconnected** communities; superseded by Leiden for most purposes |
| **Walktrap** | Random-walk-based (short walks tend to stay within communities) | A reasonable alternative with a different inductive bias; useful as a robustness comparison |

### Mandatory Seed Discipline

Leiden and Louvain visit nodes in random order and make non-deterministic scheduling decisions; **their output depends on the random seed.** Two runs without a fixed seed can produce different community counts and assignments on identical data. This is a reproducibility hazard, not a nuisance.

- **Always set a seed** before community detection, and **record the seed** in the script and the report so the partition is reproducible. In R this is `set.seed()` (igraph hooks into R's RNG); in Python, `random.seed()` before the call is the documented simple path.
- **Report the modularity** and, where feasible, check partition **stability** across several seeds — if the community structure dissolves under re-seeding, it is fragile and should be reported as such rather than presented as a firm finding.

### Modularity Caveats

Modularity optimization has a known **resolution limit**: it can fail to detect communities smaller than a scale set by the total number of edges, merging genuinely distinct small communities. High modularity is not proof of meaningful structure — random graphs can attain non-trivial modularity. Treat a partition as a hypothesis to interrogate (do the communities correspond to something substantively interpretable?), not as ground truth.

**Directedness constraint (repeat):** the common igraph community algorithms are undirected-only. Convert directed graphs to undirected deliberately, documenting how asymmetric ties were collapsed.

---

## Paths, Components, and the Disconnected-Graph Guardrail

Path-based analysis (shortest paths, diameter, average path length) and reachability depend entirely on the component structure of the graph.

- **Components** are maximal sets of mutually reachable nodes. A graph with several components is several sub-networks that happen to share a data structure.
- **The guardrail:** before computing closeness, betweenness, diameter, or average path length, **establish the component structure.** These metrics are ill-defined across components — unreachable pairs have infinite distance. Options: compute within the largest connected component (and say so), report per-component, or use variants defined for disconnected graphs (e.g., harmonic centrality instead of closeness). Silently running a global closeness on a multi-component graph produces numbers that look fine and mean nothing.
- **Directed graphs** distinguish weakly connected (ignoring direction) from strongly connected (respecting direction) components — pick the notion that matches how "reach" is defined for your question.
- **Ego networks** (the k-step neighborhood around a focal node) are the local-structure counterpart to global path analysis: use them when the research question is about an actor's immediate environment (support networks, local density, brokerage opportunities around a person) rather than whole-network structure. Extraction and neighborhood operations are covered in the library skills' paths/components references.

---

## Bipartite / Two-Mode Data

Many relational datasets are **two-mode**: ties connect nodes of two different kinds — people × events, authors × papers, firms × board members, students × courses. These are naturally represented as **bipartite graphs** (edges only ever run between the two node types, never within).

- **Construct as bipartite** rather than forcing into a one-mode graph. Keep the two-mode structure until you have a specific reason to collapse it.
- **Projection loses information.** Projecting a two-mode graph to one mode (e.g., "two authors are tied if they co-wrote a paper") is common but lossy: it discards the events/papers that mediated the ties and **inflates edge counts** (every k-author paper creates a k-clique among its authors, manufacturing dense local structure that is an artifact of a single event, not many independent ties). Downstream centrality on a projected graph can be dominated by a few large events.
- **Interpret projected metrics cautiously.** If you project, weight the projected edges by shared events and be explicit that clustering/density in the projection partly reflects event sizes, not organic dyadic ties. Where possible, run key analyses on the bipartite graph directly (bipartite-aware measures) rather than only on the projection.

---

## Reproducibility Requirements

Network analysis has **two** distinct sources of non-determinism, and both must be pinned for results and figures to reproduce:

1. **Stochastic algorithms** — community detection (Leiden/Louvain) depends on a random seed (see Seed Discipline above). Set and record it.
2. **Force-directed layouts** — network *visualizations* (Fruchterman-Reingold, Kamada-Kawai, DrL, etc.) randomize their initial node placement, so the same graph produces a differently-arranged figure on each run. **Set a layout seed** before generating any figure so the visualization is reproducible. In R, `set.seed()` before the layout call; in Python, `random.seed()`. The deprecated C-level `srand()` no longer controls this — use the language RNG.

Record both seeds in the script (IAT `# ASSUMES:`/`# REASONING:` comments are the right home) and in the report's methods/limitations, exactly as you would record a bootstrap seed.

---

## Out of Current Scope: Statistical Network Models

**ERGM (Exponential Random Graph Models), SAOM/stochastic actor-oriented models, and TERGM (temporal ERGM) are NOT currently covered by any DAAF skill.** These are inferential models of *tie formation* — they ask what dyadic and structural processes (reciprocity, transitivity, homophily) generate an observed network, rather than describing a network taken as given.

They are deferred deliberately, not by oversight: ERGMs carry MCMC estimation cost, model-degeneracy hazards, and network-size limits that make them a distinct methodological undertaking from the descriptive/community/visualization scope of the current skills. If a research question genuinely requires modeling *why ties exist* (as opposed to describing structure, position, or communities), **escalate to the orchestrator** — this is a candidate future extension (statnet's `ergm`/`network`/`sna` stack in R), not something to approximate with the descriptive tools here.

Everything the current `igraph`/`igraph-r` skills cover — construction, centrality, community detection, paths/components, bipartite projection, and static visualization — takes the network as observed and describes it. That descriptive/positional boundary is the line between "in scope" and "escalate."

---

## Routing to Implementation

Once the methodology decisions above are made, load the language-appropriate library skill for syntax, installed-version constraints, and API-level caveats:

- **Python:** `igraph` skill (python-igraph; graph construction from Polars edge lists, centrality, community detection, bipartite, matplotlib rendering).
- **R:** `igraph-r` skill (igraph fronted by tidygraph/ggraph; tidyverse edge-list round-trip, `cluster_leiden`/`cluster_louvain`, ggraph grammar-of-graphics figures).

Both wrap the same igraph C core, so algorithms and coded-value semantics are consistent across the language pair — but the auto-weighting behavior, the undirected-only community constraint, and the seed mechanics described above are exactly the kind of curated caveat the library skills encode and general knowledge misses. Load the routed skill before giving tool-specific advice or writing code, on advisory turns as much as implementation turns.

---

## References and Further Reading

### Software

Csárdi, G. & Nepusz, T. (2006). "The igraph software package for complex network research." *InterJournal, Complex Systems*, 1695. https://igraph.org/

Antonov, M., Csárdi, G., Horvát, S., Müller, K., Nepusz, T., Noom, D., Salmon, M., Traag, V., Foucault Welles, B., & Zanini, F. (2023). "igraph enables fast and robust network analysis across programming languages." *arXiv preprint arXiv:2311.10260*. https://doi.org/10.48550/arXiv.2311.10260

Pedersen, T.L. (2024). *tidygraph: A Tidy API for Graph Manipulation.* R package version 1.3.1. https://CRAN.R-project.org/package=tidygraph

Pedersen, T.L. (2025). *ggraph: An Implementation of Grammar of Graphics for Graphs and Networks.* R package version 2.2.2. https://CRAN.R-project.org/package=ggraph

### Methodological

Traag, V.A., Waltman, L., & van Eck, N.J. (2019). "From Louvain to Leiden: guaranteeing well-connected communities." *Scientific Reports*, 9, 5233. (Leiden algorithm; the well-connected-communities guarantee that motivates preferring Leiden over Louvain.)

Fortunato, S. & Barthélemy, M. (2007). "Resolution limit in community detection." *PNAS*, 104(1), 36-41. (Modularity resolution limit.)

Freeman, L.C. (1978). "Centrality in social networks: Conceptual clarification." *Social Networks*, 1(3), 215-239. (Degree, betweenness, closeness — the canonical centrality taxonomy.)

Borgatti, S.P. & Everett, M.G. (1997). "Network analysis of 2-mode data." *Social Networks*, 19(3), 243-269. (Bipartite/two-mode analysis and the pitfalls of projection.)
