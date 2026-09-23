"""
Workflow 9: Variables
─────────────────────
A2A_START ─▶ TRANSFORM ─▶ TRANSFORM ─▶ CONDITION ─▶ TRANSFORM ─▶ END
 saves        saves        reads both    branches on
 `order`      `priced`     by name       a variable

Each node can name its result. Later nodes read it as `vars['<name>']`, whether
or not it is still on the edge — which is the point: the `label` node uses the
*entry* payload even though its edge only carries the pricing step's output.

How variables work, and why they look like this: ADK graphs have no separate
variable concept. Variables are session-state keys, and a node's parameters are
bound from state by name — a node returning `Event(state={"customer": "ACME"})`
makes a later node's `customer` parameter arrive as `"ACME"`. So a canvas
variable is a flat, top-level state key, the same place an agent's `output_key`
writes. Names are validated against that shared namespace: `wf`, `_loop_*` and
ADK's `app:` / `user:` / `temp:` are reserved.

Try it:

    python run_once.py '{"sku": "WIDGET", "qty": 2}'   -> tier "standard"
    python run_once.py '{"sku": "WIDGET", "qty": 8}'   -> tier "bulk"

Runs entirely offline: no model, no MCP server, no credentials.
"""
import sys

import httpx

BASE = "http://localhost:8001/api/v1"
UNIT_PRICE = 25
BULK_AT = 100


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
    # No schema_version: the backend stamps the current one, so a seed
    # cannot be stranded on an old version by a later migration.
    "nodes": [
        _node("trigger", "A2A_START", "Order", {
            "input_mode": "json",
            "state_key": "wf",
            # Name the entry payload so any later node can reach it.
            "output_variable": "order",
            "payload_schema": {"fields": [
                {"name": "sku", "type": "string", "description": "What was ordered",
                 "required": True},
                {"name": "qty", "type": "integer", "description": "How many",
                 "required": True},
            ]},
        }, 40, 240),

        _node("price", "TRANSFORM", "Price It", {
            "mode": "python",
            "output_variable": "priced",
            "expression": f"result = {{'total': (data.get('qty') or 0) * {UNIT_PRICE}}}",
        }, 480, 240),

        _node("label", "TRANSFORM", "Describe It", {
            "mode": "python",
            # Reads the entry payload two nodes back, by name — the edge only
            # carries the pricing step's output.
            "expression": (
                "result = {'label': vars['order']['sku'] + ' x' "
                "+ str(vars['order']['qty']) + ' = ' + str(vars['priced']['total'])}"
            ),
        }, 920, 240),

        _node("tier", "CONDITION", "Bulk?", {
            "branches": [
                {"name": "bulk", "expression": f"vars['priced']['total'] >= {BULK_AT}"},
                {"name": "standard", "expression": "True"},
            ],
        }, 1360, 240),

        _node("bulk", "TRANSFORM", "Bulk Tier", {
            "mode": "python",
            "expression": "result = {'tier': 'bulk', 'discount': 0.1}",
        }, 1800, 120),
        _node("standard", "TRANSFORM", "Standard Tier", {
            "mode": "python",
            "expression": "result = {'tier': 'standard', 'discount': 0}",
        }, 1800, 380),

        _node("end", "END", "End", {"output_mapping": {}}, 2240, 240),
    ],
    "edges": [
        _edge("e1", "trigger", "price"),
        _edge("e2", "price", "label"),
        _edge("e3", "label", "tier"),
        _edge("e4", "tier", "bulk", "bulk"),
        _edge("e5", "tier", "standard", "standard"),
        _edge("e6", "bulk", "end"),
        _edge("e7", "standard", "end"),
    ],
}


def seed():
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{BASE}/workflows", json={
            "name": "Variables",
            "description": (
                "Nodes name their results; later nodes read them by name, "
                "including across edges that no longer carry them."
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
