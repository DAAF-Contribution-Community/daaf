# smoke_igraph_r.R -- Smoke test for igraph, tidygraph, ggraph (igraph-r skill)
# Validates: tbl_graph construction, centrality with weights = NA, seeded
#            community detection (Louvain + Leiden) on an undirected graph,
#            directed -> undirected conversion, bipartite projection, and a
#            seeded ggraph layout build (plot object only, not rendered to file).
# All tests use synthetic data (no external files needed).
#
# NOT YET EXECUTED: tidygraph 1.3.1 and ggraph 2.2.2 are added to the Dockerfile
# framework R block but are NOT loadable until the container is rebuilt. Run this
# test after `bash rebuild_daaf.sh` from the daaf-docker folder. igraph 2.2.3 is
# already installed; the tidygraph/ggraph-dependent tests require the rebuild.

# --- Config ---
library(igraph)
library(tidygraph)
library(ggraph)
library(ggplot2)

SEED <- 20260715

cat("=== igraph-r Smoke Test ===\n\n")

# --- Test 1: Version checks ---
cat("Test 1: Version checks\n")
igraph_ver <- as.character(packageVersion("igraph"))
tidygraph_ver <- as.character(packageVersion("tidygraph"))
ggraph_ver <- as.character(packageVersion("ggraph"))

cat("  igraph:", igraph_ver, "\n")
cat("  tidygraph:", tidygraph_ver, "\n")
cat("  ggraph:", ggraph_ver, "\n")

stopifnot(igraph_ver == "2.2.3")
stopifnot(tidygraph_ver == "1.3.1")
stopifnot(ggraph_ver == "2.2.2")
cat("  PASS: All versions match skill metadata\n\n")

# --- Test 2: tbl_graph construction from an edge-list tibble ---
cat("Test 2: tbl_graph construction from edge-list tibble\n")
edges <- tibble::tibble(
  from = c("A", "A", "B", "C", "C", "D", "E", "F"),
  to   = c("B", "C", "C", "D", "E", "E", "F", "G")
)
g <- as_tbl_graph(edges, directed = FALSE)
stopifnot(inherits(g, "tbl_graph"))
stopifnot(gorder(g) == 7)              # A-G
stopifnot(gsize(g) == 8)
stopifnot(!is_directed(g))
# No 'weight' attribute should exist on a bare edge-list construction
stopifnot(!("weight" %in% edge_attr_names(g)))
cat("  Nodes:", gorder(g), " Edges:", gsize(g), " (unweighted, undirected)\n")
cat("  PASS\n\n")

# --- Test 3: Round-trip graph -> tidy tables -> graph ---
cat("Test 3: tidyverse round-trip (activate/as_tibble)\n")
node_tbl <- g |> activate(nodes) |> as_tibble()
edge_tbl <- igraph::as_data_frame(g, what = "edges")   # name-based endpoints
stopifnot(nrow(node_tbl) == gorder(g))
stopifnot(nrow(edge_tbl) == gsize(g))
g2 <- tbl_graph(nodes = node_tbl, edges = edge_tbl, directed = FALSE, node_key = "name")
stopifnot(gorder(g2) == gorder(g))
stopifnot(gsize(g2) == gsize(g))
cat("  Round-trip preserved", gorder(g2), "nodes,", gsize(g2), "edges\n")
cat("  PASS\n\n")

# --- Test 4: Centrality with weights = NA (unweighted discipline) ---
cat("Test 4: Centrality with weights = NA\n")
deg <- degree(g, mode = "all")
stopifnot(sum(deg) == 2 * gsize(g))    # handshake lemma
btw <- betweenness(g, weights = NA)    # weights = NA suppresses auto-use
stopifnot(length(btw) == gorder(g))
stopifnot(all(btw >= 0))
pr <- page_rank(g)$vector
stopifnot(abs(sum(pr) - 1) < 1e-8)     # PageRank scores form a distribution
cat("  Max degree:", max(deg), " Max betweenness:", round(max(btw), 2), "\n")
cat("  PASS\n\n")

# --- Test 5: Component check + closeness on the giant component ---
cat("Test 5: Component-aware closeness\n")
comp <- components(g)
stopifnot(comp$no == 1)                # this synthetic graph is connected
stopifnot(is_connected(g))
cc <- closeness(g, weights = NA)       # safe: single component
stopifnot(length(cc) == gorder(g))
cat("  Components:", comp$no, " (connected -> closeness well-defined)\n")
cat("  PASS\n\n")

