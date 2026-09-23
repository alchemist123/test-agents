"""
Workflow 10: Field Mapping
──────────────────────────
A2A_START ─▶ TRANSFORM ─▶ TRANSFORM ─▶ END
  order       "fields"     "fields"
              shipment     invoice line

A TRANSFORM in `fields` mode declares the shape it builds instead of holding an
expression. Each output field names its type and where its value comes from,
and the source is picked from a list rather than typed: the compiler works out
what is readable at a node — the entry payload's declared fields, any earlier
`fields` transform's output, and every named variable — and offers exactly
that. Picking a path that nothing produces is then not a thing that can happen
by accident, and the compiler says so if a saved workflow is edited into that
state.

Three things this seed exercises that a text box could not check:

  * `qty` is an integer on the way in and `quantity_label` is a string on the
    way out, so the value is converted rather than rejected;
  * `gift_message` is optional, and when it is absent the key is *left out* of
    the result rather than set to null — `"gift_message" in data` is how a
    later node asks, and a null would answer it wrongly;
  * `Invoice Line` maps from `Shipment`'s output, which it knows only because
    `Shipment` declares its own shape. Mappers chain.

Try it:

    python run_once.py '{"sku": "WIDGET", "qty": 4, "gift_message": "enjoy"}'
    python run_once.py '{"sku": "WIDGET", "qty": 4}'    -> no gift_message key

Runs entirely offline: no model, no MCP server, no credentials.
"""
import sys

import httpx

BASE = "http://localhost:8001/api/v1"
UNIT_PRICE = 25


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
            # Naming the entry payload puts it in the picker as `vars.order.*`
            # as well as `data.*`, so a later node can still reach it once the
            # edge no longer carries it.
            "output_variable": "order",
            "payload_schema": {"fields": [
                {"name": "sku", "type": "string", "description": "What was ordered",
                 "required": True},
                {"name": "qty", "type": "integer", "description": "How many",
                 "required": True},
                {"name": "gift_message", "type": "string",
                 "description": "Optional note for the recipient", "required": False},
            ]},
        }, 40, 240),

        _node("shipment", "TRANSFORM", "Shipment", {
            "mode": "fields",
            "output_variable": "shipment",
            "output_fields": [
                # Renamed straight across, and required: the run fails loudly
                # rather than shipping a line with no product on it.
                {"name": "product_code", "type": "string",
                 "source": "data.sku", "required": True},
                {"name": "units", "type": "integer",
                 "source": "data.qty", "required": True},
                # An integer asked for as a string: 4 -> "4".
                {"name": "quantity_label", "type": "string", "source": "data.qty"},
                # No source at all — a constant, which is how a mapper adds a
                # field the input never carried.
                {"name": "carrier", "type": "string", "default": "standard-post"},
                # Optional: absent from the result when absent from the input.
                {"name": "gift_message", "type": "string", "source": "data.gift_message"},
            ],
        }, 480, 240),

        _node("invoice", "TRANSFORM", "Invoice Line", {
            "mode": "fields",
            "output_variable": "invoice",
            "output_fields": [
                # Reads what the node before it declared.
                {"name": "item", "type": "string",
                 "source": "data.product_code", "required": True},
                {"name": "quantity", "type": "integer",
                 "source": "data.units", "required": True},
                # And reaches back past it, by variable name, for something the
                # shipment step did not pass on.
                {"name": "ordered_sku", "type": "string", "source": "vars.order.sku"},
                {"name": "currency", "type": "string", "default": "EUR"},
            ],
        }, 920, 240),

        _node("done", "END", "Done", {"output_mapping": {}}, 1360, 240),
    ],
    "edges": [
        _edge("e1", "trigger", "shipment"),
        _edge("e2", "shipment", "invoice"),
        _edge("e3", "invoice", "done"),
    ],
}


def seed():
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{BASE}/workflows", json={
            "name": "Field Mapping",
            "description": (
                "Transforms that declare the shape they build and pick each "
                "field's source from what is actually available upstream."
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
