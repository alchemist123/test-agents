"""
Workflow 12: MCP Tool Call
──────────────────────────
A2A_START ─▶ TRANSFORM ─▶ MCP_TOOL ─▶ TRANSFORM ─▶ END
  order       normalise    price_quote  invoice line

An MCP_TOOL node calls one named tool on one MCP server, every time the flow
reaches it. No agent, no model deciding — it is an ordinary step, and the
tool's result is merged into the payload for the next node.

That is the difference from the older TOOL node, which is a tool *provider*:
wired into an agent's tools handle so a model may choose to call it. Both are
useful; they are not the same thing, and this one is what you want when the
workflow already knows which tool it needs.

The arguments are mapped field by field from what is available upstream, not
dumped in wholesale. A payload accumulates keys from every earlier node, and an
MCP server that validates its input schema strictly rejects the ones its tool
never declared. In the config panel you press **Fetch tools**, the server is
asked what it has, and picking a tool fills in one row per parameter — right
names, right types, required ones marked — each with the same source dropdown a
TRANSFORM uses.

Running this one needs an MCP server. The repo ships a small one:

    python backend/tests/support/demo_mcp_server.py 8000 0.0.0.0

Then:

    python run_once.py '{"item": "widget", "count": 3}'
    → sku WIDGET, quantity 3, total 75.0, currency GBP
"""
import sys

import httpx

BASE = "http://localhost:8001/api/v1"
# host.docker.internal, because the platform runs in a container and packages
# the workflow there too — `localhost` inside that container is the backend
# itself, which answers 404 and reads as "not an MCP server". Outside Docker
# use localhost. Either way the URL is an environment variable in the package,
# so a deployment changes it in `.env` rather than re-packaging.
MCP_URL = "http://host.docker.internal:8000/mcp"

# What the demo server reports for price_quote. The config panel caches this
# when you press Fetch tools; it is written out here so the seed compiles with
# the same checking a hand-built node would get.
QUOTE_SCHEMA = {
    "type": "object",
    "properties": {
        "sku": {"type": "string"},
        "quantity": {"type": "integer"},
        "currency": {"type": "string"},
    },
    "required": ["sku", "quantity"],
}


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
                {"name": "item", "type": "string", "description": "What was ordered",
                 "required": True},
                {"name": "count", "type": "integer", "description": "How many",
                 "required": True},
            ]},
        }, 40, 240),

        _node("normalise", "TRANSFORM", "Normalise", {
            "mode": "fields",
            "output_variable": "normalised",
            "output_fields": [
                {"name": "code", "type": "string", "source": "data.item",
                 "required": True},
                {"name": "units", "type": "integer", "source": "data.count",
                 "required": True},
            ],
        }, 420, 240),

        _node("quote", "MCP_TOOL", "Price Quote", {
            "mcp_url": MCP_URL,
            "tool_name": "price_quote",
            "tool_description": "Quote a price for a SKU and quantity.",
            "tool_schema": QUOTE_SCHEMA,
            "arg_mode": "fields",
            "output_variable": "quote",
            # One row per parameter the server declared. `currency` has no
            # source: a fixed value, which is how an argument the workflow
            # decides rather than reads is sent.
            "arg_fields": [
                {"name": "sku", "type": "string", "source": "data.code",
                 "required": True},
                {"name": "quantity", "type": "integer", "source": "data.units",
                 "required": True},
                {"name": "currency", "type": "string", "default": "GBP"},
            ],
        }, 800, 240),

        _node("invoice", "TRANSFORM", "Invoice Line", {
            "mode": "fields",
            "output_fields": [
                # The tool's own keys are on the payload, so they are picked
                # here like anything else.
                {"name": "description", "type": "string", "source": "data.sku",
                 "required": True},
                {"name": "quantity", "type": "integer", "source": "data.quantity",
                 "required": True},
                {"name": "amount", "type": "number", "source": "data.total",
                 "required": True},
                {"name": "currency", "type": "string", "source": "data.currency"},
                # And so is the entry payload, by variable name.
                {"name": "ordered_as", "type": "string", "source": "vars.order.item"},
            ],
        }, 1180, 240),

        _node("done", "END", "Done", {"output_mapping": {}}, 1560, 240),
    ],
    "edges": [
        _edge("e1", "trigger", "normalise"),
        _edge("e2", "normalise", "quote"),
        _edge("e3", "quote", "invoice"),
        _edge("e4", "invoice", "done"),
    ],
}


def seed():
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{BASE}/workflows", json={
            "name": "MCP Tool Call",
            "description": (
                "Calls one tool on an MCP server as a step in the flow, with "
                "its arguments mapped from what earlier nodes produced."
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