# --- Test 6: Seeded Louvain community detection (undirected) ---
cat("Test 6: Seeded Louvain community detection\n")
set.seed(SEED)                         # stochastic -> seed for reproducibility
comm_louvain <- cluster_louvain(g, weights = NA)
stopifnot(inherits(comm_louvain, "communities"))
stopifnot(length(membership(comm_louvain)) == gorder(g))
mod_louvain <- modularity(comm_louvain)
# Reproducibility: same seed -> identical membership
set.seed(SEED)
comm_louvain2 <- cluster_louvain(g, weights = NA)
stopifnot(all(membership(comm_louvain) == membership(comm_louvain2)))
cat("  Louvain communities:", length(comm_louvain),
    " Modularity:", round(mod_louvain, 3), " (reproducible under seed)\n")
cat("  PASS\n\n")

# --- Test 7: Seeded Leiden community detection (undirected, modularity objective) ---
cat("Test 7: Seeded Leiden community detection\n")
set.seed(SEED)
comm_leiden <- cluster_leiden(g, objective_function = "modularity", weights = NA)
stopifnot(inherits(comm_leiden, "communities"))
stopifnot(length(membership(comm_leiden)) == gorder(g))
cat("  Leiden communities:", length(comm_leiden), "\n")
cat("  PASS\n\n")

# --- Test 8: Directed graph -> as_undirected() conversion ---
cat("Test 8: Directed -> undirected conversion for community detection\n")
dg <- as_tbl_graph(
  tibble::tibble(from = c("A","B","C","A","D"), to = c("B","C","A","C","A")),
  directed = TRUE
)
stopifnot(is_directed(dg))
dg_undir <- as_undirected(dg, mode = "collapse")   # collapse reciprocal edges
stopifnot(!is_directed(dg_undir))
set.seed(SEED)
comm_dg <- cluster_louvain(dg_undir, weights = NA)  # now valid (undirected)
stopifnot(inherits(comm_dg, "communities"))
cat("  Directed graph collapsed to undirected;",
    length(comm_dg), "communities found\n")
cat("  PASS\n\n")

# --- Test 9: Bipartite construction + one-mode projection ---
cat("Test 9: Bipartite construction + projection\n")
bp_edges <- tibble::tibble(
  from = c("Ann", "Ann", "Bea", "Cy", "Cy"),   # authors
  to   = c("P1",  "P2",  "P1",  "P2", "P3")     # papers
)
bg <- graph_from_data_frame(bp_edges, directed = FALSE)
V(bg)$type <- V(bg)$name %in% bp_edges$to        # papers -> TRUE
stopifnot(bipartite_mapping(bg)$res)             # valid bipartition
proj <- bipartite_projection(bg)
authors_g <- proj$proj1
stopifnot(gorder(authors_g) == 3)                # Ann, Bea, Cy
stopifnot("weight" %in% edge_attr_names(authors_g))  # projection creates weights
cat("  Bipartition valid; author projection:", gorder(authors_g), "authors,",
    gsize(authors_g), "co-author edges\n")
cat("  PASS\n\n")

# --- Test 10: Seeded ggraph layout build (object only, not rendered) ---
cat("Test 10: Seeded ggraph plot object build\n")
set.seed(SEED)                         # seed the stochastic FR layout
g <- g |> activate(nodes) |> mutate(community = as.factor(membership(comm_louvain)))
set.seed(SEED)
p <- ggraph(g, layout = "fr") +
  geom_edge_link(alpha = 0.3, color = "grey60") +
  geom_node_point(aes(color = community), size = 3) +
  theme_void()
# Build the plot object; do NOT render to file
stopifnot(inherits(p, "ggplot"))       # ggraph objects inherit from ggplot
built <- ggplot_build(p)               # forces layout computation without writing a file
stopifnot(inherits(built, "ggplot_built"))
cat("  ggraph object built and layout computed (not rendered)\n")
cat("  PASS\n\n")

# --- Summary ---
cat("=== All 10 tests PASSED ===\n")
cat("Tested: igraph", igraph_ver, "/ tidygraph", tidygraph_ver,
    "/ ggraph", ggraph_ver, "\n")
cat("Seed used for all stochastic steps:", SEED, "\n")
