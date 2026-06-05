"""
Knowledge graph data structures for demographic constraint inference.

Design goals
────────────
1. Hand-authored now (Andorra), auto-generated from documents later (GraphRAG ingestion).
2. Country-agnostic structure — building a graph for a new country means providing
   different nodes/edges, not changing any traversal or generation code.
3. Serialisable — nodes and edges are plain dataclasses so the graph can be exported
   to JSON and rebuilt from external sources (census PDFs, policy reports, etc.).

Graph anatomy
─────────────
Nodes  — demographic positions or situational conditions.
         id format: "type:value"  e.g. "nat:Portuguese", "income:precarious", "ctx:housing_crisis"

Edges  — constraints that activate when ALL required nodes are matched for a given agent seed.
         Each edge holds one or more FieldConstraints.

FieldConstraint — a numerical range or directional label for one profile field.
         Multiple constraints on the same field are merged: the most specific
         (smallest range) takes priority; directional labels are concatenated.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class FieldConstraint:
    """
    A constraint on one numerical profile field.

    Range constraints  → inject as "field: low–high" into the HAG prompt.
    Directional labels → inject as "field: direction (note)" when no range is given.
    Both can coexist.
    """
    field: str                     # e.g. "financial_stress", "bonding_capital"
    low:   float | None  = None    # range minimum [0–1] or raw for BE fields
    high:  float | None  = None    # range maximum
    direction: str | None = None   # "high" | "low" | "moderate" (qualitative)
    note: str | None      = None   # appended to constraint string for context
    priority: int         = 0      # higher priority wins when fields conflict


@dataclass
class Node:
    """A position in the demographic or situational space."""
    id:    str   # unique, e.g. "nat:Portuguese"
    type:  str   # "demographic" | "condition" | "context"
    label: str   # human-readable, used in branch path string


@dataclass
class Edge:
    """
    A constraint rule that fires when ALL nodes in `source_ids` are active.

    source_ids may combine demographic and context nodes, enabling rules like:
        ["nat:Portuguese", "years:recent", "ctx:housing_crisis"]
        → financial_stress: 0.75–0.95  (stricter during a housing crisis)
    """
    source_ids:  list[str]            # AND condition — all must be active
    constraints: list[FieldConstraint]
    note: str = ""                    # short label / HAG constraint heading
    narrative: str = ""               # qualitative description for GraphRAG injection


class KnowledgeGraph:
    """
    Container for nodes and edges. Provides lookup helpers for traversal.

    Usage:
        g = KnowledgeGraph()
        g.add_node(Node("nat:Andorran", "demographic", "Andorran national"))
        g.add_edge(Edge(["nat:Andorran"], [FieldConstraint("bonding_capital", 0.60, 0.90)]))
        active = g.active_nodes(seed)
        constraints = g.matching_edges(active)
    """

    def __init__(self):
        self._nodes: dict[str, Node] = {}
        self._edges: list[Edge]      = []

    def add_node(self, node: Node) -> "KnowledgeGraph":
        self._nodes[node.id] = node
        return self

    def add_edge(self, edge: Edge) -> "KnowledgeGraph":
        self._edges.append(edge)
        return self

    def node(self, node_id: str) -> Node | None:
        return self._nodes.get(node_id)

    def active_nodes(self, seed: dict) -> set[str]:
        """
        Map a demographic seed to a set of active node ids.

        The mapping is deterministic and generic — it uses well-known id prefixes
        (nat:, income:, age:, occ:, years:) that any country graph can adopt.
        Context nodes (ctx:) are always active — they represent persistent
        situational facts about the country (housing crisis, etc.).
        """
        active: set[str] = set()

        # Demographic dimensions
        if nat := seed.get("nationality"):
            active.add(f"nat:{nat}")

        if income := seed.get("income_bracket"):
            active.add(f"income:{income}")

        if occ := seed.get("occupation"):
            active.add(f"occ:{occ}")

        age = seed.get("age", 35)
        if age < 27:
            active.add("age:young_adult")
        elif age < 42:
            active.add("age:prime")
        elif age < 58:
            active.add("age:established")
        else:
            active.add("age:pre_retirement")

        years = float(seed.get("years_in_andorra", 0))
        if years < 5:
            active.add("years:recent")
        elif years < 10:
            active.add("years:settling")
        else:
            active.add("years:established")

        # All context nodes are always active
        for node_id, node in self._nodes.items():
            if node.type == "context":
                active.add(node_id)

        return active

    def matching_edges(self, active_nodes: set[str]) -> list[Edge]:
        """Return all edges whose source_ids are fully covered by active_nodes."""
        return [e for e in self._edges if all(s in active_nodes for s in e.source_ids)]

    def path_label(self, active_nodes: set[str]) -> str:
        """
        Build a human-readable branch path from active demographic nodes.
        Ordered: nationality → residence duration → age group → occupation.
        """
        order = ["nat:", "years:", "age:", "occ:", "income:"]
        parts = []
        for prefix in order:
            for nid in active_nodes:
                if nid.startswith(prefix) and nid in self._nodes:
                    parts.append(self._nodes[nid].label)
        return " → ".join(parts) if parts else "unknown"

    def to_dict(self) -> dict:
        """Serialise to plain dict (JSON-compatible) for export / future ingestion."""
        return {
            "nodes": [
                {"id": n.id, "type": n.type, "label": n.label}
                for n in self._nodes.values()
            ],
            "edges": [
                {
                    "source_ids": e.source_ids,
                    "note": e.note,
                    "constraints": [
                        {k: v for k, v in c.__dict__.items() if v is not None}
                        for c in e.constraints
                    ],
                }
                for e in self._edges
            ],
        }
