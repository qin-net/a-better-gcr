"""Multi-relation graph: keep every triple, optionally traversable in reverse.

The official `build_graph` stores one relation per entity pair (networkx
`add_edge` overwrites), silently dropping 7% of WebQSP test triples in the
directed graph and 30% in the undirected one. Here `adj[u][v]` is the set of
all relations usable from u to v; with `reverse=True`, a triple (h, r, t)
also lets the path go t -> r -> h, printed in traversal order like the
official undirected graph.

`install(reverse)` swaps these in for `src.utils.build_graph`, `dfs` and
`get_truth_paths`, which is all the prompt builder uses to build the trie
and the reference paths. No networkx, so it also runs on the CPU-only lab.
"""
import collections
import itertools


def build_graph(graph, reverse=True):
    adj = collections.defaultdict(lambda: collections.defaultdict(set))
    for h, r, t in graph:
        h, r, t = h.strip(), r.strip(), t.strip()
        adj[h][t].add(r)
        if reverse:
            adj[t][h].add(r)
    return adj


def _expand(adj, node_path):
    hops = [sorted(adj[u][v]) for u, v in zip(node_path, node_path[1:])]
    for rels in itertools.product(*hops):
        yield [(u, r, v) for (u, v), r in zip(zip(node_path, node_path[1:]), rels)]


def dfs(adj, start_node_list, max_length):
    """All walks of 1..max_length steps, one per relation choice (official contract)."""
    paths = set()

    def visit(node, path):
        if len(path) == max_length:
            return
        for nbr, rels in adj.get(node, {}).items():
            for r in rels:
                new_path = path + [(node, r, nbr)]
                paths.add(tuple(new_path))
                visit(nbr, new_path)

    for s in start_node_list:
        visit(s.strip(), [])
    return list(paths)


def get_truth_paths(q_entity, a_entity, adj):
    """All shortest q -> a paths per (q, a) pair, every relation combination."""
    result = []
    for h in q_entity:
        if h not in adj:
            continue
        dist, parents, frontier = {h: 0}, collections.defaultdict(list), [h]
        while frontier:
            nxt = []
            for u in frontier:
                for v in adj.get(u, {}):
                    if v not in dist:
                        dist[v] = dist[u] + 1
                        nxt.append(v)
                    if dist[v] == dist[u] + 1:
                        parents[v].append(u)
            frontier = nxt
        for t in a_entity:
            if t not in dist or t == h:
                continue

            def back(v, suffix):
                if v == h:
                    yield [h] + suffix
                    return
                for u in parents[v]:
                    yield from back(u, [v] + suffix)

            for node_path in back(t, []):
                result.extend(_expand(adj, node_path))
    return result


def install(reverse=True):
    import src.utils as utils
    utils.build_graph = lambda graph, undirected=False: build_graph(graph, reverse)
    utils.dfs = dfs
    utils.get_truth_paths = get_truth_paths
