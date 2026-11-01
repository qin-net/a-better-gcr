import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "path_audit", Path(__file__).resolve().parents[1] / "src" / "path_audit.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
audit_prediction = module.audit_prediction

GRAPH = [("Alice", "born_in", "City"), ("City", "country", "Country")]


def check(path, starts=("Alice",), hops=2):
    return audit_prediction(f"# Reasoning Path:\n{path}\n# Answer:\nCountry",
                            GRAPH, starts, hops)


def test_checks_every_edge_and_direction():
    assert check("Alice -> born_in -> City -> country -> Country")["valid"]
    assert not check("Alice -> born_in -> City -> country -> Elsewhere")["valid"]
    assert not check("City -> born_in -> Alice", starts=("City",))["valid"]


def test_requires_start_depth_and_well_formed_output():
    assert check("City -> country -> Country")["reason"] == "wrong_start"
    assert check("Alice -> born_in -> City -> country -> Country", hops=1)["reason"] == "exceeds_hop_limit"
    assert check("Alice -> born_in")["reason"] == "malformed_path"
    assert not audit_prediction("Country", GRAPH, ["Alice"], 2)["valid"]


def test_accepts_path_markers():
    assert check("<PATH>Alice -> born_in -> City</PATH>")["valid"]
