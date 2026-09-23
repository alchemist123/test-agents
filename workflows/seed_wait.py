"""
Workflow 8: Wait
────────────────
A2A_START → PARALLEL_FORK → [poll]  → WAIT (3s) → TRANSFORM (checked) ─┐
                          → [notify] → WAIT (1s) → TRANSFORM (sent) ───┴─ MERGE → END

Two branches, each with a pause. The whole run takes about as long as the
*longer* wait, not the sum of both — `asyncio.sleep` yields the event loop, so a
branch that is waiting does not hold up the one beside it.

ADK has no delay node of its own, so WAIT is `asyncio.sleep` in a generated
node. Two things follow, and both are handled for you:

  * the wait lives in the running process, so a restart loses the run
  * ADK kills a node that outlives its execution timeout, so this node's
    timeout is derived from the wait rather than from the canvas policy

Past a minute, invoke the workflow in **task mode** and poll: a blocking caller
would otherwise hold its connection open for the whole wait.

Runs entirely offline: no model, no MCP server, no credentials.
"""
import sys

import httpx

BASE = "http://localhost:8001/api/v1"


def _node(node_id, node_type, title, config, x, y):
    return {
        "id": node_id,
        "type": node_type,
        "version": "1",
        "position": {"x": x, "y": y},
        "metadata": {"title": title, "description": ""},
        "config": config,
        "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
        "policies": {"timeout_seconds": 120, "retry": {"max_attempts": 1}, "on_error": "fail"},
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
        _node("trigger", "A2A_START", "Start", {
            "input_mode": "json",
            "state_key": "wf",
            "payload_schema": {"fields": [
                {"name": "order_id", "type": "string",
                 "description": "Order to settle", "required": True},
            ]},
        }, 40, 240),

        _node("fork", "PARALLEL_FORK", "Split", {
            # PARALLEL_FORK names its branches as plain strings.
            "branches": ["poll", "notify"],
        }, 440, 240),

        _node("settle", "WAIT", "Let it settle", {
            "duration": 3, "unit": "seconds",
        }, 860, 100),
        _node("checked", "TRANSFORM", "Check Status", {
            "mode": "python",
            "expression": "result = {'status': 'settled'}",
        }, 1260, 100),

        _node("cooloff", "WAIT", "Rate limit", {
            "duration": 1, "unit": "seconds",
        }, 860, 400),
        _node("sent", "TRANSFORM", "Send Receipt", {
            "mode": "python",
            "expression": "result = {'receipt': 'sent'}",
        }, 1260, 400),

        _node("join", "MERGE", "Join", {}, 1660, 240),
        _node("end", "END", "End", {"output_mapping": {}}, 2060, 240),
    ],
    "edges": [
        _edge("e1", "trigger", "fork"),
        _edge("e2", "fork", "settle", "poll"),
        _edge("e3", "fork", "cooloff", "notify"),
        _edge("e4", "settle", "checked"),
        _edge("e5", "cooloff", "sent"),
        _edge("e6", "checked", "join"),
        _edge("e7", "sent", "join"),
        _edge("e8", "join", "end"),
    ],
}


def seed():
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{BASE}/workflows", json={
            "name": "Wait",
            "description": (
                "Two branches each pausing, to show a wait does not hold up "
                "the branch beside it."
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
