"""
Workflow 11: Parallel Fan-out
─────────────────────────────
                    ┌─▶ tax      ─┐
A2A_START ─▶ FORK ──┼─▶ shipping ─┼─▶ MERGE ─▶ TRANSFORM ─▶ END
                    ├─▶ discount ─┤            totals it up
                    └─▶ audit    ─┘

Four branches, not the usual two. A PARALLEL_FORK has one right-hand handle per
entry in its `branches` list and a spare below them, so on the canvas you drag
out a branch, another handle appears, and you keep going — the list grows to
match the wiring rather than being declared up front.

The branch names are labels, not routing values. ADK fans out along every plain
outgoing edge by itself, so the fork's generated module returns a plain event
and never `Event(route=...)`; the names exist so the canvas can tell one handle
from another and so an edge knows which handle it left from. For the same
reason a fork has no "save result as" box: it hands each branch the payload it
was given, unchanged, so there is nothing of its own to name.

Every branch must reach the MERGE. A fork whose branches each end somewhere
different produces several terminal outputs and ADK rejects the run, so the
compiler refuses it up front.

Try it:

    python run_once.py '{"amount": 200}'

Runs entirely offline: no model, no MCP server, no credentials.
"""
import sys

import httpx

BASE = "http://localhost:8001/api/v1"

BRANCHES = [
    # (branch/handle name, node title, what it computes)
    ("tax",      "Tax",      "result = {'tax': round((data.get('amount') or 0) * 0.2, 2)}"),
    ("shipping", "Shipping", "result = {'shipping': 5 if (data.get('amount') or 0) < 100 else 0}"),
    ("discount", "Discount", "result = {'discount': 10 if (data.get('amount') or 0) >= 150 else 0}"),
    ("audit",    "Audit",    "result = {'audited': True}"),
]


def _node(node_id, node_type, title, config, x, y):
    return {
        "id": node_id,
        "type": node_type,
        "version": "1",
        "position": {"x": x, "y": y},
        "metadata": {"title": title, "description": ""},
        "config": config,
        "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
        "policies": {"timeout_seconds": 60, "retry": {"max_attempts": 1}, "on_error": "fail"},
    }


def _edge(edge_id, source, target, source_handle="output"):
    return {
        "id": edge_id,
        "source": source,
        "source_handle": source_handle,
        "target": target,
        "target_handle": "input",
        "condition": None,
    }


CANVAS = {
    "schema_version": 7,
    "nodes": [
        _node("trigger", "A2A_START", "Order", {
            "input_mode": "json",
            "state_key": "wf",
            "output_variable": "order",
            "payload_schema": {"fields": [
                {"name": "amount", "type": "number", "description": "Order total",
                 "required": True},
            ]},
        }, 40, 300),

        # One handle per name, in this order, top to bottom on the node.
        _node("fork", "PARALLEL_FORK", "Fan Out",
              {"branches": [name for name, _, _ in BRANCHES]}, 420, 300),

        *[
            _node(name, "TRANSFORM", title, {"mode": "python", "expression": expr},
                  800, 120 + index * 140)
            for index, (name, title, expr) in enumerate(BRANCHES)
        ],

        _node("join", "MERGE", "Join", {
            "merge_mode": "merge",
        }, 1180, 300),

        _node("total", "TRANSFORM", "Grand Total", {
            "mode": "python",
            "output_variable": "totals",
            "expression": (
                "result = {'total': round("
                "(vars['order']['amount'] or 0) "
                "+ (data.get('tax') or 0) "
                "+ (data.get('shipping') or 0) "
                "- (data.get('discount') or 0), 2)}"
            ),
        }, 1560, 300),

        _node("done", "END", "Done", {"output_mapping": {}}, 1940, 300),
    ],
    "edges": [
        _edge("e_in", "trigger", "fork"),
        # The handle each edge leaves from is the branch name.
        *[_edge(f"e_out_{name}", "fork", name, name) for name, _, _ in BRANCHES],
        *[_edge(f"e_join_{name}", name, "join") for name, _, _ in BRANCHES],
        _edge("e_total", "join", "total"),
        _edge("e_done", "total", "done"),
    ],
}


def seed():
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{BASE}/workflows", json={
            "name": "Parallel Fan-out",
            "description": (
                "One fork, four branches running at once, rejoined at a merge "
                "and totalled up."
            ),
        })
        r.raise_for_status()
        workflow_id = r.json()["id"]
        print(f"Created workflow: {workflow_id}")

        r = client.post(f"{BASE}/workflows/{workflow_id}/versions", json={"canvas": CANVAS})
        r.raise_for_status()
        result = r.json()
        if result["is_valid"]:
            print(f"✓ Compiled successfully — version {result['version_id']}")
        else:
            print(f"✗ Validation errors: {result['errors']}", file=sys.stderr)
        for warning in result.get("warnings") or []:
            print(f"  ! {warning}")
        return workflow_id


if __name__ == "__main__":
    seed()
