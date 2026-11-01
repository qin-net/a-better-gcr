"""Audit decoded paths against original triples, independently of answer labels."""
import re


def audit_prediction(text, graph, starts, hops):
    match = re.search(r"# Reasoning Path:\s*(.*?)\s*# Answer:", text, re.DOTALL)
    if match is None:
        return {"valid": False, "reason": "missing_path_or_answer_section"}
    path = match.group(1).replace("<PATH>", "").replace("</PATH>", "").strip()
    parts = [part.strip() for part in path.split(" -> ")]
    if len(parts) < 3 or len(parts) % 2 != 1:
        return {"valid": False, "reason": "malformed_path", "path": path}
    if parts[0] not in {s.strip() for s in starts}:
        return {"valid": False, "reason": "wrong_start", "path": path}
    if (len(parts) - 1) // 2 > hops:
        return {"valid": False, "reason": "exceeds_hop_limit", "path": path}
    edges = {tuple(x.strip() for x in edge) for edge in graph}
    triples = [tuple(parts[i:i + 3]) for i in range(0, len(parts) - 2, 2)]
    missing = [edge for edge in triples if edge not in edges]
    return {"valid": not missing, "reason": "missing_edge" if missing else "grounded",
            "path": path, "missing_edges": missing, "endpoint": parts[-1]}
