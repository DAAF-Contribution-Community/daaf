# Paths and Components

Shortest paths, distances, diameter, connected components, and reachability. This
is also the home of the **connectivity check** that centrality analysis depends on
— run it before betweenness/closeness (see `centrality.md`).

---

## Connected Components

A component is a maximal set of mutually reachable nodes. Checking components is
the first diagnostic on any graph, because disconnection silently breaks
distance-based centrality and inflates diameter.

```r
library(igraph)

comp <- components(g)                 # for directed graphs see 'mode' below
comp$no                               # number of components
comp$csize                            # size of each component
comp$membership                       # component id per node

is_connected(g)                       # TRUE iff a single component

cat("Components:", comp$no, " Sizes:", paste(comp$csize, collapse = ", "), "\n")
```

**Directed graphs** distinguish strong vs weak connectivity:

```r
components(g, mode = "weak")     # ignore direction (default for directed too)
components(g, mode = "strong")   # every pair mutually reachable respecting direction
```

- **Weak**: connected if you ignore edge direction.
- **Strong**: connected only if every node can reach every other *following* edge
  directions. Strong components are usually smaller and are the right notion when
  direction encodes real flow (citations, hyperlinks, dependencies).

---

## Extracting the Giant Component

Most real graphs have one large ("giant") component plus small fragments.
Analyzing the giant component is a common, defensible scoping choice — document it.

```r
# INTENT: restrict distance analysis to the giant component
# REASONING: closeness/diameter are undefined across disconnected pieces
comp <- components(g)
giant_id <- which.max(comp$csize)
g_giant <- induced_subgraph(g, which(comp$membership == giant_id))

stopifnot(is_connected(g_giant))
cat("Giant component:", gorder(g_giant), "of", gorder(g), "nodes",
    sprintf("(%.1f%%)\n", 100 * gorder(g_giant) / gorder(g)))
```

---

## Shortest Paths

```r
# The path itself (sequence of vertices) from one source to targets
sp <- shortest_paths(g, from = "A", to = "E", weights = NA)
sp$vpath[[1]]                        # vertex sequence of the path

# Path length only (number of hops, or summed weights if weighted)
distances(g, v = "A", to = "E", weights = NA)

# All-pairs distance matrix (weights = NA for hop counts)
D <- distances(g, weights = NA)
dim(D)                               # gorder(g) x gorder(g)
```

> **Weight semantics apply here too.** `shortest_paths()` / `distances()`
> auto-consume a `weight` attribute as **edge length (distance)**. Pass
> `weights = NA` for unweighted hop-count paths; pass an explicit distance-valued
> weight vector for weighted shortest paths. This is the one place where the
> distance interpretation of `weight` is the *natural* one.

Unreachable pairs return `Inf` in the distance matrix — a direct signal of
disconnection:

```r
D <- distances(g, weights = NA)
n_unreachable <- sum(is.infinite(D)) / 2   # symmetric for undirected
cat("Unreachable node pairs:", n_unreachable, "\n")
```

---

## Diameter and Average Path Length

```r
# Diameter: the longest shortest path. On a disconnected graph this is
# computed within components by default (unconnected = TRUE) — otherwise Inf.
diameter(g, weights = NA, unconnected = TRUE)

# Mean shortest-path length (over reachable pairs)
mean_distance(g, weights = NA)

# The actual diameter path (endpoints and route)
get_diameter(g, weights = NA)
```

> **Diameter on disconnected graphs:** with `unconnected = TRUE` (the default),
> `diameter()` reports the largest diameter *among* components, silently ignoring
> the disconnection. If you intend a whole-graph diameter, first confirm
> connectivity — otherwise the number describes only the largest component. State
> which you mean.

---

## Reachability and Neighborhoods

```r
# Nodes reachable from A (its component, or forward-reachable set if directed)
subcomponent(g, "A", mode = "out")   # "out" follows direction; "all" ignores it

# k-hop neighborhood around a node
ego(g, order = 2, nodes = "A", mode = "all")    # nodes within 2 hops of A

# Neighborhood sizes for all nodes
ego_size(g, order = 1, mode = "all")            # = degree + 1 for order 1
```

---

## Component-Aware Analysis Pattern

```r
# --- Config ---
library(igraph)

# --- Validate connectivity BEFORE distance work ---
comp <- components(g)
if (comp$no > 1) {
  cat("Graph is disconnected:", comp$no, "components. Restricting to giant.\n")
  giant_id <- which.max(comp$csize)
  g <- induced_subgraph(g, which(comp$membership == giant_id))
}
stopifnot(is_connected(g))

# --- Now distance-based measures are well-defined ---
cat("Diameter:", diameter(g, weights = NA), "\n")
cat("Mean distance:", round(mean_distance(g, weights = NA), 3), "\n")
```

This connectivity-first pattern is the safe default any time closeness,
betweenness, diameter, or mean distance is on the table.
