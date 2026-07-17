# Bipartite Graphs and Projection

Two-mode (bipartite) graphs have two disjoint node sets — e.g., authors and
papers, people and events, firms and directors — with edges only *between* the
sets, never within. This file covers constructing a bipartite graph via the `type`
attribute and projecting it to a one-mode graph for analysis.

---

## The `type` Attribute

In igraph, a bipartite graph is an ordinary graph plus a logical vertex attribute
named **`type`** that assigns each node to one of the two modes (`FALSE` = first
mode, `TRUE` = second mode). Most bipartite functions read this attribute.

```r
library(igraph)
library(tidygraph)

# INTENT: build an author-paper bipartite graph from an incidence edge list
# ASSUMES: edges connect authors (mode FALSE) to papers (mode TRUE) only
edges <- tibble::tibble(
  from = c("Ann", "Ann", "Bea", "Cy",  "Cy"),   # authors
  to   = c("P1",  "P2",  "P1",  "P2",  "P3")     # papers
)

g <- graph_from_data_frame(edges, directed = FALSE)

# Assign the 'type' attribute: TRUE for papers, FALSE for authors
V(g)$type <- V(g)$name %in% edges$to   # papers get TRUE

# Verify it is genuinely bipartite (no within-mode edges)
stopifnot(bipartite_mapping(g)$res)    # $res is TRUE iff a valid bipartition exists
cat("Bipartite:", bipartite_mapping(g)$res,
    " | authors:", sum(!V(g)$type), " papers:", sum(V(g)$type), "\n")
```

> **`bipartite_mapping()` is the validity check.** It returns `$res = TRUE` only if
> the graph can actually be two-colored (no edge within a mode). If it returns
> `FALSE`, your edge list has a within-mode edge — a data error to fix before
> projecting. When `$res` is TRUE and `type` is not already set, `$type` gives a
> valid assignment you can use.

---

## Constructing Directly from an Incidence Structure

If you have an incidence matrix (rows = mode 1, cols = mode 2), build the graph
directly:

```r
# Incidence matrix: authors (rows) x papers (cols), 1 = authored
inc <- matrix(c(1,1,0,
                1,0,0,
                0,1,1),
              nrow = 3, byrow = TRUE,
              dimnames = list(c("Ann","Bea","Cy"), c("P1","P2","P3")))

g <- graph_from_biadjacency_matrix(inc)   # sets V(g)$type automatically
stopifnot(bipartite_mapping(g)$res)
```

> **Function-name note:** recent igraph renamed the old
> `graph_from_incidence_matrix()` to `graph_from_biadjacency_matrix()`. On igraph
> 2.2.3 use `graph_from_biadjacency_matrix()`; the old name may still work with a
> deprecation warning. If you hit an "unknown function" error on an older mental
> model, this rename is the likely cause — verify with `?graph_from_biadjacency_matrix`.

---

## One-Mode Projection

Projection collapses a two-mode graph into a one-mode graph over a single mode,
connecting nodes that share a neighbor in the other mode. Two authors become
connected if they co-authored a paper; the edge weight counts shared papers.

```r
proj <- bipartite_projection(g)

# proj is a list of two graphs, one per mode:
authors_g <- proj$proj1     # mode FALSE (authors), edges = shared papers
papers_g  <- proj$proj2     # mode TRUE  (papers),  edges = shared authors

# The projection sets a 'weight' edge attribute = number of shared neighbors
E(authors_g)$weight
igraph::as_data_frame(authors_g, what = "edges")
```

> **The projection creates a `weight` attribute — remember the auto-use trap.** The
> projected `weight` counts shared neighbors and is a **strength** (higher = more
> co-occurrence), *not* a distance. If you then run betweenness/closeness on the
> projection, the auto-used `weight` will be misinterpreted as distance (higher =
> farther), inverting the meaning. For strength-semantic weights, either pass
> `weights = NA` (topology-only centrality) or convert to a distance
> (`E(g)$dist <- 1 / E(g)$weight`) and pass that explicitly. See `centrality.md`.

---

## Choosing Which Mode to Project

Projection loses information — pick the mode that answers your question:

| Question | Project onto | Edge meaning |
|----------|-------------|--------------|
| How do authors collaborate? | authors (`proj1`) | shared papers |
| How are papers related by shared authorship? | papers (`proj2`) | shared authors |

Projection also tends to create **dense** graphs (every pair sharing any neighbor
becomes connected), which can distort centrality and inflate community counts.
Consider thresholding weak edges before downstream analysis, and document the
threshold:

```r
# INTENT: drop co-authorship edges backed by only a single shared paper
# REASONING: single-paper links add noise/density to the projection
authors_strong <- authors_g |>
  as_tbl_graph() |>
  activate(edges) |>
  dplyr::filter(weight >= 2)
```

---

## End-to-End Pattern

```r
# --- Config ---
library(igraph)
library(tidygraph)

# --- Load / construct ---
edges <- tibble::tibble(from = c("Ann","Ann","Bea","Cy","Cy"),
                        to   = c("P1","P2","P1","P2","P3"))
g <- graph_from_data_frame(edges, directed = FALSE)
V(g)$type <- V(g)$name %in% edges$to

# --- Validate bipartition ---
stopifnot(bipartite_mapping(g)$res)

# --- Project onto authors ---
authors_g <- bipartite_projection(g)$proj1

# --- Analyze (weight is a STRENGTH — use weights = NA for topology centrality) ---
V(authors_g)$degree <- degree(authors_g)
node_tbl <- authors_g |> as_tbl_graph() |> activate(nodes) |> as_tibble()

# --- Summary ---
cat("Author graph:", gorder(authors_g), "authors,", gsize(authors_g), "co-author edges\n")
print(node_tbl)
```
