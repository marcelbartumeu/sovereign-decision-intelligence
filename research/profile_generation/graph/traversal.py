"""
Graph traversal: converts a demographic seed into a HAG-compatible constraint string.

This is the drop-in replacement for the hand-coded _branch() function in exp02_hag.py.
The output format is identical — a branch path + numbered constraint list — so the
LLM prompt is unchanged. Only the derivation mechanism changes.

Merging rules when multiple edges constrain the same field
──────────────────────────────────────────────────────────
Range constraints  → intersection (max of lows, min of highs); higher priority wins ties.
Directional labels → concatenate unique values.
Notes              → concatenate unique values.
"""

from __future__ import annotations
from .knowledge_graph import KnowledgeGraph, FieldConstraint


def get_narratives(graph: KnowledgeGraph, seed: dict) -> str:
    """
    Traverse the graph for a demographic seed and return a narrative context string
    for GraphRAG injection. Concatenates non-empty narratives from all matching edges,
    ordered from broadest (single-node) to most specific (multi-node).
    """
    active = graph.active_nodes(seed)
    edges  = graph.matching_edges(active)
    path   = graph.path_label(active)

    # Sort by specificity: fewer source_ids = broader context, inject first
    edges_sorted = sorted(edges, key=lambda e: len(e.source_ids))

    snippets = [e.narrative.strip() for e in edges_sorted if e.narrative.strip()]
    body = "\n\n".join(snippets)

    return (
        f"Demographic profile: {path}\n\n"
        f"Relevant sociological context:\n{body}"
    )


def get_constraints(graph: KnowledgeGraph, seed: dict) -> str:
    """
    Traverse the graph for a demographic seed and return a HAG constraint string.

    Output format:
        Demographic branch: <path>
        Sociological constraints:
          - field: low–high  (note)
          - field: direction  (note)
          ...
    """
    active  = graph.active_nodes(seed)
    edges   = graph.matching_edges(active)
    path    = graph.path_label(active)

    merged  = _merge_constraints([c for e in edges for c in e.constraints])
    lines   = _format_constraints(merged)

    constraint_str = "\n".join(f"  - {line}" for line in lines)
    return f"Demographic branch: {path}\nSociological constraints:\n{constraint_str}"


# ── Merging ───────────────────────────────────────────────────────────────────

def _merge_constraints(constraints: list[FieldConstraint]) -> dict[str, FieldConstraint]:
    """Merge all constraints for the same field into one."""
    merged: dict[str, FieldConstraint] = {}

    for c in constraints:
        if c.field not in merged:
            merged[c.field] = FieldConstraint(
                field=c.field, low=c.low, high=c.high,
                direction=c.direction, note=c.note, priority=c.priority,
            )
            continue

        m = merged[c.field]

        # Range: take intersection; higher priority wins on conflict
        if c.low is not None and m.low is not None:
            if c.priority >= m.priority:
                m.low  = max(m.low,  c.low)
                m.high = min(m.high, c.high) if m.high is not None else c.high
        elif c.low is not None:
            m.low, m.high = c.low, c.high

        # Direction: accumulate unique labels
        if c.direction and c.direction not in (m.direction or ""):
            m.direction = f"{m.direction}/{c.direction}" if m.direction else c.direction

        # Notes: accumulate unique notes
        if c.note and c.note not in (m.note or ""):
            m.note = f"{m.note}; {c.note}" if m.note else c.note

        # Priority: track highest seen
        m.priority = max(m.priority, c.priority)

    return merged


# ── Formatting ────────────────────────────────────────────────────────────────

def _format_constraints(merged: dict[str, FieldConstraint]) -> list[str]:
    lines = []
    for field, c in merged.items():
        parts = [field + ":"]

        if c.low is not None and c.high is not None:
            parts.append(f"{c.low:.2f}–{c.high:.2f}")
        elif c.direction:
            parts.append(c.direction)

        if c.note:
            parts.append(f"— {c.note}")

        lines.append(" ".join(parts))
    return lines
