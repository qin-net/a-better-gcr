import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "multi_relation_graph", Path(__file__).resolve().parents[1] / "src" / "multi_relation_graph.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# Two relations between Actor and Cvt; the official graph keeps only one of them.
GRAPH = [("Actor", "film.actor.film", "Cvt"), ("Cvt", "film.performance.actor", "Actor"),
         ("Cvt", "film.performance.film", "Movie")]


def test_keeps_every_relation_and_reverse_steps():
    adj = module.build_graph(GRAPH, reverse=True)
    assert adj["Actor"]["Cvt"] == {"film.actor.film", "film.performance.actor"}
    assert adj["Movie"]["Cvt"] == {"film.performance.film"}
    assert "Movie" not in module.build_graph(GRAPH, reverse=False)


def test_dfs_enumerates_each_relation_up_to_max_length():
    paths = module.dfs(module.build_graph(GRAPH, reverse=False), ["Actor"], 2)
    # Walks may revisit nodes, as in the official dfs: Actor -> Cvt -> Actor.
    assert sorted(len(p) for p in paths) == [1, 2, 2]
    reverse_paths = module.dfs(module.build_graph(GRAPH), ["Actor"], 1)
    assert {p[0][1] for p in reverse_paths} == {"film.actor.film", "film.performance.actor"}


def test_truth_paths_expand_relation_combinations():
    paths = module.get_truth_paths(["Actor"], ["Movie"], module.build_graph(GRAPH))
    assert sorted(p[0][1] for p in paths) == ["film.actor.film", "film.performance.actor"]
    assert all(p[-1] == ("Cvt", "film.performance.film", "Movie") for p in paths)
    assert module.get_truth_paths(["Actor"], ["Actor"], module.build_graph(GRAPH)) == []
